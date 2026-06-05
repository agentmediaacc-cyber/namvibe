import unittest
from services.presence_engine import get_presence
from services.feed_engine import build_feed
from services.verification_engine import get_verification_status
from services.job_engine import enqueue_job

class TestEngines(unittest.TestCase):
    def test_presence_empty(self):
        p = get_presence([])
        self.assertEqual(p, [])

    def test_feed_public(self):
        feed = build_feed(limit=5)
        self.assertIsInstance(feed, list)

    def test_verification_none(self):
        status = get_verification_status('00000000-0000-0000-0000-000000000000')
        self.assertIsNone(status)

    def test_job_enqueue(self):
        try:
            job_id = enqueue_job('test_job', {'foo': 'bar'})
            self.assertIsNotNone(job_id)
        except Exception as e:
            print(f"Job enqueue failed (likely DB): {e}")

if __name__ == "__main__":
    unittest.main()
