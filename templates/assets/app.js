// Filtres et tri du rapport (100% côté client, aucun réseau requis).
(function () {
  const grid = document.getElementById('grid');
  const q = document.getElementById('q');
  const fSell = document.getElementById('f-sellable');
  const fSrc = document.getElementById('f-source');
  const fGroup = document.getElementById('f-group');
  const sort = document.getElementById('sort');
  const count = document.getElementById('count');

  if (grid && q) {
    const cards = Array.from(grid.children);

    const apply = () => {
      const term = q.value.trim().toLowerCase();
      const sell = fSell.value, src = fSrc.value, grp = fGroup.value;
      let shown = 0;
      cards.forEach(c => {
        const okTerm = !term || c.dataset.title.includes(term);
        const okSell = !sell || c.dataset.sellable === sell;
        const okSrc = !src || c.querySelector('.badge.source').textContent.trim() === src;
        const okGrp = !grp || c.dataset.group === grp;
        const ok = okTerm && okSell && okSrc && okGrp;
        c.style.display = ok ? '' : 'none';
        if (ok) shown++;
      });
      count.textContent = shown + ' / ' + cards.length + ' modèles affichés';
    };

    const applySort = () => {
      const key = sort.value;
      const sorted = cards.slice().sort((a, b) => {
        if (key === 'title') return a.dataset.title.localeCompare(b.dataset.title);
        return (+b.dataset[key] || 0) - (+a.dataset[key] || 0);
      });
      sorted.forEach(c => grid.appendChild(c));
    };

    [q, fSell, fSrc, fGroup].forEach(el => el && el.addEventListener('input', apply));
    sort && sort.addEventListener('change', applySort);
    apply();
  }

  // « Relancer » est un simple lien vers _setup : aucun JS, donc rien à
  // intercepter (un app.js gardé en cache ne peut pas relancer tout seul).

  // page « par famille » : filtre du sommaire
  const qg = document.getElementById('q-group');
  if (qg) {
    qg.addEventListener('input', () => {
      const term = qg.value.trim().toLowerCase();
      document.querySelectorAll('.group').forEach(sec => {
        sec.style.display = !term || sec.dataset.label.includes(term) ? '' : 'none';
      });
      document.querySelectorAll('.toc li').forEach(li => {
        li.style.display = !term || li.textContent.toLowerCase().includes(term) ? '' : 'none';
      });
    });
  }
})();
