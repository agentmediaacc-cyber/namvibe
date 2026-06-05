import io
import unittest
from unittest.mock import patch

from flask import Flask

from api_routes.auth_routes import auth_bp
from api_routes.reels_routes import reels_bp
from services.media_pipeline import process_reel_metadata_job, validate_upload


class TestReelsProcessing(unittest.TestCase):
    def test_upload_requires_auth(self):
        app = Flask(__name__)
        app.secret_key = "test"
        app.register_blueprint(reels_bp)
        app.register_blueprint(auth_bp)
        with app.test_client() as client:
            response = client.get("/reels/upload")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/auth/login", response.location)

    def test_validation_rejects_bad_mime(self):
        file_obj = io.BytesIO(b"not-video")
        file_obj.content_type = "text/plain"
        valid, error = validate_upload(file_obj, allowed_types={"video/mp4"}, max_mb=5)
        self.assertFalse(valid)
        self.assertIn("Unsupported file type", error)

    def test_process_job_handles_missing_ffmpeg(self):
        with patch("services.media_pipeline.write_query") as mock_write:
            result = process_reel_metadata_job("reel-1")
        self.assertIn("extractor", result)
        self.assertTrue(mock_write.called)


if __name__ == "__main__":
    unittest.main(verbosity=2)
