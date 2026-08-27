import tempfile
import unittest
from pathlib import Path

import imageio.v2 as imageio
import numpy as np
from PIL import Image

from media_quality_gate import evaluate_media_quality


class MediaQualityGateTests(unittest.TestCase):
    def test_valid_image_reports_measurements_and_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "good.png"
            image = np.zeros((20, 20, 3), dtype=np.uint8)
            image[:10, :, :] = [40, 120, 200]
            image[10:, :, :] = [210, 80, 30]
            Image.fromarray(image).save(path)
            report = evaluate_media_quality(
                path, metadata={"character_key": "female_04", "asset_fingerprint": "fp-1"},
                expected_character_key="female_04", expected_asset_fingerprint="fp-1",
            )
        self.assertTrue(report["passed"])
        self.assertIn("sha256", report["measurements"])
        self.assertGreater(report["measurements"]["entropy_bits"], 0)

    def test_black_and_corrupt_images_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            black = Path(directory) / "black.png"
            Image.fromarray(np.zeros((12, 12, 3), dtype=np.uint8)).save(black)
            corrupt = Path(directory) / "broken.png"
            corrupt.write_bytes(b"not an image")
            black_report = evaluate_media_quality(black, media_type="image")
            corrupt_report = evaluate_media_quality(corrupt, media_type="image")
        self.assertFalse(black_report["passed"])
        self.assertIn("black_frame", {reason["code"] for reason in black_report["reasons"]})
        self.assertFalse(corrupt_report["passed"])
        self.assertIn("corrupt_file", {reason["code"] for reason in corrupt_report["reasons"]})

    def test_metadata_mismatch_fails_with_both_reasons(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "good.png"
            Image.fromarray(np.full((10, 10, 3), 100, dtype=np.uint8)).save(path)
            report = evaluate_media_quality(path, metadata={"character_key": "wrong", "asset_fingerprint": "old"}, expected_character_key="right", expected_asset_fingerprint="new")
        self.assertFalse(report["passed"])
        self.assertEqual({"character_key_mismatch", "asset_fingerprint_mismatch"}, {reason["code"] for reason in report["reasons"]})

    def test_static_video_fails_without_network_or_models(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "static.mp4"
            frames = [np.full((32, 32, 3), 90, dtype=np.uint8) for _ in range(4)]
            imageio.mimwrite(path, frames, fps=4, format="FFMPEG")
            report = evaluate_media_quality(path, media_type="video")
        self.assertFalse(report["passed"])
        self.assertIn("static_video", {reason["code"] for reason in report["reasons"]})
        self.assertGreaterEqual(report["measurements"]["sampled_frames"], 2)

    def test_missing_file_is_structured_failure(self):
        report = evaluate_media_quality("does-not-exist.png")
        self.assertFalse(report["passed"])
        self.assertEqual(report["reasons"][0]["code"], "missing_file")


if __name__ == "__main__":
    unittest.main()
