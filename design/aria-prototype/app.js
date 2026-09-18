// Standalone ARIA design prototype. All data is fictional and stays in memory.
const rooms = [
  {id:"101",tenant:"วราภรณ์ ใจดี",email:"waraporn@example.com",rent:3500,water:{prev:1231,ocr:1244,confirmed:1244,confidence:.97},electric:{prev:3502,ocr:3611,confirmed:3611,confidence:.96}},
  {id:"102",tenant:"ศักดิ์ชัย แสนสุข",email:"sakchai@example.com",rent:3700,water:{prev:987,ocr:998,confirmed:998,confidence:.98},electric:{prev:2140,ocr:2233,confirmed:2233,confidence:.95}},
  {id:"103",tenant:"ธนพร พรมมา",email:"thanaporn@example.com",rent:3600,water:{prev:1518,ocr:1532,confirmed:1532,confidence:.95},electric:{prev:2901,ocr:2977,confirmed:null,confidence:.94}},
  {id:"104",tenant:"นิภาพร สุขใจ",email:"nipaporn@example.com",rent:3400,water:{prev:1192,ocr:1205,confirmed:null,confidence:.91},electric:{prev:3271,ocr:3340,confirmed:null,confidence:.89}},
  {id:"105",tenant:"กิตติพงษ์ รัตนวงศ์",email:"kittipong@example.com",rent:3800,water:{prev:1402,ocr:1477,confirmed:null,confidence:.41},electric:{prev:5012,ocr:5096,confirmed:5096,confidence:.96}},
  {id:"106",tenant:"",email:"",rent:0,vacant:true,water:{prev:802,ocr:811,confirmed:811,confidence:.93},electric:{prev:1320,ocr:1352,confirmed:1352,confidence:.94}},
  {id:"107",tenant:"พิมพ์ชนก วงศ์ดี",email:"pimchanok@example.com",rent:3500,water:{prev:1105,ocr:1117,confirmed:1117,confidence:.96},electric:{prev:4521,ocr:4602,confirmed:4602,confidence:.97}},
  {id:"108",tenant:"นรินทร์ คำมา",email:"narin@example.com",rent:3900,water:{prev:1351,ocr:1362,confirmed:1362,confidence:.94},electric:{prev:3204,ocr:3184,confirmed:null,confidence:.83}},
  {id:"109",tenant:"รัชนี แก้วตา",email:"ratchanee@example.com",rent:3500,water:{prev:890,ocr:null,confirmed:null,confidence:null},electric:{prev:2750,ocr:null,confirmed:null,confidence:null}},
  {id:"110",tenant:"สุรเชษฐ์ จันทร์ดี",email:"",rent:3300,water:{prev:1120,ocr:1133,confirmed:1133,confidence:.95},electric:{prev:2876,ocr:2950,confirmed:2950,confidence:.97}}
];
const state={page:"home",selectedReview:null,selectedRoom:"101",billFilter:"all",includeRent:false,approved:new Map(),sent:new Set()};
const rate={water:18,electric:8};
const baht=n=>"฿"+new Intl.NumberFormat("en-US",{maximumFractionDigits:2}).format(n);
const num=n=>n==null?"—":new Intl.NumberFormat("en-US",{maximumFractionDigits:3}).format(n);
const esc=s=>String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]));
const roomById=id=>rooms.find(r=>r.id===id);
const readingKey=(room,type)=>`${room.id}:${type}`;
const readingName=type=>type==="water"?"น้ำ":"ไฟ";
const allReadings=()=>rooms.flatMap(room=>["water","electric"].map(type=>({room,type,...room[type]})));
const needsReview=r=>r.ocr!=null&&r.confirmed==null&&!r.rejected;
const severity=r=>r.ocr<r.prev?0:r.confidence<.7?1:2;
const reviewQueue=()=>allReadings().filter(needsReview).sort((a,b)=>severity(a)-severity(b)||a.room.id.localeCompare(b.room.id));
const hasPair=room=>room.water.confirmed!=null&&room.electric.confirmed!=null;
const capturedRoom=room=>room.water.ocr!=null&&room.electric.ocr!=null;
const roomStatus=room=>{
  if(room.vacant)return {text:"ห้องว่าง",tone:"purple"};
  if(!capturedRoom(room))return {text:"ยังไม่อ่านครบ",tone:"warn"};
  if(room.water.rejected||room.electric.rejected)return {text:"รอถ่ายใหม่",tone:"bad"};
  if(!hasPair(room))return {text:"รอยืนยันค่า",tone:"warn"};
  if(!room.email)return {text:"ไม่มีอีเมล",tone:"bad"};
  if(state.sent.has(room.id))return {text:"ส่งบิลแล้ว",tone:"good"};
  return {text:"พร้อมตรวจบิล",tone:"good"};
};
const status=(text,tone="")=>`<span class="status ${tone}">${esc(text)}</span>`;
const readingDisplay=(reading,type)=>reading.ocr==null?`<span class="muted">ยังไม่อ่าน</span>`:`<span class="meter-mini ${type}"><span class="type">${type==="water"?"◈":"ϟ"}</span><span>${num(reading.prev)}</span><span class="arrow">→</span><strong>${num(reading.confirmed??reading.ocr)}</strong></span>`;
const liveInvoice=room=>{
  if(room.vacant||!hasPair(room))return null;
  const waterUnits=room.water.confirmed-room.water.prev;
  const electricUnits=room.electric.confirmed-room.electric.prev;
  if(waterUnits<0||electricUnits<0)return null;
  const water=waterUnits*rate.water,electric=electricUnits*rate.electric;
  const rent=state.includeRent?room.rent:0;
  return {waterUnits,electricUnits,water,electric,rent,total:water+electric+rent,includeRent:state.includeRent,waterRate:rate.water,electricRate:rate.electric};
};
const invoice=room=>state.approved.get(room.id)||liveInvoice(room);
const billStatus=room=>{
  if(room.vacant)return {text:"ห้องว่าง",tone:"purple",kind:"vacant"};
  if(!hasPair(room))return {text:"ข้อมูลไม่ครบ",tone:"warn",kind:"blocked"};
  if(state.sent.has(room.id))return {text:"ส่งแล้ว",tone:"good",kind:"sent"};
  if(state.approved.has(room.id)&&!room.email)return {text:"อนุมัติแล้ว · ไม่มีอีเมล",tone:"bad",kind:"approved"};
  if(state.approved.has(room.id))return {text:"อนุมัติแล้ว",tone:"purple",kind:"approved"};
  if(!room.email)return {text:"ไม่มีอีเมล",tone:"bad",kind:"blocked"};
  return {text:"พร้อมตรวจ",tone:"good",kind:"draft"};
};
const totals=()=>({captured:rooms.filter(capturedRoom).length,review:reviewQueue().length,ready:rooms.filter(r=>billStatus(r).kind==="draft").length,sent:state.sent.size});
function toast(message){const node=document.getElementById("toast");node.textContent=message;node.classList.add("show");clearTimeout(toast.timer);toast.timer=setTimeout(()=>node.classList.remove("show"),3400)}
function setPage(page){state.page=page;render();window.scrollTo({top:0,behavior:"smooth"});document.getElementById("page-content").focus()}
function render(){
  const names={home:"หน้าหลัก",review:"ยืนยันค่ามิเตอร์",bills:"บิล",rooms:"ห้องและมิเตอร์",settings:"ตั้งค่า"};
  document.getElementById("top-page-name").textContent=names[state.page];
  document.querySelectorAll("#side-nav button").forEach(b=>{const active=b.dataset.page===state.page;b.classList.toggle("active",active);if(active)b.setAttribute("aria-current","page");else b.removeAttribute("aria-current")});
  document.getElementById("nav-review-count").textContent=totals().review;
  const renderers={home:renderHome,review:renderReview,bills:renderBills,rooms:renderRooms,settings:renderSettings};
  document.getElementById("page-content").innerHTML=renderers[state.page]();
}
function pageHead(kicker,title,subtitle,action=""){return `<div class="page-head"><div><span class="eyebrow">${kicker}</span><h1>${title}</h1><p class="page-subtitle">${subtitle}</p></div><div class="page-actions">${action}</div></div>`}
function homeAttention(){
  const list=[];
  for(const r of reviewQueue()){
    if(r.ocr<r.prev)list.push({icon:"!",tone:"red",title:`ห้อง ${r.room.id} · มิเตอร์${readingName(r.type)}ต่ำกว่างวดก่อน`,desc:`OCR ${num(r.ocr)} < ค่ายืนยันก่อน ${num(r.prev)} · ต้องดูรูป`,page:"review",reviewKey:readingKey(r.room,r.type)});
    else if(r.confidence<.7)list.push({icon:"?",tone:"amber",title:`ห้อง ${r.room.id} · OCR มิเตอร์${readingName(r.type)}ไม่มั่นใจ`,desc:`ความมั่นใจ ${(r.confidence*100).toFixed(0)}% · ดูรูปเทียบ`,page:"review",reviewKey:readingKey(r.room,r.type)});
  }
  const rejected=allReadings().filter(r=>r.rejected);
  if(rejected.length)list.push({icon:"↻",tone:"red",title:`รอถ่ายใหม่ ${rejected.length} ค่า`,desc:`ห้อง ${[...new Set(rejected.map(r=>r.room.id))].join(", ")} · ค่าเดิมถูกปฏิเสธแล้ว`,page:"rooms",roomId:rejected[0].room.id});
  const missing=rooms.filter(r=>!capturedRoom(r));
  if(missing.length)list.push({icon:"◌",tone:"amber",title:`ยังไม่มีรูป ${missing.length} ห้อง`,desc:`ห้อง ${missing.map(r=>r.id).join(", ")} · เลือกมิเตอร์บน /drive ก่อนถ่าย`,page:"rooms",roomId:missing[0].id});
  const noEmail=rooms.filter(r=>!r.vacant&&hasPair(r)&&!r.email);
  if(noEmail.length)list.push({icon:"@",tone:"amber",title:`ผู้เช่า ${noEmail.length} ห้องยังไม่มีอีเมล`,desc:`ห้อง ${noEmail.map(r=>r.id).join(", ")} · ดูบิลได้ แต่ส่งไม่ได้`,page:"rooms",roomId:noEmail[0].id});
  return list.map(x=>`<button class="attention-item" data-page="${x.page}" ${x.reviewKey?`data-review-target="${x.reviewKey}"`:""} ${x.roomId?`data-room-target="${x.roomId}"`:""}><span class="attention-icon ${x.tone}">${x.icon}</span><span class="attention-copy"><strong>${x.title}</strong><span>${x.desc}</span></span><span class="attention-chevron">›</span></button>`).join("")||`<div class="empty">ไม่มีรายการเร่งด่วน</div>`;
}
function renderHome(){const t=totals();return `<section class="page">
  ${pageHead("ARIA / OVERVIEW","รอบบิลกันยายน 2569","ภาพรวมการอ่านมิเตอร์ของหอตัวอย่าง 10 ห้อง · ห้องละมิเตอร์น้ำและไฟ",`<button class="btn primary" data-page="review">ตรวจค่าที่ค้าง ${t.review} ค่า <span aria-hidden="true">→</span></button>`)}
  <div class="info-banner"><span class="spark">✦</span><div><strong>ข้อมูลตัวอย่าง</strong> ตัวเลข รูปมิเตอร์ และชื่อผู้เช่าในหน้านี้ใช้ทดลองหน้าจอเท่านั้น ยังไม่เชื่อม Pi หรือคลาวด์</div></div>
  <div class="grid stat-grid">
    <div class="card stat-card"><div class="label">อ่านมิเตอร์ครบ</div><div class="number">${t.captured}<small> / 10 ห้อง</small></div><div class="hint">มีรูปน้ำและไฟครบทั้งคู่</div></div>
    <div class="card stat-card"><div class="label">ค่ารอยืนยัน</div><div class="number warn">${t.review}<small> ค่า</small></div><div class="hint">ตรวจรูปก่อนนำไปคิดบิล</div></div>
    <div class="card stat-card"><div class="label">บิลพร้อมตรวจ</div><div class="number accent">${t.ready}<small> ใบ</small></div><div class="hint">ยืนยันครบและมีอีเมล</div></div>
    <div class="card stat-card"><div class="label">อีเมลส่งแล้ว</div><div class="number good">${t.sent}<small> ฉบับ</small></div><div class="hint">ในต้นแบบเป็นการจำลองเท่านั้น</div></div>
  </div>
  <div class="grid two-col">
    <div class="card card-pad"><div class="card-head"><div><h2>ต้องดูก่อน</h2><p>รายการที่อาจทำให้บิลคลาดเคลื่อน</p></div><button class="text-link" data-page="review">ไปหน้ายืนยัน →</button></div><div class="attention-list">${homeAttention()}</div></div>
    <div class="card card-pad"><div class="card-head"><div><h2>ความคืบหน้ารอบบิล</h2><p>จากหุ่นสู่ผู้เช่า</p></div>${status("รอบปัจจุบัน","purple")}</div>
      <div class="step-list"><div class="step"><span class="step-num done">1</span><div><strong>หุ่นถ่ายภาพ</strong><small>${t.captured}/10 ห้องมีรูปครบ</small></div></div><div class="step"><span class="step-num current">2</span><div><strong>ผู้ให้เช่ายืนยันค่า</strong><small>เหลือ ${t.review} ค่าที่ต้องตรวจ</small></div></div><div class="step"><span class="step-num">3</span><div><strong>ตรวจและอนุมัติบิล</strong><small>${t.ready} ใบพร้อมตรวจ</small></div></div><div class="step"><span class="step-num">4</span><div><strong>ส่งอีเมล</strong><small>${t.sent} ฉบับจำลองแล้ว</small></div></div></div>
      <div class="device-panel"><div><small>หุ่น</small><b>MRC-001</b></div><div><small>ซิงก์ล่าสุดตามตัวอย่าง</small><b>16 ก.ย. · 20:12</b></div></div>
    </div>
  </div>
  <div class="card"><div class="card-head card-pad" style="margin-bottom:0"><div><h2>ห้องในรอบนี้</h2><p>ค่าที่แสดงเป็นตัวอย่าง และแยกสถานะระดับห้องจากจำนวนค่ามิเตอร์</p></div><button class="text-link" data-page="rooms">ดูทะเบียนทั้งหมด →</button></div><div class="table-wrap"><table class="data-table"><thead><tr><th>ห้อง</th><th>มิเตอร์น้ำ</th><th>มิเตอร์ไฟ</th><th>สถานะ</th></tr></thead><tbody>${rooms.map(r=>`<tr><td><span class="room-label">ห้อง ${r.id}</span></td><td>${readingDisplay(r.water,"water")}</td><td>${readingDisplay(r.electric,"electric")}</td><td>${status(roomStatus(r).text,roomStatus(r).tone)}</td></tr>`).join("")}</tbody></table></div></div>
  </section>`}
function reviewAlert(r){
  if(r.ocr<r.prev)return `<div class="alert bad"><strong>ค่าน้อยกว่างวดก่อน</strong> · ค่าใหม่ต้องไม่น้อยกว่า ${num(r.prev)} หากมิเตอร์ถูกเปลี่ยนตัว ต้องใช้ขั้นตอนเปลี่ยนมิเตอร์แยก</div>`;
  if(r.confidence<.7)return `<div class="alert warn"><strong>OCR ไม่มั่นใจ</strong> · ความมั่นใจ ${(r.confidence*100).toFixed(0)}% ตรวจรูปก่อนยืนยัน</div>`;
  return `<div class="alert good">ค่า OCR ไม่ผิดปกติ แต่ยังต้องให้ผู้ให้เช่ายืนยันก่อนคิดบิล</div>`;
}
function renderReview(){
  const q=reviewQueue();if(!q.length)return `<section class="page">${pageHead("METER REVIEW","ยืนยันค่ามิเตอร์","ไม่มีค่าที่รอยืนยันในข้อมูลตัวอย่าง")}</section>`;
  if(!q.some(r=>readingKey(r.room,r.type)===state.selectedReview))state.selectedReview=readingKey(q[0].room,q[0].type);
  const r=q.find(r=>readingKey(r.room,r.type)===state.selectedReview)||q[0];const item=r.room[r.type];const needsReason=r.ocr<r.prev||r.confidence<.7;
  return `<section class="page">${pageHead("METER REVIEW","ยืนยันค่ามิเตอร์",`รอบกันยายน 2569 · เหลือ ${q.length} ค่า · เรียงผิดปกติ → OCR ไม่มั่นใจ → ปกติ`)}
    <div class="info-banner"><span class="spark">◈</span><div>ภาพมิเตอร์ด้านล่างเป็นกราฟิกตัวอย่าง ค่า OCR และค่าที่ยืนยันแยกกันเสมอ การกดยืนยันเปลี่ยนเฉพาะข้อมูลจำลองในหน้านี้</div></div>
    <div class="review-layout"><div class="card queue-card"><div class="queue-top"><h2>คิวรอยืนยัน</h2><p>${q.length} ค่า · เลือกรายการเพื่อตรวจ</p></div><div class="queue-list">${q.map(a=>`<button class="queue-item ${readingKey(a.room,a.type)===state.selectedReview?"active":""}" data-review="${readingKey(a.room,a.type)}"><span class="queue-type">${a.type==="water"?"◈":"ϟ"}</span><span class="queue-copy"><strong>ห้อง ${a.room.id} · ${readingName(a.type)}</strong><small>OCR ${num(a.ocr)} · ${a.ocr<a.prev?"ต่ำกว่าเดิม":`มั่นใจ ${(a.confidence*100).toFixed(0)}%`}</small></span>${a.ocr<a.prev?status("ผิดปกติ","bad"):a.confidence<.7?status("ไม่มั่นใจ","warn"):""}</button>`).join("")}</div></div>
    <div class="card review-detail"><div class="review-header"><div><h2>ห้อง ${r.room.id} · มิเตอร์${readingName(r.type)}</h2><p>meter_id ${r.type==="water"?"W":"E"}-${r.room.id}-01 · ข้อมูลตัวอย่าง</p></div>${r.ocr<r.prev?status("ต้องแก้","bad"):r.confidence<.7?status("OCR ไม่มั่นใจ","warn"):status("รอยืนยัน","purple")}</div>
      <div class="image-stage"><div class="meter-housing"><small>ARIA / ${r.type==="water"?"WATER":"ELECTRIC"} METER</small><div class="digital">${esc(String(r.ocr).padStart(5,"0"))}</div></div><p class="image-caption">ภาพกราฟิกตัวอย่าง · ในระบบจริงแสดง crop จาก Pi</p></div>
      <div class="reading-comparison"><div class="comparison-box"><small>ยืนยันงวดก่อน</small><strong>${num(r.prev)}</strong></div><div class="comparison-box"><small>OCR รอบนี้</small><strong>${num(r.ocr)}</strong></div><div class="comparison-box"><small>หน่วยหากรับ OCR</small><strong>${num(r.ocr-r.prev)}</strong></div></div>
      ${reviewAlert(r)}
      <form id="confirm-form" class="confirm-form"><label>ค่าที่จะยืนยัน<input id="confirm-value" name="value" type="number" step="0.001" min="${r.prev}" value="${r.ocr}" required></label><label>เหตุผล ${needsReason?"(จำเป็น)":"(เมื่อแก้ค่า)"}<input name="reason" type="text" placeholder="เช่น ตรวจรูปแล้วอ่านเป็น …"></label><button class="btn primary" type="submit">ยืนยันค่า</button><button class="btn danger" type="button" data-action="reject-reading">ปฏิเสธ</button></form>
      <div class="history"><strong>ประวัติ:</strong> หุ่นอ่าน OCR ${num(r.ocr)} · ความมั่นใจ ${(r.confidence*100).toFixed(0)}% ${item.history?`<br>${item.history.map(h=>esc(h)).join("<br>")}`:""}</div>
    </div></div></section>`;
}
function billTabs(){return [["all","ทั้งหมด"],["draft","พร้อมตรวจ"],["approved","อนุมัติแล้ว"],["blocked","ข้อมูลไม่ครบ"],["sent","ส่งแล้ว"]].map(([key,label])=>`<button class="filter ${state.billFilter===key?"active":""}" data-filter="${key}">${label}</button>`).join("")}
function renderBills(){const list=rooms.filter(r=>state.billFilter==="all"||billStatus(r).kind===state.billFilter);const sendable=rooms.filter(r=>state.approved.has(r.id)&&r.email&&!state.sent.has(r.id));return `<section class="page">
  ${pageHead("BILLING","บิลค่าน้ำและค่าไฟ","รอบกันยายน 2569 · คำนวณจากค่าที่ยืนยันแล้วเท่านั้น",`<button class="btn" data-action="show-send">ตัวอย่างการส่ง ${sendable.length} ใบ</button>`)}
  <div class="info-banner"><span class="spark">✦</span><div><strong>ต้นแบบ</strong> ปุ่มอนุมัติและส่งในหน้านี้จำลองสถานะเท่านั้น ไม่มีอีเมลออกจากเครื่อง</div></div>
  <label class="switch-row"><input id="include-rent" type="checkbox" ${state.includeRent?"checked":""}><span><strong>รวมค่าเช่าในบิลรอบนี้</strong><small>ค่าเช่ากำหนดต่อห้อง · ค่าเริ่มต้นปิด · บิลที่อนุมัติแล้วคงยอดเดิม</small></span></label>
  <div class="filter-bar">${billTabs()}</div>
  <div class="card"><div class="table-wrap"><table class="data-table"><thead><tr><th>ห้อง / ผู้เช่า</th><th>น้ำ</th><th>ไฟ</th><th>ค่าเช่า</th><th class="num">รวม</th><th>สถานะ</th><th></th></tr></thead><tbody>${list.map(r=>{const bill=invoice(r),s=billStatus(r);return `<tr><td><span class="room-label">ห้อง ${r.id}</span><br><small class="muted">${r.vacant?"ห้องว่าง":esc(r.tenant)} ${r.email?"":"· ไม่มีอีเมล"}</small></td><td>${bill?`${bill.waterUnits} หน่วย<br><strong>${baht(bill.water)}</strong>`:"—"}</td><td>${bill?`${bill.electricUnits} หน่วย<br><strong>${baht(bill.electric)}</strong>`:"—"}</td><td>${bill&&bill.includeRent?baht(bill.rent):"—"}</td><td class="num bill-total">${bill?baht(bill.total):"—"}</td><td>${status(s.text,s.tone)}</td><td><button class="btn small" data-preview="${r.id}" ${!bill?"disabled":""}>ดูบิล</button></td></tr>`}).join("")||`<tr><td colspan="7" class="empty">ไม่มีบิลในตัวกรองนี้</td></tr>`}</tbody></table></div><div class="bill-footer"><p>อัตราตัวอย่าง: น้ำ ${baht(rate.water)}/หน่วย · ไฟ ${baht(rate.electric)}/หน่วย · วันตัดรอบ 1 ก.ย. 2569</p><button class="btn primary" data-action="simulate-send" ${sendable.length?"":"disabled"}>จำลองส่ง ${sendable.length} บิล</button></div></div>
  </section>`}
function renderRooms(){const selected=roomById(state.selectedRoom)||rooms[0];return `<section class="page">
  ${pageHead("REGISTRY","ห้องและมิเตอร์","ทะเบียนตัวอย่าง 10 ห้อง · น้ำ 10 ตัว · ไฟ 10 ตัว")}
  <div class="info-banner"><span class="spark">▦</span><div>ข้อมูลนี้เป็นตัวอย่างที่แก้ได้ชั่วคราวในเบราว์เซอร์ รีโหลดหน้าแล้วกลับค่าเดิม; <code>meter_id</code> ของตัวที่เปลี่ยนใหม่ต้องเป็น ID ใหม่</div></div>
  <div class="room-layout"><div class="card"><div class="table-wrap"><table class="data-table" style="min-width:560px"><thead><tr><th>ห้อง</th><th>ผู้เช่า</th><th>มิเตอร์</th><th>สถานะ</th></tr></thead><tbody>${rooms.map(r=>`<tr class="room-row ${r.id===state.selectedRoom?"selected":""}" data-room="${r.id}" tabindex="0"><td class="room-label">${r.id}</td><td>${r.vacant?"— ว่าง":esc(r.tenant)}<br><small class="muted">${r.email?esc(r.email):"ไม่มีอีเมล"}</small></td><td><small>W-${r.id}-01<br>E-${r.id}-01</small></td><td>${status(roomStatus(r).text,roomStatus(r).tone)}</td></tr>`).join("")}</tbody></table></div></div>
  <div class="card room-detail"><div class="card-head"><div><h2>ห้อง ${selected.id}</h2><p>ชั้น ${selected.id[0]} · ทะเบียนตัวอย่าง</p></div>${status(selected.vacant?"ห้องว่าง":"มีผู้เช่า",selected.vacant?"purple":"good")}</div><div class="detail-grid"><div class="detail-kv"><small>ผู้เช่า</small><strong>${selected.vacant?"—":esc(selected.tenant)}</strong></div><div class="detail-kv"><small>อ่านล่าสุด</small><strong>${capturedRoom(selected)?"16 ก.ย. 2569":"ยังไม่อ่านครบ"}</strong></div></div>
    <form id="room-form"><label class="field">อีเมลรับบิล<input name="email" type="email" value="${esc(selected.email)}" placeholder="tenant@example.com" ${selected.vacant?"disabled":""}></label><label class="field">ค่าเช่า (บาท/เดือน · เมื่อเปิด option)<input name="rent" type="number" min="0" step="1" value="${selected.rent}" ${selected.vacant?"disabled":""}></label><button class="btn primary small" type="submit" ${selected.vacant?"disabled":""}>บันทึกตัวอย่าง</button></form>
    <div class="divider"></div><h3>มิเตอร์ที่ติดตั้ง</h3><div class="meter-card"><div><b>◈ น้ำ · W-${selected.id}-01</b><small>ค่างวดก่อน ${num(selected.water.prev)} · ปัจจุบัน ${num(selected.water.confirmed??selected.water.ocr)}</small></div>${status(selected.water.confirmed!=null?"ยืนยันแล้ว":selected.water.ocr==null?"ยังไม่อ่าน":"รอยืนยัน",selected.water.confirmed!=null?"good":"warn")}</div><div class="meter-card"><div><b>ϟ ไฟ · E-${selected.id}-01</b><small>ค่างวดก่อน ${num(selected.electric.prev)} · ปัจจุบัน ${num(selected.electric.confirmed??selected.electric.ocr)}</small></div>${status(selected.electric.confirmed!=null?"ยืนยันแล้ว":selected.electric.ocr==null?"ยังไม่อ่าน":"รอยืนยัน",selected.electric.confirmed!=null?"good":"warn")}</div>
    <div class="callout">โหมดใช้งานจริง: คนขับเลือกห้อง/มิเตอร์บนหน้า <code>/drive</code> ก่อนถ่าย หากลืมเลือก ภาพยังถูกบันทึกและเข้าคิว “ยังไม่ผูกห้อง”</div>
  </div></div></section>`}
function renderSettings(){return `<section class="page">${pageHead("PREFERENCES","ตั้งค่า","ค่าในหน้านี้เป็นแนวทางสำหรับระบบจริง")}
  <div class="settings-grid">
    <div class="card settings-box"><h2>อัตราค่าน้ำและไฟ</h2><p>เก็บเป็นรายการพร้อมวันที่เริ่มมีผล บิลที่อนุมัติแล้วไม่เปลี่ยนตามอัตราใหม่</p><div class="setting-line"><span>น้ำ · มีผล 1 ม.ค. 2569</span><strong>${baht(rate.water)} / หน่วย</strong></div><div class="setting-line"><span>ไฟ · มีผล 1 มิ.ย. 2569</span><strong>${baht(rate.electric)} / หน่วย</strong></div></div>
    <div class="card settings-box"><h2>การเข้าสู่ระบบ</h2><p>ระบบจริงใช้ Google Sign-in และอนุญาตเฉพาะบัญชีเจ้าของหอที่ระบุไว้</p><div class="setting-line"><span>วิธีเข้าระบบ</span>${status("Google / Gmail","purple")}</div><div class="setting-line"><span>ต้นแบบนี้</span><strong>Demo · ไม่มีการล็อกอินจริง</strong></div></div>
    <div class="card settings-box"><h2>ส่งบิลทางอีเมล</h2><p>ใช้ Gmail แยกของหอ สิทธิ์ส่งเป็นการตั้งค่าแยกจากการเข้าระบบ งานส่งต้องทำฝั่งเซิร์ฟเวอร์</p><div class="setting-line"><span>บัญชีผู้ส่ง</span><strong>Gmail ของหอ · ยังไม่เชื่อม</strong></div><div class="setting-line"><span>การส่งในต้นแบบ</span><strong>จำลองเท่านั้น</strong></div></div>
    <div class="card settings-box"><h2>เวลาและการซิงก์</h2><p>ปกติ Pi ใช้เวลาที่ซิงก์ผ่านเน็ต; เมื่อไม่มีเน็ตต้องแสดงสถานะความเชื่อถือของเวลา</p><div class="setting-line"><span>Pi 5 RTC / แบตสำรอง</span><strong>ยังไม่ตรวจบนเครื่องจริง</strong></div><div class="setting-line"><span>ข้อมูลไม่มีเน็ต</span><strong>เก็บในเครื่องแล้วค่อยซิงก์</strong></div></div>
    <div class="card settings-box"><h2>ข้อมูลหอพัก</h2><p>ต้นแบบหอพักอาคารเดียว ไม่มีข้อมูลผู้เช่าจริง</p><div class="setting-line"><span>จำนวนห้องตัวอย่าง</span><strong>10 ห้อง</strong></div><div class="setting-line"><span>มิเตอร์ต่อห้อง</span><strong>น้ำ 1 · ไฟ 1</strong></div><div class="setting-line"><span>วันตัดรอบตัวอย่าง</span><strong>วันที่ 1 ของเดือน</strong></div></div>
    <div class="card settings-box"><h2>อัตลักษณ์ ARIA</h2><p>โลโก้ที่แนบใช้เป็นทิศทางภาพลักษณ์ สีม่วงเข้มเป็นสีหลักของหลังบ้าน</p><img class="logo-reference" src="../aria-logo-reference.png" alt="โลโก้ ARIA ที่ผู้ใช้แนบ"></div>
  </div></section>`}
function showInvoice(roomId){const room=roomById(roomId),bill=invoice(room);if(!bill)return;const approved=state.approved.has(room.id);document.getElementById("modal-root").innerHTML=`<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-head"><div><span class="eyebrow">INVOICE PREVIEW · DEMO</span><h2 id="modal-title">บิลห้อง ${room.id}</h2><p class="muted" style="font-size:12px;margin:0">ผู้เช่า ${esc(room.tenant)} · ${room.email?esc(room.email):"ยังไม่มีอีเมล"}</p></div><button type="button" aria-label="ปิด" data-action="close-modal">×</button></div><div class="invoice-paper"><h3>ARIA · บิลกันยายน 2569</h3><small>ข้อมูลตัวอย่าง · ยังไม่ใช่เอกสารเรียกเก็บเงินจริง</small><div class="invoice-line"><span>ค่าน้ำ ${bill.waterUnits} หน่วย × ${baht(bill.waterRate)}</span><strong>${baht(bill.water)}</strong></div><div class="invoice-line"><span>ค่าไฟ ${bill.electricUnits} หน่วย × ${baht(bill.electricRate)}</span><strong>${baht(bill.electric)}</strong></div>${bill.includeRent?`<div class="invoice-line"><span>ค่าเช่า (รายการเสริม)</span><strong>${baht(bill.rent)}</strong></div>`:""}<div class="invoice-line total"><span>รวม</span><span>${baht(bill.total)}</span></div></div><div class="modal-actions"><button class="btn" data-action="close-modal">ปิด</button>${approved?status("อนุมัติแล้ว · ยอดถูกตรึง","good"):`<button class="btn primary" data-action="approve" data-id="${room.id}">อนุมัติบิลตัวอย่าง</button>`}</div></div></div>`;document.querySelector(".modal [aria-label='ปิด']").focus()}
function showSend(){const sendable=rooms.filter(r=>state.approved.has(r.id)&&r.email&&!state.sent.has(r.id));document.getElementById("modal-root").innerHTML=`<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-head"><div><span class="eyebrow">EMAIL PREVIEW · DEMO</span><h2 id="modal-title">ตัวอย่างการส่งบิล</h2></div><button type="button" aria-label="ปิด" data-action="close-modal">×</button></div><p class="muted" style="font-size:12px">มี ${sendable.length} บิลที่อนุมัติและมีอีเมล การกดจำลองส่งจะเปลี่ยนสถานะบนหน้าจอเท่านั้น</p><div class="invoice-paper">${sendable.length?sendable.map(r=>`<div class="invoice-line"><span>ห้อง ${r.id} · ${esc(r.email)}</span><strong>${baht(invoice(r).total)}</strong></div>`).join(""):`<p class="muted" style="margin:0">ยังไม่มีบิลที่พร้อมส่ง</p>`}</div><div class="modal-actions"><button class="btn" data-action="close-modal">ปิด</button>${sendable.length?`<button class="btn primary" data-action="simulate-send">จำลองส่ง ${sendable.length} ฉบับ</button>`:""}</div></div></div>`;document.querySelector(".modal [aria-label='ปิด']").focus()}
function closeModal(){document.getElementById("modal-root").innerHTML=""}
document.addEventListener("click",e=>{
  const nav=e.target.closest("[data-page]");if(nav){if(nav.dataset.reviewTarget)state.selectedReview=nav.dataset.reviewTarget;if(nav.dataset.roomTarget)state.selectedRoom=nav.dataset.roomTarget;setPage(nav.dataset.page);return}
  const review=e.target.closest("[data-review]");if(review){state.selectedReview=review.dataset.review;render();return}
  const room=e.target.closest("[data-room]");if(room){state.selectedRoom=room.dataset.room;render();return}
  const filter=e.target.closest("[data-filter]");if(filter){state.billFilter=filter.dataset.filter;render();return}
  const preview=e.target.closest("[data-preview]");if(preview){showInvoice(preview.dataset.preview);return}
  const action=e.target.closest("[data-action]");if(!action)return;
  if(action.dataset.action==="close-modal"){if(e.target===action||action.tagName==="BUTTON")closeModal();return}
  if(action.dataset.action==="show-send"){showSend();return}
  if(action.dataset.action==="reject-reading"){
    const [id,type]=state.selectedReview.split(":"),r=roomById(id)[type];r.rejected=true;r.history=(r.history||[]).concat("ผู้ให้เช่าปฏิเสธค่า · รอถ่ายใหม่ (จำลอง)");state.selectedReview=null;toast(`ห้อง ${id} · ${readingName(type)} ถูกปฏิเสธในข้อมูลตัวอย่าง`);render();return;
  }
  if(action.dataset.action==="approve"){
    const room=roomById(action.dataset.id),bill=liveInvoice(room);if(!bill)return;state.approved.set(room.id,{...bill});closeModal();toast(`อนุมัติบิลห้อง ${room.id} ในข้อมูลตัวอย่างแล้ว`);render();return;
  }
  if(action.dataset.action==="simulate-send"){
    const sendable=rooms.filter(r=>state.approved.has(r.id)&&r.email&&!state.sent.has(r.id));sendable.forEach(r=>state.sent.add(r.id));closeModal();toast(`จำลองส่ง ${sendable.length} ฉบับแล้ว · ไม่มีอีเมลถูกส่งจริง`);render();return;
  }
});
document.addEventListener("submit",e=>{
  if(e.target.id==="confirm-form"){
    e.preventDefault();const [id,type]=state.selectedReview.split(":"),r=roomById(id)[type];const form=new FormData(e.target),value=Number(form.get("value")),reason=String(form.get("reason")||"").trim();
    if(!Number.isFinite(value)||value<r.prev){toast(`ยืนยันไม่ได้: ค่าต้องไม่น้อยกว่า ${num(r.prev)}`);return}
    if((value!==r.ocr||r.confidence<.7)&&!reason){toast("กรุณาระบุเหตุผลเมื่อแก้ค่า หรือ OCR ไม่มั่นใจ");return}
    r.confirmed=value;r.history=(r.history||[]).concat(`ผู้ให้เช่ายืนยัน ${num(value)}${reason?` · ${reason}`:""} (จำลอง)`);state.selectedReview=null;toast(`ยืนยันมิเตอร์${readingName(type)}ห้อง ${id} ในข้อมูลตัวอย่างแล้ว`);render();return;
  }
  if(e.target.id==="room-form"){
    e.preventDefault();const room=roomById(state.selectedRoom),form=new FormData(e.target),email=String(form.get("email")||"").trim(),rent=Number(form.get("rent"));if(room.vacant)return;
    if(email&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)){toast("อีเมลไม่ถูกต้อง");return}
    if(!Number.isFinite(rent)||rent<0){toast("ค่าเช่าต้องไม่ติดลบ");return}
    room.email=email;room.rent=rent;toast(`บันทึกห้อง ${room.id} ในข้อมูลตัวอย่างแล้ว`);render();return;
  }
});
document.addEventListener("change",e=>{if(e.target.id==="include-rent"){state.includeRent=e.target.checked;render();toast(state.includeRent?"เปิดค่าเช่าสำหรับร่างบิลรอบนี้":"ปิดค่าเช่าสำหรับร่างบิลรอบนี้")}});
document.addEventListener("keydown",e=>{if(e.key==="Escape")closeModal();if((e.key==="Enter"||e.key===" ")&&e.target.matches("tr[data-room]")){e.preventDefault();state.selectedRoom=e.target.dataset.room;render()}});
render();
