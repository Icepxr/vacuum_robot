// วอลเปเปอร์ผ้าซาตินโทนม่วง/โลหะเหลว (WebGL) หลังหน้าเข้าสู่ระบบ · ไหลเองอย่างเดียว ไม่ตามเมาส์ (ผู้ใช้สั่ง 29 ก.ย.)
// พื้นผิว = noise บิดซ้อน (domain warping) → ความสูง → normal (finite difference) → แสงกระจาย + เงาคม + รุ้งอ่อนที่ขอบรอยพับ
// เรนเดอร์ความละเอียดต่ำแล้วขยาย (ผิวนุ่มอยู่แล้ว) · rAF หยุดเองตอนแท็บถูกซ่อน · ไม่มี WebGL = ไล่สี CSS นิ่ง (.liquid-fallback) · ลดการเคลื่อนไหว = ภาพนิ่ง
const VERT = `attribute vec2 a; void main(){ gl_Position = vec4(a, 0.0, 1.0); }`;
const FRAG = `
precision highp float;
uniform vec2 uRes; uniform float uTime; uniform float uTone;   // uTone 0 = หน้าเข้าสู่ระบบ (สว่าง) · 1 = หลังบ้าน (มืด)
float hash(vec2 p){ p = fract(p * vec2(123.34, 456.21)); p += dot(p, p + 45.32); return fract(p.x * p.y); }
float noise(vec2 p){
  vec2 i = floor(p), f = fract(p); vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);   // quintic = ผิวลื่นไม่มีรอยต่อ
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x), mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}
float fbm(vec2 p){ float v = 0.0, a = 0.55; mat2 r = mat2(0.8, -0.6, 0.6, 0.8); for (int i = 0; i < 3; i++){ v += a * noise(p); p = r * p * 1.9; a *= 0.45; } return v; }
float height(vec2 p, float t){
  vec2 q = vec2(fbm(p + vec2(0.0, t)), fbm(p + vec2(5.2, 1.3) - t));
  vec2 r = vec2(fbm(p + 2.1 * q + vec2(1.7, 9.2) + 0.7 * t), fbm(p + 2.1 * q + vec2(8.3, 2.8) - 0.6 * t));
  return smoothstep(0.12, 0.88, fbm(p + 2.4 * r));                  // ดึงคอนทราสต์ = สันพับชัดขึ้น
}
vec3 pal(float t){ return 0.5 + 0.5 * cos(6.28318 * (t + vec3(0.0, 0.33, 0.67))); }
void main(){
  vec2 uv = gl_FragCoord.xy / uRes;
  float asp = uRes.x / uRes.y;
  float sc = 1.15;                                                      // รอยพับใหญ่ (ค่าน้อย = พับน้อยลง ใหญ่ขึ้น)
  vec2 p = vec2(uv.x * asp, uv.y) * sc;
  float t = uTime * 0.035;
  float e = 0.0035;
  float h  = height(p, t);
  float hx = height(p + vec2(e, 0.0), t);
  float hy = height(p + vec2(0.0, e), t);
  vec2 g = vec2(hx - h, hy - h) / e;
  vec3 n = normalize(vec3(-g * 0.55, 1.0));                            // ความนูนนุ่มแบบผ้าซาติน
  vec3 L = normalize(vec3(-0.5, 0.6, 0.62));
  float diff = clamp(dot(n, L), 0.0, 1.0);
  vec3 R = reflect(-L, n);
  float spec = pow(max(R.z, 0.0), 60.0);                                // เส้นเงาคม
  float sheen = pow(max(R.z, 0.0), 8.0);                                // เงาเนื้อผ้านุ่ม
  float fres = pow(1.0 - clamp(n.z, 0.0, 1.0), 2.2);
  vec3 deep = mix(vec3(0.40, 0.26, 0.66), vec3(0.07, 0.035, 0.16), uTone);   // ม่วงเข้ม → ลาเวนเดอร์ → ขาวอมม่วง (สว่าง)
  vec3 mid  = mix(vec3(0.66, 0.53, 0.90), vec3(0.22, 0.12, 0.44), uTone);   // โทนมืด: ไฮไลต์ถูกกดให้ตัวอักษรขาวบนพื้นยังอ่านได้ (≥ 4.5:1)
  vec3 hi   = mix(vec3(0.92, 0.87, 1.0),  vec3(0.38, 0.28, 0.66), uTone);   // กดไฮไลต์ลง → กระจกใสบนพื้นนี้ตัวอักษรยัง ≥ 5.2:1
  vec3 col = mix(deep, mid, smoothstep(0.15, 0.75, diff));
  col = mix(col, hi, smoothstep(0.7, 1.0, diff) * 0.7);
  // รุ้งเฉพาะขอบรอยพับที่ชันมาก (เหมือนมุกบนผ้า) · อ่อน
  vec3 irid = mix(vec3(1.0), pal(h * 2.2 + n.x * 0.9 + 0.2), 0.55) * vec3(0.92, 0.98, 1.0);
  col = mix(col, irid, (smoothstep(0.01, 0.2, fres) * 0.45 + spec * 0.15) * (1.0 - 0.55 * uTone));
  col += (spec * 0.85 + sheen * 0.14 * vec3(0.96, 0.94, 1.0)) * (1.0 - 0.6 * uTone);
  col *= 0.95 + 0.05 * smoothstep(1.3, 0.2, length(uv - 0.5));
  gl_FragColor = vec4(col, 1.0);
}`;

// แต่ละ canvas = อินสแตนซ์ของตัวเอง (ตอนเปลี่ยนหน้า login → หลังบ้าน วอลเปเปอร์สองโทนต้องทำงานพร้อมกันเพื่อ crossfade)
// ค่าเริ่ม = หน้าเข้าสู่ระบบ · หลังบ้านส่ง { tone: 1, scale: 0.35, fps: 30 } (เปิดตลอดระหว่างทำงาน → ลดภาระลงอีก)
const reduced = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

export function createBackdrop(canvas, o = {}) {
  const opts = { tone: 0, scale: 0.5, fps: 60, ...o };
  const noop = { stop() {} };
  if (!canvas) return noop;
  const gl = canvas.getContext('webgl', { antialias: false, alpha: false, powerPreference: 'low-power', preserveDrawingBuffer: false });
  if (!gl) { canvas.classList.add('liquid-fallback'); return noop; }
  const compile = (type, src) => {
    const sh = gl.createShader(type); gl.shaderSource(sh, src); gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
    return sh;
  };
  let prog;
  try {
    prog = gl.createProgram();
    gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
    gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
  } catch (e) { canvas.classList.add('liquid-fallback'); return noop; }
  gl.useProgram(prog);
  const buf = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, buf);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);   // สามเหลี่ยมเดียวคลุมจอ
  const a = gl.getAttribLocation(prog, 'a'); gl.enableVertexAttribArray(a); gl.vertexAttribPointer(a, 2, gl.FLOAT, false, 0, 0);
  const loc = { res: gl.getUniformLocation(prog, 'uRes'), time: gl.getUniformLocation(prog, 'uTime'), tone: gl.getUniformLocation(prog, 'uTone') };
  let raf = 0, lastDraw = 0, alive = true;
  const t0 = performance.now();

  function size() {
    const d = Math.min(devicePixelRatio || 1, 1.5);
    const w = Math.max(1, Math.round(canvas.clientWidth * opts.scale * d));
    const h = Math.max(1, Math.round(canvas.clientHeight * opts.scale * d));
    if (canvas.width !== w || canvas.height !== h) { canvas.width = w; canvas.height = h; gl.viewport(0, 0, w, h); }
  }
  function render(ms) {
    if (!alive) return;
    if (!reduced() && ms - lastDraw < 1000 / opts.fps - 2) { raf = requestAnimationFrame(render); return; }   // จำกัดเฟรม
    lastDraw = ms;
    size();
    gl.uniform2f(loc.res, canvas.width, canvas.height);
    gl.uniform1f(loc.time, reduced() ? 8 : (ms - t0) / 1000 + 8);
    gl.uniform1f(loc.tone, opts.tone);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
    if (!reduced()) raf = requestAnimationFrame(render);
  }
  // ลดการเคลื่อนไหว: วาดภาพนิ่งครั้งเดียว → ต้องวาดใหม่เมื่อขนาดจอเปลี่ยน
  const onResize = () => { if (reduced()) raf = requestAnimationFrame(render); };
  addEventListener('resize', onResize);
  raf = requestAnimationFrame(render);
  return {
    stop() {
      alive = false; cancelAnimationFrame(raf); removeEventListener('resize', onResize);
      gl.getExtension('WEBGL_lose_context')?.loseContext();   // คืนหน่วยความจำ GPU
    },
  };
}
