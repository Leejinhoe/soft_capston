"""커뮤니티: 게시글 목록/검색/상세, 좋아요, 스크랩, 댓글, 동화 공유.

- 게시글(posts)은 공유한 시점의 동화 복사본이고, story_id로 원본 동화(stories)와 연결됩니다.
- 모든 API는 토큰의 user_id 기준이며, 수정/삭제는 내 것만 됩니다.
"""
import re
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError

from database import (
    safe_create_index,
    comments_collection,
    post_likes_collection,
    post_scraps_collection,
    posts_collection,
    stories_collection,
    users_collection,
)
from reports import reported_target_ids
from security import ID_PROJECTION, find_user_by_public_id, get_current_user, public_id_query, public_user_id

router = APIRouter(tags=["community"])

POST_NOT_FOUND = "게시글을 찾지 못했어요."
COMMENT_MAX_LEN = 300


# ----------------------------------------
# 스키마
# ----------------------------------------
class Author(BaseModel):
    id: str
    nickname: str
    profile_image_url: Optional[str] = None


class PostSummary(BaseModel):
    id: str
    title: str
    preview: str
    genre: str = ""
    author: Author
    likes_count: int = 0
    comments_count: int = 0
    created_at: str = ""


class PostListResponse(BaseModel):
    items: list[PostSummary]
    page: int
    size: int
    total: int
    has_more: bool


class PostDetail(PostSummary):
    content: str
    updated_at: str = ""
    liked: bool = False
    scrapped: bool = False
    is_mine: bool = False
    reported: bool = False  # 내가 이미 신고한 글인지
    linked_id: str = ""   # 내 글일 때만: 연결된 원본 동화 id (동화가 지워졌으면 "")


class SharePostRequest(BaseModel):
    story_id: str


class SharePostResponse(BaseModel):
    success: bool
    message: str
    post_id: str
    already_shared: bool = False


class LikeResponse(BaseModel):
    liked: bool
    likes_count: int


class ScrapResponse(BaseModel):
    scrapped: bool


class CommentItem(BaseModel):
    id: str
    content: str
    author: Author
    is_mine: bool = False
    reported: bool = False  # 내가 이미 신고한 댓글인지
    created_at: str = ""


class CommentCreateRequest(BaseModel):
    content: str


class SimpleResult(BaseModel):
    success: bool
    message: str = ""


class MiniProfile(BaseModel):
    """작성자 미니 프로필 (게시글 상세/댓글에서 이름·사진을 누르면 보임)"""
    id: str
    nickname: str
    profile_image_url: Optional[str] = None
    bio: str = ""
    public_story_count: int = 0   # 커뮤니티에 공개한 동화 수
    received_likes: int = 0       # 받은 좋아요 수
    is_me: bool = False


# ----------------------------------------
# 공통 도우미
# ----------------------------------------
def _iso(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else "")


def _oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=400, detail="잘못된 요청이에요.")
    return ObjectId(value)


def _preview(content: str, length: int = 80) -> str:
    text = " ".join((content or "").split())
    return text if len(text) <= length else text[:length] + "…"


async def author_map(user_ids: list[str]) -> dict[str, Author]:
    """공개 id 목록 → 작성자 정보(닉네임, 프로필 사진). 탈퇴한 사용자는 '알 수 없는 친구'."""
    ids = list({uid for uid in user_ids if uid})
    found: dict[str, Author] = {}
    if ids:
        cursor = users_collection.find(
            public_id_query(ids),
            {**ID_PROJECTION, "nickname": 1, "name": 1, "profile_image_url": 1},
        )
        async for user in cursor:
            uid = public_user_id(user)
            found[uid] = Author(
                id=uid,
                nickname=user.get("nickname") or user.get("name") or "친구",
                profile_image_url=user.get("profile_image_url") or None,
            )
    return {uid: found.get(uid) or Author(id=uid, nickname="알 수 없는 친구") for uid in user_ids}


def _summary(doc: dict, author: Author) -> PostSummary:
    return PostSummary(
        id=str(doc["_id"]),
        title=doc.get("title") or "제목 없는 이야기",
        preview=_preview(doc.get("content") or ""),
        genre=doc.get("genre") or "",
        author=author,
        likes_count=int(doc.get("likes_count") or 0),
        comments_count=int(doc.get("comments_count") or 0),
        created_at=_iso(doc.get("created_at")),
    )


async def _summaries(docs: list[dict]) -> list[PostSummary]:
    authors = await author_map([d.get("user_id", "") for d in docs])
    return [_summary(d, authors[d.get("user_id", "")]) for d in docs]


async def _get_post_or_404(post_id: str) -> dict:
    doc = await posts_collection.find_one({"_id": _oid(post_id)})
    if not doc:
        raise HTTPException(status_code=404, detail=POST_NOT_FOUND)
    return doc


# ----------------------------------------
# 동화 ↔ 게시글 연결 도우미 (main.py의 내 동화/내 게시글 API에서도 사용)
# ----------------------------------------
async def linked_post_ids(story_ids: list[str], user_id: str) -> dict[str, str]:
    """동화 id → 연결된 내 게시글 id"""
    result: dict[str, str] = {}
    if story_ids:
        cursor = posts_collection.find({"user_id": user_id, "story_id": {"$in": story_ids}}, {"story_id": 1})
        async for doc in cursor:
            result.setdefault(doc["story_id"], str(doc["_id"]))
    return result


async def existing_story_ids(story_ids: list[str], user_id: str) -> set[str]:
    """아직 남아 있는 내 동화 id만 골라냅니다."""
    oids = [ObjectId(s) for s in set(story_ids) if s and ObjectId.is_valid(s)]
    if not oids:
        return set()
    cursor = stories_collection.find({"_id": {"$in": oids}, "user_id": user_id}, {"_id": 1})
    return {str(doc["_id"]) async for doc in cursor}


async def remove_post_relations(post_ids: list[str]) -> None:
    """게시글을 지울 때 딸린 좋아요/스크랩/댓글도 함께 지웁니다."""
    if not post_ids:
        return
    query = {"post_id": {"$in": post_ids}}
    await post_likes_collection.delete_many(query)
    await post_scraps_collection.delete_many(query)
    await comments_collection.delete_many(query)


async def ensure_indexes() -> None:
    await safe_create_index(post_likes_collection, [("post_id", 1), ("user_id", 1)], unique=True)
    await safe_create_index(post_scraps_collection, [("post_id", 1), ("user_id", 1)], unique=True)
    await safe_create_index(post_scraps_collection, [("user_id", 1), ("created_at", -1)])
    await safe_create_index(comments_collection, [("post_id", 1), ("created_at", 1)])
    await safe_create_index(posts_collection, [("created_at", -1)])
    await safe_create_index(posts_collection, [("user_id", 1), ("story_id", 1)])


# ----------------------------------------
# 동화 → 커뮤니티 공유
# ----------------------------------------
@router.post("/api/community/posts", response_model=SharePostResponse)
async def share_story(body: SharePostRequest, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    story = await stories_collection.find_one({"_id": _oid(body.story_id), "user_id": user_id})
    if not story:
        raise HTTPException(status_code=404, detail="공유할 동화를 찾지 못했어요.")

    existing = await posts_collection.find_one({"user_id": user_id, "story_id": body.story_id})
    if existing:
        return SharePostResponse(
            success=True, message="이미 커뮤니티에 올린 동화예요.",
            post_id=str(existing["_id"]), already_shared=True,
        )

    now = datetime.utcnow()
    post_doc = {
        "story_id": body.story_id,
        "user_id": user_id,
        "title": story.get("title") or "제목 없는 이야기",
        "content": story.get("content") or "",
        "genre": story.get("genre") or "",
        "likes_count": 0,
        "comments_count": 0,
        "created_at": now,
    }
    result = await posts_collection.insert_one(post_doc)
    await stories_collection.update_one({"_id": story["_id"]}, {"$set": {"is_public": True}})
    return SharePostResponse(success=True, message="커뮤니티에 동화를 올렸어요!", post_id=str(result.inserted_id))


# ----------------------------------------
# 목록 / 검색 / 상세
# ----------------------------------------
@router.get("/api/community/posts", response_model=PostListResponse)
async def list_posts(
    genre: Optional[str] = Query(None, description="장르 (비우면 전체)"),
    q: Optional[str] = Query(None, description="제목 또는 작성자 닉네임 검색어"),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    query: dict = {}
    if genre and genre.strip() and genre.strip() != "전체":
        query["genre"] = genre.strip()

    keyword = (q or "").strip()
    if keyword:
        pattern = {"$regex": re.escape(keyword), "$options": "i"}
        author_ids = [
            public_user_id(u)
            async for u in users_collection.find(
                {"$or": [{"nickname": pattern}, {"nickname": {"$exists": False}, "name": pattern},
                         {"nickname": "", "name": pattern}]},
                ID_PROJECTION,
            )
        ]
        query["$or"] = [{"title": pattern}, {"user_id": {"$in": [a for a in author_ids if a]}}]

    total = await posts_collection.count_documents(query)
    cursor = (
        posts_collection.find(query)
        .sort([("created_at", -1), ("_id", -1)])
        .skip((page - 1) * size)
        .limit(size)
    )
    docs = await cursor.to_list(length=size)
    return PostListResponse(
        items=await _summaries(docs), page=page, size=size, total=total,
        has_more=page * size < total,
    )


@router.get("/api/community/posts/{post_id}", response_model=PostDetail)
async def get_post_detail(post_id: str, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    doc = await _get_post_or_404(post_id)
    author = (await author_map([doc.get("user_id", "")]))[doc.get("user_id", "")]
    is_mine = doc.get("user_id") == user_id

    linked_id = ""
    story_id = doc.get("story_id") or ""
    if is_mine and story_id and story_id in await existing_story_ids([story_id], user_id):
        linked_id = story_id

    liked = await post_likes_collection.find_one({"post_id": post_id, "user_id": user_id}) is not None
    scrapped = await post_scraps_collection.find_one({"post_id": post_id, "user_id": user_id}) is not None
    reported = not is_mine and bool(await reported_target_ids(user_id, "post", [post_id]))
    return PostDetail(
        **_summary(doc, author).model_dump(),
        content=doc.get("content") or "",
        updated_at=_iso(doc.get("updated_at")),
        liked=liked,
        scrapped=scrapped,
        is_mine=is_mine,
        reported=reported,
        linked_id=linked_id,
    )


# ----------------------------------------
# 좋아요 / 스크랩 (토글, 한 사람 1번)
# ----------------------------------------
@router.post("/api/community/posts/{post_id}/like", response_model=LikeResponse)
async def toggle_like(post_id: str, current_user: dict = Depends(get_current_user)):
    doc = await _get_post_or_404(post_id)
    key = {"post_id": post_id, "user_id": current_user["user_id"]}
    try:
        await post_likes_collection.insert_one({**key, "created_at": datetime.utcnow()})
        liked = True
    except DuplicateKeyError:
        await post_likes_collection.delete_one(key)
        liked = False

    # 동시에 눌러도 숫자가 어긋나지 않도록 실제 개수로 맞춰 둡니다.
    count = await post_likes_collection.count_documents({"post_id": post_id})
    await posts_collection.update_one({"_id": doc["_id"]}, {"$set": {"likes_count": count}})
    return LikeResponse(liked=liked, likes_count=count)


@router.post("/api/community/posts/{post_id}/scrap", response_model=ScrapResponse)
async def toggle_scrap(post_id: str, current_user: dict = Depends(get_current_user)):
    await _get_post_or_404(post_id)
    key = {"post_id": post_id, "user_id": current_user["user_id"]}
    try:
        await post_scraps_collection.insert_one({**key, "created_at": datetime.utcnow()})
        return ScrapResponse(scrapped=True)
    except DuplicateKeyError:
        await post_scraps_collection.delete_one(key)
        return ScrapResponse(scrapped=False)


@router.get("/api/users/me/scraps", response_model=list[PostSummary])
async def get_my_scraps(current_user: dict = Depends(get_current_user)):
    scraps = await post_scraps_collection.find(
        {"user_id": current_user["user_id"]}
    ).sort("created_at", -1).to_list(length=500)
    oids = [ObjectId(s["post_id"]) for s in scraps if ObjectId.is_valid(s.get("post_id", ""))]
    docs = {str(d["_id"]): d async for d in posts_collection.find({"_id": {"$in": oids}})}
    ordered = [docs[s["post_id"]] for s in scraps if s.get("post_id") in docs]  # 스크랩한 순서 유지
    return await _summaries(ordered)


# ----------------------------------------
# 댓글
# ----------------------------------------
def _comment(doc: dict, author: Author, user_id: str, reported: bool = False) -> CommentItem:
    return CommentItem(
        id=str(doc["_id"]),
        content=doc.get("content") or "",
        author=author,
        is_mine=doc.get("user_id") == user_id,
        reported=reported,
        created_at=_iso(doc.get("created_at")),
    )


@router.get("/api/community/posts/{post_id}/comments", response_model=list[CommentItem])
async def list_comments(post_id: str, current_user: dict = Depends(get_current_user)):
    await _get_post_or_404(post_id)
    docs = await comments_collection.find({"post_id": post_id}).sort("created_at", 1).to_list(length=1000)
    user_id = current_user["user_id"]
    authors = await author_map([d.get("user_id", "") for d in docs])
    reported = await reported_target_ids(user_id, "comment", [str(d["_id"]) for d in docs])
    return [_comment(d, authors[d.get("user_id", "")], user_id, str(d["_id"]) in reported) for d in docs]


@router.post("/api/community/posts/{post_id}/comments", response_model=CommentItem)
async def create_comment(post_id: str, body: CommentCreateRequest, current_user: dict = Depends(get_current_user)):
    post = await _get_post_or_404(post_id)
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="댓글 내용을 적어 주세요.")
    if len(content) > COMMENT_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"댓글은 {COMMENT_MAX_LEN}자 이하로 적어 주세요.")

    user_id = current_user["user_id"]
    doc = {"post_id": post_id, "user_id": user_id, "content": content, "created_at": datetime.utcnow()}
    result = await comments_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    await posts_collection.update_one({"_id": post["_id"]}, {"$inc": {"comments_count": 1}})
    author = (await author_map([user_id]))[user_id]
    return _comment(doc, author, user_id)


@router.delete("/api/community/comments/{comment_id}", response_model=SimpleResult)
async def delete_comment(comment_id: str, current_user: dict = Depends(get_current_user)):
    doc = await comments_collection.find_one_and_delete(
        {"_id": _oid(comment_id), "user_id": current_user["user_id"]}
    )
    if not doc:
        raise HTTPException(status_code=404, detail="댓글을 찾지 못했어요.")
    if ObjectId.is_valid(doc.get("post_id", "")):
        await posts_collection.update_one(
            {"_id": ObjectId(doc["post_id"]), "comments_count": {"$gt": 0}},
            {"$inc": {"comments_count": -1}},
        )
    return SimpleResult(success=True, message="댓글을 지웠어요.")


# ----------------------------------------
# 작성자 미니 프로필
# ----------------------------------------
@router.get("/api/users/{user_id}/profile", response_model=MiniProfile)
async def get_mini_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    user = await find_user_by_public_id(user_id.strip())
    if not user:
        raise HTTPException(status_code=404, detail="친구 정보를 찾지 못했어요.")
    uid = public_user_id(user)
    story_count = await posts_collection.count_documents({"user_id": uid})
    likes = await posts_collection.aggregate([
        {"$match": {"user_id": uid}},
        {"$group": {"_id": None, "total": {"$sum": "$likes_count"}}},
    ]).to_list(length=1)
    return MiniProfile(
        id=uid,
        nickname=user.get("nickname") or user.get("name") or "친구",
        profile_image_url=user.get("profile_image_url") or None,
        bio=user.get("bio") or "상상력이 풍부한 동화 탐험가 ✨",
        public_story_count=story_count,
        received_likes=int(likes[0]["total"]) if likes else 0,
        is_me=uid == current_user["user_id"],
    )
