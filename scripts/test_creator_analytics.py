import unittest
from services.creator_analytics_engine import get_creator_stats

class TestCreatorAnalytics(unittest.TestCase):
    def test_stats_mock(self):
        stats = get_creator_stats('00000000-0000-0000-0000-000000000001')
        self.assertIn('total_reel_views', stats)
        self.assertIn('engagement_rate', stats)

if __name__ == "__main__":
    unittest.main()
