// drive.js — cockpit ขับเอง (rev.2 · 16 ก.ย.) · vanilla · ไม่โหลดอะไรจากเน็ต
// หลักความปลอดภัยเหมือนเดิม: browser ส่ง {t:"drive"} ทุก 100 ms ขณะมีอินพุต · ปล่อย = {t:"release"} ·
// Pi ถือค่าล่าสุดแล้วส่ง $V ซ้ำเอง · เงียบ 300 ms = Pi ส่ง $S · ESP32 มี deadman ของตัวเองอีกชั้น
(() => {
  const $ = (id) => document.getElementById(id);
  const V_MAX = 150;                                   // G14
  const DEFAULTS = { maxPct: 50, turnGain: 1000, rampMs: 250, deadzone: 0.12, turnScale: true, invY: false, invX: false,
    joySide: "left", joySize: "m", autoSuction: false, fps: 10, gridOn: false, roiOn: true, mirror: false,
    suctionPct: 100, brushPct: 24, suctionIdleOff: 0, sound: true, vibrate: true, toastSec: 3, staleSec: 2,
    accent: "mint", density: "comfortable", bigButtons: false, wakeLock: true };
  let cfg = { ...DEFAULTS };
  try { Object.assign(cfg, JSON.parse(localStorage.getItem("mrc.drive.cfg") || "{}")); } catch (e) {}
  const save = () => { try { localStorage.setItem("mrc.drive.cfg", JSON.stringify(cfg)); } catch (e) {} };

  // ── apply cfg → DOM ──
  const root = document.documentElement;
  function applyCfg() {
    root.dataset.accent = cfg.accent; root.dataset.density = cfg.density; root.dataset.big = cfg.bigButtons ? 1 : 0;
    root.dataset.joyside = cfg.joySide; root.dataset.mirror = cfg.mirror ? 1 : 0;
    root.style.setProperty("--joy", { s: "120px", m: "160px", l: "210px" }[cfg.joySize] || "160px");
    $("grid").hidden = !cfg.gridOn; $("roi").hidden = !cfg.roiOn || !roi;
    document.querySelectorAll("[data-cfg]").forEach((el) => {
      const k = el.dataset.cfg; if (el.type === "checkbox") el.checked = !!cfg[k]; else el.value = cfg[k];
      const out = el.parentElement.querySelector("output"); if (out) out.value = fmtOut(k, cfg[k]);
    });
    document.querySelectorAll("#swatches button").forEach((b) => b.classList.toggle("on", b.dataset.accent === cfg.accent));
    setSpeed(cfg.maxPct, false);
    if (streamFps !== cfg.fps) startStream();
    wake();
  }
  const fmtOut = (k, v) => ({ maxPct: `${v}% · ${Math.round(V_MAX * v / 100)} mm/s`, turnGain: `${v}`, rampMs: `${v} ms`, deadzone: `${v}`, fps: `${v} fps`,
    suctionPct: `${v}%`, brushPct: `${v}%`, suctionIdleOff: v ? `${v} s` : "ไม่ปิด", toastSec: `${v} s`, staleSec: `${v} s` })[k] ?? v;
  document.querySelectorAll("[data-cfg]").forEach((el) => el.addEventListener("input", () => {
    const k = el.dataset.cfg; cfg[k] = el.type === "checkbox" ? el.checked : (el.tagName === "SELECT" ? el.value : +el.value);
    save(); applyCfg();
  }));
  document.querySelectorAll("#swatches button").forEach((b) => b.onclick = () => { cfg.accent = b.dataset.accent; save(); applyCfg(); });
  $("cfg-reset").onclick = () => { cfg = { ...DEFAULTS }; save(); applyCfg(); toast("คืนค่าเริ่มต้นแล้ว", "good"); };

  // ── ภาพสด ──
  const cam = $("cam"); let streamFps = 0;
  function startStream() { streamFps = cfg.fps; cam.src = `/stream.mjpg?fps=${cfg.fps}&t=${Date.now()}`; }
  cam.onerror = () => setTimeout(startStream, 2000);

  // ── WebSocket ──
  let ws, wsOk = false;
  function connect() {
    ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
    ws.onopen = () => { wsOk = true; chip("link", "ลิงก์ ต่ออยู่"); };
    ws.onclose = () => { wsOk = false; setMode("ขาดการเชื่อมต่อ", "lost"); chip("link", "ลิงก์ หลุด — ต่อใหม่…", "bad"); beep("bad"); setTimeout(connect, 1000); };
    ws.onmessage = (m) => handle(JSON.parse(m.data));
  }
  const send = (o) => { if (wsOk && ws.readyState === 1) ws.send(JSON.stringify(o)); };
  connect();

  // ── HUD helpers ──
  const setMode = (t, cls) => { const e = $("mode"); e.textContent = t; e.className = "chip mode " + (cls || ""); };
  const chip = (id, html, cls) => { const e = $(id); e.innerHTML = html; e.className = "chip " + (cls || ""); };
  let toastT;
  function toast(msg, cls) { const t = $("toast"); t.textContent = msg; t.className = "toast " + (cls || ""); t.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => t.hidden = true, cfg.toastSec * 1000); }
  const evl = $("ev");
  function logEv(text, cls) { const li = document.createElement("li"); li.textContent = new Date().toLocaleTimeString("th-TH", { hour12: false }) + "  " + text; li.className = cls || ""; evl.prepend(li); while (evl.children.length > 80) evl.lastChild.remove(); }
  // เสียง/สั่น — WebAudio ไม่ต้องมีไฟล์
  let actx;
  function beep(kind) {
    if (cfg.vibrate && navigator.vibrate) navigator.vibrate(kind === "bad" ? [80, 40, 80] : 40);
    if (!cfg.sound) return;
    try { actx = actx || new (window.AudioContext || window.webkitAudioContext)(); const o = actx.createOscillator(), g = actx.createGain();
      o.frequency.value = kind === "bad" ? 220 : kind === "good" ? 880 : 520; g.gain.value = 0.05; o.connect(g); g.connect(actx.destination); o.start(); o.stop(actx.currentTime + (kind === "bad" ? 0.25 : 0.08)); } catch (e) {}
  }
  const NACK_TH = { MAST_UP: "เสายังไม่พับ — ขับไม่ได้", IN_MISSION: "หุ่นกำลังเดินภารกิจอัตโนมัติ", SUCTION_SPINUP: "เพิ่งเปิดดูด รอ 1 วิ ก่อนออกตัว", NOT_STOPPED: "หยุดล้อก่อนเปิดดูด", NOT_IMPLEMENTED: "ยังไม่รองรับคำสั่งนี้", BAD_ARGS: "คำสั่งผิดรูปแบบ" };

  let lastTele = null, lastSys = null, capCount = 0, staleT;
  function handle(ev) {
    switch (ev.t) {
      case "hello": (ev.events || []).slice(-10).forEach(handle); break;
      case "sys": lastSys = ev; chip("cams", "กล้อง " + (ev.cam_ok ? "ปกติ" : "<b>ไม่มีภาพ</b>"), ev.cam_ok ? "" : "bad");
        if (!ev.link) setMode("ไม่มี serial", "lost");
        else if (!ev.link.alive) { setMode("ESP32 ไม่ตอบ", "lost"); chip("link", ev.link.age_s == null ? "ลิงก์ ยังไม่เคยได้ข้อมูล" : `ลิงก์ เงียบ ${ev.link.age_s}s`, "bad"); }
        else chip("link", `ลิงก์ <b>${Math.round(ev.link.age_s * 1000)} ms</b>`);
        renderKv(); break;
      case "tele": lastTele = ev; clearTimeout(staleT); staleT = setTimeout(() => { setMode("ESP32 เงียบ", "lost"); beep("bad"); }, cfg.staleSec * 1000);
        setMode(ev.state_name === "MANUAL" ? "ขับเอง" : ev.state_name === "MISSION" ? "ภารกิจอัตโนมัติ" : "พร้อม", ev.state_name === "MANUAL" ? "" : ev.state_name === "MISSION" ? "mission" : "idle");
        chip("bat", ev.vbat_mV ? `แบต <b>${(ev.vbat_mV / 1000).toFixed(1)} V</b>` : "แบต —");
        if (ev.comm_lost) toast("ESP32 หยุดเอง: ไม่ได้คำสั่งใน 300 ms", "warn"); break;
      case "nack": toast("ปฏิเสธ: " + (NACK_TH[ev.reason] || ev.reason), "warn"); logEv("ปฏิเสธ " + ev.reason, "warn"); beep("warn"); break;
      case "capture": $("capture").disabled = false; if (ev.ok) { capCount++; $("capn").textContent = `${capCount} ใบ`; toast("ถ่ายแล้ว — กำลังอ่านตัวเลข…", "good"); beep("good"); } else { toast("ถ่ายไม่สำเร็จ: " + ev.reason, "bad"); beep("bad"); } logEv(ev.ok ? `ถ่าย ${ev.image}` : `ถ่ายไม่สำเร็จ ${ev.reason}`, ev.ok ? "good" : "bad"); break;
      case "reading": toast(ev.value == null ? "อ่านตัวเลขไม่ออก — เล็งให้เข้ากรอบแล้วถ่ายใหม่" : `อ่านได้ ${ev.value}`, ev.value == null ? "warn" : "good"); logEv(`ค่า ${ev.value ?? "—"} (conf ${ev.confidence})`, ev.value == null ? "warn" : "good"); break;
      case "log": if (ev.level === "bad" || ev.level === "warn") { logEv(ev.msg, ev.level); if (ev.level === "bad") toast(ev.msg, "bad"); } else if (ev.level === "good") logEv(ev.msg, "good"); break;
      case "event": logEv(`ESP32: ${ev.code} ${ev.detail || ""}`, "warn"); break;
    }
  }
  function renderKv() {
    const t = lastTele || {}, s = lastSys || { cleaning: {}, drive: {} };
    const rows = [["โหมด", t.state_name || "—"], ["ความเร็วสั่ง", t.v != null ? `${t.v} mm/s · หมุน ${t.w} mrad/s` : "—"], ["ล้อซ้าย / ขวา", t.duty_l != null ? `${t.duty_l} / ${t.duty_r} ‰` : "—"],
      ["เสายกกล้อง", t.mast === 2 ? "จับสัญญาณ (ยก/ค้าง)" : t.mast === 0 ? "พับ" : "—"], ["ดูด / แปรง", `${s.cleaning.suction ?? "—"} % / ${s.cleaning.brush ?? "—"} %`],
      ["แบตเตอรี่", t.vbat_mV ? `${(t.vbat_mV / 1000).toFixed(2)} V` : "ยังไม่มี ADC ในเฟิร์มแวร์"], ["deadman Pi", `${s.drive.tripped ?? 0} ครั้ง`], ["Pi", `${s.cpu_temp_c ?? "—"} °C · SD ว่าง ${s.disk_free_mb ?? "—"} MB`]];
    $("kv").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  }

  // ── ความเร็ว ──
  let speedPct = cfg.maxPct;
  function setSpeed(pct, persist = true) {
    speedPct = Math.max(10, Math.min(100, pct)); $("spd").value = speedPct; $("spdnum").textContent = Math.round(V_MAX * speedPct / 100);
    document.querySelectorAll(".dial-presets button").forEach((b) => b.classList.toggle("on", +b.dataset.pct === speedPct));
    if (persist) { cfg.maxPct = speedPct; save(); }
  }
  $("spd").oninput = (e) => setSpeed(+e.target.value);
  document.querySelectorAll(".dial-presets button").forEach((b) => b.onclick = () => setSpeed(+b.dataset.pct));

  // ── อินพุต: จอย / คีย์ / gamepad → vec ∈ [-1,1]² ──
  let jx = 0, jy = 0, joyActive = false;
  const joy = $("joy"), knob = $("knob"), arc = $("arc");
  const R = () => joy.clientWidth / 2;
  function paintKnob(x, y) { knob.style.transform = `translate(${x * R() * 0.6}px, ${-y * R() * 0.6}px)`; arc.style.setProperty("--a", `${(Math.atan2(x, y) * 180 / Math.PI) - 20}deg`); }
  joy.addEventListener("pointerdown", (e) => { joy.setPointerCapture(e.pointerId); joyActive = true; joy.classList.add("active"); moveJoy(e); });
  joy.addEventListener("pointermove", (e) => joyActive && moveJoy(e));
  const endJoy = () => { joyActive = false; joy.classList.remove("active"); jx = jy = 0; paintKnob(0, 0); pump(); };
  joy.addEventListener("pointerup", endJoy); joy.addEventListener("pointercancel", endJoy);
  function moveJoy(e) { const r = joy.getBoundingClientRect(); let x = (e.clientX - (r.left + r.width / 2)) / R(), y = -(e.clientY - (r.top + r.height / 2)) / R();
    const len = Math.hypot(x, y); if (len > 1) { x /= len; y /= len; } jx = x; jy = y; paintKnob(x, y); }
  const keys = new Set();
  window.addEventListener("keydown", (e) => { if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return; if (e.repeat) return; const k = e.key.toLowerCase();
    if (k === " ") { e.preventDefault(); estop(); return; } if (k === "c") { capture(); return; } if (k === "f") { toggleSuction(); return; } if (k === "g") { toggleBrush(); return; }
    if (k === "1") return setSpeed(25); if (k === "2") return setSpeed(50); if (k === "3") return setSpeed(100); keys.add(k); });
  window.addEventListener("keyup", (e) => { keys.delete(e.key.toLowerCase()); pump(); });
  window.addEventListener("blur", () => { keys.clear(); endJoy(); });
  const keyVec = () => { let x = 0, y = 0; if (keys.has("w") || keys.has("arrowup")) y++; if (keys.has("s") || keys.has("arrowdown")) y--; if (keys.has("a") || keys.has("arrowleft")) x--; if (keys.has("d") || keys.has("arrowright")) x++; return [x, y]; };
  let padBtn = {};
  function padVec() { const gp = (navigator.getGamepads ? navigator.getGamepads() : [])[0]; if (!gp) return [0, 0];
    const p = (i) => gp.buttons[i] && gp.buttons[i].pressed; const edge = (i, fn) => { if (p(i) && !padBtn[i]) fn(); padBtn[i] = p(i); };
    edge(1, estop); edge(0, capture); edge(2, toggleSuction); const boost = gp.buttons[7] ? gp.buttons[7].value : 0;
    const dz = (v) => Math.abs(v) < cfg.deadzone ? 0 : v; return [dz(gp.axes[0] || 0) * (1 + boost * 0.5), -dz(gp.axes[1] || 0) * (1 + boost * 0.5)]; }
  function inputVec() { if (joyActive) return [jx, jy]; const [kx, ky] = keyVec(); if (kx || ky) return [kx, ky]; return padVec(); }

  // ── ส่งคำสั่ง 10 Hz · ramp ฝั่ง client ตาม cfg.rampMs ──
  let driving = false, curV = 0, curW = 0, lastT = performance.now();
  function pump() {
    const now = performance.now(), dt = now - lastT; lastT = now;
    let [x, y] = inputVec();
    if (Math.hypot(x, y) < cfg.deadzone) x = y = 0;
    if (cfg.invY) y = -y; if (cfg.invX) x = -x;
    const tv = y * V_MAX * speedPct / 100;
    const tw = -x * cfg.turnGain * (cfg.turnScale ? (1 - 0.5 * Math.abs(y)) : 1);
    if (!x && !y) { curV = curW = 0; if (driving) { driving = false; send({ t: "release" }); } return; }
    if (!driving) { driving = true; if (cfg.autoSuction && !suction) toggleSuction(); }
    const step = cfg.rampMs ? Math.min(1, dt / cfg.rampMs) : 1;
    curV += (tv - curV) * step; curW += (tw - curW) * step;
    send({ t: "drive", v: Math.round(curV), w: Math.round(curW) });
  }
  setInterval(pump, 100);

  // ── ปุ่ม ──
  function estop() { send({ t: "estop" }); driving = false; curV = curW = 0; toast("หยุดฉุกเฉิน", "bad"); logEv("E-STOP", "bad"); beep("bad"); }
  $("estop").onclick = estop;
  function capture() { $("capture").disabled = true; send({ t: "capture" }); setTimeout(() => $("capture").disabled = false, 5000); }
  $("capture").onclick = capture;
  let suction = 0, brush = 0, idleT;
  function sendClean() { send({ t: "clean", suction, brush }); paintTog(); }
  function toggleSuction() { suction = suction ? 0 : cfg.suctionPct; sendClean(); }
  function toggleBrush() { brush = brush ? 0 : cfg.brushPct; sendClean(); }
  $("suction").onclick = toggleSuction; $("brush").onclick = toggleBrush;
  function paintTog() { $("suction").classList.toggle("on", !!suction); $("suction").querySelector("b").textContent = suction ? "เปิด" : "ปิด";
    $("brush").classList.toggle("on", !!brush); $("brush").querySelector("b").textContent = brush ? `${brush}%` : "ปิด"; }
  setInterval(() => { if (cfg.suctionIdleOff && suction && !driving) { idleT = (idleT || 0) + 1; if (idleT >= cfg.suctionIdleOff) { suction = 0; sendClean(); toast("ปิดดูดอัตโนมัติ (หยุดนาน)", "good"); idleT = 0; } } else idleT = 0; }, 1000);

  // ── sheet ตั้งค่า ──
  const sheet = $("sheet");
  $("settings-btn").onclick = () => { sheet.hidden = false; renderKv(); };
  $("sheet-close").onclick = () => sheet.hidden = true;
  document.querySelectorAll("#tabs button").forEach((b) => b.onclick = () => { document.querySelectorAll("#tabs button").forEach((x) => x.classList.toggle("on", x === b)); document.querySelectorAll(".pane").forEach((p) => p.classList.toggle("on", p.dataset.pane === b.dataset.tab)); });

  // ── ROI: แสดง + ลากตั้งบนภาพสด → POST /api/roi ──
  let roi = null, roiDraft = null, roiEditing = false;
  const vp = document.querySelector(".viewport"), roiEl = $("roi");
  function paintRoi(r) { if (!r) { roiEl.hidden = true; return; } roiEl.hidden = !cfg.roiOn && !roiEditing; roiEl.style.left = r.x * 100 + "%"; roiEl.style.top = r.y * 100 + "%"; roiEl.style.width = r.w * 100 + "%"; roiEl.style.height = r.h * 100 + "%"; }
  fetch("/api/roi").then((r) => r.json()).then((d) => { roi = d.crop; paintRoi(roi); }).catch(() => {});
  $("roi-edit").onclick = () => { roiEditing = true; roiEl.classList.add("edit"); vp.classList.add("roi-editing"); sheet.hidden = true; toast("ลากกรอบบนภาพ แล้วกดตั้งค่า → บันทึกกรอบ", "good"); roiEl.hidden = false; };
  let dragStart = null;
  vp.addEventListener("pointerdown", (e) => { if (!roiEditing) return; const r = vp.getBoundingClientRect(); dragStart = [(e.clientX - r.left) / r.width, (e.clientY - r.top) / r.height]; vp.setPointerCapture(e.pointerId); });
  vp.addEventListener("pointermove", (e) => { if (!roiEditing || !dragStart) return; const r = vp.getBoundingClientRect(); const px = (e.clientX - r.left) / r.width, py = (e.clientY - r.top) / r.height;
    roiDraft = { x: Math.min(dragStart[0], px), y: Math.min(dragStart[1], py), w: Math.abs(px - dragStart[0]), h: Math.abs(py - dragStart[1]) }; paintRoi(roiDraft); });
  vp.addEventListener("pointerup", () => { if (!roiEditing) return; dragStart = null; if (roiDraft && roiDraft.w > 0.02) { $("roi-save").disabled = false; sheet.hidden = false; } });
  $("roi-save").onclick = async () => { const r = await fetch("/api/roi", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ crop: roiDraft }) }).then((x) => x.json());
    if (r.ok) { roi = r.crop; roiDraft = null; roiEditing = false; roiEl.classList.remove("edit"); vp.classList.remove("roi-editing"); $("roi-save").disabled = true; paintRoi(roi); toast("บันทึกกรอบแล้ว", "good"); } else toast(r.reason, "bad"); };
  $("roi-reset").onclick = () => { roiDraft = { x: 0, y: 0, w: 1, h: 1 }; paintRoi(roiDraft); $("roi-save").disabled = false; };

  // ── กันจอดับ ──
  let wl = null;
  async function wake() { try { if (cfg.wakeLock && !wl && navigator.wakeLock) wl = await navigator.wakeLock.request("screen"); if (!cfg.wakeLock && wl) { await wl.release(); wl = null; } } catch (e) {} }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { wl = null; wake(); } });

  applyCfg(); startStream();
})();
