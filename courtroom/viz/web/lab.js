/* The strategy lab (lab.html): a guided, chapter-by-chapter walk through the game theory of any case.
 * Every number comes from trial ledgers (data/bundle.js, or fresh trials from the local server) run through
 * lab-math.js. Each chapter explains the idea in plain words, shows a chart, says what the chart means for the
 * selected case, and offers the working. The analyst chat (Ollama, via the local server) only explains and
 * steers; it never makes numbers.
 */
(function () {
  "use strict";
  const B = window.COURTROOM_BUNDLE, M = window.LabMath, root = document.getElementById("lab-root");
  if (!B || !M || !root) return;

  const STY = ["aggressive", "conservative", "adaptive", "reckless"];
  const NAME = { aggressive: "Bold", conservative: "Careful", adaptive: "Smart", reckless: "Wild" };
  const BLURB = {
    aggressive: "Shows every piece of evidence, even weak ones, and objects a lot.",
    conservative: "Shows only strong evidence and objects only when sure.",
    adaptive: "Watches the other lawyer and changes plan to match.",
    reckless: "Grabs evidence at random, objects on a whim and sometimes breaks the rules.",
  };
  // chart marks, checked for colour-blind separation on the paper surface (light mode): fixed order, one per style
  const HUE = { aggressive: "#c4502f", conservative: "#0e8f85", adaptive: "#a87a12", reckless: "#6d5bd0" };
  const P_HUE = "#c4502f", D_HUE = "#0e8f85", GOLD = "#a87a12", EL_HUE = ["#6d5bd0", "#a87a12", "#0e8f85", "#c4502f"];
  const API = location.protocol.startsWith("http") ? "/api" : null;
  const gsap = window.gsap;
  const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const NS = "http://www.w3.org/2000/svg";

  const $ = (sel, r = document) => r.querySelector(sel);
  function h(tag, attrs = {}, ...kids) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const c of kids.flat(3)) if (c != null && c !== false && c !== "") n.append(c);
    return n;
  }
  function s(tag, attrs = {}, ...kids) {
    const n = document.createElementNS(NS, tag);
    for (const [k, v] of Object.entries(attrs)) if (v != null && v !== false) n.setAttribute(k, v);
    for (const c of kids.flat()) if (c != null && c !== false) n.append(c);
    return n;
  }
  const num = (v, d = 2) => (Math.abs(v) < 5e-7 ? 0 : v).toFixed(d).replace("-", "−");
  const pct = (v) => `${Math.round(v * 100)}%`;
  const caseName = (c) => c.title.split(" — ").pop();
  const caseOf = (id) => B.cases.find((c) => c.id === id);
  const lower = (name) => NAME[name].toLowerCase();
  const bold = (text) => h("b", {}, text);
  const P = (...kids) => h("p", {}, ...kids);
  const term = (word) => h("dfn", {}, word);
  const list = (xs) => (xs.length < 2 ? xs.join("") : `${xs.slice(0, -1).join(", ")} and ${xs[xs.length - 1]}`);

  /* ------------------------------------------------------------------ state */

  const cases = B.cases.filter((c) => STY.every((r) => STY.every((d) => B.trials[`${c.id}|${r}|${d}|0`])));
  if (!cases.length) return;
  const L = {
    caseId: (cases.find((c) => c.id === "helix-espionage") ?? cases[0]).id,
    weights: { ...M.DEFAULT_WEIGHTS },
    samples: null, runs: 1, source: "bundle", live: false, liveCache: {},
    game: null, an: null, base: null,
    pair: { p: "aggressive", d: "conservative" }, sub: ["aggressive", "conservative"], start: null, landscape: "both",
    chat: [], evoText: "",
  };

  const bundleSamples = (cid) => STY.map((r) => STY.map((d) => [M.summarize(B.trials[`${cid}|${r}|${d}|0`])]));

  function recompute() {
    L.game = M.buildGame(STY, STY, L.samples, L.weights);
    L.an = M.analyze(L.game);
    const g0 = M.buildGame(STY, STY, L.samples, M.DEFAULT_WEIGHTS);
    L.base = { game: g0, an: M.analyze(g0) };
  }

  function setCase(id) {
    if (!cases.some((c) => c.id === id)) return false;
    L.caseId = id;
    const cached = L.liveCache[id];
    L.samples = cached?.samples ?? bundleSamples(id);
    L.runs = cached?.runs ?? 1;
    L.source = cached ? "live" : "bundle";
    L.start = null;
    $("#lab-case").value = id;
    refresh();
    return true;
  }

  /* The equilibrium the headline numbers describe: a pure one when it exists, else the first mixed one. */
  const headline = (an) => an.equilibria.find((e) => e.pure) ?? an.equilibria[0] ?? null;
  const mixText = (mix) => mix.map((v, i) => [v, i]).filter(([v]) => v > 0.005).sort((x, y) => y[0] - x[0])
    .map(([v, i]) => (v > 0.995 ? NAME[STY[i]] : `${pct(v)} ${NAME[STY[i]]}`)).join(", ");
  const eqText = (e) => (e.pure ? `${NAME[STY[e.x.indexOf(1)]]} Accuser against ${NAME[STY[e.y.indexOf(1)]]} Defender`
    : `Accuser mixes ${mixText(e.x)}; Defender mixes ${mixText(e.y)}`);
  const cellOf = (p, d) => L.game.cells[STY.indexOf(p)][STY.indexOf(d)];

  /* ------------------------------------------------------------------ tooltip */

  const tip = h("div", { class: "lab-tip", role: "tooltip", hidden: true });
  document.body.append(tip);
  function showTip(evt, ...content) {
    tip.replaceChildren(...content.flat().filter(Boolean));
    tip.hidden = false;
    const pad = 14, r = tip.getBoundingClientRect();
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + r.width > innerWidth - 8) x = evt.clientX - r.width - pad;
    if (y + r.height > innerHeight - 8) y = evt.clientY - r.height - pad;
    tip.style.transform = `translate(${Math.max(8, x)}px, ${Math.max(8, y)}px)`;
  }
  const hideTip = () => { tip.hidden = true; };
  const tipRow = (label, value, hue) => h("span", { class: "tip-row" }, hue && h("i", { style: `background:${hue}` }), h("span", {}, label), h("b", {}, value));
  addEventListener("scroll", hideTip, { passive: true });

  /* ------------------------------------------------------------------ page skeleton */

  const legend = (items) => h("ul", { class: "lab-legend" }, items.map(([hue, label, dash]) => h("li", {}, h("i", { class: dash ? "dash" : null, style: `--hue:${hue}` }), label)));
  const styleSelect = (id, label, value) => h("label", { class: "select-label small" }, label, h("select", { id }, STY.map((n) => h("option", { value: n, selected: n === value }, NAME[n]))));

  const CHAPTERS = [];
  /* One chapter: plain-language lead, how to read the chart, the chart, what it says for this case, the working. */
  function chapter(id, title, { lead, read, fig, maths }) {
    const n = String(CHAPTERS.length + 1).padStart(2, "0");
    CHAPTERS.push({ id, title });
    return h("section", { class: "chapter", id: `ch-${id}`, "aria-labelledby": `ch-${id}-t` },
      h("header", { class: "ch-head" }, h("span", { class: "ch-num", "aria-hidden": "true" }, n), h("h2", { id: `ch-${id}-t` }, title)),
      h("div", { class: "prose" }, lead),
      read && h("div", { class: "howto" }, h("h3", {}, "How to read it"), h("ol", {}, read.map((r) => h("li", {}, r)))),
      fig && h("div", { class: "fig" }, fig),
      h("div", { class: "says", id: `says-${id}`, hidden: true }, h("h3", {}, "What it says for this case"), h("div", { class: "says-body", role: "status" })),
      maths && h("details", { class: "maths" }, h("summary", {}, "Show the working"), h("div", { class: "maths-body" }, maths)));
  }
  function says(id, ...kids) {
    const box = $(`#says-${id}`);
    box.hidden = false;
    $(".says-body", box).replaceChildren(...kids.flat().filter(Boolean));
  }

  const chapters = [
    chapter("game", "A trial is a game", {
      lead: [
        P("Game theory is the study of choices where your result depends on what someone else chooses too. Chess is like that. So is a penalty kick. So is a trial: an Accuser who shows weak evidence may be fine against a sleepy opponent and in trouble against one who objects to everything."),
        P("A game needs three things, and a trial has all of them:"),
        h("dl", { class: "defs" },
          h("dt", {}, "Players"), h("dd", {}, "The ", h("b", { class: "t-p" }, "Accuser"), ", who says it happened, and the ", h("b", { class: "t-d" }, "Defender"), ", who says it didn't."),
          h("dt", {}, "Choices"), h("dd", {}, "Each lawyer picks one of four styles before the trial starts. Game theory calls a choice like this a ", term("strategy"), ".",
            h("ul", { class: "style-list" }, STY.map((n) => h("li", {}, h("i", { style: `background:${HUE[n]}` }), h("b", {}, NAME[n]), " ", BLURB[n])))),
          h("dt", {}, "A score"), h("dd", {}, "Each lawyer ends the trial with a number that says how well it went for them. Game theory calls it a ", term("payoff"), ". Winning adds to it. Paying to present evidence and being penalised by the judge both take away from it.")),
        P("The score matters because winning isn't everything. A lawyer who wins after burning the whole budget and collecting penalties did worse than one who wins cheaply. The table below shows exactly how one score is built."),
      ],
      read: ["Pick a style for each lawyer.", "Read each row left to right: points for winning, minus the cost of evidence, minus penalties, gives the payoff on the right."],
      fig: [
        h("div", { class: "row-controls" }, styleSelect("lg-p", "Accuser plays", L.pair.p), styleSelect("lg-d", "Defender plays", L.pair.d)),
        h("div", { class: "ledger", id: "ledger", role: "table", "aria-label": "How each lawyer's payoff is built" })],
      maths: [
        P("For each lawyer in each trial:"),
        h("p", { class: "formula" }, "payoff = V × win − c × spent − μ × sanctions"),
        h("ul", {},
          h("li", {}, bold("win"), " is 1 if the judge ruled for that lawyer and 0 if not."),
          h("li", {}, bold("spent"), " is how many budget points they used. Presenting a document costs 1 point, a witness 1.5, and so on."),
          h("li", {}, bold("sanctions"), " are penalty points from the judge, for example 0.25 for an objection that gets overruled."),
          h("li", {}, bold("V"), ", ", bold("c"), " and ", bold("μ"), " are the weights: how much a win is worth, how much each budget point hurts and how much each penalty point hurts. The real rules use V = 10, c = 0.3 and μ = 1. Chapter 6 lets you change them.")),
        P("When a pairing has been run several times, the table shows the average payoff across those runs.")],
    }),

    chapter("table", "Every pairing at once", {
      lead: [
        P("Four styles for the Accuser times four for the Defender gives sixteen possible trials. Put all sixteen scores in one grid and you have the whole game on one page. Game theory calls this grid the ", term("payoff matrix"), "."),
        P("The grid also answers the most useful question a lawyer can ask: ", h("em", {}, "if I knew what the other side was going to do, what should I do?"), " That answer is called a ", term("best reply"), ". For the Accuser you find it by looking down a column, because the column is the Defender's choice and can't be changed. The biggest Accuser number in that column is the best reply, and it gets underlined. For the Defender you look along a row instead."),
        P("Sometimes one box has both numbers underlined. That box is special. The Accuser is already giving the best reply to the Defender, and the Defender is already giving the best reply to the Accuser, so neither wants to change. It's called a ", term("Nash equilibrium"), ", after the mathematician John Nash, and it gets a gold ring."),
      ],
      read: [
        "Rows are the Accuser's style. Columns are the Defender's style.",
        ["In each box the first number is the ", h("b", { class: "t-p" }, "Accuser's"), " payoff and the second is the ", h("b", { class: "t-d" }, "Defender's"), ". The small bar under a number shows its size."],
        "An underlined number is a best reply. Two underlines in one box make a Nash equilibrium.",
        "Hover over a box for the detail. Click one to follow that trial in the other chapters."],
      fig: [
        h("div", { class: "pm", id: "pm", role: "table", "aria-label": "Payoff for every pairing of styles" }),
        h("button", { class: "linkish", id: "lab-csv", type: "button" }, "Download this table (CSV)")],
      maths: [
        P("Each box is the average over the runs for that pairing. With n runs and payoffs u₁ … uₙ:"),
        h("p", { class: "formula" }, "average = (u₁ + … + uₙ) / n"),
        P("With more than one run, the tooltip also shows ± the standard error, which says how far the average might be from the true value. It shrinks as you add runs:"),
        h("p", { class: "formula" }, "standard error = spread of the runs / √n"),
        P("Best reply, written out: style i is a best reply to the Defender's style j when no other row beats it in that column, A[i][j] ≥ A[k][j] for every k. A box (i, j) is a Nash equilibrium when i is a best reply to j and j is a best reply to i."),
        h("div", { id: "maths-table-dyn" })],
    }),

    chapter("solve", "Solving the game", {
      lead: [
        P("\"Solving\" a game means working out what two sensible players would end up doing. There isn't one trick. There are four questions, asked in order, and each one narrows things down."),
        P(bold("1. Is any style simply bad?"), " If one style earns less than another whatever the other side does, no sensible lawyer would ever pick it. It is ", term("dominated"), ", and you can cross it out. Crossing one out can make another look bad, so you repeat until nothing more goes."),
        P(bold("2. Where does nobody want to switch?"), " That's the Nash equilibrium from the last chapter. Sometimes it's a single box. Sometimes no box works, and the only stable thing is for each lawyer to pick at random with fixed chances, so the other can't predict them. That is a ", term("mixed strategy"), ". Rock-paper-scissors is the classic example: the only safe way to play is one third each."),
        P(bold("3. What if a lawyer trusts nobody?"), " A cautious lawyer can ignore the other side completely and pick the style whose worst result is the least bad. That is the ", term("safe choice"), " (game theorists say maximin)."),
        P(bold("4. Could both do better?"), " Sometimes the stable outcome is worse for both lawyers than another box they could have reached by cooperating. That gap is the cost of each side looking after only itself. The famous example is the prisoner's dilemma."),
      ],
      fig: h("ol", { class: "solve", id: "solve" }),
      maths: [
        P(bold("Dominated."), " Row r is strictly dominated by row o when A[o][j] > A[r][j] for every column j still in the game. The same test runs on the Defender's columns using their payoffs. Rows and columns are removed one at a time until none qualifies."),
        P(bold("Finding every equilibrium."), " The lab tries every possible set of styles each lawyer might use (one style each, then two each, and so on). For each set it solves the equations that make the other lawyer exactly indifferent between the styles in their set. It keeps the answer only if the chances are valid (none negative, adding to 1) and neither lawyer could gain by switching to any other style. This method is called support enumeration."),
        P(bold("The check."), " For each equilibrium the lab then measures how much either lawyer could gain by switching alone. It must be zero."),
        P(bold("Safe choice."), " For each of the Accuser's rows take the smallest number in it, then pick the row where that smallest number is largest. For the Defender do the same with columns.")],
    }),

    chapter("br", "Best replies, drawn as a picture", {
      lead: [
        P("The underlines in Chapter 2 show best replies to a single style. But the other side might mix: say Bold 70% of the time and Careful 30%. To see best replies to every possible mix at once, you need a picture, and the picture only fits on a page for two styles at a time. So pick two."),
        P("Going left to right is how often the Accuser plays the first style. Going bottom to top is how often the Defender plays it. Each lawyer gets one line. The line follows that lawyer's best reply as the other side's mix changes. It usually sits on an edge (always play one style) and then jumps across at one exact point: the mix at which the two styles pay the same."),
        P("Where the two lines meet, both lawyers are giving their best reply at the same time. That's a Nash equilibrium again, found by drawing instead of underlining."),
      ],
      read: [
        ["The ", h("b", { class: "t-p" }, "Accuser's"), " line: for each height (the Defender's mix), it shows how far right the Accuser wants to be."],
        ["The ", h("b", { class: "t-d" }, "Defender's"), " line: for each left-to-right position (the Accuser's mix), it shows how high the Defender wants to be."],
        "A gold dot marks each crossing. A dot in a corner is a pure equilibrium. A dot in the middle is a mixed one. Hover over a dot for the numbers."],
      fig: [
        h("div", { class: "row-controls" }, styleSelect("br-a", "Compare", L.sub[0]), styleSelect("br-b", "with", L.sub[1])),
        h("div", { class: "chart square", id: "br-chart" }),
        legend([[P_HUE, "Accuser's best reply"], [D_HUE, "Defender's best reply"], [GOLD, "Equilibrium"]])],
      maths: h("div", { id: "maths-br-dyn" }),
    }),

    chapter("land", "The payoff landscape", {
      lead: [
        P("Here is the table from Chapter 2 again, built in 3D so you can see its shape. Each floor tile is one pairing of styles. On it stand two bars: how well that pairing goes for the Accuser, and how well for the Defender."),
        P("Shape tells you things numbers hide. If one lawyer's bars are tall where the other's are short, the game is a tug of war. If both sets of bars rise and fall together, the lawyers mostly want the same thing. Gold tiles mark Nash equilibria, and it's worth noticing that they often aren't under the tallest bars."),
      ],
      read: ["Drag to turn the model. It also turns slowly by itself.", "A bar that drops below the floor is a negative payoff: that lawyer ended up worse off than not playing.", "The red-brown labels along one edge are the Accuser's styles; the green ones along the other are the Defender's.", "Use the buttons to show one lawyer at a time. Hover over a bar for its value."],
      fig: [
        h("div", { class: "seg", role: "group", "aria-label": "Which lawyer to show" },
          ...[["both", "Both"], ["p", "Accuser"], ["d", "Defender"]].map(([v, label]) => h("button", { type: "button", "data-land": v, "aria-pressed": String(v === "both") }, label))),
        h("div", { class: "land", id: "land" }),
        legend([[P_HUE, "Accuser's payoff"], [D_HUE, "Defender's payoff"], ["#d9a54a", "Nash equilibrium (floor tile)"]])],
    }),

    chapter("whatif", "Change the rules", {
      lead: [
        P("So far the rules have been fixed: a win is worth 10, each budget point costs 0.3 and each penalty point costs 1. But rules are a choice. A court that punishes bad objections harder, or a client who cares only about winning, changes what a sensible lawyer does."),
        P("These sliders change the three weights in the payoff formula from Chapter 1. Nothing about the trials themselves changes: the same evidence was shown and the same verdicts were reached. Only the scoring changes, and with it the whole game. Every chart on this page redraws as you drag."),
        P("This is how game theory gets used in practice. You don't tell people what to do. You change what things cost, and watch where the stable outcome moves."),
      ],
      read: ["Drag a slider and watch the sentence below it.", "Scroll back up: the table, the solution and the 3D model have all updated.", "Press reset to return to the real rules."],
      fig: [
        h("div", { class: "sliders" },
          ...[["V", "How much a win is worth", "Raise it and lawyers will pay more to win.", 0, 20, 0.5], ["c", "Cost of each budget point spent", "Raise it and showing lots of evidence gets expensive.", 0, 2, 0.05], ["mu", "Penalty for each sanction point", "Raise it and careless objections and rule-breaking hurt more.", 0, 5, 0.1]].map(([k, label, hint, min, max, step]) =>
            h("label", { class: "slider" }, h("span", {}, h("b", {}, label), h("output", { id: `w-${k}-out` })), h("input", { type: "range", id: `w-${k}`, min, max, step, value: L.weights[k] }), h("small", {}, hint)))),
        h("button", { class: "btn ghost", id: "w-reset", type: "button" }, "Reset to the real rules")],
    }),

    chapter("evo", "If lawyers copied what works", {
      lead: [
        P("Nash equilibrium assumes clever lawyers who think everything through. Real people often don't. They look around, see what's working for others, and copy it. Does that simpler process end up in the same place?"),
        P("Imagine a big crowd of Accusers and a big crowd of Defenders, each using some mix of styles. Every round, lawyers are paired off at random. A style that scores above the crowd's average gains followers. One that scores below average loses them. Nobody plans anything. Game theory calls this ", term("replicator dynamics"), ", and it came from biology, where it describes how traits spread through a population."),
        P("If the lines settle on the same styles as the stable outcome in Chapter 3, that's strong evidence the outcome is robust: you reach it by thinking and by trial and error alike. If the lines keep swinging, the game has no resting point that simple copying can find."),
      ],
      read: ["Each line is one style. Its height is the share of the crowd using it.", "Left to right is time, 300 rounds.", "\"Equal start\" begins with a quarter each. \"Random start\" picks a different starting crowd so you can see if the ending depends on where you begin."],
      fig: [
        h("div", { class: "row-controls" },
          h("button", { class: "btn ghost sm", id: "evo-equal", type: "button" }, "Equal start"),
          h("button", { class: "btn ghost sm", id: "evo-random", type: "button" }, "Random start")),
        legend(STY.map((n) => [HUE[n], NAME[n]])),
        h("div", { class: "evo-pair" }, h("figure", {}, h("figcaption", {}, "Accusers"), h("div", { class: "chart", id: "evo-p" })), h("figure", {}, h("figcaption", {}, "Defenders"), h("div", { class: "chart", id: "evo-d" })))],
      maths: [
        P("Each round, for every style:"),
        h("p", { class: "formula" }, "new share = share + 0.05 × share × (that style's payoff − the crowd's average payoff)"),
        P("A style's payoff is its row of the table averaged over the current mix of opponents. The shares are then rescaled to add up to 100%. A style with zero share stays at zero, because there is nobody left to copy.")],
    }),

    chapter("belief", "Inside one trial", {
      lead: [
        P("Every number so far summarises a whole trial as one score. This chapter opens a single trial up to show where the score comes from."),
        P("To win, the Accuser must prove a short list of things. Lawyers call them ", term("elements"), ". The judge keeps a running belief in each one, from 0% (certainly false) to 100% (certainly true). Accepted evidence pushes a belief up or down. Evidence that gets thrown out stops counting."),
        P("The dashed line is the bar the Accuser must clear, set by the ", term("standard of proof"), ". For a criminal charge it's high (\"beyond reasonable doubt\"). For a dispute between two people it's lower (\"more likely than not\"). The Accuser wins only if every element ends above the line. This is why style matters: a Bold lawyer adds evidence quickly but risks having it thrown out, and a Careful one adds less but keeps what they add."),
      ],
      read: ["Pick a style for each lawyer, or click a box in Chapter 2.", "Each line is one thing the Accuser must prove. A jump is a piece of evidence landing. A drop is evidence being thrown out or answered.", "Hover anywhere to see what happened at that step."],
      fig: [
        h("div", { class: "row-controls" }, styleSelect("bf-p", "Accuser", L.pair.p), styleSelect("bf-d", "Defender", L.pair.d),
          h("button", { class: "btn primary sm", id: "bf-watch", type: "button" }, "Watch this trial in the courtroom")),
        h("div", { id: "bf-legend" }),
        h("div", { class: "chart wide", id: "bf-chart" })],
      maths: h("div", { id: "maths-belief-dyn" }),
    }),

    chapter("analyst", "Ask the analyst", {
      lead: [
        P("If something above didn't click, ask about it here in your own words. The analyst sees the same numbers you do for the selected case and explains them."),
        P("It can also work the page for you. Ask it to show a pairing, switch case or try a what-if (\"what if sanctions cost double?\") and the charts above will change to match."),
      ],
      fig: [
        h("div", { class: "chat", id: "chat", "aria-live": "polite" }),
        h("div", { class: "chips", id: "chat-chips" }),
        h("form", { class: "chat-form", id: "chat-form" },
          h("input", { id: "chat-in", type: "text", maxlength: 600, autocomplete: "off", placeholder: "e.g. Why does Careful win here?", "aria-label": "Your question for the analyst" }),
          h("button", { class: "btn primary", type: "submit", id: "chat-send" }, "Ask")),
        h("p", { class: "fig-note", id: "chat-status" })],
    }),

    chapter("words", "The words, in one place", {
      lead: [
        h("dl", { class: "glossary" }, [
          ["Game", "Any situation where each person's result depends on what the others choose as well as on their own choice."],
          ["Player", "Someone making a choice in the game. Here: the Accuser and the Defender."],
          ["Strategy", "A complete plan for how to play. Here: a lawyer's style (Bold, Careful, Smart or Wild)."],
          ["Payoff", "The score a player ends with. Here: points for winning, minus evidence costs, minus penalties."],
          ["Payoff matrix", "The grid of payoffs for every combination of strategies."],
          ["Best reply", "The strategy that scores highest against one particular choice by the other side."],
          ["Dominated strategy", "A strategy that scores worse than some other one whatever the other side does. Never worth playing."],
          ["Dominant strategy", "A strategy that is a best reply to everything the other side could do."],
          ["Nash equilibrium", "A pair of strategies where each is a best reply to the other, so neither player gains by changing alone."],
          ["Pure strategy", "Always playing the same single strategy."],
          ["Mixed strategy", "Choosing between strategies at random with fixed chances, so the other side can't predict you."],
          ["Safe choice (maximin)", "The strategy whose worst possible result is the least bad."],
          ["Efficient (Pareto efficient)", "An outcome where nobody can be made better off without making someone else worse off."],
          ["Replicator dynamics", "A model where strategies that beat the average spread through a crowd and the rest fade."],
          ["Element", "One of the things the Accuser must prove to win."],
          ["Standard of proof", "How sure the judge must be of each element before ruling for the Accuser."],
        ].map(([t, d]) => [h("dt", {}, t), h("dd", {}, d)]))],
    }),
  ];

  root.append(
    h("div", { class: "lab-bar", id: "lab-bar" },
      h("label", { class: "select-label" }, "Case ", h("select", { id: "lab-case" }, cases.map((c) => h("option", { value: c.id }, caseName(c))))),
      h("p", { class: "lab-source", id: "lab-source", role: "status" }),
      h("div", { class: "lab-live", id: "lab-live", hidden: true },
        h("label", { class: "select-label small" }, "Runs per pairing", h("select", { id: "lab-n" }, [10, 20, 40].map((n) => h("option", { value: n, selected: n === 20 }, String(n))))),
        h("button", { class: "btn ghost sm", id: "lab-run", type: "button" }, "Run fresh trials")),
      h("div", { class: "lab-progress", id: "lab-progress", hidden: true }, h("span", {}))),
    h("section", { class: "answer", "aria-labelledby": "answer-t" },
      h("h2", { id: "answer-t" }, "The short answer"),
      h("p", { class: "answer-case", id: "answer-case" }),
      h("div", { class: "lab-kpis", id: "lab-kpis" }),
      h("p", { class: "answer-note" }, "The chapters below explain where each of these comes from.")),
    h("div", { class: "lab-layout" },
      h("nav", { class: "rail", "aria-label": "Chapters" }, h("ol", {}, CHAPTERS.map((c, i) => h("li", {}, h("a", { href: `#ch-${c.id}`, "data-ch": c.id }, h("span", {}, String(i + 1).padStart(2, "0")), c.title))))),
      h("div", { class: "chapters" }, chapters)));

  /* ------------------------------------------------------------------ the short answer */

  function renderKpis() {
    const { an, game } = L, e = headline(an), c = caseOf(L.caseId);
    const pureN = an.equilibria.filter((x) => x.pure).length, mixedN = an.equilibria.length - pureN;
    const winAt = e ? M.expected(game.cells.map((r) => r.map((x) => x.winP)), e.x, e.y) : null;
    $("#answer-case").replaceChildren(bold(caseName(c)), `. ${c.synopsis}`);
    const tiles = [
      ["Where the game settles", e ? (e.pure ? `${NAME[STY[e.x.indexOf(1)]]} vs ${NAME[STY[e.y.indexOf(1)]]}` : "A mix of styles") : "None found",
        e ? (e.pure ? "The Accuser's style against the Defender's. Neither gains by switching alone." : `${eqText(e)}.`) : "This game has exact ties that hide its equilibria.", true],
      ["Accuser's payoff there", e ? num(e.u) : "–", "On average, at that outcome."],
      ["Defender's payoff there", e ? num(e.v) : "–", "On average, at that outcome."],
      ["Accuser wins there", winAt == null ? "–" : pct(winAt), `${an.equilibria.length} stable outcome${an.equilibria.length === 1 ? "" : "s"} found: ${pureN} pure, ${mixedN} mixed.`],
    ];
    $("#lab-kpis").replaceChildren(...tiles.map(([label, value, sub, wide]) => h("div", { class: `kpi${wide ? " wide" : ""}` }, h("span", { class: "kpi-label" }, label), h("b", {}, value), h("small", {}, sub))));
  }

  /* ------------------------------------------------------------------ chapter 1: how one score is built */

  function renderLedger() {
    $("#lg-p").value = L.pair.p; $("#lg-d").value = L.pair.d;
    const x = cellOf(L.pair.p, L.pair.d), w = L.game.weights, avg = x.n > 1;
    const row = (who, cls, style, win, spent, sanct, total) => h("div", { class: "lg-row", role: "row" },
      h("span", { class: `lg-who ${cls}`, role: "rowheader" }, who, h("small", {}, NAME[style])),
      h("span", { class: "lg-term", role: "cell" }, h("small", {}, avg ? `Won ${pct(win)} of the time` : win ? "Won" : "Lost"), h("b", {}, `+${num(w.V * win)}`), h("i", {}, `${num(w.V, 1)} × ${avg ? num(win) : win}`)),
      h("span", { class: "lg-op", "aria-hidden": "true" }, "−"),
      h("span", { class: "lg-term", role: "cell" }, h("small", {}, `Spent ${num(spent, 1)} budget points`), h("b", {}, num(w.c * spent)), h("i", {}, `${num(w.c)} × ${num(spent, 1)}`)),
      h("span", { class: "lg-op", "aria-hidden": "true" }, "−"),
      h("span", { class: "lg-term", role: "cell" }, h("small", {}, `${num(sanct)} penalty points`), h("b", {}, num(w.mu * sanct)), h("i", {}, `${num(w.mu)} × ${num(sanct)}`)),
      h("span", { class: "lg-op", "aria-hidden": "true" }, "="),
      h("span", { class: "lg-total", role: "cell" }, h("small", {}, "Payoff"), h("b", {}, num(total))));
    $("#ledger").replaceChildren(
      row("Accuser", "t-p", L.pair.p, x.winP, x.spentP, x.sanctP, x.a),
      row("Defender", "t-d", L.pair.d, 1 - x.winP, x.spentD, x.sanctD, x.b));
    const winner = x.winP > 0.5 ? "Accuser" : x.winP < 0.5 ? "Defender" : null;
    says("game",
      P(`When a ${lower(L.pair.p)} Accuser meets a ${lower(L.pair.d)} Defender${avg ? ` (averaged over ${x.n} trials)` : ""}, `,
        winner ? `the ${winner} ${avg ? "usually wins" : "wins"}.` : "each side wins half the time.",
        ` The Accuser ends on ${num(x.a)} and the Defender on ${num(x.b)}.`),
      P(x.a < 0 && x.winP < 0.5 ? "The Accuser's score is negative: they lost, and still paid for the evidence they showed. " : "",
        `The Accuser spent ${num(x.spentP, 1)} budget points and the Defender ${num(x.spentD, 1)}.`,
        " These two payoffs are one box of the table in the next chapter."));
  }

  /* ------------------------------------------------------------------ chapter 2: payoff table */

  function renderMatrix() {
    const { game, an } = L, box = $("#pm");
    const all = [...game.A.flat(), ...game.B.flat()], span = Math.max(1e-9, Math.max(...all.map(Math.abs)));
    const nash = new Set(an.pure.map(([i, j]) => `${i}|${j}`)), par = new Set(an.pareto.map(([i, j]) => `${i}|${j}`));
    const bar = (v, hue) => h("i", { class: `bar${v < 0 ? " neg" : ""}`, style: `--w:${(Math.abs(v) / span * 100).toFixed(1)}%;--hue:${hue}` });
    const kids = [h("div", { class: "corner", role: "columnheader" }, h("span", { class: "t-d" }, "Defender →"), h("span", { class: "t-p" }, "Accuser ↓"))];
    for (const c of STY) kids.push(h("div", { class: "pm-h col", role: "columnheader" }, NAME[c]));
    STY.forEach((r, i) => {
      kids.push(h("div", { class: "pm-h row", role: "rowheader" }, NAME[r]));
      STY.forEach((c, j) => {
        const cell = game.cells[i][j], isNash = nash.has(`${i}|${j}`);
        const brA = an.br.row[j].has(i), brB = an.br.col[i].has(j);
        kids.push(h("button", {
          class: `pm-cell${isNash ? " nash" : ""}`, type: "button", role: "cell", "aria-pressed": String(L.pair.p === r && L.pair.d === c),
          "aria-label": `${NAME[r]} Accuser against ${NAME[c]} Defender. Accuser ${num(cell.a)}${brA ? " (best reply)" : ""}, Defender ${num(cell.b)}${brB ? " (best reply)" : ""}.${isNash ? " Nash equilibrium." : ""}`,
          onclick: () => setPair(r, c),
          onmousemove: (ev) => showTip(ev, h("b", { class: "tip-title" }, `${NAME[r]} Accuser vs ${NAME[c]} Defender`),
            tipRow("Accuser's payoff", num(cell.a) + (cell.n > 1 ? ` ± ${num(cell.seA)}` : ""), P_HUE),
            tipRow("Defender's payoff", num(cell.b) + (cell.n > 1 ? ` ± ${num(cell.seB)}` : ""), D_HUE),
            tipRow("Accuser wins", pct(cell.winP)), tipRow("Budget spent (A / D)", `${num(cell.spentP, 1)} / ${num(cell.spentD, 1)}`), tipRow("Penalty points (A / D)", `${num(cell.sanctP)} / ${num(cell.sanctD)}`),
            h("span", { class: "tip-foot" }, [isNash && "Nash equilibrium", par.has(`${i}|${j}`) && "Efficient: no box is better for both", `${cell.n} run${cell.n === 1 ? "" : "s"}`].filter(Boolean).join(" · "))),
          onmouseleave: hideTip,
        },
          h("span", { class: "pay" }, h("span", { class: brA ? "br" : null }, num(cell.a)), bar(cell.a, P_HUE)),
          h("span", { class: "pay" }, h("span", { class: brB ? "br" : null }, num(cell.b)), bar(cell.b, D_HUE)),
          isNash && h("em", {}, "Nash")));
      });
    });
    box.replaceChildren(...kids);

    // a worked example of one best reply each, using the selected pairing's column and row
    const j = STY.indexOf(L.pair.d), i = STY.indexOf(L.pair.p), col = STY.map((_, k) => game.A[k][j]), rowB = game.B[i];
    const bestA = [...an.br.row[j]].map((k) => NAME[STY[k]]), bestB = [...an.br.col[i]].map((k) => NAME[STY[k]]);
    says("table",
      P(bold("An Accuser's best reply. "), `Suppose the Defender plays ${NAME[L.pair.d]}. Look down the ${NAME[L.pair.d]} column at the Accuser's numbers: ${STY.map((n, k) => `${NAME[n]} ${num(col[k])}`).join(", ")}. The biggest is ${num(Math.max(...col))}, so ${list(bestA)} ${bestA.length > 1 ? "tie as best replies and are all" : "is the best reply and is"} underlined.`),
      P(bold("A Defender's best reply. "), `Now suppose the Accuser plays ${NAME[L.pair.p]}. Look along the ${NAME[L.pair.p]} row at the Defender's numbers: ${STY.map((n, k) => `${NAME[n]} ${num(rowB[k])}`).join(", ")}. The biggest is ${num(Math.max(...rowB))}, so ${list(bestB)} ${bestB.length > 1 ? "are" : "is"} underlined.`),
      P(bold("Nash equilibria. "), an.pure.length
        ? `${an.pure.length === 1 ? "One box has" : `${an.pure.length} boxes have`} both numbers underlined: ${list(an.pure.map(([a, c]) => `${NAME[STY[a]]} vs ${NAME[STY[c]]}`))}. From there, neither lawyer can do better by changing style alone.`
        : "No box has both numbers underlined, so there is no stable pair of single styles. Whatever pair you pick, one lawyer wants to switch. The stable outcome is a mix, which Chapter 3 works out."));
    $("#maths-table-dyn").replaceChildren(P(L.runs === 1 ? "Right now each box is a single recorded trial, so there is no ± yet. Run fresh trials (top of the page, with the local server running) to get averages." : `Right now each box is the average of ${L.runs} trials.`));
    if (gsap && !reduced) gsap.from("#pm .bar", { scaleX: 0, duration: .6, stagger: .012, ease: "power3.out", overwrite: true });
  }

  function downloadCsv() {
    const rowsOut = [["accuser_style", "defender_style", "accuser_payoff", "defender_payoff", "accuser_win_rate", "runs", "nash"]];
    const nash = new Set(L.an.pure.map(([i, j]) => `${i}|${j}`));
    STY.forEach((r, i) => STY.forEach((c, j) => { const x = L.game.cells[i][j]; rowsOut.push([NAME[r], NAME[c], x.a.toFixed(4), x.b.toFixed(4), x.winP.toFixed(4), x.n, nash.has(`${i}|${j}`) ? "yes" : "no"]); }));
    const a = h("a", { href: URL.createObjectURL(new Blob([rowsOut.map((r) => r.join(",")).join("\n")], { type: "text/csv" })), download: `payoffs-${L.caseId}.csv` });
    document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);
  }

  /* ------------------------------------------------------------------ chapter 3: solving */

  function mixBar(mix) {
    return h("span", { class: "mixbar" }, mix.map((v, i) => v > 0.005 && h("i", { style: `flex:${v};--hue:${HUE[STY[i]]}`, title: `${NAME[STY[i]]} ${pct(v)}` }, v > 0.16 ? `${NAME[STY[i]]} ${pct(v)}` : "")));
  }

  function renderSolve() {
    const { an, game } = L, items = [], e = headline(an);
    const who = (p) => (p === "row" ? "the Accuser" : "the Defender");
    const solved = an.iesds.rows.length === 1 && an.iesds.cols.length === 1;
    items.push(h("li", {}, h("h4", {}, "Cross out styles that are simply bad"),
      an.iesds.steps.length
        ? h("ul", { class: "steps" }, an.iesds.steps.map((st) => h("li", {}, h("s", {}, NAME[STY[st.removed]]), ` for ${who(st.player)}. ${NAME[STY[st.by]]} earns more against every style the other side still has.`)))
        : P("No style earns less than another against everything, so nothing can be crossed out. Every style is the right call against something."),
      P(`Still standing for the Accuser: ${list(an.iesds.rows.map((i) => NAME[STY[i]]))}. For the Defender: ${list(an.iesds.cols.map((j) => NAME[STY[j]]))}.`,
        solved ? " Only one style each is left, so crossing out alone has solved the game." : "")));

    items.push(h("li", {}, h("h4", {}, "Find where nobody wants to switch"),
      an.equilibria.length
        ? an.equilibria.map((eq) => {
          const g = M.regret(game.A, game.B, eq.x, eq.y);
          return h("div", { class: "eq" },
            h("span", { class: "eq-tag" }, eq.pure ? "Pure: one style each" : "Mixed: random with these chances"),
            h("span", { class: "eq-row" }, h("span", { class: "t-p" }, "Accuser"), mixBar(eq.x), h("b", {}, num(eq.u))),
            h("span", { class: "eq-row" }, h("span", { class: "t-d" }, "Defender"), mixBar(eq.y), h("b", {}, num(eq.v))),
            h("small", {}, `Checked: the most either could gain by switching alone is ${num(Math.max(g.row, g.col, 0))}. The numbers on the right are each lawyer's average payoff.`));
        })
        : P("The usual method found none. That happens when several payoffs tie exactly."),
      an.equilibria.some((eq) => !eq.pure) && P("Why would a lawyer pick at random? Because any fixed style here can be exploited. The chances are tuned so the other side earns the same whichever of their styles they use, which leaves them nothing to exploit.")));

    const sr = an.security.row, sc = an.security.col;
    const safeIsEq = e && e.pure && sr.index === e.x.indexOf(1) && sc.index === e.y.indexOf(1);
    items.push(h("li", {}, h("h4", {}, "The safe choice"),
      P(`The worst that can happen to a ${lower(STY[sr.index])} Accuser is ${num(sr.value)}, and no other style has a better worst case. For the Defender it's ${NAME[STY[sc.index]]}, with a worst case of ${num(sc.value)}.`,
        safeIsEq ? " Here the safe choices and the stable outcome are the same box, so being cautious costs nothing." : e ? ` At the stable outcome the Accuser averages ${num(e.u)} and the Defender ${num(e.v)}.` : "")));

    const [wi, wj] = an.welfare.cell;
    const gap = e ? an.welfare.value - (e.u + e.v) : 0;
    items.push(h("li", {}, h("h4", {}, "Could both do better?"),
      P(`Add the two payoffs in each box. The biggest total is ${num(an.welfare.value)}, when a ${lower(STY[wi])} Accuser meets a ${lower(STY[wj])} Defender. `,
        e ? (gap > 0.005 ? `The stable outcome totals ${num(e.u + e.v)}. So ${num(gap)} points are lost between them, because each lawyer looks after only their own side.` : "The stable outcome reaches that total too, so nothing is wasted.") : "")));
    $("#solve").replaceChildren(...items);

    const nEq = an.equilibria.length;
    says("solve", e ? P(bold(nEq > 1 ? "One place the game can settle: " : "The game settles on: "), `${eqText(e)}.`) : P("The solver found no clean stable outcome for this case."),
      nEq > 1 && P(`This case has ${nEq} stable outcomes, all listed in step 2 above. That happens when several styles earn exactly the same, so a lawyer has no reason to prefer one over another. The short answer at the top of the page uses the first of them.`),
      P(an.dominant.row != null ? `${NAME[STY[an.dominant.row]]} is the Accuser's best reply to everything, so the Accuser's choice is easy. ` : "The Accuser has no style that is best against everything. ",
        an.dominant.col != null ? `${NAME[STY[an.dominant.col]]} is the Defender's best reply to everything.` : "The Defender has no style that is best against everything either: the right one depends on the opponent."),
      L.runs === 1 && P(h("i", {}, "This comes from one recorded trial per pairing, so small differences can flip the answer. Fresh trials give steadier averages.")));
  }

  /* ------------------------------------------------------------------ chapter 6: what-if */

  function renderWhatIf() {
    for (const k of ["V", "c", "mu"]) { $(`#w-${k}`).value = L.weights[k]; $(`#w-${k}-out`).textContent = num(L.weights[k], k === "V" ? 1 : 2); }
    const d = M.DEFAULT_WEIGHTS, changed = ["V", "c", "mu"].some((k) => Math.abs(L.weights[k] - d[k]) > 1e-9);
    const now = headline(L.an), was = headline(L.base.an);
    $("#w-reset").disabled = !changed;
    $("#lab-bar").classList.toggle("whatif-on", changed);
    if (!changed) says("whatif", P("These are the real rules. Try doubling the penalty, or setting the cost of evidence to zero, and see if the stable outcome moves."));
    else if (!now || !was) says("whatif", P("The stakes have changed."));
    else if (eqText(now) === eqText(was)) says("whatif", P(bold("The stable outcome didn't move. "), `It is still: ${eqText(now)}. The payoffs changed (Accuser ${num(was.u)} → ${num(now.u)}, Defender ${num(was.v)} → ${num(now.v)}), but no lawyer has a reason to play differently. This outcome is robust to that change.`));
    else says("whatif", P(bold("The stable outcome moved. "), `Under the real rules it was: ${eqText(was)}. With your rules it is: ${eqText(now)}.`), P("Same trials, same evidence, same verdicts. Only the scoring changed, and that was enough to change what a sensible lawyer does."));
  }

  function setWeights(w) {
    const lim = { V: [0, 20], c: [0, 2], mu: [0, 5] };
    let any = false;
    for (const k of ["V", "c", "mu"]) {
      const v = Number(w[k]);
      if (w[k] == null || !Number.isFinite(v)) continue;
      L.weights[k] = Math.min(lim[k][1], Math.max(lim[k][0], v)); any = true;
    }
    if (any) refresh();
    return any;
  }

  /* ------------------------------------------------------------------ shared chart frame */

  function frame(host, { w = 520, hgt = 300, m = { t: 14, r: 64, b: 40, l: 46 }, xMax, xLabel, yTicks = [0, .25, .5, .75, 1], yFmt = pct, xTicks, xFmt = String, label }) {
    const iw = w - m.l - m.r, ih = hgt - m.t - m.b;
    const X = (v) => m.l + (v / xMax) * iw, Y = (v) => m.t + (1 - v) * ih;
    const svg = s("svg", { viewBox: `0 0 ${w} ${hgt}`, role: "img", "aria-label": label });
    for (const t of yTicks) svg.append(s("line", { class: "grid", x1: m.l, x2: m.l + iw, y1: Y(t), y2: Y(t) }), s("text", { class: "tick", x: m.l - 8, y: Y(t) + 4, "text-anchor": "end" }, yFmt(t)));
    for (const t of xTicks) svg.append(s("text", { class: "tick", x: X(t), y: m.t + ih + 18, "text-anchor": "middle" }, xFmt(t)));
    if (xLabel) svg.append(s("text", { class: "axis", x: m.l + iw / 2, y: hgt - 4, "text-anchor": "middle" }, xLabel));
    host.replaceChildren(svg);
    return { svg, X, Y, m, iw, ih, w, hgt };
  }

  const linePath = (pts) => pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");

  /* End-of-line labels, nudged apart so they never overlap. */
  function endLabels(f, items) {
    const minGap = 14, sorted = items.filter((it) => it.show !== false).sort((a, c) => a.y - c.y);
    for (let i = 1; i < sorted.length; i++) if (sorted[i].y - sorted[i - 1].y < minGap) sorted[i].y = sorted[i - 1].y + minGap;
    const over = sorted.length ? sorted[sorted.length - 1].y - (f.m.t + f.ih) : 0;
    if (over > 0) for (let i = sorted.length - 1; i >= 0; i--) { sorted[i].y -= over; if (i && sorted[i].y - sorted[i - 1].y >= minGap) break; }
    for (const it of sorted) f.svg.append(s("text", { class: "end", x: f.m.l + f.iw + 8, y: it.y + 4 }, it.text));
  }

  /* Crosshair plus tooltip for a line chart: `rows(i)` returns the tooltip rows for index i of `count` points. */
  function crosshair(f, count, xOf, rows, dots) {
    const line = s("line", { class: "cross", y1: f.m.t, y2: f.m.t + f.ih, visibility: "hidden" });
    const marks = dots.map((d) => s("circle", { r: 4.5, fill: d.hue, class: "cross-dot", visibility: "hidden" }));
    const hit = s("rect", { x: f.m.l, y: f.m.t, width: f.iw, height: f.ih, fill: "transparent" });
    f.svg.append(line, ...marks, hit);
    hit.addEventListener("mousemove", (ev) => {
      const box = f.svg.getBoundingClientRect(), px = (ev.clientX - box.left) / box.width * f.w;
      let best = 0;
      for (let i = 1; i < count; i++) if (Math.abs(xOf(i) - px) < Math.abs(xOf(best) - px)) best = i;
      line.setAttribute("x1", xOf(best)); line.setAttribute("x2", xOf(best)); line.setAttribute("visibility", "visible");
      marks.forEach((mk, k) => { mk.setAttribute("cx", xOf(best)); mk.setAttribute("cy", dots[k].yOf(best)); mk.setAttribute("visibility", "visible"); });
      showTip(ev, rows(best));
    });
    hit.addEventListener("mouseleave", () => { hideTip(); line.setAttribute("visibility", "hidden"); marks.forEach((mk) => mk.setAttribute("visibility", "hidden")); });
  }

  function drawOn(paths) {
    if (!gsap || reduced) return;
    for (const p of paths) {
      const len = p.getTotalLength();
      gsap.fromTo(p, { strokeDasharray: len, strokeDashoffset: len }, { strokeDashoffset: 0, duration: 1.1, ease: "power2.out", overwrite: true, onComplete: () => p.removeAttribute("stroke-dasharray") });
    }
  }

  /* ------------------------------------------------------------------ chapter 4: best-reply plot (2 x 2) */

  function renderBR() {
    const [a, c] = L.sub, idx = [STY.indexOf(a), STY.indexOf(c)];
    const A = idx.map((i) => idx.map((j) => L.game.A[i][j])), Bm = idx.map((i) => idx.map((j) => L.game.B[i][j]));
    const rc = M.reaction2x2(A, Bm), eqs = M.supportEnumeration(A, Bm);
    const f = frame($("#br-chart"), {
      w: 440, hgt: 410, m: { t: 16, r: 26, b: 52, l: 62 }, xMax: 1, xTicks: [0, .5, 1], xFmt: pct, yTicks: [0, .5, 1],
      xLabel: `How often the Accuser plays ${NAME[a]} →`, label: `Best replies when both lawyers choose between ${NAME[a]} and ${NAME[c]}`,
    });
    f.svg.append(s("text", { class: "axis", transform: `translate(14 ${f.m.t + f.ih / 2}) rotate(-90)`, "text-anchor": "middle" }, `How often the Defender plays ${NAME[a]} →`));
    f.svg.append(s("rect", { class: "plot-frame", x: f.m.l, y: f.m.t, width: f.iw, height: f.ih }));
    f.svg.append(s("text", { class: "corner-lbl", x: f.m.l + 8, y: f.m.t + f.ih - 8 }, `both ${NAME[c]}`), s("text", { class: "corner-lbl", x: f.m.l + f.iw - 8, y: f.m.t + 16, "text-anchor": "end" }, `both ${NAME[a]}`));
    const q = rc.qStar, p = rc.pStar, mid = (lo, hi) => (lo + hi) / 2, off = 3;
    let rowPts, colPts;
    if (q == null) { const v = rc.rowBR(.5) ?? .5; rowPts = [[v, 0], [v, 1]]; }
    else { const v1 = rc.rowBR(mid(0, q)) ?? rc.rowBR(1) ?? 1, v2 = rc.rowBR(mid(q, 1)) ?? rc.rowBR(0) ?? 0; rowPts = [[v1, 0], [v1, q], [v2, q], [v2, 1]]; }
    if (p == null) { const v = rc.colBR(.5) ?? .5; colPts = [[0, v], [1, v]]; }
    else { const v1 = rc.colBR(mid(0, p)) ?? rc.colBR(1) ?? 1, v2 = rc.colBR(mid(p, 1)) ?? rc.colBR(0) ?? 0; colPts = [[0, v1], [p, v1], [p, v2], [1, v2]]; }
    const pr = s("path", { class: "series", stroke: P_HUE, d: linePath(rowPts.map(([x, y]) => [f.X(x) + off, f.Y(y)])) });
    const pc = s("path", { class: "series", stroke: D_HUE, d: linePath(colPts.map(([x, y]) => [f.X(x), f.Y(y) - off])) });
    f.svg.append(pr, pc);
    for (const e of eqs) {
      const cx = f.X(e.x[0]), cy = f.Y(e.y[0]);
      const dot = s("g", { class: "eq-dot" }, s("circle", { cx, cy, r: 14, fill: "transparent" }), s("circle", { cx, cy, r: 6.5, class: "ring" }));
      dot.addEventListener("mousemove", (ev) => showTip(ev, h("b", { class: "tip-title" }, e.pure ? "Pure equilibrium" : "Mixed equilibrium"),
        tipRow(`Accuser plays ${NAME[a]}`, pct(e.x[0]), P_HUE), tipRow(`Defender plays ${NAME[a]}`, pct(e.y[0]), D_HUE), tipRow("Accuser's payoff", num(e.u)), tipRow("Defender's payoff", num(e.v))));
      dot.addEventListener("mouseleave", hideTip);
      f.svg.append(dot);
    }
    drawOn([pr, pc]);

    const always = (v) => (v === 1 ? `always does best with ${NAME[a]}` : v === 0 ? `always does best with ${NAME[c]}` : "is equally happy with either style");
    const accLine = q == null ? `The Accuser ${always(rc.rowBR(.5))}, whatever the Defender does, so the Accuser's line is one straight edge.`
      : `The Accuser's best reply flips when the Defender plays ${NAME[a]} exactly ${pct(q)} of the time. Below that the Accuser wants ${NAME[rc.rowBR(mid(0, q)) === 1 ? a : c]}; above it, ${NAME[rc.rowBR(mid(q, 1)) === 1 ? a : c]}.`;
    const defLine = p == null ? `The Defender ${always(rc.colBR(.5))}, so the Defender's line is one straight edge.`
      : `The Defender's best reply flips when the Accuser plays ${NAME[a]} exactly ${pct(p)} of the time.`;
    const eqLine = eqs.length === 0 ? "The lines overlap along an edge rather than crossing at a point, because some payoffs tie exactly."
      : eqs.length === 1 ? (eqs[0].pure ? `The lines meet once, in a corner: ${NAME[eqs[0].x[0] ? a : c]} Accuser against ${NAME[eqs[0].y[0] ? a : c]} Defender. With only these two styles, that is where the game settles.`
        : `The lines meet once, in the middle: the Accuser plays ${NAME[a]} ${pct(eqs[0].x[0])} of the time and the Defender plays it ${pct(eqs[0].y[0])} of the time. Neither has a single style that works, so both mix.`)
        : `The lines meet ${eqs.length} times, so this small game has ${eqs.length} stable outcomes: ${eqs.filter((e) => e.pure).length} in corners and ${eqs.filter((e) => !e.pure).length} in the middle. Which one happens depends on what each lawyer expects of the other.`;
    says("br", P(`With only ${NAME[a]} and ${NAME[c]} to choose from: `, accLine), P(defLine), P(eqLine),
      P(h("i", {}, "This looks at two styles only. The full four-style answer is in Chapter 3 and can differ.")));

    const da = (A[0][0] - A[1][0]) - (A[0][1] - A[1][1]), a0 = A[0][1] - A[1][1];
    const sg = (v) => (v < 0 ? `(${num(v)})` : num(v)); // negative numbers in brackets so the sums read cleanly
    $("#maths-br-dyn").replaceChildren(
      P(`Call q the chance the Defender plays ${NAME[a]}. Then the Accuser's average payoff from each style is:`),
      h("p", { class: "formula" }, `${NAME[a]}: ${sg(A[0][0])} × q + ${sg(A[0][1])} × (1 − q)`, h("br"), `${NAME[c]}: ${sg(A[1][0])} × q + ${sg(A[1][1])} × (1 − q)`),
      P(`The Accuser's line jumps where these two are equal. At q = 0, ${NAME[a]} leads ${NAME[c]} by ${num(a0)}. Going from q = 0 to q = 1 changes that lead by ${num(da)}. So the lead is zero at:`),
      h("p", { class: "formula" }, Math.abs(da) < 1e-9 ? "nowhere: the lead never changes, so there is no jump" : `q = ${sg(-a0)} ÷ ${sg(da)} = ${num(-a0 / da)}${q == null ? "   (outside 0 to 1, so no jump on the chart)" : ""}`),
      P("The Defender's jump point is found the same way from the Defender's four payoffs. A mixed equilibrium sits where each lawyer is exactly at the other's jump point: each one mixes just enough to leave the other with nothing to gain."));
  }

  /* ------------------------------------------------------------------ chapter 7: replicator dynamics */

  function renderEvo() {
    const k = STY.length, start = L.start ?? { x: Array(k).fill(1 / k), y: Array(k).fill(1 / k) };
    const steps = 300, traj = M.replicator(L.game.A, L.game.B, start.x, start.y, steps);
    const paths = [];
    for (const [host, key, who] of [[$("#evo-p"), "x", "Accusers"], [$("#evo-d"), "y", "Defenders"]]) {
      const f = frame(host, { w: 400, hgt: 260, m: { t: 12, r: 78, b: 38, l: 42 }, xMax: steps, xTicks: [0, 100, 200, 300], xLabel: "Rounds", yTicks: [0, .5, 1], label: `Share of ${who} using each style over ${steps} rounds` });
      const xOf = (i) => f.X(i);
      STY.forEach((n, si) => {
        const pth = s("path", { class: "series", stroke: HUE[n], d: linePath(traj.map((pt, i) => [xOf(i), f.Y(pt[key][si])])) });
        f.svg.append(pth); paths.push(pth);
      });
      const last = traj[steps][key];
      endLabels(f, STY.map((n, si) => ({ y: f.Y(last[si]), text: `${NAME[n]} ${pct(last[si])}`, show: last[si] > 0.03 })));
      crosshair(f, steps + 1, xOf, (i) => [h("b", { class: "tip-title" }, `${who}, round ${i}`), ...STY.map((n, si) => tipRow(NAME[n], pct(traj[i][key][si]), HUE[n]))],
        STY.map((n, si) => ({ hue: HUE[n], yOf: (i) => f.Y(traj[i][key][si]) })));
    }
    const end = traj[steps], top = (mix) => mix.indexOf(Math.max(...mix));
    const settled = Math.max(...end.x) > 0.9 && Math.max(...end.y) > 0.9, e = headline(L.an);
    const atNash = settled && L.an.pure.some(([i, j]) => i === top(end.x) && j === top(end.y));
    L.evoText = `After ${steps} rounds the Accusers are ${mixText(end.x)} and the Defenders are ${mixText(end.y)}.`;
    says("evo", P(L.start ? "From this random start: " : "From an equal start: ", L.evoText),
      P(atNash ? "That is a Nash equilibrium from Chapter 3. Lawyers who only copy what works end up exactly where careful reasoning said they would."
        : settled ? "The crowds have each settled on one style, but that pair is not the Nash equilibrium. Copying can get stuck somewhere that clever players would leave."
          : e && !e.pure ? "The crowds haven't settled on one style each. That fits Chapter 3, where the stable outcome was a mix: in a game like this the shares tend to keep moving or to hover around the mix." : "The crowds haven't fully settled after 300 rounds. Try another start to see whether they are heading the same way."));
    drawOn(paths);
  }

  /* ------------------------------------------------------------------ chapter 8: one trial */

  let beliefToken = 0;
  async function renderBelief() {
    const token = ++beliefToken, c = caseOf(L.caseId), key = `${L.caseId}|${L.pair.p}|${L.pair.d}|0`;
    $("#bf-p").value = L.pair.p; $("#bf-d").value = L.pair.d;
    let trial = B.trials[key];
    if (!trial && L.live) {
      try { trial = await (await fetch(`${API}/trial`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: L.caseId, prosecution: L.pair.p, defense: L.pair.d, seed: 0 }) })).json(); } catch { trial = null; }
    }
    if (token !== beliefToken) return;
    const host = $("#bf-chart");
    if (!trial?.events) { host.replaceChildren(P("No recorded trial for this pairing.")); return; }
    const els = c.elements, evs = trial.events, n = evs.length;
    const thr = trial.verdict.snapshot?.elements?.[0]?.threshold_probability ?? null;
    const series = els.map((e, k) => ({ id: e.id, name: e.name, hue: EL_HUE[k % EL_HUE.length], v: evs.map((ev) => ev.element_probabilities?.[e.id] ?? null) }));
    for (const sr of series) for (let i = 0; i < n; i++) if (sr.v[i] == null) sr.v[i] = i ? sr.v[i - 1] : 0.5;
    $("#bf-legend").replaceChildren(legend([...series.map((sr) => [sr.hue, sr.name]), thr != null && ["#7a6d5c", `The bar to clear (${pct(thr)})`, true]].filter(Boolean)));
    const f = frame(host, { w: 720, hgt: 320, m: { t: 14, r: 20, b: 40, l: 46 }, xMax: Math.max(1, n - 1), xTicks: [0, Math.round((n - 1) / 2), n - 1], xFmt: (t) => `Step ${t + 1}`, label: `How sure the judge is of each element across ${n} steps of the trial` });
    if (thr != null) f.svg.append(s("line", { class: "threshold", x1: f.m.l, x2: f.m.l + f.iw, y1: f.Y(thr), y2: f.Y(thr) }));
    const xOf = (i) => f.X(i), paths = series.map((sr) => s("path", { class: "series", stroke: sr.hue, d: linePath(sr.v.map((v, i) => [xOf(i), f.Y(v)])) }));
    f.svg.append(...paths);
    crosshair(f, n, xOf, (i) => [h("b", { class: "tip-title" }, `Step ${i + 1}`), h("span", { class: "tip-text" }, evs[i].summary ?? ""), ...series.map((sr) => tipRow(sr.name, pct(sr.v[i]), sr.hue))],
      series.map((sr) => ({ hue: sr.hue, yOf: (i) => f.Y(sr.v[i]) })));
    const pWon = ["guilty", "liable"].includes(trial.verdict.outcome), final = series.map((sr) => ({ name: sr.name, v: sr.v[n - 1] }));
    const short = thr == null ? [] : final.filter((x) => x.v < thr);
    const LP = trial.ledgers.prosecution, LD = trial.ledgers.defense;
    says("belief",
      P(bold(`${pWon ? "The Accuser" : "The Defender"} won this trial. `), `It ran for ${n} steps with a ${lower(L.pair.p)} Accuser against a ${lower(L.pair.d)} Defender.`),
      P(`Where each belief ended: ${list(final.map((x) => `"${x.name}" at ${pct(x.v)}`))}. `,
        thr == null ? "" : short.length && !pWon ? `${list(short.map((x) => `"${x.name}"`))} finished below the ${pct(thr)} bar, and the Accuser needs every one above it. That is why the Defender won.` : pWon ? `Everything the Accuser had to prove finished above the ${pct(thr)} bar.` : ""),
      P(`The Accuser showed ${LP.presented} piece${LP.presented === 1 ? "" : "s"} of evidence and had ${LP.excluded} thrown out. The Defender showed ${LD.presented} and had ${LD.excluded} thrown out. Payoffs under the real rules: Accuser ${num(trial.utilities.prosecution)}, Defender ${num(trial.utilities.defense)}.`));
    const Lthr = thr != null && thr > 0 && thr < 1 ? Math.log(thr / (1 - thr)) : null;
    $("#maths-belief-dyn").replaceChildren(
      P("The judge doesn't add percentages. Each accepted piece of evidence carries a weight, and the weights for one element are added up on a scale called log-odds. Strong, credible evidence has a big weight; weak or biased evidence a small one. Evidence for the Defender has a negative weight."),
      P("The total L is then turned into a belief between 0 and 1:"),
      h("p", { class: "formula" }, "belief = 1 / (1 + e^(−L))"),
      P("So L = 0 means 50%, and each extra point of weight moves the belief less the closer it gets to certainty. That's why lines flatten near the top."),
      Lthr != null && P(`This case uses the "${c.standard.replace(/_/g, " ")}" standard. The bar is L = ${num(Lthr, 1)}, which is a belief of ${pct(thr)}.`));
    drawOn(paths);
  }

  function setPair(p, d) {
    if (!STY.includes(p) || !STY.includes(d)) return false;
    L.pair = { p, d };
    renderLedger(); renderMatrix(); renderBelief();
    return true;
  }

  /* Open the home page with this case and these styles ready to play (handoff.js picks the hash up there). */
  function watchTrial() {
    location.href = `index.html#watch=${[L.caseId, L.pair.p, L.pair.d].map(encodeURIComponent).join("|")}`;
  }

  /* ------------------------------------------------------------------ chapter 5: 3D payoff landscape */

  const Land = (() => {
    const T = window.THREE, host = $("#land");
    if (!T) { host.append(P("The 3D view needs WebGL, which didn't load. The table in Chapter 2 shows the same numbers.")); return { update() {}, mode() {} }; }
    let renderer, scene, camera, group, visible = false, raf = 0, yaw = -0.65, pitch = 0.5, drag = null, idle = 0, ready = false;
    const bars = [], tiles = [];
    const GAP = 1.2, pos = (k) => (k - 1.5) * GAP, TILE = 0xd8cbb0, TILE_NASH = 0xd9a54a;

    function label(text, color, size = 0.4) {
      const cv = document.createElement("canvas"), ctx = cv.getContext("2d");
      cv.width = 256; cv.height = 72;
      ctx.font = "600 40px Inter, system-ui, sans-serif"; ctx.textAlign = "center"; ctx.textBaseline = "middle"; ctx.fillStyle = color;
      ctx.fillText(text, 128, 38);
      const sp = new T.Sprite(new T.SpriteMaterial({ map: new T.CanvasTexture(cv), transparent: true, depthWrite: false }));
      sp.scale.set(size * 3.55, size, 1);
      return sp;
    }

    function init() {
      if (ready) return true;
      try { renderer = new T.WebGLRenderer({ antialias: true, alpha: true }); } catch { host.append(P("This browser couldn't start the 3D view. The table in Chapter 2 shows the same numbers.")); return false; }
      renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
      host.append(renderer.domElement);
      scene = new T.Scene();
      camera = new T.PerspectiveCamera(34, 1, 0.1, 100);
      scene.add(new T.HemisphereLight(0xffffff, 0xcdbf9f, 1.05));
      const sun = new T.DirectionalLight(0xfff4dc, 0.7); sun.position.set(4, 9, 5); scene.add(sun);
      group = new T.Group(); scene.add(group);
      const box = new T.BoxGeometry(0.34, 1, 0.34); box.translate(0, 0.5, 0);
      const tileGeo = new T.BoxGeometry(GAP - 0.1, 0.03, GAP - 0.1);
      for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) {
        const tile = new T.Mesh(tileGeo, new T.MeshStandardMaterial({ color: TILE, transparent: true, opacity: 0.6, depthWrite: false, roughness: 1 }));
        tile.position.set(pos(j), 0, pos(i)); group.add(tile); tiles.push(tile);
        for (const [side, hue, dx] of [["p", P_HUE, -0.2], ["d", D_HUE, 0.2]]) {
          const mesh = new T.Mesh(box, new T.MeshStandardMaterial({ color: hue, roughness: 0.6, metalness: 0 }));
          mesh.position.set(pos(j) + dx, 0, pos(i)); mesh.scale.y = 0.001;
          mesh.userData = { i, j, side };
          group.add(mesh); bars.push(mesh);
        }
      }
      STY.forEach((n, k) => {
        const r = label(NAME[n], "#a23c22"); r.position.set(pos(-1) + 0.15, 0.05, pos(k)); group.add(r);
        const c = label(NAME[n], "#0b6f67"); c.position.set(pos(k), 0.05, pos(4) - 0.35); group.add(c);
      });

      const el = renderer.domElement, ray = new T.Raycaster(), ptr = new T.Vector2();
      el.addEventListener("pointerdown", (e) => { drag = { x: e.clientX, y: e.clientY, yaw, pitch }; el.setPointerCapture(e.pointerId); hideTip(); });
      el.addEventListener("pointermove", (e) => {
        if (drag) { yaw = drag.yaw - (e.clientX - drag.x) * 0.008; pitch = Math.min(1.2, Math.max(0.12, drag.pitch + (e.clientY - drag.y) * 0.006)); idle = 0; return; }
        const r = el.getBoundingClientRect();
        ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
        ray.setFromCamera(ptr, camera);
        const hit = ray.intersectObjects(bars.filter((x) => x.visible))[0];
        if (!hit) { hideTip(); return; }
        const { i, j, side } = hit.object.userData, cell = L.game.cells[i][j];
        showTip(e, h("b", { class: "tip-title" }, `${NAME[STY[i]]} Accuser vs ${NAME[STY[j]]} Defender`), side === "p" ? tipRow("Accuser's payoff", num(cell.a), P_HUE) : tipRow("Defender's payoff", num(cell.b), D_HUE));
      });
      const end = () => { drag = null; };
      el.addEventListener("pointerup", end); el.addEventListener("pointercancel", end); el.addEventListener("pointerleave", hideTip);
      new ResizeObserver(resize).observe(host);
      resize();
      ready = true;
      return true;
    }

    function resize() {
      const w = host.clientWidth, hgt = host.clientHeight;
      if (!w || !hgt) return;
      renderer.setSize(w, hgt, false);
      camera.aspect = w / hgt; camera.updateProjectionMatrix();
    }

    function tick() {
      raf = 0;
      if (!visible) return;
      if (!drag && !reduced) { idle += 1; if (idle > 90) yaw += 0.0016; }
      const rad = camera.aspect < 1 ? 15 : 10.6, cy = Math.sin(pitch) * rad, cr = Math.cos(pitch) * rad;
      camera.position.set(Math.sin(yaw) * cr, cy + 0.4, Math.cos(yaw) * cr);
      camera.lookAt(0, 0.5, 0);
      renderer.render(scene, camera);
      raf = requestAnimationFrame(tick);
    }
    const wake = () => { if (visible && !raf && ready) raf = requestAnimationFrame(tick); };

    new IntersectionObserver(([en]) => {
      visible = en.isIntersecting && !document.hidden;
      if (visible && init()) { update(); wake(); }
    }, { rootMargin: "120px" }).observe(host);
    document.addEventListener("visibilitychange", () => { if (document.hidden) visible = false; });

    function update() {
      if (!ready || !L.game) return;
      const { A, B: Bm } = L.game, span = Math.max(1e-9, ...A.flat().map(Math.abs), ...Bm.flat().map(Math.abs)), k = 2.7 / span;
      const nash = new Set(L.an.pure.map(([i, j]) => `${i}|${j}`));
      tiles.forEach((tile, n) => {
        const on = nash.has(`${Math.floor(n / 4)}|${n % 4}`);
        tile.material.color.set(on ? TILE_NASH : TILE); tile.material.opacity = on ? 0.95 : 0.6;
      });
      for (const bar of bars) {
        const { i, j, side } = bar.userData, v = (side === "p" ? A : Bm)[i][j] * k;
        bar.visible = L.landscape === "both" || L.landscape === side;
        const to = { s: Math.max(0.001, Math.abs(v)), y: v < 0 ? v : 0 };
        if (gsap && !reduced) { gsap.to(bar.scale, { y: to.s, duration: .7, ease: "power3.out", overwrite: true }); gsap.to(bar.position, { y: to.y, duration: .7, ease: "power3.out", overwrite: true }); }
        else { bar.scale.y = to.s; bar.position.y = to.y; }
        bar.material.opacity = v < 0 ? 0.6 : 1; bar.material.transparent = v < 0;
      }
      wake();
    }
    return { update, mode(v) { L.landscape = v; update(); } };
  })();

  function renderLandSays() {
    const { A, B: Bm } = L.game, cells = [];
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) cells.push([i, j]);
    const best = (Mx) => cells.reduce((m, c) => (Mx[c[0]][c[1]] > Mx[m[0]][m[1]] ? c : m));
    const pa = best(A), pd = best(Bm), same = pa[0] === pd[0] && pa[1] === pd[1];
    const nm = ([i, j]) => `${NAME[STY[i]]} Accuser vs ${NAME[STY[j]]} Defender`;
    // do the two lawyers' payoffs move together or against each other across the 16 boxes?
    const xs = A.flat(), ys = Bm.flat(), mx = M.mean(xs), my = M.mean(ys);
    const cov = M.mean(xs.map((x, k) => (x - mx) * (ys[k] - my))), sd = (v, m) => Math.sqrt(M.mean(v.map((x) => (x - m) ** 2)));
    const corr = sd(xs, mx) && sd(ys, my) ? cov / (sd(xs, mx) * sd(ys, my)) : 0;
    const onPeak = L.an.pure.some(([i, j]) => (i === pa[0] && j === pa[1]) || (i === pd[0] && j === pd[1]));
    says("land",
      P(`The Accuser's tallest bar is ${nm(pa)} (${num(A[pa[0]][pa[1]])}). The Defender's tallest is ${nm(pd)} (${num(Bm[pd[0]][pd[1]])}). `,
        same ? "They are on the same tile, so there is one outcome both would be happy with." : "They are on different tiles: each lawyer's favourite outcome is one the other would avoid."),
      P(corr < -0.4 ? "Across the floor, where one lawyer's bar is tall the other's tends to be short. This case is mostly a tug of war: what one gains, the other loses."
        : corr > 0.4 ? "Across the floor the two sets of bars tend to rise and fall together, so the lawyers' interests partly line up. Much of the payoff here is about cost, which both want to avoid."
          : "Across the floor there's no simple pattern between the two sets of bars. The lawyers are neither pure opponents nor on the same side."),
      L.an.pure.length ? P(onPeak ? "A gold tile sits under one of those tallest bars, so at least one lawyer gets their favourite outcome at equilibrium." : "No gold tile is under either tallest bar. Neither lawyer gets their favourite outcome, because the other would never go along with it.") : P("There are no gold tiles: no single pairing is stable, which matches the mixed outcome in Chapter 3."));
  }

  /* ------------------------------------------------------------------ chapter 9: the analyst */

  const SYN = { bold: "aggressive", aggressive: "aggressive", careful: "conservative", conservative: "conservative", cautious: "conservative", smart: "adaptive", adaptive: "adaptive", wild: "reckless", reckless: "reckless" };
  const STYLE_RE = "(bold|aggressive|careful|conservative|cautious|smart|adaptive|wild|reckless)";

  /* Everything the model is allowed to know: the lab's own numbers for the selected case. */
  function contextFor() {
    const c = caseOf(L.caseId), { game, an } = L, r2 = (v) => Math.round(v * 100) / 100;
    return JSON.stringify({
      case: { id: c.id, title: c.title, charge: c.charge, standard: c.standard, must_prove: c.elements.map((e) => e.name) },
      other_cases: cases.map((x) => ({ id: x.id, name: caseName(x) })),
      styles: STY.map((n) => `${n} = ${NAME[n]}`),
      weights: { win_value_V: game.weights.V, cost_weight_c: game.weights.c, sanction_weight_mu: game.weights.mu, defaults: M.DEFAULT_WEIGHTS },
      runs_per_pairing: L.runs,
      accuser_payoff_rows_accuser_cols_defender: game.A.map((r) => r.map(r2)),
      defender_payoff_rows_accuser_cols_defender: game.B.map((r) => r.map(r2)),
      accuser_win_rate: game.cells.map((r) => r.map((x) => r2(x.winP))),
      nash_equilibria: an.equilibria.map((e) => ({ kind: e.pure ? "pure" : "mixed", accuser: mixText(e.x), defender: mixText(e.y), accuser_payoff: r2(e.u), defender_payoff: r2(e.v) })),
      dominated_styles_removed_in_order: an.iesds.steps.map((st) => `${st.player === "row" ? "Accuser" : "Defender"}: ${NAME[STY[st.removed]]} (beaten by ${NAME[STY[st.by]]})`),
      safe_choice: { accuser: `${NAME[STY[an.security.row.index]]} guarantees ${r2(an.security.row.value)}`, defender: `${NAME[STY[an.security.col.index]]} guarantees ${r2(an.security.col.value)}` },
      best_combined_outcome: `${NAME[STY[an.welfare.cell[0]]]} Accuser vs ${NAME[STY[an.welfare.cell[1]]]} Defender, total ${r2(an.welfare.value)}`,
      copying_dynamics: L.evoText,
      selected_trial: `${NAME[L.pair.p]} Accuser vs ${NAME[L.pair.d]} Defender`,
    });
  }

  /* Carry out the changes the analyst (or the built-in reader) asked for. Returns what was done, in words. */
  function applyActions(actions) {
    const done = [];
    for (const a of Array.isArray(actions) ? actions.slice(0, 6) : []) {
      if (!a || typeof a !== "object") continue;
      if (a.type === "case" && a.id !== L.caseId && setCase(String(a.id))) done.push(`Switched to ${caseName(caseOf(L.caseId))}`);
      else if (a.type === "pair" && setPair(SYN[String(a.p).toLowerCase()], SYN[String(a.d).toLowerCase()])) done.push(`Now following the ${NAME[L.pair.p]} vs ${NAME[L.pair.d]} trial`);
      else if (a.type === "weights" && setWeights(a)) done.push(`Rules set to: win ${num(L.weights.V, 1)}, cost ${num(L.weights.c)}, penalty ${num(L.weights.mu)}`);
      else if (a.type === "reset" && setWeights(M.DEFAULT_WEIGHTS)) done.push("Back to the real rules");
    }
    return done;
  }

  /* Built-in analyst: reads plain requests and answers from the lab's numbers. Used when Ollama can't answer. */
  function builtIn(question) {
    const q = question.toLowerCase(), actions = [];
    const byName = cases.find((c) => q.includes(caseName(c).toLowerCase()) || q.includes(c.id) || caseName(c).toLowerCase().split(/\W+/).filter((w) => w.length > 4).some((w) => q.includes(w)));
    if (byName && /\b(show|switch|open|load|go to|use|try|look at|case)\b/.test(q)) actions.push({ type: "case", id: byName.id });
    const vs = q.match(new RegExp(`${STYLE_RE}\\s+(?:accuser\\s+)?(?:vs\\.?|versus|against|v)\\s+(?:an?\\s+)?${STYLE_RE}`));
    if (vs) actions.push({ type: "pair", p: vs[1], d: vs[2] });
    if (/\b(reset|real rules|default)\b/.test(q)) actions.push({ type: "reset" });
    else {
      const w = {}, cur = L.weights, factor = /\b(double|twice|2x|x2)\b/.test(q) ? 2 : /\b(triple|3x|x3)\b/.test(q) ? 3 : /\b(half|halve)\b/.test(q) ? 0.5 : null;
      const grab = (re) => { const m = q.match(re); return m ? parseFloat(m[1]) : null; };
      const which = /sanction|penalt|fine/.test(q) ? "mu" : /cost|budget|expens|cheap/.test(q) ? "c" : /win|stake|priz|reward/.test(q) ? "V" : null;
      const vV = grab(/win(?:ning)?(?: value| is worth| worth|s? (?:are|were) worth)?\D{0,12}?(\d+(?:\.\d+)?)/), vC = grab(/cost\D{0,24}?(\d+(?:\.\d+)?)/), vM = grab(/(?:sanction|penalt)\w*\D{0,24}?(\d+(?:\.\d+)?)/);
      if (vV != null) w.V = vV;
      if (vC != null) w.c = vC;
      if (vM != null) w.mu = vM;
      if (!Object.keys(w).length && which) {
        if (factor) w[which] = cur[which] * factor;
        else if (/\b(no|zero|free|remove|without)\b/.test(q)) w[which] = 0;
      }
      if (Object.keys(w).length) actions.push({ type: "weights", ...w });
    }
    const did = applyActions(actions);
    const { an, game } = L, e = headline(an), c = caseOf(L.caseId), out = [];
    const asksMeaning = /what is|what's|what does|what are|define|meaning|explain/.test(q);
    const best = (side) => {
      const d = side === "row" ? an.dominant.row : an.dominant.col, who = side === "row" ? "the Accuser" : "the Defender";
      if (d != null) return `${NAME[STY[d]]} is ${who}'s best style here whatever the other side does. In the table it is underlined in every ${side === "row" ? "column" : "row"}.`;
      return e ? `There is no single best style for ${who}; it depends on what the other side does. At the stable outcome ${who} plays ${mixText(side === "row" ? e.x : e.y)}.` : `There is no single best style for ${who}.`;
    };
    if (/\b(help|what can you|how do i)\b/.test(q)) out.push("Ask about the stable outcome, the best style for either lawyer, who wins, or the safe choice. You can also say things like \"show Bold vs Smart\", \"double the sanctions\", \"make a win worth 15\" or \"reset\".");
    else if (asksMeaning && /nash|equilib/.test(q)) out.push("A Nash equilibrium is a pair of styles where each one is the best reply to the other. Neither lawyer can do better by changing style alone, so the pair is stable.", e ? `In this case it is: ${eqText(e)}.` : "");
    else if (asksMeaning && /payoff/.test(q)) out.push(`A payoff is a lawyer's score for one trial: ${num(game.weights.V, 1)} for a win, minus ${num(game.weights.c)} for each budget point spent on evidence, minus ${num(game.weights.mu)} for each penalty point.`);
    else if (asksMeaning && /best repl/.test(q)) out.push("A best reply is the style that scores highest against one particular style of the other lawyer. In the table, best replies are underlined.");
    else if (/domina|always (better|worse)|cross/.test(q)) out.push(an.iesds.steps.length ? `A dominated style earns less than another whatever the other side does, so it can be crossed out. Here: ${an.iesds.steps.map((st) => `${NAME[STY[st.removed]]} for the ${st.player === "row" ? "Accuser" : "Defender"} (beaten by ${NAME[STY[st.by]]})`).join("; ")}.` : "No style is always worse than another in this case, so none can be crossed out.");
    else if (/mixed|random|unpredictab/.test(q)) { const m = an.equilibria.find((x) => !x.pure); out.push(m ? `A mixed strategy means picking at random with fixed chances so the other side can't predict you. Here: ${eqText(m)}. Average payoffs: Accuser ${num(m.u)}, Defender ${num(m.v)}.` : "There is no mixed equilibrium here. The stable outcome uses one fixed style each."); }
    else if (/safe|guarantee|maximin|worst case/.test(q)) out.push(`The safe choice ignores what the other side might do and looks only at worst cases. The Accuser can lock in at least ${num(an.security.row.value)} with ${NAME[STY[an.security.row.index]]}; the Defender at least ${num(an.security.col.value)} with ${NAME[STY[an.security.col.index]]}.`);
    else if (/pareto|efficien|both|together|welfare|cooperat/.test(q)) out.push(`The two payoffs add up to the most (${num(an.welfare.value)}) when a ${lower(STY[an.welfare.cell[0]])} Accuser meets a ${lower(STY[an.welfare.cell[1]])} Defender.${e ? ` The stable outcome adds up to ${num(e.u + e.v)}.` : ""}`);
    else if (/evol|replicat|copy|over time|crowd/.test(q)) out.push(`${L.evoText} Styles that earn more than average spread; the rest fade.`);
    else if (/who wins|win rate|chance|how often|likely/.test(q)) { const wr = game.cells.flat().map((x) => x.winP), lo = Math.min(...wr), hi = Math.max(...wr); out.push(lo === hi ? `The Accuser wins ${pct(lo)} of the time whichever styles are used, so style only changes the cost.` : `The Accuser's chance of winning runs from ${pct(lo)} to ${pct(hi)} depending on the styles.${e ? ` At the stable outcome it is ${pct(M.expected(game.cells.map((r) => r.map((x) => x.winP)), e.x, e.y))}.` : ""}`); }
    else if (/defend/.test(q) && /best|should|style|strateg|pick/.test(q)) out.push(best("col"));
    else if (/accus|prosecut/.test(q) && /best|should|style|strateg|pick/.test(q)) out.push(best("row"));
    else if (/best|should|optimal|strateg/.test(q)) out.push(best("row"), best("col"));
    else if (/payoff|formula|calculat|score|how .*work/.test(q)) out.push(`Each lawyer's payoff is ${num(game.weights.V, 1)} for a win, minus ${num(game.weights.c)} for each budget point spent on evidence, minus ${num(game.weights.mu)} for each penalty point. The table averages that over ${L.runs} run${L.runs === 1 ? "" : "s"} per pairing.`);
    else if (!did.length || /nash|equilib|stable|settle|why/.test(q)) {
      out.push(e ? `In ${caseName(c)}, the game settles on: ${eqText(e)}. That is a Nash equilibrium: each side is giving its best reply to the other, so nobody gains by switching alone. Payoffs there: Accuser ${num(e.u)}, Defender ${num(e.v)}.` : "The solver found no clean stable outcome for this case.");
      if (an.dominant.row != null || an.dominant.col != null) out.push([an.dominant.row != null && `${NAME[STY[an.dominant.row]]} is the Accuser's best reply to everything.`, an.dominant.col != null && `${NAME[STY[an.dominant.col]]} is the Defender's best reply to everything.`].filter(Boolean).join(" "));
    }
    if (did.length && !out.length && e) out.push(`The game now settles on: ${eqText(e)}. Payoffs: Accuser ${num(e.u)}, Defender ${num(e.v)}.`);
    return { text: out.filter(Boolean).join(" "), did };
  }

  function addMsg(role, text, meta, did) {
    const box = $("#chat");
    const node = h("div", { class: `msg ${role}` }, String(text).split(/\n{2,}/).map((para) => h("p", {}, para.replace(/\*\*/g, "").trim())),
      did?.length ? h("p", { class: "did" }, did.join(" · ")) : null, meta ? h("small", {}, meta) : null);
    box.append(node);
    box.scrollTop = box.scrollHeight;
    return node;
  }

  let asking = false;
  async function ask(question) {
    question = question.trim();
    if (!question || asking) return;
    asking = true;
    $("#chat-send").disabled = true;
    addMsg("user", question);
    const wait = addMsg("bot", "Thinking…");
    wait.classList.add("pending");
    let answered = false, why = "the local server isn't running";
    if (L.live) {
      try {
        const res = await fetch(`${API}/analyst`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question, context: contextFor(), history: L.chat.slice(-6) }) });
        const body = await res.json();
        if (res.ok && body.reply) {
          let reply = body.reply, actions = [];
          const m = reply.match(/ACTIONS:\s*(\[[\s\S]*\])\s*$/);
          if (m) { reply = reply.slice(0, m.index).trim(); try { actions = JSON.parse(m[1]); } catch { actions = []; } }
          const did = applyActions(actions);
          wait.remove();
          addMsg("bot", reply || "Done.", `${body.source === "cloud" ? "Ollama Cloud" : "Local Ollama"} · ${body.model}`, did);
          L.chat.push({ role: "user", content: question }, { role: "assistant", content: reply.slice(0, 1900) });
          $("#chat-status").textContent = "";
          answered = true;
        } else why = (body.reasons ?? [body.detail ?? "no reply"]).join("; ");
      } catch { why = "the analyst route didn't respond"; }
    }
    if (!answered) {
      const r = builtIn(question);
      wait.remove();
      addMsg("bot", r.text || "Done.", "Built-in analyst", r.did);
      $("#chat-status").textContent = `The AI model couldn't answer (${why}), so the lab's built-in analyst replied from the same numbers.`;
    }
    asking = false;
    $("#chat-send").disabled = false;
  }

  function renderChips() {
    const ideas = ["Where does this game settle, and why?", "What is a Nash equilibrium?", "Which style should the Defender pick?", "Double the sanctions", "Show Bold vs Smart", "Is there a safe choice?"];
    $("#chat-chips").replaceChildren(...ideas.map((t) => h("button", { type: "button", class: "chip-q", onclick: () => ask(t) }, t)));
  }

  /* ------------------------------------------------------------------ fresh trials from the local server */

  async function runLive() {
    const n = Number($("#lab-n").value), cid = L.caseId, btn = $("#lab-run"), bar = $("#lab-progress");
    const jobs = [];
    STY.forEach((r, i) => STY.forEach((d, j) => { for (let seed = 0; seed < n; seed++) jobs.push({ i, j, r, d, seed }); }));
    const total = jobs.length, samples = STY.map(() => STY.map(() => []));
    let done = 0, failed = 0;
    btn.disabled = true; bar.hidden = false;
    const step = () => { bar.firstChild.style.transform = `scaleX(${done / total})`; $("#lab-source").textContent = `Running trials: ${done} of ${total}`; };
    step();
    const worker = async () => {
      for (let job; (job = jobs.shift());) {
        try {
          const res = await fetch(`${API}/trial`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ case_id: cid, prosecution: job.r, defense: job.d, seed: job.seed }) });
          if (!res.ok) throw new Error(String(res.status));
          samples[job.i][job.j].push(M.summarize(await res.json()));
        } catch { failed++; }
        done++; step();
      }
    };
    await Promise.all(Array.from({ length: 6 }, worker));
    btn.disabled = false; bar.hidden = true;
    if (failed || samples.flat().some((x) => !x.length)) { $("#lab-source").textContent = `${failed} trial${failed === 1 ? "" : "s"} failed, so the numbers were left as they were.`; return; }
    L.liveCache[cid] = { samples, runs: n };
    if (L.caseId === cid) setCase(cid);
  }

  /* ------------------------------------------------------------------ wiring */

  function refresh() {
    recompute();
    $("#lab-source").textContent = L.source === "live" ? `Averaged over ${L.runs} fresh trials per pairing, run on this computer.`
      : `Using one recorded trial per pairing${L.live ? ". Run fresh trials for steadier averages." : "."}`;
    renderKpis(); renderLedger(); renderMatrix(); renderSolve(); renderBR(); renderLandSays(); renderWhatIf(); renderEvo(); renderBelief(); Land.update();
  }

  $("#lab-case").addEventListener("change", (e) => setCase(e.target.value));
  $("#lab-csv").addEventListener("click", downloadCsv);
  $("#lab-run").addEventListener("click", runLive);
  for (const k of ["V", "c", "mu"]) $(`#w-${k}`).addEventListener("input", (e) => setWeights({ [k]: e.target.value }));
  $("#w-reset").addEventListener("click", () => setWeights(M.DEFAULT_WEIGHTS));
  document.querySelectorAll("[data-land]").forEach((btn) => btn.addEventListener("click", () => {
    document.querySelectorAll("[data-land]").forEach((x) => x.setAttribute("aria-pressed", String(x === btn)));
    Land.mode(btn.dataset.land);
  }));
  // the two styles being compared must differ: changing one to match the other moves the other along
  const subChange = (other) => () => {
    const kept = $(other === "#br-a" ? "#br-b" : "#br-a").value;
    if ($(other).value === kept) $(other).value = STY.find((n) => n !== kept);
    L.sub = [$("#br-a").value, $("#br-b").value];
    renderBR();
  };
  $("#br-a").addEventListener("change", subChange("#br-b"));
  $("#br-b").addEventListener("change", subChange("#br-a"));
  $("#evo-equal").addEventListener("click", () => { L.start = null; renderEvo(); });
  $("#evo-random").addEventListener("click", () => {
    const mix = () => { const v = STY.map(() => 0.05 + Math.random()), t = v.reduce((x, y) => x + y, 0); return v.map((x) => x / t); };
    L.start = { x: mix(), y: mix() }; renderEvo();
  });
  for (const [id, side] of [["#bf-p", "p"], ["#lg-p", "p"], ["#bf-d", "d"], ["#lg-d", "d"]]) {
    $(id).addEventListener("change", (e) => (side === "p" ? setPair(e.target.value, L.pair.d) : setPair(L.pair.p, e.target.value)));
  }
  $("#bf-watch").addEventListener("click", watchTrial);
  $("#chat-form").addEventListener("submit", (e) => { e.preventDefault(); const box = $("#chat-in"); ask(box.value); box.value = ""; });

  L.samples = bundleSamples(L.caseId);
  $("#lab-case").value = L.caseId;
  refresh();
  renderChips();
  addMsg("bot", "Ask me anything about this case's game, or tell me what to change. The buttons below are good places to start.");

  // the chapter list on the left follows along as you scroll
  if ("IntersectionObserver" in window) {
    const links = new Map([...document.querySelectorAll(".rail a")].map((a) => [a.dataset.ch, a]));
    const spy = new IntersectionObserver((entries) => {
      for (const en of entries) if (en.isIntersecting) for (const [id, a] of links) a.setAttribute("aria-current", String(`ch-${id}` === en.target.id));
    }, { rootMargin: "-30% 0px -60% 0px" });
    document.querySelectorAll(".chapter").forEach((c) => spy.observe(c));
  }

  if (API) {
    const ctrl = new AbortController(), t = setTimeout(() => ctrl.abort(), 1500);
    fetch(`${API}/health`, { signal: ctrl.signal }).then((r) => r.ok).catch(() => false).then((ok) => {
      clearTimeout(t);
      L.live = ok;
      $("#lab-live").hidden = !ok;
      if (ok && L.source === "bundle") $("#lab-source").textContent = "Using one recorded trial per pairing. Run fresh trials for steadier averages.";
    });
  }
})();
