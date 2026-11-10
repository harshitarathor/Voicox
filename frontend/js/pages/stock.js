/* Stock page: every item with counted stock, reorder level and status. */
P.stock = async v => {
  v.innerHTML = `<p class="heard">${esc(t("chk"))}</p>`;
  const s = await api("/stock-overview");
  if (!s || !s.items) { v.innerHTML = `<div class="card bad"><p class="big">${esc(t("nobe"))}</p><p class="heard">${esc(t("nobeH"))}</p></div>`; return; }
  const n = k => s.items.filter(i => i.status === k).length;
  v.innerHTML = `<p class="heard">${esc(t("stockS"))}</p>
  <div class="g"><div class="card kpi ok"><small>${esc(t("healthy"))}</small><b>${n("ok")}</b></div><div class="card kpi"><small>${esc(t("low"))}</small><b>${n("low")}</b></div><div class="card kpi bad"><small>${esc(t("out"))}</small><b>${n("out")}</b></div></div>
  <div class="card"><h3>${esc(t("stockT"))}</h3><div class="sc2"><table><tr><th>${esc(t("item"))}</th><th class="n">${esc(t("counted"))}</th><th class="n">${esc(t("reAt"))}</th><th>${esc(t("status"))}</th></tr>
  ${s.items.map(i => `<tr><td>${esc(pn(i.product))}</td><td class="n">${fmt(i.counted)}</td><td class="n">${fmt(i.reorder_level)}</td><td><span class="chip ${i.status === "ok" ? "okk" : "low"}">${esc(i.status === "ok" ? t("ok") : i.status === "low" ? t("reorder") : t("out"))}</span></td></tr>`).join("")}</table></div></div>`;
};
