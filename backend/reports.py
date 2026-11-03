"""신고: 게시글 / 댓글 / 사용자 / 쪽지.

reports 컬렉션 문서 (관리자 신고관리 화면에서 그대로 사용):
    reporter_id      신고한 사람 (토큰의 user_id)
    target_type      "post" | "comment" | "user" | "message"
    target_id        대상 id (post/comment/message는 ObjectId 문자열, user는 공개 id)
    target_user_id   신고당한 사용자 공개 id (경고 줄 때 바로 사용)
    post_id          댓글 신고일 때 댓글이 달린 게시글 id (그 외 "")
    reason           "abuse" | "inappropriate" | "spam" | "other"
    detail           상세 내용 (기타일 때 필수, 200자 이하)
    snapshot         신고 시점의 대상 내용 {title, content} (원본이 지워져도 확인 가능)
    status           "pending" | "resolved" | "rejected"
    created_at, handled_at, handled_by, admin_memo

같은 사람이 같은 대상을 두 번 신고할 수 없습니다. (reporter_id + target_type + target_id 고유 인덱스)
"""
from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from database import (
    comments_collection,
    messages_collection,
    posts_collection,
    reports_collection,
    users_collection,
)
from security import find_user_by_public_id, get_current_user, public_user_id, require_admin

router = APIRouter(tags=["reports"])

TargetType = Literal["post", "comment", "user", "message"]
ReasonCode = Literal["abuse", "inappropriate", "spam", "other"]
ReportStatus = Literal["pending", "resolved", "rejected"]

REASON_LABELS = {
    "abuse": "욕설/비방",
    "inappropriate": "부적절한 내용",
    "spam": "도배/광고",
    "other": "기타",
}
TARGET_LABELS = {"post": "게시글", "comment": "댓글", "user": "사용자", "message": "쪽지"}
# 아이에게 보여줄 안내 문구용 (조사까지 맞춤)
_NOT_FOUND = {"post": "게시글을", "comment": "댓글을", "user": "친구를", "message": "쪽지를"}
_ALREADY = {"post": "게시글이에요", "comment": "댓글이에요", "user": "친구예요", "message": "쪽지예요"}
DETAIL_MAX_LEN = 200
SNAPSHOT_MAX_LEN = 500


# ----------------------------------------
# 스키마
# ----------------------------------------
class ReportCreateRequest(BaseModel):
    target_type: TargetType
    target_id: str
    reason: ReasonCode
    detail: Optional[str] = ""


class ReportCreateResponse(BaseModel):
    success: bool
    message: str
    report_id: str


class ReportUser(BaseModel):
    id: str
    nickname: str
    warning_count: int = 0
    status: str = "active"


class ReportSnapshot(BaseModel):
    title: str = ""
    content: str = ""


class AdminReportItem(BaseModel):
    id: str
    target_type: str
    target_type_label: str
    target_id: str
    post_id: str = ""            # 댓글이면 댓글이 달린 게시글 id
    target_exists: bool          # 대상이 아직 남아 있는지
    reporter: ReportUser
    target_user: ReportUser
    reason: str
    reason_label: str
    detail: str = ""
    snapshot: ReportSnapshot
    same_target_count: int = 1   # 같은 대상에 들어온 신고 수
    status: str
    created_at: str = ""
    handled_at: str = ""
    handled_by: str = ""
    admin_memo: str = ""


class AdminReportListResponse(BaseModel):
    items: list[AdminReportItem]
    page: int
    size: int
    total: int
    has_more: bool
    pending_count: int


class ReportStatusUpdateRequest(BaseModel):
    status: ReportStatus
    admin_memo: Optional[str] = None


# ----------------------------------------
# 도우미
# ----------------------------------------
def _iso(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else "")


def _oid_or_none(value: str) -> Optional[ObjectId]:
    return ObjectId(value) if value and ObjectId.is_valid(value) else None


def _cut(text: str, length: int = SNAPSHOT_MAX_LEN) -> str:
    text = (text or "").strip()
    return text if len(text) <= length else text[:length] + "…"


async def _resolve_target(target_type: str, target_id: str, reporter_id: str) -> dict:
    """대상을 찾아 신고당한 사용자 id와 신고 시점 내용을 돌려줍니다. 없으면 404."""
    not_found = HTTPException(status_code=404, detail=f"신고할 {_NOT_FOUND[target_type]} 찾지 못했어요.")

    if target_type == "user":
        user = await find_user_by_public_id(target_id)
        if not user:
            raise not_found
        return {
            "target_user_id": public_user_id(user),
            "post_id": "",
            "snapshot": {"title": user.get("nickname") or user.get("name") or "", "content": _cut(user.get("bio") or "")},
        }

    oid = _oid_or_none(target_id)
    if oid is None:
        raise not_found

    if target_type == "post":
        doc = await posts_collection.find_one({"_id": oid})
        if not doc:
            raise not_found
        return {
            "target_user_id": doc.get("user_id", ""),
            "post_id": "",
            "snapshot": {"title": doc.get("title") or "", "content": _cut(doc.get("content") or "")},
        }

    if target_type == "comment":
        doc = await comments_collection.find_one({"_id": oid})
        if not doc:
            raise not_found
        return {
            "target_user_id": doc.get("user_id", ""),
            "post_id": doc.get("post_id", ""),
            "snapshot": {"title": "", "content": _cut(doc.get("content") or "")},
        }

    # message: 내가 받은 쪽지만 신고할 수 있습니다.
    doc = await messages_collection.find_one({"_id": oid, "receiver_id": reporter_id})
    if not doc:
        raise not_found
    return {
        "target_user_id": doc.get("sender_id", ""),
        "post_id": "",
        "snapshot": {"title": "", "content": _cut(doc.get("content") or "")},
    }


async def reported_target_ids(reporter_id: str, target_type: str, target_ids: list[str]) -> set[str]:
    """내가 이미 신고한 대상 id (화면에서 '신고함' 표시용, community.py에서도 사용)"""
    if not target_ids:
        return set()
    cursor = reports_collection.find(
        {"reporter_id": reporter_id, "target_type": target_type, "target_id": {"$in": target_ids}},
        {"target_id": 1},
    )
    return {doc["target_id"] async for doc in cursor}


async def ensure_indexes() -> None:
    # 예전 /report 구조의 문서에는 target_id가 없으므로 고유 인덱스에서 제외합니다.
    await reports_collection.create_index(
        [("reporter_id", 1), ("target_type", 1), ("target_id", 1)],
        unique=True,
        partialFilterExpression={"target_id": {"$exists": True}},
        name="unique_reporter_target",
    )
    await reports_collection.create_index([("status", 1), ("created_at", -1)])
    await reports_collection.create_index([("target_type", 1), ("target_id", 1)])
    # 예전 상태값 정리: waiting → pending
    await reports_collection.update_many({"status": "waiting"}, {"$set": {"status": "pending"}})


# ----------------------------------------
# 신고하기 (로그인 사용자)
# ----------------------------------------
@router.post("/api/reports", response_model=ReportCreateResponse)
async def create_report(body: ReportCreateRequest, current_user: dict = Depends(get_current_user)):
    reporter_id = current_user["user_id"]
    target_id = body.target_id.strip()
    detail = (body.detail or "").strip()
    if body.reason == "other" and not detail:
        raise HTTPException(status_code=400, detail="기타 사유를 적어 주세요.")
    if len(detail) > DETAIL_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"상세 내용은 {DETAIL_MAX_LEN}자 이하로 적어 주세요.")

    target = await _resolve_target(body.target_type, target_id, reporter_id)
    if target["target_user_id"] == reporter_id:
        raise HTTPException(status_code=400, detail="내 글이나 나 자신은 신고할 수 없어요.")

    doc = {
        "reporter_id": reporter_id,
        "target_type": body.target_type,
        "target_id": target_id,
        "target_user_id": target["target_user_id"],
        "post_id": target["post_id"],
        "reason": body.reason,
        "detail": detail,
        "snapshot": target["snapshot"],
        "status": "pending",
        "created_at": datetime.utcnow(),
        "handled_at": None,
        "handled_by": "",
        "admin_memo": "",
    }
    try:
        result = await reports_collection.insert_one(doc)
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail=f"이미 신고한 {_ALREADY[body.target_type]}.")
    return ReportCreateResponse(
        success=True, message="신고가 접수되었어요. 알려 줘서 고마워요.", report_id=str(result.inserted_id)
    )


# ----------------------------------------
# 관리자: 신고 목록 / 상태 변경
# ----------------------------------------
async def _report_users(user_ids: list[str]) -> dict[str, ReportUser]:
    ids = list({uid for uid in user_ids if uid})
    found: dict[str, ReportUser] = {}
    if ids:
        cursor = users_collection.find(
            {"$or": [{"id": {"$in": ids}}, {"social_id": {"$in": ids}}, {"kakao_id": {"$in": ids}}]},
            {"id": 1, "social_id": 1, "kakao_id": 1, "nickname": 1, "name": 1, "warning_count": 1, "status": 1},
        )
        async for user in cursor:
            uid = public_user_id(user)
            found[uid] = ReportUser(
                id=uid,
                nickname=user.get("nickname") or user.get("name") or uid,
                warning_count=int(user.get("warning_count") or 0),
                status=user.get("status") or "active",
            )
    return found


async def _existing_ids(collection, ids: list[str]) -> set[str]:
    oids = [ObjectId(i) for i in set(ids) if i and ObjectId.is_valid(i)]
    if not oids:
        return set()
    return {str(d["_id"]) async for d in collection.find({"_id": {"$in": oids}}, {"_id": 1})}


async def _admin_items(docs: list[dict]) -> list[AdminReportItem]:
    users = await _report_users(
        [d.get("reporter_id", "") for d in docs] + [d.get("target_user_id", "") for d in docs]
    )

    by_type: dict[str, list[str]] = {}
    for d in docs:
        by_type.setdefault(d.get("target_type") or "post", []).append(d.get("target_id") or "")
    alive: dict[str, set[str]] = {
        "post": await _existing_ids(posts_collection, by_type.get("post", [])),
        "comment": await _existing_ids(comments_collection, by_type.get("comment", [])),
        "message": await _existing_ids(messages_collection, by_type.get("message", [])),
        "user": set(),
    }
    if by_type.get("user"):
        alive["user"] = set((await _report_users(by_type["user"])).keys())

    # 같은 대상에 들어온 신고 수
    counts: dict[tuple, int] = {}
    keys = [(d.get("target_type"), d.get("target_id")) for d in docs if d.get("target_id")]
    if keys:
        pipeline = [
            {"$match": {"$or": [{"target_type": t, "target_id": i} for t, i in set(keys)]}},
            {"$group": {"_id": {"t": "$target_type", "i": "$target_id"}, "n": {"$sum": 1}}},
        ]
        async for row in reports_collection.aggregate(pipeline):
            counts[(row["_id"]["t"], row["_id"]["i"])] = row["n"]

    items = []
    for d in docs:
        # 예전 /report 구조(author, story_title, reporter 이름만 있음)도 함께 보여줍니다.
        target_type = d.get("target_type") or "post"
        target_id = d.get("target_id") or ""
        reporter_id = d.get("reporter_id") or ""
        target_user_id = d.get("target_user_id") or ""
        reason = d.get("reason") or "other"
        snapshot = d.get("snapshot") or {"title": d.get("story_title") or "", "content": ""}
        items.append(AdminReportItem(
            id=str(d["_id"]),
            target_type=target_type,
            target_type_label=TARGET_LABELS.get(target_type, target_type),
            target_id=target_id,
            post_id=d.get("post_id") or "",
            target_exists=target_id in alive.get(target_type, set()),
            reporter=users.get(reporter_id) or ReportUser(id=reporter_id, nickname=d.get("reporter") or "알 수 없음"),
            target_user=users.get(target_user_id) or ReportUser(id=target_user_id, nickname=d.get("author") or "알 수 없음"),
            reason=reason if reason in REASON_LABELS else "other",
            reason_label=REASON_LABELS.get(reason, reason),
            detail=d.get("detail") or "",
            snapshot=ReportSnapshot(**snapshot),
            same_target_count=counts.get((target_type, target_id), 1),
            status=d.get("status") or "pending",
            created_at=_iso(d.get("created_at")),
            handled_at=_iso(d.get("handled_at")),
            handled_by=d.get("handled_by") or "",
            admin_memo=d.get("admin_memo") or "",
        ))
    return items


@router.get("/api/admin/reports", response_model=AdminReportListResponse)
async def admin_list_reports(
    status: Optional[ReportStatus] = Query(None, description="비우면 전체"),
    target_type: Optional[TargetType] = Query(None, description="비우면 전체"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    query: dict = {}
    if status:
        query["status"] = status
    if target_type:
        query["target_type"] = target_type
    total = await reports_collection.count_documents(query)
    pending_count = await reports_collection.count_documents({"status": "pending"})
    docs = await (
        reports_collection.find(query).sort([("created_at", -1), ("_id", -1)])
        .skip((page - 1) * size).limit(size).to_list(length=size)
    )
    return AdminReportListResponse(
        items=await _admin_items(docs), page=page, size=size, total=total,
        has_more=page * size < total, pending_count=pending_count,
    )


@router.get("/api/admin/reports/{report_id}", response_model=AdminReportItem)
async def admin_get_report(report_id: str, admin: dict = Depends(require_admin)):
    oid = _oid_or_none(report_id)
    doc = await reports_collection.find_one({"_id": oid}) if oid else None
    if not doc:
        raise HTTPException(status_code=404, detail="신고를 찾지 못했어요.")
    return (await _admin_items([doc]))[0]


@router.patch("/api/admin/reports/{report_id}", response_model=AdminReportItem)
async def admin_update_report(
    report_id: str, body: ReportStatusUpdateRequest, admin: dict = Depends(require_admin)
):
    oid = _oid_or_none(report_id)
    update: dict = {
        "status": body.status,
        "handled_at": None if body.status == "pending" else datetime.utcnow(),
        "handled_by": "" if body.status == "pending" else admin["user_id"],
    }
    if body.admin_memo is not None:
        update["admin_memo"] = body.admin_memo.strip()[:500]
    doc = await reports_collection.find_one_and_update(
        {"_id": oid}, {"$set": update}, return_document=ReturnDocument.AFTER
    ) if oid else None
    if not doc:
        raise HTTPException(status_code=404, detail="신고를 찾지 못했어요.")
    return (await _admin_items([doc]))[0]
