import json
from flask import g, has_request_context


def _local_cache():
    return {}


def get_request_cache():
    if not has_request_context():
        return _local_cache()
    if "request_cache" not in g:
        g.request_cache = {}
    return g.request_cache


def build_request_key(*parts, **kwargs):
    payload = {"parts": parts, "kwargs": kwargs}
    try:
        return json.dumps(payload, sort_keys=True, default=str)
    except Exception:
        return str(payload)


def request_get(key, default=None):
    return get_request_cache().get(key, default)


def request_set(key, value):
    if not has_request_context():
        return value
    get_request_cache()[key] = value
    return value


def request_cache_get(key, default=None):
    return request_get(key, default)


def request_cache_set(key, value):
    return request_set(key, value)


def request_memoize(key, fn):
    cache = get_request_cache()
    if key in cache:
        return cache[key]
    value = fn()
    if has_request_context():
        cache[key] = value
    return value


def request_cached(key, fn):
    return request_memoize(key, fn)


def clear_request_cache():
    if has_request_context() and "request_cache" in g:
        g.request_cache = {}


def cache_get(key, default=None):
    return request_get(key, default)


def cache_set(key, value):
    return request_set(key, value)


def cache_clear():
    clear_request_cache()


def get_or_set(key, creator_fn):
    return request_memoize(key, creator_fn)
