/* Data page: the cleaning report (rows read, kept, duplicates removed, rejected). */
P.data = async v => {
  const rep = await api("/data-report");
  if (!rep || !rep.report) { v.innerHTML = `<div class="card bad"><p class="big">${esc(t("nobe"))}</p><p class="heard">${esc(t("nobeH"))}</p></div>`; return; }
  const R = rep.report, why = ["duplicates_removed","missing_date","invalid_quantity","invalid_price","invalid_discount","unknown_product"].filter(k => R[k] > 0).map(k => ({reason: kl(k), rows: R[k]}));
  const ex = R.rejected_rows || [], show = n => tbl(ex.slice(0, n).map(r => ({csv_line: r.csv_line, product: r.product || "-", reason: r.reason})));
  v.innerHTML = `<div class="card"><h3>${esc(t("latest"))}</h3><p class="big">${esc(rep.summary)}</p></div>
  <div class="g"><div class="card kpi a-blue"><small>${esc(t("rRead"))}</small><b>${fmt(R.rows_read)}</b></div><div class="card kpi a-mint"><small>${esc(t("rKept"))}</small><b>${fmt(R.rows_clean)}</b></div>
  <div class="card kpi a-violet"><small>${esc(t("rDup"))}</small><b>${fmt(R.duplicates_removed)}</b></div><div class="card kpi a-red"><small>${esc(t("rRej"))}</small><b>${fmt(R.rows_rejected)}</b></div></div>
  ${why.length ? `<div class="card"><h3>${esc(t("whyRej"))}</h3>${tbl(why)}</div>` : ""}
  ${ex.length ? `<div class="card"><h3>${esc(t("ex"))}</h3><div id="exl">${show(8)}</div>${ex.length > 8 ? `<p><button class="btn alt" id="mo">${esc(t("more"))}</button></p>` : ""}</div>` : ""}`;
  if ($("#mo")) { let open = false; $("#mo").onclick = () => { open = !open; $("#exl").innerHTML = show(open ? ex.length : 8); $("#mo").textContent = t(open ? "less" : "more"); }; }
};
