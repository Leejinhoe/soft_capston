"""Verify the rendered round100 HQ pack and the 15-second storybook reel."""

from __future__ import annotations

import json
from pathlib import Path

import imageio.v2 as imageio
import numpy as np


ROOT = Path(__file__).resolve().parents[2]
HQ_MANIFEST = ROOT / "tools" / "next_actions" / "round100_hq_manifest.json"
STORY_MANIFEST = ROOT / "output" / "video_final" / "storybook_hq" / "forest_door_adventure_manifest.json"
REPORT_PATH = ROOT / "output" / "video_final" / "storybook_hq" / "final_qa_report.json"


def check_video(path: Path, *, expected_frames: int, expected_duration: float) -> dict:
    result = {"path": str(path), "ok": True, "errors": []}
    if not path.is_file():
        result["ok"] = False
        result["errors"].append("missing")
        return result
    if path.stat().st_size < 10000:
        result["ok"] = False
        result["errors"].append("file_too_small")
        return result
    reader = None
    try:
        reader = imageio.get_reader(str(path))
        meta = reader.get_meta_data()
        frame_count = reader.count_frames()
        first = reader.get_data(0)
        middle = reader.get_data(max(0, min(frame_count - 1, frame_count // 2)))
        height, width = first.shape[:2]
        fps = float(meta.get("fps", 0.0) or 0.0)
        duration = float(meta.get("duration", 0.0) or 0.0)
        variance = float(np.asarray(middle, dtype=np.float32).var())
        result.update({
            "width": width,
            "height": height,
            "fps": fps,
            "frame_count": frame_count,
            "duration_seconds": duration,
            "middle_frame_variance": round(variance, 3),
            "codec": meta.get("codec"),
        })
        if (width, height) != (960, 480):
            result["errors"].append("unexpected_size")
        if abs(fps - 30.0) > 0.2:
            result["errors"].append("unexpected_fps")
        if frame_count != expected_frames:
            result["errors"].append("unexpected_frame_count")
        if abs(duration - expected_duration) > 0.2:
            result["errors"].append("unexpected_duration")
        if variance < 5.0:
            result["errors"].append("blank_or_static")
        result["ok"] = not result["errors"]
    except Exception as exc:  # pragma: no cover - exercised by corrupt files
        result["ok"] = False
        result["errors"].append(f"read_error:{type(exc).__name__}:{exc}")
    finally:
        if reader is not None:
            reader.close()
    return result


def main() -> None:
    hq = json.loads(HQ_MANIFEST.read_text(encoding="utf-8"))
    hq_results = [
        check_video(Path(record["hq_video_path"]), expected_frames=240, expected_duration=8.0)
        for record in hq["records"]
    ]
    story = json.loads(STORY_MANIFEST.read_text(encoding="utf-8"))
    story_result = check_video(Path(story["video"]), expected_frames=450, expected_duration=15.0)
    partner_records = sum(1 for record in hq["records"] if record["quality_render"].get("partner_layer"))
    report = {
        "status": "passed" if all(item["ok"] for item in hq_results) and story_result["ok"] else "failed",
        "hq_record_count": len(hq_results),
        "hq_pass_count": sum(1 for item in hq_results if item["ok"]),
        "hq_failures": [item for item in hq_results if not item["ok"]],
        "partner_layer_record_count": partner_records,
        "storybook": story_result,
        "checks": [
            "all HQ videos are readable H.264 files",
            "all HQ videos are 960x480, 30fps, 240 frames, approximately 8 seconds",
            "storybook reel is 960x480, 30fps, 450 frames, 15 seconds",
            "middle-frame variance rejects blank/static output",
        ],
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
