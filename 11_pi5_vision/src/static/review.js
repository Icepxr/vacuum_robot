// review.js — F10 ป๊อปอัพหลังถ่าย (design/aria-data-spec-v1.md §2.0) · vanilla · ไม่โหลดอะไรจากเน็ต
// รูปใหม่ → เปิดทันที · เลือกห้อง + ชนิด → "เก็บ" (ลง readings.jsonl รอ sync) หรือ "ไม่เอา" (ลบ ต้องแตะ 2 ครั้ง)
// ปิดไว้ก่อน/เน็ตหลุด/ปิดแอป = รูปค้างบน Pi · ป้าย "รูปรอตัดสิน" เปิดกลับมาได้ · ครบ 7 วัน Pi ลบเอง
(() => {
  const $ = (id) => document.getElementById(id);
  const box = $("review"), badge = $("review-badge");
  if (!box) return;
  let queue = [], cur = null, armT = null, busy = false, replaying = false;
  let last = {};
  try { last = JSON.parse(localStorage.getItem("mrc.review.last") || "{}"); } catch (e) {}

  const typeInputs = () => [...document.querySelectorAll('input[name="review-type"]')];
  const fmtTime = (iso) => { try { return new Date(iso).toLocaleString("th-TH", { hour12: false, dateStyle: "short", timeStyle: "short" }); } catch (e) { return ""; } };

  function paintBadge() {
    const n = queue.length - (cur && !box.hidden ? 1 : 0);
    $("review-n").textContent = queue.length;
    badge.hidden = queue.length === 0 || (!box.hidden && n <= 0);
  }
  function err(msg) { const e = $("review-err"); e.textContent = msg || ""; e.hidden = !msg; }
  function disarm() { clearTimeout(armT); armT = null; $("review-discard").classList.remove("armed"); $("review-discard").textContent = "ไม่เอา · ลบรูป"; }

  function open(item) {
    cur = item; disarm(); err("");
    $("review-meta").textContent = fmtTime(item.captured_at);
    const img = $("review-img");
    if (item.crop_url) { img.src = item.crop_url + "?t=" + Date.now(); img.hidden = false; $("review-noimg").hidden = true; }
    else { img.removeAttribute("src"); img.hidden = true; $("review-noimg").hidden = false; }
    $("review-value").textContent = item.value == null ? "อ่านไม่ออก" : String(item.value);
    $("review-value").classList.toggle("none", item.value == null);
    $("review-conf").textContent = item.confidence != null && item.value != null ? `ความมั่นใจ ${Math.round(item.confidence * 100)} %` : "";
    $("review-room").value = last.room || "";
    typeInputs().forEach((r) => { r.checked = r.value === last.type; });
    box.hidden = false; paintBadge();
    ($("review-room").value ? $("review-keep") : $("review-room")).focus();
  }
  function close() { box.hidden = true; cur = null; disarm(); paintBadge(); }
  function next() { const nx = queue.find((q) => !cur || q.local_id !== cur.local_id); close(); return nx; }
  function drop(lid) { queue = queue.filter((q) => q.local_id !== lid); }

  async function decide(keep) {
    if (!cur || busy) return;
    const room = $("review-room").value.trim(), t = typeInputs().find((r) => r.checked);
    if (keep && !/^[A-Za-z0-9]{1,10}$/.test(room)) { err("ใส่เลขห้อง (ตัวอักษร/ตัวเลข ไม่เกิน 10 ตัว)"); $("review-room").focus(); return; }
    if (keep && !t) { err("เลือกชนิดมิเตอร์ น้ำ หรือ ไฟ"); return; }
    busy = true; err("");
    const lid = cur.local_id;      // ต้องจำไว้ก่อน await: เหตุการณ์ "decided" ทาง WebSocket อาจมาถึงก่อน response แล้วเลื่อน cur ไปรูปถัดไปแล้ว
    try {
      const r = await fetch(`/api/pending/${lid}`, { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify(keep ? { keep: true, room_id: room, meter_type: t.value } : { keep: false }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok && d.reason !== "not_pending") { err(d.reason === "bad_room" ? "เลขห้องไม่ถูกต้อง" : "บันทึกไม่ได้: " + (d.reason || r.status)); return; }
      if (keep) { last = { room, type: t.value }; try { localStorage.setItem("mrc.review.last", JSON.stringify(last)); } catch (e) {} }
      drop(lid);
      if (cur && cur.local_id === lid) { const nx = next(); if (nx) open(nx); } else paintBadge();
    } catch (e) {
      err("ติดต่อ Pi ไม่ได้ — รูปยังค้างอยู่บน Pi กดใหม่ได้เมื่อเชื่อมต่อกลับมา");
    } finally { busy = false; }
  }

  $("review-keep").onclick = () => decide(true);
  $("review-discard").onclick = () => {
    if (!armT) { $("review-discard").classList.add("armed"); $("review-discard").textContent = "แตะอีกครั้งเพื่อลบถาวร"; armT = setTimeout(disarm, 3000); return; }
    disarm(); decide(false);
  };
  $("review-later").onclick = close;
  badge.onclick = () => { if (queue.length) open(queue[0]); };
  $("review-room").addEventListener("keydown", (e) => { if (e.key === "Enter") decide(true); });

  async function refresh() {
    try {
      const d = await (await fetch("/api/pending", { cache: "no-store" })).json();
      queue = d.items || [];
      $("review-rooms").innerHTML = (d.rooms || []).map((r) => `<option value="${String(r).replace(/[^A-Za-z0-9]/g, "")}">`).join("");
      if (cur && !queue.some((q) => q.local_id === cur.local_id)) close();
      paintBadge();
    } catch (e) {}
  }

  window.addEventListener("mrc:ev", (e) => {
    const ev = e.detail || {};
    // ต่อ WebSocket ใหม่ = ดึงรายการค้างจาก Pi อีกรอบ · hello เล่นเหตุการณ์เก่าซ้ำ (drive.js) → ห้ามเปิดป๊อปอัพจากของเก่า
    if (ev.t === "hello") { replaying = true; setTimeout(() => { replaying = false; }, 0); refresh(); }
    else if (ev.t === "reading" && ev.pending && ev.local_id && !replaying) {
      drop(ev.local_id);
      const item = { local_id: ev.local_id, captured_at: ev.captured_at, value: ev.value, confidence: ev.confidence, crop_url: ev.crop_url };
      queue.unshift(item);
      if (box.hidden) open(item); else paintBadge();                             // กำลังตัดสินรูปก่อนหน้าอยู่ → ไม่แย่งจอ ต่อคิวไว้
    } else if (ev.t === "decided") {                                             // ตัดสินจากเครื่องอื่น/แท็บอื่น
      drop(ev.local_id);
      if (cur && cur.local_id === ev.local_id) { const nx = next(); if (nx) open(nx); } else paintBadge();
    }
  });
  refresh();
})();
