/* Courtroom visualiser: a plain-language trial viewer. Vanilla JS, no build step, no network dependencies.
 * Data source: the FastAPI backend when reachable, otherwise the pre-exported
 * bundle (data/bundle.js, loaded by a <script> tag so it also works from file://),
 * so a live demo survives a dead server or no network at all.
 * Everything a newcomer sees is translated from the event stream into everyday words;
 * rule IDs, agent rationales, hashes and exact arithmetic sit behind the "Technical details" switch.
 */
"use strict";

const $ = (sel) => document.querySelector(sel);
const SVG_NS = "http://www.w3.org/2000/svg";
const API = location.protocol.startsWith("http") ? "/api" : null;
const SIDES = ["prosecution", "defense"];
const S = {
  mode: null, bundle: null, cases: [], strategies: [], caseFiles: {}, caseFile: null,
  trial: null, trialKey: null, idx: 0, timer: null, loadToken: 0, caseToken: 0,
  tab: null, game: null, replaySteps: [], replayIdx: 0, replayTimer: null,
};

function el(tag, attrs = {}, ...kids) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue;
    if (k === "class") node.className = v;
    else node.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid != null && kid !== false) node.append(kid);
  return node;
}
function svg(tag, attrs = {}, text) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (text !== undefined) node.textContent = text;
  return node;
}
const cssVar = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const pct = (p) => `${Math.round(100 * p)}%`;
const pct1 = (p) => `${(100 * p).toFixed(1)}%`;
const title = (s) => s.replaceAll("_", " ");
const capFirst = (s) => s.charAt(0).toUpperCase() + s.slice(1);
const lowerFirst = (s) => (/^[A-Z][a-z]/.test(s) ? s.charAt(0).toLowerCase() + s.slice(1) : s);
const joinList = (xs) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs.at(-1)}`);

async function fetchJSON(url, opts = {}, timeoutMs = 20000) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...opts, signal: ctrl.signal });
    if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 200)}`);
    return await res.json();
  } finally {
    clearTimeout(t);
  }
}

/* ------------------------------------------------------------------ plain-language vocabulary */

const STYLE = {
  aggressive: { label: "Aggressive", adverb: "aggressively", blurb: "Offers everything, even shaky evidence, and objects often." },
  conservative: { label: "Careful", adverb: "carefully", blurb: "Offers only solid evidence and objects only when sure." },
  adaptive: { label: "Adaptive", adverb: "adaptively", blurb: "Watches how the other side plays and adjusts." },
  chaos: { label: "Chaotic", adverb: "chaotically", blurb: "Makes random, often illegal moves. A stress test for the rules." },
};
const STYLE_ORDER = ["aggressive", "conservative", "adaptive", "chaos"];
function styleInfo(name) {
  if (STYLE[name]) return STYLE[name];
  if (name.startsWith("mixed:")) {
    const share = pct(+name.slice(6));
    return { label: "Mixed", adverb: "with a mixed strategy", blurb: `Aggressive ${share} of the time, careful otherwise.` };
  }
  return { label: capFirst(title(name)), adverb: title(name), blurb: "" };
}

const KIND = {
  document: "Document", digital_log: "Digital record", physical: "Physical evidence",
  financial_record: "Financial record", testimony: "Witness testimony", expert: "Expert opinion",
};
const GROUND = {
  hearsay: ["it's hearsay, someone repeating what they were told", "hearsay"],
  relevance: ["it has nothing to do with the case", "irrelevant"],
  authentication: ["no one has shown it's genuine", "not verified"],
  illegally_obtained: ["it was obtained illegally", "obtained illegally"],
  late_disclosure: ["it wasn't shared with them before the trial", "shared too late"],
  speculation: ["the witness is only guessing", "guesswork"],
};
const STANDARD = {
  beyond_reasonable_doubt: "beyond reasonable doubt",
  clear_and_convincing: "by clear and convincing evidence",
  preponderance: "on the balance of probabilities",
};
// Display-only fallbacks; the judge itself compares exact fractions (see courtroom/judge/rules.py).
const THRESHOLD = { beyond_reasonable_doubt: 1 / (1 + Math.exp(-2.2)), clear_and_convincing: 1 / (1 + Math.exp(-1.1)), preponderance: 0.5 };
const STATUS_TEXT = {
  unshown: "Not shown", offered: "Waiting for ruling", admitted: "Accepted", excluded: "Thrown out",
  used: "Used against a witness", "used-failed": "Challenge failed",
};

/* ------------------------------------------------------------------ case helpers */

const isCivil = () => S.caseFile?.case_type === "civil";
function sideName(side, { the = true, cap = true } = {}) {
  const base = side === "prosecution" ? (isCivil() ? "plaintiff" : "prosecution") : "defense";
  const s = the ? `the ${base}` : base;
  return cap ? capFirst(s) : s;
}
const The = (side) => sideName(side);
const the = (side) => sideName(side, { cap: false });
const sideLabel = (side) => sideName(side, { the: false });
const opponent = (side) => (side === "prosecution" ? "defense" : "prosecution");
const sideClass = (side) => (side === "prosecution" ? "p" : side === "defense" ? "d" : "j");

function splitTitle(t) {
  const i = t.indexOf(" — ");
  return i < 0 ? { parties: "", name: t } : { parties: t.slice(0, i), name: t.slice(i + 3) };
}
const elementName = (id) => S.caseFile.elements.find((e) => e.id === id)?.name ?? capFirst(title(id));
const itemById = (id) => S.caseFile.evidence.find((e) => e.id === id);
const witnessById = (id) => S.caseFile.witnesses.find((w) => w.id === id);

const threshold = () => S.trial?.verdict.snapshot.elements[0]?.threshold_probability ?? THRESHOLD[S.caseFile.standard];
const strictStandard = () => S.caseFile.standard === "preponderance";
const proven = (p) => (strictStandard() ? p > threshold() + 1e-9 : p >= threshold() - 1e-9);
const barPhrase = () => `${strictStandard() ? "more than" : "at least"} ${pct(threshold())}`;

function flawsOf(item) {
  const flaws = [];
  if (item.hearsay) flaws.push("second-hand information (hearsay)");
  if (!item.authenticated) flaws.push("not verified as genuine");
  if (!item.lawfully_obtained) flaws.push("obtained illegally");
  if (!item.disclosed) flaws.push("not shared before the trial");
  if (item.kind === "testimony" && !item.personal_knowledge) flaws.push("the witness didn't see it first-hand");
  if (Math.max(0, ...Object.values(item.support).map(Math.abs)) < 0.05) flaws.push("barely related to the case");
  return flaws;
}
function supportText(item) {
  const helps = [], hurts = [];
  for (const [k, v] of Object.entries(item.support)) (v > 0 ? helps : hurts).push(lowerFirst(elementName(k)));
  return [helps.length && `Helps prove ${joinList(helps)}`, hurts.length && `Argues against ${joinList(hurts)}`].filter(Boolean).join(". ");
}
const itemMeta = (item) => `${[KIND[item.kind] ?? capFirst(title(item.kind)), supportText(item)].filter(Boolean).join(". ")}.`;

/* ------------------------------------------------------------------ narration: event -> everyday words */

function phaseLabel(phase) {
  return {
    opening: "Opening",
    prosecution_case: `${sideLabel("prosecution")}'s case`,
    directed_verdict_review: "Judge's check",
    defense_case: "Defense's case",
    rebuttal: "Rebuttal",
    deliberation: "Verdict",
    closed: "Verdict",
  }[phase] ?? capFirst(title(phase));
}

function phaseNarration(ev) {
  const P = The("prosecution"), p = the("prosecution");
  if (ev.phase === "opening") {
    const t = S.trial;
    return {
      head: "Court is in session.",
      sub: `${P} plays ${styleInfo(t.prosecution_strategy).adverb}. The defense plays ${styleInfo(t.defense_strategy).adverb}.`,
    };
  }
  return {
    prosecution_case: { head: `${P} presents its case.`, sub: "It offers evidence one piece at a time. The defense can object to each piece." },
    directed_verdict_review: {
      head: `${P} has finished. The defense can now ask the judge to end the trial early.`,
      sub: `The judge will only do that if ${p} has no accepted evidence for one of the points it must prove.`,
    },
    defense_case: { head: "The defense presents its case.", sub: `Now ${p} can object.` },
    rebuttal: { head: `${P} gets a final chance to respond.`, sub: "It can answer anything the defense brought up." },
    deliberation: { head: "The judge weighs the evidence.", sub: "Only accepted evidence counts toward the verdict." },
  }[ev.phase] ?? { head: ev.summary };
}

function verdictNarration() {
  const v = S.trial.verdict;
  const winner = ["guilty", "liable"].includes(v.outcome) ? "prosecution" : "defense";
  const word = {
    guilty: "Guilty", not_guilty: "Not guilty", liable: "Liable", not_liable: "Not liable",
    directed_acquittal: isCivil() ? "Dismissed" : "Not guilty",
  }[v.outcome] ?? capFirst(title(v.outcome));
  const P = The("prosecution");
  const decisive = v.snapshot.elements.find((e) => e.element_id === v.decisive_element);
  const point = v.decisive_element ? `“${lowerFirst(elementName(v.decisive_element))}”` : "one of the points";
  let reason;
  if (winner === "prosecution") reason = `${P} proved every point ${STANDARD[S.caseFile.standard]}.`;
  else if (v.outcome === "directed_acquittal") reason = `${P} had no accepted evidence for ${point}, so the judge ended the trial early.`;
  else if (decisive) reason = `${P} didn't prove ${point} strongly enough. The judge was ${pct(decisive.probability)} sure and needed ${barPhrase()}.`;
  else reason = v.reason;
  return { winner, word, reason };
}

function narrate(ev) {
  const a = ev.action, actor = ev.actor;
  const rules = new Set(ev.rules.map((r) => r.rule_id));
  switch (ev.kind) {
    case "phase_change": {
      const n = phaseNarration(ev);
      return { speaker: "court", ...n, short: ev.phase === "opening" ? n.head : phaseLabel(ev.phase) };
    }
    case "action": {
      const W = The(actor);
      switch (a?.type) {
        case "present_evidence": {
          const item = itemById(a.evidence_id);
          return {
            speaker: actor, head: `${W} presents new evidence.`, exhibit: item,
            sub: `${The(opponent(actor))} can object if it spots a problem.`,
            short: `${W} presents: ${item?.title ?? a.evidence_id}`,
          };
        }
        case "pass":
          if (ev.summary.includes("does not object")) return { speaker: actor, head: `${W} doesn't object.` };
          if (ev.summary.includes("no motion")) return { speaker: actor, head: `${W} doesn't ask to end the trial early.` };
          return { speaker: actor, head: `${W} passes its turn.` };
        case "rest":
          return { speaker: actor, head: `${W} rests its case.`, sub: "It has nothing more to present." };
        case "motion_directed_verdict":
          return {
            speaker: actor, head: `${W} asks the judge to end the trial now.`,
            sub: `It argues ${the("prosecution")} hasn't shown real evidence for every point.`,
            short: `${W} asks to end the trial early.`,
          };
      }
      break;
    }
    case "ruling": {
      const W = actor ? The(actor) : "";
      if (a?.type === "object") {
        const item = itemById(ev.subject);
        const sustained = ev.status === "excluded";
        const [long, short] = GROUND[a.ground] ?? [title(a.ground ?? "objection"), title(a.ground ?? "")];
        const penalties = [];
        if (rules.has("SANCTION-BF") && item) penalties.push(`${The(item.owner)} is penalised for knowingly offering flawed evidence.`);
        if (rules.has("SANCTION-OVR")) penalties.push(`${W} is penalised for a failed objection.`);
        return {
          speaker: actor, head: `${W} objects: ${long}.`, exhibit: item, penalties,
          judge: sustained ? "Objection accepted. The evidence is thrown out." : "Objection rejected. The evidence stays in.",
          tone: sustained ? "no" : "yes",
          short: `${W} objects (${short}). ${sustained ? "Thrown out." : "Overruled."}`,
        };
      }
      if (a?.type === "impeach") {
        const w = witnessById(ev.subject ?? a.witness_id);
        const who = w ? `${w.name} (${lowerFirst(w.role)})` : ev.subject;
        const ok = ev.status === "impeached";
        return {
          speaker: actor, head: `${W} challenges the credibility of ${who}.`, exhibit: itemById(a.evidence_id),
          judge: ok ? "Challenge succeeds. This witness now counts for half as much." : `Challenge rejected. ${W} is penalised.`,
          tone: ok ? "yes" : "no",
          short: `${W} challenges ${w?.name ?? ev.subject}. ${ok ? "It works." : "Rejected."}`,
        };
      }
      if (ev.status === "admitted") {
        const item = itemById(ev.subject);
        return {
          speaker: "court", head: "The judge accepts the evidence.", exhibit: item, tone: "yes",
          sub: "No one objected, so it now counts toward the verdict.", short: "Judge accepts it.",
        };
      }
      if (rules.has("TURN-CAP")) return { speaker: "court", head: `${W} has used all its turns, so its case is closed.` };
      if (rules.has("STALL-1")) return { speaker: "court", head: `${W} kept passing, so the judge treats its case as finished.` };
      if (rules.has("CONTEMPT-1")) return { speaker: "court", head: `${W} broke the rules too many times. The judge closes its case.`, tone: "no" };
      break;
    }
    case "violation":
      return {
        speaker: actor, head: `${The(actor)} tries a move that isn't allowed right now.`,
        judge: "The judge counts it as a pass and fines them.", tone: "no", short: `${The(actor)} makes an illegal move and is fined.`,
      };
    case "directed_verdict": {
      const m = ev.summary.match(/GRANTED on (\S+?)\.?$/);
      if (m) {
        return {
          speaker: "court", head: "The judge ends the trial early.", tone: "no",
          sub: `There's no accepted evidence for “${lowerFirst(elementName(m[1]))}”, so ${the("prosecution")} can't win.`,
        };
      }
      return { speaker: "court", head: "The judge lets the trial continue.", sub: `${The("prosecution")} has shown enough to keep going.`, short: "The trial continues." };
    }
    case "watchdog":
      return { speaker: "court", head: "The trial has run too long. The judge moves straight to a decision." };
    case "verdict": {
      const v = verdictNarration();
      return { speaker: "court", head: v.reason, verdict: v, short: `Verdict: ${v.word.toLowerCase()}.` };
    }
  }
  return { speaker: actor ?? "court", head: ev.summary };
}

/* ------------------------------------------------------------------ data layer */

async function init() {
  initTechToggle();
  initTheme();
  initTabs();
  try {
    if (!API) throw new Error("opened from disk");
    await fetchJSON(`${API}/health`, {}, 1500);
    S.mode = "live";
    S.cases = await fetchJSON(`${API}/cases`);
    S.strategies = await fetchJSON(`${API}/strategies`);
  } catch {
    if (!window.COURTROOM_BUNDLE) {
      $("#source").textContent = "No trial data found.";
      showStageMessage("The trial data didn't load. Start the simulator with python -m courtroom serve, or save trials for offline use with python -m courtroom export.");
      return;
    }
    S.bundle = window.COURTROOM_BUNDLE;
    S.mode = "offline";
    S.cases = S.bundle.cases;
    S.strategies = S.bundle.strategies;
    S.bundle.cases.forEach((c) => (S.caseFiles[c.id] = c));
  }
  document.body.classList.add(S.mode);
  $("#source").textContent = S.mode === "live" ? "Connected to the live simulator." : "Showing saved trials.";

  const caseSel = $("#case");
  const main = el("optgroup", { label: "Main cases" }), edge = el("optgroup", { label: "Edge cases: stress tests for the rules" });
  for (const c of S.cases) (c.id.startsWith("edge-") ? edge : main).append(el("option", { value: c.id }, splitTitle(c.title).name));
  caseSel.append(...[main, edge].filter((g) => g.children.length));
  buildStyleControls();

  caseSel.addEventListener("change", () => selectCase(caseSel.value));
  $("#seed").addEventListener("change", () => loadTrial());
  $("#setup").addEventListener("submit", (e) => { e.preventDefault(); loadTrial({ autoplay: true }); });
  $("#hero-start").addEventListener("click", () => {
    activateTab("courtroom");
    loadTrial({ autoplay: true });
  });
  $("#replay-open").addEventListener("click", () => {
    activateTab("courtroom");
    if (S.trial) { stop(); seek(0); play(); }
  });
  $("#play").addEventListener("click", togglePlay);
  $("#first").addEventListener("click", () => { stop(); seek(0); });
  $("#last").addEventListener("click", () => { stop(); seek(Infinity); });
  $("#prev").addEventListener("click", () => { stop(); seek(S.idx - 1); });
  $("#next").addEventListener("click", () => { stop(); seek(S.idx + 1); });
  $("#scrub").addEventListener("input", (e) => { stop(); seek(+e.target.value); });
  $("#speed").addEventListener("change", () => { if (S.timer) { stop(); play(); } });
  $("#grun").addEventListener("click", runGame);
  document.addEventListener("keydown", (e) => {
    if (e.target.matches("input, select, textarea, [role=tab]") || e.metaKey || e.ctrlKey || e.altKey || !S.trial || S.tab !== "courtroom") return;
    if (e.key === "ArrowRight") { stop(); seek(S.idx + 1); }
    if (e.key === "ArrowLeft") { stop(); seek(S.idx - 1); }
    if (e.key === " " && !e.target.matches("button, a, summary")) { e.preventDefault(); togglePlay(); }
  });

  await selectCase(caseSel.value);
}

async function getCaseFile(id) {
  if (!S.caseFiles[id]) S.caseFiles[id] = await fetchJSON(`${API}/cases/${encodeURIComponent(id)}`);
  return S.caseFiles[id];
}

async function selectCase(id) {
  const token = ++S.caseToken;
  let c;
  try {
    c = await getCaseFile(id);
  } catch (err) {
    showStageMessage(`This case couldn't load (${err.message}). Check that the simulator is still running, then pick the case again.`);
    return;
  }
  if (token !== S.caseToken) return;
  S.caseFile = c;
  S.trial = null;
  S.trialKey = null;
  document.querySelectorAll("[data-side-label]").forEach((n) => (n.textContent = sideLabel(n.dataset.sideLabel)));
  document.querySelectorAll("[data-side-lower]").forEach((n) => (n.textContent = sideName(n.dataset.sideLower, { the: false, cap: false })));
  updateAvailability();
  renderBrief();
  renderCaseStrip();
  renderCaseFile();
  buildEvidenceBoard();
  loadGame();
  await loadTrial();
}

function currentRequest() {
  return {
    case_id: S.caseFile.id,
    prosecution: selectedStyle("prosecution"),
    defense: selectedStyle("defense"),
    seed: S.mode === "live" ? Math.max(0, Math.floor(+$("#seed").value || 0)) : 0,
  };
}

async function loadTrial({ autoplay = false } = {}) {
  if (!S.caseFile) return;
  const req = currentRequest();
  const key = `${req.case_id}|${req.prosecution}|${req.defense}|${req.seed}`;
  if (S.trial && S.trialKey === key) {
    if (autoplay) { stop(); seek(0); play(); }
    return;
  }
  const token = ++S.loadToken;
  stop();
  $("#run").disabled = true;
  try {
    const trial = S.mode === "live"
      ? await fetchJSON(`${API}/trial`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(req) })
      : S.bundle.trials[key];
    if (token !== S.loadToken) return;
    if (!trial) {
      showStageMessage("This matchup isn't in the saved trials. Pick another style, or run the simulator on your computer to try any combination.");
      return;
    }
    S.trial = trial;
    S.trialKey = key;
    setupTrial();
    seek(0);
    if (autoplay) play();
  } catch (err) {
    if (token === S.loadToken) showStageMessage(`The trial couldn't run (${err.message}). Check that the simulator is still running, then press Start trial again.`);
  } finally {
    if (token === S.loadToken) $("#run").disabled = false;
  }
}

function showStageMessage(text) {
  stop();
  S.trial = null;
  S.trialKey = null;
  $("#now").className = "now";
  $("#now").replaceChildren(el("p", { class: "sub" }, text));
  for (const id of ["#phases", "#meters", "#transcript", "#bar-note", "#meters-note"]) $(id).replaceChildren();
  for (const id of ["#first", "#prev", "#play", "#next", "#last", "#scrub"]) $(id).disabled = true;
  $("#step-label").textContent = "";
  renderVerdictTab();
  replayReset();
}

/* ------------------------------------------------------------------ setup controls */

function buildStyleControls() {
  const names = STYLE_ORDER.filter((n) => S.strategies.some((s) => s.name === n));
  for (const s of S.strategies) if (!names.includes(s.name) && !s.name.includes("<")) names.push(s.name);
  if (S.mode === "live") names.push("mixed:0.4");
  for (const side of SIDES) {
    const group = $(`#${side}-style`);
    group.setAttribute("aria-label", `${sideLabel(side)} style`);
    group.replaceChildren(...names.map((n) =>
      el("label", {}, el("input", { type: "radio", name: `${side}-style`, value: n }), el("span", {}, styleInfo(n).label))));
    group.addEventListener("change", () => {
      updateAvailability();
      loadTrial();
    });
  }
  setStyle("prosecution", "aggressive");
  setStyle("defense", "conservative");
}
const selectedStyle = (side) => document.querySelector(`input[name="${side}-style"]:checked`)?.value;
function setStyle(side, value) {
  const input = document.querySelector(`input[name="${side}-style"][value="${CSS.escape(value)}"]`);
  if (input) input.checked = true;
}

function updateAvailability() {
  if (S.mode === "offline" && S.caseFile) {
    const pairs = new Set(Object.keys(S.bundle.trials).filter((k) => k.startsWith(`${S.caseFile.id}|`)).map((k) => k.split("|").slice(1, 3).join("|")));
    const inputs = (side) => [...document.querySelectorAll(`input[name="${side}-style"]`)];
    const choose = (side, ok) => {
      for (const input of inputs(side)) {
        input.disabled = !ok(input.value);
        input.parentElement.title = input.disabled ? "Not in the saved trials. Run the simulator locally to try this matchup." : "";
      }
      const current = inputs(side).find((i) => i.checked);
      if (!current || current.disabled) {
        const pick = ["conservative", "aggressive"].map((v) => inputs(side).find((i) => i.value === v && !i.disabled)).find(Boolean)
          ?? inputs(side).find((i) => !i.disabled);
        if (pick) pick.checked = true;
      }
    };
    choose("prosecution", (v) => [...pairs].some((k) => k.startsWith(`${v}|`)));
    const p = selectedStyle("prosecution");
    choose("defense", (v) => pairs.has(`${p}|${v}`));
  }
  for (const side of SIDES) $(`#${side}-style-help`).textContent = styleInfo(selectedStyle(side) ?? "").blurb;
}

function renderBrief() {
  const c = S.caseFile;
  const { parties, name } = splitTitle(c.title);
  const kind = isCivil() ? "civil" : "criminal";
  const bar = strictStandard() ? `more than ${pct(THRESHOLD[c.standard])}` : `at least ${pct(THRESHOLD[c.standard])}`;
  $("#brief").replaceChildren(
    el("div", {},
      parties && el("p", { class: "parties" }, parties),
      el("h3", {}, name),
      el("p", { class: "synopsis" }, c.synopsis),
      el("p", { class: "charge" }, `${isCivil() ? "Claim" : "Charge"}: ${c.charge}`)),
    el("div", { class: "points" },
      el("h4", {}, `To win, ${the("prosecution")} must prove every one of these`),
      el("ul", {}, c.elements.map((e) => el("li", {}, el("strong", {}, e.name), el("span", {}, e.description)))),
      el("p", { class: "bar-rule" },
        `This is a ${kind} case, so the judge must be ${bar} sure of each point (${STANDARD[c.standard]}).`)),
  );
}

/* ------------------------------------------------------------------ playback */

function togglePlay() {
  if (S.timer) stop();
  else play();
}
function play() {
  if (!S.trial || S.timer) return;
  if (S.idx >= S.trial.events.length - 1) seek(0);
  $("#play").classList.add("playing");
  $("#play").setAttribute("aria-label", "Pause");
  S.timer = setInterval(() => {
    if (S.idx >= S.trial.events.length - 1) return stop();
    seek(S.idx + 1);
  }, +$("#speed").value);
}
function stop() {
  clearInterval(S.timer);
  S.timer = null;
  $("#play").classList.remove("playing");
  $("#play").setAttribute("aria-label", "Play");
}
function seek(i) {
  if (!S.trial) return;
  S.idx = Math.max(0, Math.min(S.trial.events.length - 1, i));
  renderFrame();
}

/* ------------------------------------------------------------------ trial rendering */

function setupTrial() {
  const t = S.trial;
  $("#scrub").max = t.events.length - 1;
  for (const id of ["#first", "#prev", "#play", "#next", "#last", "#scrub"]) $(id).disabled = false;
  buildPhases();
  buildMeters();
  buildTranscript();
  buildWorking();
  renderVerdictTab();
  replayReset();
}

function renderFrame() {
  const t = S.trial, n = t.events.length, ev = t.events[S.idx];
  renderNow(ev);
  updatePhases(ev);
  updateMeters(ev, t.events[S.idx - 1]);
  updateTranscript();
  updateEvidenceBoard();
  $("#scrub").value = S.idx;
  $("#step-label").textContent = `Step ${S.idx + 1} of ${n}`;
  $("#first").disabled = $("#prev").disabled = S.idx === 0;
  $("#next").disabled = $("#last").disabled = S.idx === n - 1;
}

const speakerTag = (who) => el("span", { class: `tag ${sideClass(who)}` }, who === "court" ? "Judge" : sideLabel(who));

function exhibitCard(item) {
  if (!item) return null;
  const flaws = flawsOf(item);
  return el("div", { class: "exhibit" },
    el("span", { class: `tag ${sideClass(item.owner)}` }, item.id),
    el("p", { class: "ex-title" }, item.title),
    el("p", { class: "ex-meta" }, itemMeta(item)),
    flaws.length ? el("p", { class: "flaw" }, `Hidden flaw: ${joinList(flaws)}.`) : null);
}

function techBlock(ev) {
  return el("div", { class: "tech tech-block" },
    ev.rules.map((r) => el("p", {}, el("span", { class: "rule-chip" }, r.rule_id), r.detail)),
    ev.action?.rationale ? el("p", {}, el("strong", {}, "Lawyer's reasoning: "), ev.action.rationale) : null,
    el("p", {}, el("strong", {}, "Log: "), ev.summary),
    el("p", { class: "hash" }, `Event #${ev.seq}  sha256 ${ev.hash}`));
}

function renderNow(ev) {
  const n = narrate(ev);
  const box = $("#now");
  box.className = n.verdict ? `now verdict win-${sideClass(n.verdict.winner)}` : "now";
  const kids = [el("div", { class: "speaker" }, speakerTag(n.speaker), n.verdict ? "Verdict" : null)];
  if (n.verdict) {
    kids.push(el("p", { class: "verdict-word" }, n.verdict.word));
    kids.push(el("p", { class: "winner" }, speakerTag(n.verdict.winner), `${The(n.verdict.winner)} wins the case.`));
  }
  kids.push(el("p", { class: "line" }, n.head));
  if (n.exhibit) kids.push(exhibitCard(n.exhibit));
  if (n.judge) kids.push(el("div", { class: `judge-says ${n.tone ?? ""}` }, speakerTag("court"), el("p", {}, n.judge)));
  for (const p of n.penalties ?? []) kids.push(el("p", { class: "penalty" }, p));
  if (n.sub) kids.push(el("p", { class: "sub" }, n.sub));
  kids.push(techBlock(ev));
  box.replaceChildren(...kids);
}

function trialPhases() {
  const seen = [];
  for (const ev of S.trial.events) {
    const ph = ev.phase === "closed" ? "deliberation" : ev.phase;
    if (!seen.includes(ph)) seen.push(ph);
  }
  return seen;
}
function buildPhases() {
  $("#phases").replaceChildren(...trialPhases().map((ph) => el("li", { "data-phase": ph }, phaseLabel(ph))));
}
function updatePhases(ev) {
  const cur = ev.phase === "closed" ? "deliberation" : ev.phase;
  let passed = true;
  for (const li of $("#phases").children) {
    const isCur = li.dataset.phase === cur;
    if (isCur) passed = false;
    li.className = isCur ? "current" : passed ? "done" : "";
    if (isCur) {
      li.setAttribute("aria-current", "step");
      const ol = li.parentElement; // keep the current stage visible when the stepper scrolls sideways on phones
      if (ol.scrollWidth > ol.clientWidth) ol.scrollLeft = li.offsetLeft - (ol.clientWidth - li.offsetWidth) / 2;
    } else li.removeAttribute("aria-current");
  }
}

function buildMeters() {
  const first = S.trial.events[0].element_probabilities;
  const thr = threshold();
  $("#bar-note").replaceChildren(el("i", { class: "key-bar", "aria-hidden": "true" }), `Line = the ${pct(thr)} needed to prove a point`);
  $("#meters").replaceChildren(...Object.keys(first).map((id) =>
    el("div", { class: "meter", "data-el": id },
      el("div", { class: "meter-name" }, el("span", {}, elementName(id)), el("span", { class: "proven-mark" }, "Proven")),
      el("div", { class: "meter-track", role: "meter", "aria-valuemin": "0", "aria-valuemax": "100", "aria-label": elementName(id) },
        el("div", { class: "meter-fill" }), el("div", { class: "meter-bar", style: `left: ${100 * thr}%` })),
      el("div", { class: "meter-value" }, el("span", { class: "delta" }), el("span", { class: "val" })))));
  const start = Object.values(first)[0] ?? 0.5;
  $("#meters-note").textContent = isCivil()
    ? `Every point starts at ${pct(start)}: undecided. Evidence moves the judge one way or the other.`
    : `Every point starts at ${pct(start)} because the accused is presumed innocent. Evidence moves the judge one way or the other.`;
}
function updateMeters(ev, prev) {
  const final = S.idx === S.trial.events.length - 1;
  const exact = Object.fromEntries(S.trial.verdict.snapshot.elements.map((e) => [e.element_id, e.met]));
  for (const row of $("#meters").children) {
    const id = row.dataset.el, p = ev.element_probabilities[id];
    const ok = final && id in exact ? exact[id] : proven(p);
    row.classList.toggle("proven", ok);
    row.querySelector(".meter-fill").style.setProperty("--fill", `${100 * p}%`);
    row.querySelector(".val").textContent = pct(p);
    row.querySelector(".meter-track").setAttribute("aria-valuenow", Math.round(100 * p));
    row.querySelector(".meter-track").setAttribute("aria-valuetext", `${pct(p)} sure${ok ? ", proven" : ""}. Needs ${barPhrase()}.`);
    const d = prev ? Math.round(100 * p) - Math.round(100 * prev.element_probabilities[id]) : 0;
    row.querySelector(".delta").textContent = d ? `${d > 0 ? "+" : "−"}${Math.abs(d)}` : "";
  }
}

function buildTranscript() {
  const ol = $("#transcript");
  ol.replaceChildren();
  S.trial.events.forEach((ev, i) => {
    const n = narrate(ev);
    const cls = ev.kind === "phase_change" ? "t-btn t-phase" : `t-btn ${n.speaker}`;
    const btn = el("button", { type: "button", class: cls }, el("span", { class: "tech t-seq" }, `#${ev.seq}`), n.short ?? n.head);
    btn.addEventListener("click", () => { stop(); seek(i); });
    ol.append(el("li", { "data-i": i }, btn));
  });
  ol.append(el("li", { class: "t-more", id: "t-more" }));
}
function updateTranscript() {
  const ol = $("#transcript"), n = S.trial.events.length;
  let current = null;
  for (const li of ol.children) {
    if (li.id === "t-more") continue;
    const i = +li.dataset.i;
    li.hidden = i > S.idx;
    const btn = li.firstChild;
    if (i === S.idx) { btn.setAttribute("aria-current", "step"); current = li; } else btn.removeAttribute("aria-current");
  }
  const left = n - 1 - S.idx;
  $("#t-more").textContent = left ? `${left} more ${left === 1 ? "step" : "steps"} to go` : "End of the trial.";
  if (current && (current.offsetTop < ol.scrollTop || current.offsetTop + current.offsetHeight > ol.scrollTop + ol.clientHeight)) {
    ol.scrollTop = current.offsetTop - ol.clientHeight / 2;
  }
}

/* ------------------------------------------------------------------ evidence board */

function buildEvidenceBoard() {
  for (const side of SIDES) {
    $(`#${side}-ev-title`).textContent = `${sideLabel(side)}'s evidence`;
    const items = S.caseFile.evidence.filter((e) => e.owner === side);
    const list = $(`#${side}-evidence`);
    list.replaceChildren(...items.map((item) => {
      const flaws = flawsOf(item);
      return el("li", { class: "ev-item", "data-id": item.id },
        el("span", { class: `tag ${sideClass(side)}` }, item.id),
        el("div", {},
          el("p", { class: "ev-title" }, item.title),
          el("p", { class: "ev-meta" }, itemMeta(item)),
          flaws.length ? el("p", { class: "flaw" }, `Hidden flaw: ${joinList(flaws)}.`) : null),
        el("span", { class: "status unshown" }, STATUS_TEXT.unshown));
    }));
    if (!items.length) list.append(el("li", { class: "ev-empty" }, "No evidence on file for this side."));
    $(`#${side}-score`).replaceChildren();
  }
}

function boardState(upto) {
  const status = {};
  const score = Object.fromEntries(SIDES.map((s) => [s, { shown: 0, accepted: 0, thrown: 0, objections: 0, won: 0 }]));
  for (const ev of S.trial.events.slice(0, upto + 1)) {
    const a = ev.action;
    if (a?.type === "impeach") status[a.evidence_id] = ev.status === "impeached" ? "used" : "used-failed";
    else if (ev.subject && ev.status && itemById(ev.subject)) status[ev.subject] = ev.status;
    if (ev.kind === "action" && a?.type === "present_evidence" && score[ev.actor]) score[ev.actor].shown++;
    const owner = ev.kind === "ruling" && itemById(ev.subject ?? "")?.owner;
    if (owner && ev.status === "admitted") score[owner].accepted++;
    if (owner && ev.status === "excluded") score[owner].thrown++;
    if (ev.kind === "ruling" && a?.type === "object" && score[ev.actor]) {
      score[ev.actor].objections++;
      if (ev.status === "excluded") score[ev.actor].won++;
    }
  }
  return { status, score };
}

function updateEvidenceBoard() {
  if (!S.trial) return;
  const { status, score } = boardState(S.idx);
  const subject = S.trial.events[S.idx].subject ?? S.trial.events[S.idx].action?.evidence_id;
  document.querySelectorAll(".ev-item").forEach((li) => {
    const st = status[li.dataset.id] ?? "unshown";
    li.classList.toggle("excluded", st === "excluded");
    li.classList.toggle("current", li.dataset.id === subject);
    const badge = li.querySelector(".status");
    badge.className = `status ${st}`;
    badge.textContent = STATUS_TEXT[st] ?? st;
  });
  for (const side of SIDES) {
    const s = score[side];
    const stat = (label, value) => el("div", {}, el("dt", {}, label), el("dd", {}, value));
    $(`#${side}-score`).replaceChildren(
      stat("Shown", String(s.shown)), stat("Accepted", String(s.accepted)), stat("Thrown out", String(s.thrown)),
      stat("Objections won", `${s.won} of ${s.objections}`));
  }
}

/* ------------------------------------------------------------------ technical working (final verdict) */

function buildWorking() {
  const t = S.trial, v = t.verdict;
  const findings = $("#findings");
  findings.replaceChildren(el("tr", {}, ["Point", "Certainty", "Needed", "Result", "Exact log-odds", "Evidence counted (log-odds)"].map((h) => el("th", {}, h))));
  for (const es of v.snapshot.elements) {
    const counted = es.contributions.filter((c) => c.counted).map((c) => `${c.evidence_id} ${c.log_odds >= 0 ? "+" : ""}${c.log_odds.toFixed(2)}`);
    findings.append(el("tr", {},
      el("td", {}, elementName(es.element_id)), el("td", { class: "num" }, pct1(es.probability)),
      el("td", { class: "num" }, `${pct1(es.threshold_probability)} (${es.threshold})`),
      el("td", { class: es.met ? "met" : "unmet" }, es.met ? "Proven" : "Not proven"),
      el("td", { class: "num mono" }, es.log_odds), el("td", {}, counted.join(", ") || "None")));
  }
  const lp = t.ledgers.prosecution, ld = t.ledgers.defense;
  const ledger = $("#ledger");
  ledger.replaceChildren(el("tr", {}, el("th", {}, ""), el("th", {}, sideLabel("prosecution")), el("th", {}, "Defense")));
  const rows = [
    ["Style", styleInfo(t.prosecution_strategy).label, styleInfo(t.defense_strategy).label],
    ...[["Budget left", "budget"], ["Budget spent", "spent"], ["Evidence accepted / shown", null], ["Evidence thrown out", "excluded"],
      ["Objections (won)", "obj"], ["Witness challenges", "impeachments"], ["Rule violations", "violations"], ["Penalty points", "sanctions"],
    ].map(([label, k]) => {
      const f = (l) => (k === null ? `${l.admitted} / ${l.presented}` : k === "obj" ? `${l.objections} (${l.sustained})` : `${+l[k].toFixed(2)}`);
      return [label, f(lp), f(ld)];
    }),
    ["Payoff (utility)", t.utilities.prosecution.toFixed(2), t.utilities.defense.toFixed(2)],
  ];
  for (const [a, b, c] of rows) ledger.append(el("tr", {}, el("td", {}, a), el("td", { class: "num" }, b), el("td", { class: "num" }, c)));
  $("#digest").textContent = t.digest;
}

/* ------------------------------------------------------------------ which style wins */

function loadGame() {
  S.game = null;
  const { name } = splitTitle(S.caseFile.title);
  $("#styles-case").textContent = `Case: ${name}`;
  $("#gstatus").textContent = "";
  if (S.mode === "offline") return renderGame(S.bundle.games[S.caseFile.id]);
  $("#matrix").replaceChildren();
  $("#matrix-note").replaceChildren();
  $("#insight").replaceChildren(el("p", { class: "empty-note" }, "Press Run the numbers to replay this case for every combination of styles."));
  $("#game-notes").replaceChildren();
  $("#dynamics").replaceChildren();
}

async function runGame() {
  const strategies = $("#gstrats").value.split(",");
  const seeds = Math.min(100, Math.max(1, Math.floor(+$("#gseeds").value || 20)));
  const btn = $("#grun"), status = $("#gstatus"), caseId = S.caseFile.id;
  btn.disabled = true;
  status.textContent = `Running ${seeds} trials for each of ${strategies.length ** 2} matchups…`;
  try {
    const game = await fetchJSON(`${API}/game`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: caseId, strategies, seeds }) }, 180000);
    if (caseId !== S.caseFile.id) return;
    renderGame(game);
    status.textContent = `Done: ${game.seeds.length} trials per matchup.`;
  } catch (err) {
    status.textContent = `The numbers couldn't be run (${err.message}). Try fewer trials per matchup.`;
  } finally {
    btn.disabled = false;
  }
}

function equilibriumWinRate(game, eq) {
  let w = 0;
  for (const c of game.cells) w += (eq.row_mix[c.row] ?? 0) * (eq.col_mix[c.col] ?? 0) * c.prosecution_win_rate;
  return w;
}
const pureChoice = (mix) => Object.keys(mix).find((k) => mix[k] === 1);

function renderGame(game) {
  if (!game) {
    $("#insight").replaceChildren(el("p", { class: "empty-note" }, "No comparison is saved for this case."));
    return;
  }
  S.game = game;
  const a = game.analysis, n = game.seeds.length;
  const P = The("prosecution"), p = the("prosecution");
  $("#styles-intro").textContent = `Should a lawyer go on the attack or play it safe? We replayed this case ${n} times for every combination of styles to find out.`;

  const stable = new Set(a.equilibria.filter((e) => e.pure).map((e) => `${pureChoice(e.row_mix)}|${pureChoice(e.col_mix)}`));
  const cells = Object.fromEntries(game.cells.map((c) => [`${c.row}|${c.col}`, c]));
  const head = el("tr", {}, el("td", { class: "corner" }), game.col_strategies.map((c) => el("th", { scope: "col" }, el("small", {}, "Defense"), styleInfo(c).label)));
  const body = game.row_strategies.map((r) => el("tr", {},
    el("th", { scope: "row" }, el("small", {}, sideLabel("prosecution")), styleInfo(r).label),
    game.col_strategies.map((c) => {
      const cell = cells[`${r}|${c}`];
      const isStable = stable.has(`${r}|${c}`);
      const split = el("div", { class: "split", "aria-hidden": "true" }, el("span", { style: `width: ${100 * cell.prosecution_win_rate}%` }));
      return el("td", { class: isStable ? "stable" : "" },
        el("p", { class: "cell-rate" }, pct(cell.prosecution_win_rate)),
        el("p", { class: "cell-label" }, `of trials won by ${p}`),
        split,
        isStable ? el("p", { class: "cell-badge" }, "Stable choice") : null,
        el("p", { class: "tech cell-tech" },
          `Payoffs: ${sideLabel("prosecution")} ${cell.mean_row.toFixed(2)} ± ${cell.se_row.toFixed(2)}, defense ${cell.mean_col.toFixed(2)} ± ${cell.se_col.toFixed(2)}`));
    })));
  $("#matrix").replaceChildren(el("caption", { class: "tech" }, `Mean payoffs over ${n} seeds per cell.`), el("thead", {}, head), el("tbody", {}, body));
  $("#matrix-note").replaceChildren(...[
    el("span", {}, el("i", { style: `background: ${cssVar("--p")}` }), `${sideLabel("prosecution")} wins`),
    el("span", {}, el("i", { style: `background: ${cssVar("--d")}` }), "Defense wins"),
    stable.size ? el("span", {}, "Outlined: where both sides end up when each plays its best response.") : null,
  ].filter(Boolean));

  const eqs = a.equilibria;
  const kids = [];
  if (!eqs.length) {
    kids.push(el("p", { class: "headline" }, "No stable way to play this case was found."));
  } else if (eqs.length === 1 && eqs[0].pure) {
    const r = pureChoice(eqs[0].row_mix), c = pureChoice(eqs[0].col_mix);
    kids.push(el("p", { class: "headline" }, `If both sides play smart, ${p} plays ${styleInfo(r).adverb} and the defense plays ${styleInfo(c).adverb}.`));
    kids.push(el("p", {}, "Neither side can do better by switching style on its own. Game theorists call this a Nash equilibrium."));
  } else if (eqs.length === 1) {
    kids.push(el("p", { class: "headline" }, "There's no single best style here. Smart lawyers mix it up."));
    kids.push(el("p", {}, "If each side picks its style at random with the odds below, neither can do better by changing its approach. Game theorists call this a mixed Nash equilibrium."));
  } else {
    kids.push(el("p", { class: "headline" }, `There are ${eqs.length} stable ways to play this case.`));
    kids.push(el("p", {}, "In each one, neither side can do better by switching style on its own. Which one happens depends on what each side expects the other to do."));
  }
  const dominance = [];
  if (a.row_dominant) dominance.push(`For ${p}, ${styleInfo(a.row_dominant).label.toLowerCase()} is always the better choice, whatever the defense does.`);
  if (a.col_dominant) dominance.push(`For the defense, ${styleInfo(a.col_dominant).label.toLowerCase()} is always the better choice, whatever ${p} does.`);
  if (dominance.length) kids.push(el("p", { class: "dominance" }, dominance.join(" ")));

  const mixed = eqs.filter((e) => !e.pure);
  if (mixed.length) {
    const mixRow = (side, mix, exact) => {
      const entries = Object.entries(mix);
      const full = cssVar(`--${sideClass(side)}`), soft = cssVar(`--${sideClass(side)}-soft`);
      const shades = entries.length > 2 ? [full, `color-mix(in srgb, ${full} 50%, ${soft})`, soft] : [full, soft];
      return el("div", {},
        el("p", { class: "mix-label" }, speakerTag(side), `${sideLabel(side)}'s smart mix`),
        el("div", { class: "mix-bar", role: "img", "aria-label": entries.map(([k, v]) => `${styleInfo(k).label} ${pct(v)}`).join(", ") },
          entries.map(([, v], j) => el("span", { style: `width: ${100 * v}%; background: ${shades[j % shades.length]}` }))),
        el("p", { class: "mix-legend" }, entries.map(([k, v], j) => v < 0.005 ? null :
          el("span", {}, el("i", { style: `background: ${shades[j % shades.length]}` }), el("b", {}, `${styleInfo(k).label} ${pct(v)}`),
            el("span", { class: "tech" }, ` (${exact[k]})`)))));
    };
    kids.push(el("div", { class: "mixes" }, mixed.slice(0, 1).flatMap((e) => [mixRow("prosecution", e.row_mix, e.row_mix_exact), mixRow("defense", e.col_mix, e.col_mix_exact)])));
  }
  if (eqs.length) {
    kids.push(el("div", { class: "big-stat" },
      el("strong", {}, pct(equilibriumWinRate(game, eqs[0]))),
      el("span", {}, `of trials won by ${p} when both sides play smart.`)));
  }
  $("#insight").replaceChildren(...kids);

  const facts = [
    `Dominant strategy: ${sideLabel("prosecution")} ${a.row_dominant ? `${a.row_dominant} (${a.row_dominance})` : "none"}; defense ${a.col_dominant ? `${a.col_dominant} (${a.col_dominance})` : "none"}.`,
    `Survivors of iterated elimination of strictly dominated strategies: {${a.iesds_rows.join(", ")}} × {${a.iesds_cols.join(", ")}}.`,
    ...eqs.map((e, i) => `Equilibrium ${i + 1} (${e.pure ? "pure" : "mixed"}, ${e.verified ? "verified" : "unverified"}): expected payoff ${sideLabel("prosecution")} ${e.row_payoff.toFixed(3)}, defense ${e.col_payoff.toFixed(3)}.`),
    ...a.notes,
  ];
  $("#game-notes").replaceChildren(...facts.map((f) => el("li", {}, f)));
  renderDynamics(game);
}

function renderDynamics(game) {
  const g = $("#dynamics");
  g.replaceChildren();
  const pad = 44, W = 420, span = W - 2 * pad;
  const X = (v) => pad + span * v, Y = (v) => W - pad - span * v;
  g.append(svg("rect", { x: pad, y: pad, width: span, height: span, style: `fill: none; stroke: ${cssVar("--rule-strong")}` }));
  g.append(svg("text", { x: W / 2, y: W - 8, "text-anchor": "middle", class: "muted" }, `${sideLabel("prosecution")} share playing ${styleInfo(game.row_strategies[0]).label.toLowerCase()}`));
  g.append(svg("text", { x: 14, y: W / 2, "text-anchor": "middle", class: "muted", transform: `rotate(-90 14 ${W / 2})` }, `Defense share playing ${styleInfo(game.col_strategies[0]).label.toLowerCase()}`));
  for (const v of [0, 0.5, 1]) {
    g.append(svg("text", { x: X(v), y: W - pad + 16, "text-anchor": "middle", class: "muted" }, pct(v)));
    g.append(svg("text", { x: pad - 6, y: Y(v) + 4, "text-anchor": "end", class: "muted" }, pct(v)));
  }
  if (game.dynamics?.length) {
    const d = game.dynamics.map((pt, i) => `${i ? "L" : "M"}${X(pt.x[0]).toFixed(1)},${Y(pt.y[0]).toFixed(1)}`).join("");
    g.append(svg("path", { d, style: `fill: none; stroke: ${cssVar("--d")}; stroke-width: 2` }));
    const s = game.dynamics[0], e = game.dynamics.at(-1);
    g.append(svg("circle", { cx: X(s.x[0]), cy: Y(s.y[0]), r: 4, style: `fill: ${cssVar("--muted")}` }));
    g.append(svg("circle", { cx: X(e.x[0]), cy: Y(e.y[0]), r: 5, style: `fill: ${cssVar("--d")}` }));
  }
  for (const eq of game.analysis.equilibria) {
    const cx = X(eq.row_mix[game.row_strategies[0]] ?? 0), cy = Y(eq.col_mix[game.col_strategies[0]] ?? 0);
    g.append(svg("circle", { cx, cy, r: 7, style: `fill: none; stroke: ${cssVar("--ink")}; stroke-width: 2.5` }));
    g.append(svg("text", { x: cx + 10, y: cy - 8 }, "Equilibrium"));
  }
}

/* ------------------------------------------------------------------ tabs and theme */

const TABS = ["overview", "courtroom", "casefile", "verdict", "strategy", "judge"];
const TAB_ALIAS = { trial: "courtroom", styles: "strategy", top: "overview" };
function tabFromHash() {
  const h = decodeURIComponent(location.hash.slice(1));
  const t = TAB_ALIAS[h] ?? h;
  return TABS.includes(t) ? t : null;
}

function initTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')];
  for (const t of tabs) {
    t.addEventListener("click", () => activateTab(t.dataset.tab, { push: true }));
    t.addEventListener("keydown", (e) => {
      const i = tabs.indexOf(t);
      const j = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (j === undefined) return;
      e.preventDefault();
      const next = tabs[(j + tabs.length) % tabs.length];
      next.focus();
      activateTab(next.dataset.tab, { push: true });
    });
  }
  document.addEventListener("click", (e) => {
    const link = e.target.closest("[data-tab-link]");
    if (!link || e.metaKey || e.ctrlKey || e.shiftKey) return;
    e.preventDefault();
    activateTab(link.dataset.tabLink, { push: true });
  });
  window.addEventListener("hashchange", () => {
    const t = tabFromHash();
    if (t && t !== S.tab) activateTab(t);
  });
  document.addEventListener("visibilitychange", replaySync);
  if ("ResizeObserver" in window) new ResizeObserver(() => drawEvidenceMap()).observe($("#evmap"));
  activateTab(tabFromHash() ?? "overview", { initial: true });
  // a tab's hash would otherwise make the browser jump past the header on load
  if ("scrollRestoration" in history) history.scrollRestoration = "manual";
  window.scrollTo(0, 0);
}

function activateTab(name, { push = false, initial = false } = {}) {
  const prev = S.tab;
  S.tab = name;
  for (const t of document.querySelectorAll('[role="tab"]')) {
    const on = t.dataset.tab === name;
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    if (on && !initial) t.scrollIntoView({ block: "nearest", inline: "nearest" });
  }
  for (const panel of document.querySelectorAll('[role="tabpanel"]')) {
    const on = panel.id === name;
    panel.hidden = !on;
    if (on && !initial && prev !== name) {
      panel.classList.remove("entering");
      void panel.offsetWidth; // restart the entrance animation
      panel.classList.add("entering");
    }
  }
  if (push && location.hash !== `#${name}`) history.pushState(null, "", `#${name}`);
  // a new tab starts at the top of the folder, not wherever the last one was scrolled to
  const top = $(".site-header").offsetHeight;
  if (!initial && window.scrollY > top) window.scrollTo({ top, behavior: "instant" });
  if (name === "verdict") drawEvidenceMap();
  replaySync();
}

function initTheme() {
  const btn = $("#theme-toggle"), root = document.documentElement;
  const mq = matchMedia("(prefers-color-scheme: dark)");
  const sync = () => {
    const dark = root.dataset.theme ? root.dataset.theme === "dark" : mq.matches;
    root.toggleAttribute("data-dark", dark);
    btn.setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
    btn.title = btn.getAttribute("aria-label");
    $('meta[name="theme-color"]').content = cssVar("--desk");
    if (S.game) renderGame(S.game); // its chart colours are read from the theme at render time
  };
  btn.addEventListener("click", () => {
    root.dataset.theme = root.hasAttribute("data-dark") ? "light" : "dark";
    try { localStorage.setItem("courtroom-theme", root.dataset.theme); } catch { /* storage unavailable */ }
    sync();
  });
  mq.addEventListener?.("change", sync);
  sync();
}

const icon = (id) => {
  const s = svg("svg", { "aria-hidden": "true" });
  s.append(svg("use", { href: `#${id}` }));
  return s;
};

/* ------------------------------------------------------------------ overview: the bench replay */

const REPLAY_MS = 2300;
const reducedMotion = () => matchMedia("(prefers-reduced-motion: reduce)").matches;

function replayReset() {
  clearTimeout(S.replayTimer);
  // skip the quiet "doesn't object" beats so the short replay stays lively
  S.replaySteps = S.trial ? S.trial.events.map((ev, i) => (ev.kind === "action" && ev.action?.type === "pass" ? -1 : i)).filter((i) => i >= 0) : [];
  S.replayIdx = reducedMotion() ? Math.max(0, S.replaySteps.length - 1) : 0;
  replayRender();
  replaySync();
}
function replaySync() {
  clearTimeout(S.replayTimer);
  S.replayTimer = null;
  const live = Boolean(S.trial) && S.tab === "overview" && !document.hidden && !reducedMotion();
  $("#replay").classList.toggle("paused", !live);
  if (live) S.replayTimer = setTimeout(replayTick, S.replayIdx >= S.replaySteps.length - 1 ? 5200 : REPLAY_MS);
}
function replayTick() {
  if (!S.trial) return;
  S.replayIdx = S.replayIdx >= S.replaySteps.length - 1 ? 0 : S.replayIdx + 1;
  replayRender(true);
  replaySync();
}
function replayRender(animate = false) {
  const t = S.trial, now = $("#replay-now"), meters = $("#replay-meters");
  if (!t || !S.caseFile) {
    $("#replay-case").textContent = S.caseFile ? "Loading a trial…" : "No trial loaded yet.";
    for (const id of ["#replay-matchup", "#replay-step"]) $(id).replaceChildren();
    now.replaceChildren(el("p", { class: "bench-line" }, "Pick a case in the courtroom to start a trial."));
    meters.replaceChildren();
    meters.dataset.key = "";
    $("#replay-progress").style.width = "0";
    return;
  }
  const i = S.replaySteps[S.replayIdx] ?? 0, ev = t.events[i], n = narrate(ev);
  const final = i === t.events.length - 1;
  $("#replay-case").textContent = splitTitle(S.caseFile.title).name;
  $("#replay-matchup").replaceChildren(
    speakerTag("prosecution"), styleInfo(t.prosecution_strategy).label, el("span", {}, "vs"), speakerTag("defense"), styleInfo(t.defense_strategy).label);
  $("#replay-step").textContent = `Step ${i + 1} of ${t.events.length}`;
  const kids = [el("div", { class: "speaker" }, speakerTag(n.speaker), el("span", {}, phaseLabel(ev.phase === "closed" ? "deliberation" : ev.phase)))];
  if (n.verdict) kids.push(el("p", { class: `bench-verdict ${sideClass(n.verdict.winner)}` }, n.verdict.word));
  kids.push(el("p", { class: `bench-line${animate ? " swap" : ""}` }, n.verdict ? `${The(n.verdict.winner)} wins the case.` : n.judge ? `${n.head} ${n.judge}` : n.head));
  now.replaceChildren(...kids);

  const thr = threshold();
  if (meters.dataset.key !== S.trialKey) {
    meters.dataset.key = S.trialKey;
    meters.replaceChildren(...Object.keys(ev.element_probabilities).map((id) =>
      el("div", { class: "mini", "data-el": id },
        el("span", { class: "mini-name", title: elementName(id) }, elementName(id)),
        el("span", { class: "mini-track", "aria-hidden": "true" }, el("span", { class: "mini-fill" }), el("span", { class: "mini-bar", style: `left: ${100 * thr}%` })),
        el("span", { class: "mini-val" }))));
  }
  const exact = Object.fromEntries(t.verdict.snapshot.elements.map((e) => [e.element_id, e.met]));
  for (const row of meters.children) {
    const id = row.dataset.el, p = ev.element_probabilities[id] ?? 0;
    row.classList.toggle("proven", final && id in exact ? exact[id] : proven(p));
    row.querySelector(".mini-fill").style.setProperty("--fill", `${100 * p}%`);
    row.querySelector(".mini-val").textContent = pct(p);
  }
  $("#replay-progress").style.width = `${(100 * (i + 1)) / t.events.length}%`;
}

/* ------------------------------------------------------------------ case strip and case file */

function renderCaseStrip() {
  const c = S.caseFile, { parties, name } = splitTitle(c.title);
  $("#case-strip").replaceChildren(
    el("div", {},
      parties && el("p", { class: "parties" }, parties),
      el("h3", {}, name),
      el("p", { class: "must" }, `${The("prosecution")} must prove `, el("b", {}, joinList(c.elements.map((e) => lowerFirst(e.name)))), ` ${STANDARD[c.standard]}.`)),
    el("a", { class: "btn quiet small", href: "#casefile", "data-tab-link": "casefile" }, "Read the case file", icon("i-arrow")));
}

function initials(name) {
  return name.split(/\s+/).filter((w) => /^[A-Za-z']/.test(w) && !w.endsWith(".")).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
}

function renderCaseFile() {
  const c = S.caseFile;
  const fact = (k, v) => el("div", {}, el("dt", {}, k), el("dd", {}, v));
  $("#case-facts").replaceChildren(
    fact("Type of case", isCivil() ? "Civil" : "Criminal"),
    fact("Exhibits on file", String(c.evidence.length)),
    fact("Budget per side", `${c.budget} points`),
    fact("Moves per stage", String(c.max_primary_turns)),
    fact("Flaws read correctly", pct(c.perception_accuracy)));

  const wl = $("#witnesses");
  wl.replaceChildren(...c.witnesses.map((w) => {
    const gave = c.evidence.filter((e) => e.witness_id === w.id);
    const challenged = c.evidence.filter((e) => e.impeaches?.includes(w.id));
    return el("li", { class: "witness" },
      el("div", { class: "witness-head" },
        el("span", { class: "avatar", "aria-hidden": "true" }, initials(w.name)),
        el("div", {}, el("h4", {}, w.name), el("p", { class: "role" }, w.role))),
      el("div", { class: "cred" }, el("span", {}, "Credibility"),
        el("span", { class: "cred-track", "aria-hidden": "true" }, el("span", { style: `width: ${100 * w.credibility}%` })),
        el("b", {}, pct(w.credibility))),
      w.bias_note ? el("p", { class: "bias" }, `Possible bias: ${lowerFirst(w.bias_note)}`) : null,
      gave.length ? el("p", { class: "gave" }, `Testifies in ${joinList(gave.map((g) => g.id))} for ${the(gave[0].owner)}.`) : null,
      challenged.length ? el("p", { class: "gave" }, `Can be challenged with ${joinList(challenged.map((g) => g.id))}.`) : null);
  }));
  if (!c.witnesses.length) wl.append(el("li", { class: "empty-note" }, "No witnesses in this case."));

  $("#exhibits").replaceChildren(...SIDES.map((side) => {
    const items = c.evidence.filter((e) => e.owner === side);
    return el("section", { class: sideClass(side) },
      el("h4", {}, `${sideLabel(side)}'s exhibits`),
      items.length ? el("ul", {}, items.map(exhibitRow)) : el("p", { class: "empty-note xh" }, "No evidence on file for this side."));
  }));
}

function exhibitRow(item) {
  const flaws = flawsOf(item);
  const w = item.witness_id && witnessById(item.witness_id);
  const links = [];
  if (w) links.push(`Witness: ${w.name}`);
  if (item.contradicts.length) links.push(`Clashes with ${joinList(item.contradicts)}`);
  if (item.impeaches?.length) links.push(`Can discredit ${joinList(item.impeaches.map((id) => witnessById(id)?.name ?? id))}`);
  return el("li", { class: "xh" },
    el("span", { class: `tag ${sideClass(item.owner)}` }, item.id),
    el("p", { class: "xh-title" }, item.title),
    el("p", { class: "xh-meta" }, itemMeta(item)),
    el("div", { class: "xh-rel" }, el("span", {}, "Reliability"),
      el("span", { class: "cred-track", "aria-hidden": "true" }, el("span", { style: `width: ${100 * item.reliability}%` })),
      el("b", {}, pct(item.reliability))),
    links.length ? el("p", { class: "xh-links" }, `${links.join(". ")}.`) : null,
    flaws.length ? el("p", { class: "flaw" }, `Hidden flaw: ${joinList(flaws)}.`) : null);
}

/* ------------------------------------------------------------------ verdict tab */

function renderVerdictTab() {
  const t = S.trial, ruling = $("#ruling");
  if (!t) {
    ruling.className = "ruling empty";
    ruling.replaceChildren(el("p", { class: "empty-note" }, "No trial is loaded yet. Pick a case and a style for each side in the courtroom, then come back here."));
    for (const id of ["#breakdown", "#evmap", "#map-legend", "#chain", "#findings", "#ledger"]) $(id).replaceChildren();
    $("#digest").textContent = "";
    return;
  }
  const v = verdictNarration();
  ruling.className = `ruling win-${sideClass(v.winner)}`;
  ruling.replaceChildren(
    el("p", { class: "verdict-word" }, v.word),
    el("div", { class: "ruling-why" },
      el("p", { class: "winner" }, speakerTag(v.winner), `${The(v.winner)} wins the case.`),
      el("p", {}, v.reason)),
    el("div", { class: "ruling-meta" },
      el("span", {}, `${sideLabel("prosecution")} played: ${styleInfo(t.prosecution_strategy).label}`),
      el("span", {}, `Defense played: ${styleInfo(t.defense_strategy).label}`),
      S.mode === "live" ? el("span", {}, `Trial number ${t.seed}`) : null,
      el("a", { href: "#courtroom", "data-tab-link": "courtroom" }, "Replay it in the courtroom")));

  renderBreakdown();
  renderEvidenceMap();

  $("#chain").replaceChildren(...t.events.map((ev, i) => {
    const n = narrate(ev);
    return el("li", { class: `${SIDES.includes(n.speaker) ? n.speaker : "court"}${i === t.events.length - 1 ? " last-row" : ""}` },
      el("span", { class: "seq" }, `#${ev.seq}`),
      el("span", { class: "what" }, n.short ?? n.head),
      el("span", { class: "hash", title: `This step: ${ev.hash}\nPrevious step: ${ev.prev_hash}` }, el("b", {}, ev.hash.slice(0, 10)), ` ← ${ev.prev_hash.slice(0, 6)}`));
  }));
}

function renderBreakdown() {
  const t = S.trial, start = t.events[0].element_probabilities;
  const all = t.verdict.snapshot.elements.flatMap((es) => es.contributions.map((c) => Math.abs(c.log_odds)));
  const maxAbs = Math.max(0.01, ...all);
  const points = t.verdict.snapshot.elements.map((es) => {
    const rows = [...es.contributions].sort((a, b) => b.log_odds - a.log_odds).map((c) => {
      const item = itemById(c.evidence_id), pos = c.log_odds >= 0, size = Math.abs(c.log_odds);
      const why = [];
      if (c.contradiction_discount > 0) why.push(`cut ${pct(c.contradiction_discount)} by clashing evidence`);
      if (c.corroboration_factor > 1) why.push(`boosted ${pct(c.corroboration_factor - 1)} by backing evidence`);
      if (!c.counted) why.push("not counted: the same fact was already counted");
      return el("div", { class: `bd-row${c.counted ? "" : " uncounted"}`, title: why.length ? capFirst(why.join("; ")) : "" },
        el("p", { class: "bd-label" }, el("span", { class: `tag ${sideClass(item?.owner)}` }, c.evidence_id), el("span", {}, item?.title ?? "")),
        el("div", { class: "bd-bar", role: "img", "aria-label": `${pos ? "Toward" : "Against"} proving this point by ${size.toFixed(1)}${why.length ? `, ${why.join(", ")}` : ""}` },
          el("i", { class: pos ? "p" : "d", style: `width: ${(50 * size) / maxAbs}%` })),
        el("p", { class: "bd-val" }, `${pos ? "+" : "−"}${size.toFixed(1)}`));
    });
    return el("article", { class: "bd-point" },
      el("div", { class: "bd-head" },
        el("h4", {}, elementName(es.element_id)),
        el("span", { class: `bd-result ${es.met ? "met" : "unmet"}` }, es.met ? "Proven" : "Not proven")),
      el("p", { class: "bd-sum" }, `Started at ${pct(start[es.element_id] ?? 0)} and ended at ${pct(es.probability)}. The judge needed ${barPhrase()}.`),
      el("div", { class: `meter-track bd-meter${es.met ? " proven" : ""}`, role: "meter", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": Math.round(100 * es.probability), "aria-label": `${elementName(es.element_id)} certainty` },
        el("div", { class: "meter-fill", style: `--fill: ${100 * es.probability}%` }),
        el("div", { class: "meter-bar", style: `left: ${100 * es.threshold_probability}%` })),
      rows.length ? el("div", { class: "bd-rows" }, rows) : el("p", { class: "bd-none bd-rows" }, "No accepted evidence touched this point, so it stayed where it started."));
  });
  $("#breakdown").replaceChildren(...points,
    el("p", { class: "bd-foot" }, "Numbers show the size of each push in the judge's arithmetic (log-odds). The judge adds them to the starting point. Hover a row to see whether clashing or backing evidence changed it."));
}

const NODE_STATUS = { admitted: "Accepted", excluded: "Thrown out", unpresented: "Never shown" };
function renderEvidenceMap() {
  const g = S.trial.graph, box = $("#evmap");
  const lgLine = (cls, text) => {
    const s = svg("svg", { viewBox: "0 0 28 10", "aria-hidden": "true" });
    s.append(svg("line", { x1: 0, y1: 5, x2: 28, y2: 5, class: `lg-line ${cls}` }));
    return el("span", {}, s, text);
  };
  const lgBox = (cls, text) => el("span", {}, el("i", { class: `lg-box ${cls}`, "aria-hidden": "true" }), text);
  $("#map-legend").replaceChildren(
    lgLine("corroborates", "Backs each other up"), lgLine("contradicts", "Clash: both count for less"),
    lgBox("admitted", "Accepted"), lgBox("excluded", "Thrown out"), lgBox("unpresented", "Never shown"));
  if (!g.nodes.length) {
    box.replaceChildren(el("p", { class: "empty-note" }, "There's no evidence in this case, so there's nothing to map."));
    return;
  }
  const maxW = Math.max(0.01, ...g.nodes.map((n) => n.weight));
  const linksOf = (id) => g.edges.filter((e) => e.source === id || e.target === id)
    .map((e) => `${e.relation === "contradicts" ? "clashes with" : "backed by"} ${e.source === id ? e.target : e.source}`);
  const col = (side) => el("div", { class: `evmap-col ${sideClass(side)}` },
    el("h4", {}, el("span", { class: `tag ${sideClass(side)}` }, sideLabel(side))),
    g.nodes.filter((n) => n.owner === side).map((n) => {
      const links = linksOf(n.id);
      const node = el("button", {
        type: "button", class: `node ${n.status}`, "data-id": n.id, title: n.label,
        "aria-label": `${n.id}, ${n.label}. ${NODE_STATUS[n.status] ?? n.status}.${links.length ? ` ${capFirst(joinList(links))}.` : ""}`,
      },
      el("span", { class: "node-top" }, el("span", { class: `tag ${sideClass(side)}` }, n.id), el("span", {}, n.label)),
      el("span", { class: "node-w", "aria-hidden": "true" }, el("i", { style: `width: ${(100 * n.weight) / maxW}%` })));
      for (const [on, off] of [["mouseenter", "mouseleave"], ["focus", "blur"]]) {
        node.addEventListener(on, () => focusNode(n.id));
        node.addEventListener(off, () => focusNode(null));
      }
      return node;
    }));
  box.replaceChildren(col("prosecution"), col("defense"), svg("svg", { class: "evmap-lines", "aria-hidden": "true" }));
  drawEvidenceMap();
}

function drawEvidenceMap() {
  const box = $("#evmap"), lines = box.querySelector(".evmap-lines");
  if (!lines || !S.trial || box.offsetParent === null) return;
  const B = box.getBoundingClientRect();
  const room = parseFloat(getComputedStyle(box).paddingLeft) - 4;
  const pos = (id) => {
    const n = box.querySelector(`.node[data-id="${CSS.escape(id)}"]`);
    if (!n) return null;
    const r = n.getBoundingClientRect();
    return { l: r.left - B.left, r: r.right - B.left, y: r.top - B.top + r.height / 2, p: n.parentElement.classList.contains("p") };
  };
  lines.setAttribute("viewBox", `0 0 ${B.width} ${B.height}`);
  lines.replaceChildren(...S.trial.graph.edges.map((e) => {
    const a = pos(e.source), b = pos(e.target);
    if (!a || !b) return null;
    let d;
    if (a.p !== b.p) {
      const [L, R] = a.p ? [a, b] : [b, a];
      const mx = (L.r + R.l) / 2;
      d = `M${L.r},${L.y} C${mx},${L.y} ${mx},${R.y} ${R.l},${R.y}`;
    } else {
      // same side: arc out into the margin so the line doesn't cross other exhibits
      const out = a.p ? -1 : 1, x = a.p ? Math.min(a.l, b.l) : Math.max(a.r, b.r);
      const bulge = out * Math.min(room, 10 + Math.abs(a.y - b.y) * 0.15);
      d = `M${x},${a.y} C${x + bulge},${a.y} ${x + bulge},${b.y} ${x},${b.y}`;
    }
    return svg("path", { d, class: e.relation, "data-a": e.source, "data-b": e.target });
  }).filter(Boolean));
}

function focusNode(id) {
  const box = $("#evmap");
  box.classList.toggle("focus", Boolean(id));
  const lit = new Set(id ? [id] : []);
  for (const p of box.querySelectorAll(".evmap-lines path")) {
    const on = Boolean(id) && (p.dataset.a === id || p.dataset.b === id);
    p.classList.toggle("lit", on);
    if (on) { lit.add(p.dataset.a); lit.add(p.dataset.b); }
  }
  for (const n of box.querySelectorAll(".node")) n.classList.toggle("lit", lit.has(n.dataset.id));
}

/* ------------------------------------------------------------------ technical details switch */

function initTechToggle() {
  const box = $("#tech-toggle");
  let on = false;
  try { on = localStorage.getItem("courtroom-tech") === "1"; } catch { /* storage unavailable */ }
  box.checked = on;
  document.body.classList.toggle("show-tech", on);
  box.addEventListener("change", () => {
    document.body.classList.toggle("show-tech", box.checked);
    try { localStorage.setItem("courtroom-tech", box.checked ? "1" : "0"); } catch { /* storage unavailable */ }
  });
}

init();
