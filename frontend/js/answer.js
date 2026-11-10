/* The answer card: what was heard, the numbers, chart or table, ranked causes, and the Listen button. */
/* ============ answer card ============ */
/* `again` is how to ask the same thing a second time, so a language change can re-word the answer. */
function handle(d, voice, again) {
  LAST = {d, voice: false, again: again || (d && d.transcript ? {text: d.transcript} : null)};
  renderAnswer(d, voice);
}
function renderAnswer(d, voice) {
  const res = $("#res"); if (!res) return;
  if (!d) { res.innerHTML = `<div class="card bad"><p class="big">${esc(t("nobe"))}</p><p class="heard">${esc(t("nobeH"))}</p></div>`; return; }
  if (!d.status) { res.innerHTML = `<div class="card bad"><p class="big">${esc(t("retry"))}</p></div>`; return; }
  let h = d.transcript ? `<p class="heard">${esc(t(voice ? "heard" : "asked"))} <b>${esc(d.transcript)}</b></p>` : "";
  h += understood(d.query);
  let say = "";
  if (d.status !== "ok") {
    const ask = d.status === "confirm" && d.query;
    h += `<div class="card ${ask ? "" : "bad"}"><div class="say"><p class="big">${esc(d.message || t("retry"))}</p>${d.status !== "error" ? `<button class="btn alt" id="play">▶ ${esc(t("listen"))}</button>` : ""}</div><p id="spmsg" class="heard"></p>
      ${ask ? `<p><button class="btn" id="yes">${esc(t("yes"))}</button> <button class="btn alt" id="no">${esc(t("no"))}</button></p>` : ""}</div>`;
    res.innerHTML = h; say = d.status === "error" ? "" : (d.voice || d.message);
    if ($("#yes")) $("#yes").onclick = () => runText({query: d.query, confirmed: true});
    if ($("#no")) $("#no").onclick = () => { res.innerHTML = ""; LAST = null; $("#q").focus(); };
  } else {
    const r = d.result || {}, c = r.chart, hasC = c && c.x && c.x.length; say = d.voice || r.spoken;
    h += `<div class="card"><div class="say"><p class="big">${esc(r.spoken)}</p><button class="btn alt" id="play">▶ ${esc(t("listen"))}</button></div><p id="spmsg" class="heard"></p>${tiles(r.numbers)}</div>`;
    if (r.causes && r.causes.length) h += causes(r.causes, r.disclaimer);
    if (r.alerts && r.alerts.length) h += `<div class="card"><h3>${esc(t("alerts"))}</h3>${r.alerts.map(a => `<p class="al">${esc(a.message)}</p>`).join("")}</div>`;
    if (hasC) h += `<div class="card"><h3>${esc(c.title || t("chart"))}</h3><div id="ch"></div></div>`;
    if (r.table && r.table.length) h += `<div class="card">${tbl(r.table)}</div>`;
    res.innerHTML = h; if (hasC) plot("ch", c.x.map(pn), c.y, c.type === "line"); fill();
  }
  const p = $("#play"); if (p) p.onclick = () => speak(say);
  if (voice && say) speak(say);                     // asked by voice, answered by voice
}
async function runText(body) {
  const res = $("#res"); if (!res) return; res.innerHTML = `<p class="heard">${esc(t("work"))}</p>`;
  handle(await api("/ask", body), false, body);
}
