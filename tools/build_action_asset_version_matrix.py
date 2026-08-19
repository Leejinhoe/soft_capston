"""Build and validate the five-step v24-v28 action-asset upgrade matrix.

Every release is written below ``output/`` so the five quality iterations are
reproducible. The verified v28 pack is also promoted into the tracked
motion-sheet directory as the canonical asset set. Existing v22/v23 assets
are never deleted or overwritten.
"""

from __future__ import annotations

import json
import hashlib
import shutil
import sys
import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
TOOLS_DIR = ROOT / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from build_all_character_action_cycles import (  # noqa: E402
    CHARACTER_KEYS,
    CELL_SIZE,
    CROP_MARGIN,
    FRAME_COUNT,
    SHEET_SIZE,
    SUPPORTED_VERSIONS,
    UPGRADE_ROUNDS,
    build_all,
    output_names,
    write_manifest,
    promote_canonical_pack,
)


VERSIONS = tuple(f"v{number}" for number in range(24, 29))
OUTPUT_ROOT = ROOT / "output" / "action_asset_versions"


def validate_version(version: str, output_dir: Path) -> dict[str, object]:
    names = output_names(version)
    files = [
        output_dir / template.format(character_key=key)
        for key in CHARACTER_KEYS
        for template in names.values()
    ]
    missing = [str(path) for path in files if not path.is_file()]
    if missing:
        raise AssertionError(f"{version}: missing {len(missing)} files")

    hashes: dict[str, str] = {}
    for path in files:
        with Image.open(path) as image:
            if image.mode != "RGBA" or image.size != SHEET_SIZE:
                raise AssertionError(
                    f"{version}: invalid sheet contract for {path.name}"
                )
            alpha = image.getchannel("A")
            if alpha.getextrema()[0] != 0:
                raise AssertionError(f"{version}: opaque canvas for {path.name}")
            for index in range(FRAME_COUNT):
                left = index % 4 * CELL_SIZE[0]
                top = index // 4 * CELL_SIZE[1]
                cell = alpha.crop(
                    (left, top, left + CELL_SIZE[0], top + CELL_SIZE[1])
                )
                if cell.getbbox() is None:
                    raise AssertionError(
                        f"{version}: empty frame {index} in {path.name}"
                    )
                bbox = cell.getbbox()
                assert bbox is not None
                if (
                    bbox[0] < CROP_MARGIN
                    or bbox[1] < CROP_MARGIN
                    or bbox[2] > CELL_SIZE[0] - CROP_MARGIN
                    or bbox[3] > CELL_SIZE[1] - CROP_MARGIN
                ):
                    raise AssertionError(
                        f"{version}: crop margin violation in {path.name} frame {index}"
                    )
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        hashes[path.name] = digest

    return {
        "version": version,
        "characters": len(CHARACTER_KEYS),
        "actions_per_character": len(names),
        "files": len(files),
        "output_dir": str(output_dir.resolve()),
        "sha256": hashes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate existing v24-v28 outputs without rebuilding them.",
    )
    args = parser.parse_args()
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    reports = []
    for version in VERSIONS:
        output_dir = OUTPUT_ROOT / version
        if not args.validate_only:
            build_all(output_dir=output_dir, version=version)
            write_manifest(output_dir, CHARACTER_KEYS, version)
        reports.append(validate_version(version, output_dir))
        print(f"{version}: {reports[-1]['files']} files validated")

    for action_name in output_names(VERSIONS[0]):
        for character_key in CHARACTER_KEYS:
            hashes = {
                report["sha256"][
                    output_names(report["version"])[action_name].format(
                        character_key=character_key
                    )
                ]
                for report in reports
            }
            if len(hashes) != len(VERSIONS):
                raise AssertionError(
                    f"Version outputs are identical for {character_key}/{action_name}"
                )

    canonical_files = promote_canonical_pack(
        OUTPUT_ROOT / "v28",
        ROOT / "assets" / "characters" / "motion_sheets",
        "v28",
    )
    canonical_manifest = write_manifest(
        ROOT / "assets" / "characters" / "motion_sheets",
        CHARACTER_KEYS,
        "v28",
    )

    report_path = OUTPUT_ROOT / "version_matrix_report.json"
    report_path.write_text(
        json.dumps(
            {
                "range": [VERSIONS[0], VERSIONS[-1]],
                "upgrade_rounds": [UPGRADE_ROUNDS[version] for version in VERSIONS],
                "versions": reports,
                "canonical": {
                    "version": "v28",
                    "files": len(canonical_files),
                    "directory": str(canonical_files[0].parent.resolve()),
                    "manifest": str(canonical_manifest.resolve()),
                },
                "contract": {
                    "sheet_size": list(SHEET_SIZE),
                    "cell_size": list(CELL_SIZE),
                    "columns": 4,
                    "rows": 2,
                    "frame_count": FRAME_COUNT,
                    "crop_margin": CROP_MARGIN,
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(report_path.resolve())


if __name__ == "__main__":
    main()
