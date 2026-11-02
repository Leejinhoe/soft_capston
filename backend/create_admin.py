"""관리자 계정 만들기 / 기존 계정을 관리자로 바꾸기.

사용법 (backend 폴더에서, venv 활성화 후):
    python create_admin.py <관리자아이디> [표시이름]

- 비밀번호는 화면에 보이지 않게 입력받습니다. (명령어 기록에 남지 않음)
- 같은 아이디가 이미 있으면, 확인 후 role을 admin으로 바꾸고 비밀번호를 새로 설정합니다.
"""
import asyncio
import getpass
import sys
from datetime import datetime

import bcrypt

from database import users_collection
from security import ROLE_ADMIN, STATUS_ACTIVE, new_user_defaults

MIN_PASSWORD_LENGTH = 8


def ask_password() -> str:
    while True:
        pw = getpass.getpass("관리자 비밀번호: ")
        if len(pw) < MIN_PASSWORD_LENGTH:
            print(f"비밀번호는 {MIN_PASSWORD_LENGTH}자 이상이어야 해요.")
            continue
        if pw != getpass.getpass("비밀번호 확인: "):
            print("두 비밀번호가 달라요. 다시 입력해 주세요.")
            continue
        return pw


async def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1

    admin_id = sys.argv[1].strip()
    name = sys.argv[2].strip() if len(sys.argv) > 2 else "관리자"
    if not admin_id:
        print("아이디를 입력해 주세요.")
        return 1

    existing = await users_collection.find_one({"id": admin_id})
    if existing:
        answer = input(
            f"'{admin_id}' 계정이 이미 있어요 (role={existing.get('role', 'user')}). "
            "관리자로 바꾸고 비밀번호를 새로 설정할까요? [y/N]: "
        )
        if answer.strip().lower() != "y":
            print("취소했어요.")
            return 1

    hashed = bcrypt.hashpw(ask_password().encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    if existing:
        await users_collection.update_one(
            {"_id": existing["_id"]},
            {"$set": {"role": ROLE_ADMIN, "status": STATUS_ACTIVE, "password": hashed}},
        )
        print(f"✅ '{admin_id}' 계정을 관리자로 바꿨어요.")
    else:
        await users_collection.insert_one({
            "id": admin_id,
            "password": hashed,
            "name": name,
            "nickname": name,
            "email": None,
            "birth": None,
            **new_user_defaults(),
            "role": ROLE_ADMIN,
            "created_at": datetime.utcnow(),
        })
        print(f"✅ 관리자 계정 '{admin_id}'을(를) 만들었어요.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
