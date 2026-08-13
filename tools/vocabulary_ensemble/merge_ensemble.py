"""Merge independent vocabulary annotations into one conservative dataset."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PHASE_NAMES = ("prepare", "act", "recover")
VOTED_FIELDS = (
    "canonical_action",
    "motion_mode",
    "participant_count",
    "requires_partner",
    "requires_object",
    "requires_target",
    "solo_action",
)


def _as_entries(document: Any) -> list[Mapping[str, Any]]:
    if isinstance(document, list):
        entries = document
    elif isinstance(document, dict):
        entries = document.get("entries") or document.get("words") or []
        if isinstance(entries, dict):
            entries = [dict(value, word=key) for key, value in entries.items()]
    else:
        entries = []
    if not isinstance(entries, list) or not all(isinstance(item, Mapping) for item in entries):
        raise ValueError("Each report must contain a list of object entries.")
    return list(entries)


def load_report(path: Path) -> tuple[str, list[Mapping[str, Any]]]:
    document = json.loads(path.read_text(encoding="utf-8-sig"))
    entries = _as_entries(document)
    if not entries or any(not str(item.get("word") or "").strip() for item in entries):
        raise ValueError(f"Report has missing words: {path}")
    return path.stem, entries


def load_reports(runs_dir: Path) -> list[tuple[str, list[Mapping[str, Any]]]]:
    paths = sorted(runs_dir.glob("agent_*.json"))
    if not paths:
        raise FileNotFoundError(f"No agent reports found in {runs_dir}")
    return [load_report(path) for path in paths]


def _clean_strings(values: Iterable[Any], *, limit: int = 15) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
        if len(result) >= limit:
            break
    return result


def _first_mode(values: Sequence[Any]) -> Any:
    counts = Counter(values)
    if not counts:
        return None
    highest = max(counts.values())
    return next(value for value in values if counts[value] == highest)


def _vote(entries: Sequence[Mapping[str, Any]], field: str, default: Any) -> Any:
    values = [entry.get(field, default) for entry in entries]
    return _first_mode(values) if values else default


def _normalise_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes"}
    return bool(value)


def _normalise_int(value: Any, default: int = 1) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _field_disagreement(entries: Sequence[Mapping[str, Any]], field: str) -> list[Any]:
    values: list[Any] = []
    for entry in entries:
        value = entry.get(field)
        if field in {"requires_partner", "requires_object", "requires_target", "solo_action"}:
            value = _normalise_bool(value)
        elif field == "participant_count":
            value = _normalise_int(value)
        if value not in values:
            values.append(value)
    return values


def _merge_phases(entries: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    phases: dict[str, list[Any]] = {name: [] for name in PHASE_NAMES}
    for entry in entries:
        for phase in entry.get("phases") or []:
            if not isinstance(phase, Mapping):
                continue
            name = str(phase.get("name") or "").strip().lower()
            if name in phases:
                phases[name].extend(phase.get("cues") or [])
    return [
        {"name": name, "cues": _clean_strings(phases[name], limit=15)}
        for name in PHASE_NAMES
    ]


def _merge_word(word: str, entries: Sequence[Mapping[str, Any]], source_names: Sequence[str]) -> dict[str, Any]:
    semantic = {
        field: _vote(entries, field, False if field.startswith("requires_") or field == "solo_action" else None)
        for field in VOTED_FIELDS
    }
    for field in ("requires_partner", "requires_object", "requires_target", "solo_action"):
        semantic[field] = _normalise_bool(semantic[field])
    semantic["participant_count"] = _normalise_int(semantic["participant_count"], default=1)

    # A majority requirement always wins over an optimistic solo label.
    if semantic["requires_partner"] or semantic["requires_object"] or semantic["requires_target"]:
        semantic["solo_action"] = False
    elif semantic["solo_action"] and semantic["participant_count"] <= 0:
        # Some annotators use zero for "no additional participant". The runtime
        # contract uses one for the character shown in the scene.
        semantic["participant_count"] = 1

    confidence_values = []
    for entry in entries:
        try:
            confidence_values.append(min(max(float(entry.get("confidence", 0.0)), 0.0), 1.0))
        except (TypeError, ValueError):
            continue
    mean_confidence = sum(confidence_values) / max(len(confidence_values), 1)
    agreement_values = []
    disagreements: dict[str, list[Any]] = {}
    for field in VOTED_FIELDS:
        values = _field_disagreement(entries, field)
        if len(values) > 1:
            disagreements[field] = values
        agreement_values.append(
            Counter(
                _normalise_bool(item.get(field))
                if field in {"requires_partner", "requires_object", "requires_target", "solo_action"}
                else _normalise_int(item.get(field))
                if field == "participant_count"
                else item.get(field)
                for item in entries
            ).most_common(1)[0][1] / len(entries)
        )
    agreement = sum(agreement_values) / max(len(agreement_values), 1)

    return {
        "word": word,
        **semantic,
        "synonyms": _clean_strings(
            (value for entry in entries for value in entry.get("synonyms") or [])
        ),
        "positive_cues": _clean_strings(
            (value for entry in entries for value in entry.get("positive_cues") or [])
        ),
        "negative_cues": _clean_strings(
            (value for entry in entries for value in entry.get("negative_cues") or [])
        ),
        "phases": _merge_phases(entries),
        "scene_requirements": _clean_strings(
            (value for entry in entries for value in entry.get("scene_requirements") or [])
        ),
        "prompt_variants": _clean_strings(
            (value for entry in entries for value in entry.get("prompt_variants") or [])
        ),
        "ambiguity_notes": _clean_strings(
            (entry.get("ambiguity_notes") for entry in entries), limit=8
        ),
        "ensemble": {
            "annotator_count": len(entries),
            "source_agents": list(source_names),
            "mean_confidence": round(mean_confidence, 3),
            "agreement": round(agreement, 3),
            "ensemble_confidence": round(0.6 * mean_confidence + 0.4 * agreement, 3),
            "disagreements": disagreements,
            "evidence_count": sum(
                len(entry.get("positive_cues") or [])
                + len(entry.get("negative_cues") or [])
                + len(entry.get("prompt_variants") or [])
                for entry in entries
            ),
        },
    }


def merge_reports(reports: Sequence[tuple[str, Sequence[Mapping[str, Any]]]]) -> dict[str, Any]:
    if len(reports) < 2:
        raise ValueError("At least two independent reports are required.")
    word_sets = [
        {str(entry.get("word") or "").strip() for entry in entries}
        for _, entries in reports
    ]
    if any(not words for words in word_sets):
        raise ValueError("Every report must contain at least one word.")
    expected = word_sets[0]
    if any(words != expected for words in word_sets[1:]):
        raise ValueError("Independent reports must use the same word set.")

    by_word: dict[str, list[Mapping[str, Any]]] = {word: [] for word in sorted(expected)}
    for _, entries in reports:
        for entry in entries:
            by_word[str(entry["word"]).strip()].append(entry)
    source_names = [name for name, _ in reports]
    words = [
        _merge_word(word, by_word[word], source_names)
        for word in sorted(by_word)
    ]
    return {
        "schema_version": 1,
        "ensemble_version": "visual-vocabulary-ensemble-v1",
        "annotator_count": len(reports),
        "word_count": len(words),
        "source_agents": source_names,
        "words": words,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parent
    parser.add_argument("--runs", type=Path, default=root / "runs")
    parser.add_argument(
        "--output",
        type=Path,
        default=root / "merged_visual_vocabulary.json",
    )
    args = parser.parse_args()
    merged = merge_reports(load_reports(args.runs))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output.resolve()), **{key: merged[key] for key in ("annotator_count", "word_count")}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
