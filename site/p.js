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
  const BOLA = '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#fff" stroke="#111" stroke-width="2"/><path d="M12 7l4 3-1.5 5h-5L8 10z" fill="#111"/></svg>';
  const marcas = p => {
    const st = p.st || {}; let m = '';
    for (let k = 0; k < Math.min(st.g || 0, 3); k++) m += `<i class="mk-g" title="Gol">${BOLA}</i>`;
    if (st.vm) m += '<i class="mk-c vm" title="Cartão vermelho"></i>'; else if (st.am) m += '<i class="mk-c am" title="Cartão amarelo"></i>';
    return m ? `<em class="mks">${m}</em>` : '';
  };
  const chave = p => p.id || ('n' + p.n + '-' + p.nome);
  function campo(es, casa, fora) {
    const fila = (ps, cls) => `<div class="fila">${ps.map(p => `<button type="button" class="jg ${cls}" data-j="${cls === 'ca' ? 'c' : 'f'}:${esc(chave(p))}" aria-label="${esc(p.nome)}: ver os números no jogo"><b>${esc(p.n)}${marcas(p)}</b><span>${esc(sobrenome(p.nome))}</span>${p.s ? `<small class="sai">▼ ${esc(p.s)}</small>` : ''}</button>`).join('')}</div>`;
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
    const achar = (l, nome) => { const x = l === 'c' ? es.casa : es.fora; return [...(x.titulares || []), ...(x.reservas || [])].find(p => p.nome === nome); };
    const nomeJ = (l, nome, cls) => { const p = achar(l, nome); return p ? `<button type="button" class="jl ${cls}" data-j="${l}:${esc(chave(p))}">${cls === 'in' ? '▲' : '▼'} ${esc(nome)}</button>` : `<span class="${cls}">${cls === 'in' ? '▲' : '▼'} ${esc(nome)}</span>`; };
    const sb = l => subs.filter(x => x.l === l).map(x => `<li><b>${esc(x.m)}</b>${nomeJ(l, x.ent, 'in')}${nomeJ(l, x.sai, 'out')}</li>`).join('');
    const htmlSubs = subs.length ? `<div class="subs"><h3>Substituições</h3><div class="esqs"><div><h4>${esc(casa)}</h4><ul>${sb('c') || '<li class="nd">Nenhuma</li>'}</ul></div><div><h4>${esc(fora)}</h4><ul>${sb('f') || '<li class="nd">Nenhuma</li>'}</ul></div></div></div>` : '';
    const banco = (x, n) => { const r = (x.reservas || []).filter(p => !p.e); return r.length ? `<div><h3>${esc(n)}</h3><p>${r.map(p => (p.n ? esc(p.n) + ' ' : '') + esc(p.nome)).join(', ')}</p></div>` : ''; };
    const b = banco(es.casa, casa) + banco(es.fora, fora);
    const htmlBanco = b ? `<details class="resv"><summary>Reservas que não entraram</summary><div class="esqs">${b}</div></details>` : '';
    const temNum = [...(es.casa.titulares || []), ...(es.fora.titulares || [])].some(p => p.st);
    return (temNum ? '<p class="dica">Toque num jogador para ver os números dele no jogo.</p>' : '') + htmlSubs + htmlBanco;
  }

  // janelinha do jogador (como no SofaScore): o que ele fez no jogo, com os dados da ESPN
  const POS = [[/^(G|GK)$/, 'Goleiro'], [/^(CD|CB|SW)(-[LR])?$/, 'Zagueiro'], [/^(RB|LB)$/, 'Lateral'], [/^(RWB|LWB)$/, 'Ala'],
    [/^DM/, 'Volante'], [/^CM/, 'Meio-campista'], [/^(RM|LM|M)$/, 'Meia'], [/^AM/, 'Meia ofensivo'], [/^(RW|LW|RF|LF)$/, 'Ponta'],
    [/^(F|CF|ST|FW|SS|RCF|LCF)(-[LR])?$/, 'Atacante']];
  const posNome = p => { const a = String(p || '').toUpperCase(); for (const [r, n] of POS) if (r.test(a)) return n; return ''; };
  const LINHAS = [['ch', 'Finalizações'], ['cg', 'Finalizações no gol'], ['fs', 'Faltas sofridas'], ['fc', 'Faltas cometidas'],
    ['imp', 'Impedimentos'], ['df', 'Defesas'], ['gs', 'Gols sofridos'], ['gc', 'Gols contra']];
  let jan = null, atual = null, jogoEs = null, nomesT = {};
  function fichaJogador(lado, k) {
    const x = lado === 'c' ? jogoEs.casa : jogoEs.fora, time = nomesT[lado];
    const p = [...(x.titulares || []), ...(x.reservas || [])].find(q => chave(q) === k); if (!p) return '';
    const st = p.st || {}, gk = GOL.has(String(p.pos).toUpperCase());
    const sub = (jogoEs.subs || []).filter(s => s.l === lado);
    const entrou = p.e ? sub.find(s => s.ent === p.nome) : null, saiu = p.s ? sub.find(s => s.sai === p.nome) : null;
    const tempo = p.e ? `Entrou aos ${esc(p.e)}${entrou ? ` no lugar de ${esc(entrou.sai)}` : ''}` + (p.s ? `; saiu aos ${esc(p.s)}` : '')
      : p.s ? `Titular; saiu aos ${esc(p.s)}${saiu ? ` (entrou ${esc(saiu.ent)})` : ''}` : (jogoEs.casa.titulares || []).concat(jogoEs.fora.titulares || []).includes(p) ? 'Titular' : 'Não entrou';
    const cart = st.vm ? '<span class="jc vm">Cartão vermelho</span>' : st.am ? '<span class="jc am">Cartão amarelo</span>' : '';
    const linhas = LINHAS.filter(([c]) => (c !== 'df' && c !== 'gs') || gk).filter(([c]) => c !== 'gc' || st.gc)
      .map(([c, n]) => `<li><span>${n}</span><b${st[c] ? ' class="v"' : ''}>${st[c] || 0}</b></li>`).join('');
    // sem nenhum número no jogo (a ESPN não publicou, ou ainda está carregando): não mostra zeros
    const todos = [jogoEs.casa, jogoEs.fora].flatMap(t => [...(t.titulares || []), ...(t.reservas || [])]);
    const temNum = todos.some(q => q.st && Object.keys(q.st).length);
    const numeros = temNum ? `<div class="jgs"><div><b>${st.g || 0}</b><span>${(st.g || 0) === 1 ? 'Gol' : 'Gols'}</span></div><div><b>${st.a || 0}</b><span>${(st.a || 0) === 1 ? 'Assistência' : 'Assistências'}</span></div></div>
      <ul class="jls">${linhas}</ul><p class="jf">Dados da ESPN${box && !box.dataset.final && Date.now() < Date.parse(box.dataset.ini) + 150 * 60e3 ? ', atualizados durante o jogo' : ''}.</p>`
      : '<p class="jf">A ESPN ainda não publicou os números dos jogadores deste jogo.</p>';
    return `<div class="jh"><b class="jn ${lado === 'c' ? 'ca' : 'fo'}">${esc(p.n)}</b><div><h3 id="jan-t">${esc(p.nome)}</h3>
        <p>${[posNome(p.pos), esc(time)].filter(Boolean).join(' · ')}</p></div>
        <button type="button" class="jx" aria-label="Fechar">×</button></div>
      <p class="jt">${tempo}</p>${cart}${numeros}`;
  }
  function abrirJogador(dj) {
    const [lado, k] = dj.split(/:(.*)/s);
    if (!jan) {
      jan = document.createElement('dialog'); jan.className = 'jan'; jan.setAttribute('aria-labelledby', 'jan-t');
      document.body.appendChild(jan);
      jan.addEventListener('click', e => { if (e.target === jan || e.target.closest('.jx')) jan.close(); });
      jan.addEventListener('close', () => { atual = null; });
    }
    const h = fichaJogador(lado, k); if (!h) return;
    atual = dj; jan.innerHTML = `<div class="jbox">${h}</div>`;
    if (!jan.open) jan.showModal();
  }
  document.addEventListener('click', e => { const b = e.target.closest('[data-j]'); if (b && jogoEs) { e.preventDefault(); abrirJogador(b.dataset.j); } });

  // mesmo formato do robô (robo/extras.py _lado e _substituicoes)
  const EST = { totalGoals: 'g', goalAssists: 'a', totalShots: 'ch', shotsOnTarget: 'cg', foulsCommitted: 'fc', foulsSuffered: 'fs',
    offsides: 'imp', yellowCards: 'am', redCards: 'vm', saves: 'df', goalsConceded: 'gs', ownGoals: 'gc' };
  const minSub = (p, ult) => { const m = (p.plays || []).filter(x => x.substitution).map(x => (x.clock || {}).displayValue).filter(Boolean); return m.length ? (ult ? m[m.length - 1] : m[0]) : '?'; };
  const lado = r => {
    const o = { titulares: [], reservas: [] };
    (r.roster || []).forEach(p => {
      const a = p.athlete || {}, pos = (p.position || {}).abbreviation || '';
      const it = { n: p.jersey || '', nome: a.shortName || a.displayName || '?', pos, fp: +p.formationPlace || 99 }; if (a.id) it.id = String(a.id);
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
      jogoEs = es; nomesT = { c: casa, f: fora };
      box.innerHTML = campo(es, casa, fora);
      if (atual && jan && jan.open) { const h = fichaJogador(...atual.split(/:(.*)/s)); if (h) jan.innerHTML = `<div class="jbox">${h}</div>`; }
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
