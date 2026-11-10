/* Stock Loss Detective: items whose counted stock does not match the records, with the "Why?" explainer. */
P.detective = async v => {
  v.innerHTML = `<p class="heard">${esc(t("chk"))}</p>`;
  const g = await api("/stock-gaps");
  if (!g || !g.result) { v.innerHTML = `<div class="card bad"><p class="big">${esc(t("nobe"))}</p><p class="heard">${esc(t("nobeH"))}</p></div>`; return; }
  const gaps = g.result.alerts;
  v.innerHTML = `<p class="heard">${esc(t("dIntro"))}</p><div class="g">${gaps.map(a => `<div class="card gap"><b>${esc(pn(a.product))}</b><div class="bg">${a.gap}</div><div class="row2"><span>${esc(t("exp"))} ${a.expected_stock}</span><span>${esc(t("counted"))} ${a.counted_stock}</span></div><button class="btn alt" data-p="${esc(a.product)}">${esc(t("why"))}</button></div>`).join("") || `<div class="card"><p class="big">${esc(t("allOk"))}</p></div>`}</div><div id="why"></div>`;
  v.querySelectorAll("[data-p]").forEach(b => b.onclick = async () => { const p = b.dataset.p; $("#why").innerHTML = `<p class="heard">${esc(t("look"))}</p>`;
    const d = await api("/ask", {text: `Why is there a gap in ${p}?`}), r = d && d.result;
    if (!r || !r.causes) { $("#why").innerHTML = `<div class="card bad"><p class="big">${esc((d && d.message) || t("retry"))}</p></div>`; return; }
    $("#why").innerHTML = `<h3 style="font:700 1.1rem var(--d);margin:6px 0 10px">${esc(t("whyH", pn(p)))}</h3><div class="card"><div class="say"><p class="big sm">${esc(r.spoken)}</p><button class="btn alt" id="play">▶ ${esc(t("listen"))}</button></div><p id="spmsg" class="heard"></p></div>` + causes(r.causes, r.disclaimer || t("leads")); fill();
    $("#play").onclick = () => speak(r.spoken); });
};
