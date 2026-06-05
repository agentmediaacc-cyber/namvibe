import unittest
from app import create_app
from services.feed_engine import build_feed
from services.trust_score_engine import calculate_profile_trust_score
from services.search_service import smart_search
from services.analytics_v2_service import get_admin_analytics

class TestPhase11Scale(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        self.ctx.pop()

    def test_feed_ranking_logic(self):
        # Test building different feeds
        for_you = build_feed(feed_type="explore", limit=10)
        trending = build_feed(feed_type="trending", limit=10)
        
        self.assertIsInstance(for_you, list)
        self.assertIsInstance(trending, list)
        print(f"Feed build test: For You ({len(for_you)}), Trending ({len(trending)}) - OK")

    def test_trust_score_calculation(self):
        # Test with a dummy profile ID (needs a real one from DB for full test, but we check if it runs)
        from services.neon_service import fast_query
        p = fast_query("SELECT id FROM chain_profiles LIMIT 1")
        if p:
            score = calculate_profile_trust_score(p[0]['id'])
            self.assertGreaterEqual(score, 0.0)
            self.assertLessEqual(score, 10.0)
            print(f"Trust score calculation for {p[0]['id']}: {score} - OK")
        else:
            print("Skipping trust score test: No profiles in DB")

    def test_search_v2(self):
        results = smart_search("test")
        self.assertIn('recent', results)
        self.assertIn('trending', results)
        self.assertIn('suggested', results)
        print("Search V2 response structure - OK")

    def test_analytics_admin(self):
        metrics = get_admin_analytics()
        self.assertIn('total_users', metrics)
        self.assertIn('dau', metrics)
        print("Admin analytics metrics - OK")

if __name__ == '__main__':
    unittest.main()
