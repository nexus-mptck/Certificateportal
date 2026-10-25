/* attendance.js — admin daily attendance interactions (client-side demo state) */
(function () {
  'use strict';
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var table = $('#attendance-table'); if (!table) return;
  var done = $('#class-done'), actual = $('#actual-hours'), dirty = false;

  function counts() {
    var c = { present: 0, absent: 0, leave: 0 }, rows = $$('tbody tr[data-row]', table);
    rows.forEach(function (r) { var v = $('input:checked', r); if (v) c[v.value]++; });
    var total = rows.length, rate = total ? Math.round(c.present / total * 100) : 0;
    $('#sum-present').textContent = c.present; $('#sum-absent').textContent = c.absent; $('#sum-leave').textContent = c.leave; $('#sum-rate').textContent = rate + '%';
    var bar = $('#rate-bar'); if (bar) bar.style.width = rate + '%';
  }
  function mark(v) { $$('tbody tr[data-row]', table).forEach(function (r) { var i = $('input[value="' + v + '"]', r); if (i) i.checked = true; }); counts(); dirty = true; }
  table.addEventListener('change', function () { counts(); dirty = true; });
  $('#mark-all-present').addEventListener('click', function () { mark('present'); showToast('All students marked present', 'Review exceptions, then save.'); });
  function syncDone() { actual.disabled = !done.checked; if (!done.checked) actual.value = ''; }
  done.addEventListener('change', function () { syncDone(); dirty = true; }); syncDone();
  $('#attendance-form').addEventListener('submit', function (e) {
    e.preventDefault();
    var topic = $('#topic');
    if (!topic.value.trim()) { topic.closest('.field').classList.add('has-error'); topic.focus(); return; }
    topic.closest('.field').classList.remove('has-error');
    if (done.checked && (!actual.value || +actual.value <= 0)) { actual.closest('.field').classList.add('has-error'); actual.focus(); return; }
    actual.closest('.field').classList.remove('has-error');
    dirty = false; showToast('Attendance saved', 'Demo only: nothing was stored.');
  });
  $$('#course-select,#date-select').forEach(function (s) { s.addEventListener('change', function () { showToast('Session loaded', 'Demo data: the roster is the same for every selection.'); }); });
  window.addEventListener('beforeunload', function (e) { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
  counts();
})();
