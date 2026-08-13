import hashlib
import json
import time
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from pymongo import UpdateOne

from database import fit_vocabulary_collection, visual_vocabulary_collection
from visual_vocabulary import (
    CLASSIFIER_VERSION,
    classify_fit_vocabulary,
    match_visual_vocabulary,
    normalize_text,
)


_CACHE_DOCUMENTS: List[Dict[str, Any]] = []
_CACHE_LOADED_AT = 0.0
CACHE_TTL_SECONDS = 300
ENSEMBLE_PROFILE_PATH = (
    Path(__file__).resolve().parents[1]
    / "tools"
    / "vocabulary_ensemble"
    / "merged_visual_vocabulary.json"
)
_ENSEMBLE_PROFILES: Dict[str, Dict[str, Any]] | None = None


def _ensemble_key(value: Any) -> str:
    return unicodedata.normalize("NFKC", str(value or "")).strip().casefold()


def load_ensemble_profiles() -> Dict[str, Dict[str, Any]]:
    global _ENSEMBLE_PROFILES
    if _ENSEMBLE_PROFILES is not None:
        return _ENSEMBLE_PROFILES
    _ENSEMBLE_PROFILES = {}
    if not ENSEMBLE_PROFILE_PATH.is_file():
        return _ENSEMBLE_PROFILES
    try:
        document = json.loads(ENSEMBLE_PROFILE_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return _ENSEMBLE_PROFILES
    for profile in document.get("words", []) if isinstance(document, dict) else []:
        if not isinstance(profile, dict):
            continue
        key = _ensemble_key(profile.get("word"))
        if key:
            _ENSEMBLE_PROFILES[key] = profile
    return _ENSEMBLE_PROFILES


def ensemble_profile_for_document(document: Dict[str, Any]) -> Dict[str, Any] | None:
    profiles = load_ensemble_profiles()
    candidates = (
        document.get("word"),
        document.get("original_word"),
        document.get("vocabulary_key"),
    )
    for candidate in candidates:
        key = _ensemble_key(candidate)
        if key in profiles:
            return profiles[key]
        normalized = _ensemble_key(normalize_text(candidate))
        if normalized in profiles:
            return profiles[normalized]
    return None


def apply_ensemble_profile(
    classified: Dict[str, Any],
    source: Dict[str, Any],
) -> Dict[str, Any]:
    profile = ensemble_profile_for_document(source)
    if not profile:
        return classified
    return {
        **classified,
        "ensemble_profile": profile,
        "ensemble_learning_version": "visual-vocabulary-ensemble-v1",
        "ensemble_learning_agents": profile.get("ensemble", {}).get(
            "source_agents", []
        ),
    }


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
            "core_story_score",
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


async def _read_all_documents(cursor: Any) -> List[Dict[str, Any]]:
    """Materialize a Motor cursor without imposing an application-side cap."""
    return await cursor.to_list(length=None)


def _cacheable_documents(documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Keep the in-memory matcher consistent with the MongoDB visibility flags."""
    return [
        item
        for item in documents
        if bool(item.get("enabled", True)) and bool(item.get("usable_for_image"))
    ]


async def sync_visual_vocabulary() -> Dict[str, int]:
    global _CACHE_DOCUMENTS, _CACHE_LOADED_AT
    source_documents = await _read_all_documents(
        fit_vocabulary_collection.find({})
    )
    existing_documents = await _read_all_documents(
        visual_vocabulary_collection.find(
            {},
            {"source_key": 1, "source_fingerprint": 1},
        )
    )
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
        classified = apply_ensemble_profile(
            classify_fit_vocabulary(source),
            source,
        )
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

    _CACHE_DOCUMENTS = _cacheable_documents(classified_documents)
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
        _CACHE_DOCUMENTS = await _read_all_documents(
            visual_vocabulary_collection.find(
                {"enabled": True, "usable_for_image": True},
            )
        )
        _CACHE_LOADED_AT = now
    return match_visual_vocabulary(story_text, _CACHE_DOCUMENTS)
