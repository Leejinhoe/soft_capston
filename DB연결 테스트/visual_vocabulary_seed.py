import hashlib
import json
import time
from datetime import datetime
from typing import Any, Dict, List

from pymongo import UpdateOne

from database import fit_vocabulary_collection, visual_vocabulary_collection
from visual_vocabulary import (
    CLASSIFIER_VERSION,
    classify_fit_vocabulary,
    match_visual_vocabulary,
)


_CACHE_DOCUMENTS: List[Dict[str, Any]] = []
_CACHE_LOADED_AT = 0.0
CACHE_TTL_SECONDS = 300


def _source_key(document: Dict[str, Any]) -> str:
    return str(
        document.get("vocabulary_key")
        or document.get("_id")
        or document.get("word")
        or ""
    )


def _fingerprint(document: Dict[str, Any]) -> str:
    fields = {
        key: document.get(key)
        for key in (
            "word",
            "original_word",
            "meaning",
            "child_friendly_meaning",
            "part_of_speech",
            "pos_group",
            "fit_score",
            "difficulty_level",
            "age_band",
            "enabled",
        )
    }
    fields["classifier_version"] = CLASSIFIER_VERSION
    payload = json.dumps(
        fields,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def sync_visual_vocabulary() -> Dict[str, int]:
    global _CACHE_DOCUMENTS, _CACHE_LOADED_AT
    source_documents = await fit_vocabulary_collection.find({}).to_list(length=5000)
    existing_documents = await visual_vocabulary_collection.find(
        {},
        {"source_key": 1, "source_fingerprint": 1},
    ).to_list(length=5000)
    existing_by_key = {
        str(item.get("source_key")): item for item in existing_documents
    }

    now = datetime.utcnow()
    operations = []
    source_keys = []
    classified_documents = []
    unchanged = 0
    for source in source_documents:
        source_key = _source_key(source)
        if not source_key:
            continue
        source_keys.append(source_key)
        fingerprint = _fingerprint(source)
        classified = classify_fit_vocabulary(source)
        derived = {
            **classified,
            "source_key": source_key,
            "source_id": str(source.get("_id", "")),
            "vocabulary_key": source.get("vocabulary_key"),
            "fit_score": source.get("fit_score"),
            "core_story_score": source.get("core_story_score"),
            "difficulty_level": source.get("difficulty_level"),
            "age_band": source.get("age_band"),
            "enabled": bool(source.get("enabled", True)),
            "source_fingerprint": fingerprint,
            "updated_at": now,
        }
        classified_documents.append(derived)
        existing = existing_by_key.get(source_key)
        if existing and existing.get("source_fingerprint") == fingerprint:
            unchanged += 1
            continue
        operations.append(
            UpdateOne(
                {"source_key": source_key},
                {
                    "$set": derived,
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        )

    if operations:
        await visual_vocabulary_collection.bulk_write(operations, ordered=False)
    if source_keys:
        await visual_vocabulary_collection.update_many(
            {"source_key": {"$nin": source_keys}, "enabled": True},
            {"$set": {"enabled": False, "updated_at": now}},
        )

    _CACHE_DOCUMENTS = [
        item for item in classified_documents if item["usable_for_image"]
    ]
    _CACHE_LOADED_AT = time.monotonic()
    return {
        "source_count": len(source_documents),
        "derived_count": len(classified_documents),
        "updated_count": len(operations),
        "unchanged_count": unchanged,
    }


async def load_visual_context(story_text: str) -> Dict[str, Any]:
    global _CACHE_DOCUMENTS, _CACHE_LOADED_AT
    now = time.monotonic()
    if not _CACHE_DOCUMENTS or now - _CACHE_LOADED_AT >= CACHE_TTL_SECONDS:
        _CACHE_DOCUMENTS = await visual_vocabulary_collection.find(
            {"enabled": True, "usable_for_image": True},
        ).to_list(length=5000)
        _CACHE_LOADED_AT = now
    return match_visual_vocabulary(story_text, _CACHE_DOCUMENTS)
