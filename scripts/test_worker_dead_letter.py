import unittest
from unittest.mock import patch

from services import job_engine


class TestWorkerDeadLetter(unittest.TestCase):
    def test_fail_job_dead_letters_at_max_attempts(self):
        with patch("services.job_engine.fast_query", return_value=[{"attempts": 3, "max_attempts": 3, "error_history": []}]), \
             patch("services.job_engine.write_query") as mock_write:
            job_engine.fail_job("job-1", "boom")
        sql = mock_write.call_args[0][0]
        self.assertIn("dead_letter", sql)

    def test_fail_job_retries_with_backoff(self):
        with patch("services.job_engine.fast_query", return_value=[{"attempts": 1, "max_attempts": 3, "error_history": []}]), \
             patch("services.job_engine.write_query") as mock_write:
            job_engine.fail_job("job-2", "boom")
        sql = mock_write.call_args[0][0]
        self.assertIn("run_after", sql)


if __name__ == "__main__":
    unittest.main(verbosity=2)
