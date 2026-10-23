/* Courtroom viewer: pick a case, brief two lawyers, then step into a 3D courtroom and watch and hear the trial.
 * Cases, strategy tables and pre-run trials come from data/bundle.js (works offline and from file://).
 * When the FastAPI backend is reachable, trials for any style pairing are run live instead.
 * Each trial event becomes one or two spoken "beats" (a lawyer's line, then the judge's ruling); the camera
 * cuts to whoever speaks, captions follow along, and auto-play waits for the voice before moving on.
 */
"use strict";

const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];
const B = window.COURTROOM_BUNDLE;
const API = location.protocol.startsWith("http") ? "/api" : null;
const hasGsap = !!window.gsap;
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const S = { live: false, filter: "everyday", caseId: null, p: "aggressive", d: "conservative", trial: null, idx: 0, auto: false, voice: true, run: 0 };

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const c of kids.flat()) if (c != null && c !== false) n.append(c);
  return n;
}
const pct = (p) => `${Math.round(100 * p)}%`;
const capFirst = (s) => s[0].toUpperCase() + s.slice(1);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

/* ------------------------------------------------------------------ plain words */

const CASE_PLAIN = {
  "helix-espionage": "An engineer is accused of secretly copying his company's chip design and selling it to a rival. He says hackers stole his password and he was home asleep.",
  "aurora-defi": "$31 million was taken from a crypto app. The accused says he only took it to keep it safe, like a friendly hacker, and gave most of it back.",
  "kestrel-av": "A self-driving taxi hit a cyclist. The cyclist says the car's software was faulty. The company says the cyclist rode through a red light.",
  "edge-empty-docket": "The Accuser brings a case but has no evidence at all. What should a fair judge do?",
  "edge-mutual-exclusion": "Two equally believable workers tell opposite stories about who sent a bad drone command. There's nothing else to go on.",
  "edge-poisoned-tree": "Every piece of the Accuser's evidence has a problem. If the Defender objects, it all gets thrown out. If not, it counts.",
  "edge-defense-only": "The only evidence in the file actually helps the person accused. The judge should end the trial early.",
};
const STYLE = {
  aggressive: { label: "Bold", blurb: "Shows every piece of evidence, even weak ones, and objects a lot." },
  conservative: { label: "Careful", blurb: "Shows only strong evidence and objects only when sure." },
  adaptive: { label: "Smart", blurb: "Watches the other lawyer and changes plan to match." },
  reckless: { label: "Wild", blurb: "Grabs evidence at random, objects on a whim and sometimes breaks the rules." },
  chaos: { label: "Chaos", blurb: "Pure random moves. A stress test for the rules." },
};
const STYLE_ORDER = ["aggressive", "conservative", "adaptive", "reckless"];
const styleOf = (n) => STYLE[n] ?? { label: n.startsWith("mixed:") ? "Mixed" : capFirst(n), blurb: "" };
const KIND = { document: "Document", digital_log: "Digital record", physical: "Physical evidence", financial_record: "Money record", testimony: "Witness", expert: "Expert opinion" };
const GROUND = {
  hearsay: "that's only a rumour. The witness heard it from someone else",
  relevance: "that has nothing to do with this case",
  authentication: "nobody has shown that it's real",
  illegally_obtained: "it was collected illegally",
  late_disclosure: "we were never shown it before the trial",
  speculation: "the witness is only guessing",
};
const STANDARD = {
  beyond_reasonable_doubt: "The judge must be almost certain, about 90 percent.",
  clear_and_convincing: "The judge must be fairly sure, about 75 percent.",
  preponderance: "The judge just needs to think it's more likely than not.",
};
const PHASE_NAME = { opening: "Court opens", prosecution_case: "The Accuser's turn", directed_verdict_review: "A quick check", defense_case: "The Defender's turn", rebuttal: "The last word", deliberation: "The decision", closed: "The decision" };
const WHO = { prosecution: ["The Accuser", "p"], defense: ["The Defender", "d"], court: ["The Judge", "j"], witness: ["Witness", "w"], bailiff: ["The Bailiff", "b"] };

const caseById = (id) => B.cases.find((c) => c.id === id);
const C = () => caseById(S.caseId);
const item = (id) => C().evidence.find((e) => e.id === id);
const witness = (id) => C().witnesses.find((w) => w.id === id);
const pointName = (id) => window.STORY?.[S.caseId]?.points?.[id] ?? C().elements.find((e) => e.id === id)?.name ?? id;
// lower-case the first letter mid-sentence, unless it starts with a name
const lowerFirst = (t) => (/^[A-Z][a-z]/.test(t) && !/^(Sam|Raj|Rex|Vance|Lark|Kaur|Park)\b/.test(t) ? t[0].toLowerCase() + t.slice(1) : t);
const Side = (s) => WHO[s]?.[0] ?? "The judge";
const category = (c) => (c.tags.includes("everyday") ? "everyday" : c.tags.includes("edge-case") ? "edge-case" : "serious");
const splitTitle = (t) => { const i = t.indexOf(" — "); return i < 0 ? { parties: "", name: t } : { parties: t.slice(0, i), name: t.slice(i + 3) }; };

function flaws(it) {
  const f = [];
  if (it.hearsay) f.push("it's a rumour");
  if (!it.authenticated) f.push("not proven real");
  if (!it.lawfully_obtained) f.push("collected illegally");
  if (!it.disclosed) f.push("kept secret until now");
  if (it.kind === "testimony" && !it.personal_knowledge) f.push("the witness didn't see it");
  return f;
}

/* ------------------------------------------------------------------ narration: event -> spoken beats */

const story = () => window.STORY?.[S.caseId] ?? { ev: {} };
const witnessKey = (it) => it?.witness_id ?? it?.id;
const CALL = ["Your Honour, I'd like to call my witness, {X}.", "Your Honour, the {S} calls {X}."];
/* a witness exhibit plays out like a film: the call, the walk to the box, the oath, the question, the testimony */
function witnessBeats(ev, actor, it, s, say) {
  const key = witnessKey(it), name = s.witness.split(",")[0];
  const sworn = S.trial.events.some((e) => e.seq < ev.seq && e.action?.type === "present_evidence" && story().ev[e.action.evidence_id]?.wit && witnessKey(item(e.action.evidence_id)) === key);
  // split into sentences without breaking on titles like "Mrs." or "Dr."
  const safe = say.replace(/\b(Mrs|Mr|Ms|Dr|Det|Prof|St)\./g, "$1§");
  const sentences = (safe.match(/[^.?!]+[.?!]+/g) ?? [safe]).map((x) => x.trim().replaceAll("§", "."));
  const callIdx = sentences.findIndex((x) => / calls /.test(x));
  const who = callIdx >= 0 ? sentences[callIdx].replace(/^.* calls /, "").replace(/\.$/, "") : s.witness.replace(",", ", the");
  const question = sentences.filter((_, k) => k !== callIdx).join(" ");
  const keep = { mode: "keep" };
  const beats = [{ who: actor, text: pick(CALL, ev.seq).replace("{X}", who).replace("{S}", actor === "prosecution" ? "Accuser" : "Defender"), exhibit: { item: it, mode: "show" }, call: key }];
  if (sworn) beats.push({ who: "court", text: `${name}, please remember you are still under oath.`, shot: "witness", waitWitness: true, exhibit: keep });
  else beats.push(
    { who: "bailiff", text: "Please raise your right hand. Do you swear to tell the truth, the whole truth, and nothing but the truth?", shot: "witness", waitWitness: true, oath: true, exhibit: keep },
    { who: "witness", name: s.witness, text: "I do.", shot: "witness", oath: true, exhibit: keep },
  );
  if (question) beats.push({ who: actor, text: question, exhibit: keep });
  beats.push({ who: "witness", name: s.witness, text: s.wit, shot: "witness", exhibit: keep });
  return beats;
}
/* the witness standing at the stand after event i: called by the latest exhibit, sent away by a phase change */
function witnessAt(i) {
  for (let k = i; k >= 0; k--) {
    const ev = S.trial.events[k];
    if (ev.kind === "phase_change") return null;
    if (ev.action?.type === "present_evidence") {
      const it = item(ev.action.evidence_id);
      return story().ev[it?.id]?.wit ? witnessKey(it) : null;
    }
  }
  return null;
}
const shortOf = (it) => (it ? story().ev[it.id]?.short ?? `the ${(KIND[it.kind] ?? "evidence").toLowerCase()}` : "that evidence");
const pick = (arr, seed) => arr[Math.abs(seed) % arr.length];
const NO_OBJ = ["No objection, Your Honour.", "We don't object.", "No objection. Let the court see it.", "That's fine by us, Your Honour."];
const REST = ["That's all my evidence, Your Honour.", "Nothing further, Your Honour.", "We rest our case.", "I have nothing more to show."];
const PASS = ["I'll pass for now.", "Nothing to add right now, Your Honour.", "We'll wait, Your Honour."];
const ADMIT = ["Accepted. {S} counts as evidence.", "Very well. {S} is accepted.", "I'll allow it. {S} is now part of the record."];
const WILD = ["Your Honour, I demand you end this trial right now!", "Let's skip ahead, Your Honour. Just declare them guilty!", "I move to end the trial immediately!"];
const RULING_WHY = {
  hearsay: "A rumour isn't proof.",
  relevance: "It doesn't help decide this case.",
  authentication: "Nobody has shown it's real.",
  illegally_obtained: "Evidence taken illegally can't be used.",
  late_disclosure: "Both sides must see evidence before the trial.",
  speculation: "Guesses aren't evidence.",
};

function narrate(ev) {
  const a = ev.action, actor = ev.actor, rules = new Set(ev.rules.map((r) => r.rule_id)), seed = ev.seq;
  const J = (text, extra = {}) => ({ who: "court", text, ...extra });
  const st = story();
  switch (ev.kind) {
    case "phase_change": {
      const t = S.trial;
      const line = {
        opening: [`Court is now in session. This is the case of ${splitTitle(C().title).name}.`, `The Accuser will play ${styleOf(t.prosecution_strategy).label.toLowerCase()}. The Defender will play ${styleOf(t.defense_strategy).label.toLowerCase()}. ${STANDARD[C().standard]}`],
        prosecution_case: ["Accuser, please show your evidence.", "The Defender may object to anything unfair."],
        directed_verdict_review: ["Before we go on, a quick check. Does the Accuser have real evidence for every point?", "If a point has none, the trial ends here."],
        defense_case: ["Defender, it's your turn.", "Now the Accuser may object."],
        rebuttal: ["Accuser, you may reply one last time.", ""],
        deliberation: ["Thank you both. I will now weigh the evidence.", "Only accepted evidence counts."],
      }[ev.phase] ?? [ev.summary, ""];
      const beats = [];
      if (ev.phase === "deliberation" && st.close) beats.push({ who: "prosecution", text: st.close.prosecution, aside: "Closing argument" }, { who: "defense", text: st.close.defense, aside: "Closing argument" });
      beats.push(J(line[0], { aside: line[1] }));
      if (ev.phase === "opening" && st.open) beats.push({ who: "prosecution", text: st.open.prosecution, aside: "Opening statement" }, { who: "defense", text: st.open.defense, aside: "Opening statement" });
      return { log: line[0], beats };
    }
    case "action": {
      const W = Side(actor);
      if (a?.type === "present_evidence") {
        const it = item(a.evidence_id);
        const s = st.ev[a.evidence_id] ?? {};
        const say = s.say ?? `Your Honour, I'd like to show the court this: ${it?.title ?? a.evidence_id}.`;
        if (!s.wit) return { log: `${W} shows: ${it?.title ?? a.evidence_id}`, beats: [{ who: actor, text: say, exhibit: { item: it, mode: "show" } }] };
        return { log: `${W} calls ${s.witness.split(",")[0]}.`, beats: witnessBeats(ev, actor, it, s, say) };
      }
      if (a?.type === "pass") {
        if (ev.summary.includes("does not object")) return { log: `${W} doesn't object.`, beats: [{ who: actor, text: pick(NO_OBJ, seed), exhibit: { mode: "keep" } }] };
        if (ev.summary.includes("no motion")) return { log: `${W} lets the trial go on.`, beats: [{ who: actor, text: "We're happy to carry on, Your Honour." }] };
        return { log: `${W} passes.`, beats: [{ who: actor, text: pick(PASS, seed) }] };
      }
      if (a?.type === "rest") return { log: `${W} is done.`, beats: [{ who: actor, text: pick(REST, seed) }] };
      if (a?.type === "motion_directed_verdict") {
        const probs = ev.element_probabilities, weakest = Object.keys(probs).sort((x, y) => probs[x] - probs[y])[0];
        return { log: `${W} asks to end the trial early.`, beats: [{ who: actor, text: `Your Honour, they haven't given you real proof that ${lowerFirst(pointName(weakest))}. Please end the trial now.` }] };
      }
      break;
    }
    case "ruling": {
      const W = actor ? Side(actor) : "";
      if (a?.type === "object") {
        const it = item(ev.subject), ok = ev.status === "excluded", S1 = capFirst(shortOf(it));
        const fines = [rules.has("SANCTION-BF") && it ? `${Side(it.owner)} loses points for using bad evidence.` : "", rules.has("SANCTION-OVR") ? `${W} loses points for a wrong objection.` : ""].filter(Boolean).join(" ");
        return {
          log: `${W} objects. ${ok ? "Thrown out." : "Overruled."}`,
          beats: [
            { who: actor, text: `Objection, Your Honour! ${capFirst(GROUND[a.ground] ?? "that's not fair")}.`, exhibit: { item: it, mode: "keep" }, sting: true },
            J(ok ? `Sustained. ${RULING_WHY[a.ground] ?? ""} ${S1} is thrown out.` : `Overruled. I see no problem with it. ${S1} stays in.`, { tone: ok ? "no" : "yes", aside: fines, gavel: 1, exhibit: { item: it, mode: ok ? "no" : "ok" } }),
          ],
        };
      }
      if (a?.type === "impeach") {
        const w = witness(ev.subject ?? a.witness_id), ok = ev.status === "impeached", it = item(a.evidence_id);
        const name = w?.name ?? "this witness";
        const say = st.ev[a.evidence_id]?.say ?? `Can we really trust ${name}? ${w?.bias_note ?? ""}`.trim();
        return {
          log: `${W} questions ${name}. ${ok ? "It works." : "Rejected."}`,
          beats: [
            { who: actor, text: say, exhibit: it ? { item: it, mode: "show" } : null },
            J(ok ? `A fair point. From now on, ${name}'s word counts for half.` : "No. That doesn't show any bias.", { tone: ok ? "yes" : "no", exhibit: it ? { item: it, mode: ok ? "noted" : "no" } : null }),
          ],
        };
      }
      if (ev.status === "admitted") {
        const it = item(ev.subject);
        return { log: "The judge accepts the evidence.", beats: [J(pick(ADMIT, seed).replace("{S}", capFirst(shortOf(it))), { tone: "yes", exhibit: { item: it, mode: "ok" } })] };
      }
      if (rules.has("TURN-CAP")) return { log: `${W} is out of turns.`, beats: [J(`${W} has used all their turns. Let's move on.`)] };
      if (rules.has("STALL-1")) return { log: `${W}'s turn ends.`, beats: [J(`${W} keeps passing, so their turn is over.`)] };
      if (rules.has("CONTEMPT-1")) return { log: `${W} is stopped for breaking rules.`, beats: [J(`${W}, you have broken the rules too often. Your turn is over.`, { tone: "no", gavel: 2 })] };
      break;
    }
    case "violation": {
      if (a?.type === "motion_directed_verdict") {
        return { log: `${Side(actor)} breaks a rule.`, beats: [{ who: actor, text: pick(WILD, seed) }, J("Only the Defender may ask for that, and only at the right time. Request denied, and you lose a point.", { tone: "no", gavel: 1 })] };
      }
      return { log: `${Side(actor)} breaks a rule.`, beats: [{ who: actor, text: "Your Honour, I have something else to say!" }, J("That's not allowed right now. It counts as a pass, and you lose a point.", { tone: "no", gavel: 1 })] };
    }
    case "directed_verdict": {
      const m = ev.summary.match(/GRANTED on (\S+?)\.?$/);
      if (m) return { log: "The judge ends the trial early.", beats: [J(`There is no accepted evidence that ${lowerFirst(pointName(m[1]))}. This trial ends now.`, { tone: "no", gavel: 1 })] };
      return { log: "The trial goes on.", beats: [J("Request denied. There is enough evidence to keep going.")] };
    }
    case "watchdog":
      return { log: "The judge moves to a decision.", beats: [J("This has gone on long enough. It's time to decide.")] };
    case "verdict": {
      const v = verdictInfo();
      return { log: `Verdict: ${v.word}.`, verdict: true, beats: [J(`I have reached my verdict. ${v.word}. ${v.reason}`, { gavel: 3, shot: "verdict" })] };
    }
  }
  return { log: ev.summary, beats: [{ who: actor ?? "court", text: ev.summary }] };
}

function verdictInfo() {
  const v = S.trial.verdict;
  const pWins = ["guilty", "liable"].includes(v.outcome);
  const word = { guilty: "Guilty", not_guilty: "Not guilty", liable: "Must pay", not_liable: "Doesn't have to pay", directed_acquittal: "Case dismissed" }[v.outcome] ?? capFirst(v.outcome.replaceAll("_", " "));
  const dec = v.snapshot.elements.find((e) => e.element_id === v.decisive_element);
  let reason;
  if (pWins) reason = "The Accuser proved every point.";
  else if (v.outcome === "directed_acquittal") reason = `The Accuser had no accepted evidence that "${pointName(v.decisive_element)}".`;
  else if (dec) reason = `The Accuser didn't prove that "${pointName(dec.element_id)}". I was ${pct(dec.probability)} sure, and I needed ${pct(dec.threshold_probability)}.`;
  else reason = v.reason;
  return { pWins, word, reason };
}

/* ------------------------------------------------------------------ voices (Web Speech API) */

const Voice = (() => {
  const synth = window.speechSynthesis;
  let picks = null;
  function choose() {
    const all = synth?.getVoices().filter((v) => /^en/i.test(v.lang)) ?? [];
    if (!all.length) return null;
    const find = (...res) => res.map((re) => all.find((v) => re.test(v.name))).find(Boolean);
    const judge = find(/Google UK English Male/, /Daniel/, /George/, /Ryan/, /Guy/, /David/, /Male/i) ?? all[0];
    const p = find(/Google UK English Female/, /Sonia/, /Libby/, /Hazel/, /Samantha/, /Zira/, /Female/i) ?? all[1 % all.length];
    const d = find(/Google US English/, /Aria/, /Jenny/, /Mark/, /Alex/, /Karen/) ?? all[2 % all.length];
    return { bailiff: { v: judge, pitch: 1.0, rate: 0.95 }, court: { v: judge, pitch: 0.82, rate: 0.9 }, prosecution: { v: p, pitch: 1.05, rate: 0.98 }, defense: { v: d === p ? all[(all.indexOf(p) + 1) % all.length] : d, pitch: 0.95, rate: 0.98 } };
  }
  synth?.addEventListener?.("voiceschanged", () => { picks = choose(); });
  return {
    ok: !!synth,
    stop() { synth?.cancel(); },
    say(text, who, pace, name) {
      if (!synth) return Promise.resolve();
      picks ??= choose();
      return new Promise((resolve) => {
        const u = new SpeechSynthesisUtterance(text.replace(/[“”"]/g, ""));
        let pk = picks?.[who];
        if (who === "witness" && picks) { // vary voice and pitch per witness so each sounds like someone new
          const h = [...(name ?? "")].reduce((a, c) => a + c.charCodeAt(0), 0);
          const pool = [picks.prosecution, picks.defense, picks.court];
          pk = { ...pool[h % 3], pitch: 0.8 + (h % 7) * 0.08 };
        }
        if (pk?.v) u.voice = pk.v;
        u.pitch = pk?.pitch ?? 1;
        u.rate = Math.min(1.35, (pk?.rate ?? 1) * (0.85 + pace * 0.18));
        let done = false;
        const finish = () => { if (!done) { done = true; resolve(); } };
        u.onend = finish; u.onerror = finish;
        // Chrome sometimes never fires onend; never let the trial hang on it
        setTimeout(finish, 2500 + text.split(/\s+/).length * 520 / pace);
        synth.speak(u);
      });
    },
  };
})();

/* ------------------------------------------------------------------ landing: docket + brief */

function renderCases() {
  const box = $("#cases");
  box.replaceChildren(...B.cases.filter((c) => category(c) === S.filter).map((c) => {
    const t = splitTitle(c.title);
    return el("button", { class: "folder", "aria-pressed": String(c.id === S.caseId), onclick: () => selectCase(c.id), "data-id": c.id },
      el("span", { class: "tab" }, c.case_type === "civil" ? "Dispute" : "Accusation"),
      el("span", { class: "body" },
        el("h3", {}, t.name),
        t.parties && el("span", { class: "parties" }, t.parties),
        el("p", {}, CASE_PLAIN[c.id] ?? c.synopsis),
        el("span", { class: "meta" }, `${c.evidence.length} pieces of evidence · ${c.witnesses.length} witnesses`)));
  }));
  if (hasGsap && !reduced) gsap.from(box.children, { y: 40, rotate: () => gsap.utils.random(-2, 2), opacity: 0, duration: .7, stagger: .08, ease: "power3.out" });
}

function selectCase(id) {
  S.caseId = id;
  $$(".folder").forEach((f) => f.setAttribute("aria-pressed", String(f.dataset.id === id)));
  fixCombo("p");
  renderStyles();
  // next step: brief the lawyers, with the courtroom button right below
  const head = $("#brief-title");
  scrollTo({ top: head.getBoundingClientRect().top + scrollY - 90, behavior: reduced ? "auto" : "smooth" });
  if (hasGsap && !reduced) gsap.fromTo(".start-row", { y: 16, opacity: .4 }, { y: 0, opacity: 1, duration: .7, delay: .5, ease: "power3.out" });
}

const available = (p, d) => S.live || !!B.trials[`${S.caseId}|${p}|${d}|0`];

function renderStyles() {
  for (const [side, key] of [["prosecution", "p"], ["defense", "d"]]) {
    const col = $(`#style-${key}`);
    $$(".style-opt", col).forEach((n) => n.remove());
    for (const name of STYLE_ORDER) {
      const st = STYLE[name];
      const ok = side === "prosecution" ? STYLE_ORDER.some((o) => available(name, o)) : available(S.p, name);
      col.append(el("button", {
        class: "style-opt", type: "button", "aria-pressed": String(S[key] === name), disabled: !ok,
        title: ok ? null : "Not in the offline demo. Run the local server to try every pairing.",
        onclick: () => { S[key] = name; fixCombo(key); renderStyles(); },
      }, el("b", {}, st.label), el("small", {}, st.blurb), el("span", { class: "tick", "aria-hidden": "true" })));
    }
  }
  const ok = !!S.caseId && available(S.p, S.d);
  $("#start").disabled = !ok;
  $("#start-case").textContent = S.caseId ? splitTitle(C().title).name : "No case picked yet";
  $("#combo-note").textContent = !S.caseId ? "Pick a case first." : ok ? `A ${STYLE[S.p].label.toLowerCase()} Accuser against a ${STYLE[S.d].label.toLowerCase()} Defender.` : "That pairing isn't in the offline demo. Pick another style.";
}

function fixCombo(changed) {
  if (available(S.p, S.d)) return;
  if (changed === "p") S.d = STYLE_ORDER.find((o) => available(S.p, o)) ?? S.d;
  else S.p = STYLE_ORDER.find((o) => available(o, S.d)) ?? S.p;
}

/* ------------------------------------------------------------------ entering and leaving the courtroom */

async function enterCourt() {
  window.Sound?.unlock();
  const key = `${S.caseId}|${S.p}|${S.d}|0`;
  $("#start").disabled = true;
  try {
    S.trial = S.live
      ? await (await fetch(`${API}/trial`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: S.caseId, prosecution: S.p, defense: S.d, seed: 0 }) })).json()
      : B.trials[key];
  } catch { S.trial = B.trials[key]; }
  $("#start").disabled = false;
  if (!S.trial?.events) return;

  const c = C();
  $("#court-case").textContent = splitTitle(c.title).name;
  $("#verdict").hidden = true;
  buildMeters();
  $("#transcript").replaceChildren(...S.trial.events.map((ev, i) => {
    const n = narrate(ev);
    return el("li", { "data-i": i, hidden: true }, el("button", { onclick: () => { setAuto(false); present(i, false); } },
      el("span", { class: `s ${WHO[n.beats[0]?.who]?.[1] ?? "j"}` }), el("span", {}, n.log)));
  }));
  window.Sound?.unlock();
  const firstVisit = !S.visited;
  S.visited = true;
  if (firstVisit) window.Sound?.logo(); // the big opening sound, only the first time
  else window.Sound?.door();
  window.Sound?.score(firstVisit ? 8 : 2.5);
  Exhibit.hide(false);
  const court = $("#court");
  court.hidden = false;
  document.body.style.overflow = "hidden";
  window.Scene?.pause?.();
  window.Court3D?.reset();
  window.Court3D?.open();
  $("#leave-btn").focus({ preventScroll: true });
  showCaption("court", "All rise.", "");
  S.idx = 0;

  if (hasGsap && !reduced) {
    gsap.set(".door.l", { xPercent: 0 }); gsap.set(".door.r", { xPercent: 0 });
    gsap.set([".hud-top", ".hud-meters", ".caption", ".hud-bottom"], { opacity: 0 });
    await gsap.timeline()
      .to(".door.l", { xPercent: -100, duration: 1.6, ease: "power3.inOut", delay: .3 })
      .to(".door.r", { xPercent: 100, duration: 1.6, ease: "power3.inOut" }, "<")
      .to([".hud-top", ".hud-meters", ".caption", ".hud-bottom"], { opacity: 1, y: 0, stagger: .1, duration: .6 }, "-=.4");
  } else {
    $(".doors").hidden = true;
  }
  await wait(reduced ? 0 : firstVisit && window.Sound ? 5600 : 1200);
  if (!$("#court").hidden) setAuto(true);
}

function leaveCourt() {
  S.run++;
  setAuto(false);
  Voice.stop();
  window.Court3D?.close();
  window.Sound?.stopScore();
  window.Scene?.resume?.();
  $("#court").hidden = true;
  $(".doors").hidden = false;
  Exhibit.hide(false);
  document.body.style.overflow = "";
  $("#notes").hidden = true;
  $("#notes-btn").setAttribute("aria-expanded", "false");
  $("#court").classList.remove("show-meters");
}

/* ------------------------------------------------------------------ exhibits drawn as the real thing (data in artifacts.js) */

const SCENE = {
  shirt: '<svg viewBox="0 0 160 100"><path class="fill" d="M58 14l22 8 22-8 26 14-10 18-12-6v52H54V40l-12 6-10-18z"/><path d="M58 14l22 8 22-8 26 14-10 18-12-6v52H54V40l-12 6-10-18z"/><g class="dots"><circle cx="70" cy="50" r="2.5"/><circle cx="84" cy="58" r="2"/><circle cx="76" cy="66" r="3"/><circle cx="92" cy="47" r="2"/><circle cx="66" cy="74" r="2"/><circle cx="96" cy="70" r="2.5"/></g></svg>',
  kid: '<svg viewBox="0 0 160 100"><path d="M20 92h120M100 20h36v72h-36z"/><circle cx="62" cy="34" r="9"/><path class="red" d="M50 46h24l4 30H46z"/><path d="M54 76l-2 16M70 76l2 16"/></svg>',
  bike: '<svg viewBox="0 0 160 100"><circle cx="42" cy="66" r="22"/><circle cx="118" cy="66" r="22"/><path d="M42 66l26-34h34l16 34M68 32l14 34h-40M96 24h14M82 66l20-34"/></svg>',
  friends: '<svg viewBox="0 0 160 100"><circle class="fill" cx="128" cy="22" r="10"/><circle cx="56" cy="38" r="10"/><circle cx="96" cy="36" r="10"/><path d="M38 92c0-20 8-36 18-36s18 16 18 36M78 92c0-20 8-38 18-38s18 18 18 38M70 64l12-6"/><path d="M10 92h140"/></svg>',
  paws: '<svg viewBox="0 0 160 100"><g class="fill-all"><g transform="translate(24 66)"><ellipse rx="7" ry="6"/><circle cx="-8" cy="-9" r="3"/><circle cx="0" cy="-12" r="3"/><circle cx="8" cy="-9" r="3"/></g><g transform="translate(62 48) rotate(-10)"><ellipse rx="7" ry="6"/><circle cx="-8" cy="-9" r="3"/><circle cx="0" cy="-12" r="3"/><circle cx="8" cy="-9" r="3"/></g><g transform="translate(100 62) rotate(8)"><ellipse rx="7" ry="6"/><circle cx="-8" cy="-9" r="3"/><circle cx="0" cy="-12" r="3"/><circle cx="8" cy="-9" r="3"/></g></g><path d="M136 10v84M146 10v84M128 30h26M128 70h26"/></svg>',
  gate: '<svg viewBox="0 0 160 100"><path d="M8 92h144M14 30v62M30 30v62M46 30v62M62 26v66M118 26v66M134 30v62M150 30v62M8 46h54M118 46h36M8 76h54M118 76h36"/><path class="fill" d="M62 30l40-18v70l-40 10z"/><path d="M62 30l40-18v70l-40 10z"/></svg>',
  car: '<svg viewBox="0 0 160 100"><path d="M10 92h140"/><path class="fill" d="M34 70l10-24h62l16 24v14H34z"/><path d="M34 70l10-24h62l16 24v14H34zM50 50h24v18H44zM80 50h22l10 18H80z"/><circle cx="54" cy="84" r="8"/><circle cx="104" cy="84" r="8"/></svg>',
  helmet: '<svg viewBox="0 0 160 100"><circle cx="42" cy="70" r="20"/><circle cx="118" cy="70" r="20"/><path d="M42 70l24-30h32l20 30M66 40l14 30h-38"/><path class="fill" d="M84 22c0-10 22-10 22 0v6H84z"/><path d="M84 22c0-10 22-10 22 0v6H84z"/></svg>',
  drive: '<svg viewBox="0 0 160 100"><rect class="fill" x="36" y="20" width="88" height="62" rx="6"/><rect x="36" y="20" width="88" height="62" rx="6"/><circle cx="80" cy="50" r="18"/><circle cx="80" cy="50" r="3"/><path d="M98 66l14 8"/></svg>',
};

function renderArtifact(a) {
  const rows = (list, cls) => el("table", { class: cls }, el("tbody", {}, ...list.map((r, i) => el("tr", { class: i === a.mark ? "mark" : null }, ...r.map((c) => el("td", {}, c))))));
  switch (a.type) {
    case "note":
      return el("div", { class: "art note" }, el("p", {}, a.text));
    case "sms":
    case "chat":
      if (a.type === "chat") return el("div", { class: "art forum" }, el("p", { class: "site" }, a.site), el("p", { class: "user" }, a.user), el("p", {}, a.text));
      return el("div", { class: "art phone" }, el("p", { class: "contact" }, a.contact, el("small", {}, a.time)),
        ...a.msgs.map(([who, t]) => el("p", { class: `bubble ${who}` }, t)));
    case "receipt":
      return el("div", { class: "art receipt" }, el("p", { class: "shop" }, a.shop), el("p", { class: "date" }, a.date),
        rows(a.lines, "lines"), el("p", { class: "total" }, el("span", {}, "TOTAL"), el("span", {}, `$${a.total}`)));
    case "log":
      return el("div", { class: "art log" }, el("p", { class: "title" }, a.title), rows(a.rows, "rows"));
    case "ledger":
      return el("div", { class: "art ledger" }, el("p", { class: "title" }, a.title), rows(a.rows, "rows"), a.foot ? el("p", { class: "foot" }, a.foot) : null);
    case "cctv": {
      const frame = el("div", { class: "art cctv" }, el("p", { class: "osd" }, el("span", {}, `● ${a.cam}`), el("span", {}, a.time)));
      frame.insertAdjacentHTML("beforeend", SCENE[a.scene] ?? "");
      frame.append(el("p", { class: "cap" }, a.caption));
      return frame;
    }
    case "photo": {
      const ph = el("div", { class: "art photo" });
      ph.insertAdjacentHTML("beforeend", SCENE[a.scene] ?? "");
      ph.append(el("p", { class: "cap" }, a.caption));
      return ph;
    }
    case "ad":
      return el("div", { class: "art ad" }, el("p", { class: "title" }, a.title), el("p", { class: "price" }, a.price), el("p", {}, a.text));
    default: // doc: letters, memos, emails, forms
      return el("div", { class: "art doc" }, el("p", { class: "head" }, a.head), el("p", { class: "title" }, a.title),
        ...a.lines.map((l) => el("p", {}, l)), a.sign ? el("p", { class: "sign" }, a.sign) : null);
  }
}

/* ------------------------------------------------------------------ the exhibit card (HTML, paper style) */

const ART = {
  document: '<svg viewBox="0 0 80 100"><path class="fill" d="M14 6h36l16 16v72H14z"/><path d="M14 6h36l16 16v72H14z"/><path d="M50 6v16h16M24 40h32M24 52h32M24 64h24M24 76h28"/></svg>',
  digital_log: '<svg viewBox="0 0 110 90"><rect class="fill" x="8" y="8" width="94" height="60" rx="5"/><rect x="8" y="8" width="94" height="60" rx="5"/><path d="M42 82h26M55 68v14M20 24h40M20 36h60M20 48h30"/><circle cx="86" cy="24" r="4"/></svg>',
  physical: '<svg viewBox="0 0 90 100"><path class="fill" d="M12 22h66v70H12z"/><path d="M12 22h66v70H12zM12 22l8-14h50l8 14"/><path d="M12 38h66"/><path d="M28 60h34M28 72h22"/></svg>',
  financial_record: '<svg viewBox="0 0 80 100"><path class="fill" d="M16 6h48v84l-8-6-8 6-8-6-8 6-8-6-8 6z"/><path d="M16 6h48v84l-8-6-8 6-8-6-8 6-8-6-8 6z"/><path d="M26 24h28M26 36h28M26 48h18M44 64h12"/></svg>',
  testimony: '<svg viewBox="0 0 110 100"><circle class="fill" cx="36" cy="40" r="14"/><circle cx="36" cy="40" r="14"/><path d="M10 92c0-16 12-28 26-28s26 12 26 28"/><path d="M62 12h40v26H78l-10 10V38h-6z"/><path d="M70 22h24M70 30h16"/></svg>',
  expert: '<svg viewBox="0 0 100 100"><path d="M10 88h80M18 88V60M36 88V44M54 88V54M72 88V30"/><circle class="fill" cx="56" cy="34" r="18"/><circle cx="56" cy="34" r="18"/><path d="M69 47l16 16"/></svg>',
};
const STAMP = { ok: ["Accepted", "ok"], no: ["Thrown out", "no"], noted: ["Noted", "ok"] };

const Exhibit = {
  id: null, stamped: null,
  show(it, animate) {
    if (!it) return;
    const card = $("#exhibit"), fresh = this.id !== it.id || card.hidden;
    this.id = it.id;
    if (!fresh) return;
    this.stamped = null;
    const art = window.ARTIFACTS?.[it.id];
    card.className = `exhibit ${it.owner === "prosecution" ? "p" : "d"}${art ? " has-artifact" : ""}`;
    $("#ex-tag").textContent = `Exhibit ${it.id} · ${it.owner === "prosecution" ? "Accuser" : "Defender"}`;
    const box = $("#ex-art");
    box.replaceChildren();
    if (art) box.append(renderArtifact(art)); else box.innerHTML = ART[it.kind] ?? ART.document;
    $("#ex-kind").textContent = KIND[it.kind] ?? "Evidence";
    $("#ex-title").textContent = it.title;
    const f = flaws(it);
    $("#ex-flaw").textContent = f.length ? `Possible problem: ${f.join(", ")}` : "";
    $("#ex-stamp").hidden = true;
    card.hidden = false;
    if (!animate || !hasGsap || reduced) { if (hasGsap) gsap.set(card, { clearProps: "all" }); return; }
    window.Sound?.whoosh();
    const fromX = it.owner === "prosecution" ? -innerWidth * 0.6 : innerWidth * 0.3;
    gsap.fromTo(card, { x: fromX, y: 120, rotate: it.owner === "prosecution" ? -25 : 25, opacity: 0, scale: .7 },
      { x: 0, y: 0, rotate: it.owner === "prosecution" ? -2 : 2, opacity: 1, scale: 1, duration: .9, ease: "power3.out" });
    gsap.from(["#ex-art > *", "#ex-kind", "#ex-title", "#ex-flaw"], { y: 10, opacity: 0, stagger: .08, duration: .4, delay: .5 });
  },
  stamp(mode, animate) {
    const [label, cls] = STAMP[mode] ?? STAMP.ok;
    const s = $("#ex-stamp");
    s.textContent = label; s.className = `ex-stamp ${cls}`; s.hidden = false;
    if (this.stamped === mode) return;
    this.stamped = mode;
    if (!animate || !hasGsap || reduced) return;
    window.Sound?.stamp(cls === "ok");
    gsap.fromTo(s, { scale: 2.6, opacity: 0, rotate: -30 }, { scale: 1, opacity: 1, rotate: -12, duration: .32, ease: "power4.in" });
    gsap.fromTo("#exhibit", { y: 0 }, { y: 6, duration: .08, delay: .3, yoyo: true, repeat: 1 });
  },
  hide(animate) {
    const card = $("#exhibit");
    if (card.hidden) return;
    const mode = this.stamped;
    this.id = null; this.stamped = null;
    if (!animate || !hasGsap || reduced) { card.hidden = true; return; }
    // accepted exhibits are filed away; thrown-out ones drop off the screen
    const to = mode === "no" ? { y: innerHeight, rotate: 35, opacity: 0, duration: .8, ease: "power2.in" } : { x: -80, y: 260, scale: .25, opacity: 0, duration: .7, ease: "power2.in" };
    gsap.to(card, { ...to, onComplete: () => { card.hidden = true; gsap.set(card, { clearProps: "all" }); } });
  },
};

/* ------------------------------------------------------------------ the trial engine */

function buildMeters() {
  const c = C(), th = S.trial.verdict.snapshot.elements;
  $("#meters").replaceChildren(el("p", { class: "title" }, "How sure is the judge?"), ...c.elements.map((e) => {
    const t = th.find((x) => x.element_id === e.id)?.threshold_probability ?? .5;
    return el("div", { class: "meter", "data-el": e.id },
      el("div", { class: "meter-head" }, el("span", {}, pointName(e.id)), el("span", { class: "val" }, "50%")),
      el("div", { class: "meter-bar" }, el("div", { class: "meter-fill" }), el("div", { class: "meter-line", style: `left:calc(${t * 100}% - 1.5px)` })));
  }));
}

function statusAt(i) {
  const st = {};
  for (let k = 0; k <= i; k++) {
    const ev = S.trial.events[k];
    if (ev.subject && ev.status && item(ev.subject)) st[ev.subject] = ev.status;
  }
  return st;
}

function showCaption(who, text, aside, tone, label) {
  const [base, cls] = WHO[who] ?? WHO.court;
  const name = label ?? base;
  const w = $("#cap-who"), t = $("#cap-text"), a = $("#cap-aside");
  w.textContent = name; w.className = `who ${cls}`;
  t.replaceChildren(tone ? el("span", { class: tone }, text) : text);
  a.textContent = aside ?? "";
  if (hasGsap && !reduced) gsap.fromTo([w, t, a], { y: 10, opacity: 0 }, { y: 0, opacity: 1, duration: .45, stagger: .06, ease: "power2.out" });
}

/* Update everything that reflects "the state after event i" (instant, works in both directions). */
function syncState(i, forward) {
  const evs = S.trial.events, ev = evs[i];
  for (const m of $$(".meter")) {
    const p = ev.element_probabilities[m.dataset.el] ?? .5;
    const t = S.trial.verdict.snapshot.elements.find((e) => e.element_id === m.dataset.el)?.threshold_probability ?? .5;
    $(".meter-fill", m).style.width = `${p * 100}%`;
    const v = $(".val", m); v.textContent = `${pct(p)} sure`; v.classList.toggle("met", p >= t);
  }
  window.Court3D?.setBalance(ev.burden_index ?? .5);
  $("#court-phase").textContent = PHASE_NAME[ev.phase] ?? "";
  const st = statusAt(i);
  for (const [side, id] of [["prosecution", "#ev-p"], ["defense", "#ev-d"]]) {
    const own = C().evidence.filter((e) => e.owner === side);
    $(id).replaceChildren(...(own.length ? own.map((e) => {
      const s = st[e.id] ?? "unshown";
      const [label, cls] = { offered: ["Waiting for the judge", "wait"], admitted: ["Accepted", "ok"], excluded: ["Thrown out", "no"] }[s] ?? ["Not shown yet", ""];
      return el("li", { class: s }, el("span", { class: "ev-title" }, e.title), s !== "unshown" ? el("span", { class: `state ${cls}` }, label) : null);
    }) : [el("li", { class: "unshown" }, "No evidence")]));
  }
  $$("#transcript li").forEach((li, k) => { li.hidden = k > i; li.classList.toggle("current", k === i); });
  $("#progress-bar").style.width = `${(100 * (i + 1)) / evs.length}%`;
  $("#step-count").textContent = `${i + 1} / ${evs.length}`;
  // the 3D paper card follows the same exhibit as the HTML card
  const current = item(ev.action?.evidence_id ?? ev.subject ?? "");
  if (current && ev.action?.type === "present_evidence") window.Court3D?.exhibit(current, "offered", forward);
  window.Court3D?.syncExhibits(st, current?.id, forward);
}

/* Play event i: set the state, then perform its beats (camera, caption, voice). Resolves when done. */
async function present(i, forward = true) {
  const evs = S.trial.events;
  S.idx = Math.max(0, Math.min(evs.length - 1, i));
  const run = ++S.run;
  Voice.stop();
  $("#verdict").hidden = true;
  $("#caption").hidden = false;
  const ev = evs[S.idx], n = narrate(ev);
  syncState(S.idx, forward);
  const pace = +$("#speed").value;
  if (!n.beats.some((b) => b.exhibit)) Exhibit.hide(forward);
  const onStand = witnessAt(S.idx), calling = n.beats.find((b) => b.call);
  if (!forward) onStand ? window.Court3D?.callWitness(onStand, false) : window.Court3D?.dismissWitness(false);
  else if (!onStand) window.Court3D?.dismissWitness(true);
  let arrival = Promise.resolve();
  for (const b of n.beats) {
    if (run !== S.run) return false;
    if (b.call && forward) arrival = window.Court3D?.callWitness(b.call, true) ?? arrival;
    if (b.waitWitness) { await Promise.race([arrival, wait(6000)]); if (run !== S.run) return false; }
    window.Court3D?.shot(b.shot ?? b.who, reduced ? 0 : 1.3);
    window.Court3D?.speak(b.who, true);
    if (b.exhibit) {
      const it = b.exhibit.item ?? (Exhibit.id && item(Exhibit.id));
      if (b.exhibit.mode === "show" || b.exhibit.mode === "keep") Exhibit.show(it, forward);
      else { Exhibit.show(it, false); setTimeout(() => Exhibit.stamp(b.exhibit.mode, forward), forward && !reduced ? 650 : 0); }
    }
    if (b.gavel) {
      window.Court3D?.gavel(b.gavel);
      for (let g = 0; g < b.gavel; g++) setTimeout(() => window.Sound?.gavel(), 320 + g * 470);
    }
    window.Court3D?.oath?.(!!b.oath);
    if (b.sting) window.Sound?.sting();
    showCaption(b.who, b.text, b.aside, b.tone, b.name);
    const words = (b.text + " " + (b.aside ?? "")).split(/\s+/).length;
    const readMs = Math.max(2400, words * 330) / pace;
    window.Sound?.duck(true);
    if (S.voice && Voice.ok) await Promise.all([Voice.say(b.text, b.who, pace, b.name), wait(900 / pace)]);
    else await wait(readMs);
    window.Court3D?.speak(b.who, false);
    window.Sound?.duck(false);
    if (run !== S.run) return false;
    await wait(450 / pace);
  }
  if (n.verdict && run === S.run) { setAuto(false); showVerdict(); }
  return run === S.run;
}

async function autoLoop() {
  while (S.auto) {
    const ok = await present(S.idx, true);
    if (!ok || !S.auto) return;
    if (S.idx >= S.trial.events.length - 1) { setAuto(false); return; }
    await wait(600 / +$("#speed").value);
    if (!S.auto) return;
    S.idx++;
  }
}

function setAuto(on) {
  const was = S.auto;
  S.auto = on;
  const b = $("#play-btn");
  b.classList.toggle("on", on);
  $(".lbl", b).textContent = on ? "Pause" : "Auto-play";
  if (on && !was) {
    if (S.idx >= S.trial.events.length - 1) S.idx = 0;
    autoLoop();
  }
  if (!on && was) { S.run++; Voice.stop(); Object.keys(WHO).forEach((w) => window.Court3D?.speak(w, false)); }
}

function step(d) {
  setAuto(false);
  present(S.idx + d, d > 0);
}

/* ------------------------------------------------------------------ verdict */

function showVerdict() {
  const v = verdictInfo(), box = $("#verdict"), word = $("#verdict-word");
  word.textContent = v.word;
  word.className = `verdict-word ${v.pWins ? "p" : "d"}`;
  $(".verdict-winner").textContent = `${v.pWins ? "The Accuser" : "The Defender"} wins this case.`;
  $(".verdict-reason").textContent = v.reason.replace("I was", "The judge was").replace("I needed", "needed");
  box.hidden = false;
  $("#caption").hidden = true;
  window.Sound?.stopScore();
  window.Sound?.ending(v.pWins);
  $("#v-replay").focus({ preventScroll: true });
  if (!hasGsap || reduced) return;
  gsap.timeline()
    .fromTo(box, { yPercent: -40, rotate: -3, opacity: 0 }, { yPercent: -50, rotate: 0, opacity: 1, duration: .7, ease: "back.out(1.4)" })
    .fromTo(word, { scale: 1.8, opacity: 0 }, { scale: 1, opacity: 1, duration: .5, ease: "power4.out" }, "-=.3")
    .fromTo([".verdict-winner", ".verdict-reason", ".verdict-actions"], { y: 12, opacity: 0 }, { y: 0, opacity: 1, stagger: .08, duration: .4 }, "-=.2");
}

/* ------------------------------------------------------------------ strategy */

function renderStrategy(cid) {
  const g = B.games[cid], box = $("#matrix");
  if (!g) { box.replaceChildren(el("p", { class: "muted" }, "No strategy data for this case.")); return; }
  const rows = g.row_strategies, cols = g.col_strategies;
  const pureKey = (mix) => Object.keys(mix).find((k) => mix[k] === 1);
  const eq = new Set(g.analysis.equilibria.filter((e) => e.pure).map((e) => `${pureKey(e.row_mix)}|${pureKey(e.col_mix)}`));
  const cell = Object.fromEntries(g.cells.map((c) => [`${c.row}|${c.col}`, c]));
  box.style.setProperty("--cols", cols.length);
  const kids = [el("div", { class: "h" }, ""), ...cols.map((c) => el("div", { class: "h col" }, `${styleOf(c).label} Defender`))];
  for (const r of rows) {
    kids.push(el("div", { class: "h row" }, `${styleOf(r).label} Accuser`));
    for (const c of cols) {
      const w = cell[`${r}|${c}`]?.prosecution_win_rate ?? 0;
      kids.push(el("div", { class: `cell${eq.has(`${r}|${c}`) ? " eq" : ""}` },
        el("span", { class: "bg", style: `transform:scaleY(${w})` }), el("b", {}, pct(w)), el("small", {}, "Accuser wins")));
    }
  }
  box.replaceChildren(...kids);
  if (hasGsap && !reduced) gsap.from($$(".cell .bg", box), { scaleY: 0, duration: 1, stagger: .1, ease: "power3.out" });
  const e = g.analysis.equilibria.find((x) => x.pure);
  const t = $("#takeaway");
  t.replaceChildren();
  if (e) t.append(el("b", {}, "The stable pick: "), `a ${styleOf(pureKey(e.row_mix)).label.toLowerCase()} Accuser against a ${styleOf(pureKey(e.col_mix)).label.toLowerCase()} Defender. Neither lawyer can do better by switching alone. Game theory calls this a Nash equilibrium.`);
  else t.append(el("b", {}, "No single best style here. "), "Each lawyer does best by mixing it up, so the other side can't predict them.");
}

/* ------------------------------------------------------------------ page motion */

function initMotion() {
  const nav = $("#nav");
  addEventListener("scroll", () => nav.classList.toggle("solid", scrollY > 40), { passive: true });
  if (!hasGsap || reduced) return;
  gsap.registerPlugin(ScrollTrigger);
  gsap.timeline({ delay: .1 })
    .from(".hero-title .line > span", { yPercent: 110, duration: 1.2, stagger: .14, ease: "power4.out" })
    .from([".hero-sub", ".hero .btn"], { y: 24, opacity: 0, duration: .8, stagger: .12, ease: "power3.out" }, "-=.8");
  gsap.to(".hero-title", { yPercent: -25, ease: "none", scrollTrigger: { trigger: ".hero", start: "top top", end: "bottom top", scrub: true } });
  const enter = (sel, trigger, extra = {}) => gsap.from(sel, { y: 28, opacity: 0, duration: .8, stagger: .08, ease: "power3.out", scrollTrigger: { trigger, start: "top 78%" }, ...extra });
  enter(".how .section-title", ".how");
  enter(".how-list li", ".how-list", { stagger: .12 });
  enter([".docket .section-title", ".docket .filters", ".docket .lede"], ".docket");
  enter([".brief .section-title", ".brief .lede"], ".brief");
  enter(".style-col", ".styles", { stagger: .12 });
  enter([".strategy .section-title", ".strategy .lede", ".strategy .select-label"], ".strategy");
  ScrollTrigger.create({ trigger: "#strategy", start: "top 70%", once: true, onEnter: () => renderStrategy($("#strat-case").value) });
}

/* ------------------------------------------------------------------ boot */

async function init() {
  if (!B) { document.body.prepend(el("p", { class: "noscript" }, "Could not load the case data (data/bundle.js).")); return; }
  $$(".filters .chip").forEach((b) => b.addEventListener("click", () => {
    S.filter = b.dataset.filter;
    $$(".filters .chip").forEach((x) => x.setAttribute("aria-selected", String(x === b)));
    renderCases();
  }));
  S.caseId = B.cases.find((c) => category(c) === "everyday")?.id ?? B.cases[0].id;
  renderCases();
  renderStyles();

  $("#start").addEventListener("click", enterCourt);
  $("#leave-btn").addEventListener("click", leaveCourt);
  $("#home-btn").addEventListener("click", () => { leaveCourt(); scrollTo({ top: 0, behavior: "instant" }); });
  $("#play-btn").addEventListener("click", () => setAuto(!S.auto));
  $("#next").addEventListener("click", () => step(1));
  $("#back").addEventListener("click", () => step(-1));
  $("#voice-btn").addEventListener("click", (e) => {
    S.voice = !S.voice;
    e.currentTarget.setAttribute("aria-pressed", String(S.voice));
    e.currentTarget.textContent = S.voice ? "Voices on" : "Voices off";
    if (!S.voice) Voice.stop();
  });
  if (!Voice.ok) { S.voice = false; $("#voice-btn").hidden = true; }
  const vol = $("#music-vol");
  if (window.Sound) {
    vol.value = Math.round(window.Sound.volume * 100);
    vol.addEventListener("input", () => { window.Sound.volume = vol.value / 100; });
  } else vol.closest("label").hidden = true;
  $("#notes-btn").addEventListener("click", (e) => {
    const open = $("#notes").hidden;
    $("#notes").hidden = !open;
    e.currentTarget.setAttribute("aria-expanded", String(open));
    $("#court").classList.toggle("show-meters", open);
  });
  $("#v-replay").addEventListener("click", () => { $("#verdict").hidden = true; Exhibit.hide(false); window.Sound?.score(0.5); window.Court3D?.reset(); S.idx = 0; window.Court3D?.shot("wide"); setAuto(true); });
  $("#v-styles").addEventListener("click", () => { leaveCourt(); $("#brief").scrollIntoView({ behavior: reduced ? "auto" : "smooth" }); });
  $("#v-cases").addEventListener("click", () => { leaveCourt(); $("#docket").scrollIntoView({ behavior: reduced ? "auto" : "smooth" }); });
  addEventListener("keydown", (e) => {
    if ($("#court").hidden || e.target.closest("select")) return;
    if (e.key === "Escape") leaveCourt();
    else if (e.key === "ArrowRight") step(1);
    else if (e.key === "ArrowLeft") step(-1);
    else if (e.key === " " && !e.target.closest("button")) { e.preventDefault(); setAuto(!S.auto); }
  });

  const sc = $("#strat-case");
  sc.replaceChildren(...B.cases.filter((c) => B.games[c.id]).map((c) => el("option", { value: c.id }, splitTitle(c.title).name)));
  const varied = B.cases.find((c) => new Set(B.games[c.id]?.cells.map((x) => x.prosecution_win_rate)).size > 1);
  if (varied) sc.value = varied.id;
  sc.addEventListener("change", () => renderStrategy(sc.value));
  initMotion();
  if (!hasGsap || reduced) renderStrategy(sc.value);
  if (API) { // a live server unlocks every style pairing
    try {
      const ctrl = new AbortController(), t = setTimeout(() => ctrl.abort(), 1500);
      S.live = (await fetch(`${API}/health`, { signal: ctrl.signal })).ok;
      clearTimeout(t);
    } catch { S.live = false; }
    if (S.live) renderStyles();
  }
}

init();
