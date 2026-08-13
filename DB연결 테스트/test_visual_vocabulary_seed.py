import asyncio
import os
import sys
import unittest
from pathlib import Path


# database.py creates a Motor client at import time, but these tests never query it.
os.environ.setdefault("MONGO_URI", "mongodb://127.0.0.1:27017")
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from visual_vocabulary_seed import (  # noqa: E402
    _fingerprint,
    _cacheable_documents,
    _read_all_documents,
    apply_ensemble_profile,
)


class _CursorProbe:
    def __init__(self, documents):
        self.documents = documents
        self.requested_length = "not-called"

    async def to_list(self, length=None):
        self.requested_length = length
        return self.documents


class VisualVocabularySeedTests(unittest.TestCase):
    def test_ensemble_profile_is_attached_without_replacing_classifier_fields(self):
        source = {"word": "걷다"}
        classified = {
            "primary_role": "action",
            "action_semantics": {"animation_action": "journey"},
        }

        enriched = apply_ensemble_profile(classified, source)

        self.assertEqual(enriched["primary_role"], "action")
        self.assertEqual(
            enriched["action_semantics"]["animation_action"],
            "journey",
        )
        self.assertEqual(enriched["ensemble_profile"]["word"], "걷다")

    def test_read_all_documents_does_not_apply_5000_document_cap(self):
        documents = [{"word": f"word-{index}"} for index in range(5001)]
        cursor = _CursorProbe(documents)

        result = asyncio.run(_read_all_documents(cursor))

        self.assertIs(result, documents)
        self.assertIsNone(cursor.requested_length)

    def test_core_story_score_changes_source_fingerprint(self):
        source = {
            "word": "모험하다",
            "meaning": "새로운 일을 시도하다",
            "fit_score": 0.8,
            "core_story_score": 0.4,
        }

        original = _fingerprint(source)
        source["core_story_score"] = 0.9

        self.assertNotEqual(original, _fingerprint(source))

    def test_disabled_documents_are_not_kept_in_matcher_cache(self):
        documents = [
            {"word": "visible", "enabled": True, "usable_for_image": True},
            {"word": "disabled", "enabled": False, "usable_for_image": True},
            {"word": "unusable", "enabled": True, "usable_for_image": False},
        ]

        self.assertEqual(
            [item["word"] for item in _cacheable_documents(documents)],
            ["visible"],
        )


if __name__ == "__main__":
    unittest.main()
