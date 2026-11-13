/* Lets the strategy lab (lab.html) send a visitor here with a case and two styles already chosen.
 * The lab links to index.html#watch=<case>|<accuser style>|<defender style>; this picks that up once the
 * trial player (app.js) has loaded, selects them, and scrolls to "Brief your lawyers".
 * A generated case found by search (gen-<n>) is not in the recorded bundle: with the local server running it is fetched,
 * added to the docket as "found by search", and then selected the same way. Nothing else changes. */
(function () {
  "use strict";
  const m = location.hash.match(/^#watch=([^|]+)\|([^|]+)\|([^|]+)$/);
  if (!m) return;
  const [caseId, p, d] = m.slice(1).map(decodeURIComponent);
  history.replaceState(null, "", location.pathname + location.search);
  try {
    /* global S, B, STYLE_ORDER, selectCase, API */
    if (!STYLE_ORDER.includes(p) || !STYLE_ORDER.includes(d)) return;
    if (B.cases.some((c) => c.id === caseId)) {
      S.p = p; S.d = d;
      setTimeout(() => selectCase(caseId), 400);
    } else if (/^gen-\d+$/.test(caseId) && typeof API === "string" && window.Live) {
      fetch(`${API}/cases/${caseId}`).then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status))))).then((c) => {
        window.Live.addCase(c, "found");
        S.p = p; S.d = d;
        window.Live.showFilter("found");
        setTimeout(() => selectCase(c.id), 400);
      }).catch(() => { /* no server: the found case cannot be played here, leave the page as it is */ });
    }
  } catch { /* the player didn't load; leave the page as it is */ }
})();
