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
  // Monta as linhas pelo esquema que a ESPN informa (ex.: 3-4-3): ordena os jogadores do mais recuado
  // ao mais adiantado pela sigla da posição e preenche as linhas com a quantidade de cada uma.
  const GOL = new Set(['G', 'GK', 'GOL']);
  const PROF = [[/^(CD|CB|SW|D|DF)(-[LR])?$|^Z/, 1], [/^(RB|LB|LD|LE)$/, 1.1], [/^(RWB|LWB)$/, 1.3], [/^DM|^VOL/, 2],
    [/^CM|^MC/, 3], [/^(RM|LM|M|MD|ME)$/, 3.2], [/^AM|^MA|^MEI/, 4], [/^(RCF|LCF)$/, 4.2], [/^(RW|LW|RF|LF|PD|PE|AD|AE)$/, 4.4],
    [/^CF-|^SS$|^ATC|^ACI/, 4.6], [/^(F|CF|ST|FW|A|CA)$/, 5]];
  const prof = p => { const a = (p || '').toUpperCase(); if (GOL.has(a)) return 0; for (const [r, v] of PROF) if (r.test(a)) return v; return 3; };
  // posição na largura do campo, do ponto de vista do time: -2 ponta/lateral esquerdo, -1 centro-esquerda,
  // 0 centro, 1 centro-direita, 2 ponta/lateral direito (siglas em inglês)
  const ladoDe = p => { const a = (p || '').toUpperCase();
    if (/^R(B|WB|M|W|F)$/.test(a)) return 2; if (/^L(B|WB|M|W|F)$/.test(a)) return -2;
    if (/-R$/.test(a)) return 1; if (/-L$/.test(a)) return -1; return 0; };
  const sobrenome = n => { const p = String(n || '').split(' '); return p.length > 1 && p[0].length <= 3 ? p.slice(1).join(' ') : n; };

  // devolve as linhas do goleiro para o ataque; cada linha vai da esquerda para a direita do time
  function linhas(lado) {
    const tit = (lado.titulares || []).slice().sort((a, b) => (a.fp || 99) - (b.fp || 99));
    let gol = tit.filter(p => prof(p.pos) === 0), resto = tit.filter(p => prof(p.pos) !== 0);
    if (!gol.length && resto.length) gol = [resto.shift()];
    resto.sort((a, b) => prof(a.pos) - prof(b.pos) || (a.fp || 99) - (b.fp || 99));
    const qtd = String(lado.esquema || '').split('-').map(Number).filter(n => n > 0);
    let ls = [];
    if (qtd.length >= 2 && qtd.reduce((s, n) => s + n, 0) === resto.length) {
      let i = 0; qtd.forEach(n => { ls.push(resto.slice(i, i + n)); i += n; });
    } else { // sem esquema: defesa, meio e ataque pela posição
      const f = [[], [], []]; resto.forEach(p => { const v = prof(p.pos); f[v < 1.5 ? 0 : v < 4.3 ? 1 : 2].push(p); }); ls = f;
    }
    ls = ls.filter(x => x.length).map(x => x.sort((a, b) => ladoDe(a.pos) - ladoDe(b.pos)));
    return [gol, ...ls].filter(x => x.length);
  }
  function campo(es, casa, fora) {
    const fila = (ps, cls) => `<div class="fila">${ps.map(p => `<div class="jg ${cls}"><b>${esc(p.n)}</b><span>${esc(sobrenome(p.nome))}</span></div>`).join('')}</div>`;
    const lc = linhas(es.casa), lf = linhas(es.fora);
    return `<div class="cp-tit"><span class="tf">${esc(fora)}${es.fora.esquema ? ' · ' + esc(es.fora.esquema) : ''}</span></div>
      <div class="gramado"><div class="meio"></div><div class="area a1"></div><div class="area a2"></div>
        <div class="metade m-fora">${lf.map(x => fila(x.slice().reverse(), 'fo')).join('')}</div>
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
      // escalação não guardada: a partir de 90 min antes, consulta a ESPN direto do navegador (também depois do jogo)
      const ini = Date.parse(box.dataset.ini);
      const url = `https://site.web.api.espn.com/apis/site/v2/sports/soccer/${box.dataset.lg}/summary?event=${box.dataset.eid}&region=br&lang=en`;
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
        if (agora < ini - 90 * 60e3) return false;
        try {
          const r = await (await fetch(url, { cache: 'no-store' })).json();
          const m = {}; (r.rosters || []).forEach(x => m[x.homeAway] = x);
          if (!m.home || !m.away) return false;
          const es = { casa: lado(m.home), fora: lado(m.away) };
          if (es.casa.titulares.length < 11 || es.fora.titulares.length < 11) return false;
          box.innerHTML = campo(es, box.dataset.casa, box.dataset.fora);
          box.insertAdjacentHTML('afterend', reservas(es, box.dataset.casa, box.dataset.fora));
          const n = $('.escnota'); if (n) n.textContent = 'Escalações oficiais.';
          const sec = box.closest('section'); if (sec) sec.hidden = false;
          return true;
        } catch (_) { return false; }
      };
      // depois do jogo (mais de 2h30 do início) basta uma consulta; antes, tenta de novo a cada 2 minutos
      tentar().then(ok => { if (!ok && Date.now() < ini + 150 * 60e3) { const t = setInterval(async () => { if (await tentar() || Date.now() > ini + 150 * 60e3) clearInterval(t); }, 120e3); } });
    }
  }
})();
