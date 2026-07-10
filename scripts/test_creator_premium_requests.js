#!/usr/bin/env node
const fs = require("fs");
const vm = require("vm");

const source = fs.readFileSync("static/js/creator_premium.js", "utf8").replace(
  /\}\)\(\);\s*$/,
  "window.__creatorPremiumTestHooks = { apiFetch: apiFetch, fetchDashboard: fetchDashboard, renderCreatorProfile: renderCreatorProfile };})();"
);

let pass = 0;
let fail = 0;

function check(label, condition, detail) {
  if (condition) {
    pass += 1;
    console.log(`  [PASS] ${label}`);
  } else {
    fail += 1;
    console.log(`  [FAIL] ${label}${detail ? " — " + detail : ""}`);
  }
}

function makeSandbox(fetchImpl, csrfToken) {
  const elements = {};
  const documentStub = {
    body: {
      appendChild() {},
    },
    createElement() {
      return {
        className: "",
        textContent: "",
        innerHTML: "",
        style: {},
        remove() {},
        appendChild(node) {
          this.textContent = node && node.textContent ? node.textContent : "";
          this.innerHTML = this.textContent;
        },
        classList: { toggle() {}, add() {}, remove() {} },
      };
    },
    createTextNode(text) {
      return {
        textContent: text,
        innerHTML: text,
      };
    },

    getElementById(id) {
      return elements[id] || null;
    },
    querySelector(selector) {
      if (selector === 'meta[name="csrf-token"]') {
        return csrfToken ? { getAttribute() { return csrfToken; } } : null;
      }
      return null;
    },
    querySelectorAll() {
      return [];
    },
    addEventListener() {},
  };

  const sandbox = {
    window: {},
    document: documentStub,
    fetch: fetchImpl,
    setTimeout(fn) {
      if (typeof fn === "function") fn();
      return 1;
    },
    clearTimeout() {},
    console,
  };
  sandbox.window = sandbox;
  vm.createContext(sandbox);
  vm.runInContext(source, sandbox);
  return sandbox;
}

async function run() {
  console.log("=== Creator Premium Request Tests ===");

  let fetchCalls = [];
  let dashboardResponses = [
    { status: 200, body: JSON.stringify({ ok: true, data: {} }) },
    { status: 200, body: JSON.stringify({ ok: true, data: { verification_status: "pending" } }) },
  ];
  let sandbox = makeSandbox((url, options) => {
    fetchCalls.push({ url, options: options || {} });
    const next = dashboardResponses.shift() || { status: 200, body: JSON.stringify({ ok: true, data: {} }) };
    return Promise.resolve({
      ok: next.status >= 200 && next.status < 300,
      status: next.status,
      text: () => Promise.resolve(next.body),
    });
  }, "csrf-token-123");

  await sandbox.creatorPost("/creator/subscriptions", { tier: "vip" });
  check("POST uses same-origin credentials", fetchCalls[0].options.credentials === "same-origin", JSON.stringify(fetchCalls[0]));
  check("POST includes CSRF token", fetchCalls[0].options.headers["X-CSRFToken"] === "csrf-token-123", JSON.stringify(fetchCalls[0].options.headers));

  fetchCalls = [];
  dashboardResponses = [
    { status: 200, body: JSON.stringify({ ok: true, data: {} }) },
    { status: 200, body: JSON.stringify({ ok: true, data: {} }) },
  ];
  sandbox = makeSandbox((url, options) => {
    fetchCalls.push({ url, options: options || {} });
    const next = dashboardResponses.shift() || { status: 200, body: JSON.stringify({ ok: true, data: {} }) };
    return Promise.resolve({
      ok: next.status >= 200 && next.status < 300,
      status: next.status,
      text: () => Promise.resolve(next.body),
    });
  }, "csrf-token-123");
  await sandbox.__creatorPremiumTestHooks.fetchDashboard();
  check("GET uses same-origin credentials", fetchCalls[0].options.credentials === "same-origin", JSON.stringify(fetchCalls[0]));
  check("GET does not include CSRF", !(fetchCalls[0].options.headers || {})["X-CSRFToken"], JSON.stringify(fetchCalls[0].options.headers || {}));

  let rejected = false;
  sandbox = makeSandbox(() => Promise.resolve({
    ok: false,
    status: 503,
    text: () => Promise.resolve(""),
  }), "csrf-token-123");
  try {
    await sandbox.__creatorPremiumTestHooks.apiFetch("/creator/api/dashboard");
  } catch (err) {
    rejected = String(err && err.message || err).indexOf("http_503") !== -1;
  }
  check("non-2xx responses reject with useful error", rejected);

  sandbox = makeSandbox(() => Promise.resolve({
    ok: true,
    status: 204,
    text: () => Promise.resolve(""),
  }), "csrf-token-123");
  try {
    const res = await sandbox.creatorPost("/creator/payouts", { amount_coins: 1 });
    check("204 or empty response does not crash JSON parsing", true, String(res));
  } catch (err) {
    check("204 or empty response does not crash JSON parsing", false, String(err));
  }

  let profileHtml = "";
  const profileContainer = { innerHTML: "" };
  sandbox = makeSandbox((url) => Promise.resolve({
    ok: true,
    status: 200,
    text: () => Promise.resolve(JSON.stringify({ ok: true, data: { username: "creatorx" } })),
  }), "");
  sandbox.document.getElementById = function (id) {
    if (id === "creatorProfileContainer") return profileContainer;
    return null;
  };
  await sandbox.__creatorPremiumTestHooks.renderCreatorProfile();
  profileHtml = profileContainer.innerHTML;
  check("creator profile render tolerates missing optional fields", profileHtml.indexOf("creatorx") !== -1 && profileHtml.indexOf("not_submitted") !== -1, profileHtml);

  console.log(`PASS: ${pass} FAIL: ${fail}`);
  process.exit(fail ? 1 : 0);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
