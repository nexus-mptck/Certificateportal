/* certificates.js — certificate preview scaling, live field binding, logo preview, print/download (frontend only) */
(function () {
  'use strict';
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };
  var PX = 297 * 96 / 25.4; /* A4 landscape width in CSS px */

  function fit(box) { var s = box.clientWidth / PX; if (s > 0) box.style.setProperty('--cert-scale', s.toFixed(4)); }
  function fitAll() { $$('.cert-fit').forEach(fit); }
  if (window.ResizeObserver) { var ro = new ResizeObserver(function (en) { en.forEach(function (e) { fit(e.target); }); }); $$('.cert-fit').forEach(function (b) { ro.observe(b); }); }
  window.addEventListener('resize', fitAll); window.addEventListener('load', fitAll); fitAll();

  /* Set text of data-cert-field elements inside a root */
  function setField(root, name, val) { $$('[data-cert-field="' + name + '"]', root).forEach(function (n) { n.textContent = val; }); }
  window.applyCert = function (root, d) {
    var sheet = $('[data-cert-sheet]', root) || root, ach = d.type === 'achievement';
    sheet.classList.toggle('achievement', ach);
    var map = { name: d.name, course: d.course, number: d.number, completed: d.completed, issued: d.issued };
    Object.keys(map).forEach(function (k) { if (map[k]) setField(root, k, map[k]); });
    if (d.days) setField(root, 'duration', d.days + ' training days · ' + d.hours + ' training hours');
    setField(root, 'title', ach ? 'Certificate of Achievement' : 'Certificate of Completion');
    setField(root, 'lead', ach ? 'in recognition of outstanding achievement in the course' : 'for successfully completing the training course');
    var award = $('.cert-award', root);
    if (ach && !award) { var a = document.createElement('div'); a.className = 'cert-award'; a.setAttribute('data-cert-field', 'award'); a.textContent = 'Awarded for [achievement description placeholder]'; var c = $('.cert-course', root); c.parentNode.insertBefore(a, $('.cert-meta', root)); }
    if (!ach && award) award.remove();
  };

  /* Certificate list: preview buttons carry row data */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-cert-preview]'); if (!b) return;
    var r = b.closest('[data-row]'), id = b.getAttribute('data-cert-preview');
    applyCert(document.getElementById(id), { type: r.getAttribute('data-type'), name: r.getAttribute('data-name'), course: r.getAttribute('data-course'), number: r.getAttribute('data-number'), days: r.getAttribute('data-days'), hours: r.getAttribute('data-hours'), completed: r.getAttribute('data-completed'), issued: r.getAttribute('data-issued') });
    openModal(id); fitAll();
  });
  document.addEventListener('click', function (e) { if (e.target.closest('[data-modal-open]')) setTimeout(fitAll, 30); });

  /* Generation form: live preview */
  var gen = $('#generate-form');
  if (gen) {
    var stage = $('#gen-preview');
    var upd = function () {
      var s = gen.student.selectedOptions[0], c = gen.course.selectedOptions[0], t = gen.querySelector('[name=cert_type]:checked').value;
      applyCert(stage, { type: t, name: s && s.value ? s.textContent.split(' (')[0] : 'Student Name', course: c && c.value ? c.textContent : 'Course Title', days: c && c.value ? c.getAttribute('data-days') : '5', hours: c && c.value ? c.getAttribute('data-hours') : '30', number: 'MTI-2026-NEXT', completed: '24 October 2026', issued: '24 October 2026' });
    };
    gen.addEventListener('change', upd); upd();
  }

  /* Settings: live branding preview + local logo preview */
  $$('[data-bind]').forEach(function (i) { i.addEventListener('input', function () { setField(document, i.getAttribute('data-bind'), i.value || i.placeholder); }); });
  var logo = $('[data-logo-input]');
  if (logo) logo.addEventListener('change', function () {
    var f = logo.files && logo.files[0]; if (!f) return;
    if (!/^image\//.test(f.type)) { showToast('Choose an image file', 'PNG, JPG or SVG works.', 'error'); logo.value = ''; return; }
    var rd = new FileReader(); rd.onload = function () { $$('[data-logo-preview]').forEach(function (im) { im.src = rd.result; }); showToast('Logo preview updated', 'Demo only: the file is not uploaded.'); }; rd.readAsDataURL(f);
  });

  /* Standalone certificate pages */
  $$('[data-print-page]').forEach(function (b) { b.addEventListener('click', function () { window.print(); }); });
})();
