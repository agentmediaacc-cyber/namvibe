from __future__ import annotations

import re
from urllib.parse import urlsplit, urlunsplit


_CRED_URL_RE = re.compile(
    r"(?P<scheme>postgres(?:ql)?|redis(?:s)?)://"
    r"(?P<user>[^:/@\s]+)"
    r":(?P<pw>[^@\s]+)@"
    r"(?P<host>\[[^\]]+\]|[^/\s:@?]+)"
    r"(?::(?P<port>\d+))?"
    r"(?P<path>/[^\s?#]*)?"
    r"(?P<query>\?[^\s#]*)?"
    r"(?P<frag>#[^\s]*)?",
    re.IGNORECASE,
)


def sanitize_connection_url(value: str | None) -> str:
    """Return a safe connection URL for logs without credentials."""
    if not value:
        return "<not-configured>"

    text = str(value).strip()
    if not text:
        return "<not-configured>"

    try:
        parsed = urlsplit(text)
    except (TypeError, ValueError):
        return "<invalid-url>"

    if not parsed.scheme:
        return "<configured>"

    hostname = parsed.hostname or "<unknown-host>"
    try:
        port = parsed.port
    except ValueError:
        port = None

    host = hostname
    if ":" in hostname and not hostname.startswith("["):
        host = f"[{hostname}]"
    if port is not None:
        host = f"{host}:{port}"

    return urlunsplit((parsed.scheme, host, parsed.path or "", "", ""))


def redact_connection_urls(text: str | None) -> str:
    if not text:
        return "" if text == "" else "<not-configured>"

    def _replace(match):
        scheme = match.group("scheme")
        host = match.group("host")
        port = match.group("port")
        path = match.group("path") or ""
        safe_host = host
        if port:
            safe_host = f"{safe_host}:{port}"
        return urlunsplit((scheme, safe_host, path, "", ""))

    try:
        return _CRED_URL_RE.sub(_replace, str(text))
    except Exception:
        return str(text)


def safe_exception_summary(exc: BaseException) -> str:
    return f"{type(exc).__name__}: connection operation failed"


def safe_connection_error(exc: BaseException, *, endpoint: str | None = None) -> str:
    safe_endpoint = sanitize_connection_url(endpoint)
    return f"{type(exc).__name__}: connection failed for {safe_endpoint}"
