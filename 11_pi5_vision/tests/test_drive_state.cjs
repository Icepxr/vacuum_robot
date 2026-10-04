// Run with: node 11_pi5_vision/tests/test_drive_state.cjs (no child-process permission needed)
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { airOverview, EmergencyLatch } = require('../src/static/drive-state.js');
const sample = { available: true, validity: 0, rating: 'good', eco2_ppm: 700, tvoc_ppb: 100, aqi: 2, temp_c: 27.4, rh_pct: 58 };

test('air overview formats all five metrics, without converting eCO2 to CO2', () => {
  assert.deepEqual(airOverview(sample), { status: 'ดี', tone: 'good', values: { co2: '700', tvoc: '100', aqi: '2', temp: '27.4', rh: '58' } });
});
test('missing, disabled, waiting and disconnected sensors remain explicit', () => {
  for (const [air, options, status] of [[null, {}, 'ปิดเซนเซอร์'], [{ available: false }, {}, 'ไม่พบเซนเซอร์'], [null, { waiting: true }, 'รอข้อมูล'], [sample, { disconnected: true }, 'ลิงก์หลุด']]) {
    const out = airOverview(air, options); assert.equal(out.status, status); assert.equal(out.tone, 'offline');
    assert.ok(Object.values(out.values).every(v => v === '—'));
  }
});
test('warming-up and initial readings are never labelled good', () => {
  for (const validity of [1, 2]) assert.equal(airOverview({ ...sample, validity }).tone, 'warm');
});
test('invalid gas readings are hidden while valid temperature is retained', () => {
  const out = airOverview({ ...sample, validity: 3 }); assert.equal(out.tone, 'bad');
  assert.equal(out.values.co2, '—'); assert.equal(out.values.tvoc, '—'); assert.equal(out.values.aqi, '—'); assert.equal(out.values.temp, '27.4');
});
test('partial / nonnumeric data does not invent readings or good quality', () => {
  const out = airOverview({ available: true, temp_c: 0, rh_pct: 0, eco2_ppm: '<script>', aqi: 7 });
  assert.equal(out.status, 'ข้อมูลบางส่วน'); assert.equal(out.values.temp, '0.0'); assert.equal(out.values.rh, '0'); assert.equal(out.values.co2, '—'); assert.equal(out.values.aqi, '—');
  assert.equal(airOverview({ ...sample, tvoc_ppb: null }).status, 'ข้อมูลบางส่วน');
  assert.equal(airOverview({ ...sample, aqi: null }).status, 'ข้อมูลบางส่วน');
});
test('poor and bad ratings are distinguished', () => {
  assert.equal(airOverview({ ...sample, rating: 'poor' }).tone, 'warn');
  assert.equal(airOverview({ ...sample, rating: 'bad' }).tone, 'bad');
});
test('a sensor read error clears old readings', () => {
  const out = airOverview({ ...sample, error: 'I2C read failed' }); assert.equal(out.status, 'อ่านค่าไม่ได้');
  assert.ok(Object.values(out.values).every(v => v === '—'));
});
test('emergency latch gates motion, cleaning, camera and queued commands', () => {
  const latch = new EmergencyLatch(); latch.trip();
  for (const command of ['drive', 'release', 'clean', 'capture', 'cam', 'm', 'x', 'limits']) assert.equal(latch.allowsCommand(command), false);
  assert.equal(latch.allowsCommand('estop'), true); assert.equal(latch.allowsCommand('status'), true);
  assert.equal(latch.observeInput(0, 0, .12), false); assert.equal(latch.state, 'active');
});
test('acknowledgement does not resume a held gamepad; neutral then fresh input required', () => {
  const latch = new EmergencyLatch(); latch.trip(); latch.acknowledge();
  assert.equal(latch.observeInput(1, 0, .12), false); assert.equal(latch.allowsCommand('drive'), false);
  assert.equal(latch.observeInput(0, 0, .12), false); assert.equal(latch.state, '');
  assert.equal(latch.observeInput(1, 0, .12), true);
});
test('active and waiting-for-neutral states can survive refresh', () => {
  for (const state of ['active', 'neutral']) assert.equal(new EmergencyLatch(state).state, state);
  assert.equal(new EmergencyLatch('active').observeInput(1, 1, .12), false);
  assert.equal(new EmergencyLatch('neutral').observeInput(1, 1, .12), false);
});

// Run the actual browser script against a minimal DOM and WebSocket double.
// Nothing connects to a Pi or sends commands outside this test process.
function browserHarness(savedStop = '', savedCfg = null) {
  const handlers = {}, intervals = [], sent = [], nodes = new Map(), storage = new Map();
  if (savedStop) storage.set('aria.drive.stop', savedStop);
  const document = { activeElement: null, hidden: false };
  class Element {
    constructor(id = '') {
      this.id = id; this.hidden = false; this.dataset = {}; this.children = []; this.style = { setProperty() {} };
      const classes = new Set(); this.classList = { add: (...a) => a.forEach(v => classes.add(v)), remove: (...a) => a.forEach(v => classes.delete(v)), toggle: (v, on) => on ? classes.add(v) : classes.delete(v) };
      this.listeners = {}; this.clientWidth = 160; this.parentElement = { className: '', querySelector: () => null };
    }
    addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
    querySelector() { return new Element(); }
    querySelectorAll() { return []; }
    setAttribute() {} matches() { return false; } closest() { return null; }
    focus() { document.activeElement = this; }
    prepend(e) { this.children.unshift(e); }
    setPointerCapture() {}
  }
  const html = fs.readFileSync(path.join(__dirname, '../src/static/drive.html'), 'utf8');
  for (const [, id] of html.matchAll(/\bid="([^"]+)"/g)) nodes.set(id, new Element(id));
  nodes.get('sheet').hidden = true; nodes.get('emergency-screen').hidden = true;
  document.documentElement = new Element(); document.getElementById = id => nodes.get(id);
  document.querySelectorAll = () => []; document.querySelector = () => new Element(); document.createElement = () => new Element(); document.addEventListener = () => {};
  let gamepad = null, socket;
  const window = { ARIAViewState: { airOverview, EmergencyLatch }, addEventListener: (name, fn) => (handlers[name] ||= []).push(fn) };
  const context = { document, window, navigator: { getGamepads: () => gamepad ? [gamepad] : [] },
    WebSocket: class { constructor() { socket = this; this.readyState = 1; } send(json) { sent.push(JSON.parse(json)); } },
    location: { protocol: 'http:', host: 'test.invalid' },
    localStorage: { getItem: () => savedCfg && JSON.stringify(savedCfg), setItem: (k, v) => { savedCfg = JSON.parse(v); } }, sessionStorage: { getItem: k => storage.get(k), setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
    setInterval: (fn, ms) => { intervals.push({ fn, ms }); return intervals.length; }, clearInterval() {}, setTimeout: () => 0, clearTimeout() {}, requestAnimationFrame: fn => fn(),
    performance: { now: (() => { let time = 0; return () => time += 100; })() },
    fetch: () => Promise.resolve({ json: () => Promise.resolve(null) }), console };
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../src/static/drive.js'), 'utf8'), context);
  socket.onopen();
  const pump = intervals.find(i => i.ms === 100).fn;
  return { nodes, sent, pump, socket, storage, config: () => savedCfg,
    key: key => handlers.keydown.forEach(fn => fn({ key, target: new Element(), repeat: false, preventDefault() {} })),
    gamepad: (axes, stop = false) => { gamepad = { axes, buttons: Array.from({ length: 8 }, (_, i) => ({ pressed: i === 1 && stop, value: 0 })) }; } };
}
test('actual script clears held keyboard input and blocks all new drive frames after E-stop', () => {
  const h = browserHarness(); h.key('w'); h.pump(); assert.ok(h.sent.some(c => c.t === 'drive'));
  h.nodes.get('estop').onclick(); const stopIndex = h.sent.length;
  h.key('w'); h.pump(); h.pump();
  assert.equal(h.sent[stopIndex - 1].t, 'estop'); assert.ok(!h.sent.slice(stopIndex).some(c => c.t === 'drive'));
  assert.equal(h.nodes.get('cockpit').inert, true); assert.equal(h.nodes.get('emergency-screen').hidden, false);
  h.nodes.get('emergency-ack').onclick(); h.pump();
  assert.ok(!h.sent.slice(stopIndex).some(c => c.t === 'drive'));
  h.key('w'); h.pump(); assert.equal(h.sent.at(-1).t, 'drive');
});
test('actual script cannot emit drive on the same pump as gamepad E-stop or on held-stick acknowledgement', () => {
  const h = browserHarness(); h.gamepad([0, -1], true); h.pump();
  assert.equal(h.sent.at(-1).t, 'estop'); assert.ok(!h.sent.some(c => c.t === 'drive'));
  h.gamepad([0, -1]); h.nodes.get('emergency-ack').onclick(); h.pump(); h.pump();
  assert.ok(!h.sent.some(c => c.t === 'drive'));
  h.gamepad([0, 0]); h.pump(); h.gamepad([0, -1]); h.pump(); assert.equal(h.sent.at(-1).t, 'drive');
});
test('actual script restores emergency screen and retries only E-stop when websocket connects', () => {
  const h = browserHarness('active'); assert.equal(h.nodes.get('emergency-screen').hidden, false);
  assert.equal(h.nodes.get('cockpit').inert, true); assert.equal(h.sent.at(-1).t, 'estop'); h.key('w'); h.pump();
  assert.ok(!h.sent.some(c => c.t === 'drive'));
});
test('actual sys event updates all air HUD metrics; disconnect removes stale values', () => {
  const h = browserHarness(); h.socket.onmessage({ data: JSON.stringify({ t: 'sys', air: sample, cam_ok: false, link: null, cleaning: {}, drive: {} }) });
  assert.equal(h.nodes.get('air-hud-co2').textContent, '700'); assert.equal(h.nodes.get('air-hud-tvoc').textContent, '100');
  assert.equal(h.nodes.get('air-hud-aqi').textContent, '2'); assert.equal(h.nodes.get('air-hud-temp').textContent, '27.4'); assert.equal(h.nodes.get('air-hud-rh').textContent, '58');
  h.socket.onclose(); assert.equal(h.nodes.get('air-hud-co2').textContent, '—'); assert.equal(h.nodes.get('air-hud-state').textContent, 'ลิงก์หลุด');
  assert.equal(h.nodes.get('air-state').textContent, 'ลิงก์หลุด'); assert.equal(h.nodes.get('a-co2').textContent, '—'); assert.equal(h.nodes.get('a-rating').textContent, '');
});

test('merged UI preserves C43/C44 calibration and keyboard power presets', () => {
  const h = browserHarness('', { calVer: 2, vMax: 300, wMax: 3000, turnGain: 2000, maxPct: 25 });
  h.key('1'); assert.equal(h.config().calVer, 6); assert.equal(h.config().rampMs, 0); assert.equal(h.config().turnGain, 6231);
  assert.equal(h.config().spinMinPct, 70); assert.equal(h.config().maxPct, 50);
  assert.equal(h.config().wMax, 3000); // Retain a saved ceiling without destructively clamping turnGain.
  h.key('2'); assert.equal(h.config().maxPct, 75); h.key('3'); assert.equal(h.config().maxPct, 100);
});

test('merged HTML keeps unique IDs and exposes the latest rotation setting', () => {
  const html = fs.readFileSync(path.join(__dirname, '../src/static/drive.html'), 'utf8');
  const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map(m => m[1]);
  assert.equal(new Set(ids).size, ids.length); assert.match(html, /data-cfg="spinMinPct"/);
  assert.doesNotMatch(html, /data-pct="25"|<<<<<<<|>>>>>>>/);
});
