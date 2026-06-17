import logging
import os
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv as _load_dotenv
except ModuleNotFoundError:
    _load_dotenv = None

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"

_LOADED = False
_LOADED_RESULT = False
_SECRET_MARKERS = ("key", "secret", "token", "password", "database_url", "redis_url")


def _is_secret_name(name: str) -> bool:
    lowered = name.lower()
    return any(marker in lowered for marker in _SECRET_MARKERS)


def mask_env_value(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    if value == "":
        return ""
    if not _is_secret_name(name):
        return value
    if len(value) <= 8:
        return "[masked]"
    return f"{value[:4]}...{value[-4:]}"


def load_project_env() -> bool:
    """
    Load .env from the project root without overriding production-provided env vars.
    Returns True when a project .env file was found and parsed.
    """
    global _LOADED, _LOADED_RESULT
    if _LOADED:
        return _LOADED_RESULT

    if _load_dotenv is not None:
        _LOADED_RESULT = _load_dotenv(dotenv_path=ENV_PATH, override=False)
    else:
        _LOADED_RESULT = _load_env_file_fallback(ENV_PATH)
    _LOADED = True
    logger.info("project_env_loaded", extra={"env_path": str(ENV_PATH), "loaded": _LOADED_RESULT})
    return _LOADED_RESULT


def _load_env_file_fallback(path: Path) -> bool:
    if not path.exists():
        return False
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
    return True


def get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    load_project_env()
    value = os.getenv(name)
    if value is None and name == "SUPABASE_KEY":
        value = os.getenv("SUPABASE_ANON_KEY")
    if value is None:
        value = default
    logger.debug("env_read", extra={"name": name, "value": mask_env_value(name, value)})
    return value


def require_env(name: str) -> str:
    value = get_env(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def env_status() -> dict:
    load_project_env()
    names = [
        "DATABASE_URL",
        "REDIS_URL",
        "SUPABASE_URL",
        "SUPABASE_ANON_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_KEY",
    ]
    return {
        "env_path": str(ENV_PATH),
        "env_file_exists": ENV_PATH.exists(),
        "env_file_loaded": _LOADED_RESULT,
        "values": {
            name: {
                "present": bool(get_env(name)),
                "value": mask_env_value(name, get_env(name)),
            }
            for name in names
        },
    }


class EnvService:
    """Backward-compatible wrapper around the module-level env helpers."""

    load_project_env = staticmethod(load_project_env)
    get_env = staticmethod(get_env)
    require_env = staticmethod(require_env)
    env_status = staticmethod(env_status)
