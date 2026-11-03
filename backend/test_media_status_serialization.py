import unittest

from bson import ObjectId

from media_queue import serialize_media_job_document


class MediaStatusSerializationTests(unittest.TestCase):
    def test_partial_video_failure_keeps_image_and_legacy_result(self):
        image_id = ObjectId()
        job = {"_id": ObjectId(), "status": "partial", "include_video": True,
               "image_file_id": image_id, "error": "video unavailable"}
        result = serialize_media_job_document(job)
        self.assertEqual(result["image"]["status"], "completed")
        self.assertEqual(result["video"]["status"], "failed")
        self.assertEqual(result["video"]["error_code"], "video unavailable")
        self.assertEqual(result["result"]["image_file_id"], str(image_id))
        self.assertEqual(result["status"], "partial")

    def test_running_image_only_marks_video_not_requested(self):
        result = serialize_media_job_document(
            {"_id": ObjectId(), "status": "running", "request": {"include_video": False}}
        )
        self.assertEqual(result["image"]["status"], "running")
        self.assertEqual(result["video"]["status"], "not_requested")

    def test_completed_without_requested_video_is_not_pending(self):
        result = serialize_media_job_document(
            {"_id": ObjectId(), "status": "completed", "include_video": True,
             "image_url": "/example.png"}
        )
        self.assertEqual(result["image"]["status"], "completed")
        self.assertEqual(result["video"]["status"], "failed")


if __name__ == "__main__":
    unittest.main()
