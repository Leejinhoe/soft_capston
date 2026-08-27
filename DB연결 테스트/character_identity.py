"""Pure helpers for keeping a character identity stable across scene assets."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any, Dict, Optional


_IDENTITY_FIELDS = (
    "character_key",
    "face_asset",
    "image_file_id",
    "asset_version",
    "asset_fingerprint",
)


def _clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _asset_id(asset: Any) -> Optional[str]:
    if isinstance(asset, Mapping):
        return _clean(
            asset.get("face_asset")
            or asset.get("image_file_id")
            or asset.get("image_id")
        )
    return _clean(asset)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def asset_fingerprint(asset: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Return a stable digest for an asset's identity-relevant content.

    Runtime URLs, database ids, and presentation-only fields are excluded so
    the digest remains useful when the same asset is served from another store.
    """
    if not isinstance(asset, Mapping):
        return None
    identity_data = {
        key: asset[key]
        for key in (
            "character_key",
            "face_asset",
            "asset_version",
            "pose",
            "emotion",
            "quality_tier",
            "tags",
            "scene_keywords",
            "identity_anchor",
        )
        if key in asset and asset[key] is not None
    }
    image_file_id = _asset_id(asset)
    if image_file_id:
        identity_data["image_file_id"] = image_file_id
    if not identity_data:
        return None
    return hashlib.sha256(_canonical_json(identity_data).encode("utf-8")).hexdigest()


def asset_version(asset: Optional[Mapping[str, Any]]) -> Optional[str]:
    """Read an explicit asset version, falling back to its stable fingerprint."""
    if not isinstance(asset, Mapping):
        return None
    return (
        _clean(asset.get("asset_version") or asset.get("version"))
        or _clean(asset.get("asset_fingerprint"))
        or asset_fingerprint(asset)
    )


def build_character_identity_context(
    character_key: Any = None,
    face_asset: Any = None,
    image_file_id: Any = None,
    asset_version: Any = None,
    fingerprint: Any = None,
    asset: Optional[Mapping[str, Any]] = None,
    profile: Optional[Mapping[str, Any]] = None,
) -> Dict[str, str]:
    """Build a serializable identity anchor without using a display name.

    Explicit arguments take precedence, followed by the supplied asset and
    profile. ``face_asset`` and ``image_file_id`` are retained as aliases for
    compatibility with scene payloads that use either field.
    """
    profile = profile if isinstance(profile, Mapping) else {}
    asset = asset if isinstance(asset, Mapping) else {}
    key = _clean(character_key) or _clean(asset.get("character_key")) or _clean(profile.get("character_key"))
    face_id = _clean(face_asset) or _asset_id(face_asset) or _asset_id(asset)
    image_id = _clean(image_file_id) or _clean(asset.get("image_file_id")) or face_id
    face_id = face_id or image_id
    image_id = image_id or face_id
    version = _clean(asset_version) or asset_version_from_context(asset) or get_asset_version(asset)
    stable_fingerprint = _clean(fingerprint) or _clean(asset.get("asset_fingerprint")) or asset_fingerprint(asset)

    context: Dict[str, str] = {}
    for field, value in (
        ("character_key", key),
        ("face_asset", face_id),
        ("image_file_id", image_id),
        ("asset_version", version),
        ("asset_fingerprint", stable_fingerprint),
    ):
        if value:
            context[field] = value
    if context:
        context["identity_fingerprint"] = hashlib.sha256(
            _canonical_json({field: context.get(field) for field in _IDENTITY_FIELDS}).encode("utf-8")
        ).hexdigest()
    return context


def asset_version_from_context(asset: Mapping[str, Any]) -> Optional[str]:
    """Read a nested identity context used by already persisted assets."""
    nested = asset.get("identity_context")
    if isinstance(nested, Mapping):
        return _clean(nested.get("asset_version") or nested.get("asset_fingerprint"))
    return None


def with_character_identity(
    asset: Optional[Mapping[str, Any]],
    context: Optional[Mapping[str, Any]],
) -> Optional[Dict[str, Any]]:
    """Return an asset copy carrying the identity context and version fields."""
    if not isinstance(asset, Mapping):
        return None
    if isinstance(context, Mapping) and context:
        identity = build_character_identity_context(
            character_key=context.get("character_key"),
            face_asset=context.get("face_asset") or _asset_id(asset),
            image_file_id=context.get("image_file_id") or _asset_id(asset),
            asset_version=context.get("asset_version"),
            fingerprint=context.get("asset_fingerprint") or context.get("fingerprint"),
        )
    else:
        identity = build_character_identity_context(asset=asset)
    result = dict(asset)
    if identity:
        result["identity_context"] = identity
        result.setdefault("character_key", identity.get("character_key"))
        result.setdefault("face_asset", identity.get("face_asset"))
        result.setdefault("image_file_id", identity.get("image_file_id"))
        result["asset_version"] = identity.get("asset_version")
        result["asset_fingerprint"] = identity.get("asset_fingerprint")
    return result


def character_identity_matches(
    expected: Optional[Mapping[str, Any]],
    actual: Optional[Mapping[str, Any]],
) -> bool:
    """Compare identity anchors, allowing missing legacy fields."""
    def context_values(value: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
        if not isinstance(value, Mapping):
            return {}
        return {
            "character_key": value.get("character_key"),
            "face_asset": value.get("face_asset"),
            "image_file_id": value.get("image_file_id"),
            "asset_version": value.get("asset_version"),
            "fingerprint": value.get("asset_fingerprint") or value.get("fingerprint"),
        }

    left = build_character_identity_context(**context_values(expected))
    right = build_character_identity_context(**context_values(actual))
    for field in ("character_key", "face_asset", "image_file_id", "asset_version", "asset_fingerprint"):
        if left.get(field) and right.get(field) and left[field] != right[field]:
            return False
    return bool(left and right)


def identity_context_from_profile(profile: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """Create an anchor from a profile, preferring its default/reference asset."""
    if not isinstance(profile, Mapping):
        return {}
    assets = profile.get("assets")
    selected = next(
        (item for item in assets if item.get("quality_tier") == "premium_reference")
        if isinstance(assets, list) else (),
        None,
    )
    if selected is None and isinstance(assets, list):
        selected = next((item for item in assets if item.get("pose") == "default"), None)
    return build_character_identity_context(profile=profile, asset=selected)


# Short aliases for callers that use the vocabulary from the API payloads.
build_identity_context = build_character_identity_context
build_asset_identity_context = build_character_identity_context
get_asset_fingerprint = asset_fingerprint
get_asset_version = asset_version
resolve_asset_version = asset_version


def identity_context_from_asset(asset: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    return build_character_identity_context(asset=asset)
