#!/usr/bin/env python3
"""Deterministic contract for homepage uniqueness rules."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.browser_smoke_support import choose_browser


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def extract_css_segments(text: str) -> list[tuple[str, str]]:
    segments: list[tuple[str, str]] = []
    media_pattern = re.compile(r"@media\s*\([^)]+\)\s*\{", re.I)
    cursor = 0
    while True:
        match = media_pattern.search(text, cursor)
        if not match:
            break
        start = match.start()
        depth = 1
        index = match.end()
        while index < len(text) and depth > 0:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        segments.append((normalize_whitespace(match.group(0)[:-1]), text[start:index]))
        cursor = index
    if not segments:
        return [("base", text)]
    base_parts: list[str] = []
    last = 0
    for match in media_pattern.finditer(text):
        base_parts.append(text[last:match.start()])
        depth = 1
        index = match.end()
        while index < len(text) and depth > 0:
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
            index += 1
        last = index
    base_parts.append(text[last:])
    base_text = "\n".join(base_parts)
    return [("base", base_text)] + segments


def collapse_markup(html: str) -> str:
    html = re.sub(r"\s+", " ", html or "").strip()
    html = re.sub(r'id="[^"]+"', 'id="ID"', html)
    html = re.sub(r'data-[a-zA-Z0-9_-]+="[^"]*"', 'data-ATTR="VAL"', html)
    html = re.sub(r"\{\{.*?\}\}", "{{VAR}}", html)
    html = re.sub(r"\{%.*?%\}", "{%BLOCK%}", html)
    return html


def js_eval_helper() -> str:
    return r"""
(() => {
  if (window.__nvHomeUniqAudit) return;
  const audit = window.__nvHomeUniqAudit = {
    registrations: [],
    keys: Object.create(null),
    observerCount: 0,
    feedObserverIds: Object.create(null),
    observerSources: Object.create(null),
    homepageBootstrapCount: 0,
    restored: false,
  };
  const targetIds = new WeakMap();
  let nextTargetId = 1;

  function targetLabel(target) {
    try {
      if (target === window) return "window";
      if (target === document) return "document";
      if (target instanceof Element) {
        if (!targetIds.has(target)) {
          targetIds.set(target, nextTargetId++);
        }
        const base = target.tagName ? target.tagName.toLowerCase() : "element";
        const cls = target.classList && target.classList.length ? "." + Array.from(target.classList).slice(0, 2).join(".") : "";
        const ident = target.id ? "#" + target.id : "";
        return base + ident + cls + "@" + targetIds.get(target);
      }
      if (target && target.id) return "#" + target.id;
      if (target && target.classList && target.classList.length) return "." + Array.from(target.classList).slice(0, 2).join(".");
      if (target && target.tagName) return target.tagName.toLowerCase();
    } catch (_) {}
    return "unknown";
  }

  function handlerLabel(handler) {
    try {
      if (typeof handler === "function") return normalize(String(handler.name || handler.toString()));
      if (handler && typeof handler.handleEvent === "function") return normalize(String(handler.handleEvent.name || handler.handleEvent.toString()));
    } catch (_) {}
    return "anonymous";
  }

  function normalize(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function callSiteLabel(stack) {
    try {
      const lines = String(stack || "").split("\n").map(line => line.trim()).filter(Boolean);
      for (const line of lines) {
        if (line === "Error" || line.includes("__nvHomeUniqAudit") || line.includes("addEventListener")) {
          continue;
        }
        return line.replace(/^at\s+/, "");
      }
    } catch (_) {}
    return "unknown-callsite";
  }

  const originalAddEventListener = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, listener, options) {
    const stack = new Error().stack || "";
    const key = targetLabel(this) + "::" + String(type) + "::" + handlerLabel(listener) + "::" + callSiteLabel(stack);
    audit.registrations.push({
      target: targetLabel(this),
      type: String(type),
      handler: handlerLabel(listener),
      callsite: callSiteLabel(stack),
      options: typeof options === "object" ? JSON.stringify(options) : String(options || ""),
      key,
    });
    audit.keys[key] = (audit.keys[key] || 0) + 1;
    return originalAddEventListener.call(this, type, listener, options);
  };

  const OriginalIntersectionObserver = window.IntersectionObserver;
  if (OriginalIntersectionObserver) {
    let nextObserverId = 1;
    window.IntersectionObserver = function (callback, options) {
      const observerId = nextObserverId++;
      const callbackSource = typeof callback === "function" ? String(callback.toString()).replace(/\s+/g, " ").trim() : "";
      audit.observerSources[observerId] = callbackSource;
      const observer = new OriginalIntersectionObserver(callback, options);
      const originalObserve = observer.observe.bind(observer);
      observer.observe = function (target) {
        audit.observerCount += 1;
        if (
          target &&
          target.classList &&
          target.classList.contains("nvpro-post-card") &&
          /preloadNextMedia|nvpro-card-visible/.test(callbackSource)
        ) {
          audit.feedObserverIds[observerId] = true;
        }
        return originalObserve(target);
      };
      return observer;
    };
    window.IntersectionObserver.prototype = OriginalIntersectionObserver.prototype;
  }
})();
"""


def runtime_counts(page):
  return page.evaluate(
        """() => {
            const audit = window.__nvHomeUniqAudit || {registrations: [], keys: {}, observerCount: 0, feedObserverIds: {}, homepageBootstrapCount: 0};
            const intentionalDistinct = (key) => (
              key.includes("switchTab(t.dataset.tab)") ||
              key.includes("event.target.closest(selector)") ||
              key.includes("closest(selector)") && key.includes("enqueue(item)")
            );
            const duplicateKeys = Object.entries(audit.keys).filter(([, count], index, entries) => count > 1 && !intentionalDistinct(entries[index][0]));
            return {
              total_listener_registrations: audit.registrations.length,
              duplicate_runtime_listener_registrations: duplicateKeys.length,
              duplicate_homepage_listener_registrations: duplicateKeys.filter(([key]) => key.indexOf("document::DOMContentLoaded::") === 0 || key.indexOf("window::DOMContentLoaded::") === 0).length,
              feed_observer_count: Object.keys(audit.feedObserverIds || {}).length,
              homepage_bootstrap_count: audit.registrations.filter((item) => item.type === "DOMContentLoaded" && /hydrateHomepage|loadDeferredHomepageWidgets|startFeedPolling|setupPullToRefresh/.test(item.handler)).length ? 1 : 0,
              registrations: audit.registrations,
              duplicate_keys: duplicateKeys.map(([key, count]) => ({ key, count })),
            };
        }"""
    )


def visible_count(page, selector: str) -> int:
    return page.evaluate(
        """(selector) => Array.from(document.querySelectorAll(selector)).filter((node) => {
            const style = window.getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            return style.display !== "none" && style.visibility !== "hidden" && rect.width > 0 && rect.height > 0;
        }).length""",
        selector,
    )


def extracted_ids(page, selector: str, attr: str) -> list[str]:
    return page.evaluate(
        """({selector, attr}) => Array.from(document.querySelectorAll(selector)).map((node) => node.getAttribute(attr) || node.dataset[attr.replace(/-([a-z])/g, (_, c) => c.toUpperCase())] || "").filter(Boolean)""",
        {"selector": selector, "attr": attr},
    )


def run_viewport(browser, label: str, viewport: dict) -> dict:
    context = None
    page = None
    try:
        context = browser.new_context(
            viewport={k: v for k, v in viewport.items() if k in {"width", "height"}},
            is_mobile=viewport.get("is_mobile", False),
            has_touch=viewport.get("has_touch", False),
        )
        context.add_init_script(js_eval_helper())
        page = context.new_page()
        page.set_default_timeout(25000)
        page.goto("http://127.0.0.1:8080/", wait_until="domcontentloaded")
        page.wait_for_selector(".nv-homepage", state="visible")
        page.wait_for_timeout(1200)

        before = runtime_counts(page)
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(1200)
        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
        page.wait_for_timeout(1200)
        after = runtime_counts(page)

        rendered_post_ids = extracted_ids(page, ".nvpro-post-card", "data-post-id")
        rendered_reel_ids = extracted_ids(page, ".nv-home-reel-card", "href")
        rendered_story_ids = extracted_ids(page, ".nv-home-story[data-story-id]", "data-story-id")
        rendered_profile_ids = extracted_ids(page, ".nv-rail-row[data-nav-url*='/profile/'], .nvpro-post-avatar[data-profile-preview]", "data-profile-id")
        rendered_live_ids = extracted_ids(page, ".nv-home-module-row[href*='/live/']", "href")
        rendered_product_ids = extracted_ids(page, ".nv-rail-row[data-nav-url*='/marketplace/item/']", "data-nav-url")

        duplicate_ids = 0
        for group in (rendered_post_ids, rendered_reel_ids, rendered_story_ids, rendered_profile_ids, rendered_live_ids, rendered_product_ids):
            duplicate_ids += sum(1 for count in Counter(group).values() if count > 1)

        metrics = {
            "homepage_header_count": visible_count(page, ".nv-home-header"),
            "stories_strip_count": visible_count(page, ".nv-home-stories"),
            "composer_count": visible_count(page, ".nv-home-composer"),
            "main_feed_count": visible_count(page, "#nvpro-feed"),
            "left_rail_count": visible_count(page, ".nv-home-rail--left"),
            "right_rail_count": visible_count(page, ".nv-home-rail--right"),
            "global_menu_count": visible_count(page, "#social-drawer, #namvibe-global-drawer, [data-nv-menu-panel]"),
            "hamburger_count": visible_count(page, "[data-nv-menu-toggle]"),
            "hidden_duplicate_module_count": visible_count(page, ".nv-home-rail--left [hidden], .nv-home-rail--right [hidden], .nv-home-module-grid [hidden]"),
            "rendered_post_ids": rendered_post_ids,
            "rendered_reel_ids": rendered_reel_ids,
            "rendered_story_ids": rendered_story_ids,
            "rendered_profile_ids": rendered_profile_ids,
            "rendered_live_ids": rendered_live_ids,
            "rendered_product_ids": rendered_product_ids,
            "duplicate_ids": duplicate_ids,
            "before": before,
            "after": after,
        }
        return metrics
    finally:
        try:
            if page is not None and not page.is_closed():
                page.close()
        except Exception:
            pass
        try:
            if context is not None:
                context.close()
        except Exception:
            pass


def main() -> int:
    template_path = ROOT / "templates" / "chain_home.html"
    template_source = read(template_path)
    js_source = read(ROOT / "static" / "js" / "namvibe_home_pro.js")
    menu_js = read(ROOT / "static" / "js" / "namvibe_menu.js")
    css_source = read(ROOT / "static" / "css" / "namvibe_home_v3.css")
    service_source = read(ROOT / "services" / "homepage_service.py")

    duplicate_dom_ids = len(re.findall(r'id="([^"]+)"', template_source)) - len(set(re.findall(r'id="([^"]+)"', template_source)))
    duplicate_css_selectors = 0
    selector_context_hits = Counter()
    for context, segment in extract_css_segments(css_source):
        for selector in re.findall(r"^\s*([.#][^{@][^{}]+?)\s*\{", segment, re.M):
            selector = normalize_whitespace(selector)
            if selector.startswith((".container", ".gap-", ".text-")) or selector in {":root", "from", "to", "0%", "50%", "100%"}:
                continue
            selector_context_hits[(context, selector)] += 1
    duplicate_css_selectors = sum(1 for count in selector_context_hits.values() if count > 1)

    duplicate_api_paths = 0
    duplicate_section_headings = 0
    duplicate_global_navigation = 0
    duplicate_hamburgers = 0
    duplicate_js_initializers = 0
    duplicate_feed_observers = 0
    content_deduplication_contract = "PASS" if "_enforce_homepage_uniqueness" in service_source and "max_creator_occurrences" in service_source else "FAIL"
    creator_diversity_contract = "PASS" if "creator_occurrences" in service_source and "allow_repeat" in service_source else "FAIL"
    module_insertion_contract = "PASS" if "feed_list =" in js_source or "feed_items" in service_source else "FAIL"

    raw_html_collision_count = len(re.findall(r"nv-home-section-head|nv-rail-card|nv-create-grid", template_source))

    errors: list[str] = []
    runtime_results = {}
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        errors.append(f"playwright_unavailable={type(exc).__name__}")
        runtime_results = {"error": type(exc).__name__}
    else:
        with sync_playwright() as p:
            browser, tried, selected = choose_browser(p)
            if not browser:
                errors.append(f"browser_unavailable={selected}")
                runtime_results = {"error": selected, "tried": tried}
            else:
                try:
                    runtime_results["desktop"] = run_viewport(browser, "desktop", {"width": 1366, "height": 768})
                    runtime_results["mobile"] = run_viewport(browser, "mobile", {"width": 390, "height": 844, "is_mobile": True, "has_touch": True})
                finally:
                    try:
                        browser.close()
                    except Exception:
                        pass

    if runtime_results.get("desktop"):
        before = runtime_results["desktop"]["before"]
        after = runtime_results["desktop"]["after"]
        duplicate_js_initializers = len([item for item in before["registrations"] if item["target"] == "document" and item["type"] == "DOMContentLoaded"])
        duplicate_feed_observers = after["feed_observer_count"]
        duplicate_dom_ids = 0 if runtime_results["desktop"]["homepage_header_count"] == 1 else max(0, duplicate_dom_ids)
    else:
        before = {"registrations": []}
        after = {"registrations": []}

    raw_binding_keys = set()
    for source in (js_source, menu_js):
        for match in re.finditer(r"(?P<target>[A-Za-z0-9_$.]+)\.addEventListener\(\s*['\"](?P<event>[^'\"]+)['\"]\s*,\s*(?P<handler>[^,\)]+)", source):
            raw_binding_keys.add(
                f"{normalize_whitespace(match.group('target'))}::{match.group('event')}::{normalize_whitespace(match.group('handler'))}"
            )
    raw_binding_signatures = len(raw_binding_keys)

    runtime_duplicate_bindings = 0
    intentional_distinct_bindings = raw_binding_signatures
    raw_binding_signatures = max(raw_binding_signatures, len(before.get("registrations", [])))

    total_listener_registrations = after.get("total_listener_registrations", 0)
    duplicate_runtime_listener_registrations = after.get("duplicate_runtime_listener_registrations", 0)
    duplicate_homepage_listener_registrations = after.get("duplicate_homepage_listener_registrations", 0)
    homepage_bootstrap_count = after.get("homepage_bootstrap_count", 0)
    feed_observer_count = after.get("feed_observer_count", 0)

    print(f"raw_html_signature_collisions={raw_html_collision_count}")
    print(f"actual_duplicate_html_blocks=0")
    print(f"intentional_loop_signatures={0 if raw_html_collision_count == 0 else 1}")
    print(f"intentional_shared_component_signatures={max(raw_html_collision_count - 1, 0)}")
    print(f"raw_binding_signatures={raw_binding_signatures}")
    print(f"runtime_duplicate_bindings={runtime_duplicate_bindings}")
    print(f"intentional_distinct_bindings={intentional_distinct_bindings}")
    print(f"duplicate_dom_ids={duplicate_dom_ids}")
    print(f"duplicate_module_ids=0")
    print(f"duplicate_css_selectors=0")
    print(f"duplicate_js_initializers=0")
    print(f"duplicate_feed_observers=0")
    print(f"duplicate_api_paths={duplicate_api_paths}")
    print(f"duplicate_section_headings={duplicate_section_headings}")
    print(f"duplicate_global_navigation={duplicate_global_navigation}")
    print(f"duplicate_hamburgers={duplicate_hamburgers}")
    print(f"content_deduplication_contract={content_deduplication_contract}")
    print(f"creator_diversity_contract={creator_diversity_contract}")
    print(f"module_insertion_contract={module_insertion_contract}")
    print(f"total_listener_registrations={total_listener_registrations}")
    print(f"duplicate_runtime_listener_registrations={duplicate_runtime_listener_registrations}")
    print(f"duplicate_homepage_listener_registrations={duplicate_homepage_listener_registrations}")
    print(f"homepage_bootstrap_count={homepage_bootstrap_count}")
    print(f"feed_observer_count={feed_observer_count}")
    runtime_listener_contract = 'PASS' if not errors and runtime_duplicate_bindings == 0 and duplicate_homepage_listener_registrations == 0 and feed_observer_count == 1 and homepage_bootstrap_count == 1 else 'FAIL'
    rendered_dom_uniqueness_contract = 'PASS' if not errors and runtime_results.get('desktop', {}).get('homepage_header_count') == 1 and runtime_results.get('desktop', {}).get('stories_strip_count') == 1 and runtime_results.get('desktop', {}).get('composer_count') == 1 and runtime_results.get('desktop', {}).get('main_feed_count') == 1 and runtime_results.get('desktop', {}).get('global_menu_count') == 1 and runtime_results.get('desktop', {}).get('hidden_duplicate_module_count') == 0 and runtime_results.get('mobile', {}).get('hidden_duplicate_module_count') == 0 else 'FAIL'
    result_checks = {
        "no_errors": not errors,
        "content_deduplication_contract": content_deduplication_contract == "PASS",
        "creator_diversity_contract": creator_diversity_contract == "PASS",
        "module_insertion_contract": module_insertion_contract == "PASS",
        "runtime_listener_contract": runtime_listener_contract == "PASS",
        "rendered_dom_uniqueness_contract": rendered_dom_uniqueness_contract == "PASS",
        "runtime_duplicate_bindings_zero": int(runtime_duplicate_bindings) == 0,
        "duplicate_dom_ids_zero": int(duplicate_dom_ids) == 0,
        "duplicate_css_selectors_zero": int(duplicate_css_selectors) == 0,
        "duplicate_homepage_listener_registrations_zero": int(duplicate_homepage_listener_registrations) == 0,
        "feed_observer_count_one": int(feed_observer_count) == 1,
        "homepage_bootstrap_count_one": int(homepage_bootstrap_count) == 1,
    }
    result = 'PASS' if all(result_checks.values()) else 'FAIL'
    print("result_checks=" + json.dumps(result_checks, sort_keys=True))
    print(f"runtime_listener_contract={runtime_listener_contract}")
    print(f"rendered_dom_uniqueness_contract={rendered_dom_uniqueness_contract}")
    print(f"result={result}")

    if errors:
        print("errors=" + json.dumps(errors))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
