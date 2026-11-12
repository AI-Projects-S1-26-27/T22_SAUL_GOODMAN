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

  /* ---------------------------------------------------------------- shared helpers for the certified-results chapters */

  const A = window.COURTROOM_ANALYSIS ?? {};
  const STYLE_NAME = { aggressive: "Bold", conservative: "Careful", adaptive: "Smart", reckless: "Wild" };
  const nameOf = (n) => STYLE_NAME[n] ?? (/^best-pro-(\d+)/.test(n) ? `Found Accuser ${n.match(/(\d+)$/)[1]}` : /^best-def-(\d+)/.test(n) ? `Found Defender ${n.match(/(\d+)$/)[1]}` : n);
  const mixText = (mix) => Object.entries(mix ?? {}).sort((x, y) => y[1] - x[1]).map(([k, v]) => (v > 0.995 ? nameOf(k) : `${pct(v)} ${nameOf(k)}`)).join(", ") || "none";
  const num2 = (v) => (Math.abs(v) < 5e-3 ? 0 : v).toFixed(2).replace("-", "−");
  const toggle = (checked, onchange) => h("label", { class: "check small" }, h("input", { type: "checkbox", checked, onchange: (e) => onchange(e.target.checked) }), h("span", {}, " Courtroom surprises on"));
  const LABEL_WORDS = { pure: "one clear best pair of styles", mixed: "no single best style: each lawyer mixes", "dominance-solvable": "one style simply wins for each side", "no-equilibrium-found": "no equilibrium found" };

  /* ---------------------------------------------------------------- chapter: how sure are we? */

  let sureSur = false;
  let sureLive = null;

  function sureCase(id, sur, fresh) {
    const b = fresh ?? A[sur ? "bootstrap_surprises" : "bootstrap"]?.cases?.[id];
    const sens = A[sur ? "sensitivity_surprises" : "sensitivity"];
    return { b, sens };
  }

  function renderSure() {
    const c = B.cases.find((x) => x.id === caseId), body = $("#sure-fig");
    if (!c || !body) return;
    const { b, sens } = sureCase(c.id, sureSur, sureLive?.case_id === c.id && sureLive.surprises === sureSur ? sureLive : null);
    const kids = [toggle(sureSur, (v) => { sureSur = v; sureLive = null; renderSure(); })];
    if (!b) { body.replaceChildren(...kids, note("No resampling result is stored for this case.")); return; }
    const stab = b.stability;
    kids.push(
      h("div", { class: "stab" }, h("div", { class: "stab-label" }, h("b", {}, `Label: ${b.baseline_label}`), ` (${LABEL_WORDS[b.baseline_label] ?? ""})`),
        h("div", { class: "stab-bar", role: "img", "aria-label": `The same label came back in ${pct(stab)} of ${b.n_resamples} resamples` }, h("span", { style: `width:${stab * 100}%` }), h("em", {}, `${(stab * 100).toFixed(1)}%`)),
        h("p", { class: "muted small" }, `In ${(stab * 100).toFixed(1)}% of ${b.n_resamples} resamples of the ${b.n_seeds} seeds, the game came out with the same label. The others: ${Object.entries(b.label_counts).filter(([k]) => k !== b.baseline_label).map(([k, v]) => `${k} ${v}`).join(", ") || "none"}.`)));
    // payoff intervals
    const cells = Object.fromEntries(b.accuser_payoff_intervals.map((x) => [`${x.row}|${x.col}`, x]));
    kids.push(h("h3", {}, "The Accuser's payoff, and how far it could move"),
      h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
        h("thead", {}, h("tr", {}, h("th", {}, ""), ...b.col_strategies.map((d) => h("th", {}, `${nameOf(d)} Defender`)))),
        h("tbody", {}, b.row_strategies.map((r) => h("tr", {}, h("th", { scope: "row" }, `${nameOf(r)} Accuser`), b.col_strategies.map((d) => { const x = cells[`${r}|${d}`]; return h("td", { title: `95% of resamples fall between ${num2(x.low)} and ${num2(x.high)}` }, h("b", {}, num2(x.mean)), h("small", {}, ` (${num2(x.low)} to ${num2(x.high)})`)); })))))),
      note("Each cell is the average over the seeds; the range in brackets holds 95% of the averages when the seeds are resampled."));
    // sensitivity
    if (sens) {
      const base = sens.baseline[c.id];
      const rows = sens.variations.map((v) => { const lab = v.labels[c.id]; return h("tr", { class: lab !== base ? "changed" : null }, h("td", {}, v.parameter.replaceAll("_", " ")), h("td", {}, v.setting), h("td", {}, lab), h("td", {}, pct(v.prosecution_win_rate[c.id]))); });
      const robust = sens.robust_cases.includes(c.id);
      kids.push(h("h3", {}, "If the rulebook's own numbers were different"),
        h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" }, h("thead", {}, h("tr", {}, ["Constant changed", "By", "Label then", "Accuser wins"].map((t) => h("th", {}, t)))), h("tbody", {}, rows))),
        note(`Costs, sanctions, the weight of evidence and the standards of proof were moved by 25% each way (and the "almost certain" bar from 80% to 95%). Highlighted rows changed the label from "${base}". Over the whole library: ${sens.robust_cases.length} case(s) never changed (${sens.robust_cases.join(", ") || "none"}); ${sens.fragile_cases.length} changed under at least one setting.`));
      says("sure", h("p", {}, h("b", {}, caseName(c)), `: the label "${b.baseline_label}" survived ${(stab * 100).toFixed(0)}% of resamples${stab < 0.8 ? ", so treat it as shaky" : ""}. ${robust ? "It also never changed when the rulebook's constants moved by 25%." : `Under the constant changes it changed ${sens.variations.filter((v) => v.labels[c.id] !== base).length} time(s) out of ${sens.variations.length}, so the conclusion depends on the rulebook's numbers.`}${sureSur ? " (With courtroom surprises on.)" : ""}`));
    }
    if (live) {
      const btn = h("button", { class: "btn ghost sm", type: "button" }, "Re-measure with fresh seeds (about 20 seconds)");
      btn.addEventListener("click", async () => {
        btn.disabled = true; btn.textContent = "Resampling…";
        try { sureLive = await post("/bootstrap", { case_id: c.id, seeds: 20, resamples: 200, surprises: sureSur }); sureLive.case_id = c.id; sureLive.surprises = sureSur; renderSure(); } catch { btn.textContent = "Could not run it"; }
      });
      kids.push(h("p", {}, btn, sureLive?.case_id === c.id ? h("span", { class: "muted small" }, " Showing the fresh run (20 seeds) instead of the stored one (100 seeds).") : null));
    }
    body.replaceChildren(...kids);
  }

  registry.push({
    id: "sure",
    build: () => chapter("sure", "How sure are we?", {
      lead: [
        h("p", {}, "Every number in this lab comes from a limited number of trials. Run the trials again with different seeds and each average moves a little, so the conclusion (\"Careful is best\", \"nobody has a best style\") could be an accident of which seeds we happened to use."),
        h("p", {}, "Two checks. First, a ", h("dfn", {}, "bootstrap"), ": we reshuffle the same trials many times, draw new sets of seeds from them, and solve the game again each time. The ", h("dfn", {}, "stability"), " is how often the same conclusion comes back. Second, we change the rulebook's own constants (what an objection costs, how heavily evidence weighs, how sure the judge must be) by 25% either way and see whether the conclusion survives. The constants are fixed by design, but a conclusion that only holds at one setting is not much of a result."),
      ],
      read: ["A stability near 100% means the conclusion does not depend on which seeds were drawn. Below about 80%, treat it as shaky.", "In the payoff table, a wide range means that number is not pinned down.", "Highlighted rows in the last table are settings where the conclusion changed."],
      fig: h("div", { id: "sure-fig" }),
      maths: h("p", {}, "The label is “dominance-solvable” if iterated elimination of strictly dominated strategies leaves one pair, else “pure” if some equilibrium is a single pair, else “mixed”. Each resample draws as many seeds as the original, with replacement, takes the mean payoffs of the drawn seeds and re-solves exactly. The sensitivity run re-estimates the whole library at each setting; it does not change the judge's arithmetic, only the named constants, and restores them afterwards."),
    }),
    refresh: renderSure,
  });

  /* ---------------------------------------------------------------- chapter: can a better lawyer be found? */

  let betterSur = false;
  let betterLive = null;

  function oracleView(r, fresh) {
    const kids = [];
    kids.push(h("p", { class: "headline" }, r.headline));
    kids.push(h("p", { class: "muted small" }, `${fresh ? "A quick live search: " : ""}${r.rounds_run} round(s) of at most ${r.max_rounds}; ${r.budget} candidate profiles tried per side per round; searched on ${r.train_seeds.length} seeds, accepted on ${r.heldout_seeds.length} different ones${r.confirm_seeds?.length ? `, confirmed on ${r.confirm_seeds.length} more` : ""}. ${r.trials} trials, ${r.seconds}s. Stopped: ${r.stopped}.`));
    const kept = r.candidates.filter((c) => c.accepted);
    if (kept.length) {
      kids.push(h("h3", {}, "The better lawyers it found"),
        h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
          h("thead", {}, h("tr", {}, ["Side", "How it plays", "Beats the old equilibrium by", "Confirmed on fresh seeds"].map((t) => h("th", {}, t)))),
          h("tbody", {}, kept.map((c) => h("tr", {}, h("td", {}, c.side === "prosecution" ? "Accuser" : "Defender"), h("td", {}, c.plain), h("td", {}, `${num2(c.difference)} per trial (±${num2(c.standard_error)}, z ${c.z})`), h("td", {}, c.confirmed == null ? "–" : c.confirmed ? `yes (z ${c.confirm_z})` : `no (z ${c.confirm_z})`)))))));
    } else kids.push(h("p", {}, "Every candidate it tried lost to the equilibrium of the four hand-written styles."));
    const dropped = r.candidates.length - kept.length;
    if (dropped) kids.push(note(`${dropped} other candidate profile(s) were the best of their round's search but did not beat the equilibrium by more than 2 standard errors on held-out seeds, so they were dropped.`));
    kids.push(h("h3", {}, "Before and after"),
      h("p", {}, h("b", {}, "Four hand-written styles: "), `Accuser ${mixText(r.start_equilibrium.prosecution_mix)}; Defender ${mixText(r.start_equilibrium.defense_mix)}.`),
      h("p", {}, h("b", {}, "With what was found: "), `Accuser ${mixText(r.final_equilibrium.prosecution_mix)}; Defender ${mixText(r.final_equilibrium.defense_mix)}.`),
      h("p", { class: "muted small" }, ["prosecution", "defense"].map((s) => { const x = r.exploitability[s]; return `${s === "prosecution" ? "Accuser" : "Defender"}: the old equilibrium earned ${num2(x.equilibrium_payoff)}; the best profile found earns ${num2(x.best_found_payoff)} against the same opponent (${x.found_better ? `+${num2(x.gain)}` : "no gain"}). `; }).join("")));
    return kids;
  }

  function renderBetter() {
    const c = B.cases.find((x) => x.id === caseId), body = $("#better-fig");
    if (!c || !body) return;
    const stored = A.oracle?.[`${c.id}${betterSur ? "_surprises" : ""}`];
    const r = betterLive?.case_id === c.id && betterLive.surprises === betterSur ? betterLive : stored;
    const kids = [toggle(betterSur, (v) => { betterSur = v; betterLive = null; renderBetter(); })];
    if (r) kids.push(...oracleView(r, r === betterLive));
    else kids.push(h("p", {}, `The full search was run for the cases where strategy was measured to matter (${Object.keys(A.oracle ?? {}).filter((k) => !k.endsWith("_surprises")).join(", ") || "none stored"}). It has not been run for ${caseName(c)}.`));
    if (live) {
      const btn = h("button", { class: "btn ghost sm", type: "button" }, "Run a quick search now (about 20 seconds)");
      btn.addEventListener("click", async () => {
        btn.disabled = true; btn.textContent = "Searching…";
        try { betterLive = await post("/oracle", { case_id: c.id, budget: 12, rounds: 2, surprises: betterSur }); betterLive.case_id = c.id; betterLive.surprises = betterSur; renderBetter(); } catch { btn.textContent = "Could not run it"; }
      });
      kids.push(h("p", {}, btn, h("span", { class: "muted small" }, " A smaller budget than the stored results, so it may find less.")));
    } else kids.push(needServer("Running a search yourself"));
    const kept = r?.candidates?.filter((x) => x.accepted).length ?? 0;
    says("better", r ? h("p", {}, h("b", {}, caseName(c)), `${betterSur ? " (surprises on)" : ""}: ${kept ? `${kept} better profile(s) found; the styles were not unbeatable.` : "no better profile found within the budget; that is evidence the hand-written styles were hard to beat here, not proof."}`) : h("p", {}, `No stored search for ${caseName(c)}.`));
    // the AI lawyer exhibition
    const ex = A.exhibition;
    kids.push(h("h3", {}, "The AI lawyer against the four styles"),
      ex ? h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
        h("thead", {}, h("tr", {}, ["Case", "AI plays", "Against", "AI wins", "Smart in its seat", "Model fell back"].map((t) => h("th", {}, t)))),
        h("tbody", {}, ex.cells.map((x) => h("tr", {}, h("td", {}, x.case_id), h("td", {}, x.ai_side === "prosecution" ? "Accuser" : "Defender"), h("td", {}, nameOf(x.style)), h("td", {}, pct(x.ai_win_rate)), h("td", {}, pct(x.smart_reference_win_rate)), h("td", {}, pct(x.fallback_rate)))))))
        : h("p", { class: "muted" }, "Not run yet: it needs a language-model backend. Run ", h("code", {}, "python -m courtroom exhibition --json results/exhibition.json"), " with one available."),
      note("Exhibition, not certified. A language model is not one of the hand-written styles, so it cannot be in a payoff table or tested for best responses (see docs/LLM_ROLE.md). “Model fell back” is how often it gave no usable move and the Smart style played instead."));
    body.replaceChildren(...kids);
  }

  registry.push({
    id: "better",
    build: () => chapter("better", "Can a better lawyer be found?", {
      lead: [
        h("p", {}, "The four styles were written by hand. Nothing says they are the best lawyers possible, and the game theory above only compares them with each other. So we ask the harder question: is there a lawyer, outside the four, who beats them?"),
        h("p", {}, "Three of the styles are really just a handful of numbers: how many known problems a lawyer will tolerate in its own evidence, how much a move must help before it is worth a turn, how sure it must be before it objects, and so on. A search tries many settings of those numbers, keeps the one that does best against what the other side is likely to play, and tests it on trials the search never saw. If it wins clearly, it joins the game and the game is solved again, because now the other side has a new thing to answer. This is called a ", h("dfn", {}, "double oracle"), " method."),
      ],
      read: ["“Beats the old equilibrium by” is extra points per trial against the other side's equilibrium play. z says how many standard errors that is; the search keeps a profile only above 2.", "“Confirmed on fresh seeds” re-tests it on a third set of seeds that played no part in finding or accepting it.", "“No better lawyer found” is evidence, not proof: it only covers the family of lawyers the search can express, within its budget."],
      fig: h("div", { id: "better-fig" }),
      maths: h("p", {}, "Each round, for each side: take the other side's equilibrium mix y. Draw random profiles (60% of the budget) then refine the best by coordinate steps (40%), scoring each by its mean payoff against y on the training seeds. Re-score the winner and the current equilibrium mix x on held-out seeds, paired by seed; keep the winner if the mean difference exceeds 2 standard errors. Add what was kept, fill in the new rows and columns, and solve again exactly. Stop when neither side keeps anything, or after 4 rounds. With this many comparisons a lone result just above 2 standard errors is weak evidence on its own, which is why every kept profile is also confirmed on a third set of seeds."),
    }),
    refresh: renderBetter,
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
