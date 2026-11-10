/* Sales page: 7-day / 30-day toggle, KPI cards, daily revenue chart, top sellers and slow movers. */
P.sales = async v => {
  v.innerHTML = `<p class="heard">${esc(t("chk"))}</p>`;
  const s = await api("/sales-overview");
  if (!s || !s.daily) { v.innerHTML = `<div class="card bad"><p class="big">${esc(t("nobe"))}</p><p class="heard">${esc(t("nobeH"))}</p></div>`; return; }
  const X = s.daily.x, Y = s.daily.y, mx = Math.max(...s.top.map(r => r.value), 1);
  const bars = L => L.map(r => `<div class="bar"><span>${esc(pn(r.label))}</span><div><i style="width:${r.value / mx * 100}%"></i></div><b class="n">${inr(r.value)}</b></div>`).join("");
  v.innerHTML = `<div class="seg" id="seg"><button data-n="7">${esc(t("d7"))}</button><button data-n="30" class="on">${esc(t("d30"))}</button></div>
  <div class="g" id="kp"></div><div class="card"><h3>${esc(t("daily"))}</h3><div id="ch"></div></div>
  <div class="g" style="grid-template-columns:repeat(auto-fit,minmax(300px,1fr))"><div class="card"><h3>${esc(t("topS"))}</h3>${bars(s.top)}</div><div class="card"><h3>${esc(t("slow"))}</h3>${bars(s.slow)}</div></div>`;
  const draw = n => {
    const cut = new Date(Date.parse(s.today + "T00:00:00Z") - (n - 1) * 864e5).toISOString().slice(0, 10);
    const x = X.filter(d => d >= cut), y = Y.filter((_, i) => X[i] >= cut);
    const tot = y.reduce((a, b) => a + b, 0), bi = y.indexOf(Math.max(...y));
    $("#kp").innerHTML = `<div class="card kpi"><small>${esc(t("rev"))}</small><b>${inr(tot)}</b><i>${esc(t("lastN", n))}</i></div>
      <div class="card kpi"><small>${esc(t("avg"))}</small><b>${inr(tot / n)}</b></div>
      <div class="card kpi ok"><small>${esc(t("bestD"))}</small><b>${inr(y[bi])}</b><i>${esc(x[bi])}</i></div>`;
    plot("ch", x, y, true);
  };
  draw(30);
  $("#seg").onclick = e => { const n = e.target.dataset.n; if (!n) return; document.querySelectorAll("#seg button").forEach(b => b.classList.toggle("on", b === e.target)); draw(+n); };
};
