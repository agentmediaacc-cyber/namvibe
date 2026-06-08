import inspect
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = ROOT / "templates"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app


def unwrap(func):
    return inspect.unwrap(func)


def template_refs(func):
    try:
        source = inspect.getsource(unwrap(func))
    except OSError:
        return []
    return re.findall(r'render_template\(\s*["\']([^"\']+)["\']', source)


def uses_feature_page(func):
    try:
        source = inspect.getsource(unwrap(func))
    except OSError:
        return False
    return "feature_page.html" in source


def main():
    seen = {}
    missing_templates = []
    duplicates = []
    placeholders = []

    print("CHAIN route audit")
    print("=" * 72)

    for rule in sorted(app.url_map.iter_rules(), key=lambda item: (item.rule, item.endpoint)):
        if rule.endpoint == "static":
            continue

        methods = sorted(method for method in rule.methods if method not in {"HEAD", "OPTIONS"})
        signature = (rule.rule, tuple(methods))
        if signature in seen:
            duplicates.append((rule, seen[signature]))
        else:
            seen[signature] = rule.endpoint

        func = app.view_functions.get(rule.endpoint)
        print(f"{','.join(methods):10} {rule.rule:35} -> {rule.endpoint}")

        if func:
            for template_name in template_refs(func):
                if not (TEMPLATE_ROOT / template_name).exists():
                    missing_templates.append((rule.endpoint, template_name))
            if uses_feature_page(func):
                placeholders.append((rule.endpoint, rule.rule))

    print("\nFlags")
    print("-" * 72)

    if duplicates:
        print("Duplicate routes:")
        for rule, original_endpoint in duplicates:
            print(f"  {rule.rule} {sorted(rule.methods)} duplicates {original_endpoint} with endpoint {rule.endpoint}")
    else:
        print("Duplicate routes: none")

    if missing_templates:
        print("Missing templates:")
        for endpoint, template_name in missing_templates:
            print(f"  {endpoint} -> {template_name}")
    else:
        print("Missing templates: none")

    if placeholders:
        print("Routes likely returning dashboard/feature_page.html:")
        for endpoint, route in placeholders:
            print(f"  {endpoint} -> {route}")
    else:
        print("Routes likely returning dashboard/feature_page.html: none")


if __name__ == "__main__":
    main()
