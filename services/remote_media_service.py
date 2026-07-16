from __future__ import annotations

import ipaddress
import os
import socket
import ssl
import tempfile
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPHandler, HTTPSHandler, Request, build_opener

from utils.supabase_client import SUPABASE_URL, get_supabase_admin

_LOCAL_HOSTNAMES = {"localhost"}
_METADATA_HOSTNAMES = {"metadata", "metadata.google.internal"}
_INFRA_HOST_SUFFIXES = (
    ".neon.tech",
    ".upstash.io",
    ".fly.dev",
    ".render.com",
)
_PRIVATE_NETWORKS = (
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
)


def _ip_category(value: str) -> str:
    try:
        addr = ipaddress.ip_address(value)
    except Exception:
        return "unknown"
    if addr.is_loopback:
        return "loopback"
    if addr.is_link_local:
        return "link_local"
    if addr.is_multicast:
        return "multicast"
    if addr.is_unspecified:
        return "unspecified"
    if any(addr in network for network in _PRIVATE_NETWORKS):
        return "private"
    if addr.is_reserved:
        return "reserved"
    return "public"


def _resolve_host(hostname: str) -> tuple[str | None, list[str]]:
    if not hostname:
        return None, ["dns_resolution_failed"]
    host = hostname.strip().lower().rstrip(".")
    if host in _LOCAL_HOSTNAMES:
        return None, ["localhost_hostname"]
    if host in _METADATA_HOSTNAMES:
        return None, ["metadata_endpoint"]
    try:
        addr = ipaddress.ip_address(host)
        category = _ip_category(str(addr))
        if category != "public":
            return None, [f"{category}_ipv{addr.version}"]
        return "public", []
    except Exception:
        pass
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return None, ["dns_resolution_failed"]
    except Exception:
        return None, ["dns_resolution_failed"]
    categories: list[str] = []
    for item in infos:
        sockaddr = item[4]
        if not sockaddr:
            continue
        ip = sockaddr[0]
        category = _ip_category(ip)
        if category != "public":
            suffix = "ipv6" if ":" in ip else "ipv4"
            reason = {
                "loopback": f"loopback_{suffix}",
                "private": f"private_{suffix}",
                "link_local": f"link_local_{suffix}",
                "multicast": f"multicast_{suffix}",
                "unspecified": f"unspecified_{suffix}",
                "reserved": f"private_{suffix}",
            }.get(category, f"unsafe_{suffix}")
            categories.append(reason)
    if categories:
        return None, categories
    return "public", []


def sanitize_connection_url(value: str | None) -> str:
    if not value:
        return "<not-configured>"
    try:
        parsed = urlparse(str(value))
    except Exception:
        return "<invalid-url>"
    if not parsed.scheme:
        return "<configured>"
    hostname = parsed.hostname or "<unknown-host>"
    if ":" in hostname and not hostname.startswith("["):
        hostname = f"[{hostname}]"
    if parsed.port is not None:
        host = f"{hostname}:{parsed.port}"
    else:
        host = hostname
    return f"{parsed.scheme}://{host}{parsed.path or ''}"


def classify_media_source(media_url: str | None, *, app_root: Path | str | None = None) -> dict[str, Any]:
    root = Path(app_root or Path.cwd()).resolve()
    value = (media_url or "").strip()
    parsed = urlparse(value)
    result: dict[str, Any] = {
        "source_kind": "missing",
        "normalized_url": "",
        "local_path": None,
        "exists": False,
        "scheme": parsed.scheme or "",
        "hostname": parsed.hostname or "",
        "provider": "generic",
        "reason": "missing_source",
        "safe": True,
    }
    if not value:
        return result

    def _set_local(public_path: Path, *, reason: str = "local_media_candidate") -> dict[str, Any]:
        try:
            resolved = public_path.resolve()
        except Exception:
            resolved = public_path
        if not str(resolved).startswith(str(root)):
            return {
                **result,
                "source_kind": "missing",
                "normalized_url": "",
                "local_path": None,
                "exists": False,
                "scheme": "",
                "hostname": "",
                "provider": "local",
                "reason": "path_traversal_rejected",
                "safe": False,
            }
        try:
            rel = resolved.relative_to(root)
        except Exception:
            rel = None
        public_url = ""
        if rel is not None:
            public_url = "/" + rel.as_posix().lstrip("/")
        exists = resolved.exists()
        return {
            **result,
            "source_kind": "local",
            "normalized_url": public_url,
            "local_path": resolved,
            "exists": exists,
            "scheme": "",
            "hostname": "",
            "provider": "local",
            "reason": "missing_local_source" if not exists else reason,
            "safe": True,
        }

    if value.startswith("file://"):
        return {**result, "source_kind": "missing", "reason": "unsupported_scheme", "safe": False}

    if value.startswith("/static/"):
        local = _set_local((root / value.lstrip("/")).resolve())
        if local.get("reason") == "missing_local_source":
            local["reason"] = "missing_local_thumbnail" if "/thumbnails/" in (local.get("normalized_url") or value) else "missing_local_source"
        return local

    if value.startswith("static/"):
        local = _set_local((root / value).resolve())
        if local.get("reason") == "missing_local_source":
            local["reason"] = "missing_local_thumbnail" if "/thumbnails/" in (local.get("normalized_url") or value) else "missing_local_source"
        return local

    if parsed.scheme in {"http", "https"}:
        hostname = (parsed.hostname or "").lower()
        provider = "generic"
        if SUPABASE_URL:
            supabase_host = urlparse(SUPABASE_URL).hostname or ""
            if hostname and hostname == supabase_host.lower():
                provider = "supabase"
        if any(hostname.endswith(suffix) for suffix in _INFRA_HOST_SUFFIXES):
            return {
                **result,
                "source_kind": "remote",
                "normalized_url": value,
                "local_path": None,
                "exists": False,
                "scheme": parsed.scheme,
                "hostname": parsed.hostname or "",
                "provider": provider,
                "reason": "invalid_media_origin",
                "safe": False,
            }
        return {
            **result,
            "source_kind": "remote",
            "normalized_url": value,
            "local_path": None,
            "exists": False,
            "scheme": parsed.scheme,
            "hostname": parsed.hostname or "",
            "provider": provider,
            "reason": "remote_candidate",
            "safe": True,
        }

    if parsed.scheme:
        return {**result, "source_kind": "missing", "reason": "unsupported_scheme", "safe": False}

    if value.startswith("/"):
        return _set_local((root / value.lstrip("/")).resolve())

    if Path(value).is_absolute():
        path = Path(value).resolve()
        allowed_roots = [
            (root / "static" / "uploads").resolve(),
            (root / "static").resolve(),
        ]
        if any(str(path).startswith(str(allowed)) for allowed in allowed_roots):
            return _set_local(path)
        return {**result, "source_kind": "missing", "reason": "path_traversal_rejected", "safe": False}

    if value.startswith("static/"):
        return _set_local((root / value).resolve())

    return {**result, "source_kind": "missing", "reason": "unsupported_scheme", "safe": False}


def _build_ssl_context() -> tuple[ssl.SSLContext, str]:
    cafile = os.getenv("SSL_CERT_FILE") or os.getenv("REQUESTS_CA_BUNDLE")
    if cafile:
        return ssl.create_default_context(cafile=cafile), "environment"
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where()), "certifi"
    except Exception:
        return ssl.create_default_context(), "system"


def build_verified_ssl_context() -> tuple[ssl.SSLContext, str]:
    context, source = _build_ssl_context()
    return context, source


def inspect_remote_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url or "")
    hostname = parsed.hostname or ""
    resolved_category, reasons = _resolve_host(hostname)
    provider = "generic"
    supabase_host = urlparse(SUPABASE_URL).hostname if SUPABASE_URL else None
    path = parsed.path or ""
    if supabase_host and hostname and hostname.lower() == supabase_host.lower():
        provider = "supabase"
    elif path.startswith("/storage/v1/object/public/") or path.startswith("/storage/v1/object/sign/"):
        provider = "supabase"
    elif "cloudflare" in hostname.lower():
        provider = "cloudflare"
    return {
        "scheme": parsed.scheme or "",
        "hostname": hostname,
        "port": parsed.port,
        "path_suffix": path[-60:],
        "has_query": bool(parsed.query),
        "provider": provider,
        "resolved_ip_category": resolved_category or ("unsafe" if reasons else "unknown"),
        "rejection_reasons": reasons,
    }


def validate_remote_url(url: str) -> dict[str, Any]:
    parsed = urlparse(url or "")
    if parsed.scheme not in {"http", "https"}:
        return {"ok": False, "reason": "unsafe_scheme", "details": inspect_remote_url(url)}
    details = inspect_remote_url(url)
    reasons = list(details.get("rejection_reasons") or [])
    if reasons:
        return {"ok": False, "reason": reasons[0], "details": details}
    return {"ok": True, "reason": None, "details": details}


def _build_opener(context: ssl.SSLContext):
    return build_opener(HTTPHandler(), HTTPSHandler(context=context))


def _http_reason_from_status(status: int) -> str:
    if status == 401:
        return "inaccessible_http_401"
    if status == 403:
        return "inaccessible_http_403"
    if status == 404:
        return "inaccessible_http_404"
    if 500 <= status <= 599:
        return "inaccessible_http_5xx"
    return f"inaccessible_http_{status}"


def _classify_exception(exc: BaseException) -> str:
    if isinstance(exc, ssl.SSLCertVerificationError):
        return "inaccessible_tls"
    if isinstance(exc, TimeoutError):
        return "inaccessible_timeout"
    if isinstance(exc, socket.timeout):
        return "inaccessible_timeout"
    if isinstance(exc, HTTPError):
        return _http_reason_from_status(getattr(exc, "code", 0) or 0)
    if isinstance(exc, URLError):
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            return "inaccessible_tls"
        if isinstance(reason, TimeoutError):
            return "inaccessible_timeout"
        if isinstance(reason, socket.timeout):
            return "inaccessible_timeout"
        if isinstance(reason, socket.gaierror):
            return "inaccessible_dns"
        if isinstance(reason, OSError) and "CERTIFICATE_VERIFY_FAILED" in str(reason):
            return "inaccessible_tls"
        if isinstance(reason, OSError) and "timed out" in str(reason).lower():
            return "inaccessible_timeout"
        return "inaccessible_remote"
    return "inaccessible_remote"


def fetch_remote_headers(url: str, *, timeout_seconds: int = 10, max_redirects: int = 3) -> dict[str, Any]:
    validation = validate_remote_url(url)
    if not validation["ok"]:
        return {"ok": False, "reason": validation["reason"], "details": validation["details"]}
    current = url
    context, tls_source = build_verified_ssl_context()
    opener = _build_opener(context)
    for _ in range(max_redirects + 1):
        req = Request(current, method="HEAD", headers={"User-Agent": "NamVibe-Reel-Audit/1.0"})
        try:
            with opener.open(req, timeout=timeout_seconds) as resp:
                headers = {k.lower(): v for k, v in resp.headers.items()}
                return {"ok": True, "headers": headers, "tls_ca_source": tls_source, "tls_verified": True, "details": inspect_remote_url(current)}
        except HTTPError as exc:
            if 300 <= exc.code < 400 and exc.headers.get("Location"):
                next_url = urljoin(current, exc.headers.get("Location"))
                next_validation = validate_remote_url(next_url)
                if not next_validation["ok"]:
                    return {"ok": False, "reason": "redirect_to_unsafe_host", "details": next_validation["details"], "tls_ca_source": tls_source, "tls_verified": True}
                current = next_url
                continue
            return {"ok": False, "reason": _http_reason_from_status(exc.code), "details": inspect_remote_url(current), "tls_ca_source": tls_source, "tls_verified": True}
        except Exception as exc:
            return {"ok": False, "reason": _classify_exception(exc), "details": inspect_remote_url(current), "tls_ca_source": tls_source, "tls_verified": True}
    return {"ok": False, "reason": "redirect_to_unsafe_host", "details": inspect_remote_url(current), "tls_ca_source": tls_source, "tls_verified": True}


def _storage_object_from_url(url: str) -> tuple[str | None, str | None]:
    parsed = urlparse(url)
    path = parsed.path or ""
    marker = "/storage/v1/object/"
    idx = path.find(marker)
    if idx < 0:
        return None, None
    remainder = path[idx + len(marker) :]
    parts = remainder.split("/", 2)
    if len(parts) < 3:
        return None, None
    _visibility, bucket, object_path = parts[0], parts[1], parts[2]
    return bucket, object_path


def parse_supabase_storage_url(url: str) -> dict[str, Any]:
    bucket, object_path = _storage_object_from_url(url)
    parsed = urlparse(url or "")
    return {
        "provider": "supabase" if bucket and object_path else "generic",
        "bucket": bucket,
        "object_path": object_path,
        "hostname": parsed.hostname or "",
        "path": parsed.path or "",
        "is_supabase_storage": bool(bucket and object_path),
    }


def _download_supabase_storage(url: str) -> tuple[Path | None, dict[str, Any]]:
    bucket, object_path = _storage_object_from_url(url)
    if not bucket or not object_path:
        return None, {"ok": False, "reason": "missing_source"}
    try:
        storage = get_supabase_admin().storage
        downloader = storage.from_(bucket)
        payload = downloader.download(object_path)
        if payload is None:
            return None, {"ok": False, "reason": "missing_source"}
        if hasattr(payload, "read"):
            data = payload.read()
        else:
            data = payload
        if isinstance(data, str):
            data = data.encode("utf-8")
        lower = bytes(data[:4096]).lower()
        if b"<svg" in lower or b"<?xml" in lower or b"<!doctype html" in lower or b"<html" in lower:
            return None, {"ok": False, "reason": "svg_not_video", "provider": "supabase", "bucket": bucket, "object_path": object_path}
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(object_path).suffix or ".bin")
        try:
            tmp.write(data)
            tmp.flush()
        finally:
            tmp.close()
        return Path(tmp.name), {"ok": True, "provider": "supabase", "bucket": bucket, "object_path": object_path}
    except Exception as exc:
        return None, {"ok": False, "reason": _classify_exception(exc), "provider": "supabase", "bucket": bucket, "object_path": object_path}


def download_remote_media_to_tempfile(
    url: str,
    *,
    timeout_seconds: int = 10,
    max_download_mb: int = 100,
    max_redirects: int = 3,
) -> tuple[Path | None, dict[str, Any]]:
    validation = validate_remote_url(url)
    if not validation["ok"]:
        return None, {"ok": False, "reason": validation["reason"], "details": validation["details"]}
    provider = validation["details"].get("provider")
    if provider == "supabase":
        tmp, meta = _download_supabase_storage(url)
        if tmp:
            meta.update({"ok": True, "tls_ca_source": "supabase_client", "tls_verified": True})
            return tmp, meta
        if meta.get("reason") not in {"missing_source"}:
            return None, meta
    context, tls_source = build_verified_ssl_context()
    opener = _build_opener(context)
    current = url
    limit = max_download_mb * 1024 * 1024
    for _ in range(max_redirects + 1):
        req = Request(current, headers={"User-Agent": "NamVibe-Reel-Backfill/1.0", "Range": f"bytes=0-{min(limit, 1024 * 1024) - 1}"})
        try:
            with opener.open(req, timeout=timeout_seconds) as resp:
                ctype = (resp.headers.get("Content-Type") or "").split(";", 1)[0].lower()
                if not (ctype.startswith("video/") or ctype == "application/octet-stream"):
                    return None, {"ok": False, "reason": "invalid_media_type", "content_type": ctype, "tls_ca_source": tls_source, "tls_verified": True, "details": inspect_remote_url(current)}
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=Path(urlparse(current).path or "").suffix or ".mp4")
                total = 0
                sniff = bytearray()
                try:
                    while True:
                        chunk = resp.read(min(1024 * 1024, limit - total))
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > limit:
                            return None, {"ok": False, "reason": "download_too_large", "tls_ca_source": tls_source, "tls_verified": True, "details": inspect_remote_url(current)}
                        tmp.write(chunk)
                        if len(sniff) < 4096:
                            sniff.extend(chunk[: 4096 - len(sniff)])
                    tmp.flush()
                finally:
                    tmp.close()
                lower = bytes(sniff).lower()
                if b"<svg" in lower or b"<?xml" in lower or b"<!doctype html" in lower or b"<html" in lower:
                    try:
                        Path(tmp.name).unlink(missing_ok=True)
                    except Exception:
                        pass
                    return None, {"ok": False, "reason": "svg_not_video", "tls_ca_source": tls_source, "tls_verified": True, "details": inspect_remote_url(current)}
                return Path(tmp.name), {"ok": True, "tls_ca_source": tls_source, "tls_verified": True, "details": inspect_remote_url(current), "content_type": ctype, "download_bytes": total}
        except HTTPError as exc:
            if 300 <= exc.code < 400 and exc.headers.get("Location"):
                next_url = urljoin(current, exc.headers.get("Location"))
                next_validation = validate_remote_url(next_url)
                if not next_validation["ok"]:
                    return None, {"ok": False, "reason": "redirect_to_unsafe_host", "tls_ca_source": tls_source, "tls_verified": True, "details": next_validation["details"]}
                current = next_url
                continue
            return None, {"ok": False, "reason": _http_reason_from_status(exc.code), "tls_ca_source": tls_source, "tls_verified": True, "details": inspect_remote_url(current)}
        except Exception as exc:
            return None, {"ok": False, "reason": _classify_exception(exc), "tls_ca_source": tls_source, "tls_verified": True, "details": inspect_remote_url(current)}
    return None, {"ok": False, "reason": "redirect_to_unsafe_host", "tls_ca_source": tls_source, "tls_verified": True, "details": inspect_remote_url(current)}
