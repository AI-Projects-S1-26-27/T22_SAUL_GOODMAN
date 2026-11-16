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
    if (!mattersCache.has(key)) mattersCache.set(key, await post("/matters", { case_id: id, seeds: 8, surprises }));
    return mattersCache.get(key);
  };
  const TONE = { evidence: "flat", lawyers: "moves", partly_lawyers: "some", seeds: "luck" };

  async function renderMatters() {
    const c = B.cases.find((x) => x.id === caseId), body = $("#matters-fig");
    if (!c || !body) return;
    const stored = (sur) => (window.COURTROOM_ANALYSIS ?? {})[sur ? "matters_surprises" : "matters"]?.cases;
    const row = (k, m) => h("tr", { class: k.id === caseId ? "current" : null },
      h("th", { scope: "row" }, caseName(k)), h("td", {}, h("span", { class: `matter-tag ${TONE[m.verdict]}` }, m.label)),
      h("td", {}, pct(m.pairing_spread)), h("td", {}, pct(m.seed_noise)), h("td", {}, pct(m.overall_win_rate)));
    const sw = h("label", { class: "check small" }, h("input", { type: "checkbox", checked: surprises, onchange: (e) => { surprises = e.target.checked; renderMatters(); } }), h("span", {}, " Courtroom surprises on (a witness may not appear, a record may lack its certificate, a witness may turn hostile)"));
    const table = (rows, caption) => [sw, h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
      h("thead", {}, h("tr", {}, ["Case", "Verdict", "Lawyers move it by", "Seed coin-flip", "Accuser wins overall"].map((t) => h("th", {}, t)))), h("tbody", {}, rows))), note(caption)];
    let m;
    if (!live) {
      const all = stored(surprises);
      if (!all) { body.replaceChildren(needServer("Measuring this with fresh runs")); return; }
      body.replaceChildren(...table(B.cases.filter((k) => all[k.id]).map((k) => row(k, all[k.id])), "Stored measurement: all 9 pairings of Bold, Careful and Smart over 8 seeds each, run by the engine and saved with the results. Run the local server to measure it again, live."));
      m = all[caseId];
    } else {
      body.replaceChildren(h("p", { class: "muted" }, "Measuring every case from fresh runs…"));
      const rows = [];
      for (const k of B.cases) {
        try { rows.push(row(k, await getMatters(k.id))); } catch { /* leave the row out */ }
        if (caseId !== c.id) return;
      }
      body.replaceChildren(...table(rows, "Every number is measured now: all 9 pairings of Bold, Careful and Smart over 8 seeds (72 fresh trials per case)."));
      m = await getMatters(caseId);
    }
    if (m) says("matters", h("p", {}, h("b", {}, caseName(c)), `: ${m.label.toLowerCase()}. ${m.explanation} The best pairing and the worst differ by ${pct(m.pairing_spread)} in how often the Accuser wins, and in the average pairing the seed alone moves the result ${pct(m.seed_noise)} of the way to a coin flip.`));
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

  /* ---------------------------------------------------------------- the lecture games: classic games, Pareto, security */

  /* The five textbook games, as 2x2 payoffs (row player, column player). These are the textbook definitions the classifier is tested
   * against in tests/test_classic.py; they are not results. Everything else in these chapters is read from results/. */
  const TEXTBOOK = {
    "prisoners-dilemma": { name: "Prisoner's dilemma", rows: ["Cooperate", "Defect"], cols: ["Cooperate", "Defect"], A: [[3, 0], [5, 1]], B: [[3, 5], [0, 1]],
      story: "Each side does better by defecting whatever the other does, yet both are worse off when both defect than when both cooperate." },
    "stag-hunt": { name: "Stag hunt", rows: ["Stag", "Hare"], cols: ["Stag", "Hare"], A: [[4, 0], [3, 3]], B: [[4, 3], [0, 3]],
      story: "Two stable outcomes. Hunting the stag together is best, but it fails if the other goes for the safe hare." },
    "battle-of-the-sexes": { name: "Battle of the sexes", rows: ["Bach", "Stravinsky"], cols: ["Bach", "Stravinsky"], A: [[3, 0], [0, 2]], B: [[2, 0], [0, 3]],
      story: "Two stable outcomes and each side prefers a different one; going to different concerts is worst for both." },
    chicken: { name: "Chicken", rows: ["Swerve", "Straight"], cols: ["Swerve", "Straight"], A: [[0, -1], [1, -10]], B: [[0, 1], [-1, -10]],
      story: "Each side would like to be the one who does not give way, but both refusing is a crash." },
    "matching-pennies": { name: "Matching pennies", rows: ["Heads", "Tails"], cols: ["Heads", "Tails"], A: [[1, -1], [-1, 1]], B: [[-1, 1], [1, -1]],
      story: "One side wants to match, the other wants to differ: no pure choice is stable, so each must randomise." },
  };
  const CLASSIC_NAME = { ...Object.fromEntries(Object.entries(TEXTBOOK).map(([k, v]) => [k, v.name])), "dominance-solvable": "Dominance-solvable (one clear best play)", other: "None of the classic games" };
  const CLASSIC_ORDER = ["prisoners-dilemma", "stag-hunt", "battle-of-the-sexes", "chicken", "matching-pennies", "dominance-solvable", "other"];
  const toNum = (v) => (typeof v === "string" && v.includes("/") ? +v.split("/")[0] / +v.split("/")[1] : +v);
  const mixOf = (mix) => mixText(Object.fromEntries(Object.entries(mix ?? {}).map(([k, v]) => [k, toNum(v)]).filter(([, v]) => v > 0)));
  const fmt = (v) => (Math.abs(v) < 5e-3 ? 0 : Math.round(v * 100) / 100).toString().replace("-", "−");
  const grid2 = (A, B, rows, cols, caption, extra = {}) => h("table", { class: "game2", "aria-label": caption },
    h("thead", {}, h("tr", {}, h("th", {}), cols.map((c) => h("th", { scope: "col" }, c)))),
    h("tbody", {}, rows.map((r, i) => h("tr", {}, h("th", { scope: "row" }, r), cols.map((_, j) => h("td", { title: extra.title?.(i, j) }, h("b", {}, fmt(A[i][j])), ", ", fmt(B[i][j])))))));

  let lectSur = false;
  let classicLive = null, classicPick = { r: [0, 1], c: [0, 1] }, searchLive = null;
  const lectCase = (name, id, sur) => A[`${name}${sur ? "_surprises" : ""}`]?.cases?.[id];
  const lectToggle = () => toggle(lectSur, (v) => { lectSur = v; classicLive = null; effLive = null; refreshLect(); });
  const refreshLect = () => { renderClassic(); renderPareto(); renderMinimax(); renderAhead?.(); };

  async function renderClassic() {
    const c = B.cases.find((x) => x.id === caseId), body = $("#classic-fig");
    if (!c || !body) return;
    const r = classicLive?.case_id === c.id && classicLive.surprises === lectSur ? classicLive : lectCase("classic", c.id, lectSur);
    const kids = [lectToggle()];
    kids.push(h("div", { class: "tbk" }, Object.entries(TEXTBOOK).map(([k, t]) => h("figure", { class: "tbk-card" },
      h("figcaption", {}, h("b", {}, t.name)), grid2(t.A, t.B, t.rows, t.cols, `${t.name}, textbook payoffs`), h("p", { class: "muted small" }, t.story)))),
      note("The five textbook games. Each cell shows the row player's payoff first, then the column player's. Only the order of the payoffs matters, not their size."));
    if (!r) { body.replaceChildren(...kids, note("No measurement is stored for this case.")); return; }
    const total = r.subgames.length;
    kids.push(h("h3", {}, `${caseName(c)}: the ${total} two-by-two corners of its measured table`),
      h("p", {}, `Pick any two of the four styles for the Accuser and any two for the Defender and you get a two-by-two game. There are ${total} such corners. Each is named by the order of its payoffs, treating a gap smaller than two standard errors as a tie.`),
      h("ul", { class: "classic-counts" }, CLASSIC_ORDER.map((k) => h("li", { class: r.label_counts[k] ? null : "zero" }, h("b", {}, String(r.label_counts[k] ?? 0)), ` ${CLASSIC_NAME[k]}`))),
      note(`Measured over ${r.n_seeds} seeds. How often a corner keeps its label when the seeds are resampled ${r.n_resamples} times: ${pct(r.mean_stability)} on average.`));
    // one corner at a time, beside the textbook game it resembles
    const S4 = r.row_strategies;
    const pick = (key, which, label) => h("select", { "aria-label": label, onchange: (e) => { const v = [...e.target.parentNode.querySelectorAll("select")].map((x) => +x.value); classicPick[key] = v.sort(); renderClassic(); } },
      S4.map((n, i) => h("option", { value: i, selected: classicPick[key][which] === i }, nameOf(n))));
    const [r0, r1] = classicPick.r, [c0, c1] = classicPick.c;
    const rowsKey = [S4[r0], S4[r1]], colsKey = [S4[c0], S4[c1]];
    const sub = r0 !== r1 && c0 !== c1 ? r.subgames.find((g) => g.rows[0] === rowsKey[0] && g.rows[1] === rowsKey[1] && g.cols[0] === colsKey[0] && g.cols[1] === colsKey[1]) : null;
    const chooser = h("div", { class: "pair-pick" }, h("span", {}, "Accuser plays "), pick("r", 0, "Accuser style one"), " or ", pick("r", 1, "Accuser style two"),
      h("span", {}, "  against Defender "), pick("c", 0, "Defender style one"), " or ", pick("c", 1, "Defender style two"));
    kids.push(chooser);
    if (sub) {
      const ri = [r0, r1], ci = [c0, c1];
      const sel = (M) => ri.map((i) => ci.map((j) => M[i][j]));
      const tb = TEXTBOOK[sub.label];
      kids.push(h("div", { class: "side-by-side" },
        h("figure", {}, h("figcaption", {}, h("b", {}, "Ours (measured)")),
          grid2(sel(r.A), sel(r.B), rowsKey.map(nameOf), colsKey.map(nameOf), "measured payoffs", { title: (i, j) => `Accuser ±${fmt(r.SA[ri[i]][ci[j]])}, Defender ±${fmt(r.SB[ri[i]][ci[j]])} (standard errors)` })),
        tb ? h("figure", {}, h("figcaption", {}, h("b", {}, `Textbook: ${tb.name}`)), grid2(tb.A, tb.B, tb.rows, tb.cols, "textbook payoffs")) : null),
        h("p", {}, h("b", {}, CLASSIC_NAME[sub.label]), `. ${sub.reason} The label kept ${pct(sub.stability)} of ${r.n_resamples} resamples.`));
    } else kids.push(note("Choose two different styles on each side."));
    // what search over generated cases found
    const sr = searchLive ?? A[`classic_search${lectSur ? "_surprises" : ""}`];
    kids.push(h("h3", {}, "Could the three games we did not find be found by search?"));
    if (sr) {
      const total2 = Object.values(sr.label_counts).reduce((x, y) => x + y, 0);
      kids.push(h("p", {}, `${searchLive ? "Just now, " : ""}${sr.tried} generated cases (gen-${sr.start} to gen-${sr.start + sr.tried - 1}) were measured: ${total2} two-by-two corners. A case counts only if the same corner carries the same name again on fresh seeds.`),
        h("ul", { class: "classic-counts" }, CLASSIC_ORDER.map((k) => h("li", { class: sr.label_counts[k] ? null : "zero" }, h("b", {}, String(sr.label_counts[k] ?? 0)), ` ${CLASSIC_NAME[k]}`))),
        sr.found.length ? h("ul", { class: "found-classic" }, sr.found.map((f) => h("li", {}, h("b", {}, f.case_id), ` ${CLASSIC_NAME[f.label]}: ${f.rows.map(nameOf).join(" or ")} against ${f.cols.map(nameOf).join(" or ")}, kept on ${pct(f.stability)} of resamples. `,
          h("a", { class: "btn ghost sm", href: `index.html#watch=${f.case_id}|${f.rows[0]}|${f.cols[0]}` }, "Play it in the courtroom"), h("span", { class: "muted small" }, " (needs the local server; found by search, not written by hand)"))))
          : h("p", { class: "headline" }, `Not found: none of the ${sr.tried} generated cases has a prisoner's dilemma, stag hunt or battle of the sexes that survives fresh seeds.`),
        sr.label_counts_no_tolerance ? note(`Reading the measured means as exact numbers (no tolerance) the same corners would be called: ${CLASSIC_ORDER.filter((k) => sr.label_counts_no_tolerance[k]).map((k) => `${sr.label_counts_no_tolerance[k]} ${CLASSIC_NAME[k]}`).join(", ")}.`) : null);
    } else kids.push(h("p", { class: "muted" }, "No stored search."));
    if (live) {
      const btn = h("button", { class: "btn ghost sm", type: "button" }, "Search 12 more generated cases now (about 25 seconds)");
      btn.addEventListener("click", async () => {
        btn.disabled = true; btn.textContent = "Searching…";
        try { searchLive = await post("/classic/find", { start: 5000 + Math.floor(Math.random() * 90) * 12, count: 12, surprises: lectSur }); renderClassic(); } catch { btn.textContent = "Could not run it"; }
      });
      const btn2 = h("button", { class: "btn ghost sm", type: "button" }, "Re-measure this case with fresh seeds (about 20 seconds)");
      btn2.addEventListener("click", async () => {
        btn2.disabled = true; btn2.textContent = "Measuring…";
        try { classicLive = await post("/classic", { case_id: c.id, seeds: 20, resamples: 60, surprises: lectSur }); classicLive.case_id = c.id; classicLive.surprises = lectSur; renderClassic(); } catch { btn2.textContent = "Could not run it"; }
      });
      kids.push(h("p", {}, btn, " ", btn2));
    } else kids.push(needServer("Searching again or re-measuring"));
    body.replaceChildren(...kids);
    const named = CLASSIC_ORDER.slice(0, 5).filter((k) => r.label_counts[k]);
    says("classic", h("p", {}, h("b", {}, caseName(c)), `${lectSur ? " (surprises on)" : ""}: ${r.label_counts["dominance-solvable"]} of ${total} corners are dominance-solvable and ${r.label_counts.other} match no classic game. `,
      named.length ? `The classic games that do appear: ${named.map((k) => `${CLASSIC_NAME[k].toLowerCase()} (${r.label_counts[k]})`).join(", ")}. ` : "None of the five classic games appears in this case. ",
      "The classifier says so plainly rather than forcing a match: the payoffs are what the engine measured and nothing was changed to make a lecture game appear."));
  }

  registry.push({
    id: "classic",
    build: () => chapter("classic", "Which classic game is this?", {
      lead: [
        h("p", {}, "Game theory has a few famous two-by-two games. The ", h("dfn", {}, "prisoner's dilemma"), ": each side does better by defecting, yet both lose if both do. The ", h("dfn", {}, "stag hunt"), ": two stable outcomes, one better but riskier. ", h("dfn", {}, "Battle of the sexes"), " (Bach or Stravinsky): two stable outcomes, each side prefers a different one. ", h("dfn", {}, "Chicken"), ": each wants to be the one who does not give way, but both refusing is a crash. ", h("dfn", {}, "Matching pennies"), ": one side wants to match, the other to differ."),
        h("p", {}, "What makes a game one of these is only the order of its payoffs. So we can read that order off our own measured tables and ask honestly: does anything in this courtroom look like the games from the lectures? If not, the answer is \"no\", and the page says so."),
      ],
      read: ["The five cards are the textbook games. Cells show the row player's payoff first.", "Each case's 4×4 table contains 36 two-by-two corners. The counts say how many corners carry each name.", "“Dominance-solvable” means one play is simply best, so there is no dilemma. “None of the classic games” means the payoffs do not have that order, or the data cannot separate them.", "The last block is a search over generated cases for the three games we did not find in the library."],
      fig: h("div", { id: "classic-fig" }),
      maths: h("p", {}, "A payoff counts as better than another only if it is higher by more than two standard errors of the difference; otherwise it is a tie, and a game that needs a strict order where the data has a tie is “none of the classic games”. Prisoner's dilemma: both sides have a strictly dominant play, and for each side temptation > reward > punishment > sucker. Stag hunt: two pure equilibria, both sides prefer the same one, and for both sides the other equilibrium's play has the better worst case. Battle of the sexes: two pure equilibria, each side prefers a different one, and both equilibria beat both mismatches for both sides. Chicken: the same, but each side ranks the four outcomes strictly, with mutual pushing the worst. Matching pennies: no pure equilibrium. The result files are produced by scripts/run_analysis.py classic and scripts/run_classic_search.py."),
    }),
    refresh: renderClassic,
  });

  /* ---- Pareto */

  let effLive = null;
  const effOf = (id) => (effLive?.case_id === id && effLive.surprises === lectSur ? effLive : lectCase("efficiency", id, lectSur));
  const isPureEq = (q) => Object.values(q.row_mix).filter((v) => v !== "0").length === 1 && Object.values(q.col_mix).filter((v) => v !== "0").length === 1;

  function renderPareto() {
    const c = B.cases.find((x) => x.id === caseId), body = $("#pareto-fig");
    if (!c || !body) return;
    const e = effOf(c.id);
    const kids = [lectToggle()];
    if (!e) { body.replaceChildren(...kids, note("No measurement is stored for this case.")); return; }
    const ef = e.efficiency, pc = new Set(ef.pareto_cells.map(([r, k]) => `${r}|${k}`));
    const eqCells = new Set(ef.equilibria.filter(isPureEq).map((q) => `${Object.keys(q.row_mix).find((k) => q.row_mix[k] !== "0")}|${Object.keys(q.col_mix).find((k) => q.col_mix[k] !== "0")}`));
    kids.push(h("div", { class: "ed-scroll" }, h("table", { class: "lab-table pareto-table" },
      h("thead", {}, h("tr", {}, h("th", {}, ""), e.col_strategies.map((d) => h("th", {}, `${nameOf(d)} Defender`)))),
      h("tbody", {}, e.row_strategies.map((r, i) => h("tr", {}, h("th", { scope: "row" }, `${nameOf(r)} Accuser`), e.col_strategies.map((d, j) => {
        const key = `${r}|${d}`;
        return h("td", { class: `${pc.has(key) ? "pareto" : "dominated"} ${eqCells.has(key) ? "eqcell" : ""}`, title: `${pc.has(key) ? "Pareto-efficient" : "another cell is at least as good for both and better for one"}${eqCells.has(key) ? "; a pure equilibrium" : ""}` },
          h("b", {}, fmt(e.A[i][j])), ", ", fmt(e.B[i][j]), pc.has(key) ? h("span", { class: "tag-p", "aria-label": "Pareto-efficient" }, " ★") : null, eqCells.has(key) ? h("span", { class: "tag-e", "aria-label": "pure equilibrium" }, " ◆") : null);
      })))))),
      note("Each cell: Accuser's payoff, then Defender's. ★ marks a Pareto-efficient cell: no other cell is at least as good for both sides and better for one. ◆ marks a pure equilibrium."));
    kids.push(h("h3", {}, "Is each equilibrium efficient?"),
      h("ul", { class: "eq-eff" }, ef.equilibria.map((q) => h("li", {},
        h("b", {}, `Accuser ${mixOf(q.row_mix)}, Defender ${mixOf(q.col_mix)}`), ` pays (${fmt(q.row_payoff)}, ${fmt(q.col_payoff)}): `,
        q.pareto_efficient ? "Pareto-efficient, nothing beats it for both sides." : q.strictly_dominated ? `dominated: ${nameOf(q.dominated_by[0].row)} Accuser against ${nameOf(q.dominated_by[0].col)} Defender would give both sides more (${fmt(q.dominated_by[0].row_gain)} and ${fmt(q.dominated_by[0].col_gain)}). That is the prisoner's-dilemma lesson.` : `weakly dominated: ${nameOf(q.dominated_by[0].row)} Accuser against ${nameOf(q.dominated_by[0].col)} Defender helps ${q.dominated_by[0].row_gain > 0 && q.dominated_by[0].col_gain > 0 ? "both" : "one side"} and hurts nobody (+${fmt(q.dominated_by[0].row_gain)}, +${fmt(q.dominated_by[0].col_gain)}).`))),
      note("A mixed equilibrium is compared by its expected payoffs against the cells (pure pairs of styles); mixing across cells together, which would need the sides to coordinate, is not considered."));
    body.replaceChildren(...kids);
    const nd = ef.equilibria.filter((q) => !q.pareto_efficient).length, nd2 = ef.equilibria.filter((q) => q.strictly_dominated).length;
    says("pareto", h("p", {}, h("b", {}, caseName(c)), `${lectSur ? " (surprises on)" : ""}: ${ef.pareto_cells.length} of ${e.row_strategies.length * e.col_strategies.length} cells are Pareto-efficient. `,
      ef.equilibria.length ? `${ef.equilibria.length - nd} of ${ef.equilibria.length} equilibria are efficient; ${nd2 ? `${nd2} ${nd2 === 1 ? "is" : "are"} dominated for both sides by some other cell, so this case shows the prisoner's-dilemma pattern.` : nd ? "the others are only weakly dominated (a cell helps one side without hurting the other), which is not a dilemma." : "none is dominated, so there is no dilemma in the equilibrium."}` : "No equilibrium was found."));
  }

  registry.push({
    id: "pareto",
    build: () => chapter("pareto", "Is the equilibrium efficient?", {
      lead: [
        h("p", {}, "An outcome is ", h("dfn", {}, "Pareto-efficient"), " if nobody can be made better off without making someone worse off. It sounds like a mild test, but the prisoner's dilemma shows what failing it means: both sides play the equilibrium, and both would have preferred another outcome."),
        h("p", {}, "So for each case we mark the Pareto-efficient cells of the 4×4 table, and for each Nash equilibrium ask whether some other cell is better for both sides at once."),
      ],
      read: ["★ cells are efficient. A plain cell has some other cell that is at least as good for both sides and better for one.", "◆ marks a pure equilibrium. A ◆ without a ★ is an equilibrium the sides could jointly improve on.", "“Dominated for both sides” is the dilemma pattern. “Weakly dominated” is not: one side could gain and nobody loses."],
      fig: h("div", { id: "pareto-fig" }),
      maths: h("p", {}, "A cell (i, j) is Pareto-efficient if no cell has both payoffs at least as high and one strictly higher. This is checked in exact arithmetic on the measured mean payoffs (the same table as the other chapters, 100 seeds). The comparison uses the means, not a significance test, so a small apparent gain can be noise; the table shows the gains so you can judge their size."),
    }),
    refresh: renderPareto,
  });

  /* ---- Minimax */

  const allEqual = (m) => m.flat().every((v) => v === m[0][0]);

  function renderMinimax() {
    const c = B.cases.find((x) => x.id === caseId), body = $("#minimax-fig");
    if (!c || !body) return;
    const e = effOf(c.id);
    const kids = [lectToggle()];
    if (!e) { body.replaceChildren(...kids, note("No measurement is stored for this case.")); return; }
    const ef = e.efficiency, cs = e.constant_sum;
    const side = (who, sec) => h("tr", {}, h("th", { scope: "row" }, who), h("td", {}, `${fmt(sec.pure_value)} (${nameOf(sec.pure_strategy)})`), h("td", {}, `${fmt(sec.mixed_value)}`),
      h("td", {}, mixOf(sec.mixed_strategy)));
    kids.push(h("h3", {}, "What each side can guarantee in the real game"),
      h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
        h("thead", {}, h("tr", {}, ["Side", "Safest single style (guaranteed payoff)", "Safest mix: guaranteed payoff", "The mix"].map((t) => h("th", {}, t)))),
        h("tbody", {}, side("Accuser", ef.row_security), side("Defender", ef.col_security)))),
      h("p", {}, "At each equilibrium, how far above its guaranteed floor does each side end up?"),
      h("ul", { class: "eq-eff" }, ef.equilibria.map((q) => h("li", {}, `${mixOf(q.row_mix)} Accuser against ${mixOf(q.col_mix)} Defender, paying (${fmt(q.row_payoff)}, ${fmt(q.col_payoff)}): Accuser ${fmt(q.security_gap_row)} above its floor, Defender ${fmt(q.security_gap_col)} above its floor.`))),
      note("The courtroom game is not zero-sum and each lawyer sees only part of the evidence, so the guaranteed payoff is only a floor: a cautious lawyer who ignores the opponent's incentives. The gap is what reasoning about the opponent adds."),
      h("h3", {}, "The constant-sum game: the minimax theorem"),
      h("p", {}, "Take only who wins: the Accuser's chance of winning, and the Defender's, which is one minus it. That is constant-sum, because every gain for one side is exactly a loss for the other."),
      h("div", { class: "stab" }, h("div", { class: "stab-label" }, h("b", {}, `Accuser can guarantee ${pct(cs.maximin)}`), `; Defender can hold the Accuser to ${pct(cs.minimax)}`, cs.nash_value != null ? `; Nash value ${pct(cs.nash_value)}.` : "."),
        h("p", { class: cs.theorem_holds ? "headline" : "warn" }, cs.theorem_holds ? `Maximin equals minimax${cs.nash_value != null ? " equals the Nash value" : ""}, as the minimax theorem says${cs.saddle_point ? " (here a pure saddle point, so nobody needs to randomise)" : " (here the sides must mix)"}.` : "The theorem did not hold on this table, which should be impossible: report it.")),
      allEqual(e.accuser_win_rate) ? note(`Every box is ${pct(e.accuser_win_rate[0][0])} because the evidence decides this case: whatever either lawyer does, the Accuser wins ${pct(e.accuser_win_rate[0][0])} of the time. That is a true result, not missing data, and it is why the guarantee, the minimax and the Nash value are all the same number.`) : "",
      h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
        h("thead", {}, h("tr", {}, h("th", {}, "Accuser wins"), e.col_strategies.map((d) => h("th", {}, `${nameOf(d)} Defender`)))),
        h("tbody", {}, e.row_strategies.map((r, i) => h("tr", {}, h("th", { scope: "row" }, `${nameOf(r)} Accuser`), e.accuser_win_rate[i].map((w) => h("td", {}, pct(w)))))))));
    body.replaceChildren(...kids);
    says("minimax", h("p", {}, h("b", {}, caseName(c)), `${lectSur ? " (surprises on)" : ""}: in the win-probability game the Accuser can guarantee ${pct(cs.maximin)} and the Defender can hold it there, so the value of the game is ${pct(cs.maximin)}. In the full game the Accuser's guaranteed payoff is ${fmt(ef.row_security.mixed_value)} and the Defender's is ${fmt(ef.col_security.mixed_value)}.`));
  }

  registry.push({
    id: "minimax",
    build: () => chapter("minimax", "What can each side guarantee?", {
      lead: [
        h("p", {}, "A cautious player can ask a different question from “what is the best reply?”: “what is the most I can be sure of, whatever the other side does?” That is the ", h("dfn", {}, "security value"), " or maximin. A lawyer can improve on playing one style by mixing styles, so we compute the best mix exactly."),
        h("p", {}, "In a game where one side's gain is exactly the other's loss (", h("dfn", {}, "zero-sum"), " or constant-sum), the most the first can guarantee and the least the second can hold it to are the same number, and equal the Nash value. That is the ", h("dfn", {}, "minimax theorem"), ". Our courtroom game is not zero-sum, but the question of who wins is, so we check the theorem on that."),
      ],
      read: ["The first table is the real game: what each side can guarantee, and how far above that floor the equilibrium puts it.", "The second part is the win-probability game, where the theorem should hold exactly.", "If the table shows a pure saddle point, neither side needs to randomise."],
      fig: h("div", { id: "minimax-fig" }),
      maths: h("p", {}, "The maximin of a payoff matrix is max v subject to: for every opposing play, the mix's expected payoff is at least v. Its solution sits at a vertex of that polytope, so the code tries every choice of k plays to mix over and k opposing plays that bind, solves the (k+1)×(k+1) system exactly in rational numbers, keeps the feasible ones and takes the best v. The minimax value is the same computation on the transposed negation. The test suite checks maximin = minimax = Nash value on random constant-sum matrices and on the project's own tables."),
    }),
    refresh: renderMinimax,
  });

  /* ---------------------------------------------------------------- thinking ahead: minimax and alpha-beta on the trial tree */

  let aheadLive = null, aheadLookLive = null;
  const treeData = () => A.tree_search;
  const nodesText = (n, limit) => (n == null ? `more than ${(limit ?? 0).toLocaleString("en")}` : n.toLocaleString("en"));
  const WINNER = (v) => (["guilty", "liable"].includes(v) ? "Accuser wins" : "Defender wins");

  function treeList(n, depth = 0) {
    if (n.kind === "leaf") return h("li", { class: "t-leaf" }, h("span", { class: "t-move" }, n.move), " → ", h("b", {}, fmt(n.value)), h("span", { class: "muted small" }, ` (${WINNER(n.verdict)})`));
    const label = h("span", {}, h("span", { class: "t-move" }, n.move), h("span", { class: "muted small" }, ` · ${n.mover} chooses the ${n.kind === "max" ? "highest" : "lowest"} value`), " → ", h("b", {}, fmt(n.value)));
    return h("li", {}, h("details", { open: depth < 2 }, h("summary", {}, label),
      h("ul", { class: "t-tree" }, n.children.map((c) => treeList(c, depth + 1)),
        n.skipped?.length ? h("li", { class: "t-cut" }, `✂ not looked at (it cannot change the answer): ${n.skipped.join("; ")}`) : null)));
  }

  function renderAhead() {
    const c = B.cases.find((x) => x.id === caseId), body = $("#ahead-fig");
    if (!c || !body) return;
    const T = treeData(), kids = [];
    const rows = T ? Object.values(T.cases) : [];
    const mine = aheadLive?.case_id === c.id ? aheadLive : T?.cases?.[c.id];
    if (T) {
      kids.push(h("h3", {}, "How much of the tree does alpha-beta need to look at?"),
        h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
          h("thead", {}, h("tr", {}, ["Case", "Exhibits (Accuser, Defender)", "Best-play value", "Plain minimax", "Alpha-beta", "Alpha-beta, best move first", "Same answer?"].map((t) => h("th", {}, t)))),
          h("tbody", {}, rows.map((r) => h("tr", { class: r.case_id === c.id ? "current" : null },
            h("th", { scope: "row" }, r.case_id), h("td", {}, `${r.evidence[0]}, ${r.evidence[1]}`), h("td", {}, r.value == null ? "not solved" : fmt(r.value)),
            h("td", {}, r.ran_all_three === false ? "not run" : r.minimax_nodes != null ? nodesText(r.minimax_nodes) : nodesText(null, r.node_limit)),
            h("td", {}, r.ran_all_three === false ? "not run" : r.alphabeta_nodes != null ? nodesText(r.alphabeta_nodes) : nodesText(null, r.node_limit)),
            h("td", {}, r.alphabeta_ordered_nodes != null ? nodesText(r.alphabeta_ordered_nodes) : nodesText(null, r.node_limit)),
            h("td", {}, r.values_agree == null ? "–" : r.values_agree ? "yes" : "NO")))))),
        note(`Nodes visited by each method. ${T.relaxation}. “Not solved” means the tree was too big for the node limit shown in the “more than” cells, which is itself the point: this is what pruning is for.`));
      const ex = T.example;
      kids.push(h("h3", {}, `A small tree, drawn: ${ex.case_id}`),
        h("p", {}, "Each line is a position. The side named chooses the move; the Accuser takes the highest value below it and the Defender the lowest. A value is the Accuser's utility minus the Defender's if the trial ended there (10 for a win, less 0.3 per unit of money spent and any sanctions). ✂ marks moves alpha-beta never needed to look at."),
        h("ul", { class: "t-tree t-root" }, treeList(ex.tree)));
    } else kids.push(note("No stored search."));
    if (live) {
      const btn = h("button", { class: "btn ghost sm", type: "button" }, "Solve this case's tree now (small cases only)");
      btn.addEventListener("click", async () => {
        btn.disabled = true; btn.textContent = "Searching…";
        try { aheadLive = await post("/tree", { case_id: c.id, picture: true }); aheadLive.case_id = c.id; renderAhead(); } catch { btn.textContent = "Could not run it"; }
      });
      kids.push(h("p", {}, btn, aheadLive?.case_id === c.id ? h("span", { class: "muted small" }, ` Live result: value ${aheadLive.value == null ? "not solved (too big)" : fmt(aheadLive.value)}, nodes ${nodesText(aheadLive.minimax_nodes, 15000)} / ${nodesText(aheadLive.alphabeta_nodes, 15000)} / ${nodesText(aheadLive.alphabeta_ordered_nodes, 15000)}.`) : null));
      if (aheadLive?.case_id === c.id && aheadLive.picture) kids.push(h("ul", { class: "t-tree t-root" }, treeList(aheadLive.picture)));
      if (aheadLive?.case_id === c.id && aheadLive.best_play?.length) kids.push(h("p", {}, h("b", {}, "Best play: "), aheadLive.best_play.join(", then ") + "."));
    } else kids.push(needServer("Solving another case's tree"));
    // the lookahead lawyer against the four styles
    const L = A[`lookahead${lectSur ? "_surprises" : ""}`];
    kids.push(h("h3", {}, "Does a lawyer that thinks ahead beat the four styles?"), lectToggle(),
      h("p", {}, "The lookahead lawyer is an extra style: in a real trial it can only use what any counsel is given (its own exhibits and the public scoring rule) and it weighs what the opponent will do in reply. Here it plays the equilibrium of the four hand-written styles, in each seat, on the same seeds."));
    if (L) {
      kids.push(h("div", { class: "ed-scroll" }, h("table", { class: "lab-table" },
        h("thead", {}, h("tr", {}, ["Case", "As Accuser: lookahead − equilibrium (z)", "As Defender: lookahead − equilibrium (z)", "Result"].map((t) => h("th", {}, t)))),
        h("tbody", {}, Object.values(L.cases).map((r) => h("tr", { class: r.case_id === c.id ? "current" : null },
          h("th", { scope: "row" }, r.case_id),
          h("td", {}, `${r.prosecution.difference >= 0 ? "+" : ""}${num2(r.prosecution.difference)} (z ${r.prosecution.z})`),
          h("td", {}, `${r.defense.difference >= 0 ? "+" : ""}${num2(r.defense.difference)} (z ${r.defense.z})`),
          h("td", {}, r.verdict)))))),
        note(`Exhibition, not certified: lookahead is not one of the four certified styles. ${L.n_seeds} seeds per cell, paired by seed; “beats” means more than 2 standard errors. A result of “not distinguishable” is not evidence that it is as good, only that this many seeds cannot tell.`));
    } else kids.push(h("p", { class: "muted" }, "No stored comparison."));
    if (live) {
      const btn = h("button", { class: "btn ghost sm", type: "button" }, "Compare lookahead on this case now (about 20 seconds)");
      btn.addEventListener("click", async () => {
        btn.disabled = true; btn.textContent = "Playing…";
        try { aheadLookLive = await post("/lookahead", { case_id: c.id, seeds: 8, surprises: lectSur }); aheadLookLive.case_id = c.id; renderAhead(); } catch { btn.textContent = "Could not run it"; }
      });
      kids.push(h("p", {}, btn, aheadLookLive?.case_id === c.id ? h("span", { class: "muted small" }, ` Live (8 seeds): ${aheadLookLive.verdict} (Accuser z ${aheadLookLive.prosecution.z}, Defender z ${aheadLookLive.defense.z}).`) : null));
    }
    body.replaceChildren(...kids);
    const t = mine;
    says("ahead", t ? h("p", {}, h("b", {}, caseName(c)), `: ${t.value == null ? "the tree is too big to solve exactly here." : `with both sides seeing everything and playing perfectly, the Accuser's advantage is ${fmt(t.value)} (${t.value > 0 ? "the Accuser wins" : "the Defender wins"}). Plain minimax looked at ${nodesText(t.minimax_nodes, t.node_limit)} positions; alpha-beta with the best move first looked at ${nodesText(t.alphabeta_ordered_nodes, t.node_limit)}, and all methods gave the same value.`} This is the open-file game, not the real one with hidden information.`) : h("p", {}, `No exact search is stored for ${caseName(c)}${live ? ", but you can solve it above if it is small" : ""}.`));
  }

  registry.push({
    id: "ahead",
    build: () => chapter("ahead", "Thinking ahead", {
      lead: [
        h("p", {}, "So far each lawyer picks one style and sticks to it. A real trial is a sequence of moves: offer an exhibit, wait for the objection, answer. A lawyer who thinks ahead asks \"if I do this, what will the other side do, and what do I do then?\" Searching that is the job of ", h("dfn", {}, "minimax"), ": assume the other side always picks the reply that is worst for you, and choose the move whose worst case is best."),
        h("p", {}, h("dfn", {}, "Alpha-beta pruning"), " gives exactly the same answer while skipping lines that cannot matter: if you already have a move that guarantees 5, there is no need to finish checking a move once you find a reply that holds you to 3. Looking at the most promising move first prunes more."),
        h("p", {}, "The real trial hides information (you see the other side's exhibits through a noisy signal) and is not zero-sum, so minimax does not apply to it as it stands. The search here solves an ", h("dfn", {}, "open-file"), " version: both sides see everything, and the payoff is the Accuser's utility minus the Defender's. It runs on the engine's own rules, not a copy."),
      ],
      read: ["The table counts the positions each method looked at. The three methods must give the same value; the page says if they do not.", "The drawn tree is a small case. Open and close branches to follow the search. ✂ marks branches that were never explored.", "The last table is a separate experiment: a lawyer that searches a few moves ahead using only what a real lawyer is given, against the four styles."],
      fig: h("div", { id: "ahead-fig" }),
      maths: h("p", {}, "Alpha-beta keeps two numbers, alpha (the best the Accuser can already guarantee) and beta (the best the Defender can already guarantee), and stops looking at a position once alpha ≥ beta. With perfect ordering it looks at about the square root of the positions plain minimax does. Passing a turn, and objections or impeachments the judge would reject, are left out of the search because they are never better than another move; a test puts them back and checks the value is unchanged. The lookahead lawyer searches its own next three moves, assumes the opponent replies with whatever hurts it most, and (when the opponent offers an exhibit) weighs an objection by its belief that the objection will be sustained. It scores a position by the log-odds potential, a smooth estimate of whether the Accuser clears the bar, and the money and sanctions so far. These are simplifications, so it is reported as an exhibition."),
    }),
    refresh: renderAhead,
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
