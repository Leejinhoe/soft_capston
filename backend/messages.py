"""1:1 쪽지 (간단한 일회성 쪽지, 대화방 없음).

direct_messages 컬렉션 문서: ("messages" 컬렉션은 팀원 기능용이라 쓰지 않음)
    sender_id, receiver_id   보낸 사람 / 받는 사람 공개 id
    content                  내용 (300자 이하)
    is_read, read_at         읽음 여부
    reply_to                 답장이면 원래 쪽지 id (아니면 "")
    deleted_by_sender        보낸 쪽지함에서 지웠는지
    deleted_by_receiver      받은 쪽지함에서 지웠는지
    created_at
양쪽 모두 지우면 문서를 실제로 지웁니다. (신고에는 내용이 복사되어 남아 있음)
"""
from datetime import datetime
from typing import Literal, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from community import Author, author_map
from database import direct_messages_collection, safe_create_index
from reports import reported_target_ids
from security import find_user_by_public_id, get_current_user

router = APIRouter(tags=["messages"])

MESSAGE_MAX_LEN = 300
NOT_FOUND = "쪽지를 찾지 못했어요."


class MessageSendRequest(BaseModel):
    receiver_id: str
    content: str
    reply_to: Optional[str] = ""


class MessageItem(BaseModel):
    id: str
    box: Literal["received", "sent"]   # 내가 받은 쪽지인지 보낸 쪽지인지
    other: Author                      # 상대방 (받은 쪽지면 보낸 사람, 보낸 쪽지면 받는 사람)
    content: str
    is_read: bool
    reply_to: str = ""
    reported: bool = False             # 받은 쪽지를 내가 이미 신고했는지
    created_at: str = ""


class MessageListResponse(BaseModel):
    items: list[MessageItem]
    page: int
    size: int
    total: int
    has_more: bool
    unread_count: int


class UnreadCountResponse(BaseModel):
    count: int


class SimpleResult(BaseModel):
    success: bool
    message: str = ""


def _iso(value) -> str:
    return value.isoformat() if isinstance(value, datetime) else (str(value) if value else "")


def _oid(value: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    return ObjectId(value)


async def ensure_indexes() -> None:
    dm = direct_messages_collection
    await safe_create_index(dm, [("receiver_id", 1), ("deleted_by_receiver", 1), ("created_at", -1)], name="dm_receiver_box_idx")
    await safe_create_index(dm, [("sender_id", 1), ("deleted_by_sender", 1), ("created_at", -1)], name="dm_sender_box_idx")
    await safe_create_index(dm, [("receiver_id", 1), ("is_read", 1)], name="dm_receiver_unread_idx")


def _box_query(user_id: str, box: str) -> dict:
    if box == "received":
        return {"receiver_id": user_id, "deleted_by_receiver": {"$ne": True}}
    return {"sender_id": user_id, "deleted_by_sender": {"$ne": True}}


async def _unread_count(user_id: str) -> int:
    return await direct_messages_collection.count_documents(
        {"receiver_id": user_id, "is_read": False, "deleted_by_receiver": {"$ne": True}}
    )


async def _items(docs: list[dict], user_id: str) -> list[MessageItem]:
    def other_id(d: dict) -> str:
        return d.get("sender_id", "") if d.get("receiver_id") == user_id else d.get("receiver_id", "")

    authors = await author_map([other_id(d) for d in docs])
    received_ids = [str(d["_id"]) for d in docs if d.get("receiver_id") == user_id]
    reported = await reported_target_ids(user_id, "message", received_ids)
    return [
        MessageItem(
            id=str(d["_id"]),
            box="received" if d.get("receiver_id") == user_id else "sent",
            other=authors[other_id(d)],
            content=d.get("content") or "",
            is_read=bool(d.get("is_read")),
            reply_to=d.get("reply_to") or "",
            reported=str(d["_id"]) in reported,
            created_at=_iso(d.get("created_at")),
        )
        for d in docs
    ]


@router.post("/api/messages", response_model=MessageItem)
async def send_message(body: MessageSendRequest, current_user: dict = Depends(get_current_user)):
    sender_id = current_user["user_id"]
    receiver_id = body.receiver_id.strip()
    if receiver_id == sender_id:
        raise HTTPException(status_code=400, detail="나에게는 쪽지를 보낼 수 없어요.")
    content = body.content.strip()
    if not content:
        raise HTTPException(status_code=400, detail="쪽지 내용을 적어 주세요.")
    if len(content) > MESSAGE_MAX_LEN:
        raise HTTPException(status_code=400, detail=f"쪽지는 {MESSAGE_MAX_LEN}자 이하로 적어 주세요.")
    if not await find_user_by_public_id(receiver_id):
        raise HTTPException(status_code=404, detail="쪽지를 받을 친구를 찾지 못했어요.")

    reply_to = (body.reply_to or "").strip()
    if reply_to:
        # 답장은 내가 받은 쪽지에만 할 수 있습니다.
        original = await direct_messages_collection.find_one(
            {"_id": _oid(reply_to), "receiver_id": sender_id, "sender_id": receiver_id}
        ) if ObjectId.is_valid(reply_to) else None
        if not original:
            reply_to = ""

    doc = {
        "sender_id": sender_id,
        "receiver_id": receiver_id,
        "content": content,
        "is_read": False,
        "read_at": None,
        "reply_to": reply_to,
        "deleted_by_sender": False,
        "deleted_by_receiver": False,
        "created_at": datetime.utcnow(),
    }
    result = await direct_messages_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return (await _items([doc], sender_id))[0]


@router.get("/api/messages", response_model=MessageListResponse)
async def list_messages(
    box: Literal["received", "sent"] = Query("received"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    query = _box_query(user_id, box)
    total = await direct_messages_collection.count_documents(query)
    docs = await (
        direct_messages_collection.find(query).sort([("created_at", -1), ("_id", -1)])
        .skip((page - 1) * size).limit(size).to_list(length=size)
    )
    return MessageListResponse(
        items=await _items(docs, user_id), page=page, size=size, total=total,
        has_more=page * size < total, unread_count=await _unread_count(user_id),
    )


@router.get("/api/messages/unread-count", response_model=UnreadCountResponse)
async def unread_count(current_user: dict = Depends(get_current_user)):
    return UnreadCountResponse(count=await _unread_count(current_user["user_id"]))


@router.get("/api/messages/{message_id}", response_model=MessageItem)
async def read_message(message_id: str, current_user: dict = Depends(get_current_user)):
    """쪽지 하나 보기. 받은 쪽지를 열면 읽음으로 바뀝니다."""
    user_id = current_user["user_id"]
    oid = _oid(message_id)
    doc = await direct_messages_collection.find_one({
        "_id": oid,
        "$or": [
            {"receiver_id": user_id, "deleted_by_receiver": {"$ne": True}},
            {"sender_id": user_id, "deleted_by_sender": {"$ne": True}},
        ],
    })
    if not doc:
        raise HTTPException(status_code=404, detail=NOT_FOUND)
    if doc.get("receiver_id") == user_id and not doc.get("is_read"):
        now = datetime.utcnow()
        await direct_messages_collection.update_one({"_id": oid}, {"$set": {"is_read": True, "read_at": now}})
        doc["is_read"] = True
    return (await _items([doc], user_id))[0]


@router.delete("/api/messages/{message_id}", response_model=SimpleResult)
async def delete_message(message_id: str, current_user: dict = Depends(get_current_user)):
    """내 쪽지함에서만 지웁니다. 상대방 쪽지함에는 남아 있어요."""
    user_id = current_user["user_id"]
    oid = _oid(message_id)
    doc = await direct_messages_collection.find_one({"_id": oid, "$or": [{"receiver_id": user_id}, {"sender_id": user_id}]})
    if not doc:
        raise HTTPException(status_code=404, detail=NOT_FOUND)

    update: dict = {}
    if doc.get("receiver_id") == user_id:
        update["deleted_by_receiver"] = True
    if doc.get("sender_id") == user_id:
        update["deleted_by_sender"] = True
    doc.update(update)
    if doc.get("deleted_by_receiver") and doc.get("deleted_by_sender"):
        await direct_messages_collection.delete_one({"_id": oid})
    else:
        await direct_messages_collection.update_one({"_id": oid}, {"$set": update})
    return SimpleResult(success=True, message="쪽지를 지웠어요.")
