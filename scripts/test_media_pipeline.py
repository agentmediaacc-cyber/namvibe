import unittest
import io
from services.media_pipeline import validate_upload

class TestMediaPipeline(unittest.TestCase):
    def test_validate_upload_size(self):
        # Mock file object
        f = io.BytesIO(b"0" * (2 * 1024 * 1024)) # 2MB
        f.content_type = "image/jpeg"
        ok, error = validate_upload(f, ["image/jpeg"], 1) # 1MB limit
        self.assertFalse(ok)
        self.assertIn("File too large", error)

    def test_validate_upload_type(self):
        f = io.BytesIO(b"Fake content")
        f.content_type = "application/exe"
        ok, error = validate_upload(f, ["image/jpeg", "video/mp4"], 10)
        self.assertFalse(ok)
        self.assertIn("Unsupported", error)

if __name__ == "__main__":
    unittest.main()
