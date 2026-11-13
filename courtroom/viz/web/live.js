/* Live controls. These only work when the local server is running (python -m courtroom serve); the hosted site
 * replays recorded trials and says so. Everything here asks the engine, so every number on screen was computed by it:
 *
 *   seed box + "new seed"            run the same lawyers again with a different draw
 *   LIVE / RECORDED badge + digest   "Run it again and compare" proves the trial is reproducible
 *   "Does strategy matter here?"     measured from fresh runs of every pairing of the three styles
 *   Surprise me                      searches generated cases for one where the lawyers move the verdict
 *   courtroom surprises              no-show, missing certificate, hostile witness (off unless ticked)
 *   change the case (what-if)        edit an exhibit or a witness, re-run, watch the verdict move
 *   why this verdict / what flips it the judge's own numbers in plain words, and the smallest change that flips it
 *   spoken lines for unscripted cases built from the exhibit's own text
 *
 * It uses app.js's globals (S, B, C, el, $, $$ ...), so it must load after app.js.
 */
"use strict";

window.Live = (() => {
  /* global API, S, B, C, el, $, $$, selectCase, renderCases, renderStyles, enterCourt, rerun, splitTitle, STYLE, STYLE_ORDER, Voice */
  const post = async (path, body) => {
    const r = await fetch(`${API}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!r.ok) throw new Error(`${path}: ${r.status} ${(await r.text()).slice(0, 200)}`);
    return r.json();
  };
  const randomSeed = () => Math.floor(Math.random() * 99999) + 1;
  const pctText = (x) => `${Math.round(100 * x)}%`;
  const short = (d) => `${d.slice(0, 8)}…${d.slice(-4)}`;
  const clone = (x) => JSON.parse(JSON.stringify(x));
  const surprisesBody = () => (S.surprises ? true : false);

  /* ---------------------------------------------------------------- a custom or found case joins the docket */

  function addCase(c, tag) {
    const copy = clone(c);
    copy.tags = [...new Set([...(copy.tags ?? []).filter((t) => t !== "found" && t !== "custom"), tag])];
    const i = B.cases.findIndex((x) => x.id === copy.id);
    if (i >= 0) B.cases[i] = copy; else B.cases.push(copy);
    $("#found-chip").hidden = false;
    return copy;
  }

  function showFilter(name) {
    S.filter = name;
    $$(".filters .chip").forEach((x) => x.setAttribute("aria-selected", String(x.dataset.filter === name)));
    renderCases();
  }

  /* ---------------------------------------------------------------- "does strategy matter here?" */

  const matters = new Map(); // key -> result (computed fresh from the engine, cached for this page visit)
  const isCustom = (id) => !!caseById(id)?.tags?.includes("custom");
  // an edited or drafted case is not in the server's library, so it is measured by sending its own JSON; its key changes when it does
  const mattersKey = (id) => `${id}|${S.surprises ? "s" : "p"}${isCustom(id) ? `|custom${JSON.stringify(caseById(id)).length}` : ""}`;

  async function getMatters(id) {
    const key = mattersKey(id);
    if (matters.has(key)) return matters.get(key);
    const body = { seeds: 8, surprises: surprisesBody() };
    if (isCustom(id)) body.case = caseById(id); else body.case_id = id;
    const m = await post("/matters", body);
    matters.set(key, m);
    return m;
  }

  const MATTER_TONE = { evidence: "flat", lawyers: "moves", partly_lawyers: "some", seeds: "luck" };

  function decorateDocket() {
    if (!S.live) return;
    for (const card of $$("#cases .folder")) {
      const id = card.dataset.id, cached = matters.get(mattersKey(id));
      let tag = card.querySelector(".matter-tag");
      if (!tag) { tag = el("span", { class: "matter-tag" }, "Measuring…"); card.querySelector(".body").append(tag); }
      if (cached) { tag.textContent = cached.label; tag.className = `matter-tag ${MATTER_TONE[cached.verdict]}`; tag.title = cached.explanation; }
      else getMatters(id).then(() => decorateDocket()).catch(() => { tag.textContent = ""; });
    }
  }

  async function renderMatters() {
    const box = $("#matters-box");
    if (!box || !S.caseId) return;
    box.replaceChildren(el("b", {}, "Does strategy matter here?"), el("p", { class: "muted" }, "Measuring from fresh runs of every pairing…"));
    const id = S.caseId;
    try {
      const m = await getMatters(id);
      if (id !== S.caseId) return;
      const head = ["", ...m.styles.map((x) => `${STYLE[x].label} Defender`)];
      const rows = m.styles.map((x, i) => [`${STYLE[x].label} Accuser`, ...m.win_rate[i].map(pctText)]);
      box.replaceChildren(
        el("b", {}, "Does strategy matter here? ", el("span", { class: `matter-tag ${MATTER_TONE[m.verdict]}` }, m.label)),
        el("p", {}, m.explanation),
        el("table", { class: "mini" }, el("thead", {}, el("tr", {}, ...head.map((h) => el("th", {}, h)))), el("tbody", {}, ...rows.map((r) => el("tr", {}, ...r.map((c, k) => el(k ? "td" : "th", {}, c)))))),
        el("p", { class: "muted small" }, `Accuser win rate over ${m.seeds.length} seeds for each of the 9 pairings (${m.trials} fresh trials)${m.surprises ? ", with courtroom surprises on" : ""}. Best pairing minus worst: ${pctText(m.pairing_spread)}. Seed-to-seed coin flip: ${pctText(m.seed_noise)}.`),
      );
    } catch (e) { box.replaceChildren(el("b", {}, "Does strategy matter here?"), el("p", { class: "muted" }, "Could not measure this case.")); }
  }

  /* ---------------------------------------------------------------- the panel in "Brief your lawyers" */

  function buildPanel() {
    const box = $("#live-panel");
    if (!S.live) {
      box.replaceChildren(el("p", { class: "muted" }, el("b", { class: "pill rec" }, "RECORDED"), " This page is replaying trials that were run earlier. To pick a seed, switch on courtroom surprises, edit a case or search for contested ones, run the local server: ", el("code", {}, "python -m courtroom serve")));
      return;
    }
    const seed = el("input", { id: "live-seed", type: "number", min: "0", max: "2147483647", value: String(S.seed), "aria-label": "Seed" });
    seed.addEventListener("change", () => { S.seed = Math.max(0, Math.floor(+seed.value || 0)); seed.value = S.seed; });
    const newSeed = el("button", { class: "tbtn", type: "button", onclick: () => { S.seed = randomSeed(); seed.value = S.seed; } }, "New seed");
    const sur = el("input", { type: "checkbox", id: "live-surprises" });
    sur.checked = S.surprises;
    sur.addEventListener("change", () => { S.surprises = sur.checked; renderMatters(); decorateDocket(); });
    box.replaceChildren(
      el("div", { class: "live-head" }, el("b", { class: "pill live" }, "LIVE"), el("span", {}, "The local server is on. Every trial is computed now, not replayed.")),
      el("div", { class: "live-grid" },
        el("div", { class: "live-cell" }, el("label", { for: "live-seed" }, "Seed"), el("div", { class: "row" }, seed, newSeed), el("p", { class: "muted small" }, "Same seed, same trial, every time. A new seed changes the lawyers' perception, and the surprises if they are on.")),
        el("div", { class: "live-cell" }, el("label", { class: "check", for: "live-surprises" }, sur, el("span", {}, el("b", {}, "Courtroom surprises"), " a witness may not turn up, a digital record may have no certificate, a witness may turn hostile.")), el("p", { class: "muted small" }, "Off by default. This is what lets the seed change the verdict.")),
        el("div", { class: "live-cell wide", id: "matters-box" }),
        el("div", { class: "live-cell wide actions" },
          el("button", { class: "btn ghost", type: "button", id: "edit-case", onclick: () => openEditor() }, "Change this case…"),
          el("button", { class: "btn ghost", type: "button", id: "blank-case", onclick: () => openEditor(blankCase(), "A blank case. Fill it in by hand: every number is yours.") }, "Write a case yourself…")),
        el("div", { class: "live-cell wide", id: "ai-box", hidden: true }),
      ),
    );
    renderMatters();
  }

  /* ---------------------------------------------------------------- badge in the courtroom */

  function trialLoaded() {
    const box = $("#live-badge");
    const t = S.trial, live = S.source === "live";
    const parts = [el("span", { class: `pill ${live ? "live" : "rec"}` }, live ? "LIVE" : "RECORDED")];
    const when = live ? `computed just now (${S.computedAt.toLocaleTimeString()}), seed ${t.seed}` : `replayed from a saved file, seed ${t.seed}`;
    parts.push(el("span", { class: "when" }, when));
    if (t.surprises) parts.push(el("span", { class: "pill sur" }, "SURPRISES ON"));
    if (S.inline?.id === S.caseId) parts.push(el("span", { class: "pill edit" }, "EDITED CASE"));
    if (S.llmNote) parts.push(el("span", { class: "pill ai" }, S.llmNote));
    if (t.certified === false) parts.push(el("span", { class: "pill ai", title: "A language model played, so this trial is an exhibition and never part of the certified analysis." }, "AI LAWYER · NOT CERTIFIED"));
    parts.push(el("code", { class: "digest", title: t.digest }, `digest ${short(t.digest)}`));
    if (live) {
      parts.push(el("button", { class: "tbtn small", type: "button", onclick: verify }, "Run it again and compare"));
      parts.push(el("button", { class: "tbtn small", type: "button", onclick: () => { S.seed = randomSeed(); const i = $("#live-seed"); if (i) i.value = S.seed; rerun(); } }, "New seed"));
    }
    box.replaceChildren(el("div", { class: "badge-row" }, ...parts), el("p", { class: "verify-out", id: "verify-out", role: "status" }));

    if (!live) box.querySelector(".verify-out").textContent = "Run the local server to recompute this trial and compare.";
  }

  async function verify() {
    const out = $("#verify-out");
    out.textContent = "Running it twice…";
    try {
      const r = await post("/verify", S.request);
      const same = r.digest_first === r.digest_second && r.digest_first === S.trial.digest;
      out.replaceChildren(
        el("span", {}, `Run 1: ${short(r.digest_first)}  ·  Run 2: ${short(r.digest_second)}  ·  `),
        el("b", { class: r.identical && same ? "ok" : "no" }, r.identical && same ? "identical, and the same as the trial on screen" : "NOT identical"),
        el("span", {}, `  ·  hash chain over ${r.events} events: `), el("b", { class: r.chain_valid ? "ok" : "no" }, r.chain_valid ? "valid" : "BROKEN"),
      );
    } catch (e) { out.textContent = "Could not reach the server."; }
  }

  /* ---------------------------------------------------------------- the verdict card: why, and what would flip it */

  function applyChange(tip) {
    const c = clone(C());
    if (tip.kind === "exhibit") c.evidence.find((e) => e.id === tip.target).reliability = tip.to_value;
    else c.witnesses.find((w) => w.id === tip.target).credibility = tip.to_value;
    useEdited(c, `${tip.field} of ${tip.name}: ${tip.from_value} → ${tip.to_value}`);
    rerun();
  }

  function useEdited(c, note) {
    const base = c.id.replace(/-edited$/, "");
    c.id = `${base}-edited`;
    if (!/\(edited\)$/.test(c.title)) c.title = `${c.title} (edited)`;
    c.tags = ["custom"];
    S.inline = addCase(c, "custom");
    S.caseId = c.id;
    S.llmNote = null;
    S.editNote = note;
  }

  async function verdictShown() {
    const box = $("#verdict-extra");
    if (S.source !== "live") { box.replaceChildren(el("p", { class: "muted small" }, "Recorded trial. Run the local server to see why it ended this way and what would flip it.")); return; }
    box.replaceChildren(el("p", { class: "muted small" }, "Working out why…"));
    try {
      const r = await post("/explain", { ...S.request, words: !!S.ai?.available });
      if (r.digest !== S.trial.digest) return;
      const tips = r.tipping.slice(0, 3);
      box.replaceChildren(
        ...(S.trial.ai ? [el("p", { class: "ai-line" }, el("b", {}, "AI lawyer, not certified. "), aiSummary(S.trial.ai))] : []),
        el("details", { class: "why" }, el("summary", {}, "Why this verdict?"), el("p", {}, r.text), el("p", { class: "muted small" }, r.text_source === "model" ? "Worded by the model, then checked: every number and exhibit in it is one the judge produced." : "Written straight from the judge's own numbers.")),
        el("div", { class: "flip" },
          el("b", {}, "What would flip it?"),
          tips.length
            ? el("ul", {}, ...tips.map((t) => el("li", {}, el("span", {}, t.sentence), el("button", { class: "tbtn small", type: "button", onclick: () => applyChange(t) }, "Try it"))))
            : el("p", { class: "muted small" }, "No change to one exhibit or one witness alone would flip this verdict."),
          tips.length ? el("p", { class: "muted small" }, "Found by re-scoring the same record with the judge's own rules. “Try it” plays the whole trial again with that change; the lawyers may play differently.") : null),
      );
    } catch (e) { box.replaceChildren(); }
  }

  /* ---------------------------------------------------------------- the case editor (what-if, drafted cases, blank form) */

  const FLAGS = [
    ["hearsay", "It's a rumour"],
    ["authenticated", "Proven real"],
    ["lawfully_obtained", "Collected legally"],
    ["disclosed", "Shown to the other side beforehand"],
    ["personal_knowledge", "Witness saw it themself"],
  ];
  const KINDS = [["document", "Document"], ["digital_log", "Digital record"], ["physical", "Physical evidence"], ["financial_record", "Money record"], ["testimony", "Witness"], ["expert", "Expert opinion"]];
  const STANDARDS = [["beyond_reasonable_doubt", "Almost certain (about 90%)"], ["clear_and_convincing", "Fairly sure (about 75%)"], ["preponderance", "More likely than not"]];
  const MAX_ITEMS = 12, MAX_WITNESSES = 6, MAX_POINTS = 4;

  let draft = null; // the case being edited
  let origin = null; // the case it started from (the "before" in a comparison)

  const blankCase = () => ({
    id: "my-case", title: "Me v. You — My Own Case", synopsis: "Describe what happened in a sentence or two.", case_type: "civil", standard: "preponderance",
    charge: "The Accuser says the other side did something wrong.",
    elements: [{ id: "wrongdoing", name: "Wrongdoing", description: "The other side did it." }],
    witnesses: [],
    evidence: [
      { id: "P-ONE", title: "The Accuser's evidence", description: "What it shows.", kind: "document", owner: "prosecution", fact_id: "f1", support: { wrongdoing: 0.8 }, reliability: 0.85 },
      { id: "D-ONE", title: "The Defender's evidence", description: "What it shows.", kind: "document", owner: "defense", fact_id: "f2", support: { wrongdoing: -0.7 }, reliability: 0.8 },
    ],
    budget: 10, max_primary_turns: 8, rebuttal_turns: 2, perception_accuracy: 0.8, tags: ["custom"],
  });

  function outcomeLine(t) {
    const s = t.verdict.snapshot;
    const weakest = s.elements.find((e) => e.element_id === s.weakest_element);
    return { word: t.verdict.outcome.replaceAll("_", " "), wins: ["guilty", "liable"].includes(t.verdict.outcome), burden: s.burden_index, lo: weakest?.log_odds_float };
  }

  function openEditor(startFrom, note) {
    origin = clone(startFrom ?? C());
    origin.evidence.forEach((e) => { e.support ??= {}; });
    draft = clone(origin);
    S.draftNote = note ?? null;
    renderEditor();
    $("#editor").hidden = false;
    document.body.style.overflow = "hidden";
    $("#editor").querySelector("input,select")?.focus();
  }
  function closeEditor() { $("#editor").hidden = true; if ($("#court").hidden) document.body.style.overflow = ""; }

  const round2 = (v, lo = 0, hi = 1) => Math.min(hi, Math.max(lo, Math.round((+v || 0) * 100) / 100));
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

  function field(obj, key, { type = "text", min, max, step, width, label, onchange } = {}) {
    const attrs = { type, value: String(obj[key] ?? ""), "aria-label": label ?? key };
    if (min != null) attrs.min = String(min);
    if (max != null) attrs.max = String(max);
    if (step != null) attrs.step = String(step);
    if (width) attrs.style = `width:${width}`;
    const i = el("input", attrs);
    i.addEventListener("change", () => {
      obj[key] = type === "number" ? round2(i.value, +(min ?? -1), +(max ?? 1)) : i.value;
      if (type === "number") i.value = obj[key];
      onchange?.();
    });
    return i;
  }
  const select = (obj, key, options, label, onchange) => {
    const s = el("select", { "aria-label": label }, ...options.map(([v, l]) => el("option", { value: v, selected: obj[key] === v }, l)));
    s.addEventListener("change", () => { obj[key] = s.value; onchange?.(); });
    return s;
  };

  function renderEditor() {
    const box = $("#editor");
    const rerender = () => renderEditor();
    const elementIds = () => draft.elements.map((e) => e.id);

    const std = select(draft, "standard", STANDARDS, "How sure the judge must be");
    const type = select(draft, "case_type", [["criminal", "Criminal (someone is accused)"], ["civil", "Civil (someone must pay)"]], "Kind of case", () => {
      if (draft.case_type === "civil") draft.standard = "preponderance";
      else if (draft.standard === "preponderance") draft.standard = "beyond_reasonable_doubt";
      rerender();
    });

    const pointRows = draft.elements.map((p, i) => el("tr", {},
      el("td", {}, field(p, "name", { label: "Point to prove", width: "14em" })),
      el("td", {}, field(p, "description", { label: "In a sentence", width: "100%" })),
      el("td", {}, draft.elements.length > 1 ? el("button", { class: "tbtn small", type: "button", onclick: () => { const gone = p.id; draft.elements.splice(i, 1); draft.evidence.forEach((e) => delete e.support[gone]); rerender(); } }, "Remove") : null)));

    const witnessOptions = () => [["", "—"], ...draft.witnesses.map((w) => [w.id, w.name])];
    const evRows = draft.evidence.map((e, i) => {
      const o = origin.evidence.find((x) => x.id === e.id);
      const row = el("tr", { class: e.owner === "prosecution" ? "p" : "d" });
      const upd = () => row.classList.toggle("changed", !same(e, o));
      const supports = elementIds().map((id, k) => el("label", { class: "supp", title: draft.elements[k].name }, el("small", {}, draft.elements[k].name.slice(0, 14)), field(e.support, id, { type: "number", min: -1, max: 1, step: 0.05, width: "5.5em", label: `${e.title} bears on ${draft.elements[k].name}`, onchange: upd })));
      e.support = Object.fromEntries(elementIds().map((id) => [id, e.support[id] ?? 0]));
      row.append(
        el("td", {}, field(e, "title", { label: "Exhibit title", width: "100%", onchange: upd }), el("div", { class: "pair" }, select(e, "owner", [["prosecution", "Accuser's"], ["defense", "Defender's"]], "Whose exhibit", () => { upd(); rerender(); }), select(e, "kind", KINDS, "Kind", () => { upd(); rerender(); }),
          e.kind === "testimony" || e.kind === "expert" ? select(e, "witness_id", witnessOptions(), "Witness", upd) : null)),
        el("td", {}, field(e, "reliability", { type: "number", min: 0, max: 1, step: 0.01, label: `Reliability of ${e.title}`, onchange: upd })),
        el("td", { class: "supports" }, ...supports),
        el("td", { class: "flags" }, ...FLAGS.filter(([k]) => k in e || ["hearsay", "authenticated", "lawfully_obtained", "disclosed"].includes(k)).filter(([k]) => k !== "personal_knowledge" || e.kind === "testimony").map(([k, label]) => {
          const cb = el("input", { type: "checkbox" });
          cb.checked = k in e ? !!e[k] : k !== "hearsay";
          cb.addEventListener("change", () => { e[k] = cb.checked; upd(); });
          return el("label", { class: "check small" }, cb, el("span", {}, label));
        })),
        el("td", {}, el("button", { class: "tbtn small", type: "button", onclick: () => { draft.evidence.splice(i, 1); rerender(); } }, "Remove")));
      upd();
      return row;
    });

    const wRows = draft.witnesses.map((w, i) => {
      const o = origin.witnesses.find((x) => x.id === w.id);
      const row = el("tr", {});
      const upd = () => row.classList.toggle("changed", !same(w, o));
      row.append(el("td", {}, field(w, "name", { label: "Witness name", onchange: upd })), el("td", {}, field(w, "role", { label: "Role", onchange: upd })),
        el("td", {}, field(w, "credibility", { type: "number", min: 0, max: 1, step: 0.01, label: `Credibility of ${w.name}`, onchange: upd })),
        el("td", {}, el("button", { class: "tbtn small", type: "button", onclick: () => { const gone = w.id; draft.witnesses.splice(i, 1); draft.evidence.forEach((e) => { if (e.witness_id === gone) e.witness_id = null; }); rerender(); } }, "Remove")));
      upd();
      return row;
    });

    const nextId = (prefix, list) => { let n = list.length + 1; while (list.some((x) => x.id === `${prefix}${n}`)) n++; return `${prefix}${n}`; };
    const budget = field(draft, "budget", { type: "number", min: 1, max: 50, step: 0.5, label: "Budget for each lawyer" });
    budget.addEventListener("change", () => { draft.budget = Math.min(50, Math.max(1, +budget.value || 10)); budget.value = draft.budget; });

    box.replaceChildren(el("div", { class: "editor-card" },
      el("div", { class: "editor-bar" }, el("h2", { id: "editor-title" }, "Change the case"), el("button", { class: "tbtn", type: "button", onclick: closeEditor }, "Close")),
      S.draftNote ? el("p", { class: "draft-note" }, S.draftNote) : null,
      el("p", { class: "muted" }, "Change a number or a word, then run it. The judge scores the new version with the same fixed rules, so you can see exactly what moves the verdict. Changed rows are highlighted."),
      el("div", { class: "ed-top" }, el("label", {}, "Title ", field(draft, "title", { label: "Title", width: "22em" })), el("label", {}, "Kind ", type), el("label", {}, "The judge must be ", std), el("label", {}, "Budget for each lawyer ", budget)),
      el("div", { class: "ed-top" }, el("label", {}, "What the Accuser claims ", field(draft, "charge", { label: "Charge", width: "34em" }))),
      el("h3", {}, "What the Accuser must prove"),
      el("div", { class: "ed-scroll" }, el("table", { class: "ed" }, el("tbody", {}, ...pointRows))),
      draft.elements.length < MAX_POINTS ? el("button", { class: "tbtn small", type: "button", onclick: () => { const id = nextId("point_", draft.elements); draft.elements.push({ id, name: "Another point", description: "Something else the Accuser must show." }); draft.evidence.forEach((e) => { e.support[id] = 0; }); rerender(); } }, "Add a point") : null,
      el("h3", {}, "Evidence"),
      el("p", { class: "muted small" }, "Reliability: 0 means worthless, 1 means rock solid. “Bears on” says which point each exhibit helps: up to +1 helps the Accuser, down to −1 helps the Defender."),
      el("div", { class: "ed-scroll" }, el("table", { class: "ed" }, el("thead", {}, el("tr", {}, ["Exhibit", "Reliability", "Bears on", "About it", ""].map((t) => el("th", {}, t)))), el("tbody", {}, ...evRows))),
      draft.evidence.length < MAX_ITEMS ? el("button", { class: "tbtn small", type: "button", onclick: () => { draft.evidence.push({ id: nextId("X-", draft.evidence), title: "New exhibit", description: "What it shows.", kind: "document", owner: "prosecution", fact_id: nextId("f", draft.evidence), support: Object.fromEntries(elementIds().map((id) => [id, 0])), reliability: 0.8 }); rerender(); } }, "Add an exhibit") : null,
      el("h3", {}, "Witnesses"),
      wRows.length ? el("div", { class: "ed-scroll" }, el("table", { class: "ed" }, el("thead", {}, el("tr", {}, ["Name", "Role", "Credibility (how much the judge believes them)", ""].map((t) => el("th", {}, t)))), el("tbody", {}, ...wRows))) : el("p", { class: "muted small" }, "No witnesses yet. Add one, then set an exhibit's kind to Witness and choose them."),
      draft.witnesses.length < MAX_WITNESSES ? el("button", { class: "tbtn small", type: "button", onclick: () => { draft.witnesses.push({ id: nextId("W-", draft.witnesses), name: "New Witness", role: "bystander", credibility: 0.8, bias_note: null }); rerender(); } }, "Add a witness") : null,
      el("div", { class: "ed-actions" },
        el("button", { class: "btn ghost", type: "button", onclick: () => { draft = clone(origin); renderEditor(); } }, "Reset"),
        el("button", { class: "btn ghost", type: "button", onclick: tryDraft }, "Run it here"),
        el("button", { class: "btn primary", type: "button", onclick: watchDraft }, "Watch it in the courtroom")),
      el("div", { class: "ed-result", id: "ed-result", "aria-live": "polite" }),
    ));
  }

  function draftCase() {
    const c = clone(draft);
    const base = (origin.id || "my-case").replace(/-edited$/, "");
    c.id = /^draft-/.test(base) || base === "my-case" ? base : `${base}-edited`;
    if (c.id !== base && !/\(edited\)$/.test(c.title)) c.title = `${c.title} (edited)`;
    for (const e of c.evidence) {
      e.support = Object.fromEntries(Object.entries(e.support).filter(([k, v]) => c.elements.some((p) => p.id === k) && v !== 0));
      if (!Object.keys(e.support).length && c.elements.length) e.support = { [c.elements[0].id]: 0.05 };
      if (e.kind !== "testimony" && e.kind !== "expert") e.witness_id = null;
      else e.witness_id ||= null;
      if (!e.witness_id) delete e.witness_id;
    }
    c.witnesses.forEach((w) => { w.bias_note ??= null; });
    return c;
  }

  const tryBody = (c) => ({ case: c, prosecution: S.p, defense: S.d, seed: S.seed, surprises: surprisesBody() });
  const problemText = (e) => String(e.message).replace(/^\/\w+: /, "").slice(0, 400);

  async function tryDraft() {
    const out = $("#ed-result");
    out.textContent = "Running both versions…";
    try {
      const [a, b] = await Promise.all([post("/trial", tryBody(origin)), post("/trial", tryBody(draftCase()))]);
      const x = outcomeLine(a), y = outcomeLine(b);
      const flipped = x.wins !== y.wins;
      const row = (k, p, q) => el("tr", {}, el("th", {}, k), el("td", {}, p), el("td", {}, q));
      out.replaceChildren(
        el("table", { class: "mini" }, el("thead", {}, el("tr", {}, el("th", {}), el("th", {}, "Before"), el("th", {}, "After"))),
          el("tbody", {}, row("Verdict", x.word, y.word), row("Weakest point", `${pctText(x.burden)} sure`, `${pctText(y.burden)} sure`), row("Log-odds of it", String(x.lo?.toFixed(2)), String(y.lo?.toFixed(2))))),
        el("p", { class: flipped ? "flip-note" : "muted" }, flipped ? `The verdict flipped to the ${y.wins ? "Accuser" : "Defender"}.` : "Same verdict, but look at how sure the judge is."),
      );
    } catch (e) { out.replaceChildren(el("p", { class: "no" }, "The server did not accept this case: ", problemText(e))); }
  }

  async function watchDraft() {
    const c = draftCase(), out = $("#ed-result");
    try { await post("/trial", tryBody(c)); } catch (e) { out.replaceChildren(el("p", { class: "no" }, "The server did not accept this case: ", problemText(e))); return; }
    const changes = [];
    for (const e of draft.evidence) { const o = origin.evidence.find((x) => x.id === e.id); if (!same(e, o)) changes.push(e.title); }
    for (const w of draft.witnesses) { const o = origin.witnesses.find((x) => x.id === w.id); if (!same(w, o)) changes.push(w.name); }
    S.inline = addCase(c, "custom");
    S.caseId = c.id;
    S.editNote = changes.length ? `Changed: ${changes.join(", ")}` : "No changes";
    S.llmNote = S.draftNote ? "DRAFTED BY AI" : null;
    closeEditor();
    showFilter("found");
    selectCase(c.id);
    if (!$("#court").hidden) rerun(); else enterCourt();
  }

  /* ---------------------------------------------------------------- Surprise me: search for contested cases */

  let searchStart = Math.floor(Math.random() * 40) * 60; // a different slice of generated cases each visit

  async function surprise() {
    const note = $("#surprise-note"), btn = $("#surprise-me");
    Voice.unlock(); window.Sound?.unlock();
    btn.disabled = true;
    note.textContent = "Searching generated cases for a contested one (this takes up to about 25 seconds)…";
    try {
      const r = await post("/find", { start: searchStart, count: 40, top: 5, surprises: surprisesBody() });
      searchStart += 40;
      if (!r.found.length) { note.textContent = "Nothing contested in that slice. Press again to search the next one."; return; }
      note.textContent = `${r.note} Took ${r.seconds}s.`;
      renderFound(r);
      await playFound(r.found[0]);
    } catch (e) { note.textContent = "The search could not run. Is the local server on?"; } finally { btn.disabled = false; }
  }

  async function playFound(f) {
    const c = await (await fetch(`${API}/cases/${f.case_id}`)).json();
    addCase(c, "found");
    S.found = { ...(S.found ?? {}), [f.case_id]: f };
    S.inline = null;
    // the pairing where the Accuser's win rate is closest to a toss-up is where the lawyers' choice bites hardest
    const m = f.mattering;
    let best = [0, 0], gap = 9;
    m.win_rate.forEach((row, i) => row.forEach((w, j) => { if (Math.abs(w - 0.5) < gap) { gap = Math.abs(w - 0.5); best = [i, j]; } }));
    S.p = m.styles[best[0]]; S.d = m.styles[best[1]];
    matters.set(mattersKey(c.id), m);
    showFilter("found");
    selectCase(c.id);
    enterCourt();
  }

  function renderFound(r) {
    const box = $("#found-panel");
    box.hidden = false;
    box.replaceChildren(
      el("h3", {}, "Found by search"),
      el("p", { class: "muted" }, r.note + " Nobody wrote these cases."),
      el("ul", {}, ...r.found.map((f) => el("li", {},
        el("div", {}, el("b", {}, f.case_id), " ", el("span", { class: `matter-tag ${MATTER_TONE[f.mattering.verdict]}` }, f.mattering.label),
          el("small", {}, ` lawyers move the Accuser's win rate by ${pctText(f.mattering.pairing_spread)}; seed noise ${pctText(f.mattering.seed_noise)}${f.no_dominant_strategy === true ? "; no dominant strategy (" + f.equilibrium_kind + " equilibrium)" : f.no_dominant_strategy === false ? "; one style simply wins (" + f.equilibrium_kind + ")" : ""}`)),
        el("button", { class: "tbtn small", type: "button", onclick: () => playFound(f) }, "Play it")))),
    );
  }

  /* ---------------------------------------------------------------- spoken lines for unscripted cases */

  const KIND_WORD = { document: "document", digital_log: "digital record", physical: "object", financial_record: "money record", testimony: "witness statement", expert: "expert opinion" };
  const plain = (t) => String(t ?? "").replace(/\s+/g, " ").trim();
  // generated cases carry placeholder descriptions; speaking those aloud would only be noise
  const usable = (t) => !!plain(t) && !/procedurally generated|^synthetic/i.test(plain(t));
  const firstSentence = (t) => (plain(t).match(/^.*?[.!?](\s|$)/)?.[0] ?? plain(t)).trim();

  function ensureStory(c) {
    window.STORY ??= {};
    if (window.STORY[c.id]) return;
    const base = c.id.replace(/-edited$/, "");
    if (window.STORY[base]) { window.STORY[c.id] = window.STORY[base]; return; }
    const ev = {};
    for (const it of c.evidence) {
      const who = it.owner === "prosecution" ? "The Accuser" : "The Defender";
      const w = it.witness_id ? c.witnesses.find((x) => x.id === it.witness_id) : null;
      if (w) {
        ev[it.id] = {
          short: `${w.name}'s account`,
          say: `${who} calls ${w.name}, ${w.role}. ${w.name}, please tell the court what you know.`,
          witness: `${w.name}, ${w.role}`,
          wit: usable(it.description) ? plain(it.description) : `I can tell the court what I know about this: ${plain(it.title)}.`,
        };
      } else {
        const kind = KIND_WORD[it.kind] ?? "exhibit";
        ev[it.id] = { short: `the ${kind}`, say: `Your Honour, I'd like to show the court this ${kind}: ${plain(it.title)}. ${usable(it.description) ? firstSentence(it.description) : ""}`.trim() };
      }
    }
    const points = Object.fromEntries(c.elements.map((e) => [e.id, plain(e.description || e.name).replace(/\.$/, "")]));
    window.STORY[c.id] = {
      points,
      open: {
        prosecution: `Your Honour, we will show that ${lowerCase(plain(c.charge || c.synopsis))}.`,
        defense: `Your Honour, the evidence does not prove it. We ask the court to weigh it carefully.`,
      },
      close: {
        prosecution: `Your Honour, the evidence we showed proves each point. We ask for a finding for the Accuser.`,
        defense: `Your Honour, the Accuser has not proved every point. There is real doubt here.`,
      },
      ev,
      generic: true,
    };
    wordWithModel(c);
  }
  const lowerCase = (t) => (/^[A-Z][a-z]/.test(t) ? t[0].toLowerCase() + t.slice(1) : t);

  /* ---------------------------------------------------------------- the language model (optional) */

  function aiSummary(ai) {
    const bits = Object.entries(ai.sides).map(([side, r]) => {
      const who = side === "prosecution" ? "AI Accuser" : "AI Defender";
      return `${who}: the model chose ${r.model_choices} of ${r.choices} real decisions; ${r.fallbacks} fell back to the Smart style (${pctText(r.fallback_rate)})${r.model ? `, model ${r.model}` : ""}.`;
    });
    return bits.join(" ");
  }

  /* the lawyer's thinking: shown on screen, never spoken, never presented as a fact about the case */
  function thinking(ev) {
    const box = $("#thinking");
    if (!box) return;
    const r = ev?.action?.rationale ?? "";
    const side = ev?.actor;
    const isAi = side && S.trial && ["prosecution_strategy", "defense_strategy"].some((k) => S.trial[k] === "llm" && (side === "prosecution") === (k === "prosecution_strategy"));
    if (isAi && r.startsWith("[ai] ")) {
      box.textContent = `The AI lawyer's thinking: ${r.slice(5)}`;
      box.className = `thinking ${side === "prosecution" ? "p" : "d"}`;
      box.hidden = false;
    } else if (isAi && r.startsWith("[fallback")) {
      box.textContent = "The AI lawyer's model did not give a usable answer, so the Smart style made this move.";
      box.className = "thinking fb";
      box.hidden = false;
    } else box.hidden = true;
  }

  async function loadAI() {
    try {
      S.ai = await (await fetch(`${API}/ai`)).json();
    } catch { S.ai = { available: false }; }
    const box = $("#ai-box");
    if (!box || !S.ai.available) return;
    if (!STYLE.llm) { STYLE.llm = { label: "AI lawyer", blurb: "A language model picks each move from the legal ones and says why. An exhibition: never certified." }; STYLE_ORDER.push("llm"); renderStyles(); }
    const text = el("textarea", { id: "ai-text", rows: "3", maxlength: "1500", placeholder: "e.g. My neighbour borrowed my drone and returned it with a cracked frame. He says it was already cracked. A friend saw him crash it.", "aria-label": "Describe a case in plain English" });
    const out = el("p", { class: "muted small", id: "ai-out", role: "status" });
    const go = el("button", { class: "btn ghost", type: "button", id: "ai-draft" }, "Draft it with AI");
    go.addEventListener("click", async () => {
      if (text.value.trim().length < 10) { out.textContent = "Write a sentence or two first."; return; }
      go.disabled = true; out.textContent = "The model is drafting a case file and checking it against the rules…";
      try {
        const r = await post("/case/draft", { text: text.value });
        out.textContent = r.repairs ? `Drafted after ${r.repairs} correction${r.repairs > 1 ? "s" : ""} (${r.model ?? r.backend}).` : `Drafted (${r.model ?? r.backend}).`;
        openEditor(r.case, r.notes.join(" "));
      } catch (e) { out.textContent = `The model could not draft a valid case: ${problemText(e)} You can write one yourself with "Write a case yourself".`; } finally { go.disabled = false; }
    });
    box.hidden = false;
    box.replaceChildren(el("label", { for: "ai-text" }, el("b", {}, "Describe a case in plain English"), el("span", { class: "pill ai" }, `AI · ${S.ai.model ?? S.ai.backend}`)), text,
      el("div", { class: "row" }, go), out,
      el("p", { class: "muted small" }, "The model writes a case file; the same checks every case passes validate it. It opens in the editor so you can see and change every number. The model proposed them. The judge, as always, is the fixed rulebook."));
  }

  /* model-worded lines for a case with no script, applied as they arrive; lines that add a fact are refused by the server */
  async function wordWithModel(c) {
    if (!S.ai?.available || !S.live) return;
    const body = /^gen-\d+$/.test(c.id) ? { case_id: c.id } : { case: S.inline?.id === c.id ? S.inline : c };
    try {
      const r = await post("/narrate", body);
      const story = window.STORY[c.id];
      if (!story || !story.generic) return;
      for (const [id, line] of Object.entries(r.ev)) story.ev[id] = { ...story.ev[id], ...line };
      story.worded = { model: r.model, lines: Object.keys(r.ev).length, refused: Object.keys(r.refused).length };
    } catch { /* the generic lines stay */ }
  }

  /* ---------------------------------------------------------------- start-up */

  function caseSelected(id) {
    if (S.inline && S.inline.id !== id) S.inline = null;
    if (S.live) renderMatters();
  }

  /* An exhibition style that is not one of the four certified ones: selectable only with the local server (it has no recorded trials). */
  function addLookahead() {
    if (STYLE.lookahead) return;
    STYLE.lookahead = { label: "Lookahead", blurb: "Thinks a few moves ahead with alpha-beta and fears the worst reply. An exhibition style: not one of the four certified ones." };
    STYLE_ORDER.push("lookahead");
    renderStyles();
  }

  function ready() {
    addLookahead();
    $("#surprise-row").hidden = false;
    $("#surprise-me").addEventListener("click", surprise);
    $("#editor").addEventListener("click", (e) => { if (e.target.id === "editor") closeEditor(); });
    addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#editor").hidden) { e.stopPropagation(); closeEditor(); } }, true);
    buildPanel();
    decorateDocket();
    loadAI();
  }

  // The panel exists on the hosted site too, as a plain note that explains what the local server adds.
  document.addEventListener("DOMContentLoaded", () => { if (!S.live) buildPanel(); });
  if (document.readyState !== "loading") buildPanel();

  return { ready, trialLoaded, verdictShown, decorateDocket, caseSelected, ensureStory, openEditor, addCase, showFilter, post, useEdited, thinking };
})();
