/* main.js — shared interactions (frontend only, no network requests) */
(function () {
  'use strict';
  var $ = function (s, c) { return (c || document).querySelector(s); };
  var $$ = function (s, c) { return Array.prototype.slice.call((c || document).querySelectorAll(s)); };

  function icons() { if (window.lucide && window.lucide.createIcons) window.lucide.createIcons(); }
  window.refreshIcons = icons;

  /* Toasts */
  window.showToast = function (title, detail, type) {
    var region = $('#toast-region'); if (!region) return;
    var t = document.createElement('div');
    t.className = 'toast is-' + (type || 'success'); t.setAttribute('role', 'status');
    t.innerHTML = '<i data-lucide="' + (type === 'error' ? 'circle-alert' : 'circle-check') + '"></i><div><strong></strong><small></small></div>';
    $('strong', t).textContent = title; $('small', t).textContent = detail || '';
    region.appendChild(t); icons();
    setTimeout(function () { t.remove(); }, 3800);
  };

  /* Sidebar: collapse (desktop) and slide-in (mobile) */
  document.addEventListener('click', function (e) {
    var tgl = e.target.closest('[data-sidebar-toggle]');
    if (tgl) {
      if (window.matchMedia('(max-width:900px)').matches) document.body.classList.toggle('sidebar-open');
      else { document.body.classList.toggle('sidebar-collapsed'); try { localStorage.setItem('sb', document.body.classList.contains('sidebar-collapsed') ? '1' : ''); } catch (x) {} }
      tgl.setAttribute('aria-expanded', String(document.body.classList.contains('sidebar-open')));
    }
    if (e.target.closest('.scrim')) document.body.classList.remove('sidebar-open');
  });
  try { if (localStorage.getItem('sb') === '1') document.body.classList.add('sidebar-collapsed'); } catch (x) {}

  /* Active nav from <body data-nav="key"> */
  var key = document.body.getAttribute('data-nav');
  $$('.nav-link[data-nav-key]').forEach(function (a) {
    if (a.getAttribute('data-nav-key') === key) { a.classList.add('is-active'); a.setAttribute('aria-current', 'page'); }
  });

  /* Dropdowns */
  function closeDropdowns(except) {
    $$('.dropdown-menu').forEach(function (m) {
      if (m !== except && !m.hidden) { m.hidden = true; var b = m.parentNode.querySelector('[data-dropdown]'); if (b) b.setAttribute('aria-expanded', 'false'); }
    });
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-dropdown]');
    if (btn) {
      var menu = $('.dropdown-menu', btn.parentNode); var open = menu.hidden;
      closeDropdowns(menu); menu.hidden = !open; btn.setAttribute('aria-expanded', String(open)); return;
    }
    if (!e.target.closest('.dropdown-menu')) closeDropdowns();
  });

  /* Modals: data-modal-open="id", data-modal-close */
  var lastFocus = null;
  window.openModal = function (id) {
    var m = document.getElementById(id); if (!m) return;
    lastFocus = document.activeElement; m.hidden = false;
    var f = $('input,select,textarea,button:not([data-modal-close])', m) || $('button', m); if (f) f.focus();
  };
  window.closeModal = function (m) { m.hidden = true; if (lastFocus) lastFocus.focus(); };
  document.addEventListener('click', function (e) {
    var o = e.target.closest('[data-modal-open]'); if (o) { openModal(o.getAttribute('data-modal-open')); return; }
    var c = e.target.closest('[data-modal-close]'); if (c) { closeModal(c.closest('.modal-backdrop')); return; }
    if (e.target.classList.contains('modal-backdrop')) closeModal(e.target);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') { $$('.modal-backdrop').forEach(function (m) { if (!m.hidden) closeModal(m); }); closeDropdowns(); document.body.classList.remove('sidebar-open'); }
  });

  /* Password visibility */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-toggle-password]'); if (!b) return;
    var input = document.getElementById(b.getAttribute('data-toggle-password'));
    var show = input.type === 'password'; input.type = show ? 'text' : 'password';
    b.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    var i = $('[data-lucide],svg', b); if (i) { b.innerHTML = '<i data-lucide="' + (show ? 'eye-off' : 'eye') + '"></i>'; icons(); }
  });

  /* Tabs */
  $$('[data-tabs]').forEach(function (root) {
    var tabs = $$('[role="tab"]', root);
    function select(t) {
      tabs.forEach(function (x) { var on = x === t; x.setAttribute('aria-selected', String(on)); x.tabIndex = on ? 0 : -1; var p = document.getElementById(x.getAttribute('aria-controls')); if (p) p.hidden = !on; });
    }
    tabs.forEach(function (t, i) {
      t.addEventListener('click', function () { select(t); });
      t.addEventListener('keydown', function (e) {
        var n = e.key === 'ArrowRight' ? i + 1 : e.key === 'ArrowLeft' ? i - 1 : null;
        if (n !== null) { var tt = tabs[(n + tabs.length) % tabs.length]; tt.focus(); select(tt); }
      });
    });
  });

  /* Form validation: <form data-validate novalidate> with .field wrappers and .error-text */
  function validateField(el) {
    var field = el.closest('.field'); if (!field) return true;
    var msg = $('.error-text span', field), ok = el.checkValidity();
    if (!ok && msg) {
      var v = el.validity;
      msg.textContent = el.dataset.error || (v.valueMissing ? 'This field is required.' : v.typeMismatch ? 'Enter a valid value.' : v.rangeUnderflow ? 'Value is too low.' : v.patternMismatch ? 'Check the format.' : 'Invalid value.');
    }
    field.classList.toggle('has-error', !ok); el.setAttribute('aria-invalid', String(!ok)); return ok;
  }
  $$('form[data-validate]').forEach(function (form) {
    form.noValidate = true;
    $$('input,select,textarea', form).forEach(function (el) {
      el.addEventListener('blur', function () { if (el.value !== '' || el.closest('.field.has-error')) validateField(el); });
      el.addEventListener('input', function () { if (el.closest('.field.has-error')) validateField(el); });
    });
    form.addEventListener('submit', function (e) {
      var bad = null;
      $$('input,select,textarea', form).forEach(function (el) { if (!validateField(el) && !bad) bad = el; });
      var cross = form.getAttribute('data-cross'); if (!bad && cross && window[cross]) { bad = window[cross](form) || null; }
      if (bad) {
        e.preventDefault();
        bad.focus && bad.focus();
        var a = $('.alert-error', form);
        if (a) a.hidden = false;
        return;
      }
      var a2 = $('.alert-error', form); if (a2) a2.hidden = true;
      if (form.getAttribute('data-demo-only') === 'true') {
        e.preventDefault();
        var ok = form.getAttribute('data-success');
        showToast(ok || 'Saved', '');
        var go = form.getAttribute('data-redirect');
        if (go) setTimeout(function () { location.href = go; }, 800);
      }
    });
  });

  /* Table/card filtering: [data-filter-scope] contains search input [data-search], selects [data-filter="col"], chips [data-chip-filter] */
  $$('[data-filter-scope]').forEach(function (scope) {
    var rows = $$('[data-row]', scope), search = $('[data-search]', scope), selects = $$('select[data-filter]', scope), chips = $$('[data-chip]', scope);
    var empty = $('.empty', scope), count = $('[data-count]', scope), chip = 'all';
    function run() {
      var q = search ? search.value.trim().toLowerCase() : '', shown = 0;
      rows.forEach(function (r) {
        var ok = !q || r.textContent.toLowerCase().indexOf(q) > -1;
        selects.forEach(function (s) { if (s.value && r.getAttribute('data-' + s.getAttribute('data-filter')) !== s.value) ok = false; });
        if (chip !== 'all' && r.getAttribute('data-status') !== chip) ok = false;
        r.hidden = !ok; if (ok) shown++;
      });
      if (empty) empty.classList.toggle('is-visible', shown === 0);
      if (count) count.textContent = shown;
    }
    if (search) search.addEventListener('input', run);
    selects.forEach(function (s) { s.addEventListener('change', run); });
    chips.forEach(function (c) { c.addEventListener('click', function () { chips.forEach(function (x) { x.setAttribute('aria-pressed', 'false'); }); c.setAttribute('aria-pressed', 'true'); chip = c.getAttribute('data-chip'); run(); }); });
  });

  /* Generic simulated actions: data-demo-action="Title|Detail" and data-confirm */
  document.addEventListener('click', function (e) {
    var b = e.target.closest('[data-demo-action]'); if (!b) return;
    var p = b.getAttribute('data-demo-action').split('|');
    var row = b.closest('[data-row]');
    if (b.hasAttribute('data-remove-row') && row) { row.hidden = true; }
    if (b.hasAttribute('data-set-status') && row) { var s = $('[data-status-badge]', row); if (s) { s.className = 'badge ' + b.getAttribute('data-badge-class'); s.textContent = b.getAttribute('data-set-status'); } row.setAttribute('data-status', b.getAttribute('data-set-status').toLowerCase()); $$('[data-row-action]', row).forEach(function (x) { x.disabled = true; }); }
    showToast(p[0], p[1] || '', b.getAttribute('data-toast-type') || 'success');
    var m = b.closest('.modal-backdrop'); if (m) closeModal(m);
  });

  /* Display server-sent Django messages */
  $$('[data-django-message]').forEach(function (el) {
    var tag = el.getAttribute('data-django-message') || 'info';
    var text = el.textContent.trim();
    if (text) {
      var toastType = (tag.indexOf('error') > -1) ? 'error' : 'success';
      showToast(text, '', toastType);
    }
  });

  /* Login check stub (server validates credentials) */
  window.demoLoginCheck = function (form) {
    return null;
  };

  /* Print helper */
  document.addEventListener('click', function (e) {
    var p = e.target.closest('[data-print]'); if (!p) return;
    var sel = p.getAttribute('data-print'); document.body.classList.add('printing-certificate');
    $$('.print-target').forEach(function (n) { n.classList.remove('print-target'); });
    var t = sel && sel !== 'page' ? $(sel) : null; if (t) t.classList.add('print-target');
    window.print();
  });
  window.addEventListener('afterprint', function () { document.body.classList.remove('printing-certificate'); $$('.print-target').forEach(function (n) { n.classList.remove('print-target'); }); });

  var tt=$('#topbar-title'); if(tt){ var t=document.title.split(' · ')[0]; if(t) tt.textContent=t; }
  icons();
})();
