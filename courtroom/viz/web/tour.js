/* Guided tour: a spotlight walk-through that opens on a visitor's first landing.
 * It drives the real UI (switches tabs, points at live controls) instead of showing screenshots,
 * so it can never drift out of date. Skippable at any point; remembered in localStorage;
 * replayable from the header button or by opening the page with #tour.
 * Depends on app.js globals: $, el, activateTab, stop, S.
 */
"use strict";

const TOUR_KEY = "courtroom-tour-v2";

/* Each step: tab to open, element to spotlight (null = centred card), copy, optional hooks.
 * Steps whose target isn't visible (e.g. live-only controls in the offline demo) are skipped automatically. */
const TOUR_STEPS = [
  {
    tab: "overview", target: null, kicker: "Welcome",
    title: "Two AI lawyers. One rulebook judge.",
    body: "This tour shows you how to watch a trial and how to read the result. It takes about a minute, and you can skip it at any time.",
    welcome: true,
  },
  {
    tab: "overview", target: ".tabs", kicker: "Getting around",
    title: "Six tabs, one case folder",
    body: "Each tab is one part of the case. You can switch between them at any time and nothing is lost. Each tab also has its own link you can share.",
  },
  {
    tab: "overview", target: "#replay", kicker: "Overview",
    title: "A real trial, replayed",
    body: "This card replays a trial from the simulator. The bars show how sure the judge is of each point the prosecution has to prove.",
  },
  {
    tab: "courtroom", target: "#setup", kicker: "Step 1 · Set up",
    title: "Pick a case and two styles",
    body: "Choose a fictional case, then how each lawyer plays: aggressive, careful, adaptive or chaotic. The trial reloads as soon as you change anything.",
  },
  {
    tab: "courtroom", target: ".player", kicker: "Step 2 · Watch",
    title: "Play, pause and step through",
    body: "Press play to watch the trial unfold, or step one move at a time. Drag the slider to jump anywhere.",
    keys: true,
  },
  {
    tab: "courtroom", target: "#now", kicker: "Step 2 · Watch",
    title: "What's happening right now",
    body: "Every move is explained in plain English: who acted, what evidence was involved, and how the judge ruled.",
  },
  {
    tab: "courtroom", target: ".meters", kicker: "The key idea",
    title: "How sure is the judge?",
    body: "Each bar is one point that has to be proven. The thin line is the bar it must clear. If even one point stays short of its line, the accused wins.",
  },
  {
    tab: "courtroom", target: ".evidence", kicker: "Evidence",
    title: "Both sides' evidence",
    body: "You can see hidden flaws here, but the lawyers can't. Each one has to spot the other side's flaws and object, and a wrong objection costs a penalty.",
  },
  {
    tab: "verdict", target: "#ruling", kicker: "Step 3 · Understand",
    title: "Why the trial ended that way",
    body: "The verdict tab breaks the result down point by point, showing which exhibit pushed the judge which way and by how much.",
  },
  {
    tab: "strategy", target: "#styles-body", kicker: "Strategy",
    title: "Which style wins?",
    body: "The case is replayed for every pairing of styles. Outlined cells are where both sides end up if each plays its best response.",
  },
  {
    tab: "judge", target: ".flow", kicker: "The judge",
    title: "No AI in the judge's chair",
    body: "The judge follows fixed, written rules. Same case, same choices, same verdict, every time.",
  },
  {
    tab: null, target: ".header-tools", kicker: "Make it yours",
    title: "Extra detail, dark mode and this tour",
    body: "Turn on Technical details to see rule IDs, the lawyers' reasoning and exact numbers. The ? button replays this tour whenever you want it.",
  },
  {
    tab: "courtroom", target: null, kicker: "You're ready",
    title: "Start your first trial",
    body: "Pick a case and two styles, then press Start trial. If you're not sure where to begin, an aggressive prosecution against a careful defense makes a good first match.",
    finale: true,
  },
];

const T = { on: false, i: 0, steps: [], root: null, spot: null, card: null, raf: 0, lastFocus: null, returnTab: null };

const tourVisible = (node) => Boolean(node) && node.getClientRects().length > 0 && getComputedStyle(node).visibility !== "hidden";
const tourSmooth = () => (matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth");

function tourBuild() {
  T.root = el("div", { class: "tour", hidden: true });
  T.spot = el("div", { class: "tour-spot", "aria-hidden": "true" });
  T.card = el("div", { class: "tour-card", role: "dialog", "aria-modal": "true", "aria-labelledby": "tour-title", "aria-describedby": "tour-body", tabindex: "-1" });
  const shield = el("div", { class: "tour-shield", "aria-hidden": "true" });
  // clicking the dimmed page doesn't close the tour by accident, it nudges the card instead
  shield.addEventListener("click", () => {
    T.card.classList.remove("nudge");
    void T.card.offsetWidth;
    T.card.classList.add("nudge");
  });
  T.root.append(shield, T.spot, T.card);
  document.body.append(T.root);
  document.addEventListener("keydown", tourKeys, true);
  window.addEventListener("resize", tourQueue);
  window.addEventListener("scroll", tourQueue, { passive: true });
}

function tourStart({ from = 0 } = {}) {
  if (!T.root) tourBuild();
  if (T.on) return;
  stop();
  T.on = true;
  T.lastFocus = document.activeElement;
  T.returnTab = S.tab;
  T.steps = TOUR_STEPS;
  T.root.hidden = false;
  document.body.classList.add("touring");
  for (const node of document.querySelectorAll("body > :not(.tour, script, .sprite)")) node.inert = true;
  tourGo(from);
}

function tourEnd({ finished = false, toTab } = {}) {
  if (!T.on) return;
  T.on = false;
  try { localStorage.setItem(TOUR_KEY, finished ? "done" : "skipped"); } catch { /* storage unavailable */ }
  for (const node of document.querySelectorAll("body > [inert]")) node.inert = false;
  document.body.classList.remove("touring");
  T.root.classList.add("leaving");
  setTimeout(() => { T.root.hidden = true; T.root.classList.remove("leaving"); }, 220);
  if (location.hash === "#tour") history.replaceState(null, "", `#${toTab ?? S.tab}`);
  if (toTab) activateTab(toTab, { push: true });
  const back = toTab === "courtroom" ? $("#case") : T.lastFocus?.isConnected ? T.lastFocus : $("#tour-btn");
  back?.focus({ preventScroll: true });
}

function tourStepAvailable(step) {
  if (!step.target) return true;
  if (step.tab && step.tab !== S.tab) activateTab(step.tab);
  return tourVisible($(step.target));
}

function tourGo(i, dir = 1) {
  // walk past steps whose target isn't on the page in this mode (e.g. live-only controls)
  while (i >= 0 && i < T.steps.length && !tourStepAvailable(T.steps[i])) i += dir;
  if (i < 0) i = 0;
  if (i >= T.steps.length) return tourEnd({ finished: true });
  T.i = i;
  const step = T.steps[i];
  if (step.tab && step.tab !== S.tab) activateTab(step.tab);
  const target = step.target && $(step.target);
  T.root.classList.toggle("centered", !target);
  if (target) {
    const r = target.getBoundingClientRect();
    // on phones the card is a bottom sheet, so keep the target up top where the sheet can't cover it
    const top = r.height > window.innerHeight * 0.55 || document.documentElement.clientWidth <= 640;
    target.scrollIntoView({ block: top ? "start" : "center", behavior: tourSmooth() });
  } else {
    window.scrollTo({ top: 0, behavior: tourSmooth() });
  }
  tourRenderCard(step);
  tourQueue();
  // smooth scrolling moves the target after we measure it; re-place once it settles
  setTimeout(tourQueue, 380);
}

function tourRenderCard(step) {
  const n = T.steps.length, i = T.i;
  const dots = el("ol", { class: "tour-dots", "aria-hidden": "true" },
    T.steps.map((_, j) => el("li", { class: j === i ? "on" : j < i ? "done" : "" })));
  const actions = [];
  if (step.welcome) {
    actions.push(el("button", { type: "button", class: "btn quiet small", "data-act": "skip" }, "Skip for now"));
    actions.push(el("button", { type: "button", class: "btn primary small", "data-act": "next" }, "Show me around", icon("i-arrow")));
  } else if (step.finale) {
    actions.push(el("button", { type: "button", class: "btn quiet small", "data-act": "back" }, "Back"));
    actions.push(el("button", { type: "button", class: "btn primary small", "data-act": "finish" }, "Start a trial", icon("i-arrow")));
  } else {
    actions.push(el("button", { type: "button", class: "tour-skip", "data-act": "skip" }, "Skip tour"));
    actions.push(el("button", { type: "button", class: "btn quiet small", "data-act": "back", disabled: i === 0 }, "Back"));
    actions.push(el("button", { type: "button", class: "btn primary small", "data-act": "next" }, i === n - 2 ? "Finish" : "Next", icon("i-arrow")));
  }
  T.card.classList.toggle("is-welcome", Boolean(step.welcome || step.finale));
  // replaceChildren (unlike el) turns null into the text "null", so optional parts are filtered out
  T.card.replaceChildren(...[
    el("div", { class: "tour-top" },
      el("span", { class: "tour-kicker" }, step.kicker),
      step.welcome || step.finale ? null : el("span", { class: "tour-count" }, `${i} of ${n - 2}`),
      step.finale ? null : el("button", { type: "button", class: "tour-x", "data-act": "skip", "aria-label": "Skip the tour" },
        svg("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" }))),
    step.welcome ? el("div", { class: "tour-mark", "aria-hidden": "true" }, el("i"), el("i")) : null,
    el("h2", { id: "tour-title" }, step.title),
    el("p", { id: "tour-body" }, step.body),
    step.keys ? el("p", { class: "tour-keys" }, "Keyboard: ", el("kbd", {}, "←"), " ", el("kbd", {}, "→"), " to step, ", el("kbd", {}, "Space"), " to play or pause.") : null,
    step.welcome ? el("p", { class: "tour-hint" }, "You can replay this tour any time with the ? button at the top.") : null,
    el("div", { class: "tour-foot" }, step.welcome || step.finale ? null : dots, el("div", { class: "tour-actions" }, actions)),
  ].filter(Boolean));
  T.card.querySelector(".tour-x svg")?.append(svg("path", { d: "M6 6l12 12M18 6 6 18" }));
  T.card.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => tourAct(b.dataset.act)));
  T.card.classList.remove("swap");
  void T.card.offsetWidth;
  T.card.classList.add("swap");
  (T.card.querySelector('[data-act="next"], [data-act="finish"]') ?? T.card).focus({ preventScroll: true });
}

function tourAct(act) {
  if (act === "next") tourGo(T.i + 1, 1);
  else if (act === "back") tourGo(T.i - 1, -1);
  else if (act === "skip") tourEnd({ toTab: T.i === 0 ? T.returnTab : undefined });
  else if (act === "finish") tourEnd({ finished: true, toTab: "courtroom" });
}

function tourQueue() {
  if (!T.on) return;
  cancelAnimationFrame(T.raf);
  T.raf = requestAnimationFrame(tourPlace);
}

function tourPlace() {
  const step = T.steps[T.i], target = step?.target && $(step.target);
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  if (!target) {
    T.spot.style.cssText = `top:${vh / 2}px; left:${vw / 2}px; width:0; height:0;`;
    T.card.style.cssText = "";
    return;
  }
  const pad = 8, r = target.getBoundingClientRect();
  const top = Math.max(r.top - pad, 4), left = Math.max(r.left - pad, 4);
  const bottom = Math.min(r.bottom + pad, vh - 4), right = Math.min(r.right + pad, vw - 4);
  T.spot.style.cssText = `top:${top}px; left:${left}px; width:${Math.max(0, right - left)}px; height:${Math.max(0, bottom - top)}px;`;

  // phones: the card docks to the bottom of the screen as a sheet (handled in CSS)
  if (vw <= 640) { T.card.style.cssText = ""; return; }
  const cw = T.card.offsetWidth, ch = T.card.offsetHeight, gap = 16, m = 16;
  const below = vh - bottom - gap, above = top - gap;
  let y, x;
  if (below >= ch + m) y = bottom + gap;
  else if (above >= ch + m) y = top - gap - ch;
  else {
    // target fills the screen: sit beside it if there's room, else float over its lower part
    const rightRoom = vw - right - gap, leftRoom = left - gap;
    if (rightRoom >= cw + m) { x = right + gap; y = Math.min(Math.max(top, m), vh - ch - m); }
    else if (leftRoom >= cw + m) { x = left - gap - cw; y = Math.min(Math.max(top, m), vh - ch - m); }
    else y = vh - ch - m;
  }
  if (x === undefined) x = Math.min(Math.max(r.left + r.width / 2 - cw / 2, m), vw - cw - m);
  T.card.style.cssText = `top:${Math.round(y)}px; left:${Math.round(x)}px;`;
}

function tourKeys(e) {
  if (!T.on) return;
  if (e.key === "Escape") { e.preventDefault(); tourEnd(); return; }
  if (e.key === "Tab") {
    // keep focus inside the tour card
    const f = [...T.card.querySelectorAll("button:not(:disabled)")];
    if (!f.length) return;
    const first = f[0], last = f.at(-1);
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    else if (!T.card.contains(document.activeElement)) { e.preventDefault(); first.focus(); }
    return;
  }
  if (e.target.closest?.("button") && (e.key === "Enter" || e.key === " ")) return;
  if (e.key === "ArrowRight") { e.preventDefault(); e.stopPropagation(); tourGo(T.i + 1, 1); }
  else if (e.key === "ArrowLeft") { e.preventDefault(); e.stopPropagation(); if (T.i > 0) tourGo(T.i - 1, -1); }
}

function tourInit() {
  $("#tour-btn").addEventListener("click", () => tourStart());
  window.addEventListener("hashchange", () => { if (location.hash === "#tour") tourStart(); });
  let seen = null;
  try { seen = localStorage.getItem(TOUR_KEY); } catch { /* storage unavailable: show the tour */ }
  // every first-time visitor gets the tour, whichever tab link they arrived on
  if (location.hash === "#tour" || !seen) setTimeout(() => tourStart(), 250);
}

tourInit();
