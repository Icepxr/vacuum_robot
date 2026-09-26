// Pure view-state helpers. This latch protects this browser only, not other controllers.
(function (scope) {
  const finite = (v) => typeof v === "number" && Number.isFinite(v);
  function airOverview(a, { waiting = false, disconnected = false } = {}) {
    const values = { co2: "—", tvoc: "—", aqi: "—", temp: "—", rh: "—" };
    if (disconnected) return { status: "ลิงก์หลุด", tone: "offline", values };
    if (waiting) return { status: "รอข้อมูล", tone: "offline", values };
    if (!a) return { status: "ปิดเซนเซอร์", tone: "offline", values };
    if (!a.available) return { status: "ไม่พบเซนเซอร์", tone: "offline", values };
    if (a.error) return { status: "อ่านค่าไม่ได้", tone: "bad", values };
    if (finite(a.temp_c)) values.temp = a.temp_c.toFixed(1);
    if (finite(a.rh_pct)) values.rh = a.rh_pct.toFixed(0);
    if (a.validity !== 3) {
      if (finite(a.eco2_ppm)) values.co2 = a.eco2_ppm.toFixed(0);
      if (finite(a.tvoc_ppb)) values.tvoc = a.tvoc_ppb.toFixed(0);
      if (finite(a.aqi) && a.aqi >= 1 && a.aqi <= 5) values.aqi = String(a.aqi);
    }
    if (a.validity === 3) return { status: "ค่าผิดปกติ", tone: "bad", values };
    if (a.validity === 1) return { status: "กำลังอุ่น", tone: "warm", values };
    if (a.validity === 2) return { status: "ค่ายังไม่นิ่ง", tone: "warm", values };
    const labels = { excellent: "ดีมาก", good: "ดี", fair: "พอใช้", poor: "แย่", bad: "แย่มาก" };
    if (a.validity !== 0 || [values.co2, values.tvoc, values.aqi].includes("—") || !labels[a.rating]) return { status: "ข้อมูลบางส่วน", tone: "offline", values };
    return { status: labels[a.rating], tone: a.rating === "bad" ? "bad" : a.rating === "poor" ? "warn" : "good", values };
  }
  class EmergencyLatch {
    constructor(state = "") { this.active = state === "active"; this.needsNeutral = this.active || state === "neutral"; }
    get state() { return this.active ? "active" : this.needsNeutral ? "neutral" : ""; }
    trip() { this.active = true; this.needsNeutral = true; }
    acknowledge() { this.active = false; }
    allowsCommand(type) {
      if (this.active) return ["estop", "status", "ping"].includes(type);
      return !(this.needsNeutral && type === "drive");
    }
    observeInput(x, y, deadzone) {
      if (this.active || !finite(x) || !finite(y)) return false;
      if (this.needsNeutral) {
        if (Math.hypot(x, y) <= deadzone) this.needsNeutral = false;
        return false; // Always leave one idle frame before accepting fresh input.
      }
      return true;
    }
  }
  const api = { airOverview, EmergencyLatch };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else scope.ARIAViewState = api;
})(typeof window !== "undefined" ? window : globalThis);
