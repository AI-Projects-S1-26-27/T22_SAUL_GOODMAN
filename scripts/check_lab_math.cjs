/* Checks the strategy lab's maths (courtroom/viz/web/lab-math.js) against the engine's own exact analysis
 * stored in data/bundle.js, plus a few textbook games. Run: node scripts/check_lab_math.cjs */
const fs = require("fs"), path = require("path");
const web = path.join(__dirname, "..", "courtroom", "viz", "web");
const M = require(path.join(web, "lab-math.js"));
const B = new Function("window", fs.readFileSync(path.join(web, "data", "bundle.js"), "utf8") + ";return window.COURTROOM_BUNDLE")({});
let fails = 0;
const ok = (cond, msg) => { if (!cond) { fails++; console.error("FAIL", msg); } };
const near = (a, b, t = 1e-6) => Math.abs(a - b) < t;

// 1. every bundled 2x2 game: same equilibria as the engine's exact support enumeration
for (const [cid, g] of Object.entries(B.games)) {
  const { A, B: Bm, equilibria, row_labels, col_labels } = g.analysis;
  const mine = M.supportEnumeration(A, Bm);
  if (!g.analysis.degenerate) ok(mine.length === equilibria.length, `${cid}: ${mine.length} equilibria, engine has ${equilibria.length}`);
  for (const e of equilibria) {
    const x = row_labels.map((l) => e.row_mix[l]), y = col_labels.map((l) => e.col_mix[l]);
    const r = M.regret(A, Bm, x, y);
    ok(r.row < 1e-6 && r.col < 1e-6, `${cid}: engine equilibrium has regret under lab maths`);
    if (!g.analysis.degenerate) ok(mine.some((m) => m.x.every((v, i) => near(v, x[i])) && m.y.every((v, j) => near(v, y[j]))), `${cid}: engine equilibrium missing from lab result`);
  }
  // replicator matches the engine's trajectory (bundle keeps every 5th step)
  const traj = M.replicator(A, Bm, [0.5, 0.5], [0.5, 0.5], 300);
  g.dynamics.forEach((pt, k) => ok(near(traj[k * 5].x[0], pt.x[0], 1e-9) && near(traj[k * 5].y[0], pt.y[0], 1e-9), `${cid}: replicator step ${k * 5}`));
}

// 2. utilities rebuilt from ledgers equal the engine's utilities for every bundled trial
for (const [key, t] of Object.entries(B.trials)) {
  const s = M.summarize(t);
  ok(near(M.utility(s.p, M.DEFAULT_WEIGHTS), t.utilities.prosecution) && near(M.utility(s.d, M.DEFAULT_WEIGHTS), t.utilities.defense), `${key}: utility mismatch`);
  const pWins = ["guilty", "liable"].includes(t.verdict.outcome);
  ok(s.p.win === (pWins ? 1 : 0) && s.d.win === (pWins ? 0 : 1), `${key}: winner mismatch`);
}

// 2b. the full 4x4 game of every case: pure equilibria are exactly 0/1, mixes add to 1, nobody gains by deviating
const STY = ["aggressive", "conservative", "adaptive", "reckless"];
for (const c of B.cases) {
  const g = M.buildGame(STY, STY, STY.map((r) => STY.map((d) => [M.summarize(B.trials[`${c.id}|${r}|${d}|0`])])));
  const an = M.analyze(g);
  for (const e of an.equilibria) {
    if (e.pure) ok(e.x.indexOf(1) >= 0 && e.y.indexOf(1) >= 0, `${c.id}: pure equilibrium is not exactly 0/1`);
    ok(near(e.x.reduce((a, v) => a + v, 0), 1, 1e-12) && near(e.y.reduce((a, v) => a + v, 0), 1, 1e-12), `${c.id}: mix does not add to 1`);
    const r = M.regret(g.A, g.B, e.x, e.y);
    ok(r.row < 1e-6 && r.col < 1e-6, `${c.id}: 4x4 equilibrium has regret`);
  }
  ok(an.pure.length === an.equilibria.filter((e) => e.pure).length, `${c.id}: pure Nash count differs between the two methods`);
}

// 3. textbook games
const pd = M.analyze({ A: [[3, 0], [5, 1]], B: [[3, 5], [0, 1]] }); // prisoner's dilemma
ok(pd.pure.length === 1 && pd.pure[0][0] === 1 && pd.pure[0][1] === 1, "PD: defect/defect");
ok(pd.iesds.rows.join() === "1" && pd.iesds.cols.join() === "1", "PD: dominance-solvable");
ok(pd.dominant.row === 1 && pd.dominant.col === 1, "PD: dominant strategies");
const mp = M.supportEnumeration([[1, -1], [-1, 1]], [[-1, 1], [1, -1]]); // matching pennies
ok(mp.length === 1 && near(mp[0].x[0], 0.5) && near(mp[0].y[0], 0.5), "matching pennies: 50/50");
const bos = M.supportEnumeration([[2, 0], [0, 1]], [[1, 0], [0, 2]]); // battle of the sexes
ok(bos.length === 3 && bos.filter((e) => e.pure).length === 2, "BoS: two pure and one mixed");
const mixed = bos.find((e) => !e.pure);
ok(mixed && near(mixed.x[0], 2 / 3) && near(mixed.y[0], 1 / 3), "BoS: mixed is (2/3, 1/3)");
const rps = M.supportEnumeration([[0, -1, 1], [1, 0, -1], [-1, 1, 0]], [[0, 1, -1], [-1, 0, 1], [1, -1, 0]]);
ok(rps.length === 1 && rps[0].x.every((v) => near(v, 1 / 3)), "rock-paper-scissors: uniform");
const rc = M.reaction2x2([[1, -1], [-1, 1]], [[-1, 1], [1, -1]]);
ok(near(rc.qStar, 0.5) && near(rc.pStar, 0.5), "matching pennies reaction curves cross at 1/2");

console.log(fails ? `${fails} check(s) failed` : `lab maths OK (${Object.keys(B.games).length} games, ${Object.keys(B.trials).length} trials, 5 textbook games)`);
process.exit(fails ? 1 : 0);
