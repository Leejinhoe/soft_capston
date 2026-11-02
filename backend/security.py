"""JWT 발급/검증과 로그인·관리자 권한 의존성.

- 토큰의 sub = 사용자의 공개 id (일반: id, 카카오: kakao_id, 네이버/구글: social_id)
- 매 요청마다 DB에서 사용자를 다시 읽어 role/status를 확인합니다. (정지가 즉시 반영됨)
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

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

BANNED_MESSAGE = "이용이 정지된 계정이에요. 관리자에게 문의해 주세요."

_bearer = HTTPBearer(auto_error=False)


def public_user_id(user: dict) -> str:
    return str(user.get("id") or user.get("social_id") or user.get("kakao_id") or "")


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


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def find_user_by_public_id(user_id: str) -> Optional[dict]:
    if not user_id:
        return None
    return await users_collection.find_one(
        {"$or": [{"id": user_id}, {"social_id": user_id}, {"kakao_id": user_id}]}
    )


def is_banned(user: dict) -> bool:
    return user.get("status") == STATUS_BANNED


def banned_exception() -> HTTPException:
    # 프론트가 정지 상태를 구분할 수 있도록 code를 함께 보냅니다.
    return HTTPException(status_code=403, detail={"code": "banned", "message": BANNED_MESSAGE})


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
