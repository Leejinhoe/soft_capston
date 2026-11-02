"""소셜 로그인(OAuth) 토큰 교환/사용자 정보 조회. JWT 발급은 security.py에서 합니다."""
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY")
KAKAO_REDIRECT_URI = os.getenv("KAKAO_REDIRECT_URI")

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
NAVER_REDIRECT_URI = os.getenv("NAVER_REDIRECT_URI")

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")


async def get_kakao_access_token(code: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://kauth.kakao.com/oauth/token",
            data={
                "grant_type": "authorization_code",
                "client_id": KAKAO_REST_API_KEY,
                "redirect_uri": KAKAO_REDIRECT_URI,
                "code": code,
            },
        )
    token_data = response.json()
    print("카카오 응답:", token_data)

    if "access_token" not in token_data:
        raise Exception(f"카카오 토큰 발급 실패: {token_data}")

    return token_data["access_token"]


async def get_kakao_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    data = response.json()
    return {
        "kakao_id": str(data["id"]),
        "nickname": data["kakao_account"]["profile"]["nickname"],
        "email": data["kakao_account"].get("email", ""),
    }


async def get_naver_access_token(code: str, state: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://nid.naver.com/oauth2.0/token",
            params={
                "grant_type": "authorization_code",
                "client_id": NAVER_CLIENT_ID,
                "client_secret": NAVER_CLIENT_SECRET,
                "code": code,
                "state": state,
                "redirect_uri": NAVER_REDIRECT_URI,
            },
        )

    token_data = response.json()
    print("네이버 토큰 응답:", token_data)

    if "access_token" not in token_data:
        raise Exception(f"네이버 토큰 발급 실패: {token_data}")

    return token_data["access_token"]


async def get_naver_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://openapi.naver.com/v1/nid/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    data = response.json()
    print("네이버 사용자 정보 응답:", data)

    profile = data.get("response", {})

    name = profile.get("name", "")
    nickname = profile.get("nickname", "") or name

    return {
        "social_id": str(profile.get("id", "")),
        "nickname": nickname,
        "email": profile.get("email", ""),
        "profile_image": profile.get("profile_image", ""),
        "name": name,
    }

async def get_google_access_token(code: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded"
            },
        )

    token_data = response.json()
    print("구글 토큰 응답:", token_data)

    if "access_token" not in token_data:
        raise Exception(f"구글 토큰 발급 실패: {token_data}")

    return token_data["access_token"]

async def get_google_user_info(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    data = response.json()
    print("구글 사용자 정보 응답:", data)

    return {
        "social_id": str(data.get("id", "")),
        "nickname": data.get("name", ""),
        "email": data.get("email", ""),
        "profile_image": data.get("picture", ""),
        "name": data.get("name", ""),
    }
