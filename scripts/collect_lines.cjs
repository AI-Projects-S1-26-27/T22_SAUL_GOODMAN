// Collect every line the courtroom can speak for the trials in data/bundle.js.
// Runs app.js's narration in a bare VM (no browser) and writes a JSON list of
// { who, name, text } to stdout, one entry per unique (speaker, text) pair.
// Usage: node scripts/collect_lines.cjs > lines.json
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const web = path.join(__dirname, "..", "courtroom", "viz", "web");
const stub = () => ({ matches: false, addEventListener() {} });
const ctx = { console, setTimeout, clearTimeout, matchMedia: stub, location: { protocol: "file:" }, localStorage: { getItem: () => null, setItem() {} } };
ctx.window = ctx;
ctx.document = { querySelector: () => null, querySelectorAll: () => [], addEventListener() {}, createElement: () => ({}) };
vm.createContext(ctx);
for (const f of ["data/bundle.js", "story.js", "artifacts.js"]) vm.runInContext(fs.readFileSync(path.join(web, f), "utf8"), ctx, { filename: f });

// app.js without its boot call, plus a collector that runs in the same script scope
const app = fs.readFileSync(path.join(web, "app.js"), "utf8").replace(/\ninit\(\);\s*$/, "\n");
const collect = `
globalThis.__lines = (() => {
  const seen = new Map();
  for (const t of Object.values(COURTROOM_BUNDLE.trials)) {
    S.caseId = t.case_id; S.trial = t;
    for (const ev of t.events) for (const b of narrate(ev).beats) {
      const who = b.who === "witness" ? "witness:" + b.name : b.who;
      const key = who + "|" + b.text;
      if (!seen.has(key)) seen.set(key, { who, text: b.text });
    }
  }
  return [...seen.values()];
})();`;
vm.runInContext(app + collect, ctx, { filename: "app.js" });
process.stdout.write(JSON.stringify(ctx.__lines, null, 1));
