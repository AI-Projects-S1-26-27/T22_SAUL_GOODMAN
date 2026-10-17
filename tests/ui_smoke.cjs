/* Smoke-run the web UI's real JavaScript against the real bundle, with a stub DOM.
 *
 * What it can catch: a ReferenceError (a function that was deleted or never defined), or a crash
 * while rendering real trial data. Both slipped past the Python suite before this existed: a
 * splice deleted three functions that init() still called, and a guard missed a null trial.
 *
 * What it cannot: layout, colour, or anything that needs a real browser. It is a net, not a test
 * of how the page looks.
 *
 * Every stubbed element is a Proxy that answers any property or call with itself, so code runs
 * through its branches rather than dying on the first missing DOM method. fetch always fails, so
 * the page takes its offline path and renders from bundle.js. Every registered listener is then
 * fired once with a fake event.
 */
const fs = require("fs");
const vm = require("vm");
const path = require("path");

const web = path.join(__dirname, "..", "courtroom", "viz", "web");
const problems = [];
const note = (where, err) => problems.push(`${where}: ${err && err.stack ? err.stack.split("\n").slice(0, 3).join(" | ") : err}`);
process.on("unhandledRejection", (e) => note("unhandled rejection", e));
process.on("uncaughtException", (e) => note("uncaught exception", e));

/* The app catches some of its own errors and shows them to the user ("The trial couldn't run
 * (x is not defined)"). That is correct behaviour for a user and exactly the failure this harness
 * exists to find, so anything the app tries to display that reads like a JavaScript error counts. */
const SELF_REPORTED = /is not defined|is not a function|Cannot read propert|Cannot set propert|is not iterable|undefined \(reading/;
function scanForSelfReportedErrors(where, args) {
  for (const a of args) if (typeof a === "string" && SELF_REPORTED.test(a)) note(`the app displayed an error from ${where}`, a);
}

const dataIds = new Set(); // "<class>|<data-id>" for every element stamped with a data-id, e.g. "ev-item|P-LAPTOP"
const listeners = [];
function makeEl(label) {
  const store = {};
  const p = new Proxy(function () {}, {
    get(_t, k) {
      if (k === Symbol.toPrimitive) return (hint) => (hint === "number" ? 0 : "");
      if (k === Symbol.iterator) return function* () {};
      if (k === "then") return undefined;
      if (k === "length") return 0;
      if (k === "addEventListener") return (type, fn) => listeners.push({ label, type, fn });
      if (k === "setAttribute") return (name, value) => { if (name === "data-id") dataIds.add(`${store.className ?? ""}|${value}`); };
      if (k === "append" || k === "replaceChildren" || k === "prepend") return (...args) => { scanForSelfReportedErrors(label, args); return undefined; };
      if (k === "dataset") return store.dataset ?? (store.dataset = {});
      if (k in store) return store[k];
      return p;
    },
    set(_t, k, v) {
      if (k === "textContent" || k === "innerHTML") scanForSelfReportedErrors(label, [v]);
      store[k] = v;
      return true;
    },
    apply() { return p; },
    has() { return true; },
  });
  return p;
}

/* Live scenario. With UI_SMOKE_LIVE=<fixtures.json> the page believes it is talking to the real
 * server, so the live-only code (injection, replay at a bar, recompute, the editor's Analyse) runs.
 * The fixtures are genuine engine output written by the Python test, not hand-made stand-ins. */
const fx = process.env.UI_SMOKE_LIVE ? JSON.parse(fs.readFileSync(process.env.UI_SMOKE_LIVE, "utf8")) : null;
const calls = [];
function liveFetch(url, opts) {
  const u = String(url);
  const body = opts && opts.body ? JSON.parse(opts.body) : null;
  calls.push({ path: u.replace(/^.*\/api/, ""), injections: body && body.injections ? body.injections.length : 0, bar: body && body.bar != null ? body.bar : null, inlineCase: !!(body && body.case) });
  const ok = (data) => Promise.resolve({ ok: true, status: 200, json: async () => data, text: async () => JSON.stringify(data) });
  if (u.endsWith("/health")) return ok({ status: "ok" });
  if (u.endsWith("/cases")) return ok(fx.cases.map((c) => ({ id: c.id, title: c.title, synopsis: c.synopsis, case_type: c.case_type, standard: c.standard, tags: c.tags })));
  if (u.endsWith("/strategies")) return ok(fx.strategies);
  if (u.endsWith("/rules")) return ok(fx.rules);
  const m = u.match(/\/cases\/([^/]+)$/);
  if (m) return ok(fx.cases.find((c) => c.id === decodeURIComponent(m[1])));
  if (u.endsWith("/trial")) return ok(body && body.injections && body.injections.length ? fx.injected : fx.baseline);
  if (u.endsWith("/game")) return ok(fx.game);
  if (u.endsWith("/narrate")) return ok({ digest: "", narration: {}, source: "template", usage: { calls: 0, cache_hits: 0, unavailable: 0, cost_estimate_usd: 0 } });
  if (u.endsWith("/validate")) return ok({ ok: true, case_id: "x", title: "x", elements: 3, witnesses: 1, evidence: 2 });
  return Promise.reject(new Error("no network in the smoke test"));
}

const memory = new Map();
const ctx = {
  console: { log() {}, warn() {}, error() {}, info() {}, debug() {} },
  document: {
    querySelector: (sel) => {
      // Give the controls the values a user would have, or init never selects a case and the
      // whole trial-rendering path goes unexercised.
      const e = makeEl(sel);
      const values = {
        "#case": ctx.COURTROOM_BUNDLE?.cases?.[0]?.id, "#seed": "0", "#thr-slider": "85", "#gseeds": "20", "#gstrats": "aggressive,conservative",
        "#speed": "1200", "#thr-seeds": "10", "#inj-owner": "prosecution", "#inj-kind": "document", "#inj-title": "Newly recovered drive image",
        "#inj-reliability": "0.9", "#ed-text": fx ? JSON.stringify(fx.cases[0]) : "",
      };
      if (sel in values) e.value = values[sel];
      if (/^#inj-(hearsay|unverified|illegal|late)$/.test(sel)) e.checked = false;
      if (sel.includes('name="prosecution-style"')) e.value = "aggressive";
      if (sel.includes('name="defense-style"')) e.value = "conservative";
      return e;
    },
    querySelectorAll: (sel) => {
      if (sel === "#inj-support input") {
        const input = makeEl("#inj-support input");
        input.dataset = { element: fx && fx.cases[0].elements[0].id };
        input.value = "0.8";
        return [input];
      }
      return [];
    },
    getElementById: (id) => makeEl(`#${id}`),
    createElement: (t) => makeEl(`<${t}>`),
    createElementNS: (_ns, t) => makeEl(`<${t}>`),
    createTextNode: () => makeEl("#text"),
    body: makeEl("body"),
    documentElement: makeEl("html"),
    addEventListener: (type, fn) => listeners.push({ label: "document", type, fn }),
    activeElement: makeEl("active"),
  },
  localStorage: { getItem: (k) => (memory.has(k) ? memory.get(k) : null), setItem: (k, v) => memory.set(k, String(v)), removeItem: (k) => memory.delete(k) },
  location: { protocol: "http:", hash: "", search: "", href: "http://localhost/", pathname: "/", origin: "http://localhost" },
  history: { replaceState() {}, pushState() {} },
  fetch: (url, opts) => (fx ? liveFetch(url, opts) : Promise.reject(new Error("no network in the smoke test"))),
  matchMedia: () => ({ matches: false, addEventListener() {}, addListener() {} }),
  getComputedStyle: () => ({ getPropertyValue: () => "#888" }),
  requestAnimationFrame: () => 0,
  cancelAnimationFrame() {},
  setTimeout: () => 0,
  clearTimeout() {},
  setInterval: () => 0,
  clearInterval() {},
  ResizeObserver: class { observe() {} disconnect() {} },
  IntersectionObserver: class { observe() {} disconnect() {} },
  AbortController, URL, URLSearchParams, JSON, Math, Date, Promise, Map, Set, Number, String, Object, Array, Boolean, RegExp, Error, Symbol,
  addEventListener: (type, fn) => listeners.push({ label: "window", type, fn }),
  CSS: { escape: (x) => String(x) },
  scrollTo() {}, open() {}, innerWidth: 1200, innerHeight: 800,
};
ctx.window = ctx;
ctx.self = ctx;
ctx.globalThis = ctx;
vm.createContext(ctx);

function run(file) {
  const override = file === "app.js" && process.env.UI_SMOKE_APP ? process.env.UI_SMOKE_APP : null;
  vm.runInContext(fs.readFileSync(override ?? path.join(web, file), "utf8"), ctx, { filename: file });
}

(async () => {
  run("data/bundle.js");
  if (!ctx.COURTROOM_BUNDLE) throw new Error("bundle.js did not define COURTROOM_BUNDLE");
  run("app.js");
  for (let i = 0; i < 40; i++) await new Promise((r) => setImmediate(r));

  const initProblems = problems.length;
  const fake = () => ({ target: makeEl("target"), currentTarget: makeEl("current"), key: "", preventDefault() {}, stopPropagation() {}, clientX: 0, clientY: 0 });
  for (const l of listeners.slice()) {
    try {
      const out = l.fn(fake());
      if (out && typeof out.then === "function") await out.catch((e) => note(`handler ${l.type} on ${l.label}`, e));
    } catch (e) {
      note(`handler ${l.type} on ${l.label}`, e);
    }
    await new Promise((r) => setImmediate(r));
  }
  // Tabs are activated by buttons the stub DOM does not have, so visit each one directly.
  for (const tab of ["overview", "courtroom", "casefile", "verdict", "strategy", "judge"]) {
    try { if (typeof ctx.activateTab === "function") ctx.activateTab(tab); } catch (e) { note(`activating the ${tab} tab`, e); }
    await new Promise((r) => setImmediate(r));
  }
  for (let i = 0; i < 20; i++) await new Promise((r) => setImmediate(r));

  const fatal = problems.filter((p) => !p.includes("no network in the smoke test"));
  console.log(JSON.stringify({ listeners: listeners.length, initProblems, problems: fatal, calls: fx ? calls : undefined, dataIds: fx ? [...dataIds].sort() : undefined }, null, 2));
  process.exit(fatal.length ? 1 : 0);
})().catch((e) => { console.log(JSON.stringify({ crashed: String(e && e.stack || e) })); process.exit(2); });
