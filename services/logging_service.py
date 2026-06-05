import json
import os
import time
from flask import g, has_request_context, request


_SECRET_MARKERS = ("key", "token", "secret", "password", "authorization", "cookie", "dsn")


def mask_secrets(value):
    if isinstance(value, dict):
        return {
            key: ("[masked]" if any(marker in str(key).lower() for marker in _SECRET_MARKERS) else mask_secrets(val))
            for key, val in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [mask_secrets(item) for item in value]
    text = str(value)
    if "://" in text and "@" in text:
        return "[masked-url]"
    if len(text) > 240:
        return text[:240]
    return value


def _log(level, event, **fields):
    payload = {
        "ts": round(time.time(), 3),
        "level": level,
        "event": event,
    }
    if has_request_context():
        payload.update({
            "request_id": getattr(g, "request_id", None),
            "route": request.path,
            "method": request.method,
        })
        if g.get("current_profile_id"):
            payload["profile_id"] = g.current_profile_id
    payload.update(mask_secrets(fields))
    print(json.dumps(payload, default=str, sort_keys=True))


def log_info(event, **fields):
    _log("info", event, **fields)


def log_warning(event, **fields):
    _log("warning", event, **fields)


def log_error(event, error=None, **fields):
    if error is not None:
        fields["error"] = mask_secrets(error)
    _log("error", event, **fields)


def log_metric(name, value, **tags):
    _log("metric", "metric", metric=name, value=value, tags=tags)


def log_security(event, **fields):
    _log("security", event, **fields)


def log_wallet_event(event, **fields):
    _log("wallet", event, **fields)


def log_socket_event(event, **fields):
    _log("socket", event, **fields)
