// ธีมสีที่ผู้ใช้เลือก (ต่อเบราว์เซอร์) · สลับ stylesheet เป็นชุด .<ธีม>.css ก่อนวาดหน้าแรก · ม่วง = ค่าเริ่ม
// ธีม + สี theme-color ต้องตรงกับ ACCENTS ใน app.js (ไฟล์ CSS สร้างจาก tools/make_accent.py)
(function () {
  var META = { teal: '#071918', graphite: '#151617', rose: '#270e16', gold: '#1c1508', sapphire: '#0c142e', navy: '#12161e', emerald: '#081912', ruby: '#290d10', copper: '#21120a', blush: '#250f13', hotpink: '#2a0a1b' };
  var a = 'purple';
  try { a = localStorage.getItem('aria.accent') || 'purple'; } catch (e) {}
  if (!META[a]) return;
  document.documentElement.setAttribute('data-accent', a);
  var links = document.querySelectorAll('link[data-css]');
  for (var i = 0; i < links.length; i++) links[i].href = links[i].getAttribute('href').replace(/css\/(\w+)\.css/, 'css/$1.' + a + '.css');
  var m = document.querySelector('meta[name="theme-color"]'); if (m) m.content = META[a];
})();
