import argparse
import asyncio
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "DB연결 테스트"
sys.path.insert(0, str(BACKEND_DIR))
EVENT_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(EVENT_LOOP)

from database import fit_vocabulary_collection  # noqa: E402
from motion_policy import is_solo_action_semantics  # noqa: E402
from visual_vocabulary import classify_fit_vocabulary  # noqa: E402


async def load_rows():
    query = {
        "$or": [
            {"pos_group": "동사"},
            {"part_of_speech": "동사"},
        ]
    }
    projection = {
        "_id": 0,
        "word": 1,
        "original_word": 1,
        "meaning": 1,
        "child_friendly_meaning": 1,
        "fit_score": 1,
        "pos_group": 1,
        "part_of_speech": 1,
    }
    source_documents = await fit_vocabulary_collection.find(
        query,
        projection,
    ).sort("word", 1).to_list(length=500)

    rows = []
    for source in source_documents:
        classified = classify_fit_vocabulary(source)
        semantics = classified.get("action_semantics") or {}
        rows.append(
            {
                "word": classified["word"],
                "meaning": classified["meaning"],
                "primary_role": classified["primary_role"],
                "action_tags": classified["action_tags"],
                "motion_mode": semantics.get("motion_mode"),
                "participant_count": semantics.get("participant_count"),
                "requires_partner": semantics.get("requires_partner", False),
                "interaction_kind": semantics.get("interaction_kind"),
                "subject_role": semantics.get("subject_role"),
                "partner_role": semantics.get("partner_role"),
                "requires_object": semantics.get("requires_object", False),
                "object_role": semantics.get("object_role"),
                "requires_target": semantics.get("requires_target", False),
                "target_type": semantics.get("target_type"),
                "solo_action": is_solo_action_semantics(semantics),
                "body_focus": semantics.get("body_focus"),
                "path_pattern": semantics.get("path_pattern"),
                "temporal_pattern": semantics.get("temporal_pattern"),
                "fit_score": source.get("fit_score"),
            }
        )
    return rows


def print_table(rows):
    for row in rows:
        tags = ",".join(row["action_tags"]) or "-"
        print(
            "\t".join(
                [
                    row["word"],
                    row["meaning"],
                    f"role={row['primary_role']}",
                    f"tags={tags}",
                    f"motion={row['motion_mode'] or '-'}",
                    f"participants={row['participant_count'] if row['participant_count'] is not None else '-'}",
                    f"partner={row['requires_partner']}",
                    f"kind={row['interaction_kind'] or '-'}",
                    f"object={row['object_role'] or '-'}",
                    f"target={row['target_type'] or '-'}",
                    f"solo={row['solo_action']}",
                    f"body={row['body_focus'] or '-'}",
                    f"path={row['path_pattern'] or '-'}",
                    f"time={row['temporal_pattern'] or '-'}",
                ]
            )
        )
    print(f"TOTAL={len(rows)}")


async def main():
    parser = argparse.ArgumentParser(
        description="Compare fit_vocabulary verb meanings with visual action semantics."
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--only-unmapped", action="store_true")
    parser.add_argument("--solo-only", action="store_true")
    parser.add_argument("--non-solo-only", action="store_true")
    args = parser.parse_args()

    rows = await load_rows()
    if args.only_unmapped:
        rows = [row for row in rows if not row["motion_mode"]]
    if args.solo_only and args.non_solo_only:
        parser.error("--solo-only and --non-solo-only cannot be used together")
    if args.solo_only:
        rows = [row for row in rows if row["solo_action"]]
    elif args.non_solo_only:
        rows = [row for row in rows if not row["solo_action"]]
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        print_table(rows)


if __name__ == "__main__":
    try:
        EVENT_LOOP.run_until_complete(main())
    finally:
        EVENT_LOOP.close()
