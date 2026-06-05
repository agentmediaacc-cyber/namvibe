import unittest
from unittest.mock import patch

from services import job_engine
import scripts.chain_worker as chain_worker


class TestWorkerOrchestration(unittest.TestCase):
    def test_worker_imports_and_once_exits(self):
        with patch("scripts.chain_worker.claim_next_job", return_value=None):
            code = chain_worker.run_worker(once=True, queues=["default"])
        self.assertEqual(code, 0)

    def test_job_claim_complete_fail_safe(self):
        fake_job = {"id": "job-1", "job_type": "cleanup_typing_state", "payload": {}}
        with patch("scripts.chain_worker.claim_next_job", return_value=fake_job), \
             patch("scripts.chain_worker.complete_job") as mock_complete:
            code = chain_worker.run_worker(once=True, queues=["maintenance"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_complete.called)

        fake_bad_job = {"id": "job-2", "job_type": "unknown", "payload": {}}
        with patch("scripts.chain_worker.claim_next_job", return_value=fake_bad_job), \
             patch("scripts.chain_worker.fail_job") as mock_fail:
            code = chain_worker.run_worker(once=True, queues=["maintenance"])
        self.assertEqual(code, 0)
        self.assertTrue(mock_fail.called)

    def test_run_due_jobs_shape(self):
        with patch("services.job_engine.fast_query", return_value=[{"id": "job-1", "status": "queued"}]):
            rows = job_engine.run_due_jobs(limit=1)
        self.assertEqual(rows[0]["id"], "job-1")


if __name__ == "__main__":
    unittest.main(verbosity=2)
