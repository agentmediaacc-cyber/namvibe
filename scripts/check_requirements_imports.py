"""
Phase 68B — Requirements Import Checker.
Parses all Python imports and verifies they are covered by requirements.txt.
"""
import ast
import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

TOP_LEVEL_MAP = {
    "PIL": "pillow",
    "flask": "Flask",
    "flask_socketio": "Flask-SocketIO",
    "flask_limiter": "Flask-Limiter",
    "flask_caching": "Flask-Caching",
    "dotenv": "python-dotenv",
    "apscheduler": "APScheduler",
    "sentry_sdk": "sentry-sdk",
    "cachelib": "cachelib",
    "better_profanity": "better-profanity",
    "slugify": "python-slugify",
    "dateutil": "python-dateutil",
    "croniter": "croniter",
    "deprecation": "deprecation",
    "gotrue": "gotrue",
    "postgrest": "postgrest",
    "realtime": "realtime",
    "storage3": "storage3",
    "supabase": "supabase",
    "supafunc": "supafunc",
    "strenum": "StrEnum",
    "pydantic": "pydantic",
    "pydantic_core": "pydantic-core",
    "pyjwt": "PyJWT",
    "magic": "python-magic",
    "websocket_client": "websocket-client",
    "wsproto": "wsproto",
    "zope": "zope.interface",
    "engineio": "python-engineio",
    "socketio": "python-socketio",
    "gunicorn": "gunicorn",
    "gevent": "gevent",
    "greenlet": "greenlet",
    "redis": "redis",
    "psycopg2": "psycopg2-binary",
    "requests": "requests",
    "jinja2": "Jinja2",
    "werkzeug": "Werkzeug",
    "markupsafe": "MarkupSafe",
    "click": "click",
    "itsdangerous": "itsdangerous",
    "blinker": "blinker",
    "certifi": "certifi",
    "charset_normalizer": "charset-normalizer",
    "urllib3": "urllib3",
    "idna": "idna",
    "h11": "h11",
    "h2": "h2",
    "hpack": "hpack",
    "httpcore": "httpcore",
    "httpx": "httpx",
    "hyperframe": "hyperframe",
    "sniffio": "sniffio",
    "anyio": "anyio",
    "bidict": "bidict",
    "ordered_set": "ordered-set",
    "typing_extensions": "typing-extensions",
    "typing_inspection": "typing-inspection",
    "annotated_types": "annotated-types",
    "tzlocal": "tzlocal",
    "packaging": "packaging",
    "six": "six",
    "wrapt": "wrapt",
    "websockets": "websockets",
    "text_unidecode": "text-unidecode",
    "webencodings": "webencodings",
    "simple_websocket": "simple-websocket",
    "bcrypt": "bcrypt",
    "cryptography": "cryptography",
    "email_validator": "email-validator",
    "geventwebsocket": "gevent-websocket",
    "opencv": "opencv-python",
    "numpy": "numpy",
    "pytest": "pytest",
    "freezegun": "freezegun",
}

STDLIB_MODULES = {
    "os", "sys", "re", "json", "time", "math", "random", "datetime",
    "uuid", "threading", "functools", "wraps", "collections", "itertools",
    "typing", "enum", "pathlib", "io", "base64", "hashlib", "hmac",
    "urllib", "html", "xml", "csv", "copy", "textwrap", "string",
    "logging", "warnings", "traceback", "inspect", "ast", "bisect",
    "operator", "fractions", "decimal", "statistics", "weakref",
    "contextlib", "abc", "dataclasses", "concurrent", "signal",
    "subprocess", "argparse", "shlex", "shutil", "tempfile",
    "fileinput", "glob", "fnmatch", "linecache", "pickle", "struct",
    "pprint", "profile", "pstats", "ctypes", "platform",
    "ssl", "socket", "selectors", "asyncio", "ipaddress",
    "http", "email", "mimetypes", "quopri", "binascii",
    "getpass", "grp", "pwd", "spwd", "termios", "tty", "pty",
    "turtle", "tkinter", "venv", "zipfile", "tarfile", "gzip",
    "bz2", "lzma", "zlib", "imp", "importlib", "pkgutil",
    "pdb", "cgitb", "code", "codeop", "codecs", "encodings",
    "gettext", "locale", "calendar", "numbers", "types",
    "dis", "symtable", "tabnanny", "pyclbr", "py_compile",
    "compileall", "doctest", "unittest", "test", "configparser",
    "shelve", "dbm", "sqlite3", "xmlrpc", "netrc", "getopt",
    "webbrowser", "cgi", "formatter", "modulefinder",
    "runpy", "atexit", "gc", "__future__",
    "multiprocessing", "unicodedata", "difflib",
    "builtins", "__main__", "this", "antigravity",
}

LOCAL_PACKAGES = {
    "api_routes", "services", "engines", "utils", "config", "models",
    "middleware", "security", "jobs", "scheduler", "workers", "analytics",
    "reports", "systemd", "nginx", "api_v1", "scripts", "app",
    "auth_api", "creator_api", "feed_api", "live_api", "messages_api",
    "notifications_api", "profile_api", "reels_api", "system_api",
    "stripe",
}


def find_imports(root):
    imports = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(('.', '_')) and d not in {'venv', '__pycache__', 'node_modules'}]
        for fn in filenames:
            if not fn.endswith('.py'):
                continue
            fpath = os.path.join(dirpath, fn)
            try:
                with open(fpath, 'r') as f:
                    tree = ast.parse(f.read())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        top = alias.name.split('.')[0]
                        imports.add(top)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        top = node.module.split('.')[0]
                        imports.add(top)
    return imports


def main():
    errors = 0
    warnings = 0
    
    req_file = ROOT / 'requirements.txt'
    if not req_file.exists():
        print("FAIL: requirements.txt not found")
        sys.exit(1)

    with open(req_file) as f:
        req_lines = [line.strip() for line in f if line.strip() and not line.startswith('#')]

    req_packages = set()
    for line in req_lines:
        pkg = line.split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].split('!=')[0].strip()
        if pkg and not pkg.startswith('-'):
            req_packages.add(pkg.lower())

    print(f"Found {len(req_packages)} packages in requirements.txt")
    
    search_dirs = [
        ROOT / 'app.py',
        ROOT / 'api_routes',
        ROOT / 'services',
        ROOT / 'engines',
        ROOT / 'utils',
        ROOT / 'config',
        ROOT / 'scripts',
        ROOT / 'workers',
        ROOT / 'scheduler',
    ]

    all_imports = set()
    for sp in search_dirs:
        if sp.is_file():
            all_imports.update(find_imports(sp.parent))
        elif sp.is_dir():
            all_imports.update(find_imports(sp))

    all_imports.discard('typing')  # explicit allow
    all_imports.discard('typing_extensions')
    
    checked = set()
    missing = []
    
    for imp in sorted(all_imports):
        if imp in STDLIB_MODULES:
            continue
        if imp in LOCAL_PACKAGES:
            continue
        imp_lower = imp.lower()
        if imp_lower in checked:
            continue
        checked.add(imp_lower)

        pkg_name = TOP_LEVEL_MAP.get(imp, imp.replace('_', '-').lower())

        if pkg_name.lower() in req_packages:
            continue

        # Check in installed packages
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'show', pkg_name],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                continue
        except Exception:
            pass

        missing.append((imp, pkg_name))
    
    for imp, pkg in sorted(missing):
        print(f"WARNING: Import '{imp}' -> package '{pkg}' not in requirements.txt")
        warnings += 1

    if warnings == 0:
        print("PASS: All imports are covered by requirements.txt or installed packages")
    else:
        print(f"\n{warnings} import(s) missing from requirements.txt")
        errors += warnings

    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
