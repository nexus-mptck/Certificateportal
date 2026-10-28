/* attendance.js — admin daily attendance interactions */
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
    var sp = $('#sum-present'), sa = $('#sum-absent'), sl = $('#sum-leave'), sr = $('#sum-rate');
    if (sp) sp.textContent = c.present;
    if (sa) sa.textContent = c.absent;
    if (sl) sl.textContent = c.leave;
    if (sr) sr.textContent = rate + '%';
    var bar = $('#rate-bar'); if (bar) bar.style.width = rate + '%';
  }

  function mark(v) {
    $$('tbody tr[data-row]', table).forEach(function (r) {
      var i = $('input[value="' + v + '"]', r);
      if (i) i.checked = true;
    });
    counts();
    dirty = true;
  }

  table.addEventListener('change', function () { counts(); dirty = true; });
  var mapBtn = $('#mark-all-present');
  if (mapBtn) {
    mapBtn.addEventListener('click', function () {
      mark('present');
      showToast('All students marked present', 'Review exceptions, then save.');
    });
  }

  function syncDone() {
    if (!done || !actual) return;
    actual.disabled = !done.checked;
    if (!done.checked) actual.value = '0';
  }

  if (done) {
    done.addEventListener('change', function () { syncDone(); dirty = true; });
    syncDone();
  }

  var attForm = $('#attendance-form');
  if (attForm) {
    attForm.addEventListener('submit', function (e) {
      var topic = $('#topic');
      if (topic && !topic.value.trim()) {
        e.preventDefault();
        topic.closest('.field').classList.add('has-error');
        topic.focus();
        return;
      }
      if (topic) topic.closest('.field').classList.remove('has-error');

      if (done && done.checked && (!actual.value || +actual.value < 0)) {
        e.preventDefault();
        actual.closest('.field').classList.add('has-error');
        actual.focus();
        return;
      }
      if (actual) actual.closest('.field').classList.remove('has-error');

      dirty = false;
      // Allow natural form POST submission to backend
    });
  }

  // Reload session roster when course or date changes
  function reloadSession() {
    var cSel = $('#course-select');
    var dSel = $('#date-select');
    if (cSel && dSel) {
      var cId = cSel.value;
      var dVal = dSel.value;
      window.location.href = '/portal/admin/attendance/?course_id=' + encodeURIComponent(cId) + '&date=' + encodeURIComponent(dVal);
    }
  }

  var cSelect = $('#course-select');
  if (cSelect) cSelect.addEventListener('change', reloadSession);

  var dSelect = $('#date-select');
  if (dSelect) dSelect.addEventListener('change', reloadSession);

  window.addEventListener('beforeunload', function (e) { if (dirty) { e.preventDefault(); e.returnValue = ''; } });
  counts();
})();
