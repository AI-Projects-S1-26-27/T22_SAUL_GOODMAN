/* Lets the strategy lab (lab.html) send a visitor here with a case and two styles already chosen.
 * The lab links to index.html#watch=<case>|<accuser style>|<defender style>; this picks that up once the
 * trial player (app.js) has loaded, selects them, and scrolls to "Brief your lawyers". Nothing else changes. */
(function () {
  "use strict";
  const m = location.hash.match(/^#watch=([^|]+)\|([^|]+)\|([^|]+)$/);
  if (!m) return;
  const [caseId, p, d] = m.slice(1).map(decodeURIComponent);
  history.replaceState(null, "", location.pathname + location.search);
  try {
    /* global S, B, STYLE_ORDER, selectCase */
    if (!B.cases.some((c) => c.id === caseId) || !STYLE_ORDER.includes(p) || !STYLE_ORDER.includes(d)) return;
    S.p = p; S.d = d;
    setTimeout(() => selectCase(caseId), 400);
  } catch { /* the player didn't load; leave the page as it is */ }
})();
