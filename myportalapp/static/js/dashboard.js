/* dashboard.js — Chart.js rendering for the admin dashboard */
(function () {
  'use strict';
  if (!window.Chart) return;
  var css = getComputedStyle(document.documentElement);
  var blue = css.getPropertyValue('--blue-600').trim() || '#2563eb';
  var navy = css.getPropertyValue('--navy-900').trim() || '#0e1a2f';
  var gold = css.getPropertyValue('--gold').trim() || '#a8812f';
  Chart.defaults.font.family = css.getPropertyValue('--font').trim();
  Chart.defaults.color = '#64748b';

  // Read dynamic enrollment data from json_script if available
  var months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var counts = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
  var enrScript = document.getElementById('enrollment-data');
  if (enrScript) {
    try {
      var d = JSON.parse(enrScript.textContent);
      if (d && d.labels && d.counts) {
        months = d.labels;
        counts = d.counts;
      }
    } catch (e) {}
  }

  var el = document.getElementById('enrollmentChart');
  if (el) new Chart(el, {
    type: 'line',
    data: {
      labels: months,
      datasets: [{
        label: 'New enrollments',
        data: counts,
        borderColor: blue,
        backgroundColor: 'rgba(37,99,235,.08)',
        fill: true,
        tension: .35,
        pointRadius: 3,
        pointBackgroundColor: '#fff',
        pointBorderColor: blue,
        borderWidth: 2
      }]
    },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2f7' }, border: { display: false } },
        x: { grid: { display: false } }
      }
    }
  });

  // Read dynamic certificate type breakdown
  var compCount = 0;
  var achCount = 0;
  var typeScript = document.getElementById('cert-type-data');
  if (typeScript) {
    try {
      var td = JSON.parse(typeScript.textContent);
      if (td) {
        compCount = td.completion || 0;
        achCount = td.achievement || 0;
      }
    } catch (e) {}
  }

  var t = document.getElementById('typeChart');
  if (t) new Chart(t, {
    type: 'doughnut',
    data: {
      labels: ['Completion', 'Achievement'],
      datasets: [{
        data: [compCount, achCount],
        backgroundColor: [blue, gold],
        borderColor: '#fff',
        borderWidth: 3
      }]
    },
    options: {
      maintainAspectRatio: false,
      cutout: '68%',
      plugins: {
        legend: { position: 'bottom', labels: { usePointStyle: true, boxWidth: 8, padding: 16 } }
      }
    }
  });
})();
