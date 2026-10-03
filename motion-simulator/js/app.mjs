import { DEFAULTS, clamp, deriveGeometry, emptyPose, simulateDuration, stepPose, wheelRpmToMotion } from './kinematics.mjs';

const $ = (id) => document.getElementById(id);
const controls = {
  wheelDiameterMm: $('wheel-diameter'), wheelWidthMm: $('wheel-width'), trackWidthMm: $('track-width'),
  countsPerRev: $('counts-per-rev'), ratedRpm: $('rated-rpm'), duration: $('duration'),
  leftRpm: $('left-rpm'), rightRpm: $('right-rpm'),
};
const simulationView = $('simulation');
let pose = emptyPose();
let history = [{ xM: 0, yM: 0 }];
let running = false;
let simulatedTime = 0;
let lastFrame = performance.now();
let accumulator = 0;
const fixedStep = 1 / 120;

function getParams() {
  return {
    wheelDiameterMm: Number(controls.wheelDiameterMm.value),
    wheelWidthMm: Number(controls.wheelWidthMm.value),
    trackWidthMm: Number(controls.trackWidthMm.value),
    countsPerRev: Number(controls.countsPerRev.value),
    ratedRpm: Number(controls.ratedRpm.value),
    chassisLengthMm: DEFAULTS.chassisLengthMm,
    chassisWidthMm: DEFAULTS.chassisWidthMm,
  };
}

function syncRangeLimits() {
  const rated = Math.max(1, Number(controls.ratedRpm.value) || DEFAULTS.ratedRpm);
  for (const input of [controls.leftRpm, controls.rightRpm]) {
    input.min = -rated; input.max = rated;
    input.value = clamp(Number(input.value), -rated, rated);
  }
}

function updateReadout() {
  try {
    syncRangeLimits();
    const params = getParams();
    const geometry = deriveGeometry(params);
    const left = Number(controls.leftRpm.value);
    const right = Number(controls.rightRpm.value);
    const motion = wheelRpmToMotion(left, right, params);
    const preview = simulateDuration(left, right, Number(controls.duration.value), params);
    $('validation').textContent = '';
    $('left-rpm-output').value = `${left.toFixed(0)} rpm`;
    $('right-rpm-output').value = `${right.toFixed(0)} rpm`;
    $('linear-speed').textContent = motion.linearMps.toFixed(3);
    $('angular-speed').textContent = motion.angularDegps.toFixed(2);
    $('turn-radius').textContent = Number.isFinite(motion.radiusM) ? motion.radiusM.toFixed(3) : '∞';
    $('distance').textContent = pose.distanceM.toFixed(3);
    $('heading').textContent = (pose.thetaRad * 180 / Math.PI).toFixed(2);
    $('position').textContent = `${pose.xM.toFixed(2)}, ${pose.yM.toFixed(2)}`;
    $('mm-per-count').textContent = `${geometry.mmPerCount.toFixed(5)} mm/count`;
    $('counts-per-degree').textContent = `${geometry.countsPerDegree.toFixed(2)} count/ล้อ`;
    $('rated-speed').textContent = `${geometry.ratedSpeedMps.toFixed(4)} m/s`;
    $('overflow-time').textContent = `${geometry.secondsToInt16Limit.toFixed(2)} s`;
    $('left-counts').textContent = Math.round(pose.leftCounts).toLocaleString('th-TH');
    $('right-counts').textContent = Math.round(pose.rightCounts).toLocaleString('th-TH');
    $('sim-time').textContent = `${simulatedTime.toFixed(2)} s`;
    simulationView.dataset.preview = JSON.stringify({ xM: preview.xM, yM: preview.yM });
  } catch (error) {
    running = false;
    $('validation').textContent = `ตรวจค่าอินพุต: ${error.message}`;
  }
}

function resetSimulation() {
  running = false; pose = emptyPose(); simulatedTime = 0; accumulator = 0;
  history = [{ xM: 0, yM: 0 }]; $('sim-state').textContent = 'พร้อม'; updateReadout(); draw();
}

function setPreset(name) {
  const rpm = Number(controls.ratedRpm.value) || 178;
  const values = {
    forward: [rpm * .56, rpm * .56], left: [rpm * .35, rpm * .75],
    spin: [-rpm * .4, rpm * .4], reverse: [-rpm * .45, -rpm * .45],
  }[name];
  controls.leftRpm.value = Math.round(values[0]); controls.rightRpm.value = Math.round(values[1]); updateReadout(); draw();
}

function worldTransform() {
  const points = history.concat([{ xM: pose.xM, yM: pose.yM }]);
  const farthestPoint = Math.max(...points.map(p => Math.max(Math.abs(p.xM), Math.abs(p.yM))));
  const extent = Math.max(1.25, farthestPoint + .65);
  const scale = 720 / (2 * extent);
  return { scale, cx: 600, cy: 360, extent };
}

function draw() {
  const { scale, cx, cy, extent } = worldTransform();
  const gridM = extent > 5 ? 1 : extent > 2.5 ? .5 : .25;
  $('grid-scale').textContent = `${gridM} m`;
  const grid = $('grid-lines');
  grid.replaceChildren();
  const span = Math.ceil(extent / gridM) * gridM;
  for (let m = -span; m <= span + 1e-9; m += gridM) {
    const x = cx + m * scale, y = cy - m * scale;
    grid.append(svgLine(x, 0, x, 720), svgLine(0, y, 1200, y));
  }
  $('path-line').setAttribute('points', history.map(p => `${cx + p.xM * scale},${cy - p.yM * scale}`).join(' '));
  const robotX = cx + pose.xM * scale;
  const robotY = cy - pose.yM * scale;
  drawRobot(robotX, robotY, pose.thetaRad, scale);
  drawGeometry();
}

function drawGeometry() {
  const p = getParams();
  const motion = wheelRpmToMotion(Number(controls.leftRpm.value), Number(controls.rightRpm.value), p);
  const b = p.trackWidthMm / 1000;
  const turning = Math.abs(motion.angularRadps) > 1e-9;
  const radius = turning ? motion.radiusM : 0;
  // Fit the wheel centres and ICC independently of the trajectory view.
  const angle = pose.thetaRad;
  const forward = [Math.cos(angle), -Math.sin(angle)];
  const leftNormal = [-Math.sin(angle), -Math.cos(angle)];
  const offsets = [-b / 2, b / 2, 0, ...(turning ? [radius] : [])];
  const extent = Math.max(b * 2.3, Math.abs(radius) + b * .9);
  const scale = Math.min(480 / extent, 1000);
  const low = Math.min(...offsets), high = Math.max(...offsets);
  const centreOffset = (low + high) / 2;
  const centre = [550 - leftNormal[0] * centreOffset * scale, 325 - leftNormal[1] * centreOffset * scale];
  const at = offset => [centre[0] + leftNormal[0] * offset * scale, centre[1] + leftNormal[1] * offset * scale];
  const L = at(b / 2), R = at(-b / 2), ICC = at(radius);
  const group = $('geometry-drawing'); group.replaceChildren();
  const add = (tag, attrs, content) => {
    const el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, value);
    if (content !== undefined) el.textContent = content;
    group.append(el); return el;
  };
  const line = (a, z, cls, arrows = false) => add('line', {x1:a[0], y1:a[1], x2:z[0], y2:z[1], class:cls, ...(arrows ? {'marker-start':'url(#geo-arrow)', 'marker-end':'url(#geo-arrow)'} : {})});
  const label = (point, text, cls = 'geo-label') => add('text', {x:point[0],y:point[1],class:cls}, text);
  const shift = (point, distance) => [point[0] + forward[0] * distance, point[1] + forward[1] * distance];
  const dot = point => add('circle',{cx:point[0],cy:point[1],r:5,class:'geo-dot'});
  line([80,570],[230,570],'geo-axis'); line([80,570],[80,435],'geo-axis');
  label([235,577],'x'); label([65,428],'y');
  line(shift(at(low-b*.35),0),shift(at(high+b*.35),0),'geo-guide');
  // B is always the measured wheel-centre spacing, independent of turn radius.
  const dl = shift(L,-90), dr = shift(R,-90);
  line(L,dl,'geo-guide'); line(R,dr,'geo-guide'); line(dl,dr,'geo-dimension',true);
  label(shift(at(0),-125),`B = ${p.trackWidthMm.toFixed(0)} mm`);
  if (turning) {
    const dimC = shift(centre,125), dimI = shift(ICC,125);
    line(centre,dimC,'geo-guide'); line(ICC,dimI,'geo-guide'); line(dimC,dimI,'geo-dimension',true);
    const mid = [(dimC[0]+dimI[0])/2,(dimC[1]+dimI[1])/2];
    label([mid[0]+14,mid[1]-12],`R = ${(radius*1000).toFixed(1)} mm`);
    dot(ICC); label([ICC[0]+12,ICC[1]-15],'ICC');
    add('circle',{cx:ICC[0],cy:ICC[1],r:Math.abs(radius)*scale,class:'geo-orbit'});
  }
  // Wheels aligned with the robot's forward axis.
  for (const [point,name,speed] of [[L,'L',motion.leftMps],[R,'R',motion.rightMps]]) {
    const length = Math.max(62,p.wheelDiameterMm/1000*scale), width = Math.max(29,p.wheelWidthMm/1000*scale);
    add('rect',{x:-length/2,y:-width/2,width:length,height:width,rx:width/2,class:'geo-wheel',transform:`translate(${point[0]} ${point[1]}) rotate(${-angle*180/Math.PI})`});
    dot(point); label([point[0]-8,point[1]-width-10],name,'geo-wheel-label');
    const velocityLength = Math.abs(speed)<1e-9 ? 0 : Math.sign(speed)*(35+Math.abs(speed)/Math.max(.01,deriveGeometry(p).ratedSpeedMps)*130);
    if (velocityLength) line(point,shift(point,velocityLength),'geo-velocity');
    label([point[0]+24,point[1]+38],`v${name} = ${speed.toFixed(3)} m/s`,'geo-speed-label');
  }
  dot(centre); label([centre[0]+12,centre[1]+22],'C');
  line(centre,shift(centre,70),'geo-heading'); label(shift(centre,85),'θ','geo-wheel-label');
  const moving = Math.abs(motion.leftMps)+Math.abs(motion.rightMps)>1e-9;
  $('geo-mode').textContent = !moving ? 'หยุดนิ่ง · ICC ไม่กำหนด' : !turning ? 'วิ่งตรง · ICC อยู่ที่อนันต์' : Math.abs(motion.linearMps)<1e-9 ? 'หมุนอยู่กับที่ · ICC = C' : 'เคลื่อนที่ตามส่วนโค้ง';
  $('geo-radii').textContent = turning ? `Rₗ = ${((radius-b/2)*1000).toFixed(1)} mm · Rᵣ = ${((radius+b/2)*1000).toFixed(1)} mm` : moving ? 'Rₗ, Rᵣ → ∞ เมื่อวิ่งตรง' : 'R ไม่กำหนดเมื่อทั้งสองล้อหยุด';
  const iccX = pose.xM - radius * Math.sin(pose.thetaRad);
  const iccY = pose.yM + radius * Math.cos(pose.thetaRad);
  $('geo-icc').textContent = turning ? `ICC โลก = (${iccX.toFixed(3)}, ${iccY.toFixed(3)}) m · θ = ${(pose.thetaRad*180/Math.PI).toFixed(1)}°` : `θ = ${(pose.thetaRad*180/Math.PI).toFixed(1)}°`;
}

function drawRobot(x, y, theta, scale) {
  const p = getParams(); const length = p.chassisLengthMm / 1000 * scale; const width = p.chassisWidthMm / 1000 * scale;
  const wheelD = p.wheelDiameterMm / 1000 * scale; const wheelW = p.wheelWidthMm / 1000 * scale; const track = p.trackWidthMm / 1000 * scale;
  const robot = $('robot-g');
  robot.setAttribute('transform', `translate(${x} ${y}) rotate(${-theta * 180 / Math.PI})`);
  setRect($('robot-body'), -length / 2, -width / 2, length, width, Math.min(22, width * .2));
  setRect($('wheel-left'), -wheelD / 2, -track / 2 - wheelW / 2, wheelD, wheelW, 3);
  setRect($('wheel-right'), -wheelD / 2, track / 2 - wheelW / 2, wheelD, wheelW, 3);
  $('robot-arrow').setAttribute('transform', `scale(${Math.max(.55, length / 115)})`);
}

function setRect(element, x, y, width, height, radius) {
  for (const [name, value] of Object.entries({ x, y, width, height, rx: radius })) element.setAttribute(name, value);
}

function svgLine(x1, y1, x2, y2) {
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  for (const [name, value] of Object.entries({ x1, y1, x2, y2 })) line.setAttribute(name, value);
  line.setAttribute('class', 'grid-line');
  return line;
}

function animate(now) {
  const frameDt = Math.min(.05, (now - lastFrame) / 1000); lastFrame = now;
  if (running) {
    accumulator += frameDt;
    while (accumulator >= fixedStep) {
      pose = stepPose(pose, Number(controls.leftRpm.value), Number(controls.rightRpm.value), fixedStep, getParams());
      simulatedTime += fixedStep; accumulator -= fixedStep;
      if (history.length === 0 || simulatedTime * 20 >= history.length) history.push({ xM: pose.xM, yM: pose.yM });
      const limit = Number(controls.duration.value);
      if (Number.isFinite(limit) && simulatedTime >= limit) { running = false; $('sim-state').textContent = 'ครบเวลาที่กำหนด'; break; }
    }
    updateReadout(); draw();
  }
  requestAnimationFrame(animate);
}

for (const input of Object.values(controls)) input.addEventListener('input', () => { updateReadout(); draw(); });
document.querySelectorAll('[data-preset]').forEach(button => button.addEventListener('click', () => setPreset(button.dataset.preset)));
$('start').addEventListener('click', () => { if (simulatedTime >= Number(controls.duration.value)) resetSimulation(); running = true; $('sim-state').textContent = 'กำลังจำลอง'; lastFrame = performance.now(); });
$('pause').addEventListener('click', () => { running = false; $('sim-state').textContent = 'หยุดชั่วคราว'; });
$('reset-simulation').addEventListener('click', resetSimulation);
$('reset-parameters').addEventListener('click', () => { controls.wheelDiameterMm.value = DEFAULTS.wheelDiameterMm; controls.wheelWidthMm.value = DEFAULTS.wheelWidthMm; controls.trackWidthMm.value = DEFAULTS.trackWidthMm; controls.countsPerRev.value = DEFAULTS.countsPerRev; controls.ratedRpm.value = DEFAULTS.ratedRpm; controls.duration.value = 5; setPreset('forward'); resetSimulation(); });
window.addEventListener('resize', draw);

class CadPreview {
  constructor(canvasElement) { this.canvas = canvasElement; this.ctx = canvasElement.getContext('2d'); this.meshes = []; this.angle = -.65; this.pitch = .78; this.last = performance.now(); this.drag = null; this.active = false; this.part = null; this.requestId = 0; this.bind(); }
  bind() { this.canvas.addEventListener('pointerdown', e => { this.drag = { x:e.clientX, y:e.clientY }; this.canvas.setPointerCapture(e.pointerId); }); this.canvas.addEventListener('pointermove', e => { if (!this.drag) return; this.angle += (e.clientX-this.drag.x)*.012; this.pitch=clamp(this.pitch+(e.clientY-this.drag.y)*.008,.15,1.35); this.drag={x:e.clientX,y:e.clientY}; }); this.canvas.addEventListener('pointerup',()=>this.drag=null); }
  async load(part) {
    const requestId = ++this.requestId;
    this.active = false;
    try {
      this.meshes = [];
      const filename = part === 'lower' ? 'Robot_lowerpart.stl' : 'Robot_upperpart.stl';
      const response = await fetch(`../05_CAD/${filename}`);
      if (!response.ok) throw new Error(`${response.status} ${filename}`);
      const buffer = await response.arrayBuffer();
      if (requestId !== this.requestId) return;
      this.meshes = [{triangles:parseStl(buffer),color:part === 'lower' ? '#30d5e8' : '#ffb454'}];
      const all=this.meshes.flatMap(m=>m.triangles.flat()); const min=[0,1,2].map(a=>Math.min(...all.map(v=>v[a]))); const max=[0,1,2].map(a=>Math.max(...all.map(v=>v[a]))); this.center=min.map((v,a)=>(v+max[a])/2); this.size=Math.max(...max.map((v,a)=>v-min[a]));
      this.active = true;
      $('cad-status').textContent=`${part === 'lower' ? 'ฐานล่าง' : 'ชั้นบน'} · ${(all.length/3).toLocaleString('th-TH')} triangles`; $('cad-status').className='cad-status ok';
      $('cad-part-note').textContent = `${filename} · ชิ้นส่วนเดี่ยว ไม่รวมตำแหน่งประกอบ · ลากเพื่อหมุนดู`;
      this.last = performance.now(); requestAnimationFrame(t=>this.draw(t, requestId));
    } catch (error) { $('cad-status').textContent='เปิดผ่าน web server เพื่อโหลด STL'; $('cad-status').className='cad-status error'; this.drawEmpty(); }
  }
  draw(t, requestId) { if (!this.active || requestId !== this.requestId) return; const dt=(t-this.last)/1000;this.last=t;if(!this.drag)this.angle+=dt*.18;const rect=this.canvas.getBoundingClientRect(),dpr=Math.min(2,devicePixelRatio||1);this.canvas.width=Math.round(rect.width*dpr);this.canvas.height=Math.round(rect.height*dpr);this.ctx.clearRect(0,0,this.canvas.width,this.canvas.height);const projected=[];for(const mesh of this.meshes){for(const tri of mesh.triangles){const pts=tri.map(v=>project(v,this.center,this.angle,this.pitch,this.size,this.canvas));const depth=pts.reduce((s,p)=>s+p.z,0)/3;projected.push({pts,depth,color:mesh.color})}}projected.sort((a,b)=>a.depth-b.depth);for(const face of projected){const c=this.ctx;c.beginPath();c.moveTo(face.pts[0].x,face.pts[0].y);c.lineTo(face.pts[1].x,face.pts[1].y);c.lineTo(face.pts[2].x,face.pts[2].y);c.closePath();c.globalAlpha=.16;c.fillStyle=face.color;c.fill();c.globalAlpha=.35;c.strokeStyle=face.color;c.lineWidth=.45*dpr;c.stroke()}this.ctx.globalAlpha=1;requestAnimationFrame(n=>this.draw(n, requestId)); }
  drawEmpty(){const c=this.ctx;c.fillStyle='#8da4af';c.textAlign='center';c.font='12px Anuphan';c.fillText('CAD preview ต้องเปิดผ่าน http://localhost',this.canvas.width/2,this.canvas.height/2);}
}

function parseStl(buffer) { const view=new DataView(buffer);const count=view.getUint32(80,true);const triangles=[];for(let i=0;i<count;i++){const tri=[];const start=84+i*50+12;for(let v=0;v<3;v++)tri.push([view.getFloat32(start+v*12,true),view.getFloat32(start+v*12+4,true),view.getFloat32(start+v*12+8,true)]);triangles.push(tri)}return triangles; }
function project(v,center,yaw,pitch,size,canvasElement){let x=v[0]-center[0],y=v[1]-center[1],z=v[2]-center[2];const cy=Math.cos(yaw),sy=Math.sin(yaw);const x1=x*cy-y*sy,y1=x*sy+y*cy;const cp=Math.cos(pitch),sp=Math.sin(pitch);const y2=y1*cp-z*sp,z2=y1*sp+z*cp;const scale=Math.min(canvasElement.width,canvasElement.height)*.72/size;return{x:canvasElement.width/2+x1*scale,y:canvasElement.height/2-y2*scale,z:z2};}

const cadPreview = new CadPreview($('cad-view'));
document.querySelectorAll('[data-cad-mode]').forEach(button => button.addEventListener('click', () => {
  const mode = button.dataset.cadMode;
  cadPreview.active = false; cadPreview.requestId++;
  $('cad-assembly').hidden = mode !== 'assembly';
  $('cad-photos').hidden = mode !== 'photos';
  $('cad-part').hidden = mode !== 'lower' && mode !== 'upper';
  document.querySelectorAll('[data-cad-mode]').forEach(item => item.setAttribute('aria-pressed', item === button ? 'true' : 'false'));
  if (mode === 'lower' || mode === 'upper') cadPreview.load(mode);
  else { $('cad-status').textContent = mode === 'assembly' ? 'Assembly จาก Fusion' : 'ภาพหุ่นจริงจากผู้ใช้'; $('cad-status').className = 'cad-status ok'; }
}));
updateReadout(); draw(); requestAnimationFrame(animate);
