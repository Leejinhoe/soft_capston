from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId


def coerce_object_id(value: Any) -> Optional[ObjectId]:
    if isinstance(value, ObjectId):
        return value
    if isinstance(value, str) and ObjectId.is_valid(value):
        return ObjectId(value)
    return None


def serialize_object_id(value: Any) -> Optional[str]:
    object_id = coerce_object_id(value)
    if object_id is not None:
        return str(object_id)
    if value is None:
        return None
    return str(value)


def serialize_datetime(value: Any) -> str:
    if isinstance(value, datetime):
        return value.isoformat()
    if value:
        return str(value)
    return datetime.utcnow().isoformat()


def serialize_optional_datetime(value: Any) -> Optional[str]:
    if not value:
        return None
    return serialize_datetime(value)


def build_media_file_url(file_id: Any, media_kind: str) -> Optional[str]:
    serialized_id = serialize_object_id(file_id)
    if not serialized_id:
        return None
    if media_kind == "image":
        return f"/api/media/images/{serialized_id}"
    if media_kind == "video":
        return f"/api/media/videos/{serialized_id}"
    return f"/api/media/files/{serialized_id}"


def _job_result_payload(job: Dict[str, Any]) -> Dict[str, Any]:
    result = job.get("result")
    if isinstance(result, dict):
        return result
    return {}


def _job_value(job: Dict[str, Any], key: str) -> Any:
    if job.get(key) is not None:
        return job.get(key)
    return _job_result_payload(job).get(key)


def extract_media_result(job: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    image_file_id = serialize_object_id(_job_value(job, "image_file_id"))
    video_file_id = serialize_object_id(_job_value(job, "video_file_id"))
    image_url = build_media_file_url(image_file_id, "image") or _job_value(job, "image_url")
    video_url = build_media_file_url(video_file_id, "video") or _job_value(job, "video_url")

    result_payload = _job_result_payload(job)
    metadata = job.get("result_metadata") or result_payload.get("metadata")
    if metadata is None and result_payload:
        metadata = {
            key: value
            for key, value in result_payload.items()
            if key
            not in {
                "image_url",
                "video_url",
                "image_file_id",
                "video_file_id",
                "provider",
                "metadata",
            }
        } or None
    provider = _job_value(job, "provider")
    if (
        not image_url
        and not video_url
        and not image_file_id
        and not video_file_id
        and not metadata
        and not provider
    ):
        return None

    return {
        "image_url": image_url,
        "video_url": video_url,
        "image_file_id": image_file_id,
        "video_file_id": video_file_id,
        "provider": provider,
        "metadata": metadata,
    }


def serialize_media_job_document(job: Dict[str, Any]) -> Dict[str, Any]:
    request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
    def request_value(key: str, default: Any = None) -> Any:
        return job.get(key) if job.get(key) is not None else request_payload.get(key, default)

    return {
        "job_id": str(job["_id"]),
        "status": job.get("status", "pending"),
        "status_url": f"/api/media/jobs/{job['_id']}",
        "created_at": serialize_datetime(job.get("created_at")),
        "updated_at": serialize_datetime(job.get("updated_at")),
        "started_at": serialize_optional_datetime(job.get("started_at")),
        "completed_at": serialize_optional_datetime(job.get("completed_at")),
        "request": {
            "story_id": serialize_object_id(
                job.get("story_id") if job.get("story_id") is not None else request_payload.get("story_id")
            ),
            "step_number": (
                job.get("step_number")
                if job.get("step_number") is not None
                else request_payload.get("step_number")
            ),
            "story_text": (
                job.get("story_text")
                if job.get("story_text") is not None
                else request_payload.get("story_text")
            ),
            "genre": job.get("genre") if job.get("genre") is not None else request_payload.get("genre"),
            "age": job.get("age") if job.get("age") is not None else request_payload.get("age"),
            "include_video": (
                job.get("include_video")
                if job.get("include_video") is not None
                else request_payload.get("include_video", True)
            ),
            "width": request_value("width"),
            "height": request_value("height"),
            "flux_steps": request_value("flux_steps"),
            "video_width": request_value("video_width"),
            "video_height": request_value("video_height"),
            "num_frames": request_value("num_frames"),
            "frame_rate": request_value("frame_rate"),
            "video_timeout": request_value("video_timeout"),
        },
        "result": extract_media_result(job),
        "error": job.get("error"),
    }
