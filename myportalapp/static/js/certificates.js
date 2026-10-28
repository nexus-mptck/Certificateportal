/* certificates.js — certificate preview scaling, live field binding, logo preview, print/download */
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
    if (!root) return;
    var sheet = $('[data-cert-sheet]', root) || root, ach = d.type === 'achievement';
    sheet.classList.toggle('achievement', ach);
    var map = { name: d.name, course: d.course, number: d.number, completed: d.completed, issued: d.issued };
    Object.keys(map).forEach(function (k) { if (map[k]) setField(root, k, map[k]); });
    if (d.days) setField(root, 'duration', d.days + ' training days · ' + d.hours + ' training hours');
    setField(root, 'title', ach ? 'Certificate of Achievement' : 'Certificate of Completion');
    setField(root, 'lead', ach ? 'in recognition of outstanding achievement in the course' : 'for successfully completing the training course');
    var award = $('.cert-award', root);
    if (ach && !award) {
      var a = document.createElement('div');
      a.className = 'cert-award';
      a.setAttribute('data-cert-field', 'award');
      a.textContent = d.award || 'In recognition of exceptional dedication and performance';
      var c = $('.cert-course', root);
      if (c && c.parentNode) c.parentNode.insertBefore(a, $('.cert-meta', root));
    }
    if (!ach && award) award.remove();
    if (d.signature) {
      $$('[data-signature-preview]', root).forEach(function (im) {
        im.src = d.signature;
        var wrap = im.closest('.signature-img-wrap');
        if (wrap) wrap.style.display = '';
      });
    } else {
      $$('[data-signature-preview]', root).forEach(function (im) {
        im.src = '';
        var wrap = im.closest('.signature-img-wrap');
        if (wrap) wrap.style.display = 'none';
      });
    }
  };

  /* Certificate list: preview buttons carry row data and modal download link */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-cert-preview]'); if (!b) return;
    var r = b.closest('[data-row]'), id = b.getAttribute('data-cert-preview');
    var modal = document.getElementById(id);
    if (!modal) return;
    var data = {
      type: r.getAttribute('data-type'),
      name: r.getAttribute('data-name'),
      course: r.getAttribute('data-course'),
      number: r.getAttribute('data-number'),
      days: r.getAttribute('data-days'),
      hours: r.getAttribute('data-hours'),
      completed: r.getAttribute('data-completed'),
      issued: r.getAttribute('data-issued'),
      award: r.getAttribute('data-award'),
      signature: r.getAttribute('data-signature-url'),
    };
    applyCert(modal, data);
    var dl = $('[data-modal-download]', modal);
    var dlUrl = r.getAttribute('data-download-url');
    if (dl) {
      if (dlUrl) {
        dl.onclick = function () { window.location.href = dlUrl; };
        dl.removeAttribute('data-demo-action');
      } else {
        dl.onclick = null;
      }
    }
    openModal(id);
    fitAll();
  });
  document.addEventListener('click', function (e) { if (e.target.closest('[data-modal-open]')) setTimeout(fitAll, 30); });

  /* Generation form: live preview */
  var gen = $('#generate-form');
  if (gen) {
    var stage = $('#gen-preview');
    var upd = function () {
      var s = gen.student ? gen.student.selectedOptions[0] : null;
      var c = gen.course ? gen.course.selectedOptions[0] : null;
      var tRadio = gen.querySelector('[name=cert_type]:checked');
      var t = tRadio ? tRadio.value : 'completion';
      applyCert(stage, {
        type: t,
        name: s && s.value ? s.textContent.split(' (')[0] : 'Student Name',
        course: c && c.value ? c.textContent : 'Course Title',
        days: c && c.value && c.getAttribute('data-days') ? c.getAttribute('data-days') : '5',
        hours: c && c.value && c.getAttribute('data-hours') ? c.getAttribute('data-hours') : '30',
        number: 'MTI-AUTO',
        completed: 'Course completion date',
        issued: 'Today'
      });
    };
    gen.addEventListener('change', upd);
    upd();
  }

  /* Settings: live branding preview + local logo preview */
  $$('[data-bind]').forEach(function (i) {
    i.addEventListener('input', function () {
      setField(document, i.getAttribute('data-bind'), i.value || i.placeholder);
    });
  });

  var logo = $('[data-logo-input]');
  if (logo) {
    logo.addEventListener('change', function () {
      var f = logo.files && logo.files[0]; if (!f) return;
      if (!/^image\//.test(f.type)) {
        showToast('Choose an image file', 'PNG, JPG or SVG works.', 'error');
        logo.value = '';
        return;
      }
      var rd = new FileReader();
      rd.onload = function () {
        $$('[data-logo-preview]').forEach(function (im) { im.src = rd.result; });
        showToast('Logo preview updated', 'Save settings to store the new logo.');
      };
      rd.readAsDataURL(f);
    });
  }

  var sigInp = $('[data-signature-input]');
  var sigRemoveBtn = $('[data-signature-remove]');
  var removeSigInput = $('#remove-signature-input');
  var sigUploadBtnText = $('#signature-upload-btn-text');

  if (sigInp) {
    sigInp.addEventListener('change', function () {
      var f = sigInp.files && sigInp.files[0];
      if (!f) return;

      var ext = f.name ? f.name.split('.').pop().toLowerCase() : '';
      var validExts = ['png', 'jpg', 'jpeg'];
      var isImgType = /^image\/(png|jpeg|jpg)/i.test(f.type) || validExts.indexOf(ext) !== -1;

      if (!isImgType) {
        showToast('Invalid file format', 'Signature must be a PNG or JPG image file.', 'error');
        sigInp.value = '';
        return;
      }

      if (f.size > 5 * 1024 * 1024) {
        showToast('File too large', 'Signature image file size must not exceed 5MB.', 'error');
        sigInp.value = '';
        return;
      }

      var rd = new FileReader();
      rd.onload = function () {
        $$('[data-signature-preview]').forEach(function (im) {
          im.src = rd.result;
          im.style.display = '';
          var wrap = im.closest('.signature-img-wrap');
          if (wrap) wrap.style.display = '';
        });

        var ph = $('[data-signature-preview-placeholder]');
        if (ph) ph.style.display = 'none';

        if (sigRemoveBtn) sigRemoveBtn.style.display = '';
        if (removeSigInput) removeSigInput.value = '0';
        if (sigUploadBtnText) sigUploadBtnText.textContent = 'Replace signature';

        if (window.refreshIcons) window.refreshIcons();
        showToast('Signature preview updated', 'Save settings to store the new digital signature.');
      };
      rd.readAsDataURL(f);
    });
  }

  if (sigRemoveBtn) {
    sigRemoveBtn.addEventListener('click', function () {
      if (sigInp) sigInp.value = '';
      if (removeSigInput) removeSigInput.value = '1';

      $$('[data-signature-preview]').forEach(function (im) {
        im.src = '';
        if (im.id === 'signature-form-preview' || im.hasAttribute('data-signature-form-preview')) {
          im.style.display = 'none';
        }
        var wrap = im.closest('.signature-img-wrap');
        if (wrap) wrap.style.display = 'none';
      });

      var ph = $('[data-signature-preview-placeholder]');
      if (ph) ph.style.display = 'flex';

      sigRemoveBtn.style.display = 'none';
      if (sigUploadBtnText) sigUploadBtnText.textContent = 'Choose signature image';

      if (window.refreshIcons) window.refreshIcons();
      showToast('Signature removed', 'Save settings to apply changes.');
    });
  }

  /* Standalone certificate pages */
  $$('[data-print-page]').forEach(function (b) {
    b.addEventListener('click', function () { window.print(); });
  });
})();
