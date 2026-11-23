/* Onde Passa Jogo – páginas de jogo, time e campeonato: abas e escalações (campo desenhado). */
(function () {
  'use strict';
  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => [...(r || document).querySelectorAll(s)];
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  // ---------- abas (Tabela | Próximos jogos | Resultados)
  const abas = $$('.abas .aba');
  if (abas.length) {
    document.documentElement.classList.add('com-abas');
    const mostrar = (id, rolar) => {
      if (!abas.some(a => a.dataset.aba === id)) id = abas[0].dataset.aba;
      abas.forEach(a => { const on = a.dataset.aba === id; a.classList.toggle('on', on); a.setAttribute('aria-selected', on); });
      $$('.painel').forEach(p => { p.hidden = p.id !== id; });
      if (rolar) $('.abas').scrollIntoView({ block: 'nearest' });
    };
    abas.forEach(a => a.addEventListener('click', ev => { ev.preventDefault(); mostrar(a.dataset.aba); history.replaceState(null, '', '#' + a.dataset.aba); }));
    mostrar((location.hash || '').slice(1), false);
  }

  // ---------- escalações
  const GOL = new Set(['G', 'GK', 'GOL']);
  const ATA = new Set(['A', 'AC', 'AE', 'AD', 'CA', 'PE', 'PD', 'F', 'CF', 'ST', 'LW', 'RW', 'SS', 'FW', 'LF', 'RF']);
  const DEF = new Set(['LD', 'LE', 'LB', 'RB', 'CB', 'D', 'DF', 'RWB', 'LWB', 'SW', 'DC', 'CD-L', 'CD-R', 'ZC']);
  const linha = p => { const a = (p || '').toUpperCase(); if (GOL.has(a)) return 0; if (a[0] === 'Z' || DEF.has(a)) return 1; if (ATA.has(a)) return 3; return 2; };
  const sobrenome = n => { const p = String(n || '').split(' '); return p.length > 1 && p[0].length <= 3 ? p.slice(1).join(' ') : n; };

  function linhas(lado) {
    const l = [[], [], [], []];
    (lado.titulares || []).forEach(p => l[linha(p.pos)].push(p));
    l.forEach(x => x.sort((a, b) => (a.fp || 99) - (b.fp || 99)));
    return l.filter(x => x.length);
  }
  function campo(es, casa, fora) {
    const fila = (ps, cls) => `<div class="fila">${ps.map(p => `<div class="jg ${cls}"><b>${esc(p.n)}</b><span>${esc(sobrenome(p.nome))}</span></div>`).join('')}</div>`;
    const lc = linhas(es.casa), lf = linhas(es.fora);
    return `<div class="cp-tit"><span class="tf">${esc(fora)}${es.fora.esquema ? ' · ' + esc(es.fora.esquema) : ''}</span></div>
      <div class="gramado"><div class="meio"></div><div class="area a1"></div><div class="area a2"></div>
        <div class="metade m-fora">${lf.map(x => fila(x, 'fo')).join('')}</div>
        <div class="metade m-casa">${lc.slice().reverse().map(x => fila(x, 'ca')).join('')}</div></div>
      <div class="cp-tit"><span class="tc">${esc(casa)}${es.casa.esquema ? ' · ' + esc(es.casa.esquema) : ''}</span></div>`;
  }
  function reservas(es, casa, fora) {
    const r = (x, n) => x.reservas && x.reservas.length ? `<div><h3>${esc(n)}</h3><p>${x.reservas.map(p => (p.n ? esc(p.n) + ' ' : '') + esc(p.nome)).join(', ')}</p></div>` : '';
    return `<details class="resv"><summary>Reservas</summary><div class="esqs">${r(es.casa, casa)}${r(es.fora, fora)}</div></details>`;
  }

  const box = $('.campo');
  if (box) {
    const dataEl = $('.escdata');
    const titulo = $('h1') ? $('h1').textContent : '';
    if (dataEl) {
      try {
        const es = JSON.parse(dataEl.textContent);
        box.innerHTML = campo(es, es.time_casa, es.time_fora);
        const lista = $('.esqs-txt'); if (lista) lista.classList.add('so-leitor');
        box.insertAdjacentHTML('afterend', reservas(es, es.time_casa, es.time_fora));
      } catch (_) {}
    } else if (box.dataset.eid && box.dataset.lg) {
      // ainda não saiu: a partir de 90 min antes, consulta a ESPN direto do navegador a cada 2 minutos
      const ini = Date.parse(box.dataset.ini);
      const url = `https://site.web.api.espn.com/apis/site/v2/sports/soccer/${box.dataset.lg}/summary?event=${box.dataset.eid}&region=br&lang=pt`;
      const lado = r => {
        const o = { titulares: [], reservas: [] };
        (r.roster || []).forEach(p => {
          const a = p.athlete || {}, it = { n: p.jersey || '', nome: a.shortName || a.displayName || '?', pos: (p.position || {}).abbreviation || '', fp: +p.formationPlace || 99 };
          (p.starter ? o.titulares : o.reservas).push(it);
        });
        const f = r.formation; if (f) o.esquema = typeof f === 'string' ? f : (f.summary || f.name || '');
        return o;
      };
      const tentar = async () => {
        const agora = Date.now();
        if (agora < ini - 90 * 60e3 || agora > ini + 150 * 60e3) return false;
        try {
          const r = await (await fetch(url, { cache: 'no-store' })).json();
          const m = {}; (r.rosters || []).forEach(x => m[x.homeAway] = x);
          if (!m.home || !m.away) return false;
          const es = { casa: lado(m.home), fora: lado(m.away) };
          if (es.casa.titulares.length < 11 || es.fora.titulares.length < 11) return false;
          box.innerHTML = campo(es, box.dataset.casa, box.dataset.fora);
          box.insertAdjacentHTML('afterend', reservas(es, box.dataset.casa, box.dataset.fora));
          const n = $('.escnota'); if (n) n.textContent = 'Escalações oficiais.';
          return true;
        } catch (_) { return false; }
      };
      tentar().then(ok => { if (!ok) { const t = setInterval(async () => { if (await tentar()) clearInterval(t); }, 120e3); } });
    }
  }
})();
