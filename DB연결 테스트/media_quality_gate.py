"""Deterministic, model-free quality checks for generated media."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Union

import numpy as np
from PIL import Image, ImageStat


PathLike = Union[str, Path]
DEFAULTS = {
    "black_pixel_ratio": 0.98,
    "uniform_pixel_ratio": 0.995,
    "min_motion_score": 0.0015,
    "max_sampled_frames": 12,
}


def _result(media_type: str) -> Dict[str, Any]:
    return {
        "passed": True,
        "media_type": media_type,
        "reasons": [],
        "measurements": {},
        "metadata": {},
    }


def _fail(result: Dict[str, Any], code: str, message: str) -> None:
    result["passed"] = False
    result["reasons"].append({"code": code, "message": message})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata_value(metadata: Mapping[str, Any], *names: str) -> Any:
    for name in names:
        if name in metadata:
            return metadata[name]
    return None


def _check_metadata(
    result: Dict[str, Any],
    metadata: Optional[Mapping[str, Any]],
    expected_character_key: Optional[str],
    expected_asset_fingerprint: Optional[str],
) -> None:
    supplied = dict(metadata or {})
    result["metadata"] = supplied
    actual_character = _metadata_value(supplied, "character_key", "expected_character_key")
    actual_fingerprint = _metadata_value(
        supplied, "asset_fingerprint", "fingerprint", "expected_asset_fingerprint"
    )
    result["measurements"]["character_key"] = actual_character
    result["measurements"]["asset_fingerprint"] = actual_fingerprint
    if expected_character_key is not None and actual_character != expected_character_key:
        _fail(result, "character_key_mismatch", "Media character_key does not match the expected character_key.")
    if expected_asset_fingerprint is not None and actual_fingerprint != expected_asset_fingerprint:
        _fail(result, "asset_fingerprint_mismatch", "Media asset fingerprint does not match the expected fingerprint.")


def _image_stats(image: Image.Image) -> Dict[str, float]:
    gray = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    histogram = np.bincount((gray * 255).astype(np.uint8).ravel(), minlength=256)
    probabilities = histogram[histogram > 0] / gray.size
    return {
        "width": float(image.width),
        "height": float(image.height),
        "mean_luma": float(gray.mean()),
        "std_luma": float(gray.std()),
        "black_pixel_ratio": float((gray <= 0.01).mean()),
        "near_uniform_pixel_ratio": float((gray <= 0.01).mean() + (gray >= 0.99).mean()),
        "entropy_bits": float(-(probabilities * np.log2(probabilities)).sum()),
    }


def _check_image(result: Dict[str, Any], path: Path, options: Mapping[str, Any]) -> None:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            if image.width < 2 or image.height < 2:
                _fail(result, "invalid_dimensions", "Image dimensions are too small.")
            result["measurements"].update(_image_stats(image))
    except Exception as exc:
        _fail(result, "corrupt_file", "Image could not be decoded: %s" % exc)
        return
    measurements = result["measurements"]
    if measurements["black_pixel_ratio"] >= options["black_pixel_ratio"]:
        _fail(result, "black_frame", "Image is overwhelmingly black.")
    if measurements["near_uniform_pixel_ratio"] >= options["uniform_pixel_ratio"]:
        _fail(result, "uniform_frame", "Image contains almost no visual variation.")


def _sample_video(path: Path, limit: int) -> Iterable[np.ndarray]:
    import imageio.v2 as imageio

    reader = imageio.get_reader(str(path))
    try:
        meta = reader.get_meta_data() or {}
        yield from ()
        raw_count = meta.get("nframes")
        count = int(raw_count) if raw_count and math.isfinite(float(raw_count)) else 0
        indices = list(range(min(count, limit))) if count else list(range(limit))
        for index in indices:
            try:
                yield np.asarray(reader.get_data(index))
            except IndexError:
                break
    finally:
        reader.close()


def _check_video(result: Dict[str, Any], path: Path, options: Mapping[str, Any]) -> None:
    try:
        frames = list(_sample_video(path, options["max_sampled_frames"]))
    except Exception as exc:
        _fail(result, "corrupt_file", "Video could not be decoded: %s" % exc)
        return
    if not frames:
        _fail(result, "no_frames", "Video contains no decodable frames.")
        return
    arrays = [frame.astype(np.float32) for frame in frames]
    luma = [np.asarray(Image.fromarray(frame.astype(np.uint8)).convert("L"), dtype=np.float32) / 255.0 for frame in arrays]
    black_ratios = [float((frame <= 0.01).mean()) for frame in luma]
    differences = [float(np.mean(np.abs(current - previous))) for previous, current in zip(luma, luma[1:])]
    motion_score = float(np.mean(differences)) if differences else 0.0
    result["measurements"].update({
        "sampled_frames": len(frames),
        "black_frame_ratio": float(np.mean([ratio >= options["black_pixel_ratio"] for ratio in black_ratios])),
        "max_black_pixel_ratio": max(black_ratios),
        "motion_score": motion_score,
        "mean_frame_luma": float(np.mean([frame.mean() for frame in luma])),
        "width": int(frames[0].shape[1]),
        "height": int(frames[0].shape[0]),
    })
    if result["measurements"]["black_frame_ratio"] >= options["black_pixel_ratio"]:
        _fail(result, "black_frame", "Most sampled video frames are overwhelmingly black.")
    if len(frames) > 1 and motion_score < options["min_motion_score"]:
        _fail(result, "static_video", "Video has insufficient frame-to-frame motion.")


def evaluate_media_quality(
    media_path: PathLike,
    media_type: Optional[str] = None,
    *,
    metadata: Optional[Mapping[str, Any]] = None,
    expected_character_key: Optional[str] = None,
    expected_asset_fingerprint: Optional[str] = None,
    thresholds: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return a deterministic quality report; never raises for bad media files."""
    path = Path(media_path)
    kind = (media_type or ("video" if path.suffix.lower() in {".mp4", ".mov", ".webm", ".avi", ".mkv"} else "image")).lower()
    result = _result(kind)
    options = dict(DEFAULTS)
    options.update(thresholds or {})
    result["measurements"]["file_exists"] = path.is_file()
    if not path.is_file():
        _fail(result, "missing_file", "Media file does not exist.")
        _check_metadata(result, metadata, expected_character_key, expected_asset_fingerprint)
        return result
    try:
        result["measurements"]["file_size_bytes"] = path.stat().st_size
        result["measurements"]["sha256"] = _sha256(path)
        if path.stat().st_size == 0:
            _fail(result, "empty_file", "Media file is empty.")
        elif kind == "image":
            _check_image(result, path, options)
        elif kind == "video":
            _check_video(result, path, options)
        else:
            _fail(result, "unsupported_media_type", "media_type must be 'image' or 'video'.")
    except Exception as exc:
        _fail(result, "inspection_error", "Media inspection failed: %s" % exc)
    _check_metadata(result, metadata, expected_character_key, expected_asset_fingerprint)
    return result


check_media_quality = evaluate_media_quality
inspect_media_quality = evaluate_media_quality
media_quality_gate = evaluate_media_quality
