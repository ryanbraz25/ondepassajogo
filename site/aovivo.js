/* Ao vivo, direto da ESPN (grátis, sem chave):
   1) página do jogo: placar, tempo de jogo, gols e expulsões enquanto o jogo acontece;
   2) tabelas: reordena a classificação com os jogos em andamento (tabela provisória, como no ge). */
(() => {
  'use strict';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const API = 'https://site.api.espn.com/apis/';
  const respostas = {}; // a mesma resposta serve para a página e para as tabelas por 45 s
  const pega = url => {
    const c = respostas[url];
    if (c && Date.now() - c.t < 45e3) return c.p;
    const p = fetch(url, { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
    respostas[url] = { t: Date.now(), p };
    p.catch(() => { delete respostas[url]; });
    return p;
  };
  const estado = ev => (((ev.status || (ev.competitions && ev.competitions[0].status) || {}).type) || {}).state;
  const lados = cp => { const t = {}; (cp.competitors || []).forEach(c => { t[c.homeAway] = c; }); return t; };

  // ---------------------------------------------------------------- 1) página do jogo
  const BOLA = '<svg class="lb" width="16" height="16" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="10" fill="#fff" stroke="currentColor" stroke-width="1.5"/><path d="M12 7l3.8 2.8-1.45 4.45h-4.7L8.2 9.8Z" fill="currentColor"/><path d="M12 2v5M15.8 9.8l5.2-1.7M14.35 14.25l3.1 4.3M9.65 14.25l-3.1 4.3M8.2 9.8 3 8.1" fill="none" stroke="currentColor" stroke-width="1.4"/></svg>';
  const CARTAO = '<svg class="lb" width="15" height="15" viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="3" width="12" height="18" rx="2" fill="#e3242b"/></svg>';

  function tempo(st) {
    const ty = st.type || {};
    if (ty.state === 'post') return 'Encerrado';
    const d = (ty.description || '').toLowerCase(), curto = ty.shortDetail || '';
    if (/half ?time|halftime/.test(d) || curto === 'HT') return 'Intervalo';
    if (/penalt|shootout/.test(d)) return 'Disputa de pênaltis';
    const relogio = /\d/.test(st.displayClock || '') ? st.displayClock.replace(/'\+/, '+') : curto;
    const p = st.period || 0;
    const parte = p === 1 ? '1º tempo' : p === 2 ? '2º tempo' : p >= 3 ? 'Prorrogação' : '';
    return [parte, /\d/.test(relogio) ? relogio : ''].filter(Boolean).join(' · ') || 'Ao vivo';
  }

  function lancesHtml(cp, t, casa, fora) {
    const lado = {}; if (t.home) lado[t.home.team.id] = 'c'; if (t.away) lado[t.away.team.id] = 'f';
    return (cp.details || []).map(d => {
      const tipo = ((d.type && d.type.text) || '').toLowerCase();
      if (/shootout/.test(tipo)) return '';
      const k = d.scoringPlay ? (d.ownGoal ? 'c' : d.penaltyKick ? 'p' : 'g') : /red/.test(tipo) ? 'v' : '';
      const l = lado[(d.team || {}).id];
      if (!k || !l) return '';
      const a = (d.athletesInvolved || [])[0] || {};
      const m = ((d.clock || {}).displayValue || '').replace(/'\+/, '+').replace(/'$/, '') + "'";
      const extra = k === 'p' ? ' (pênalti)' : k === 'c' ? ' (contra)' : '';
      return `<li class="l${l}${k === 'v' ? ' lv' : ''}"><span class="lm">${esc(m)}</span>${k === 'v' ? CARTAO : BOLA}<span class="ln">${esc(a.shortName || a.displayName || '')}${extra}</span><span class="so-leitor"> (${k === 'v' ? 'expulso' : 'gol'} do ${esc(l === 'c' ? casa : fora)})</span></li>`;
    }).join('');
  }

  function desenharJogo(pl, ev) {
    const cp = ev.competitions[0], st = ev.status || cp.status || {}, t = lados(cp);
    if (estado(ev) === 'pre' || !t.home || !t.away) return false;
    const fim = estado(ev) === 'post';
    const hr = pl.querySelector('.hr');
    const b = hr.querySelector('b');
    b.className = 'pl';
    b.textContent = `${t.home.score} x ${t.away.score}`;
    const pen = t.home.shootoutScore != null && t.away.shootoutScore != null ? ` · pênaltis ${t.home.shootoutScore} x ${t.away.shootoutScore}` : '';
    hr.querySelector('small').textContent = tempo(st) + pen;
    pl.classList.toggle('aovivo', !fim);
    const s = document.getElementById('st');
    if (s) {
      s.hidden = false;
      s.className = fim ? 'status fim' : 'status live';
      s.textContent = fim ? 'Fim de jogo' : 'Ao vivo';
    }
    const nomes = [...pl.querySelectorAll('.tm span')].map(x => x.textContent);
    const sec = document.querySelector('.lances');
    if (sec) {
      const html = lancesHtml(cp, t, nomes[0], nomes[1]);
      if (html) { sec.querySelector('ul').innerHTML = html; sec.hidden = false; }
    }
    return fim;
  }

  const placa = document.querySelector('.placa[data-eid][data-lg]');
  if (placa) {
    const ini = Date.parse(placa.dataset.ini);
    const url = `${API}site/v2/sports/soccer/${placa.dataset.lg}/scoreboard${placa.dataset.ed ? '?dates=' + placa.dataset.ed : ''}`;
    const vez = async () => {
      const agora = Date.now();
      if (agora > ini + 4 * 3600e3) return;
      if (agora < ini - 10 * 60e3) { setTimeout(vez, Math.min(ini - 10 * 60e3 - agora, 30 * 60e3)); return; }
      let acabou = false;
      try {
        const r = await pega(url);
        const ev = (r.events || []).find(x => String(x.id) === placa.dataset.eid);
        if (ev) acabou = desenharJogo(placa, ev);
      } catch (_) {}
      if (!acabou) setTimeout(vez, 45e3);
    };
    vez();
  }

  // ---------------------------------------------------------------- 2) tabela ao vivo
  const fotos = new WeakMap(); // tabela -> como ela veio do robô (para voltar quando não houver jogo)
  const num = x => parseInt(String(x).replace('+', ''), 10) || 0;

  function foto(tb) {
    if (fotos.has(tb)) return fotos.get(tb);
    const linhas = [...tb.tBodies[0].rows].map((tr, i) => {
      const s = {}; tr.querySelectorAll('[data-s]').forEach(td => { s[td.dataset.s] = num(td.textContent); });
      return { tr, tid: tr.dataset.tid, o: i, s };
    });
    const faixas = linhas.map(l => ({ zn: l.tr.classList.contains('zn'), style: l.tr.getAttribute('style'), title: (l.tr.cells[0].querySelector('span') || {}).title || '' }));
    const f = { linhas, faixas, mexida: false };
    fotos.set(tb, f);
    return f;
  }

  function aviso(tb, ligar) {
    const caixa = tb.closest('.tabwrap, .tbw') || tb;
    let p = caixa.previousElementSibling;
    if (!(p && p.classList.contains('tvivo-aviso'))) p = null;
    if (ligar && !p) caixa.insertAdjacentHTML('beforebegin', '<p class="tvivo-aviso"><span></span>Tabela ao vivo: já conta os jogos em andamento (provisória)</p>');
    if (!ligar && p) p.remove();
  }

  function desenhar(tb, f, linhas) {
    linhas.forEach((l, i) => {
      const tr = l.tr, fx = f.faixas[i];
      tr.classList.toggle('zn', fx.zn);
      if (fx.style) tr.setAttribute('style', fx.style); else tr.removeAttribute('style');
      const sp = tr.cells[0].querySelector('span') || tr.cells[0];
      sp.textContent = i + 1;
      if (sp.title !== undefined) sp.title = fx.title;
      tr.querySelectorAll('[data-s]').forEach(td => {
        const v = l.s[td.dataset.s];
        const txt = td.dataset.s === 'sg' && v > 0 ? '+' + v : String(v);
        const b = td.querySelector('b'); (b || td).textContent = txt;
      });
      const nomeTd = tr.cells[1], alvo = nomeTd.querySelector('a') || nomeTd;
      alvo.querySelectorAll('.tvivo,.tseta').forEach(x => x.remove());
      if (l.vivo) alvo.insertAdjacentHTML('beforeend', `<span class="tvivo ${l.vivo.r}" title="Jogando agora">${esc(l.vivo.txt)}</span>`);
      const dif = l.o - i;
      if (l.mudou && dif) alvo.insertAdjacentHTML('beforeend', `<span class="tseta ${dif > 0 ? 'sobe' : 'desce'}" title="${dif > 0 ? 'Sobe' : 'Desce'} ${Math.abs(dif)}">${dif > 0 ? '▲' : '▼'}${Math.abs(dif)}</span>`);
      tr.classList.toggle('tjogando', !!l.vivo);
    });
    const corpo = tb.tBodies[0];
    linhas.forEach(l => corpo.appendChild(l.tr));
  }

  function aplicar(tb, oficial, jogos, emTabela) {
    const f = foto(tb);
    const porId = {};
    f.linhas.forEach(l => { if (l.tid) porId[l.tid] = l; });
    const atual = {}; // tid -> estatísticas oficiais mais novas (da ESPN agora) ou as da página
    if (oficial) {
      (oficial.children || [oficial]).forEach(ch => ((ch.standings || {}).entries || []).forEach(en => {
        const id = String((en.team || {}).id || ''); if (!porId[id]) return;
        const st = {}; (en.stats || []).forEach(x => { st[x.name] = Math.round(+x.value || 0); });
        atual[id] = { pts: st.points, pj: st.gamesPlayed, v: st.wins, e: st.ties, d: st.losses, gp: st.pointsFor, gc: st.pointsAgainst, sg: st.pointDifferential, rank: st.rank };
      }));
    }
    const contar = jogos.filter(g => porId[g.c] && porId[g.f] && (g.vivo ||
      // jogo que acabou há pouco: entra se a tabela oficial ainda não o contou
      ((atual[g.c] || porId[g.c].s).pj === porId[g.c].s.pj && g.ini > emTabela - 115 * 60e3)));
    if (!contar.length) {
      if (f.mexida) { desenhar(tb, f, f.linhas.map(l => ({ ...l, s: l.s, vivo: null, mudou: false }))); f.mexida = false; aviso(tb, false); }
      return;
    }
    const linhas = f.linhas.map(l => ({ tr: l.tr, tid: l.tid, o: l.o, s: { ...(atual[l.tid] || l.s) }, rank: (atual[l.tid] || {}).rank || l.o + 1, vivo: null }));
    const por = {}; linhas.forEach(l => { if (l.tid) por[l.tid] = l; });
    contar.forEach(g => {
      [[g.c, g.gc, g.gf], [g.f, g.gf, g.gc]].forEach(([id, pro, contra]) => {
        const l = por[id], s = l.s;
        s.pj += 1; s.gp += pro; s.gc += contra; s.sg = s.gp - s.gc;
        if (pro > contra) { s.v += 1; s.pts += 3; } else if (pro === contra) { s.e += 1; s.pts += 1; } else s.d += 1;
        if (g.vivo) l.vivo = { txt: `${pro} x ${contra}`, r: pro > contra ? 'ganha' : pro < contra ? 'perde' : 'empata' };
      });
    });
    // pontos decidem; no empate, quem está jogando é comparado por vitórias, saldo e gols; o resto segue a ordem oficial
    linhas.sort((a, b) => (b.s.pts - a.s.pts) || ((a.vivo || b.vivo) ? (b.s.v - a.s.v) || (b.s.sg - a.s.sg) || (b.s.gp - a.s.gp) : 0) || (a.rank - b.rank));
    linhas.forEach(l => { l.mudou = true; });
    desenhar(tb, f, linhas);
    f.mexida = true;
    aviso(tb, contar.some(g => g.vivo));
  }

  let espera = null;
  async function tabelas() {
    clearTimeout(espera);
    const tbs = [...document.querySelectorAll('table[data-lg]')].filter(tb => tb.tBodies[0] && tb.querySelector('tr[data-tid]'));
    if (!tbs.length) return;
    const porLg = {};
    tbs.forEach(tb => { (porLg[tb.dataset.lg] = porLg[tb.dataset.lg] || []).push(tb); });
    const situacoes = await Promise.all(Object.entries(porLg).map(async ([lg, lista]) => {
      let sb;
      try { sb = await pega(`${API}site/v2/sports/soccer/${lg}/scoreboard`); } catch (_) { return 'erro'; }
      const jogos = [];
      let previsto = false;
      (sb.events || []).forEach(ev => {
        const e = estado(ev), cp = ev.competitions && ev.competitions[0];
        if (e === 'pre') { if (Date.parse(ev.date) - Date.now() < 3 * 3600e3) previsto = true; return; }
        if (!cp) return;
        const t = lados(cp);
        if (!t.home || !t.away) return;
        jogos.push({ c: String(t.home.team.id), f: String(t.away.team.id), gc: num(t.home.score), gf: num(t.away.score), vivo: e === 'in', ini: Date.parse(ev.date) });
      });
      const temVivo = jogos.some(g => g.vivo);
      const recentes = jogos.some(g => !g.vivo && Date.now() - g.ini < 165 * 60e3);
      let oficial = null;
      if (temVivo || recentes) { try { oficial = await pega(`${API}v2/sports/soccer/${lg}/standings`); } catch (_) {} }
      lista.forEach(tb => aplicar(tb, oficial, temVivo || recentes ? jogos : [], Date.parse(tb.dataset.em || '') || 0));
      return temVivo ? 'vivo' : previsto ? 'previsto' : 'nada';
    }));
    const prox = situacoes.includes('vivo') ? 60e3 : situacoes.includes('previsto') ? 5 * 60e3 : 0;
    if (prox) espera = setTimeout(tabelas, prox);
  }
  tabelas();
  window.OPJAoVivo = { tabelas };
})();
