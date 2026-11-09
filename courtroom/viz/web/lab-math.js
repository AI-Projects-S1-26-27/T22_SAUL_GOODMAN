/* Strategy lab maths: everything the lab plots is computed here, in the browser, from trial ledgers.
 * Pure functions, no DOM. Loads as window.LabMath in the page and as a CommonJS module in Node (for checks).
 *
 * A game is two payoff matrices over the same grid: A[i][j] is the Accuser's (row player's) payoff when the
 * Accuser plays style i and the Defender plays style j; B[i][j] is the Defender's (column player's).
 * Payoff per trial: U = V * win - c * spent - mu * sanctions (the engine's formula, courtroom/engine/utility.py).
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.LabMath = api;
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const EPS = 1e-9;
  const DEFAULT_WEIGHTS = { V: 10, c: 0.3, mu: 1 };
  const sum = (xs) => xs.reduce((a, b) => a + b, 0);
  const mean = (xs) => (xs.length ? sum(xs) / xs.length : 0);
  const stderr = (xs) => {
    if (xs.length < 2) return 0;
    const m = mean(xs);
    return Math.sqrt(sum(xs.map((x) => (x - m) ** 2)) / (xs.length - 1) / xs.length);
  };

  /* One trial reduced to what the payoff formula needs. `trial` is a TrialResult (bundle or /api/trial). */
  function summarize(trial) {
    const side = (name) => {
      const L = trial.ledgers[name];
      // utilities were produced with the default weights, so the win flag can be read back out of them
      const win = Math.round((trial.utilities[name] + DEFAULT_WEIGHTS.c * L.spent + DEFAULT_WEIGHTS.mu * L.sanctions) / DEFAULT_WEIGHTS.V);
      return { win: win ? 1 : 0, spent: L.spent, sanctions: L.sanctions, admitted: L.admitted, excluded: L.excluded, objections: L.objections, sustained: L.sustained };
    };
    return { p: side("prosecution"), d: side("defense"), outcome: trial.verdict.outcome };
  }

  const utility = (s, w) => w.V * s.win - w.c * s.spent - w.mu * s.sanctions;

  /* samples[i][j] is a list of summarize() results for row style i against column style j. */
  function buildGame(rows, cols, samples, weights = DEFAULT_WEIGHTS) {
    const cells = rows.map((_, i) => cols.map((__, j) => {
      const runs = samples[i][j];
      const up = runs.map((r) => utility(r.p, weights)), ud = runs.map((r) => utility(r.d, weights));
      return {
        n: runs.length, a: mean(up), b: mean(ud), seA: stderr(up), seB: stderr(ud),
        winP: mean(runs.map((r) => r.p.win)),
        spentP: mean(runs.map((r) => r.p.spent)), spentD: mean(runs.map((r) => r.d.spent)),
        sanctP: mean(runs.map((r) => r.p.sanctions)), sanctD: mean(runs.map((r) => r.d.sanctions)),
      };
    }));
    return { rows, cols, cells, A: cells.map((r) => r.map((c) => c.a)), B: cells.map((r) => r.map((c) => c.b)), weights: { ...weights } };
  }

  /* Best responses. row[j] = set of row indices that maximise A[.][j]; col[i] = set of column indices maximising B[i][.]. */
  function bestResponses(A, B) {
    const m = A.length, n = A[0].length;
    const row = [], col = [];
    for (let j = 0; j < n; j++) {
      const best = Math.max(...A.map((r) => r[j]));
      row.push(new Set(A.map((r, i) => (r[j] >= best - EPS ? i : -1)).filter((i) => i >= 0)));
    }
    for (let i = 0; i < m; i++) {
      const best = Math.max(...B[i]);
      col.push(new Set(B[i].map((v, j) => (v >= best - EPS ? j : -1)).filter((j) => j >= 0)));
    }
    return { row, col };
  }

  function pureNash(A, B) {
    const br = bestResponses(A, B), out = [];
    for (let i = 0; i < A.length; i++) for (let j = 0; j < A[0].length; j++) if (br.row[j].has(i) && br.col[i].has(j)) out.push([i, j]);
    return out;
  }

  /* Iterated elimination of strictly dominated strategies (by another pure strategy). Returns the order of removal. */
  function iesds(A, B) {
    let rows = A.map((_, i) => i), cols = A[0].map((_, j) => j);
    const steps = [];
    for (let changed = true; changed;) {
      changed = false;
      for (const r of rows) {
        const by = rows.find((o) => o !== r && cols.every((j) => A[o][j] > A[r][j] + EPS));
        if (by !== undefined) { steps.push({ player: "row", removed: r, by }); rows = rows.filter((x) => x !== r); changed = true; break; }
      }
      if (changed) continue;
      for (const c of cols) {
        const by = cols.find((o) => o !== c && rows.every((i) => B[i][o] > B[i][c] + EPS));
        if (by !== undefined) { steps.push({ player: "col", removed: c, by }); cols = cols.filter((x) => x !== c); changed = true; break; }
      }
    }
    return { rows, cols, steps };
  }

  /* Gaussian elimination with partial pivoting. Returns null when the system is singular. */
  function solve(M, b) {
    const n = M.length, a = M.map((r, i) => [...r, b[i]]);
    for (let c = 0; c < n; c++) {
      let p = c;
      for (let r = c + 1; r < n; r++) if (Math.abs(a[r][c]) > Math.abs(a[p][c])) p = r;
      if (Math.abs(a[p][c]) < 1e-11) return null;
      [a[c], a[p]] = [a[p], a[c]];
      for (let r = 0; r < n; r++) {
        if (r === c) continue;
        const f = a[r][c] / a[c][c];
        if (f) for (let k = c; k <= n; k++) a[r][k] -= f * a[c][k];
      }
    }
    return a.map((r, i) => r[n] / r[i]);
  }

  const subsets = (n, k) => {
    const out = [];
    (function rec(start, acc) {
      if (acc.length === k) { out.push(acc); return; }
      for (let i = start; i < n; i++) rec(i + 1, [...acc, i]);
    })(0, []);
    return out;
  };

  const expected = (M, x, y) => sum(x.map((xi, i) => xi * sum(y.map((yj, j) => yj * M[i][j]))));
  const rowPayoffs = (A, y) => A.map((r) => sum(r.map((v, j) => v * y[j])));
  const colPayoffs = (B, x) => B[0].map((_, j) => sum(B.map((r, i) => r[j] * x[i])));

  /* How much either player could gain by deviating alone. Zero (within tolerance) means a Nash equilibrium. */
  function regret(A, B, x, y) {
    return { row: Math.max(...rowPayoffs(A, y)) - expected(A, x, y), col: Math.max(...colPayoffs(B, x)) - expected(B, x, y) };
  }

  /* Support enumeration: every Nash equilibrium of a non-degenerate bimatrix game, pure and mixed.
   * For each pair of equal-size supports, solve the indifference conditions, then keep the solution only
   * if the mixes are valid probabilities and nobody gains by leaving the support. */
  function supportEnumeration(A, B) {
    const m = A.length, n = A[0].length, found = [];
    for (let k = 1; k <= Math.min(m, n); k++) {
      for (const I of subsets(m, k)) for (const J of subsets(n, k)) {
        // y on J makes every row in I earn the same u: sum_j A[i][j] y_j - u = 0, sum y = 1
        const My = I.map((i) => [...J.map((j) => A[i][j]), -1]); My.push([...J.map(() => 1), 0]);
        // x on I makes every column in J earn the same v
        const Mx = J.map((j) => [...I.map((i) => B[i][j]), -1]); Mx.push([...I.map(() => 1), 0]);
        const rhs = [...Array(k).fill(0), 1];
        const sy = solve(My, rhs), sx = solve(Mx, rhs);
        if (!sy || !sx) continue;
        if (sy.slice(0, k).some((v) => v < -1e-7) || sx.slice(0, k).some((v) => v < -1e-7)) continue;
        const x = Array(m).fill(0), y = Array(n).fill(0);
        I.forEach((i, t) => { x[i] = Math.max(0, sx[t]); });
        J.forEach((j, t) => { y[j] = Math.max(0, sy[t]); });
        // a true support-k equilibrium puts weight on all k strategies; smaller supports are found on their own pass
        if (I.some((i) => x[i] < 1e-7) || J.some((j) => y[j] < 1e-7)) continue;
        // remove rounding error so each mix adds up to exactly 1 (and a pure strategy is exactly 1)
        if (k === 1) { x[I[0]] = 1; y[J[0]] = 1; }
        else { const tx = sum(x), ty = sum(y); for (const i of I) x[i] /= tx; for (const j of J) y[j] /= ty; }
        const g = regret(A, B, x, y);
        if (g.row > 1e-6 || g.col > 1e-6) continue;
        if (found.some((e) => e.x.every((v, i) => Math.abs(v - x[i]) < 1e-6) && e.y.every((v, j) => Math.abs(v - y[j]) < 1e-6))) continue;
        found.push({ x, y, u: expected(A, x, y), v: expected(B, x, y), pure: k === 1, support: [I, J] });
      }
    }
    return found;
  }

  /* Two-population replicator dynamics, the same update as courtroom/gametheory/dynamics.py. */
  function replicator(A, B, x0, y0, steps = 300, dt = 0.05) {
    const m = A.length, n = A[0].length;
    let x = [...x0], y = [...y0];
    const traj = [{ x: [...x], y: [...y] }];
    for (let s = 0; s < steps; s++) {
      const ay = rowPayoffs(A, y), xb = colPayoffs(B, x);
      const ubar = sum(x.map((v, i) => v * ay[i])), vbar = sum(y.map((v, j) => v * xb[j]));
      x = x.map((v, i) => Math.max(0, v + dt * v * (ay[i] - ubar)));
      y = y.map((v, j) => Math.max(0, v + dt * v * (xb[j] - vbar)));
      const sx = sum(x) || 1, sy = sum(y) || 1;
      x = x.map((v) => v / sx); y = y.map((v) => v / sy);
      traj.push({ x: [...x], y: [...y] });
    }
    return traj;
  }

  /* Maximin over pure strategies: the payoff each player can guarantee whatever the other does. */
  function security(A, B) {
    const rowMins = A.map((r) => Math.min(...r));
    const colMins = B[0].map((_, j) => Math.min(...B.map((r) => r[j])));
    const ri = rowMins.indexOf(Math.max(...rowMins)), cj = colMins.indexOf(Math.max(...colMins));
    return { row: { index: ri, value: rowMins[ri] }, col: { index: cj, value: colMins[cj] } };
  }

  /* Cells where no other cell is at least as good for both players and better for one. */
  function pareto(A, B) {
    const cells = [];
    for (let i = 0; i < A.length; i++) for (let j = 0; j < A[0].length; j++) cells.push([i, j]);
    return cells.filter(([i, j]) => !cells.some(([k, l]) => A[k][l] >= A[i][j] - EPS && B[k][l] >= B[i][j] - EPS && (A[k][l] > A[i][j] + EPS || B[k][l] > B[i][j] + EPS)));
  }

  function welfare(A, B) {
    let best = [0, 0];
    for (let i = 0; i < A.length; i++) for (let j = 0; j < A[0].length; j++) if (A[i][j] + B[i][j] > A[best[0]][best[1]] + B[best[0]][best[1]]) best = [i, j];
    return { cell: best, value: A[best[0]][best[1]] + B[best[0]][best[1]] };
  }

  /* A strategy that is a best response to everything the other side can do (weakly dominant), or null. */
  function dominant(A, B) {
    const br = bestResponses(A, B);
    const row = A.map((_, i) => i).find((i) => br.row.every((s) => s.has(i)));
    const col = A[0].map((_, j) => j).find((j) => br.col.every((s) => s.has(j)));
    return { row: row ?? null, col: col ?? null };
  }

  /* 2x2 reaction curves. p = chance the Accuser plays style r0, q = chance the Defender plays style c0.
   * qStar is the q at which the Accuser is indifferent (null if they never are); pStar likewise for the Defender. */
  function reaction2x2(A, B) {
    const da = (A[0][0] - A[1][0]) - (A[0][1] - A[1][1]);      // slope of the Accuser's gain from r0 as q rises
    const a0 = A[0][1] - A[1][1];                               // that gain at q = 0
    const db = (B[0][0] - B[0][1]) - (B[1][0] - B[1][1]);
    const b0 = B[1][0] - B[1][1];                               // the Defender's gain from c0 at p = 0
    const cut = (slope, at0) => (Math.abs(slope) < EPS ? null : -at0 / slope);
    const qStar = cut(da, a0), pStar = cut(db, b0);
    // best reply of the row player to q: 1 (play r0), 0 (play r1) or null (indifferent)
    const rowBR = (q) => { const g = a0 + da * q; return g > EPS ? 1 : g < -EPS ? 0 : null; };
    const colBR = (p) => { const g = b0 + db * p; return g > EPS ? 1 : g < -EPS ? 0 : null; };
    return { qStar: qStar !== null && qStar > -EPS && qStar < 1 + EPS ? qStar : null, pStar: pStar !== null && pStar > -EPS && pStar < 1 + EPS ? pStar : null, rowBR, colBR };
  }

  function analyze(game) {
    const { A, B } = game;
    const equilibria = supportEnumeration(A, B);
    return {
      br: bestResponses(A, B), pure: pureNash(A, B), equilibria, iesds: iesds(A, B), security: security(A, B),
      pareto: pareto(A, B), welfare: welfare(A, B), dominant: dominant(A, B),
    };
  }

  return { DEFAULT_WEIGHTS, mean, stderr, summarize, utility, buildGame, bestResponses, pureNash, iesds, solve, expected, regret, supportEnumeration, replicator, security, pareto, welfare, dominant, reaction2x2, analyze };
});
