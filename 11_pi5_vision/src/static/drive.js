// drive.js — cockpit ขับเอง · vanilla JS · ไม่โหลดอะไรจากเน็ต
// หลัก: browser ส่ง {t:"drive",v,w} ทุก 100 ms "ตราบที่ผู้ใช้ยังกด" · ปล่อย = {t:"release"} ทันที
//       Pi ถือค่าล่าสุดแล้วส่ง $V ซ้ำเอง · เงียบ 300 ms = Pi ส่ง $S เอง (ไฟล์ 19 §19.3)
(() => {
  const $ = (id) => document.getElementById(id);
  const V_MAX = 150;                       // mm/s (G14) — ESP32 clamp ซ้ำอยู่ดี
  let wGain = 1000;                        // mrad/s ที่จอยสุดทาง
  let speedPct = 50;

  // ── ภาพสด ──
  const cam = $("cam");
  const startStream = () => { cam.src = "/stream.mjpg?" + Date.now(); };
  cam.onerror = () => setTimeout(startStream, 2000);
  startStream();

  // ── WebSocket ──
  let ws, wsOk = false;
  function connect() {
    ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
    ws.onopen = () => { wsOk = true; setLink("ต่ออยู่", ""); };
    ws.onclose = () => { wsOk = false; setMode("ขาดการเชื่อมต่อ", "lost"); setLink("หลุด — ต่อใหม่…", "bad"); stopInput(); setTimeout(connect, 1000); };
    ws.onmessage = (m) => handle(JSON.parse(m.data));
  }
  const send = (o) => { if (wsOk && ws.readyState === 1) ws.send(JSON.stringify(o)); };
  connect();

  // ── HUD ──
  const setMode = (txt, cls) => { const e = $("mode"); e.textContent = txt; e.className = "mode " + (cls || ""); };
  const setLink = (txt, cls) => { const e = $("link"); e.textContent = "ลิงก์ " + txt; e.className = "stat " + (cls || ""); };
  let warnTimer;
  function warn(msg, bad) {
    const w = $("warn"); w.textContent = msg; w.className = "warn" + (bad ? " bad" : ""); w.hidden = false;
    clearTimeout(warnTimer); warnTimer = setTimeout(() => { w.hidden = true; }, 2500);
  }
  const evl = $("ev");
  function logEv(text, cls) {
    const li = document.createElement("li"); li.textContent = new Date().toLocaleTimeString("th-TH", { hour12: false }) + " " + text; li.className = cls || "";
    evl.prepend(li); while (evl.children.length > 60) evl.lastChild.remove();
  }

  const NACK_TH = { MAST_UP: "เสายังไม่พับ — ขับไม่ได้ (G2)", IN_MISSION: "หุ่นกำลังเดินภารกิจอัตโนมัติ", SUCTION_SPINUP: "เพิ่งเปิดดูด รอ 1 วิ ก่อนออกตัว", NOT_STOPPED: "ต้องหยุดล้อก่อนเปิดดูด", NOT_IMPLEMENTED: "ESP32 ยังไม่รองรับคำสั่งนี้", BAD_ARGS: "คำสั่งผิดรูปแบบ" };

  function handle(ev) {
    switch (ev.t) {
      case "hello": (ev.events || []).slice(-10).forEach(handle); break;
      case "sys": {
        $("cams").textContent = "กล้อง " + (ev.cam_ok ? "ปกติ" : "ไม่มีภาพ");
        const L = ev.link;
        if (!L) setMode("ไม่มี serial", "lost");
        else if (!L.alive) { setMode("ESP32 ไม่ตอบ", "lost"); setLink(L.age_s == null ? "ยังไม่เคยได้ข้อมูล" : `เงียบ ${L.age_s}s`, "bad"); }
        else setLink(`${L.age_s}s · ส่ง ${L.stats.tx} · ปฏิเสธ ${L.stats.nack}`, "");
        renderKv(ev); break;
      }
      case "tele": {
        setMode(ev.state_name === "MANUAL" ? "ขับเอง" : ev.state_name === "MISSION" ? "ภารกิจอัตโนมัติ" : "พร้อม", ev.state_name === "MANUAL" ? "manual" : ev.state_name === "MISSION" ? "mission" : "");
        $("velo").textContent = `${ev.v} mm/s · ล้อ ${ev.duty_l}/${ev.duty_r}‰`;
        $("bat").textContent = ev.vbat_mV ? `แบต ${(ev.vbat_mV / 1000).toFixed(1)} V` : "แบต — (ยังไม่มี ADC)";
        if (ev.comm_lost) warn("ESP32 ตัดเอง: ไม่ได้คำสั่งใน 300 ms", true);
        lastTele = ev; break;
      }
      case "nack": { const th = NACK_TH[ev.reason] || ev.reason; warn("ปฏิเสธ: " + th, false); logEv("ปฏิเสธ " + ev.reason, "warn"); break; }
      case "capture": { $("capture").disabled = false; logEv(ev.ok ? `ถ่ายแล้ว ${ev.image}` : `ถ่ายไม่สำเร็จ: ${ev.reason}`, ev.ok ? "good" : "bad"); if (ev.ok) warn("ถ่ายแล้ว — กำลังอ่านค่า…"); break; }
      case "reading": { logEv(`ค่าที่อ่านได้: ${ev.value ?? "อ่านไม่ออก"} (conf ${ev.confidence})`, ev.value == null ? "warn" : "good"); warn(ev.value == null ? "อ่านตัวเลขไม่ออก — เล็งใหม่แล้วถ่ายอีกครั้ง" : `อ่านได้ ${ev.value}`); break; }
      case "log": if (ev.level === "warn" || ev.level === "bad") { logEv(ev.msg, ev.level); if (ev.level === "bad") warn(ev.msg, true); } break;
      case "event": logEv(`ESP32: ${ev.code} ${ev.detail || ""}`, "warn"); break;
    }
  }
  let lastTele = null;
  function renderKv(s) {
    const t = s.tele || {};
    const rows = [
      ["โหมด", t.state_name || "—"],
      ["ความเร็วสั่ง", t.v != null ? `${t.v} mm/s · หมุน ${t.w} mrad/s` : "—"],
      ["ล้อซ้าย / ขวา", t.duty_l != null ? `${t.duty_l} / ${t.duty_r} ‰` : "—"],
      ["เสายกกล้อง", t.mast === 2 ? "จับสัญญาณ (ยก/ค้าง)" : t.mast === 0 ? "พับ" : "—"],
      ["ดูด / แปรง", `${s.cleaning.suction} % / ${s.cleaning.brush} %`],
      ["แบตเตอรี่", t.vbat_mV ? `${(t.vbat_mV / 1000).toFixed(2)} V` : "ยังไม่มี ADC ในเฟิร์มแวร์"],
      ["deadman Pi", `${s.drive.tripped} ครั้ง`],
      ["Pi", `${s.cpu_temp_c ?? "—"} °C · SD ว่าง ${s.disk_free_mb} MB`],
    ];
    $("kv").innerHTML = rows.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  }

  // ── อินพุตขับ: จอย touch + คีย์บอร์ด + gamepad → (x,y) ∈ [-1,1] ──
  let jx = 0, jy = 0, joyActive = false;
  const joy = $("joy"), knob = $("knob");
  const R = () => joy.clientWidth / 2;
  function setKnob(x, y) { knob.style.transform = `translate(${x * (R() - 28)}px, ${-y * (R() - 28)}px)`; }
  joy.addEventListener("pointerdown", (e) => { joy.setPointerCapture(e.pointerId); joyActive = true; joy.classList.add("active"); moveJoy(e); });
  joy.addEventListener("pointermove", (e) => { if (joyActive) moveJoy(e); });
  const endJoy = () => { joyActive = false; joy.classList.remove("active"); jx = jy = 0; setKnob(0, 0); releaseIfIdle(); };
  joy.addEventListener("pointerup", endJoy); joy.addEventListener("pointercancel", endJoy);
  function moveJoy(e) {
    const r = joy.getBoundingClientRect(); const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    let x = (e.clientX - cx) / R(), y = -(e.clientY - cy) / R();
    const len = Math.hypot(x, y); if (len > 1) { x /= len; y /= len; }
    jx = x; jy = y; setKnob(x, y);
  }
  const keys = new Set();
  window.addEventListener("keydown", (e) => { if (e.repeat) return; if (e.key === " ") { e.preventDefault(); estop(); return; } keys.add(e.key.toLowerCase()); });
  window.addEventListener("keyup", (e) => { keys.delete(e.key.toLowerCase()); releaseIfIdle(); });
  window.addEventListener("blur", () => { keys.clear(); endJoy(); });
  function keyVec() { let x = 0, y = 0; if (keys.has("w") || keys.has("arrowup")) y += 1; if (keys.has("s") || keys.has("arrowdown")) y -= 1; if (keys.has("a") || keys.has("arrowleft")) x -= 1; if (keys.has("d") || keys.has("arrowright")) x += 1; return [x, y]; }
  function padVec() {
    const gp = (navigator.getGamepads ? navigator.getGamepads() : [])[0]; if (!gp) return [0, 0, false];
    const dz = (v) => Math.abs(v) < 0.12 ? 0 : v;
    if (gp.buttons[1] && gp.buttons[1].pressed) estop();                      // ปุ่ม B/○ = E-STOP
    return [dz(gp.axes[0] || 0), -dz(gp.axes[1] || 0), true];
  }

  // ── ส่งคำสั่งทุก 100 ms ขณะมีอินพุต · ปล่อย = release ทันที ──
  let driving = false;
  function inputVec() {
    if (joyActive) return [jx, jy];
    const [kx, ky] = keyVec(); if (kx || ky) return [kx, ky];
    const [px, py] = padVec(); return [px, py];
  }
  function releaseIfIdle() { const [x, y] = inputVec(); if (!x && !y && driving) { driving = false; send({ t: "release" }); } }
  setInterval(() => {
    const [x, y] = inputVec();
    if (!x && !y) { if (driving) { driving = false; send({ t: "release" }); } return; }
    driving = true;
    const v = Math.round(y * V_MAX * speedPct / 100);
    const w = Math.round(-x * wGain * (0.5 + speedPct / 200));               // หมุนช้าลงตามความเร็วที่ตั้ง
    send({ t: "drive", v, w });
  }, 100);
  function stopInput() { keys.clear(); driving = false; }

  // ── ปุ่ม ──
  function estop() { send({ t: "estop" }); driving = false; warn("หยุดฉุกเฉิน", true); logEv("E-STOP", "bad"); }
  $("estop").onclick = estop;
  $("capture").onclick = () => { $("capture").disabled = true; send({ t: "capture" }); setTimeout(() => { $("capture").disabled = false; }, 5000); };
  let suction = 0, brush = 0;
  $("suction").onclick = () => { suction = suction ? 0 : 100; send({ t: "clean", suction, brush }); paintTog(); };
  $("brush").onclick = () => { brush = brush ? 0 : 24; send({ t: "clean", suction, brush }); paintTog(); };
  function paintTog() { $("suction").classList.toggle("on", !!suction); $("suction").querySelector("b").textContent = suction ? "เปิด" : "ปิด";
                        $("brush").classList.toggle("on", !!brush); $("brush").querySelector("b").textContent = brush ? `${brush} %` : "ปิด"; }
  $("spd").oninput = (e) => { speedPct = +e.target.value; $("spdv").textContent = speedPct + "%"; };
  $("wgain").oninput = (e) => { wGain = +e.target.value; $("wgainv").textContent = wGain; };
  $("side-btn").onclick = () => { $("side").hidden = false; };
  $("side-close").onclick = () => { $("side").hidden = true; };
})();
