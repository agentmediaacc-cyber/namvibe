import io
import unittest
from unittest.mock import patch

from services.media_pipeline import process_reel_job, queue_reel_processing, validate_upload


class TestReelsTranscodingQueue(unittest.TestCase):
    def test_invalid_mime_rejected(self):
        file_obj = io.BytesIO(b"abc")
        file_obj.content_type = "text/plain"
        valid, error = validate_upload(file_obj, {"video/mp4"}, 5)
        self.assertFalse(valid)
        self.assertIn("Unsupported", error)

    def test_queue_and_missing_ffmpeg_safe(self):
        with patch("services.media_pipeline.enqueue_job") as mock_enqueue, \
             patch("services.media_pipeline.write_query"):
            queue_reel_processing("reel-1")
            self.assertTrue(mock_enqueue.called)
        with patch("services.media_pipeline.ffmpeg_available", return_value=False), \
             patch("services.media_pipeline.write_query") as mock_write:
            result = process_reel_job("reel-1")
        self.assertEqual(result["processing_error"], "ffmpeg_unavailable")
        self.assertTrue(mock_write.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
