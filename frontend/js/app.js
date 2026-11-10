/* Sidebar, header, language and theme switches, router, and start-up. */
/* ============ shell: language, theme, router ============ */
function applyTheme() { document.documentElement.dataset.theme = THEME; localStorage.setItem("vx_theme", THEME); }
function chrome() {
  document.documentElement.lang = LANG === "hi" ? "hi" : "en";
  const pages = PAGES();
  $("#nav").innerHTML = `<div class="logo"><svg width="26" height="26" viewBox="0 0 26 26"><g fill="#f6b73c"><rect x="1" y="10" width="4" height="6" rx="2"/><rect x="7.5" y="4" width="4" height="18" rx="2"/><rect x="14" y="8" width="4" height="10" rx="2"/><rect x="20.5" y="12" width="4" height="2" rx="1"/></g></svg>Voicox</div>` +
    pages.map(k => `<a href="#${k}" data-k="${k}"><svg viewBox="0 0 24 24"><path d="${NAVIC[k]}"/></svg>${esc(t("nav")[PAGEKEYS.indexOf(k)])}</a>`).join("") +
    `<div class="promo" role="img" aria-label="Shop Smarter with Voicox"></div><small><span class="sys${LIVE ? "" : " off"}"><i></i>${esc(LIVE ? t("online") : t("off"))}</span><br>${esc(t("tagline"))}</small>`;
  $("#lang").value = LANG; $("#lang").setAttribute("aria-label", t("lang")); $("#th").setAttribute("aria-label", t("theme")); $("#th").title = t("theme");
  $("#mode").textContent = LIVE ? t("smp") : t("off"); $("#mode").className = "pill " + (LIVE ? "smp" : "off");
  $("#asof").textContent = t("asof") + " " + (TODAY ? new Date(TODAY + "T00:00:00") : new Date(2026, 9, 31)).toLocaleDateString(LANG === "hi" ? "hi-IN" : "en-IN", {day:"numeric", month:"short", year:"numeric"});
  $("#foot").textContent = t("ai");
}
function route() {
  const pages = PAGES(), k = pages.includes(location.hash.slice(1)) ? location.hash.slice(1) : "ask";
  stopAudio(); chrome(); document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.k === k));
  $("#title").textContent = t("ttl")[PAGEKEYS.indexOf(k)];
  P[k]($("#view")); window.scrollTo(0, 0);
}
$("#lang").onchange = e => {
  LANG = e.target.value; localStorage.setItem("vx_lang", LANG); route();
  if (LAST && LAST.again && $("#res")) runText(LAST.again);      // say the last answer again in the new language
};
$("#th").onclick = () => { THEME = THEME === "dark" ? "light" : "dark"; applyTheme(); route(); };
addEventListener("hashchange", route);
applyTheme();
(async () => {                                          // learn what the backend can do, then draw the page
  const [h, vs, bm] = await Promise.all([api("/health"), api("/voice-status"), api("/benchmark")]);
  LIVE = !!h; TODAY = h && h.today; BENCH = bm;
  VOICE = !!(vs && vs.configured && navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
  route();
})();
