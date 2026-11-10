/* Ask page: hero banner with the mic and text box, quick-question chips, and the live home dashboard (KPI cards, trend, top products, stock health). */
P.ask = async v => {
  const ttl = esc(t("heroT")).replace(/\*(.+?)\*/g, "<span>$1</span>"), cq = t("chipsQ");
  v.innerHTML = `<section class="banner"><div class="hero"><h2>${ttl}</h2><p>${esc(t("heroS"))}</p></div>
  <div class="askrow">${VOICE ? `<div class="orb"><i class="w l"></i><button type="button" class="mic" id="mic" aria-label="${esc(t("mic"))}">${MIC}</button><i class="w r"></i></div>` : ""}
  <form class="ask" id="f"><input id="q" autocomplete="off" aria-label="${esc(t("ask"))}" placeholder="${esc(t("ph"))}"><button class="btn">${SEND}${esc(t("ask"))}</button></form></div>
  <div class="chips${VOICE ? "" : " no"}">${t("chipsS").map((s, i) => `<button type="button" data-q="${esc(cq[i])}">${esc(s)}</button>`).join("")}</div>
  <div class="hint${VOICE ? "" : " no"}" id="hint" aria-live="polite"></div></section><div id="res" aria-live="polite"></div><div id="home"></div>`;
  $("#f").onsubmit = e => { e.preventDefault(); const x = $("#q").value.trim(); if (x) runText({text: x}); };
  v.querySelectorAll(".chips button").forEach(b => b.onclick = () => { $("#q").value = b.dataset.q; runText({text: b.dataset.q}); });
  if ($("#mic")) $("#mic").onclick = micToggle;
  if (LAST) renderAnswer(LAST.d, false);           // keep the answer when language or theme changes
  const s = await api("/summary");
  if (!$("#home")) return;
  if (!s || s.revenue_30d === undefined) { $("#home").innerHTML = LAST ? "" : `<div class="card bad"><p class="big">${esc(t("nobe"))}</p><p class="heard">${esc(t("nobeH"))}</p></div>`; return; }
  const H = s.health, tot = H.total || 1, g1 = H.healthy / tot * 100, g2 = g1 + H.low / tot * 100;
  const maxTop = Math.max(...s.top.map(r => r.value), 1);
  const K = (c, lb, val, sub, extra, href) => `<${href ? "a" : "div"} class="kp${href ? "" : " nolink"}" style="--c:${c}"${href ? ` href="#${href}"` : ""}><small>${esc(lb)}</small><b>${val}</b>${sub}${extra || ""}</${href ? "a" : "div"}>`;
  $("#home").innerHTML = `<div class="g" style="grid-template-columns:repeat(auto-fit,minmax(200px,1fr))">
    ${K("var(--blue)", t("sales30"), inr(s.revenue_30d), chg(s.revenue_week_change), spark(s.trend && s.trend.y))}
    ${K("var(--violet)", t("units30"), fmt(s.units_30d), chg(s.units_week_change), spark(s.units_trend && s.units_trend.y))}
    ${K("var(--orange)", t("lowT"), s.low_count, `<i>${esc(t("lowS"))}</i>`, "")}
    ${K("var(--red)", t("mism"), s.mismatch_count, `<i>${esc(t("mismS"))}</i>`, `<i class="more">${esc(t("viewD"))} →</i>`, "detective")}</div>
  <div class="dash">
    <div class="card"><h3>${esc(t("trend"))}</h3><div id="tr"></div></div>
    <div class="card"><h3>${esc(t("topP"))}</h3>${s.top.map((r, i) => `<div class="bar"><span><em class="rn">${i + 1}</em>${esc(pn(r.label))}</span><div><i style="width:${r.value / maxTop * 100}%"></i></div><b class="n">${inr(r.value)}</b></div>`).join("")}</div>
    <div class="card ctr"><h3>${esc(t("health"))}</h3><div class="ring" style="background:conic-gradient(var(--mint) 0 ${g1}%,var(--orange) ${g1}% ${g2}%,var(--red) ${g2}% 100%)"><b>${Math.round(g1)}%</b></div>
      <div class="lg"><span><i style="background:var(--mint)"></i>${esc(t("healthy"))}</span><b>${H.healthy}</b></div>
      <div class="lg"><span><i style="background:var(--orange)"></i>${esc(t("low"))}</span><b>${H.low}</b></div>
      <div class="lg"><span><i style="background:var(--red)"></i>${esc(t("out"))}</span><b>${H.out}</b></div></div></div>
  ${s.insight ? `<div class="insight"><span>💡 <b>${esc(t("insight"))}:</b> ${esc(s.insight.text)}</span><a class="btn" href="#data">${esc(t("runR"))}</a></div>` : ""}`;
  plot("tr", s.trend.x, s.trend.y, true);
};
