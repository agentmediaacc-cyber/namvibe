import json
import unittest
from unittest.mock import patch

from services import redis_service


class FakePubSub:
    def __init__(self):
        self.subscribed = []

    def subscribe(self, *channels):
        self.subscribed.extend(channels)


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.sets = {}
        self.ttls = {}
        self.published = []
        self.subscriber = FakePubSub()

    def ping(self):
        return True

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value
        return True

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl
        return True

    def delete(self, key):
        self.store.pop(key, None)
        self.sets.pop(key, None)
        self.ttls.pop(key, None)
        return 1

    def sadd(self, key, member):
        self.sets.setdefault(key, set()).add(member)
        return 1

    def srem(self, key, member):
        self.sets.setdefault(key, set()).discard(member)
        return 1

    def smembers(self, key):
        return self.sets.get(key, set())

    def expire(self, key, ttl):
        self.ttls[key] = ttl
        return True

    def ttl(self, key):
        return self.ttls.get(key, -1)

    def publish(self, channel, payload):
        self.published.append((channel, payload))
        return 1

    def pubsub(self, ignore_subscribe_messages=True):
        return self.subscriber

    def scan_iter(self, pattern):
        prefix = pattern[:-1] if pattern.endswith("*") else pattern
        for key in list(self.store.keys()) + list(self.sets.keys()):
            if key.startswith(prefix):
                yield key

    def info(self):
        return {"redis_version": "7.2", "used_memory_human": "1M", "connected_clients": 2}


class TestRedisCache(unittest.TestCase):
    def setUp(self):
        self.fake = FakeRedis()

    def test_namespace_cache_and_json_helpers(self):
        with patch("services.redis_service.get_redis", return_value=self.fake):
            redis_service.cache_set("feed:test", {"ok": True}, ttl=30)
            cached = redis_service.cache_get("feed:test")
            redis_service.set_json("socket_state:user-1", {"rooms": ["thread_1"]}, ttl=60)
            state = redis_service.get_json("socket_state:user-1")

        self.assertEqual(cached, {"ok": True})
        self.assertEqual(state["rooms"], ["thread_1"])
        namespaced = redis_service.cache_key("feed:test")
        self.assertIn(namespaced, self.fake.store)

    def test_set_helpers_and_ttl(self):
        with patch("services.redis_service.get_redis", return_value=self.fake):
            redis_service.set_add("profile_sids:user-1", "sid-1", ttl=120)
            redis_service.set_add("profile_sids:user-1", "sid-2", ttl=120)
            members = redis_service.set_members("profile_sids:user-1")
            ttl = redis_service.get_ttl("profile_sids:user-1")
            redis_service.set_remove("profile_sids:user-1", "sid-1")
            remaining = redis_service.set_members("profile_sids:user-1")

        self.assertEqual(members, {"sid-1", "sid-2"})
        self.assertEqual(ttl, 120)
        self.assertEqual(remaining, {"sid-2"})

    def test_pubsub_and_invalidation(self):
        with patch("services.redis_service.get_redis", return_value=self.fake), \
             patch("services.redis_service.get_pubsub_client", return_value=self.fake):
            redis_service.cache_set("notifications:user-1", {"count": 1}, ttl=30)
            redis_service.publish("threads:thread-1", {"event": "message:new"})
            subscriber = redis_service.subscribe("threads:thread-1", "notifications:user-1")
            deleted = redis_service.invalidate_namespace("cache")

        self.assertEqual(len(self.fake.published), 1)
        self.assertTrue(subscriber.subscribed)
        self.assertGreaterEqual(deleted, 1)

    def test_redis_missing_does_not_crash_and_health_fallback(self):
        with patch("services.redis_service.get_redis", return_value=None), \
             patch("services.redis_service.get_pubsub_client", return_value=None):
            self.assertIsNone(redis_service.cache_get("missing"))
            self.assertFalse(redis_service.cache_set("missing", {"x": 1}, ttl=10))
            self.assertFalse(redis_service.publish("notifications:user-1", {"x": 1}))
            health = redis_service.get_redis_health()
        self.assertFalse(health["connected"])
        self.assertTrue(health["fallback"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
