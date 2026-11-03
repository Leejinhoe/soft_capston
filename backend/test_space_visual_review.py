import unittest

from space_visual_review import count_distinct_detections


class SpaceVisualReviewTests(unittest.TestCase):
    def test_suppresses_a_large_box_covering_a_smaller_detection(self):
        detections = [
            {"score": 0.8, "box": [10, 10, 80, 30]},
            {"score": 0.6, "box": [0, 0, 100, 40]},
        ]
        self.assertEqual(len(count_distinct_detections(detections)), 1)

    def test_preserves_two_separate_objects(self):
        detections = [
            {"score": 0.526, "box": [89, 39, 235, 122]},
            {"score": 0.575, "box": [258, 64, 441, 128]},
            {"score": 0.33, "box": [90, 41, 441, 131]},
        ]
        self.assertEqual(len(count_distinct_detections(detections)), 2)

    def test_invalid_numbers_cannot_be_counted_as_success(self):
        with self.assertRaises(ValueError):
            count_distinct_detections([{"score": float("nan"), "box": [0, 0, 4, 5]}])

    def test_low_scores_are_not_accepted(self):
        self.assertEqual(count_distinct_detections([{"score": 0.2, "box": [0, 0, 4, 5]}]), [])


if __name__ == "__main__":
    unittest.main()
