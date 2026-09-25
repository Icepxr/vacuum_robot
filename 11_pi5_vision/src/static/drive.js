// drive.js — cockpit ขับเอง (rev.3 · 21 ก.ย. — C36 ปุ่มทิศทาง 8 ทาง + ซูมกล้อง) · vanilla · ไม่โหลดอะไรจากเน็ต
// หลักความปลอดภัยเหมือนเดิม: browser ส่ง {t:"drive"} ทุก 100 ms ขณะมีอินพุต · ปล่อย = {t:"release"} ·
// Pi ถือค่าล่าสุดแล้วส่ง $V ซ้ำเอง · เงียบ 300 ms = Pi ส่ง $S · ESP32 มี deadman ของตัวเองอีกชั้น
(() => {
  const $ = (id) => document.getElementById(id);
  // C28: เพดานความเร็วเป็นของผู้ใช้ (cfg.vMax/wMax → {t:"limits"} → Pi → $L) · ESP32 clamp แค่ที่ฮาร์ดแวร์ 716 mm/s
  let V_MAX = 150;                                     // = cfg.vMax หลัง applyCfg
  const V_HW_MAX = 716, W_HW_MAX = 7950;
  const DEFAULTS = { vMax: 300, wMax: 3000, maxPct: 50, turnGain: 2000, tiltMinDeg: 0, tiltMaxDeg: 180, tiltInv: false, liftMinDeg: 45, liftMaxDeg: 135, liftInv: true, calVer: 2, camPad: true, rampMs: 250, deadzone: 0.12, turnScale: true, invY: false, invX: false,
    joySide: "left", joySize: "m", autoSuction: false, driveUi: "pad", curveTurn: 50, joySnap: true, fps: 10, gridOn: false, roiOn: true, mirror: false,
    suctionPct: 100, suctionIdleOff: 0, sound: true, vibrate: true, toastSec: 3, staleSec: 2,
    accent: "mint", density: "comfortable", bigButtons: false, wakeLock: true };
  let cfg = { ...DEFAULTS };
  try { Object.assign(cfg, JSON.parse(localStorage.getItem("mrc.drive.cfg") || "{}")); } catch (e) {}
  // rev.3: ขีดเซอร์โวเก็บเป็นองศา — แปลงค่าเก่า (µs) ของเครื่องนี้ครั้งเดียว
  const usDeg = (us) => Math.round((us - 500) / 2000 * 180);
  if (cfg.tiltMin != null) { cfg.tiltMinDeg = usDeg(cfg.tiltMin); cfg.tiltMaxDeg = usDeg(cfg.tiltMax); delete cfg.tiltMin; delete cfg.tiltMax; }
  if (cfg.liftMin != null) { cfg.liftMinDeg = usDeg(cfg.liftMin); cfg.liftMaxDeg = usDeg(cfg.liftMax); delete cfg.liftMin; delete cfg.liftMax; }
  // C42 (25 ก.ย. ผู้ใช้: "0° แล้วเสายกสูง"): เสาจริงยกเมื่อพัลส์ "สั้นลง" (500 µs = บน) → กลับทิศเป็นค่าเริ่มต้น
  // เครื่องที่เคยบันทึก liftInv:false ไว้ก่อนหน้า → บังคับครั้งเดียว + คืนขีดเสาเป็น 45–135° (= 1000–2000 µs ช่วงเดิม)
  // เพราะขีดที่เคยตั้งไว้ถูกตั้งตอนทิศกลับด้าน — ใช้ต่อจะพาไปชนสุดทางอีกฝั่ง
  if ((cfg.calVer || 1) < 2) { cfg.liftInv = true; cfg.liftMinDeg = 45; cfg.liftMaxDeg = 135; cfg.calVer = 2; }
  const save = () => { try { localStorage.setItem("mrc.drive.cfg", JSON.stringify(cfg)); } catch (e) {} };

  // ── apply cfg → DOM ──
  const root = document.documentElement;
  let limitsT;
  function pushLimits() {                              // ส่งเพดานให้ Pi (debounce ตอนลากสไลเดอร์) — ส่งซ้ำตอน ws ต่อใหม่ด้วย
    clearTimeout(limitsT); limitsT = setTimeout(() => send({ t: "limits", v_max: cfg.vMax, w_max: cfg.wMax }), 250);
  }
  function applyCfg() {
    cfg.vMax = Math.max(50, Math.min(V_HW_MAX, +cfg.vMax || 300)); cfg.wMax = Math.max(500, Math.min(W_HW_MAX, +cfg.wMax || 3000));
    if (cfg.turnGain > cfg.wMax) cfg.turnGain = cfg.wMax;
    V_MAX = cfg.vMax;
    for (const k of ["tilt", "lift"]) { const lo = k + "MinDeg", hi = k + "MaxDeg"; cfg[lo] = Math.max(0, Math.min(180, +cfg[lo] || 0)); cfg[hi] = Math.max(0, Math.min(180, +cfg[hi] || 0)); if (cfg[lo] >= cfg[hi]) cfg[hi] = Math.min(180, cfg[lo] + 1); }
    root.dataset.campad = cfg.camPad ? 1 : 0; camApplyLimits();
    root.dataset.accent = cfg.accent; root.dataset.density = cfg.density; root.dataset.big = cfg.bigButtons ? 1 : 0;
    root.dataset.joyside = cfg.joySide; root.dataset.mirror = cfg.mirror ? 1 : 0;
    $("joy").hidden = cfg.driveUi !== "joy"; $("pad").hidden = cfg.driveUi !== "pad";
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
  const fmtOut = (k, v) => ({ tiltMinDeg: `${v}°`, tiltMaxDeg: `${v}°`, liftMinDeg: `${v}°`, liftMaxDeg: `${v}°`, vMax: `${v} mm/s${v > 300 ? " ⚠ เกินค่าเริ่มต้น" : ""}`, wMax: `${v} mrad/s`, maxPct: `${v}% · ${Math.round(V_MAX * v / 100)} mm/s`, turnGain: `${v}`, curveTurn: `${v}%`, rampMs: `${v} ms`, deadzone: `${v}`, fps: `${v} fps`,
    suctionPct: `${v}%`, suctionIdleOff: v ? `${v} s` : "ไม่ปิด", toastSec: `${v} s`, staleSec: `${v} s` })[k] ?? v;
  document.querySelectorAll("[data-cfg]").forEach((el) => el.addEventListener("input", () => {
    const k = el.dataset.cfg; cfg[k] = el.type === "checkbox" ? el.checked : (el.tagName === "SELECT" ? el.value : +el.value);
    save(); applyCfg();
    if (k === "vMax" || k === "wMax") pushLimits();
  }));
  document.querySelectorAll("#swatches button").forEach((b) => b.onclick = () => { cfg.accent = b.dataset.accent; save(); applyCfg(); });
  $("cfg-reset").onclick = () => { cfg = { ...DEFAULTS }; save(); applyCfg(); toast("คืนค่าเริ่มต้นแล้ว", "good"); };

  // ── แผงกล้อง rev.3 (22 ก.ย.): คุมเป็น "องศา" — สไลเดอร์ = ไปมุมนั้น · −/+ = ขั้นละ step° (กดค้างเดินต่อ) ──
  // เฟิร์มแวร์ยังคุยเป็น µs (มุม → $X · เสา → $M · slew เอง) · หน้าเว็บแปลง: 0–180° ↔ 500–2500 µs (สเกลทั่วไปของ MG996R — ยังไม่วัดตัวจริง C8)
  // ตำแหน่งจริงมาจาก #T (us_r = มุม · us_l = เสา · 0 = ปล่อย) → ตัวเลข + สไลเดอร์ตามเมื่อไม่ได้ลาก
  const US_0 = 500, US_180 = 2500;
  const camAx = {
    tilt: { cmd: "x", tele: "us_r", step: 5, sl: $("tilt-sl"), lbl: $("tilt-v"), row: $("tilt-row"), us: 0, target: null, drag: false,
            min: () => cfg.tiltMinDeg, max: () => cfg.tiltMaxDeg, inv: () => cfg.tiltInv, start: () => Math.round((cfg.tiltMinDeg + cfg.tiltMaxDeg) / 2), name: "มุมกล้อง" },
    lift: { cmd: "m", tele: "us_l", step: 2, sl: $("lift-sl"), lbl: $("lift-v"), row: $("lift-row"), us: 0, target: null, drag: false,
            min: () => cfg.liftMinDeg, max: () => cfg.liftMaxDeg, inv: () => cfg.liftInv, start: () => cfg.liftMinDeg, name: "เสา" },
  };
  const degToUs = (a, d) => Math.round(US_0 + (a.inv() ? 180 - d : d) / 180 * (US_180 - US_0));   // d ทศนิยมได้
  const usToDeg = (a, us) => { const d = Math.round((us - US_0) / (US_180 - US_0) * 180); return a.inv() ? 180 - d : d; };
  const camDeg = (a) => a.target != null ? a.target : a.us ? usToDeg(a, a.us) : null;   // มุมที่ "รู้" ตอนนี้ (เป้า > จริง)
  // C40 (25 ก.ย. — ผู้ใช้: "เด้งๆ ขึ้นๆลงๆ ไม่สมูท"): ต้นเหตุฝั่งเว็บ 2 อย่าง
  //   1) ลากสไลเดอร์ใช้ debounce 60 ms → ระหว่างลากต่อเนื่องไม่ส่งเลย พอนิ้วชะงักค่อยส่งทีเดียว = กระตุกเป็นช่วงๆ → เปลี่ยนเป็น throttle ส่งทุก 50 ms
  //   2) กดค้าง −/+ ส่งขั้นใหญ่ (5°/2°) ทุก 150 ms แต่เฟิร์มแวร์เดินเร็วกว่ามาก → วิ่ง 20–50 ms แล้วหยุดรอ ~100 ms = หยุด-วิ่ง-หยุด 7 ครั้ง/วิ
  //      → กดค้าง = เดินต่อเนื่องที่ความเร็วคงที่ (HOLD_DPS) ส่งเป้าเล็กๆ ทุก 50 ms · แตะครั้งเดียว = 1°
  const SEND_MS = 50, HOLD_TICK_MS = 50, HOLD_DELAY_MS = 250;
  const HOLD_DPS = { tilt: 40, lift: 15 };               // °/s ตอนกดค้าง — ช้ากว่าเฟิร์มแวร์ (tilt ~187°/s · เสา ~37°/s) เฟิร์มแวร์จึงตามทันตลอด ไม่มีช่วงหยุดรอ
  function camSendNow(a) { a.lastSend = performance.now(); a.sendT = null; send({ t: a.cmd, us: degToUs(a, a.target) }); }
  function camGoto(a, deg, immediate = true) {
    deg = Math.max(a.min(), Math.min(a.max(), deg)); a.target = deg;          // เก็บทศนิยมไว้ — µs ละเอียดกว่า 1° (1° = 11 µs)
    a.lbl.textContent = `${Math.round(deg)}°`; if (!a.drag) a.sl.value = Math.round(deg);
    const wait = SEND_MS - (performance.now() - (a.lastSend || 0));
    if (immediate || wait <= 0) { clearTimeout(a.sendT); camSendNow(a); }
    else if (!a.sendT) a.sendT = setTimeout(() => camSendNow(a), wait);      // throttle: ส่งค่าล่าสุดเมื่อครบ 50 ms (ไม่เลื่อนออกไปเรื่อยๆ แบบ debounce)
  }
  function camNudge(a, dir, deg = 1) {
    const cur = camDeg(a);
    if (cur == null) { camGoto(a, a.start()); toast(`${a.name}: ผูกสัญญาณที่ ${Math.round(a.target)}° ก่อน แล้วค่อยกดอีกครั้ง`, "warn"); return false; }
    camGoto(a, cur + dir * deg, false); return true;
  }
  let holdT = null, holdD = null;
  document.querySelectorAll("[data-hold]").forEach((b) => {
    const [k, d] = b.dataset.hold.split(":"); const a = camAx[k], dir = +d;
    const stop = () => { clearTimeout(holdD); clearInterval(holdT); holdT = holdD = null; b.classList.remove("hold"); };
    b.addEventListener("pointerdown", (e) => { e.preventDefault(); try { b.setPointerCapture(e.pointerId); } catch (_) {} b.classList.add("hold");
      stop(); b.classList.add("hold");
      if (!camNudge(a, dir, 1)) return;                                         // แตะ = 1°
      holdD = setTimeout(() => { holdT = setInterval(() => camNudge(a, dir, HOLD_DPS[k] * HOLD_TICK_MS / 1000), HOLD_TICK_MS); }, HOLD_DELAY_MS); });
    ["pointerup", "pointercancel", "lostpointercapture"].forEach((ev) => b.addEventListener(ev, stop));
  });
  for (const a of Object.values(camAx)) {
    a.sl.addEventListener("pointerdown", () => { a.drag = true; });
    ["pointerup", "pointercancel"].forEach((ev) => a.sl.addEventListener(ev, () => { a.drag = false; }));
    a.sl.addEventListener("input", () => camGoto(a, +a.sl.value, false));
    a.sl.addEventListener("change", () => { a.drag = false; camGoto(a, +a.sl.value, true); });
  }
  function camFromTele(t) {
    for (const a of Object.values(camAx)) {
      a.us = t[a.tele] || 0;
      if (!a.us) a.target = null;
      a.row.classList.toggle("off", !a.us);
      if (a.drag || holdT) continue;
      const d = camDeg(a);
      a.lbl.textContent = d == null ? "ปล่อย" : `${a.us ? usToDeg(a, a.us) : d}°`;   // ตัวเลข = มุมจริง (ถ้ามี) · สไลเดอร์ = เป้า
      if (d != null && a.target == null) a.sl.value = d;
    }
  }
  function camApplyLimits() {
    for (const a of Object.values(camAx)) { a.sl.min = a.min(); a.sl.max = a.max(); }
  }
  document.querySelectorAll("[data-cam]").forEach((b) => b.onclick = () => {
    const k = b.dataset.cam;
    if (k === "mid") camGoto(camAx.tilt, camAx.tilt.start());
    else if (k === "down") camGoto(camAx.lift, cfg.liftMinDeg);
    else { send({ t: "x", us: 0 }); send({ t: "m", us: 0 }); camAx.tilt.target = camAx.lift.target = null; }
  });
  // ⚙ กล้อง: "ใช้มุมปัจจุบันเป็น ต่ำสุด/สูงสุด" — ไว้ไฟนอลขีดจากของจริง (ผู้ใช้ 22 ก.ย.)
  document.querySelectorAll("[data-setlim]").forEach((b) => b.onclick = () => {
    const [k, which] = b.dataset.setlim.split(":"); const a = camAx[k]; const d0 = a.us ? usToDeg(a, a.us) : camDeg(a); const d = d0 == null ? null : Math.round(d0);
    if (d == null) { toast(`${a.name}: ยังไม่รู้มุม — ขยับก่อน`, "warn"); return; }
    cfg[k + (which === "min" ? "MinDeg" : "MaxDeg")] = d; save(); applyCfg(); toast(`${a.name}: ${which === "min" ? "ต่ำสุด" : "สูงสุด"} = ${d}°`, "good");
  });

  // ── ภาพสด ──
  const cam = $("cam"); let streamFps = 0;
  function startStream() { streamFps = cfg.fps; cam.src = `/stream.mjpg?fps=${cfg.fps}&t=${Date.now()}`; }
  cam.onerror = () => setTimeout(startStream, 2000);

  // ── WebSocket ──
  let ws, wsOk = false;
  function connect() {
    ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
    ws.onopen = () => { wsOk = true; chip("link", "ลิงก์ ต่ออยู่"); };   // เพดานความเร็วเป็นของหุ่น (Pi ส่งมาใน sys/limits) ไม่ใช่ของเครื่องนี้
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
  const NACK_TH = { MAST_UP: "เปิดแปรงตอนเสายกไม่ได้ (ราง 5 V) — พับเสาก่อน", SERVO_MOVING: "รอมุมกล้องหยุดก่อนเปิดแปรง (ราง 5 V)", BRUSH_SPINUP: "เพิ่งเปิดแปรง รอ 1 วิ ก่อนขยับกล้อง/เสา", OUT_OF_RANGE: "ตำแหน่งนอกช่วง 500–2500 µs", SERVO_FAIL: "ผูกสัญญาณเซอร์โวไม่ได้", IN_MISSION: "หุ่นกำลังเดินภารกิจอัตโนมัติ", SUCTION_SPINUP: "เพิ่งเปิดดูด รอ 1 วิ ก่อนออกตัว", NOT_STOPPED: "หยุดล้อก่อนเปิดดูด", NOT_IMPLEMENTED: "ยังไม่รองรับคำสั่งนี้", BAD_ARGS: "คำสั่งผิดรูปแบบ" };

  let lastTele = null, lastSys = null, capCount = 0, staleT;
  function handle(ev) {
    switch (ev.t) {
      case "hello": (ev.events || []).slice(-10).forEach(handle); break;
      case "sys": lastSys = ev; chip("cams", "กล้อง " + (ev.cam_ok ? "ปกติ" : "<b>ไม่มีภาพ</b>") + (ev.cam_ctl && ev.cam_ctl.zoom > 1.01 ? ` · ${(+ev.cam_ctl.zoom).toFixed(1)}×` : ""), ev.cam_ok ? "" : "bad"); airChip(ev.air);
        if ("cam_ctl" in ev && !pts.size && !zoomT && !zoomDrag) paintCam(ev.cam_ctl);                  // ซิงก์จากเครื่องอื่น — แต่ไม่แย่งตอนนิ้วยังอยู่บนจอ
        if (ev.limits && (ev.limits.v_max !== cfg.vMax || ev.limits.w_max !== cfg.wMax)) { cfg.vMax = ev.limits.v_max; cfg.wMax = ev.limits.w_max; save(); applyCfg(); }
        if (!ev.link) setMode("ไม่มี serial", "lost");
        else if (!ev.link.alive) { setMode("ESP32 ไม่ตอบ", "lost"); chip("link", ev.link.age_s == null ? "ลิงก์ ยังไม่เคยได้ข้อมูล" : `ลิงก์ เงียบ ${ev.link.age_s}s`, "bad"); }
        else chip("link", `ลิงก์ <b>${Math.round(ev.link.age_s * 1000)} ms</b>`);
        renderKv(); break;
      case "tele": lastTele = ev; clearTimeout(staleT); staleT = setTimeout(() => { setMode("ESP32 เงียบ", "lost"); beep("bad"); }, cfg.staleSec * 1000);
        setMode(ev.state_name === "MANUAL" ? "ขับเอง" : ev.state_name === "MISSION" ? "ภารกิจอัตโนมัติ" : "พร้อม", ev.state_name === "MANUAL" ? "" : ev.state_name === "MISSION" ? "mission" : "idle");
        chip("bat", ev.vbat_mV ? `แบต <b>${(ev.vbat_mV / 1000).toFixed(1)} V</b>` : "แบต —");
        $("mast").hidden = ev.mast !== 2;                                        // C28: เสายกไม่ห้ามขับ — แค่บอกให้เห็น
        camFromTele(ev);
        if (ev.spinup_hold && !$("spin").matches(":not([hidden])")) beep("warn");
        $("spin").hidden = !ev.spinup_hold;
        if (ev.comm_lost) toast("ESP32 หยุดเอง: ไม่ได้คำสั่งใน 300 ms", "warn"); break;
      case "limits":                                                             // Pi ยืนยันเพดาน (อาจถูก clamp ที่ฮาร์ดแวร์)
        if (ev.v_max !== cfg.vMax || ev.w_max !== cfg.wMax) { cfg.vMax = ev.v_max; cfg.wMax = ev.w_max; save(); applyCfg(); }
        logEv(`เพดาน ${ev.v_max} mm/s · หมุน ${ev.w_max} mrad/s`, ""); break;
      case "nack": toast("ปฏิเสธ: " + (NACK_TH[ev.reason] || ev.reason), "warn"); logEv("ปฏิเสธ " + ev.reason, "warn"); beep("warn"); break;
      case "capture": $("capture").disabled = false; if (ev.ok) { capCount++; $("capn").textContent = `${capCount} ใบ`; toast("ถ่ายแล้ว — กำลังอ่านตัวเลข…", "good"); beep("good"); } else { toast("ถ่ายไม่สำเร็จ: " + ev.reason, "bad"); beep("bad"); } logEv(ev.ok ? `ถ่าย ${ev.image}` : `ถ่ายไม่สำเร็จ ${ev.reason}`, ev.ok ? "good" : "bad"); break;
      case "reading": toast(ev.value == null ? "อ่านตัวเลขไม่ออก — เล็งให้เข้ากรอบแล้วถ่ายใหม่" : `อ่านได้ ${ev.value}`, ev.value == null ? "warn" : "good"); logEv(`ค่า ${ev.value ?? "—"} (conf ${ev.confidence})`, ev.value == null ? "warn" : "good"); break;
      case "log": if (ev.level === "bad" || ev.level === "warn") { logEv(ev.msg, ev.level); if (ev.level === "bad") toast(ev.msg, "bad"); } else if (ev.level === "good") logEv(ev.msg, "good"); break;
      case "event": logEv(`ESP32: ${ev.code} ${ev.detail || ""}`, "warn"); break;
      case "cam_ctl": if (!pts.size && !zoomT && !zoomDrag) paintCam(ev); break;
    }
  }
  const AIR_TH = { excellent: "ดีมาก", good: "ดี", fair: "พอใช้", poor: "แย่ — ควรระบาย", bad: "แย่มาก — ระบายอากาศ" };
  function airText(a) {
    if (!a) return "ปิด"; if (!a.available) return "ไม่พบเซนเซอร์ (ENS160/AHT21)";
    const co2 = a.eco2_ppm != null ? `eCO₂ ${a.eco2_ppm} ppm (${AIR_TH[a.rating] || "—"})` : "eCO₂ —";
    const th = a.temp_c != null ? ` · ${a.temp_c} °C · ${a.rh_pct} %` : "";
    const warm = a.validity === 1 ? " · กำลังอุ่น 3 นาที" : a.validity === 2 ? " · ชั่วโมงแรก (ค่ายังไม่นิ่ง)" : a.validity === 3 ? " · ค่าผิดปกติ" : "";
    return co2 + (a.tvoc_ppb != null ? ` · TVOC ${a.tvoc_ppb} ppb` : "") + th + warm;
  }
  function airChip(a) {
    const e = $("air"); if (!a || !a.available) { e.hidden = true; airTiles(a); return; }
    e.hidden = false;
    const word = a.validity === 1 || a.validity === 2 ? "กำลังอุ่น" : (AIR_TH[a.rating] || "—").split(" ")[0];
    e.innerHTML = `อากาศ <b>${word}</b>` + (a.eco2_ppm != null ? ` · ${a.eco2_ppm}` : "") + (a.temp_c != null ? ` · ${a.temp_c.toFixed(0)}°` : "");
    e.className = "chip " + (!a.validity && (a.rating === "poor" || a.rating === "bad") ? "warn" : "");
    airTiles(a);
  }
  function airTiles(a) {
    const wrap = $("air-tiles"), st = $("air-state"); if (!wrap) return;
    const ok = a && a.available;
    wrap.classList.toggle("off", !ok);
    st.textContent = !a ? "ปิดไว้" : !ok ? "ไม่พบเซนเซอร์ — เช็คสาย SDA/SCL" : a.validity === 1 ? "กำลังอุ่น 3 นาที ค่ายังไม่ใช่ของจริง" : a.validity === 2 ? "ชั่วโมงแรกของเซนเซอร์ ค่ายังลอย" : a.validity === 3 ? "ค่าผิดปกติ" : "ปกติ";
    const set = (id, v, dp = 0) => { $(id).textContent = ok && v != null ? (+v).toFixed(dp) : "—"; };
    set("a-co2", a && a.eco2_ppm); set("a-tvoc", a && a.tvoc_ppb); set("a-aqi", a && a.aqi); set("a-temp", a && a.temp_c, 1); set("a-rh", a && a.rh_pct, 0);
    $("a-rating").textContent = ok && !a.validity ? (AIR_TH[a.rating] || "") : "";
    const bad = ok && !a.validity && (a.rating === "bad"), warn = ok && !a.validity && (a.rating === "poor");
    $("a-co2").parentElement.className = "tile" + (bad ? " bad" : warn ? " warn" : "");
    $("a-aqi").parentElement.className = "tile" + (ok && a.aqi >= 5 ? " bad" : ok && a.aqi >= 4 ? " warn" : "");
  }
  function renderKv() {
    const t = lastTele || {}, s = lastSys || { cleaning: {}, drive: {} };
    const rows = [["โหมด", t.state_name || "—"], ["ความเร็วสั่ง", t.v != null ? `${t.v} mm/s · หมุน ${t.w} mrad/s` : "—"], ["ล้อซ้าย / ขวา", t.duty_l != null ? `${t.duty_l} / ${t.duty_r} ‰` : "—"],
      ["เสายกกล้อง", t.us_l ? `${usToDeg(camAx.lift, t.us_l)}° (${t.us_l} µs)` : "ปล่อย"], ["มุมกล้อง", t.us_r ? `${usToDeg(camAx.tilt, t.us_r)}° (${t.us_r} µs)` : "ปล่อย"], ["ดูด / แปรง", `${s.cleaning.suction ? "เปิด" : "ปิด"} / ${s.cleaning.brush ? "เปิด" : "ปิด"}`],
      ["แบตเตอรี่", t.vbat_mV ? `${(t.vbat_mV / 1000).toFixed(2)} V` : "ยังไม่มี ADC ในเฟิร์มแวร์"],
 ["deadman Pi", `${s.drive.tripped ?? 0} ครั้ง`], ["Pi", `${s.cpu_temp_c ?? "—"} °C · SD ว่าง ${s.disk_free_mb ?? "—"} MB`]];
    $("kv").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  }

  // ── ความเร็ว ──
  let speedPct = cfg.maxPct;
  function setSpeed(pct, persist = true) {
    speedPct = Math.max(10, Math.min(100, pct)); $("spd").value = speedPct; $("spdnum").textContent = Math.round(V_MAX * speedPct / 100);
    document.querySelectorAll(".dial-presets button, .pad-foot button").forEach((b) => b.classList.toggle("on", +b.dataset.pct === speedPct));
    if (persist) { cfg.maxPct = speedPct; save(); }
  }
  $("spd").oninput = (e) => setSpeed(+e.target.value);
  document.querySelectorAll(".dial-presets button, .pad-foot button").forEach((b) => b.onclick = () => setSpeed(+b.dataset.pct));

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
    const len = Math.hypot(x, y); if (len > 1) { x /= len; y /= len; }
    if (cfg.joySnap && len > 0.05) { if (Math.abs(x) < 0.38 * len) x = 0; else if (Math.abs(y) < 0.38 * len) y = 0; }   // ล็อกแกน: ใกล้แนวตั้ง = ตรง · ใกล้แนวนอน = หมุนล้วน (±22°)
    jx = x; jy = y; paintKnob(x, y); }
  // C36 ปุ่มทิศทาง: แต่ละปุ่มจับ pointer ของตัวเอง (กด 2 ปุ่มพร้อมกันได้) · เวกเตอร์ = ผลรวมของปุ่มที่กดค้าง
  const padHeld = new Map();
  document.querySelectorAll("#pad [data-dir]").forEach((b) => {
    const d = b.dataset.dir;
    const up = (e) => { if (padHeld.delete(e.pointerId)) { b.classList.remove("hold"); pump(); } };
    b.addEventListener("pointerdown", (e) => { e.preventDefault();
      if (d === "stop") { padHeld.clear(); document.querySelectorAll("#pad .hold").forEach((x) => x.classList.remove("hold")); pump(); send({ t: "stop" }); return; }
      try { b.setPointerCapture(e.pointerId); } catch (_) {}
      padHeld.set(e.pointerId, d.split(":").map(Number)); b.classList.add("hold"); pump(); });
    ["pointerup", "pointercancel", "lostpointercapture"].forEach((ev) => b.addEventListener(ev, up));
  });
  function dpadVec() { if (!padHeld.size) return null; let x = 0, y = 0; for (const [dx, dy] of padHeld.values()) { x += dx; y += dy; } return [Math.max(-1, Math.min(1, x)), Math.max(-1, Math.min(1, y))]; }
  const keys = new Set();
  window.addEventListener("keydown", (e) => { if (e.target.tagName === "INPUT" || e.target.tagName === "SELECT") return; if (e.repeat) return; const k = e.key.toLowerCase();
    if (k === " ") { e.preventDefault(); estop(); return; } if (k === "c") { capture(); return; } if (k === "f") { toggleSuction(); return; } if (k === "g") { toggleBrush(); return; }
    if (k === "1") return setSpeed(25); if (k === "2") return setSpeed(50); if (k === "3") return setSpeed(100);
    if (k === "q") return zoomBy(-0.5); if (k === "e") return zoomBy(0.5); keys.add(k); });
  window.addEventListener("keyup", (e) => { keys.delete(e.key.toLowerCase()); pump(); });
  window.addEventListener("blur", () => { keys.clear(); endJoy(); padHeld.clear(); document.querySelectorAll("#pad .hold").forEach((x) => x.classList.remove("hold")); });
  const keyVec = () => { let x = 0, y = 0; if (keys.has("w") || keys.has("arrowup")) y++; if (keys.has("s") || keys.has("arrowdown")) y--; if (keys.has("a") || keys.has("arrowleft")) x--; if (keys.has("d") || keys.has("arrowright")) x++; return [x, y]; };
  let padBtn = {};
  function padVec() { const gp = (navigator.getGamepads ? navigator.getGamepads() : [])[0]; if (!gp) return [0, 0];
    const p = (i) => gp.buttons[i] && gp.buttons[i].pressed; const edge = (i, fn) => { if (p(i) && !padBtn[i]) fn(); padBtn[i] = p(i); };
    edge(1, estop); edge(0, capture); edge(2, toggleSuction); const boost = gp.buttons[7] ? gp.buttons[7].value : 0;
    const dz = (v) => Math.abs(v) < cfg.deadzone ? 0 : v; return [dz(gp.axes[0] || 0) * (1 + boost * 0.5), -dz(gp.axes[1] || 0) * (1 + boost * 0.5)]; }
  let stepInput = false;                                 // true = อินพุตแบบปุ่ม (ทิศทาง/คีย์) → หมุนตามความเร็วที่ตั้ง · มุม = โค้งตาม curveTurn
  function inputVec() { stepInput = false; if (joyActive) return [jx, jy]; const dp = dpadVec(); if (dp) { stepInput = true; return dp; }
    const [kx, ky] = keyVec(); if (kx || ky) { stepInput = true; return [kx, ky]; } return padVec(); }

  // ── ส่งคำสั่ง 10 Hz · ramp ฝั่ง client ตาม cfg.rampMs ──
  let driving = false, curV = 0, curW = 0, lastT = performance.now();
  function pump() {
    const now = performance.now(), dt = now - lastT; lastT = now;
    let [x, y] = inputVec();
    if (Math.hypot(x, y) < cfg.deadzone) x = y = 0;
    if (cfg.invY) y = -y; if (cfg.invX) x = -x;
    const tv = y * V_MAX * speedPct / 100;
    let tw = -x * cfg.turnGain * (cfg.turnScale ? (1 - 0.5 * Math.abs(y)) : 1);
    if (stepInput) tw = -x * cfg.turnGain * (y ? cfg.curveTurn / 100 : speedPct / 100);   // ปุ่ม: หมุนอยู่กับที่เร็วตามสปีดที่เลือก · ปุ่มมุม = โค้งคงที่
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
  const BRUSH_ON_PCT = 100;
  let suction = 0, brush = 0, idleT;
  function sendClean() { send({ t: "clean", suction, brush }); paintTog(); }
  function toggleSuction() { suction = suction ? 0 : cfg.suctionPct; sendClean(); }
  function toggleBrush() { brush = brush ? 0 : BRUSH_ON_PCT; sendClean(); }   // แปรง = เปิด/ปิดเหมือนดูด (ผู้ใช้ 21 ก.ย.) · 100 % ของราง 5 V = 5 V ≤ พิกัด 6 V (C30)
  $("suction").onclick = toggleSuction; $("brush").onclick = toggleBrush;
  function paintTog() { $("suction").classList.toggle("on", !!suction); $("suction").querySelector("b").textContent = suction ? "เปิด" : "ปิด";
    $("brush").classList.toggle("on", !!brush); $("brush").querySelector("b").textContent = brush ? "เปิด" : "ปิด"; }
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

  // ── C36 ซูม/แพน/ทิลต์/โฟกัสกล้อง — ค่าจริงอยู่ที่ Pi (sys.cam_ctl / cam_ctl) · ส่ง {t:"cam"} แบบ throttle ──
  let camCtl = null, camSendT = 0, camPending = null;
  function camSend(o) { camPending = { ...(camPending || {}), ...o }; const now = performance.now();
    if (now - camSendT > 80) { camSendT = now; send({ t: "cam", ...camPending }); camPending = null; }
    else setTimeout(() => { if (camPending) { camSendT = performance.now(); send({ t: "cam", ...camPending }); camPending = null; } }, 90); }
  function paintCam(c) {
    camCtl = c; const has = !!c; $("camctl-rows").classList.toggle("off", !has); $("zoom-col").classList.toggle("off", !has);
    if (!has) { $("zoom-v").textContent = "—"; $("zoom-tag").hidden = true; $("camctl-note").textContent = "กล้องนี้คุมซูมไม่ได้ (ไม่มีกล้อง / ภาพนิ่ง)"; return; }
    const z = +c.zoom; $("cc-zoom").max = c.zoom_max; $("cc-zoom").value = z; $("cc-zoom-o").textContent = `${z.toFixed(1)}×` + (c.sw_zoom ? " (ซอฟต์แวร์)" : z > 2 ? " · เกิน 2× กล้องขยายภาพ" : "");
    $("zoom-v").textContent = `${z.toFixed(1)}×`; if (!zoomDrag) { $("zoom-sl").max = c.zoom_max; $("zoom-sl").value = z; }
    $("zoom-tag").hidden = z <= 1.01; $("zoom-tag").textContent = `${z.toFixed(1)}×`; vp.classList.toggle("zoomed", z > 1.01);
    $("cc-af").checked = !!c.af; $("cc-af").disabled = !c.hw.af; $("cc-focus").disabled = c.af || !c.hw.focus; $("cc-focus").value = c.focus; $("cc-focus-o").textContent = (+c.focus).toFixed(2);
    $("camctl-note").textContent = c.sw_zoom ? "กล้องไม่มีซูม UVC — ครอปภาพ 1080p แทน (เกิน 2× ตัวเลขจะแตก)" : "ซูม UVC ครอปจากเซนเซอร์ 4K: ≤ 2× คมเท่าเดิม · ถ่าง 2 นิ้วบนภาพ = ซูม · ลาก = เลื่อน · แตะ 2 ครั้ง = 1×";
  }
  function zoomTo(z) { if (!camCtl) return; z = Math.max(1, Math.min(camCtl.zoom_max, z)); camCtl.zoom = z; paintCam(camCtl); camSend({ zoom: +z.toFixed(2) }); }
  function zoomBy(d) { zoomTo((camCtl ? +camCtl.zoom : 1) + d); }
  $("cc-zoom").oninput = (e) => zoomTo(+e.target.value);
  $("cc-af").onchange = (e) => camSend({ af: e.target.checked });
  $("cc-focus").oninput = (e) => { $("cc-focus-o").textContent = (+e.target.value).toFixed(2); camSend({ focus: +e.target.value }); };
  $("cc-reset").onclick = () => { camSend({ zoom: 1, pan: 0, tilt: 0 }); if (camCtl) { camCtl.zoom = 1; camCtl.pan = 0; camCtl.tilt = 0; paintCam(camCtl); } };
  let zoomDrag = false;
  $("zoom-sl").addEventListener("pointerdown", () => { zoomDrag = true; });
  ["pointerup", "pointercancel", "change"].forEach((ev) => $("zoom-sl").addEventListener(ev, () => { zoomDrag = false; }));
  $("zoom-sl").addEventListener("input", (e) => zoomTo(+e.target.value));
  let zoomT = null;                                    // ปุ่ม +/− บนแผงกล้อง: แตะ = 0.2× · กดค้าง = ไต่ต่อเนื่อง
  document.querySelectorAll("[data-zoom]").forEach((b) => { const dir = +b.dataset.zoom;
    const stop = () => { clearInterval(zoomT); zoomT = null; b.classList.remove("hold"); };
    b.addEventListener("pointerdown", (e) => { e.preventDefault(); try { b.setPointerCapture(e.pointerId); } catch (_) {} b.classList.add("hold"); zoomBy(dir * 0.2); clearInterval(zoomT); zoomT = setInterval(() => zoomBy(dir * 0.2), 120); });
    ["pointerup", "pointercancel", "lostpointercapture"].forEach((ev) => b.addEventListener(ev, stop)); });
  // ท่าทางบนภาพสด: ถ่าง 2 นิ้ว = ซูม · ลาก 1 นิ้วขณะซูม = แพน/ทิลต์ · แตะ 2 ครั้ง = กลับ 1× (ไม่ทำงานตอนตั้งกรอบ ROI)
  const pts = new Map(); let pinch0 = null, drag0 = null, lastTap = 0;
  vp.addEventListener("pointerdown", (e) => { if (roiEditing || !camCtl) return; pts.set(e.pointerId, [e.clientX, e.clientY]); try { vp.setPointerCapture(e.pointerId); } catch (_) {}
    if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch0 = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), z: +camCtl.zoom }; drag0 = null; }
    else if (pts.size === 1) { const now = performance.now(); if (now - lastTap < 300) { $("cc-reset").onclick(); lastTap = 0; } else lastTap = now;
      drag0 = camCtl.zoom > 1.01 ? { x: e.clientX, y: e.clientY, pan: +camCtl.pan, tilt: +camCtl.tilt } : null; } });
  vp.addEventListener("pointermove", (e) => { if (!pts.has(e.pointerId)) return; pts.set(e.pointerId, [e.clientX, e.clientY]);
    if (pts.size === 2 && pinch0) { const [a, b] = [...pts.values()]; zoomTo(pinch0.z * Math.hypot(a[0] - b[0], a[1] - b[1]) / pinch0.d); }
    else if (pts.size === 1 && drag0) { const r = vp.getBoundingClientRect(); const z = +camCtl.zoom;
      const pan = Math.max(-1, Math.min(1, drag0.pan - (e.clientX - drag0.x) / r.width * 2 / (z - 1 || 1) * (cfg.mirror ? -1 : 1)));
      const tilt = Math.max(-1, Math.min(1, drag0.tilt + (e.clientY - drag0.y) / r.height * 2 / (z - 1 || 1)));
      camCtl.pan = pan; camCtl.tilt = tilt; camSend({ pan: +pan.toFixed(3), tilt: +tilt.toFixed(3) }); } });
  const endPt = (e) => { pts.delete(e.pointerId); if (pts.size < 2) pinch0 = null; if (!pts.size) drag0 = null; };
  ["pointerup", "pointercancel"].forEach((ev) => vp.addEventListener(ev, endPt));
  fetch("/api/cam").then((r) => r.json()).then(paintCam).catch(() => paintCam(null));

  // ── กันจอดับ ──
  let wl = null;
  async function wake() { try { if (cfg.wakeLock && !wl && navigator.wakeLock) wl = await navigator.wakeLock.request("screen"); if (!cfg.wakeLock && wl) { await wl.release(); wl = null; } } catch (e) {} }
  document.addEventListener("visibilitychange", () => { if (!document.hidden) { wl = null; wake(); } });

  applyCfg(); startStream();
})();
