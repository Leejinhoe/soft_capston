"""비밀번호 재설정: 아이디 + 가입 이메일 → 6자리 인증번호 메일 → 확인 → 새 비밀번호.

흐름
1. POST /api/auth/password-reset/request {id, email}
   - 계정이 있든 없든, 맞든 틀리든 같은 응답을 돌려줍니다. (계정 존재 여부가 드러나지 않게)
   - 아이디·이메일 조합마다 password_resets 문서를 하나 만들어 두고(계정이 없어도 만듦),
     계정이 있고 재설정 가능한 경우에만 실제 인증번호 메일을 보냅니다.
   - 소셜 계정/정지 계정이면 인증번호 대신 "카카오/네이버/구글에서 관리해요" / "정지 계정은 재설정할 수 없어요"
     안내 메일을 그 이메일로 보냅니다. (화면에는 똑같은 안내만 보임)
   - 재발송은 마지막 발송 1분 뒤부터. 새로 보내면 예전 인증번호는 무효.
2. POST /api/auth/password-reset/verify {id, email, code}
   - 10분 유효, 5번 틀리면 무효 → 다시 받아야 함. 맞으면 reset_token(10분 유효)을 돌려줍니다.
3. POST /api/auth/password-reset/confirm {reset_token, new_password}
   - 회원가입과 같은 비밀번호 규칙. 성공하면 문서 삭제.

저장: 아이디/이메일/인증번호/토큰은 원문 대신 EMAIL_VERIFICATION_PEPPER로 HMAC한 값만 저장합니다.
"""
import hashlib
import hmac
import logging
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from database import database, safe_create_index, users_collection
from mailer import APP_NAME, esc, info_table, render_mail, send_mail
from security import CONTACT_EMAIL, PASSWORD_RULE_MESSAGE, is_banned, is_social_user, is_strong_password

load_dotenv()

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["password-reset"])

password_resets_collection = database.get_collection("password_resets")

PEPPER = (os.getenv("EMAIL_VERIFICATION_PEPPER") or "").encode("utf-8")
CODE_TTL = timedelta(minutes=10)
TOKEN_TTL = timedelta(minutes=10)
RESEND_AFTER = timedelta(minutes=1)
MAX_ATTEMPTS = 5

REQUEST_MESSAGE = (
    "입력한 아이디와 이메일이 가입 정보와 맞으면 인증번호를 보냈어요. "
    "메일함(스팸함도)을 확인해 주세요."
)
CODE_INVALID = "인증번호가 맞지 않아요. 다시 확인해 주세요."
CODE_EXPIRED = "인증번호가 만료되었어요. 인증번호를 다시 받아 주세요."
CODE_LOCKED = f"인증번호를 {MAX_ATTEMPTS}번 틀렸어요. 인증번호를 다시 받아 주세요."
TOKEN_INVALID = "인증 시간이 지났어요. 처음부터 다시 해 주세요."
SOCIAL_GUIDE = "카카오/네이버/구글로 가입한 계정은 비밀번호를 각 서비스에서 관리해요."


# ----------------------------------------
# 스키마
# ----------------------------------------
class ResetRequest(BaseModel):
    id: str
    email: str


class ResetRequestResponse(BaseModel):
    success: bool
    message: str
    resend_after_seconds: int
    expires_in_seconds: int


class ResetVerifyRequest(BaseModel):
    id: str
    email: str
    code: str


class ResetVerifyResponse(BaseModel):
    success: bool
    message: str
    reset_token: str


class ResetConfirmRequest(BaseModel):
    reset_token: str
    new_password: str


class ResetConfirmResponse(BaseModel):
    success: bool
    message: str


# ----------------------------------------
# 도우미
# ----------------------------------------
def _require_pepper() -> None:
    if not PEPPER:
        logger.error("[password-reset] EMAIL_VERIFICATION_PEPPER가 .env에 없어 비밀번호 재설정을 쓸 수 없음")
        raise HTTPException(status_code=503, detail="지금은 비밀번호 찾기를 쓸 수 없어요. 잠시 후 다시 해 주세요.")


def _hmac(*parts: str) -> str:
    return hmac.new(PEPPER, "\x1f".join(parts).encode("utf-8"), hashlib.sha256).hexdigest()


def _normalize(login_id: str, email: str) -> tuple[str, str]:
    return (login_id or "").strip(), (email or "").strip().lower()


def _key(login_id: str, email: str) -> str:
    """아이디+이메일 조합의 키 (원문 대신 저장)"""
    return _hmac("key", login_id, email)


def _code_hash(key: str, code: str) -> str:
    return _hmac("code", key, code)


def _email_hash(email: str) -> str:
    return _hmac("email", email)


def _token_hash(token: str) -> str:
    return _hmac("token", token)


def _new_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


async def ensure_indexes() -> None:
    await safe_create_index(password_resets_collection, "key", name="pwreset_key_idx", unique=True)
    await safe_create_index(password_resets_collection, "token_hash", name="pwreset_token_idx", sparse=True)
    await safe_create_index(password_resets_collection, [("email_hash", 1), ("last_sent_at", -1)], name="pwreset_email_idx")
    # 만료된 문서는 MongoDB가 알아서 지웁니다.
    await safe_create_index(password_resets_collection, "expires_at", name="pwreset_ttl_idx", expireAfterSeconds=0)


async def _find_account(login_id: str, email: str) -> Optional[dict]:
    """아이디 + 가입 이메일이 모두 맞는 계정. 일반 계정은 아이디로, 소셜 계정은 이메일로만 찾습니다."""
    if login_id:
        user = await users_collection.find_one({"id": login_id})
        if user and (user.get("email") or "").strip().lower() == email:
            return user
    # 소셜 계정은 사용자가 알고 있는 아이디가 없어서, 같은 이메일의 소셜 계정이 있으면 안내 메일만 보냅니다.
    async for user in users_collection.find({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}}).limit(5):
        if is_social_user(user):
            return user
    return None


# ----------------------------------------
# 메일 내용
# ----------------------------------------
async def _send_code_mail(to: str, code: str) -> None:
    body = (
        "<p style='margin:0 0 8px;'>비밀번호를 다시 만들기 위한 인증번호예요.</p>"
        "<div style='margin:20px 0;padding:18px;text-align:center;background:#f5f3ff;border-radius:14px;'>"
        f"<span style='font-size:32px;letter-spacing:10px;font-weight:bold;color:#6d28d9;'>{esc(code)}</span></div>"
        f"<p style='margin:0 0 4px;'>앱 화면에 인증번호를 넣어 주세요. <b>10분 동안</b>만 쓸 수 있고, "
        f"{MAX_ATTEMPTS}번 틀리면 다시 받아야 해요.</p>"
        "<p style='margin:12px 0 0;color:#8a7fa8;font-size:13px;'>비밀번호 찾기를 한 적이 없다면 이 메일은 무시해 주세요. "
        "다른 사람은 이 인증번호 없이는 비밀번호를 바꿀 수 없어요.</p>"
    )
    text = (
        f"[{APP_NAME}] 비밀번호 재설정 인증번호: {code}\n\n"
        f"10분 동안만 쓸 수 있고, {MAX_ATTEMPTS}번 틀리면 다시 받아야 해요.\n"
        "비밀번호 찾기를 한 적이 없다면 이 메일은 무시해 주세요."
    )
    await send_mail(to, "비밀번호 재설정 인증번호", render_mail("비밀번호 재설정 인증번호", body), text, kind="reset:code")


async def _send_social_mail(to: str, provider: str) -> None:
    name = {"kakao": "카카오", "naver": "네이버", "google": "구글"}.get(provider or "", "카카오/네이버/구글")
    msg = f"이 이메일로 가입된 계정은 {name} 로그인 계정이라 {APP_NAME}에서 따로 비밀번호를 쓰지 않아요."
    body = (
        f"<p style='margin:0 0 8px;'>{esc(msg)}</p>"
        f"<p style='margin:0 0 8px;'>로그인 화면에서 <b>{esc(name)}로 시작하기</b>를 눌러 주세요. "
        f"비밀번호는 {esc(name)}에서 관리해요.</p>"
        "<p style='margin:12px 0 0;color:#8a7fa8;font-size:13px;'>비밀번호 찾기를 한 적이 없다면 이 메일은 무시해 주세요.</p>"
    )
    text = f"{msg}\n로그인 화면에서 '{name}로 시작하기'를 눌러 주세요. 비밀번호는 {name}에서 관리해요."
    await send_mail(to, "비밀번호 찾기 안내", render_mail("비밀번호 찾기 안내", body), text, kind="reset:social")


async def _send_banned_mail(to: str) -> None:
    contact = CONTACT_EMAIL or "이 메일의 답장"
    msg = "이용이 정지된 계정이라 비밀번호를 다시 만들 수 없어요."
    body = (
        f"<p style='margin:0 0 8px;'>{esc(msg)}</p>"
        + info_table([("문의", contact)])
        + "<p style='margin:0;'>정지에 대해 궁금한 점은 이 메일에 답장해 주세요.</p>"
    )
    text = f"{msg}\n문의: {contact}\n정지에 대해 궁금한 점은 이 메일에 답장해 주세요."
    await send_mail(to, "비밀번호 찾기 안내", render_mail("비밀번호 찾기 안내", body), text, kind="reset:banned")


# ----------------------------------------
# API
# ----------------------------------------
@router.post("/api/auth/password-reset/request", response_model=ResetRequestResponse)
async def request_password_reset(body: ResetRequest, background_tasks: BackgroundTasks):
    _require_pepper()
    login_id, email = _normalize(body.id, body.email)
    if not login_id or not email:
        raise HTTPException(status_code=400, detail="아이디와 가입한 이메일을 모두 입력해 주세요.")

    response = ResetRequestResponse(
        success=True,
        message=REQUEST_MESSAGE,
        resend_after_seconds=int(RESEND_AFTER.total_seconds()),
        expires_in_seconds=int(CODE_TTL.total_seconds()),
    )
    key = _key(login_id, email)
    now = datetime.utcnow()

    existing = await password_resets_collection.find_one({"key": key})
    if existing and existing.get("last_sent_at") and now - existing["last_sent_at"] < RESEND_AFTER:
        left = RESEND_AFTER - (now - existing["last_sent_at"])
        raise HTTPException(status_code=429, detail=f"인증번호는 {int(left.total_seconds()) + 1}초 뒤에 다시 받을 수 있어요.")

    # 아이디만 바꿔 가며 같은 이메일로 메일을 계속 보내는 것도 1분에 1통으로 막습니다. (화면 응답은 똑같음)
    email_hash = _email_hash(email)
    mailed_recently = await password_resets_collection.find_one(
        {"email_hash": email_hash, "key": {"$ne": key}, "last_sent_at": {"$gt": now - RESEND_AFTER}}, {"_id": 1}
    )

    user = await _find_account(login_id, email)
    code = _new_code()
    # 계정이 없어도 똑같이 문서를 만들어, 확인 단계에서도 응답이 똑같게 합니다.
    await password_resets_collection.update_one(
        {"key": key},
        {
            "$set": {
                "code_hash": _code_hash(key, code),
                "attempts": 0,
                "user_oid": user["_id"] if user else None,
                "email_hash": email_hash,
                "last_sent_at": now,
                "expires_at": now + CODE_TTL,
                "verified_at": None,
                "token_hash": None,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )

    if user is None or mailed_recently:
        return response
    to = (user.get("email") or "").strip()
    if is_social_user(user):
        background_tasks.add_task(_send_social_mail, to, user.get("provider") or "")
    elif is_banned(user):
        background_tasks.add_task(_send_banned_mail, to)
    else:
        background_tasks.add_task(_send_code_mail, to, code)
    return response


@router.post("/api/auth/password-reset/verify", response_model=ResetVerifyResponse)
async def verify_password_reset(body: ResetVerifyRequest):
    _require_pepper()
    login_id, email = _normalize(body.id, body.email)
    code = (body.code or "").strip()
    key = _key(login_id, email)
    now = datetime.utcnow()

    doc = await password_resets_collection.find_one({"key": key})
    if not doc or not doc.get("code_hash"):
        raise HTTPException(status_code=400, detail=CODE_EXPIRED)
    if doc["expires_at"] < now:
        raise HTTPException(status_code=400, detail=CODE_EXPIRED)
    if int(doc.get("attempts") or 0) >= MAX_ATTEMPTS:
        raise HTTPException(status_code=400, detail=CODE_LOCKED)

    if not (code.isdigit() and len(code) == 6 and hmac.compare_digest(doc["code_hash"], _code_hash(key, code))):
        result = await password_resets_collection.find_one_and_update(
            {"_id": doc["_id"]}, {"$inc": {"attempts": 1}}, return_document=True
        )
        attempts = int((result or {}).get("attempts") or MAX_ATTEMPTS)
        if attempts >= MAX_ATTEMPTS:
            await password_resets_collection.update_one({"_id": doc["_id"]}, {"$set": {"code_hash": None}})
            raise HTTPException(status_code=400, detail=CODE_LOCKED)
        raise HTTPException(status_code=400, detail=f"{CODE_INVALID} (남은 기회 {MAX_ATTEMPTS - attempts}번)")

    # 인증번호가 맞더라도 재설정할 수 없는 계정(없음/소셜/정지)은 여기서 막습니다.
    # (이 경우는 메일로 인증번호를 받지 못했으므로 실제로는 맞힐 수 없음)
    user = await users_collection.find_one({"_id": doc["user_oid"]}) if doc.get("user_oid") else None
    if not user or is_social_user(user) or is_banned(user):
        await password_resets_collection.delete_one({"_id": doc["_id"]})
        raise HTTPException(status_code=400, detail=CODE_EXPIRED)

    token = secrets.token_urlsafe(32)
    await password_resets_collection.update_one(
        {"_id": doc["_id"]},
        {"$set": {"code_hash": None, "verified_at": now, "token_hash": _token_hash(token), "expires_at": now + TOKEN_TTL}},
    )
    return ResetVerifyResponse(success=True, message="확인됐어요! 새 비밀번호를 만들어 주세요.", reset_token=token)


@router.post("/api/auth/password-reset/confirm", response_model=ResetConfirmResponse)
async def confirm_password_reset(body: ResetConfirmRequest):
    _require_pepper()
    token = (body.reset_token or "").strip()
    now = datetime.utcnow()
    doc = await password_resets_collection.find_one({"token_hash": _token_hash(token)}) if token else None
    if not doc or not doc.get("verified_at") or doc["expires_at"] < now:
        raise HTTPException(status_code=400, detail=TOKEN_INVALID)

    user = await users_collection.find_one({"_id": doc.get("user_oid")})
    if not user or is_social_user(user):
        await password_resets_collection.delete_one({"_id": doc["_id"]})
        raise HTTPException(status_code=400, detail=TOKEN_INVALID)
    if is_banned(user):
        await password_resets_collection.delete_one({"_id": doc["_id"]})
        raise HTTPException(status_code=403, detail="이용이 정지된 계정은 비밀번호를 다시 만들 수 없어요.")

    if not is_strong_password(body.new_password):
        raise HTTPException(status_code=400, detail=PASSWORD_RULE_MESSAGE)

    hashed = bcrypt.hashpw(body.new_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    await users_collection.update_one(
        {"_id": user["_id"]}, {"$set": {"password": hashed, "password_changed_at": now}}
    )
    await password_resets_collection.delete_one({"_id": doc["_id"]})
    return ResetConfirmResponse(success=True, message="비밀번호를 새로 만들었어요. 새 비밀번호로 로그인해 주세요.")
