"""JWT 발급/검증과 로그인·관리자 권한 의존성.

- 토큰의 sub = 사용자의 공개 id (일반: id, 카카오: kakao_id, 네이버/구글: social_id)
- 매 요청마다 DB에서 사용자를 다시 읽어 role/status를 확인합니다. (정지가 즉시 반영됨)
"""
import os
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from bson import ObjectId
from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from database import users_collection

load_dotenv()

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7

if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET이 backend/.env에 없습니다.")

ROLE_USER = "user"
ROLE_ADMIN = "admin"
STATUS_ACTIVE = "active"
STATUS_BANNED = "banned"

# 정지 안내에 보여 줄 문의 메일 주소 (메일 보내는 계정과 같은 주소)
CONTACT_EMAIL = (os.getenv("SMTP_USER") or "").strip()
BANNED_MESSAGE = (
    f"이용이 정지된 계정이에요. 궁금한 점은 {CONTACT_EMAIL} 로 메일을 보내 주세요."
    if CONTACT_EMAIL else "이용이 정지된 계정이에요. 관리자에게 문의해 주세요."
)

_bearer = HTTPBearer(auto_error=False)


# 공개 id로 쓰는 필드. 초창기(팀원 스키마, schema_version) 회원은 이 필드가 없고 account_id만 있는데,
# 그 회원들의 동화·단어장은 user_id = str(_id)로 연결돼 있어서 공개 id도 str(_id)를 씁니다.
PUBLIC_ID_FIELDS = ("id", "social_id", "kakao_id")
# 사용자 문서를 찾을 때 공개 id 계산에 필요한 필드 (projection에 그대로 넣어 쓰기, _id는 기본 포함)
ID_PROJECTION = {"id": 1, "social_id": 1, "kakao_id": 1, "account_id": 1}


def public_user_id(user: dict) -> str:
    for field in PUBLIC_ID_FIELDS:
        if user.get(field):
            return str(user[field])
    return str(user["_id"]) if user.get("_id") else ""


def login_id(user: dict) -> str:
    """화면에 보여 줄 아이디 (초창기 회원은 account_id)."""
    return str(user.get("id") or user.get("account_id") or user.get("social_id") or user.get("kakao_id") or public_user_id(user))


def _no_public_id_fields() -> dict:
    return {field: None for field in PUBLIC_ID_FIELDS}  # None은 "필드 없음"도 포함


def public_id_query(ids: list[str]) -> dict:
    """공개 id 목록에 해당하는 사용자들을 찾는 쿼리 (초창기 회원의 str(_id)도 포함)."""
    oids = [ObjectId(i) for i in ids if ObjectId.is_valid(i)]
    conditions: list[dict] = [{field: {"$in": ids}} for field in PUBLIC_ID_FIELDS]
    if oids:
        conditions.append({"_id": {"$in": oids}, **_no_public_id_fields()})
    return {"$or": conditions}


def user_summary(user: dict) -> dict:
    """프론트에 내려줄 최소 사용자 정보."""
    uid = public_user_id(user)
    return {
        "id": uid,
        "name": user.get("nickname") or user.get("name") or uid or "사용자",
        "role": user.get("role", ROLE_USER),
        "status": user.get("status", STATUS_ACTIVE),
    }


def new_user_defaults() -> dict:
    """새 사용자 문서에 들어갈 기본 필드 (회원가입/소셜 첫 로그인 공통)."""
    return {
        "role": ROLE_USER,
        "status": STATUS_ACTIVE,
        "warnings": [],
        "warning_count": 0,
        "created_at": datetime.utcnow(),
    }


# 회원가입 화면(signup_page.dart)과 같은 규칙: 영문 소문자/대문자/숫자/특수문자 중 3가지 이상
_PASSWORD_RULES = [r"[a-z]", r"[A-Z]", r"[0-9]", r'[!@#$%^&*(),.?":{}|<>]']
PASSWORD_RULE_MESSAGE = "비밀번호는 영문 대/소문자, 숫자, 특수문자 중 3가지 이상을 섞어 주세요."


def is_strong_password(password: str) -> bool:
    return sum(1 for rule in _PASSWORD_RULES if re.search(rule, password or "")) >= 3


def is_social_user(user: dict) -> bool:
    """비밀번호 없이 소셜(카카오/네이버/구글)로만 로그인하는 계정인지."""
    return not user.get("password")


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def find_user_by_public_id(user_id: str) -> Optional[dict]:
    if not user_id:
        return None
    user = await users_collection.find_one({"$or": [{field: user_id} for field in PUBLIC_ID_FIELDS]})
    if user is None and ObjectId.is_valid(user_id):
        # 초창기 회원: 공개 필드가 하나도 없는 문서만 _id로 찾습니다. (일반 아이디와 섞이지 않게)
        user = await users_collection.find_one({"_id": ObjectId(user_id), **_no_public_id_fields()})
    return user


def is_banned(user: dict) -> bool:
    return user.get("status") == STATUS_BANNED


def banned_exception() -> HTTPException:
    # 프론트가 정지 상태를 구분할 수 있도록 code를 함께 보냅니다.
    return HTTPException(
        status_code=403,
        detail={"code": "banned", "message": BANNED_MESSAGE, "contact_email": CONTACT_EMAIL},
    )


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=401,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    """로그인한 사용자 문서를 돌려줍니다. user["user_id"]에 공개 id가 들어 있습니다."""
    if credentials is None or not credentials.credentials:
        raise _unauthorized("로그인이 필요해요.")

    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError:
        raise _unauthorized("로그인이 만료되었어요. 다시 로그인해 주세요.")

    user = await find_user_by_public_id(str(payload.get("sub") or ""))
    if not user:
        raise _unauthorized("사용자 정보를 찾을 수 없어요. 다시 로그인해 주세요.")
    if is_banned(user):
        raise banned_exception()

    user["user_id"] = public_user_id(user)
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="관리자만 사용할 수 있어요.")
    return user
