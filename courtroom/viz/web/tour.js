/* Guided tour for the home page and the strategy lab: a spotlight walk-through plus a one-screen map ("Guide" in the nav).
 *
 * - Plain DOM, no dependencies; it points at the real controls, so it cannot drift away from what is on the page.
 * - A step whose element is absent or hidden is skipped. On the hosted site (no server) the live-only controls are not on
 *   the page, so their steps drop out and the counter adjusts.
 * - It opens by itself once per browser per page (remembered in localStorage, marked as soon as it opens). "Guide" in the
 *   nav opens the map and can start the tour again at any time. It never opens over the courtroom or a shared #watch link.
 * - It speaks no lines, so no voice clip is involved.
 */
(function () {
  "use strict";
  const LAB = document.body.classList.contains("lab-page");
  const KEY = LAB ? "courtroom-tour-lab-v3" : "courtroom-tour-home-v3";

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
  const q = (sel) => (sel ? document.querySelector(sel) : null);
  const shown = (n) => Boolean(n) && n.getClientRects().length > 0 && getComputedStyle(n).visibility !== "hidden";
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* target: what to spotlight (none = a centred card). needs: a selector that must be on the page, or the step is skipped. */
  const HOME = [
    { title: "Two AI lawyers, one fixed judge", body: "This short tour points at each part of the page and says what it does. It takes about a minute. Skip it any time, and bring it back with Guide at the top." },
    { target: "#how", title: "How a trial works", body: "The Accuser has to prove each point; the Defender pokes holes. The judge is a fixed rulebook, not an AI, so the same case with the same choices always gives the same verdict." },
    { target: "#cases", title: "Pick a case", body: "Each folder is a made-up case. Click one to choose it. Your choice also drives the Which style wins section further down." },
    { target: "#surprise-row", title: "Surprise me", body: "Searches generated cases for one where the lawyers' styles really change the verdict, then picks it for you. It needs the local server, so it is missing on the hosted site." },
    { target: "#style-p", title: "Choose the lawyers' styles", body: "The Accuser and the Defender each get one of four styles: Bold, Careful, Smart or Wild. Change either one and the trial changes." },
    { target: "#live-panel .pill.rec", title: "RECORDED: replaying saved trials", body: "On the hosted site every trial was run earlier and is replayed, and the number tables are stored results. The next steps describe what the local server adds." },
    { target: "#live-panel .live-head", title: "The LIVE badge", body: "LIVE means the local server is on and every trial is computed now, not replayed. Inside the courtroom the badge shows LIVE or RECORDED for the trial you are watching." },
    { target: "#live-panel .live-cell:nth-child(1)", needs: "#live-seed", title: "The seed box", body: "The seed is the luck of the draw. Same seed, same trial, every time. Type a number or press New seed to see the same lawyers get a different draw." },
    { target: "#live-panel .live-cell:nth-child(2)", needs: "#live-surprises", title: "Courtroom surprises", body: "Tick this and a witness may not turn up, a digital record may lack its certificate, or a witness may turn hostile. It is off by default, and the Which style wins table switches to its surprise results too." },
    { target: "#matters-box", title: "Does strategy matter here?", body: "A rating for the case you picked: decided by the evidence, by the lawyers, or by the luck of the seed. It is measured by replaying every pairing of Bold, Careful and Smart." },
    { target: "#edit-case", title: "Change this case (what-if)", body: "Edit an exhibit or a witness, run the trial again and watch whether the verdict moves. Your edited copy is labelled as edited and never changes the recorded cases." },
    { target: "#start", title: "Enter the courtroom", body: "Opens the 3D courtroom and plays the trial step by step, with voices and music. Use the arrow keys to step and Space to pause." },
    { needs: "#live-seed", title: "Run it again and compare", body: "In the courtroom, the badge at the top has Run it again and compare. It plays the same trial a second time and shows that the two digests match, which is the proof that the engine is reproducible." },
    { needs: "#live-seed", title: "Why this verdict?", body: "After a live trial the verdict card has Why this verdict? It explains the judge's numbers in plain words: which exhibit moved which point and by how much." },
    { needs: "#live-seed", title: "What would flip it (the tipping point)", body: "The verdict card also lists the smallest single change to one exhibit or one witness that would flip the result. Press Try it to play the whole trial again with that change." },
    { target: "#strategy .matrix", title: "Which style wins", body: "Each box shows which side usually wins when the two styles meet, and how often, with what each side pays in small print. A gold ring is a stable pick. If every box is the same, the evidence decides the case, and the page says so." },
    { target: "#lab .btn", title: "The strategy lab", body: "The lab works out the game behind every case, chapter by chapter, in plain words. It has its own tour, and the Guide button there explains each chapter." },
  ];

  const LABT = [
    { title: "The strategy lab", body: "A trial is a game, and this page works it out one chapter at a time. This tour says what each chapter shows, how to read it and what to try. Skip it any time and bring it back with Guide." },
    { target: "#lab-case", title: "Pick a case", body: "Everything on the page is about the case chosen here. Change it and every chart and sentence updates." },
    { target: "#lab-live", needs: "#lab-run", title: "Run fresh trials", body: "With the local server on, this replays every pairing live instead of using the saved trial. Without it the page uses stored results and says so." },
    { target: "#lab-kpis", title: "Where the game settles", body: "The headline: which pair of styles is stable, what each side earns there and how often the Accuser wins. The chapters below show how it was found." },
    { target: "#ch-game-t", title: "1. A trial is a game", body: "Shows how a trial becomes a score: points for winning, minus the cost of evidence, minus penalties. Read each row left to right. Try picking different styles for each lawyer." },
    { target: "#ch-table-t", title: "2. Every pairing at once", body: "One box for every pair of styles, Accuser's payoff first. Underlined numbers are best replies and a gold ring is a Nash equilibrium. Try clicking a box to follow that trial in later chapters." },
    { target: "#ch-solve-t", title: "3. Solving the game", body: "Works out the stable outcome step by step, including when the answer is a random mix. Try opening Show the working." },
    { target: "#ch-br-t", title: "4. Best replies, drawn as a picture", body: "Each line is a lawyer's best reply to what the other does; where the lines cross, nobody wants to switch. Hover the chart for exact values." },
    { target: "#ch-land-t", title: "5. The payoff landscape", body: "A 3D model with one bar per pairing; a bar below the floor means that lawyer ends up worse off. Try dragging it to turn it, or use the buttons to show one lawyer at a time." },
    { target: "#ch-whatif-t", title: "6. Change the rules", body: "Sliders change what a win, a cost and a penalty are worth, and every chart on the page redraws. Try a harsher penalty and watch the stable pick; press reset to go back." },
    { target: "#ch-evo-t", title: "7. If lawyers copied what works", body: "A crowd of lawyers keeps copying whichever style scored more. Each line is a style's share over 300 rounds. Try Random start to see whether the ending depends on the start." },
    { target: "#ch-belief-t", title: "8. Inside one trial", body: "Opens a single trial: each line is one thing the Accuser must prove, and a jump is a piece of evidence landing. Hover to see what happened at that step." },
    { target: "#ch-matters-t", title: "9. Does strategy matter here?", body: "Rates every case as decided by the evidence, by the lawyers or by luck. Cases decided by the lawyers are the ones worth studying. The surprises box switches to the surprise results." },
    { target: "#ch-sure-t", title: "10. How sure are we?", body: "Confidence ranges and stability. Near 100% means the conclusion does not depend on which seeds were drawn; below about 80% treat it as shaky. Highlighted rows are rule changes that flipped it." },
    { target: "#ch-better-t", title: "11. Can a better lawyer be found?", body: "A search for a lawyer outside the four styles that beats the equilibrium, re-tested on fresh seeds. Read No better lawyer found as evidence, not proof." },
    { target: "#ch-classic-t", title: "12. Which classic game is this?", body: "Names each two-by-two corner of the table: prisoner's dilemma, stag hunt, battle of the sexes, chicken, matching pennies. Most corners match none, and the page says so plainly." },
    { target: "#ch-pareto-t", title: "13. Is the equilibrium efficient?", body: "A star marks a cell nothing beats for both sides, a diamond marks an equilibrium. A diamond without a star is one both sides could jointly improve on." },
    { target: "#ch-minimax-t", title: "14. What can each side guarantee?", body: "The most each lawyer can be sure of whatever the other does, and a check of the minimax theorem on the win-or-lose version of the game. If all boxes are equal, the evidence decides the case." },
    { target: "#ch-ahead-t", title: "15. Thinking ahead", body: "Searches the trial as a tree with minimax and alpha-beta, counting positions, then tests a lawyer that looks a few moves ahead. Open and close branches to follow the search. It is an exhibition, not certified." },
    { target: "#ch-analyst-t", title: "16. Ask the analyst", body: "Ask about anything that did not click. It needs a language model running locally, so it may say it is offline; it never changes a verdict or a certified number." },
    { target: "#ch-words-t", title: "17. The words, in one place", body: "A glossary of every term used on the page, in plain words. Come back here whenever a word is new." },
  ];

  const MAP_HOME = [
    ["How a trial works, the docket, Brief your lawyers, Enter the courtroom", "Watch one trial", "Recorded and live", "Certified: the engine and judge"],
    ["Seed box, LIVE badge, run it again and compare", "Prove a trial is reproducible", "Live only", "Extra"],
    ["Courtroom surprises, Surprise me, Change this case, Why this verdict, what would flip it", "Explore and stress-test", "Live only", "Extra, labelled"],
    ["Does strategy matter here?", "Rating of the case", "Live (fresh) or stored", "Certified when stored"],
    ["Which style wins", "Four-by-four result for the case", "Stored results", "Certified"],
    ["Strategy lab", "The game theory, chapter by chapter", "Stored, and live where marked", "Certified, with labelled extras"],
  ];
  const MAP_LAB = [
    ["Chapters 1 to 8", "The game, the table, the solution, the picture, the what-ifs", "One recorded trial per pairing, or live", "Certified method"],
    ["Chapters 9 and 10", "Does strategy matter, how sure are we", "Stored results", "Certified"],
    ["Chapter 11", "Can a better lawyer be found", "Stored results", "Certified search"],
    ["Chapters 12 to 14", "Classic games, efficiency, guarantees", "Stored results", "Certified"],
    ["Chapter 15", "Thinking ahead: the tree and the lookahead lawyer", "Stored results", "The lookahead lawyer is an exhibition"],
    ["Chapter 16", "Ask the analyst", "Needs a local language model", "Extra, never changes a number"],
  ];

  const T = { on: false, i: 0, steps: [], root: null, spot: null, card: null, from: null };
  const avail = (s) => (s.needs ? shown(q(s.needs)) : true) && (s.target ? shown(q(s.target)) : true);
  const courtOpen = () => { const c = q("#court"); return Boolean(c) && !c.hidden; };

  function build() {
    T.spot = h("div", { class: "tour-spot", "aria-hidden": "true" });
    T.card = h("div", { class: "tour-card", role: "dialog", "aria-modal": "true", "aria-labelledby": "tour-title", tabindex: "-1" });
    T.root = h("div", { class: "tour", hidden: true }, h("div", { class: "tour-shield", "aria-hidden": "true" }), T.spot, T.card);
    document.body.append(T.root);
    addEventListener("resize", place);
    addEventListener("scroll", place, { passive: true });
    document.addEventListener("keydown", (e) => {
      if (!T.on) return;
      if (e.key === "Escape") { e.preventDefault(); end(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); go(T.i + 1, 1); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); go(T.i - 1, -1); }
      else if (e.key === "Tab") {
        const f = [...T.card.querySelectorAll("button")];
        if (!f.length) return;
        const first = f[0], last = f.at(-1);
        if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
        else if (!e.shiftKey && (document.activeElement === last || !T.card.contains(document.activeElement))) { e.preventDefault(); first.focus(); }
      }
    }, true);
  }

  const remember = () => { try { localStorage.setItem(KEY, "seen"); } catch { /* storage unavailable */ } };

  function visibleSteps() { return (LAB ? LABT : HOME).filter(avail); }

  function start(from = 0) {
    if (courtOpen()) return;
    if (!T.root) build();
    if (T.on) return;
    remember();
    T.on = true;
    T.from = document.activeElement;
    T.root.hidden = false;
    document.body.classList.add("touring");
    go(from, 1);
  }

  function end() {
    if (!T.on) return;
    T.on = false;
    T.root.hidden = true;
    document.body.classList.remove("touring");
    (T.from?.isConnected ? T.from : q("#guide-btn"))?.focus({ preventScroll: true });
  }

  function go(i, dir) {
    T.steps = visibleSteps(); // recomputed each time: the page may have gone live, or a section may have changed
    if (i < 0) i = 0;
    if (i >= T.steps.length) return end();
    T.i = i;
    const s = T.steps[i], target = s.target ? q(s.target) : null;
    if (target) target.scrollIntoView({ block: target.getBoundingClientRect().height > innerHeight * 0.55 ? "start" : "center", behavior: reduced ? "auto" : "smooth" });
    render(s);
    place();
    setTimeout(place, 450);
    return dir;
  }

  function mapTable() {
    return h("table", { class: "tour-map" },
      h("thead", {}, h("tr", {}, ["Part", "What it does", "Where it works", "Certified or extra"].map((t) => h("th", {}, t)))),
      h("tbody", {}, (LAB ? MAP_LAB : MAP_HOME).map((r) => h("tr", {}, r.map((c, k) => h(k ? "td" : "th", { scope: k ? null : "row" }, c))))));
  }

  function render(s) {
    const n = T.steps.length, i = T.i, first = i === 0, last = i === n - 1;
    const acts = [];
    if (first) acts.push(h("button", { type: "button", class: "tour-btn ghost", "data-act": "end" }, "Skip for now"));
    else acts.push(h("button", { type: "button", class: "tour-btn ghost", "data-act": "back" }, "Back"));
    acts.push(h("button", { type: "button", class: "tour-btn primary", "data-act": last ? "end" : "next" }, first ? "Show me around" : last ? "Done" : "Next"));
    T.card.classList.toggle("centered", !s.target);
    T.card.classList.toggle("wide", first);
    T.card.replaceChildren(...[
      h("div", { class: "tour-top" }, h("span", { class: "tour-kicker" }, first ? "Guide" : `Step ${i} of ${n - 1}`), h("button", { type: "button", class: "tour-x", "data-act": "end", "aria-label": "Close the guide" }, "×")),
      h("h2", { id: "tour-title" }, s.title),
      h("p", {}, s.body),
      first ? h("p", { class: "tour-map-h" }, "One-screen map: which part does what") : null,
      first ? mapTable() : null,
      h("div", { class: "tour-actions" }, acts)].filter(Boolean));
    T.card.querySelectorAll("[data-act]").forEach((b) => b.addEventListener("click", () => {
      const a = b.dataset.act;
      if (a === "next") go(T.i + 1, 1); else if (a === "back") go(T.i - 1, -1); else end();
    }));
    (T.card.querySelector('[data-act="next"]') ?? T.card.querySelector(".tour-btn.primary"))?.focus({ preventScroll: true });
  }

  function place() {
    if (!T.on) return;
    const s = T.steps[T.i], target = s?.target ? q(s.target) : null;
    const vw = document.documentElement.clientWidth, vh = innerHeight;
    if (!target || !shown(target)) { T.spot.style.cssText = `top:${vh / 2}px;left:${vw / 2}px;width:0;height:0;`; T.card.style.cssText = ""; return; }
    const pad = 8, r = target.getBoundingClientRect();
    const top = Math.max(r.top - pad, 4), left = Math.max(r.left - pad, 4), bottom = Math.min(r.bottom + pad, vh - 4), right = Math.min(r.right + pad, vw - 4);
    T.spot.style.cssText = `top:${top}px;left:${left}px;width:${Math.max(0, right - left)}px;height:${Math.max(0, bottom - top)}px;`;
    if (vw <= 640) { T.card.style.cssText = ""; return; }
    const cw = T.card.offsetWidth, ch = T.card.offsetHeight, gap = 16, m = 16;
    let y, x;
    if (vh - bottom - gap >= ch + m) y = bottom + gap;
    else if (top - gap >= ch + m) y = top - gap - ch;
    else y = Math.max(m, vh - ch - m);
    x = Math.min(Math.max(r.left + r.width / 2 - cw / 2, m), vw - cw - m);
    T.card.style.cssText = `top:${Math.round(y)}px;left:${Math.round(x)}px;`;
  }

  /* the nav entry, on both pages */
  function addGuide() {
    const nav = q(".nav nav");
    if (!nav || q("#guide-btn")) return;
    const b = h("a", { href: "#guide", id: "guide-btn", class: "nav-guide", role: "button", onclick: (e) => { e.preventDefault(); start(0); } }, "Guide");
    const cta = nav.querySelector(".nav-cta");
    nav.insertBefore(b, cta);
  }

  addGuide();
  window.Tour = { start, end, steps: visibleSteps, key: KEY };

  let seen = null;
  try { seen = localStorage.getItem(KEY); } catch { /* storage unavailable: treat as unseen but open only once per page load */ }
  if (!seen && !location.hash.startsWith("#watch=") && !window.COURTROOM_WATCH) setTimeout(() => { if (!T.on && !courtOpen()) start(0); }, 900);
})();
