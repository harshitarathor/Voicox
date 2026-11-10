/* Voice: Timbre plays the answer (/speak); the microphone is recorded, converted to 16 kHz WAV and sent to Prisma (/ask-audio). */
/* ============ voice out: Timbre via /speak ============ */
let AUD = null; const CACHE = new Map();
const clip = s => { s = String(s || "").replace(/\s+/g, " ").trim(); if (s.length <= 600) return s; const c = s.slice(0, 600), e = Math.max(c.lastIndexOf(". "), c.lastIndexOf("? ")); return e > 100 ? c.slice(0, e + 1) : c; };
function stopAudio() { if (AUD) { AUD.pause(); AUD = null; } document.querySelectorAll("#play").forEach(b => { b.textContent = "▶ " + t("listen"); b.disabled = false; }); }
async function speak(text) {
  const btn = $("#play"), msg = $("#spmsg"); stopAudio(); if (msg) msg.textContent = ""; text = clip(text); if (!text) return;
  if (btn) { btn.disabled = true; btn.textContent = "…"; }
  try {
    const ck = LANG + "|" + text; let url = CACHE.get(ck);
    if (!url) { const r = await fetch("/speak", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text, lang: LANG})});
      if (!r.ok) { let m = ""; try { m = (await r.json()).message || ""; } catch (e) {} throw new Error(m || t("retry")); }
      url = URL.createObjectURL(await r.blob()); CACHE.set(ck, url); }
    AUD = new Audio(url); AUD.onended = stopAudio;
    if (btn) { btn.disabled = false; btn.textContent = "■ " + t("stop"); btn.onclick = () => { stopAudio(); btn.onclick = () => speak(text); }; }
    await AUD.play();
  } catch (e) {
    stopAudio(); if (e && e.name === "NotAllowedError") return;       // browser blocked autoplay: the button still works
    const m = $("#spmsg"); if (m) m.textContent = t("speakFail") + " " + e.message; }
}
/* ============ voice in: microphone -> 16 kHz WAV -> /ask-audio (Gnani Prisma) ============ */
function encodeWav(f32, rate) {
  const n = f32.length, b = new ArrayBuffer(44 + n * 2), v = new DataView(b), w = (o, s) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  w(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); w(8, "WAVE"); w(12, "fmt "); v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); w(36, "data"); v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) { const s = Math.max(-1, Math.min(1, f32[i])); v.setInt16(44 + i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true); }
  return new Blob([b], {type: "audio/wav"});
}
async function toWav16k(blob) {                       // Prisma does not accept the browser's WebM, so convert here
  const AC = window.AudioContext || window.webkitAudioContext, ctx = new AC();
  const audio = await ctx.decodeAudioData(await blob.arrayBuffer()); ctx.close();
  const off = new OfflineAudioContext(1, Math.max(1, Math.ceil(audio.duration * 16000)), 16000), src = off.createBufferSource();
  src.buffer = audio; src.connect(off.destination); src.start();
  return encodeWav((await off.startRendering()).getChannelData(0), 16000);
}
let REC = null; const MAXSEC = 28;
const hint = (m, err) => { const h = $("#hint"); if (h) { h.textContent = m || ""; h.className = "hint" + (err ? " err" : ""); } };
async function micToggle() {
  if (REC) return stopRec();
  stopAudio(); let stream;
  try { stream = await navigator.mediaDevices.getUserMedia({audio: true}); } catch (e) { return hint(t("micDenied"), true); }
  const mime = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(m => MediaRecorder.isTypeSupported(m));
  const mr = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
  REC = {mr, stream, chunks: [], t0: Date.now(), timer: null};
  mr.ondataavailable = e => { if (e.data.size) REC.chunks.push(e.data); };
  mr.onstop = finishRec; mr.start();
  const m = $("#mic"); m.classList.add("on"); m.setAttribute("aria-label", t("micStop"));
  REC.timer = setInterval(() => { const s = (Date.now() - REC.t0) / 1000; hint(`${t("listening")}  ${s.toFixed(0)}s / ${MAXSEC}s`); if (s >= MAXSEC) stopRec(); }, 250);
  hint(t("listening"));
}
function stopRec() { if (REC && REC.mr.state !== "inactive") REC.mr.stop(); }
async function finishRec() {
  const r = REC; REC = null; clearInterval(r.timer); r.stream.getTracks().forEach(x => x.stop());
  const m = $("#mic"); if (m) { m.classList.remove("on"); m.classList.add("busy"); m.setAttribute("aria-label", t("mic")); }
  const secs = (Date.now() - r.t0) / 1000;
  try {
    if (secs < 0.7) return hint(t("tooShort"), true);
    hint(t("sending")); $("#res").innerHTML = `<p class="heard">${esc(t("sending"))}</p>`;
    let wav; try { wav = await toWav16k(new Blob(r.chunks, {type: r.mr.mimeType})); } catch (e) { return hint(t("convFail"), true); }
    let d = null; try { const resp = await fetch("/ask-audio?lang=" + LANG, {method:"POST", headers:{"Content-Type":"audio/wav"}, body: wav}); d = await resp.json(); } catch (e) {}
    hint(""); handle(d, true);
  } finally { const mm = $("#mic"); if (mm) mm.classList.remove("busy"); }
}
