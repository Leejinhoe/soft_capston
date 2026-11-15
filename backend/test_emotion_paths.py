import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fairytale_emotion_service import resolve_model_artifact_paths


class EmotionModelPathTests(unittest.TestCase):
    def test_default_checkpoint_is_project_relative(self):
        root = Path("project")
        checkpoint, tokenizer = resolve_model_artifact_paths(root, {})
        self.assertEqual(checkpoint, root / "models" / "emotion_checkpoint")
        self.assertEqual(tokenizer, "beomi/KcELECTRA-base-v2022")

    def test_bundled_tokenizer_is_preferred(self):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            tokenizer_path = root / "models" / "emotion_tokenizer"
            tokenizer_path.mkdir(parents=True)
            (tokenizer_path / "vocab.txt").write_text("token", encoding="utf-8")

            _, tokenizer = resolve_model_artifact_paths(root, {})

            self.assertEqual(tokenizer, tokenizer_path)

    def test_relative_environment_overrides_use_project_root(self):
        root = Path("project")
        checkpoint, tokenizer = resolve_model_artifact_paths(root, {
            "KOTE_MODEL_PATH": "custom/checkpoint",
            "KOTE_TOKENIZER": "custom/tokenizer",
        })
        self.assertEqual(checkpoint, root / "custom" / "checkpoint")
        self.assertEqual(tokenizer, root / "custom" / "tokenizer")


if __name__ == "__main__":
    unittest.main()
