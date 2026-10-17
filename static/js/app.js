/* Minimal progressive enhancement: clock, toasts, modal dialogs, switch toggles. */
(function () {
  function tick() {
    var el = document.getElementById('live-clock');
    if (!el) return;
    var d = new Date();
    var p = function (n) { return String(n).padStart(2, '0'); };
    el.textContent = p(d.getHours()) + ':' + p(d.getMinutes()) + ':' + p(d.getSeconds());
  }
  setInterval(tick, 1000); tick();

  window.openModal = function (id) {
    var m = document.getElementById(id);
    if (m) { m.classList.add('open'); document.body.classList.add('no-scroll'); }
  };
  window.closeModal = function (id) {
    var m = typeof id === 'string' ? document.getElementById(id) : id;
    if (m) { m.classList.remove('open'); document.body.classList.remove('no-scroll'); }
  };
  document.addEventListener('click', function (e) {
    var opener = e.target.closest('[data-modal]');
    if (opener) { e.preventDefault(); window.openModal(opener.getAttribute('data-modal')); }
    var closer = e.target.closest('[data-close]');
    if (closer) { e.preventDefault(); var root = closer.closest('.modal-scrim'); if (root) window.closeModal(root); }
    if (e.target.classList && e.target.classList.contains('modal-scrim')) window.closeModal(e.target);
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      var open = document.querySelector('.modal-scrim.open');
      if (open) window.closeModal(open);
    }
  });
  setTimeout(function () {
    document.querySelectorAll('#toast-root .toast').forEach(function (t) {
      t.style.transition = 'opacity .4s'; t.style.opacity = '0';
      setTimeout(function () { t.remove(); }, 420);
    });
  }, 4200);
})();
