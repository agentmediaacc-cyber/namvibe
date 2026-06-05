import unittest
from app import create_app

class TestPhase10UIRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

    def test_ui_routes_exist(self):
        # We can't easily test logged-in routes without a real session,
        # but we can check if the routes are registered.
        routes = [rule.rule for rule in self.app.url_map.iter_rules()]
        
        expected_prefixes = [
            '/messages',
            '/calls',
            '/status',
            '/safety',
            '/admin/moderation',
            '/notifications',
            '/wallet',
            '/dating'
        ]
        
        for prefix in expected_prefixes:
            found = any(r.startswith(prefix) for r in routes)
            self.assertTrue(found, f"Route prefix {prefix} not found in app")
            print(f"Checked route: {prefix} - OK")

    def test_safety_routes(self):
        routes = [rule.rule for rule in self.app.url_map.iter_rules()]
        self.assertIn('/safety/', routes)
        self.assertIn('/safety/blocked', routes)
        self.assertIn('/safety/reports', routes)
        self.assertIn('/safety/privacy', routes)
        print("Safety routes - OK")

    def test_admin_moderation_route(self):
        routes = [rule.rule for rule in self.app.url_map.iter_rules()]
        self.assertIn('/admin/moderation', routes)
        print("Admin moderation route - OK")

if __name__ == '__main__':
    unittest.main()
