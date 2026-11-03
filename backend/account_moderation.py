from datetime import datetime
from typing import Any, Dict, Optional


DELETED_NICKNAME = "탈퇴한 사용자"


def build_soft_delete_fields(
    user_id: str,
    *,
    reason: Optional[str],
    deleted_by: str,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    deleted_at = now or datetime.utcnow()
    return {
        "account_id": f"deleted_{user_id}",
        "account_status": "deleted",
        "nickname": DELETED_NICKNAME,
        "email": None,
        "phone": None,
        "address": None,
        "password": None,
        "provider_id": None,
        "social_info": None,
        "radar_stats": {},
        "deleted_at": deleted_at,
        "deletion_reason": (reason or "").strip() or None,
        "deleted_by": deleted_by,
        "updated_at": deleted_at,
        "schema_version": 2,
    }


def serialize_warning(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(document.get("_id", "")),
        "user_id": str(document.get("user_id", "")),
        "reason": document.get("reason", ""),
        "severity": document.get("severity", "notice"),
        "status": document.get("status", "active"),
        "created_by": document.get("created_by"),
        "created_at": document.get("created_at"),
        "expires_at": document.get("expires_at"),
        "resolved_at": document.get("resolved_at"),
    }


def serialize_report(document: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(document.get("_id", "")),
        "reporter_account_id": document.get("reporter_account_id"),
        "target_type": document.get("target_type"),
        "target_id": str(document.get("target_id", "")),
        "post_id": str(document.get("post_id", "")) if document.get("post_id") else None,
        "reason": document.get("reason", ""),
        "details": document.get("details"),
        "status": document.get("status", "pending"),
        "action_taken": document.get("action_taken"),
        "resolution_note": document.get("resolution_note"),
        "created_at": document.get("created_at"),
        "resolved_at": document.get("resolved_at"),
        "resolved_by": document.get("resolved_by"),
    }
