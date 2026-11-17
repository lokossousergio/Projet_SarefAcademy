/* SAREF Academy — petits comportements partagés (aucune dépendance) */
(function () {
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // 1) Apparition au défilement : <div class="reveal" style="--d:.1s">
  var els = document.querySelectorAll('.reveal');
  if ('IntersectionObserver' in window && !reduce) {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } });
    }, { threshold: 0.12 });
    els.forEach(function (el) { io.observe(el); });
  } else { els.forEach(function (el) { el.classList.add('is-in'); }); }

  // 2) Compteurs animés : <span data-count="187" data-suffix=" FCFA" data-dec="1">
  document.querySelectorAll('[data-count]').forEach(function (el) {
    var end = parseFloat(el.dataset.count), dec = parseInt(el.dataset.dec || '0', 10), suf = el.dataset.suffix || '';
    var fmt = function (v) { return v.toLocaleString('fr-FR', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + suf; };
    if (reduce) { el.textContent = fmt(end); return; }
    var t0 = null, dur = 1100;
    function step(t) { if (!t0) t0 = t; var p = Math.min((t - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3); el.textContent = fmt(end * e); if (p < 1) requestAnimationFrame(step); }
    requestAnimationFrame(step);
  });

  // 3) Confirmation par saisie : <input data-confirm-text="SUPPRIMER" data-confirm-btn="#id-bouton">
  document.querySelectorAll('[data-confirm-text]').forEach(function (inp) {
    var btn = document.querySelector(inp.dataset.confirmBtn);
    if (!btn) return;
    inp.addEventListener('input', function () { btn.disabled = inp.value.trim() !== inp.dataset.confirmText; });
  });

  // 4) Compteur de caractères : <textarea data-counter="#cible" maxlength="255">
  document.querySelectorAll('[data-counter]').forEach(function (ta) {
    var out = document.querySelector(ta.dataset.counter);
    var upd = function () { if (out) out.textContent = ta.value.length + ' / ' + ta.maxLength; };
    ta.addEventListener('input', upd); upd();
  });
})();
