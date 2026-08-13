"""Verify the 100-word canonical motion-sheet and video pack."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import imageio.v2 as imageio
import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "tools" / "next_actions" / "round100_catalog.json"
REPORT = ROOT / "output" / "video_final" / "generated_round100" / "round100_qa_report.json"


def verify_asset(path: Path) -> dict[str, Any]:
    with Image.open(path) as source:
        image = source.convert("RGBA")
        width, height = image.size
        cells: list[dict[str, Any]] = []
        for index in range(8):
            column = index % 4
            row = index // 4
            left = round(column * width / 4)
            right = round((column + 1) * width / 4)
            top = round(row * height / 2)
            bottom = round((row + 1) * height / 2)
            cell = image.crop((left, top, right, bottom))
            bbox = cell.getchannel("A").getbbox()
            cells.append({"index": index + 1, "size": [cell.width, cell.height], "non_empty": bbox is not None})
        valid = width >= 4 and height >= 2 and all(item["non_empty"] for item in cells)
        return {"valid": valid, "size": [width, height], "cells": cells}


def verify_video(path: Path) -> dict[str, Any]:
    reader = imageio.get_reader(str(path))
    meta = reader.get_meta_data()
    frame_count = reader.count_frames()
    sample = reader.get_data(min(120, max(0, frame_count - 1)))
    reader.close()
    size = list(meta.get("size", ()))
    fps = round(float(meta.get("fps", 0)), 3)
    codec = str(meta.get("codec", "")).lower()
    variance = float(np.asarray(sample).var())
    valid = size == [960, 480] and fps == 30 and frame_count == 240 and codec in {"h264", "avc1"} and variance >= 20
    return {"valid": valid, "size": size, "fps": fps, "frame_count": frame_count, "codec": codec, "sample_variance": round(variance, 2)}


def main() -> None:
    manifest = json.loads(CATALOG.read_text(encoding="utf-8"))
    records = manifest.get("records", [])
    asset_results = []
    video_results = []
    for record in records:
        asset_path = Path(record["motion_sheet_path"])
        video_path = Path(record["video_path"])
        asset_results.append({"key": record["key"], "path": str(asset_path), **verify_asset(asset_path)})
        video_results.append({"key": record["key"], "path": str(video_path), **verify_video(video_path)})

    groups = Counter(record["group"] for record in records)
    report = {
        "report_version": "round100-qa-v1",
        "status": "passed" if len(records) == 100 and sum(groups.values()) == 100 and all(value > 0 for value in groups.values()) and all(item["valid"] for item in asset_results + video_results) else "failed",
        "target_word_count": 100,
        "manifest_record_count": len(records),
        "groups": dict(sorted(groups.items())),
        "asset_count": sum(1 for item in asset_results if item["valid"]),
        "video_count": sum(1 for item in video_results if item["valid"]),
        "asset_failures": [item for item in asset_results if not item["valid"]],
        "video_failures": [item for item in video_results if not item["valid"]],
        "format_contract": {"video_size": [960, 480], "fps": 30, "frame_count": 240, "codec": "H.264", "motion_sheet_grid": "4x2 with eight non-empty alpha cells"},
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "manifest_record_count": report["manifest_record_count"], "asset_count": report["asset_count"], "video_count": report["video_count"], "groups": report["groups"], "report": str(REPORT)}, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
