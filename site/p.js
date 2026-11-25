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
  // marcas no jogador do campo: gols, cartões e minuto em que saiu
  const BOLA = '<svg viewBox="0 0 24 24" width="11" height="11" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#fff" stroke="#111" stroke-width="2"/><path d="M12 7l4 3-1.5 5h-5L8 10z" fill="#111"/></svg>';
  const marcas = p => {
    const st = p.st || {}; let m = '';
    for (let k = 0; k < Math.min(st.g || 0, 3); k++) m += `<i class="mk-g" title="Gol">${BOLA}</i>`;
    if (st.vm) m += '<i class="mk-c vm" title="Cartão vermelho"></i>'; else if (st.am) m += '<i class="mk-c am" title="Cartão amarelo"></i>';
    return m ? `<em class="mks">${m}</em>` : '';
  };
  function campo(es, casa, fora) {
    const fila = (ps, cls) => `<div class="fila">${ps.map(p => `<div class="jg ${cls}"><b>${esc(p.n)}${marcas(p)}</b><span>${esc(sobrenome(p.nome))}</span>${p.s ? `<small class="sai" title="Saiu aos ${esc(p.s)}">▼ ${esc(p.s)}</small>` : ''}</div>`).join('')}</div>`;
    const lc = linhas(es.casa), lf = linhas(es.fora);
    return `<div class="cp-tit"><span class="tf">${esc(fora)}${es.fora.esquema ? ' · ' + esc(es.fora.esquema) : ''}</span></div>
      <div class="gramado"><div class="meio"></div><div class="area a1"></div><div class="area a2"></div>
        <div class="metade m-fora">${lf.map(x => fila(x.slice().reverse(), 'fo')).join('')}</div>
        <div class="metade m-casa">${lc.slice().reverse().map(x => fila(x, 'ca')).join('')}</div></div>
      <div class="cp-tit"><span class="tc">${esc(casa)}${es.casa.esquema ? ' · ' + esc(es.casa.esquema) : ''}</span></div>`;
  }
  // substituições (lista do jogo) + quem não entrou + números de cada jogador
  function extrasEsc(es, casa, fora) {
    const subs = es.subs || [];
    const sb = l => subs.filter(x => x.l === l).map(x => `<li><b>${esc(x.m)}</b><span class="in">▲ ${esc(x.ent)}</span><span class="out">▼ ${esc(x.sai)}</span></li>`).join('');
    const htmlSubs = subs.length ? `<div class="subs"><h3>Substituições</h3><div class="esqs"><div><h4>${esc(casa)}</h4><ul>${sb('c') || '<li class="nd">Nenhuma</li>'}</ul></div><div><h4>${esc(fora)}</h4><ul>${sb('f') || '<li class="nd">Nenhuma</li>'}</ul></div></div></div>` : '';
    const banco = (x, n) => { const r = (x.reservas || []).filter(p => !p.e); return r.length ? `<div><h3>${esc(n)}</h3><p>${r.map(p => (p.n ? esc(p.n) + ' ' : '') + esc(p.nome)).join(', ')}</p></div>` : ''; };
    const b = banco(es.casa, casa) + banco(es.fora, fora);
    const htmlBanco = b ? `<details class="resv"><summary>Reservas que não entraram</summary><div class="esqs">${b}</div></details>` : '';
    return htmlSubs + estatJog(es, casa, fora) + htmlBanco;
  }
  const COLS = [['g', 'G', 'Gols'], ['a', 'A', 'Assistências'], ['ch', 'Fin', 'Finalizações'], ['cg', 'NG', 'Finalizações no gol'],
    ['fc', 'FC', 'Faltas cometidas'], ['fs', 'FS', 'Faltas sofridas'], ['imp', 'Imp', 'Impedimentos'], ['df', 'Def', 'Defesas (goleiro)']];
  function estatJog(es, casa, fora) {
    const jogou = x => [...(x.titulares || []), ...(x.reservas || []).filter(p => p.e)];
    const tem = [...jogou(es.casa), ...jogou(es.fora)].some(p => p.st && Object.keys(p.st).length);
    if (!tem) return '';
    const tab = (x, n) => {
      const ps = jogou(x).sort((a, b) => prof(a.pos) - prof(b.pos) || (a.e ? 1 : 0) - (b.e ? 1 : 0));
      const lin = ps.map(p => {
        const st = p.st || {};
        const cart = st.vm ? '<i class="mk-c vm" title="Cartão vermelho"></i>' : st.am ? '<i class="mk-c am" title="Cartão amarelo"></i>' : '';
        const tag = p.e ? ` <small class="in" title="Entrou aos ${esc(p.e)}">▲ ${esc(p.e)}</small>` : p.s ? ` <small class="out" title="Saiu aos ${esc(p.s)}">▼ ${esc(p.s)}</small>` : '';
        return `<tr><th scope="row"><span class="nj">${esc(p.n)}</span> ${esc(p.nome)}${cart}${tag}</th>${COLS.map(([k]) => `<td${st[k] ? ' class="v"' : ''}>${st[k] || (k === 'df' && !GOL.has(String(p.pos).toUpperCase()) ? '' : 0)}</td>`).join('')}</tr>`;
      }).join('');
      return `<h4>${esc(n)}</h4><div class="tbw"><table class="ej"><thead><tr><th scope="col">Jogador</th>${COLS.map(([, a, t]) => `<th scope="col" title="${t}"><abbr title="${t}">${a}</abbr></th>`).join('')}</tr></thead><tbody>${lin}</tbody></table></div>`;
    };
    return `<details class="ejs"><summary>Números dos jogadores</summary>${tab(es.casa, casa)}${tab(es.fora, fora)}
      <p class="leg">${COLS.map(([, a, t]) => `<b>${a}</b> ${t.toLowerCase()}`).join(' · ')}. Dados da ESPN.</p></details>`;
  }

  // mesmo formato do robô (robo/extras.py _lado e _substituicoes)
  const EST = { totalGoals: 'g', goalAssists: 'a', totalShots: 'ch', shotsOnTarget: 'cg', foulsCommitted: 'fc', foulsSuffered: 'fs',
    offsides: 'imp', yellowCards: 'am', redCards: 'vm', saves: 'df', goalsConceded: 'gs', ownGoals: 'gc' };
  const minSub = (p, ult) => { const m = (p.plays || []).filter(x => x.substitution).map(x => (x.clock || {}).displayValue).filter(Boolean); return m.length ? (ult ? m[m.length - 1] : m[0]) : '?'; };
  const lado = r => {
    const o = { titulares: [], reservas: [] };
    (r.roster || []).forEach(p => {
      const a = p.athlete || {}, pos = (p.position || {}).abbreviation || '';
      const it = { n: p.jersey || '', nome: a.shortName || a.displayName || '?', pos, fp: +p.formationPlace || 99 };
      if (p.subbedIn) it.e = minSub(p); if (p.subbedOut) it.s = minSub(p, true);
      const st = {}; (p.stats || []).forEach(x => { const k = EST[x.name], v = Math.trunc(+x.value || 0); if (k && v && !(k === 'gs' && !GOL.has(pos.toUpperCase()))) st[k] = v; });
      if (Object.keys(st).length) it.st = st;
      (p.starter ? o.titulares : o.reservas).push(it);
    });
    const f = r.formation; if (f) o.esquema = typeof f === 'string' ? f : (f.summary || f.name || '');
    return o;
  };
  const substituicoes = r => {
    const nomes = {}, ladoT = {};
    (r.rosters || []).forEach(x => { ladoT[String((x.team || {}).id)] = x.homeAway === 'home' ? 'c' : 'f';
      (x.roster || []).forEach(p => { const a = p.athlete || {}; if (a.id) nomes[String(a.id)] = a.shortName || a.displayName || '?'; }); });
    const nm = a => nomes[String(a.id)] || a.shortName || a.displayName || '?';
    return (r.keyEvents || []).filter(k => /substitution/i.test((k.type || {}).text || '')).map(k => {
      const ps = (k.participants || []).map(x => x.athlete || {});
      return ps.length < 2 ? null : { l: ladoT[String((k.team || {}).id)] || '', m: (k.clock || {}).displayValue || '', ent: nm(ps[0]), sai: nm(ps[1]) };
    }).filter(Boolean);
  };

  const box = $('.campo');
  if (box) {
    const dataEl = $('.escdata');
    const sec = box.closest('section');
    const mostrar = (es, casa, fora) => {
      box.innerHTML = campo(es, casa, fora);
      const ant = sec && sec.querySelector('.esc-extra'); if (ant) ant.remove();
      box.insertAdjacentHTML('afterend', `<div class="esc-extra">${extrasEsc(es, casa, fora)}</div>`);
      const lista = $('.esqs-txt'); if (lista) lista.classList.add('so-leitor');
      if (sec) sec.hidden = false;
    };
    let casa = box.dataset.casa, fora = box.dataset.fora, temDados = false;
    if (dataEl) {
      try { const es = JSON.parse(dataEl.textContent); casa = es.time_casa || casa; fora = es.time_fora || fora; mostrar(es, casa, fora); temDados = true; } catch (_) {}
    }
    // sem escalação guardada, ou jogo ainda não terminado: busca na ESPN direto do navegador
    // (a partir de 90 min antes; durante o jogo de minuto em minuto, para as substituições e os números)
    if (box.dataset.eid && box.dataset.lg && !box.dataset.final) {
      const ini = Date.parse(box.dataset.ini), fim = ini + 150 * 60e3;
      const url = `https://site.web.api.espn.com/apis/site/v2/sports/soccer/${box.dataset.lg}/summary?event=${box.dataset.eid}&region=br&lang=en`;
      const tentar = async () => {
        if (Date.now() < ini - 90 * 60e3) return false;
        try {
          const r = await (await fetch(url, { cache: 'no-store' })).json();
          const m = {}; (r.rosters || []).forEach(x => m[x.homeAway] = x);
          if (!m.home || !m.away) return false;
          const es = { casa: lado(m.home), fora: lado(m.away), subs: substituicoes(r) };
          if (es.casa.titulares.length < 11 || es.fora.titulares.length < 11) return false;
          mostrar(es, casa, fora);
          const n = $('.escnota'); if (n) n.textContent = 'Escalações oficiais.';
          return true;
        } catch (_) { return false; }
      };
      tentar().then(() => {
        if (Date.now() > fim) return; // jogo encerrado: uma consulta basta
        const t = setInterval(async () => { if (document.hidden) return; await tentar(); if (Date.now() > fim) clearInterval(t); },
          (temDados || Date.now() > ini - 5 * 60e3) ? 60e3 : 120e3);
      });
    }
  }
})();
