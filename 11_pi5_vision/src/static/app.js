// app.js — หน้าเว็บควบคุม MRC-001 · vanilla JS · ไม่โหลดอะไรจากอินเทอร์เน็ต (สนามไม่มีเน็ต)
(() => {
  const $ = (id) => document.getElementById(id);
  const fmtT = (ts) => new Date((ts || 0) * 1000).toLocaleTimeString("th-TH", { hour12: false });
  const fmtISO = (iso, long = false) => {          // captured_at อาจหายถ้า record ไม่ครบ — อย่าโชว์ "Invalid Date"
    const d = iso ? new Date(iso) : null;
    if (!d || isNaN(d)) return "—";
    return long ? d.toLocaleString("th-TH", { hour12: false }) : d.toLocaleTimeString("th-TH", { hour12: false });
  };
  const pill = (id, cls, text) => { const e = $(id); e.className = "pill " + cls; e.textContent = text; };

  // ── ภาพสด ──
  const img = $("stream");
  const startStream = () => { img.src = "/stream.mjpg?" + Date.now(); };
  img.onerror = () => setTimeout(startStream, 2000);
  startStream();

  // ── log เหตุการณ์ ──
  const events = $("events");
  function addEvent(ev) {
    const li = document.createElement("li");
    let text = "", cls = "";
    switch (ev.t) {
      case "capture":
        text = ev.ok ? `ถ่าย #${ev.n} (${ev.source}) → ${ev.image} · เซฟ ${ev.t_ack_ms} ms`
                     : `ถ่าย #${ev.n} (${ev.source}) ล้ม: ${ev.reason}`;
        cls = ev.ok ? "good" : "bad"; break;
      case "reading":
        text = `OCR #${ev.n}: value=${ev.value ?? "—"} conf=${ev.confidence ?? "—"} raw="${ev.raw_text ?? ""}" ${ev.ocr_ms} ms` + (ev.error ? ` ⚠ ${ev.error}` : "");
        cls = ev.value == null ? "warn" : "good"; break;
      case "nack": text = `ปฏิเสธ ${ev.cmd}: ${ev.reason}`; cls = "warn"; break;
      case "log":  text = ev.msg; break;
      default: return;
    }
    li.innerHTML = `<span class="t">${fmtT(ev.ts)}</span><span>${text}</span>`;
    li.className = cls;
    events.prepend(li);
    while (events.children.length > 200) events.lastChild.remove();
  }

  // ── ค่าที่อ่านได้ ──
  const tbody = document.querySelector("#readings tbody");
  function renderLatest(r) {
    const box = $("latest");
    if (!r) { box.className = "latest empty"; box.textContent = "ยังไม่มีค่า"; return; }
    box.className = "latest";
    const none = r.value == null;
    box.innerHTML = `
      <div class="big ${none ? "none" : ""}">${none ? "อ่านไม่ออก" : r.value}</div>
      <dt class="muted">เวลา</dt><dd>${fmtISO(r.captured_at, true)}</dd>
      <dt class="muted">conf</dt><dd>${r.confidence ?? "—"}</dd>
      <dt class="muted">raw</dt><dd><code>${r.raw_text ?? ""}</code></dd>
      <dt class="muted">สถานะ</dt><dd>${r.status ?? "ocr"}${r.meter_id ? " · " + r.meter_id : ""}</dd>
      ${r.image_path ? `<img src="/${r.image_path}" alt="ภาพมิเตอร์">` : ""}`;
  }
  function addReadingRow(r, prepend = true) {
    const tr = document.createElement("tr");
    const none = r.value == null;
    tr.innerHTML = `<td>${fmtISO(r.captured_at)}</td>
      <td class="${none ? "none" : ""}">${none ? "—" : r.value}</td>
      <td>${r.confidence ?? "—"}</td><td><code>${r.raw_text ?? ""}</code></td>
      <td>${r.source_req ?? r.source ?? ""}</td><td>${r.ocr_ms ?? ""}</td>
      <td>${r.image_path ? `<a href="/${r.image_path}" target="_blank">ดู</a>` : ""}</td>`;
    prepend ? tbody.prepend(tr) : tbody.append(tr);
    $("rd-count").textContent = `(${tbody.children.length})`;
  }
  fetch("/api/readings?limit=50").then(r => r.json()).then(rows => {
    rows.forEach(r => addReadingRow(r, false));
    renderLatest(rows[0]);
  }).catch(() => {});

  // ── สถานะระบบ ──
  function applyStatus(s) {
    pill("p-cam", s.cam_ok ? "ok" : "off", s.cam_ok ? "กล้อง: มีเฟรม" : "กล้อง: ไม่มีเฟรม");
    const L = s.link;
    if (!L) pill("p-link", "off", "ESP32: ไม่มี serial");
    else if (L.alive) pill("p-link", "ok", `ESP32: ตอบล่าสุด ${L.age_s}s`);
    else pill("p-link", "warn", L.age_s == null ? "ESP32: ยังไม่เคยได้เฟรม" : `ESP32: เงียบ ${L.age_s}s`);
    pill("p-sys", (s.cpu_temp_c ?? 0) > 75 ? "warn" : "", `Pi: ${s.cpu_temp_c ?? "—"}°C · SD ว่าง ${s.disk_free_mb} MB · รอ sync ${s.pending_sync}`);
    const kv = $("link-kv");
    const st = L ? L.stats : {};
    kv.innerHTML = [
      ["พอร์ต", L ? `${L.port} @ ${L.baud}` : "—"],
      ["ESP32 รองรับ", (s.esp32_supports || []).join(" · ")],
      ["CAPTURE_REQ", `รับ ${st.req ?? 0} · ตอบ ok ${st.ok ?? 0} · fail ${st.fail ?? 0}`],
      ["ถ่ายจากเว็บ", st.manual ?? 0],
      ["บรรทัดขยะที่ทิ้ง", st.bad_lines ?? 0],
      ["client ที่ต่ออยู่", s.clients],
    ].map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join("");
  }

  // ── WebSocket ──
  let ws;
  function connect() {
    ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
    ws.onopen = () => pill("p-ws", "ok", "เว็บ: ต่ออยู่");
    ws.onclose = () => { pill("p-ws", "off", "เว็บ: หลุด — ต่อใหม่…"); setTimeout(connect, 1000); };
    ws.onmessage = (m) => {
      const ev = JSON.parse(m.data);
      if (ev.t === "hello") { (ev.events || []).forEach(addEvent); return; }
      if (ev.t === "sys") { applyStatus(ev); return; }
      addEvent(ev);
      if (ev.t === "reading") { addReadingRow(ev); renderLatest(ev); }
      if (ev.t === "capture") {
        const btn = $("btn-capture"); btn.disabled = false;
        $("cap-result").textContent = ev.ok ? `เซฟ ${ev.image} ใน ${ev.t_ack_ms} ms — รอ OCR…` : `ล้ม: ${ev.reason}`;
      }
    };
  }
  connect();

  $("btn-capture").onclick = () => {
    if (!ws || ws.readyState !== 1) return;
    $("btn-capture").disabled = true;
    $("cap-result").textContent = "กำลังถ่าย…";
    ws.send(JSON.stringify({ t: "capture" }));
    setTimeout(() => { $("btn-capture").disabled = false; }, 5000);   // กันค้างถ้าไม่มี event กลับ
  };
})();
