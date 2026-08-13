import argparse
import asyncio
import json
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "DB연결 테스트"
sys.path.insert(0, str(BACKEND_DIR))
EVENT_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(EVENT_LOOP)

from database import fit_vocabulary_collection  # noqa: E402
from visual_vocabulary import classify_fit_vocabulary  # noqa: E402


async def load_rows():
    projection = {
        "_id": 0,
        "word": 1,
        "original_word": 1,
        "meaning": 1,
        "child_friendly_meaning": 1,
        "fit_score": 1,
        "pos_group": 1,
        "part_of_speech": 1,
        "enabled": 1,
    }
    source_documents = await fit_vocabulary_collection.find(
        {}, projection
    ).to_list(length=5000)

    rows = []
    for source in source_documents:
        classified = classify_fit_vocabulary(source)
        try:
            fit_score = float(source.get("fit_score") or 0)
        except (TypeError, ValueError):
            fit_score = 0.0
        rows.append(
            {
                "word": classified["word"],
                "meaning": classified["meaning"],
                "pos_group": classified["pos_group"],
                "fit_score": fit_score,
                "primary_role": classified["primary_role"],
                "usable_for_image": classified["usable_for_image"],
                "ambiguous": classified["ambiguous"],
                "background_keys": classified["background_keys"],
                "action_tags": classified["action_tags"],
                "emotion_tags": classified["emotion_tags"],
                "effect_tags": classified["effect_tags"],
                "prop_tags": classified["prop_tags"],
                "motion_modifier_tags": classified["motion_modifier_tags"],
            }
        )
    return rows


def summarize(rows):
    return {
        "total": len(rows),
        "usable": sum(row["usable_for_image"] for row in rows),
        "unmapped": sum(not row["usable_for_image"] for row in rows),
        "by_pos": dict(Counter(row["pos_group"] for row in rows)),
        "by_role": dict(Counter(row["primary_role"] for row in rows)),
    }


def print_table(rows):
    for row in rows:
        tags = sorted(
            set(
                row["background_keys"]
                + row["action_tags"]
                + row["emotion_tags"]
                + row["effect_tags"]
                + row["prop_tags"]
                + row["motion_modifier_tags"]
            )
        )
        print(
            "\t".join(
                [
                    row["word"],
                    row["meaning"],
                    f"pos={row['pos_group']}",
                    f"fit={row['fit_score']:g}",
                    f"role={row['primary_role']}",
                    f"usable={row['usable_for_image']}",
                    f"ambiguous={row['ambiguous']}",
                    f"tags={','.join(tags) or '-'}",
                ]
            )
        )
    print(f"TOTAL={len(rows)}")


async def main():
    parser = argparse.ArgumentParser(
        description="Audit how fit_vocabulary words map to visual generation context."
    )
    parser.add_argument(
        "--pos",
        choices=("all", "noun", "verb", "adjective", "adverb", "unknown"),
        default="all",
    )
    parser.add_argument("--only-unmapped", action="store_true")
    parser.add_argument("--only-usable", action="store_true")
    parser.add_argument("--min-fit-score", type=float, default=0.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()

    rows = await load_rows()
    if args.pos != "all":
        rows = [row for row in rows if row["pos_group"] == args.pos]
    if args.only_unmapped:
        rows = [row for row in rows if not row["usable_for_image"]]
    if args.only_usable:
        rows = [row for row in rows if row["usable_for_image"]]
    rows = [row for row in rows if row["fit_score"] >= args.min_fit_score]
    rows.sort(key=lambda row: (-row["fit_score"], row["pos_group"], row["word"]))
    if args.limit > 0:
        rows = rows[: args.limit]

    output = {"summary": summarize(rows), "rows": rows} if args.summary else rows
    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    elif args.summary:
        print(json.dumps(output["summary"], ensure_ascii=False, indent=2))
        print_table(rows)
    else:
        print_table(rows)


if __name__ == "__main__":
    try:
        EVENT_LOOP.run_until_complete(main())
    finally:
        EVENT_LOOP.close()
