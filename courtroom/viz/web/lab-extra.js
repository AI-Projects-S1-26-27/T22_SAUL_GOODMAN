/* Extra strategy-lab chapters that need the local server: they are measured by the engine on request, never typed in.
 *
 *   Does strategy matter here?   for each case, how far the lawyers' styles and the seed move the verdict
 *   How sure are we?             (added with the bootstrap) confidence intervals and the stability of the conclusion
 *   Can a better lawyer be found? (added with the best-response search) whether the four styles can be beaten
 *
 * They use the same five-part shape as the chapters in lab.js and are inserted before "Ask the analyst". On the hosted
 * site (no server) each one says what it needs, and shows what the recorded bundle can honestly say.
 */
(function () {
  "use strict";
  const B = window.COURTROOM_BUNDLE, root = document.getElementById("lab-root");
  if (!B || !root) return;
  const API = location.protocol.startsWith("http") ? "/api" : null;
  const $ = (sel, r = document) => r.querySelector(sel);
  const h = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const c of kids.flat(3)) if (c != null && c !== false && c !== "") n.append(c);
    return n;
  };
  const pct = (v) => `${Math.round(v * 100)}%`;
  const caseName = (c) => c.title.split(" — ").pop();
  const NAME = { aggressive: "Bold", conservative: "Careful", adaptive: "Smart" };
  const post = async (path, body) => {
    const r = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`${path} ${r.status}`);
    return r.json();
  };

  let live = false;
  let caseId = "helix-espionage";
  let surprises = false;
  const registry = [];

  /* the same markup chapter() builds in lab.js, so the new chapters look like the old ones */
  function chapter(id, title, { lead, read, fig, maths }) {
    return h("section", { class: "chapter", id: `ch-${id}`, "aria-labelledby": `ch-${id}-t` },
      h("header", { class: "ch-head" }, h("span", { class: "ch-num", "aria-hidden": "true" }, "00"), h("h2", { id: `ch-${id}-t` }, title)),
      h("div", { class: "prose" }, lead),
      read && h("div", { class: "howto" }, h("h3", {}, "How to read it"), h("ol", {}, read.map((r) => h("li", {}, r)))),
      fig && h("div", { class: "fig" }, fig),
      h("div", { class: "says", id: `says-${id}`, hidden: true }, h("h3", {}, "What it says for this case"), h("div", { class: "says-body", role: "status" })),
      maths && h("details", { class: "maths" }, h("summary", {}, "Show the working"), h("div", { class: "maths-body" }, maths)));
  }
  const says = (id, ...kids) => { const b = $(`#says-${id}`); b.hidden = false; $(".says-body", b).replaceChildren(...kids.flat().filter(Boolean)); };
  const note = (text) => h("p", { class: "fig-note" }, text);
  const needServer = (what) => h("p", { class: "fig-note" }, `${what} needs the local server. Run `, h("code", {}, "python -m courtroom serve"), " and reload this page.");

  /* ---------------------------------------------------------------- chapter: does strategy matter here? */

  const mattersCache = new Map();
  const getMatters = async (id) => {
    const key = `${id}|${surprises}`;
    if (!mattersCache.has(key)) mattersCache.set(key, await post("/matters", { case_id: id, seeds: 5, surprises }));
    return mattersCache.get(key);
  };
  const TONE = { evidence: "flat", lawyers: "moves", partly_lawyers: "some", seeds: "luck" };

  /* what the recorded bundle can say with one trial per pairing: whether any pairing changes the verdict */
  function recordedMatters(c) {
    const styles = ["aggressive", "conservative", "adaptive"];
    const wins = styles.flatMap((p) => styles.map((d) => ["guilty", "liable"].includes(B.trials[`${c.id}|${p}|${d}|0`]?.verdict.outcome)));
    const any = wins.some(Boolean), all = wins.every(Boolean);
    return { label: !any || all ? "Decided by the evidence" : "Decided by the lawyers", verdict: !any || all ? "evidence" : "lawyers", explanation: "From one recorded trial per pairing, so this cannot tell luck from skill.", pairing_spread: any && !all ? 1 : 0, seed_noise: null };
  }

  async function renderMatters() {
    const c = B.cases.find((x) => x.id === caseId);
    const body = $("#matters-fig");
    if (!c || !body) return;
    if (!live) {
      body.replaceChildren(needServer("Measuring this with fresh runs"), h("p", {}, "From the recorded trials only: ", h("b", {}, recordedMatters(c).label), ". ", recordedMatters(c).explanation));
      says("matters", h("p", {}, `${caseName(c)}: ${recordedMatters(c).label.toLowerCase()} (recorded trials only).`));
      return;
    }
    body.replaceChildren(h("p", { class: "muted" }, "Measuring every case from fresh runs…"));
    const rows = [];
    for (const k of B.cases) {
      try {
        const m = await getMatters(k.id);
        rows.push(h("tr", { class: k.id === caseId ? "current" : null },
          h("th", { scope: "row" }, caseName(k)),
          h("td", {}, h("span", { class: `matter-tag ${TONE[m.verdict]}` }, m.label)),
          h("td", {}, pct(m.pairing_spread)), h("td", {}, pct(m.seed_noise)), h("td", {}, pct(m.overall_win_rate))));
      } catch { /* leave the row out */ }
      if (caseId !== c.id) return;
    }
    const sw = h("label", { class: "check small" }, h("input", { type: "checkbox", checked: surprises, onchange: (e) => { surprises = e.target.checked; renderMatters(); } }), h("span", {}, " Courtroom surprises on (a witness may not appear, a record may lack its certificate, a witness may turn hostile)"));
    body.replaceChildren(sw, h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
      h("thead", {}, h("tr", {}, ["Case", "Verdict", "Lawyers move it by", "Seed coin-flip", "Accuser wins overall"].map((t) => h("th", {}, t)))),
      h("tbody", {}, rows))),
      note("Every number is measured now: all 9 pairings of Bold, Careful and Smart over 5 seeds (45 fresh trials per case)."));
    const m = await getMatters(caseId);
    says("matters", h("p", {}, h("b", {}, caseName(c)), `: ${m.label.toLowerCase()}. ${m.explanation} The best pairing and the worst differ by ${pct(m.pairing_spread)} in how often the Accuser wins, and in the average pairing the seed alone moves the result ${pct(m.seed_noise)} of the way to a coin flip.`));
  }

  registry.push({
    id: "matters",
    build: () => chapter("matters", "Does strategy matter here?", {
      lead: [
        h("p", {}, "Before asking which style is best, ask whether the style matters at all. In some cases the evidence alone decides the verdict, and every lawyer, however clever, ends in the same place. Game theory has nothing to find there."),
        h("p", {}, "So for each case we run every pairing of Bold, Careful and Smart on several seeds and look at how the verdict moves. Two things can move it: who the lawyers are, and the seed (the luck of the draw)."),
      ],
      read: ["“Decided by the evidence”: no pairing and no seed changes the verdict.", "“Decided by the lawyers”: changing the styles flips it. These are the cases worth studying.", "“A coin-flip between seeds”: the same lawyers get different verdicts on different draws."],
      fig: h("div", { id: "matters-fig" }),
      maths: h("p", {}, "Pairing spread is the highest Accuser win rate minus the lowest across the 9 pairings. Seed coin-flip is, averaged over the pairings, 2 × min(win rate, 1 − win rate): 0 when a pairing always ends the same way, 1 when it is a coin flip. The label is “by the lawyers” at a spread of 50% or more, “a coin-flip” at 30% or more, “partly the lawyers” at 20% or more, else “by the evidence”. These cut-offs only choose the words; the numbers are what the engine measured."),
    }),
    refresh: renderMatters,
  });

  /* ---------------------------------------------------------------- put them on the page */

  function mount() {
    const anchor = $("#ch-analyst");
    const rail = $(".rail ol");
    for (const ch of registry) {
      if ($(`#ch-${ch.id}`)) continue;
      const node = ch.build();
      anchor ? anchor.before(node) : $(".chapters")?.append(node);
      rail?.append(h("li", {}, h("a", { href: `#ch-${ch.id}`, "data-ch": ch.id }, h("span", {}, "00"), node.querySelector("h2").textContent)));
    }
    // renumber everything in page order
    const all = [...document.querySelectorAll(".chapter")];
    all.forEach((sec, i) => { const n = String(i + 1).padStart(2, "0"); sec.querySelector(".ch-num").textContent = n; });
    const links = [...document.querySelectorAll(".rail li")].sort((a, b) => all.findIndex((s) => `#${s.id}` === a.firstElementChild.getAttribute("href")) - all.findIndex((s) => `#${s.id}` === b.firstElementChild.getAttribute("href")));
    links.forEach((li, i) => { li.firstElementChild.querySelector("span").textContent = String(i + 1).padStart(2, "0"); rail?.append(li); });
    const spy = new IntersectionObserver((entries) => {
      for (const en of entries) if (en.isIntersecting) document.querySelectorAll(".rail a").forEach((a) => a.setAttribute("aria-current", String(`ch-${a.dataset.ch}` === en.target.id)));
    }, { rootMargin: "-30% 0px -60% 0px" });
    all.forEach((c) => spy.observe(c));
  }

  const refreshAll = () => registry.forEach((ch) => ch.refresh?.());
  window.addEventListener("lab-refresh", (e) => { caseId = e.detail.caseId; refreshAll(); });
  mount();
  caseId = $("#lab-case")?.value ?? caseId;

  if (API) {
    const ctrl = new AbortController(), t = setTimeout(() => ctrl.abort(), 1500);
    fetch(`${API}/health`, { signal: ctrl.signal }).then((r) => r.ok).catch(() => false).then((ok) => { clearTimeout(t); live = ok; refreshAll(); });
  } else refreshAll();
})();
