// ธีมสีที่ผู้ใช้เลือก (ต่อเบราว์เซอร์) · สลับ stylesheet เป็นชุด .teal.css ก่อนวาดหน้าแรก · ม่วง = ค่าเริ่ม
(function () {
  var a = 'purple';
  try { a = localStorage.getItem('aria.accent') || 'purple'; } catch (e) {}
  if (a !== 'teal') return;
  document.documentElement.setAttribute('data-accent', 'teal');
  var links = document.querySelectorAll('link[data-css]');
  for (var i = 0; i < links.length; i++) links[i].href = links[i].getAttribute('href').replace(/css\/(\w+)\.css/, 'css/$1.teal.css');
  var m = document.querySelector('meta[name="theme-color"]'); if (m) m.content = '#071918';
})();
