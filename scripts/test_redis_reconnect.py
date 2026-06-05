import unittest
from unittest.mock import patch

from services.redis_service import RedisManager, cache_key, metrics_key, redis_manager


class FailingRedis:
    def ping(self):
        raise RuntimeError("redis_down")


class WorkingRedis:
    def __init__(self):
        self.store = {}

    def ping(self):
        return True

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value
        return True


class TestRedisReconnect(unittest.TestCase):
    def test_fallback_mode_and_health(self):
        manager = RedisManager()
        manager.url = "redis://example"
        with patch("services.redis_service.redis.from_url", return_value=FailingRedis()):
            self.assertIsNone(manager.get_client())
            self.assertTrue(manager.set_json("cache:test", {"ok": True}, ttl=5))
            self.assertEqual(manager.get_json("cache:test"), {"ok": True})
            health = manager.get_health()
        self.assertTrue(health["fallback"])
        self.assertEqual(cache_key("x"), "chain:cache:x")
        self.assertEqual(metrics_key("x"), "chain:metrics:x")

    def test_reconnect_recovery(self):
        manager = RedisManager()
        manager.url = "redis://example"
        with patch("services.redis_service.redis.from_url", side_effect=[FailingRedis(), WorkingRedis()]):
            self.assertIsNone(manager.get_client())
            manager.breaker.opened_at = 0
            manager.breaker.state = "half_open"
            self.assertIsNotNone(manager.get_client())
            self.assertTrue(manager.is_available())


if __name__ == "__main__":
    unittest.main(verbosity=2)
