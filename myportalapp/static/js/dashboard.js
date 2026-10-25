/* dashboard.js — Chart.js rendering for the admin dashboard (demo data only) */
(function () {
  'use strict';
  if (!window.Chart) return;
  var css = getComputedStyle(document.documentElement);
  var blue = css.getPropertyValue('--blue-600').trim() || '#2563eb';
  var navy = css.getPropertyValue('--navy-900').trim() || '#0e1a2f';
  var gold = css.getPropertyValue('--gold').trim() || '#a8812f';
  Chart.defaults.font.family = css.getPropertyValue('--font').trim();
  Chart.defaults.color = '#64748b';
  /* Backend: replace with {{ enrollment_trend|json_script:"enrollment-data" }} and read it here. */
  var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct'];
  var counts = [18, 22, 27, 31, 29, 38, 41, 46, 52, 44];
  var el = document.getElementById('enrollmentChart');
  if (el) new Chart(el, {
    type: 'line',
    data: { labels: months, datasets: [{ label: 'New enrollments', data: counts, borderColor: blue, backgroundColor: 'rgba(37,99,235,.08)', fill: true, tension: .35, pointRadius: 3, pointBackgroundColor: '#fff', pointBorderColor: blue, borderWidth: 2 }] },
    options: { maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { color: '#eef2f7' }, border: { display: false } }, x: { grid: { display: false } } } }
  });
  var t = document.getElementById('typeChart');
  if (t) new Chart(t, {
    type: 'doughnut',
    data: { labels: ['Completion', 'Achievement'], datasets: [{ data: [118, 69], backgroundColor: [blue, gold], borderColor: '#fff', borderWidth: 3 }] },
    options: { maintainAspectRatio: false, cutout: '68%', plugins: { legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 16 } } } }
  });
})();
