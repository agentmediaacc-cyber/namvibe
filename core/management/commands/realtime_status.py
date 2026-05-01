from importlib import import_module

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Verify Namvibe realtime imports and websocket routing without exposing secrets."

    def handle(self, *args, **options):
        checks = []

        try:
            import_module("channels")
            checks.append(("channels", True, "channels import OK"))
        except Exception as exc:
            checks.append(("channels", False, f"channels import failed: {exc.__class__.__name__}"))

        try:
            import_module("config.asgi")
            checks.append(("asgi", True, "config.asgi import OK"))
        except Exception as exc:
            checks.append(("asgi", False, f"config.asgi import failed: {exc.__class__.__name__}"))

        try:
            routing = import_module("config.routing")
            patterns = getattr(routing, "websocket_urlpatterns", [])
            checks.append(("routing", True, f"{len(patterns)} websocket path(s) registered"))
            for pattern in patterns:
                self.stdout.write(f"  - {pattern.pattern}")
        except Exception as exc:
            checks.append(("routing", False, f"config.routing import failed: {exc.__class__.__name__}"))

        backend = settings.CHANNEL_LAYERS.get("default", {}).get("BACKEND", "")
        redis_url = getattr(settings, "REDIS_URL", "")
        using_redis = "RedisChannelLayer" in backend
        if using_redis:
            checks.append(("channel_layer", True, f"Redis-backed channel layer configured via {self._masked_redis_host(redis_url)}"))
        else:
            checks.append(("channel_layer", True, f"Fallback channel layer active: {backend or 'unknown backend'}"))

        for name in ("messaging.consumers", "core.consumers"):
            try:
                import_module(name)
                checks.append((name, True, f"{name} import OK"))
            except Exception as exc:
                checks.append((name, False, f"{name} import failed: {exc.__class__.__name__}"))

        failed = False
        for label, ok, message in checks:
            status = self.style.SUCCESS("OK") if ok else self.style.ERROR("FAIL")
            self.stdout.write(f"[{status}] {label}: {message}")
            if not ok:
                failed = True

        if failed:
            raise SystemExit(1)

    def _masked_redis_host(self, redis_url):
        if not redis_url:
            return "redis://<not-configured>"
        if "://" not in redis_url:
            return "<configured>"
        scheme, _, rest = redis_url.partition("://")
        host = rest.split("@")[-1]
        return f"{scheme}://{host}"
