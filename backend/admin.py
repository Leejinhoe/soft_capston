"""관리자 기능: 요약 숫자, 회원 관리, 동화 관리, 공지사항.

- 모든 API는 /api/admin/... + require_admin
- 신고 관리는 reports.py에 있습니다. (신고 상세 화면이 쓰는 PUT /admin/warning/{user_id}도 여기서 계속 지원)
- 회원 id는 공개 id(일반: id, 카카오: kakao_id, 네이버/구글: social_id)를 씁니다.
"""
import re
from datetime import datetime, timedelta
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from community import remove_post_relations
from database import (
    comments_collection,
    direct_messages_collection,
    notices_collection,
    notifications_collection,
    post_likes_collection,
    post_scraps_collection,
    posts_collection,
    reports_collection,
    stories_collection,
    users_collection,
    vocabularies_collection,
)
from security import (
    ROLE_ADMIN,
    ROLE_USER,
    STATUS_ACTIVE,
    STATUS_BANNED,
    find_user_by_public_id,
    public_user_id,
    require_admin,
)

router = APIRouter(tags=["admin"])

USER_NOT_FOUND = "회원을 찾을 수 없어요."
STORY_NOT_FOUND = "동화를 찾지 못했어요."
NOTICE_NOT_FOUND = "공지사항을 찾지 못했어요."
KST = timedelta(hours=9)  # DB의 created_at은 UTC. "오늘"은 한국 시간 기준으로 셉니다.

UserStatus = Literal["active", "banned"]
NoticeTarget = Literal["all", "users"]


# ----------------------------------------
# 스키마
# ----------------------------------------
class AdminSummary(BaseModel):
    total_users: int
    pending_reports: int
    today_stories: int


class AdminUserItem(BaseModel):
    id: str
    nickname: str
    name: str
    email: str = ""
    role: str = ROLE_USER
    status: str = STATUS_ACTIVE
    warning_count: int = 0
    provider: str = ""           # "" = 일반 가입, kakao / naver / google
    created_at: str = ""


class AdminUserListResponse(BaseModel):
    items: list[AdminUserItem]
    page: int
    size: int
    total: int
    has_more: bool


class AdminWarningItem(BaseModel):
    reason: str
    admin_id: str = ""
    created_at: str = ""


class AdminUserDetail(AdminUserItem):
    birth: str = ""
    bio: str = ""
    profile_image_url: Optional[str] = None
    last_login: str = ""
    warnings: list[AdminWarningItem]
    story_count: int = 0
    post_count: int = 0
    comment_count: int = 0
    reports_received: int = 0


class WarningCreateRequest(BaseModel):
    reason: str


class LegacyWarningRequest(BaseModel):
    reason: Optional[str] = ""


class WarningResponse(BaseModel):
    success: bool
    warning_count: int


class UserStatusRequest(BaseModel):
    status: UserStatus


class SimpleResult(BaseModel):
    success: bool
    message: str = ""


class DeleteUserResult(SimpleResult):
    deleted_posts: int = 0
    deleted_comments: int = 0
    deleted_stories: int = 0


class StoryAuthor(BaseModel):
    id: str
    nickname: str
    exists: bool = True          # 탈퇴한 회원이면 False


class AdminStoryItem(BaseModel):
    id: str
    title: str
    genre: str = ""
    author: StoryAuthor
    created_at: str = ""
    shared: bool = False         # 커뮤니티에 공유됨
    post_id: str = ""            # 연결된 게시글 id (공유됐을 때)


class AdminStoryDetail(AdminStoryItem):
    content: str = ""
    updated_at: str = ""


class AdminStoryListResponse(BaseModel):
    items: list[AdminStoryItem]
    page: int
    size: int
    total: int
    has_more: bool


class NoticeTargetUser(BaseModel):
    id: str
    nickname: str
    exists: bool = True


class AdminNoticeItem(BaseModel):
    id: str
    title: str
    content: str
    target: str = "all"          # all = 전체 회원, users = 특정 회원
    target_users: list[NoticeTargetUser] = []
    author_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class NoticeWriteRequest(BaseModel):
    title: str
    content: str
    target: NoticeTarget = "all"
    user_ids: list[str] = []     # target == "users"일 때 받을 회원 아이디(공개 id)


# ----------------------------------------
# 도우미
# ----------------------------------------
def _iso(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else "")


def _oid(value: str, not_found: str) -> ObjectId:
    if not value or not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail=not_found)
    return ObjectId(value)


def _clean(value: str, label: str, max_len: int) -> str:
    text = (value or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail=f"{label}을(를) 입력해 주세요.")
    if len(text) > max_len:
        raise HTTPException(status_code=400, detail=f"{label}은(는) {max_len}자 이하로 적어 주세요.")
    return text


def _id_query(ids: list[str]) -> dict:
    return {"$or": [{"id": {"$in": ids}}, {"social_id": {"$in": ids}}, {"kakao_id": {"$in": ids}}]}


def _contains(text: str) -> dict:
    return {"$regex": re.escape(text), "$options": "i"}


def _today_start_utc() -> datetime:
    now_kst = datetime.utcnow() + KST
    return now_kst.replace(hour=0, minute=0, second=0, microsecond=0) - KST


def _user_item(user: dict) -> AdminUserItem:
    uid = public_user_id(user)
    return AdminUserItem(
        id=uid,
        nickname=user.get("nickname") or user.get("name") or uid,
        name=user.get("name") or "",
        email=user.get("email") or "",
        role=user.get("role") or ROLE_USER,
        status=user.get("status") or STATUS_ACTIVE,
        warning_count=int(user.get("warning_count") or 0),
        provider=user.get("provider") or "",
        created_at=_iso(user.get("created_at")),
    )


async def _get_user_or_404(user_id: str) -> dict:
    user = await find_user_by_public_id((user_id or "").strip())
    if not user:
        raise HTTPException(status_code=404, detail=USER_NOT_FOUND)
    return user


def _protect_admin(user: dict, action: str) -> None:
    if user.get("role") == ROLE_ADMIN:
        raise HTTPException(status_code=400, detail=f"관리자 계정은 {action}할 수 없어요.")


async def _nickname_map(user_ids: list[str]) -> dict[str, str]:
    ids = list({uid for uid in user_ids if uid})
    found: dict[str, str] = {}
    if ids:
        cursor = users_collection.find(
            _id_query(ids), {"id": 1, "social_id": 1, "kakao_id": 1, "nickname": 1, "name": 1}
        )
        async for user in cursor:
            uid = public_user_id(user)
            found[uid] = user.get("nickname") or user.get("name") or uid
    return found


async def give_warning(user: dict, reason: str, admin: dict) -> int:
    """경고 1회 추가 + 회원 알림. 새 누적 횟수를 돌려줍니다. (신고 처리 화면과 회원 관리 화면 공통)"""
    now = datetime.utcnow()
    result = await users_collection.find_one_and_update(
        {"_id": user["_id"]},
        {
            "$inc": {"warning_count": 1},
            "$push": {"warnings": {"reason": reason, "admin_id": admin["user_id"], "created_at": now}},
        },
        projection={"warning_count": 1},
        return_document=True,
    )
    count = int((result or {}).get("warning_count") or 0)
    await notifications_collection.insert_one({
        "user_id": public_user_id(user),
        "title": "⚠️ 커뮤니티 가이드라인 경고 알림",
        "message": f"서비스 이용 수칙 위반으로 경고가 부여되었습니다. (누적 경고 횟수: {count}회)",
        "is_read": False,
        "created_at": now,
    })
    return count


# ----------------------------------------
# 관리자 메인: 요약 숫자
# ----------------------------------------
@router.get("/api/admin/summary", response_model=AdminSummary)
async def admin_summary(admin: dict = Depends(require_admin)):
    return AdminSummary(
        total_users=await users_collection.count_documents({"role": {"$ne": ROLE_ADMIN}}),
        pending_reports=await reports_collection.count_documents({"status": "pending"}),
        today_stories=await stories_collection.count_documents({"created_at": {"$gte": _today_start_utc()}}),
    )


# ----------------------------------------
# 회원 관리
# ----------------------------------------
@router.get("/api/admin/users", response_model=AdminUserListResponse)
async def admin_list_users(
    q: str = Query("", description="아이디·닉네임·이름·이메일 검색"),
    status: Optional[UserStatus] = Query(None, description="비우면 전체"),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    query: dict = {}
    keyword = q.strip()
    if keyword:
        pattern = _contains(keyword)
        query["$or"] = [{field: pattern} for field in ("id", "social_id", "kakao_id", "nickname", "name", "email")]
    if status == STATUS_BANNED:
        query["status"] = STATUS_BANNED
    elif status == STATUS_ACTIVE:
        query["status"] = {"$ne": STATUS_BANNED}

    total = await users_collection.count_documents(query)
    docs = await (
        users_collection.find(query, {"password": 0})
        .sort([("created_at", -1), ("_id", -1)])
        .skip((page - 1) * size).limit(size).to_list(length=size)
    )
    return AdminUserListResponse(
        items=[_user_item(d) for d in docs], page=page, size=size, total=total, has_more=page * size < total,
    )


@router.get("/api/admin/users/{user_id}", response_model=AdminUserDetail)
async def admin_get_user(user_id: str, admin: dict = Depends(require_admin)):
    user = await _get_user_or_404(user_id)
    uid = public_user_id(user)
    warnings = [
        AdminWarningItem(
            reason=w.get("reason") or "이용 수칙 위반",
            admin_id=w.get("admin_id") or "",
            created_at=_iso(w.get("created_at")),
        )
        for w in reversed(user.get("warnings") or [])
        if isinstance(w, dict)
    ]
    return AdminUserDetail(
        **_user_item(user).model_dump(),
        birth=str(user.get("birth") or ""),
        bio=user.get("bio") or "",
        profile_image_url=user.get("profile_image_url") or None,
        last_login=_iso(user.get("last_login")),
        warnings=warnings,
        story_count=await stories_collection.count_documents({"user_id": uid}),
        post_count=await posts_collection.count_documents({"user_id": uid}),
        comment_count=await comments_collection.count_documents({"user_id": uid}),
        reports_received=await reports_collection.count_documents({"target_user_id": uid}),
    )


@router.post("/api/admin/users/{user_id}/warnings", response_model=WarningResponse)
async def admin_warn_user(user_id: str, body: WarningCreateRequest, admin: dict = Depends(require_admin)):
    user = await _get_user_or_404(user_id)
    count = await give_warning(user, _clean(body.reason, "경고 사유", 200), admin)
    return WarningResponse(success=True, warning_count=count)


@router.patch("/api/admin/users/{user_id}/status", response_model=AdminUserItem)
async def admin_set_user_status(user_id: str, body: UserStatusRequest, admin: dict = Depends(require_admin)):
    user = await _get_user_or_404(user_id)
    if body.status == STATUS_BANNED:
        _protect_admin(user, "정지")
    fields = {"status": body.status}
    fields["banned_at" if body.status == STATUS_BANNED else "unbanned_at"] = datetime.utcnow()
    await users_collection.update_one({"_id": user["_id"]}, {"$set": fields})
    user.update(fields)
    return _user_item(user)


async def _delete_user_comments(uid: str) -> int:
    """이 회원이 쓴 댓글을 지우고, 댓글이 달린 게시글의 댓글 수를 줄입니다."""
    counts: dict[str, int] = {}
    async for row in comments_collection.aggregate([
        {"$match": {"user_id": uid}},
        {"$group": {"_id": "$post_id", "n": {"$sum": 1}}},
    ]):
        if row["_id"]:
            counts[row["_id"]] = row["n"]
    result = await comments_collection.delete_many({"user_id": uid})
    for post_id, n in counts.items():
        if ObjectId.is_valid(post_id):
            await posts_collection.update_one(
                {"_id": ObjectId(post_id)},
                [{"$set": {"comments_count": {"$max": [0, {"$subtract": [{"$ifNull": ["$comments_count", 0]}, n]}]}}}],
            )
    return result.deleted_count


async def _delete_user_likes(uid: str) -> None:
    """이 회원이 누른 좋아요/스크랩을 지우고 남의 게시글 좋아요 수를 다시 셉니다."""
    liked = [d["post_id"] async for d in post_likes_collection.find({"user_id": uid}, {"post_id": 1})]
    await post_likes_collection.delete_many({"user_id": uid})
    await post_scraps_collection.delete_many({"user_id": uid})
    for post_id in set(liked):
        if ObjectId.is_valid(post_id or ""):
            count = await post_likes_collection.count_documents({"post_id": post_id})
            await posts_collection.update_one({"_id": ObjectId(post_id)}, {"$set": {"likes_count": count}})


async def _delete_posts(query: dict) -> int:
    ids = [str(d["_id"]) async for d in posts_collection.find(query, {"_id": 1})]
    if not ids:
        return 0
    await posts_collection.delete_many({"_id": {"$in": [ObjectId(i) for i in ids]}})
    await remove_post_relations(ids)
    return len(ids)


@router.delete("/api/admin/users/{user_id}", response_model=DeleteUserResult)
async def admin_delete_user(
    user_id: str,
    delete_stories: bool = Query(False, description="True면 이 회원의 동화도 함께 삭제 (False면 동화는 남김)"),
    admin: dict = Depends(require_admin),
):
    """강제 탈퇴: 게시글·댓글·좋아요·스크랩·단어장은 지우고, 동화는 선택에 따라 남기거나 지웁니다."""
    user = await _get_user_or_404(user_id)
    _protect_admin(user, "탈퇴")
    uid = public_user_id(user)

    deleted_comments = await _delete_user_comments(uid)
    deleted_posts = await _delete_posts({"user_id": uid})
    await _delete_user_likes(uid)
    await vocabularies_collection.delete_many({"user_id": uid})
    await notifications_collection.delete_many({"user_id": uid})
    # 쪽지: 이 회원 쪽 보관함에서만 지운 것으로 처리 (상대방 쪽지함에는 남음)
    await direct_messages_collection.update_many({"sender_id": uid}, {"$set": {"deleted_by_sender": True}})
    await direct_messages_collection.update_many({"receiver_id": uid}, {"$set": {"deleted_by_receiver": True}})
    await direct_messages_collection.delete_many({"deleted_by_sender": True, "deleted_by_receiver": True})
    deleted_stories = 0
    if delete_stories:
        deleted_stories = (await stories_collection.delete_many({"user_id": uid})).deleted_count

    await users_collection.delete_one({"_id": user["_id"]})
    return DeleteUserResult(
        success=True,
        message="회원을 탈퇴 처리했어요.",
        deleted_posts=deleted_posts,
        deleted_comments=deleted_comments,
        deleted_stories=deleted_stories,
    )


# 신고 상세 화면(report_detail_page.dart)이 쓰는 예전 경로. 공개 id로 정확히 찾습니다.
@router.put("/admin/warning/{user_id}", response_model=WarningResponse, include_in_schema=False)
async def legacy_warn_user(
    user_id: str, body: Optional[LegacyWarningRequest] = None, admin: dict = Depends(require_admin)
):
    user = await _get_user_or_404(user_id)
    reason = ((body.reason if body else "") or "").strip()[:200] or "이용 수칙 위반"
    return WarningResponse(success=True, warning_count=await give_warning(user, reason, admin))


# ----------------------------------------
# 동화 관리
# ----------------------------------------
async def _story_items(docs: list[dict]) -> list[dict]:
    names = await _nickname_map([d.get("user_id", "") for d in docs])
    story_ids = [str(d["_id"]) for d in docs]
    links: dict[str, str] = {}
    if story_ids:
        async for p in posts_collection.find({"story_id": {"$in": story_ids}}, {"story_id": 1}):
            links.setdefault(p["story_id"], str(p["_id"]))
    items = []
    for d in docs:
        sid, uid = str(d["_id"]), d.get("user_id") or ""
        items.append({
            "id": sid,
            "title": d.get("title") or "제목 없는 이야기",
            "genre": d.get("genre") or "",
            "author": StoryAuthor(id=uid, nickname=names.get(uid) or "탈퇴한 회원", exists=uid in names),
            "created_at": _iso(d.get("created_at")),
            "shared": sid in links,
            "post_id": links.get(sid, ""),
        })
    return items


@router.get("/api/admin/stories", response_model=AdminStoryListResponse)
async def admin_list_stories(
    q: str = Query("", description="제목 또는 작성자(아이디·닉네임·이름) 검색"),
    genre: str = Query("", description="비우면 전체"),
    page: int = Query(1, ge=1),
    size: int = Query(30, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    query: dict = {}
    keyword = q.strip()
    if keyword:
        pattern = _contains(keyword)
        cursor = users_collection.find(
            {"$or": [{f: pattern} for f in ("id", "social_id", "kakao_id", "nickname", "name")]},
            {"id": 1, "social_id": 1, "kakao_id": 1},
        )
        author_ids = [public_user_id(u) async for u in cursor]
        query["$or"] = [{"title": pattern}, {"user_id": {"$in": author_ids}}]
    if genre.strip():
        query["genre"] = genre.strip()

    total = await stories_collection.count_documents(query)
    docs = await (
        stories_collection.find(query, {"content": 0})
        .sort([("created_at", -1), ("_id", -1)])
        .skip((page - 1) * size).limit(size).to_list(length=size)
    )
    return AdminStoryListResponse(
        items=[AdminStoryItem(**i) for i in await _story_items(docs)],
        page=page, size=size, total=total, has_more=page * size < total,
    )


@router.get("/api/admin/stories/{story_id}", response_model=AdminStoryDetail)
async def admin_get_story(story_id: str, admin: dict = Depends(require_admin)):
    doc = await stories_collection.find_one({"_id": _oid(story_id, STORY_NOT_FOUND)})
    if not doc:
        raise HTTPException(status_code=404, detail=STORY_NOT_FOUND)
    item = (await _story_items([doc]))[0]
    return AdminStoryDetail(**item, content=doc.get("content") or "", updated_at=_iso(doc.get("updated_at")))


@router.delete("/api/admin/stories/{story_id}", response_model=SimpleResult)
async def admin_delete_story(
    story_id: str,
    with_linked: bool = Query(False, description="True면 연결된 커뮤니티 게시글도 함께 삭제"),
    admin: dict = Depends(require_admin),
):
    result = await stories_collection.delete_one({"_id": _oid(story_id, STORY_NOT_FOUND)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=STORY_NOT_FOUND)
    removed = await _delete_posts({"story_id": story_id}) if with_linked else 0
    message = "동화를 삭제했어요." + (f" (연결된 게시글 {removed}개도 삭제)" if removed else "")
    return SimpleResult(success=True, message=message)


# ----------------------------------------
# 공지사항
# ----------------------------------------
def notice_visible_query(user_id: str) -> dict:
    """마이페이지 알림함: 전체 공지(예전 공지 포함) + 나를 대상으로 한 공지만"""
    return {"$or": [{"target": {"$ne": "users"}}, {"target_user_ids": user_id}]}


async def _notice_items(docs: list[dict]) -> list[AdminNoticeItem]:
    names = await _nickname_map([uid for d in docs for uid in (d.get("target_user_ids") or [])])
    return [
        AdminNoticeItem(
            id=str(d["_id"]),
            title=d.get("title") or "공지사항",
            content=d.get("content") or "",
            target="users" if d.get("target") == "users" else "all",
            target_users=[
                NoticeTargetUser(id=uid, nickname=names.get(uid) or "탈퇴한 회원", exists=uid in names)
                for uid in (d.get("target_user_ids") or [])
            ],
            author_id=d.get("author_id") or "",
            created_at=_iso(d.get("created_at")),
            updated_at=_iso(d.get("updated_at")),
        )
        for d in docs
    ]


async def _notice_fields(body: NoticeWriteRequest) -> dict:
    fields = {
        "title": _clean(body.title, "제목", 100),
        "content": _clean(body.content, "내용", 5000),
        "target": body.target,
        "target_user_ids": [],
    }
    if body.target == "users":
        ids = list(dict.fromkeys(i.strip() for i in body.user_ids if i and i.strip()))
        if not ids:
            raise HTTPException(status_code=400, detail="공지를 받을 회원 아이디를 한 명 이상 넣어 주세요.")
        found = {public_user_id(u) async for u in users_collection.find(_id_query(ids), {"id": 1, "social_id": 1, "kakao_id": 1})}
        missing = [i for i in ids if i not in found]
        if missing:
            raise HTTPException(status_code=400, detail=f"없는 아이디예요: {', '.join(missing)}")
        fields["target_user_ids"] = ids
    return fields


@router.get("/api/admin/notices", response_model=list[AdminNoticeItem])
async def admin_list_notices(admin: dict = Depends(require_admin)):
    docs = await notices_collection.find().sort([("created_at", -1), ("_id", -1)]).to_list(length=500)
    return await _notice_items(docs)


@router.post("/api/admin/notices", response_model=AdminNoticeItem)
async def admin_create_notice(body: NoticeWriteRequest, admin: dict = Depends(require_admin)):
    doc = {**await _notice_fields(body), "author_id": admin["user_id"], "created_at": datetime.utcnow()}
    result = await notices_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return (await _notice_items([doc]))[0]


@router.patch("/api/admin/notices/{notice_id}", response_model=AdminNoticeItem)
async def admin_update_notice(notice_id: str, body: NoticeWriteRequest, admin: dict = Depends(require_admin)):
    oid = _oid(notice_id, NOTICE_NOT_FOUND)
    fields = {**await _notice_fields(body), "updated_at": datetime.utcnow()}
    result = await notices_collection.update_one({"_id": oid}, {"$set": fields})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail=NOTICE_NOT_FOUND)
    return (await _notice_items([await notices_collection.find_one({"_id": oid})]))[0]


@router.delete("/api/admin/notices/{notice_id}", response_model=SimpleResult)
async def admin_delete_notice(notice_id: str, admin: dict = Depends(require_admin)):
    result = await notices_collection.delete_one({"_id": _oid(notice_id, NOTICE_NOT_FOUND)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail=NOTICE_NOT_FOUND)
    return SimpleResult(success=True, message="공지사항을 삭제했어요.")
