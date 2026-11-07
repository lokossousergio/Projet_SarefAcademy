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
  // 5) Filtres et recherche dans le navigateur (en plus des liens ?statut= pour le serveur)
  //    Liste : <table id="t" data-empty="#vide-t"> avec <tr data-status="…"> ; contrôles : data-list="#t"
  //    pastille : data-filter="valeur" · champ de recherche : data-search · liste déroulante : data-match
  var state = {};
  function refresh(list) {
    var f = state[list.id] || {}, n = 0;
    list.querySelectorAll('[data-status]').forEach(function (it) {
      var txt = it.textContent.toLowerCase(), ok = true;
      if (f.st && it.dataset.status !== f.st) ok = false;
      Object.keys(f).forEach(function (k) { if (k !== 'st' && f[k] && txt.indexOf(f[k]) === -1) ok = false; });
      it.hidden = !ok; if (ok) n++;
    });
    var empty = list.dataset.empty && document.querySelector(list.dataset.empty);
    if (empty) empty.hidden = n > 0;
  }
  document.querySelectorAll('[data-list]').forEach(function (c, idx) {
    var list = document.querySelector(c.dataset.list); if (!list) return;
    state[list.id] = state[list.id] || {};
    if (c.hasAttribute('data-filter')) {
      c.addEventListener('click', function (e) {
        e.preventDefault();
        document.querySelectorAll('[data-filter][data-list="' + c.dataset.list + '"]').forEach(function (p) { p.classList.toggle('active', p === c); });
        state[list.id].st = c.dataset.filter; refresh(list);
      });
    } else if (c.hasAttribute('data-search')) {
      c.addEventListener('input', function () { state[list.id].q = c.value.trim().toLowerCase(); refresh(list); });
    } else if (c.hasAttribute('data-match')) {
      c.addEventListener('change', function () { state[list.id]['m' + idx] = c.value.trim().toLowerCase(); refresh(list); });
    }
  });
  // 6) Mots de passe : afficher / masquer, générer un mot de passe aléatoire
  document.querySelectorAll('[data-toggle-pass]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var i = document.querySelector(btn.dataset.togglePass), show = i.type === 'password';
      i.type = show ? 'text' : 'password'; btn.innerHTML = '<i class="bi bi-' + (show ? 'eye-slash' : 'eye') + '"></i>';
    });
  });
  document.querySelectorAll('[data-gen-pass]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var i = document.querySelector(btn.dataset.genPass), c = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789', a = new Uint32Array(10);
      crypto.getRandomValues(a); i.value = Array.from(a, function (x) { return c[x % c.length]; }).join('');
      i.type = 'text'; i.dispatchEvent(new Event('input', { bubbles: true }));
    });
  });

  // 7) Message WhatsApp d'identifiants : <div data-wa data-wa-name="#…" data-wa-email="#…" data-wa-pass="#…" data-wa-phone="#…" data-wa-preview="#…" data-wa-link="#…">
  document.querySelectorAll('[data-wa]').forEach(function (box) {
    function q(k) { return document.querySelector(box.dataset[k]); }
    function build() {
      var name = (q('waName').value || '').trim() || '…', email = (q('waEmail').value || '').trim() || '(e-mail)',
          pass = q('waPass').value || '', phone = (q('waPhone').value || '').replace(/\D/g, '');
      var msg = 'Bonjour ' + name + ',\n\nVoici vos accès à l’espace formateur SAREF Academy :\n• Lien : ' + location.origin + '/connexion/\n• Identifiant : ' + email +
                '\n• Mot de passe provisoire : ' + (pass || '(à générer)') + '\n\nVous choisirez votre propre mot de passe à la première connexion. Merci de ne pas partager ces informations.';
      q('waPreview').textContent = msg;
      var a = q('waLink'), ok = !!(pass && phone);
      a.href = ok ? 'https://wa.me/' + phone + '?text=' + encodeURIComponent(msg) : '#';
      a.setAttribute('aria-disabled', String(!ok));
    }
    box.addEventListener('input', build); build();
  });
  document.querySelectorAll('[data-copy]').forEach(function (b) {
    b.addEventListener('click', function () {
      var t = document.querySelector(b.dataset.copy).textContent, o = b.innerHTML;
      (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.resolve()).then(function () {
        b.innerHTML = '<i class="bi bi-check2"></i>Copié'; setTimeout(function () { b.innerHTML = o; }, 1600);
      });
    });
  });
})();
