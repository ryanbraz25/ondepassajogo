/* Lembrete por jogo ("Avisar 1 hora antes") e botão "Adicionar à minha agenda".

   Os jogos marcados ficam no aparelho (localStorage "lembretes" = {caminho da página do jogo: início ISO})
   e, com os avisos ligados, também no Firestore (campo "jogos" do inscrito). O robô (robo/avisos.py)
   manda o aviso cerca de 1 hora antes. Sem avisos ligados, o toque marca o jogo e pede para ligar:
   quando a pessoa liga, a página inicial já manda os jogos marcados junto. */
(() => {
  'use strict';
  const CHAVE = 'lembretes', MAX = 30;

  const gravar = o => { try { localStorage.setItem(CHAVE, JSON.stringify(o)); } catch (_) {} };
  function ler() {
    let o = {};
    try { o = JSON.parse(localStorage.getItem(CHAVE) || '{}') || {}; } catch (_) {}
    const limite = Date.now() - 3 * 3600e3; // jogo que já passou sai sozinho
    let mudou = false;
    Object.keys(o).forEach(k => { if (!(Date.parse(o[k]) > limite)) { delete o[k]; mudou = true; } });
    if (mudou) gravar(o);
    return o;
  }
  const lista = () => Object.entries(ler()).sort((a, b) => Date.parse(a[1]) - Date.parse(b[1])).slice(0, MAX).map(x => x[0]);
  const avisos = () => { try { return JSON.parse(localStorage.getItem('avisos') || 'null'); } catch (_) { return null; } };
  const suportado = () => ('serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window)
    || /iP(hone|ad|od)/.test(navigator.userAgent);

  // ---------- aviso rápido na tela (com botão opcional)
  let caixa = null, tempo = 0;
  function aviso(msg, acao) {
    if (!caixa) {
      caixa = document.createElement('div');
      caixa.className = 'lemb-aviso';
      caixa.setAttribute('role', 'status');
      caixa.setAttribute('aria-live', 'polite');
      document.body.appendChild(caixa);
    }
    caixa.innerHTML = '';
    caixa.append(Object.assign(document.createElement('span'), { textContent: msg }));
    if (acao) caixa.append(Object.assign(document.createElement('a'), { href: acao.href, textContent: acao.texto }));
    caixa.classList.add('on');
    clearTimeout(tempo);
    tempo = setTimeout(() => caixa.classList.remove('on'), acao ? 8000 : 3500);
  }

  // ---------- Firestore: grava só o campo "jogos" do documento que a página inicial criou ao ligar os avisos
  let cfg = null;
  const config = () => cfg || (cfg = window.OPJ_PUSH ? Promise.resolve(window.OPJ_PUSH)
    : fetch('/dados/push.json').then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }));
  async function salvarNuvem() {
    const a = avisos();
    if (!a || !a.id) return;
    const c = (await config()).cfg;
    const js = lista();
    const url = `https://firestore.googleapis.com/v1/projects/${c.projectId}/databases/(default)/documents/inscritos/${a.id}`
      + `?key=${encodeURIComponent(c.apiKey)}&updateMask.fieldPaths=jogos&updateMask.fieldPaths=atualizado&currentDocument.exists=true`;
    const r = await fetch(url, {
      method: 'PATCH', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ fields: {
        jogos: js.length ? { arrayValue: { values: js.map(x => ({ stringValue: x })) } } : { arrayValue: {} },
        atualizado: { stringValue: new Date().toISOString() } } })
    });
    if (!r.ok) throw new Error('Firestore ' + r.status);
  }

  // ---------- botões "Avisar 1 hora antes"
  function pintar(raiz) {
    const o = ler(), agora = Date.now(), ok = suportado();
    (raiz || document).querySelectorAll('[data-lemb]').forEach(b => {
      const ini = Date.parse(b.dataset.ini);
      b.hidden = !ok || !(ini - agora > 5 * 60e3); // só jogo que ainda vai começar
      const on = !!o[b.dataset.lemb];
      b.classList.toggle('on', on);
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
      const t = b.querySelector('.lemb-t');
      const txt = on ? 'Aviso marcado' : (b.dataset.curto ? 'Avisar' : 'Avisar 1 hora antes');
      if (t && t.textContent !== txt) t.textContent = txt; // só muda se precisar (o observador abaixo vigia a página)
      b.title = on ? 'Você vai receber um aviso 1 hora antes. Toque para desmarcar.' : 'Receber um aviso no celular 1 hora antes do jogo';
    });
  }

  function alternar(b) {
    const pg = b.dataset.lemb, ini = b.dataset.ini, o = ler();
    const ligar = !o[pg];
    if (ligar && Object.keys(o).length >= MAX) { aviso(`Você já marcou ${MAX} jogos. Desmarque algum para marcar este.`); return; }
    if (ligar) o[pg] = ini; else delete o[pg];
    gravar(o);
    pintar();
    try { window.gtag && gtag('event', ligar ? 'lembrete_marcado' : 'lembrete_desmarcado'); } catch (_) {}
    if (!avisos()) {
      if (!ligar) return;
      // sem avisos ligados: o jogo fica marcado aqui e vai junto quando a pessoa ligar os avisos
      if (window.OPJ && window.OPJ.avisos) { window.OPJ.avisos(); return; }
      aviso('Jogo marcado. Falta ligar os avisos no celular.', { href: '/?utm_source=lembrete#avisos', texto: 'Ligar avisos' });
      return;
    }
    salvarNuvem().then(() => aviso(ligar ? 'Combinado! Você recebe um aviso 1 hora antes do jogo.' : 'Aviso desmarcado.'))
      .catch(() => {
        const v = ler();
        if (ligar) delete v[pg]; else v[pg] = ini;
        gravar(v);
        pintar();
        aviso('Não deu para salvar agora. Tente de novo em instantes.');
      });
  }

  // ---------- "Adicionar à minha agenda": copiar o link do calendário
  async function copiar(b) {
    const url = b.dataset.copiar;
    try { await navigator.clipboard.writeText(url); aviso('Link copiado. Cole na opção "assinar calendário" ou "adicionar por URL" do seu app.'); }
    catch (_) { window.prompt('Copie o link do calendário:', url); }
  }

  document.addEventListener('click', e => {
    const b = e.target.closest('[data-lemb]');
    if (b) { e.preventDefault(); alternar(b); return; }
    const c = e.target.closest('[data-copiar]');
    if (c) { e.preventDefault(); copiar(c); return; }
    const a = e.target.closest('.agd-op a');
    if (a) { try { window.gtag && gtag('event', 'agenda_assinada', { app: a.dataset.app || '' }); } catch (_) {} }
  });
  // a página inicial redesenha a lista o tempo todo: pinta os botões novos assim que aparecem
  new MutationObserver(ms => { if (ms.some(m => m.addedNodes.length)) pintar(); })
    .observe(document.body, { childList: true, subtree: true });
  pintar();
  // /time/<time>/#agenda (link da página inicial, na lista de quem a pessoa segue): já abre as opções
  if (location.hash === '#agenda') {
    const d = document.querySelector('details.agd');
    if (d) { d.open = true; d.id = d.id || 'agenda'; d.scrollIntoView({ block: 'center' }); d.querySelector('summary').focus({ preventScroll: true }); }
  }
  window.OPJLembretes = { lista, pintar };
})();
