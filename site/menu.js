// Menu do site: abre a gaveta pelos botões [data-menu] e fecha no X, no Esc, tocando fora ou num link.
(() => {
  const dlg = document.getElementById('menu');
  if (!dlg || typeof dlg.showModal !== 'function') return; // navegador muito antigo: os links do rodapé continuam lá
  const raiz = document.documentElement;
  const naHome = location.pathname === '/' || location.pathname === '/index.html';
  let origem = null;

  function abrir(btn) {
    origem = btn || null;
    const av = dlg.querySelector('[data-menu-avisos]');
    if (av && naHome && window.OPJ) av.hidden = !window.OPJ.avisosOk();
    dlg.showModal();
    raiz.classList.add('mn-aberto');
    document.querySelectorAll('[data-menu]').forEach(b => b.setAttribute('aria-expanded', 'true'));
  }
  function fechar() { if (dlg.open) dlg.close(); }
  dlg.addEventListener('close', () => {
    raiz.classList.remove('mn-aberto');
    document.querySelectorAll('[data-menu]').forEach(b => b.setAttribute('aria-expanded', 'false'));
    if (origem && document.contains(origem) && origem.offsetParent) origem.focus({ preventScroll: true });
  });

  document.addEventListener('click', e => {
    const b = e.target.closest('[data-menu]');
    if (b) { e.preventDefault(); abrir(b); return; }
    if (!dlg.open) return;
    if (e.target === dlg || e.target.closest('[data-menu-fechar]')) { fechar(); return; } // toque no fundo escuro
    const a = e.target.closest('a');
    if (!a || !dlg.contains(a)) return;
    // na página inicial, "Meus times" e "Avisos" abrem direto, sem recarregar
    if (naHome && window.OPJ && a.hasAttribute('data-menu-seguindo')) { e.preventDefault(); fechar(); window.OPJ.seguindo(); return; }
    if (naHome && window.OPJ && a.hasAttribute('data-menu-avisos')) { e.preventDefault(); fechar(); window.OPJ.avisos(); return; }
    if (a.target !== '_blank') fechar();
  });
})();
