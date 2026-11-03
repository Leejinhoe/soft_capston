"""Deterministic cache-key helpers for generated story media."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from collections.abc import Mapping
from typing import Any, Dict, Optional


CACHE_KEY_VERSION = "media-v1"


def _normalize_text(value: Any) -> str:
    """Normalize user-facing text without imposing a length-based collision."""

    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKC", str(value))
    return " ".join(normalized.strip().casefold().split())


def _canonicalize(value: Any) -> Any:
    """Return JSON-safe, recursively ordered data for stable hashing."""

    if isinstance(value, Mapping):
        return {
            _normalize_text(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: _normalize_text(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonicalize(item) for item in value]
    if isinstance(value, set):
        return sorted((_canonicalize(item) for item in value), key=_stable_json)
    if isinstance(value, str):
        return _normalize_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _normalize_text(value)


def _stable_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _asset_version(value: Any) -> Optional[str]:
    if not isinstance(value, Mapping):
        return _normalize_text(value) or None
    for field in (
        "asset_version",
        "character_asset_version",
        "version",
        "filename_version",
        "quality_tier",
    ):
        candidate = _normalize_text(value.get(field))
        if candidate:
            return candidate
    return None


def _request_parts(request: Mapping[str, Any]) -> Dict[str, Any]:
    """Accept both API-shaped requests and the cache helper's field names."""

    def first(*names: str) -> Any:
        for name in names:
            if name in request:
                return request[name]
        return None

    known = {
        "story": first("story", "story_text", "story_id"),
        "scene": first("scene", "step_number", "scene_id"),
        "character": first("character", "character_key"),
        "action": first("action", "animation_action"),
        "background": first("background", "background_key", "background_asset"),
        "character_asset_version": first(
            "character_asset_version", "asset_version", "character_asset"
        ),
        "scene_contract": first("scene_contract", "contract"),
    }
    known["character_asset"] = first("character_asset")
    known["options"] = {
        key: value
        for key, value in request.items()
        if key not in {
            "story", "story_text", "story_id", "scene", "step_number", "scene_id",
            "character", "character_key", "action", "animation_action", "background",
            "background_key", "background_asset", "character_asset_version", "asset_version",
            "character_asset", "scene_contract", "contract",
        }
    }
    return known


def canonical_media_request(
    story: Any = None,
    scene: Any = None,
    character: Any = None,
    action: Any = None,
    background: Any = None,
    character_asset_version: Any = None,
    scene_contract: Any = None,
    *,
    character_asset: Any = None,
    request: Optional[Mapping[str, Any]] = None,
    **options: Any,
) -> Dict[str, Any]:
    """Build the canonical request payload used by both key and dedup checks."""

    if request is None and isinstance(story, Mapping) and all(
        value is None
        for value in (
            scene, character, action, background, character_asset_version,
            scene_contract, character_asset,
        )
    ) and not options:
        request = story

    if request is not None:
        parts = _request_parts(request)
        story = parts["story"]
        scene = parts["scene"]
        character = parts["character"]
        action = parts["action"]
        background = parts["background"]
        character_asset_version = parts["character_asset_version"]
        scene_contract = parts["scene_contract"]
        character_asset = parts["character_asset"]
        options = {**parts["options"], **options}

    if isinstance(character_asset_version, Mapping):
        if character_asset is None:
            character_asset = character_asset_version
        character_asset_version = _asset_version(character_asset_version)
    elif character_asset_version is None:
        character_asset_version = _asset_version(character_asset)
    return _canonicalize(
        {
            "story": story,
            "scene": scene,
            "character": character,
            "action": action,
            "background": background,
            "character_asset_version": character_asset_version,
            "character_asset": character_asset,
            "scene_contract": scene_contract,
            "options": options,
        }
    )


def build_media_cache_key(
    story: Any = None,
    scene: Any = None,
    character: Any = None,
    action: Any = None,
    background: Any = None,
    character_asset_version: Any = None,
    scene_contract: Any = None,
    *,
    character_asset: Any = None,
    request: Optional[Mapping[str, Any]] = None,
    **options: Any,
) -> str:
    """Return a fixed-length key for one complete media-generation request."""

    payload = canonical_media_request(
        story, scene, character, action, background, character_asset_version,
        scene_contract, character_asset=character_asset, request=request, **options
    )
    digest = hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_VERSION}:{digest}"


def is_duplicate_media_request(
    existing_request: Mapping[str, Any],
    requested_request: Mapping[str, Any],
) -> bool:
    """Return whether two requests identify the same generated media."""

    return build_media_cache_key(request=existing_request) == build_media_cache_key(
        request=requested_request
    )


media_requests_match = is_duplicate_media_request
