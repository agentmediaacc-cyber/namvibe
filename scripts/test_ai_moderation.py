import unittest
from services.ai_moderation_engine import moderate_text

class TestAIModeration(unittest.TestCase):
    def test_clean_text(self):
        status, score = moderate_text("Hello this is a nice post")
        self.assertEqual(status, "clean")

    def test_blocked_keyword(self):
        status, score = moderate_text("Join my scam crypto invest")
        self.assertEqual(status, "blocked")

    def test_warning_spam(self):
        status, score = moderate_text("Check this out http://a.com http://b.com http://c.com")
        self.assertEqual(status, "warning")

if __name__ == "__main__":
    unittest.main()
