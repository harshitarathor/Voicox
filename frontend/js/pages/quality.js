/* Reliability page: the benchmark results. Only shown once benchmark/results.json exists. */
P.quality = v => {
  const B = BENCH, ring = (l, x) => { const n = pct(x); return `<div class="card ctr"><div class="ring" style="--v:${n ?? 0}"><b>${n === null ? "–" : n + "%"}</b></div>${esc(l)}</div>`; };
  const langs = Object.entries(B.by_language || {}), fails = B.failures || [];
  v.innerHTML = `<p class="heard">${esc(t("nq", B.n_questions ?? "?"))}${B.measured_on ? " · " + esc(B.measured_on) : ""}</p>
  <div class="g">${ring(t("speech"), B.speech_accuracy)}${ring(t("query"), B.query_accuracy)}${ring(t("answer"), B.answer_accuracy)}</div>
  <div class="g" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))">
  ${langs.length ? `<div class="card"><h3>${esc(t("byLang"))}</h3>${langs.map(([k, x]) => `<div class="bar"><span>${esc(k)}</span><div><i style="width:${pct(x)}%"></i></div><b class="n">${pct(x)}%</b></div>`).join("")}</div>` : ""}
  ${fails.length ? `<div class="card"><h3>${esc(t("fails"))}</h3>${tbl(fails.map(f => ({question: f.question, heard: f.heard, problem: f.problem})))}</div>` : ""}</div>`;
};
