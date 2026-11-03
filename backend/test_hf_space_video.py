import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import hf_space_video
from hf_media_common import HfMediaError


class VideoSpaceTests(unittest.TestCase):
    def test_disabled_by_default(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(hf_space_video.enabled())

    def test_remote_result_is_checked_and_seed_zero_is_preserved(self):
        submitted = []

        class Client:
            def __init__(self, space, hf_token=None, verbose=False, download_files=None):
                self.folder = download_files

            def submit(self, image, action, seed, api_name):
                submitted.append((action, seed, api_name))
                path = Path(self.folder) / "output.mp4"
                path.write_bytes(b"\x00\x00\x00\x18ftypisomtest")
                return SimpleNamespace(result=lambda timeout: {"video": str(path)})

        fake = SimpleNamespace(Client=Client, handle_file=lambda path: path)
        with patch.dict(sys.modules, {"gradio_client": fake}), patch.dict(os.environ, {
            "HF_TOKEN": "test", "HF_VIDEO_SPACE_ID": "owner/private",
        }):
            data = hf_space_video._generate(b"image", "wave", 0)
        self.assertEqual(data[4:8], b"ftyp")
        self.assertEqual(submitted, [("wave", 0, "/generate")])

    def test_rejects_output_outside_download_directory(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as other:
            class Client:
                def __init__(self, space, hf_token=None, verbose=False, download_files=None):
                    pass

                def submit(self, *args, **kwargs):
                    return SimpleNamespace(result=lambda timeout: other.name)

            fake = SimpleNamespace(Client=Client, handle_file=lambda path: path)
            with patch.dict(sys.modules, {"gradio_client": fake}), patch.dict(os.environ, {
                "HF_TOKEN": "test", "HF_VIDEO_SPACE_ID": "owner/private",
            }), self.assertRaises(HfMediaError):
                hf_space_video._generate(b"image", "wave", 42)


    def test_korean_story_text_is_translated_to_english_motion_prompt_for_t5(self):
        prompt = hf_space_video._normalize_video_action_prompt(
            "미나(은)는 무지갯빛 다리를 건너 별빛 정원으로 힘차게 나아갔습니다."
        )
        self.assertIn("walks forward", prompt)
        self.assertEqual(hf_space_video._normalize_video_action_prompt("wave"), "wave")


if __name__ == "__main__":
    unittest.main()
