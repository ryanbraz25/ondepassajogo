/* Estatísticas do jogo ao vivo (posse, finalizações, escanteios...), direto do resumo da ESPN (grátis).
   A página já sai com o que o robô guardou; aqui o bloco é atualizado a cada minuto enquanto a bola rola. */
(() => {
  'use strict';
  const sec = document.querySelector('.estat');
  const pl = document.querySelector('.placa[data-eid][data-lg]');
  if (!sec || !pl) return;
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  // mesma lista e ordem de robo/estatisticas.py
  const ITENS = [
    ['possessionPct', 'Posse de bola', 'pct'], ['totalShots', 'Finalizações'], ['shotsOnTarget', 'Finalizações no gol'],
    ['wonCorners', 'Escanteios'], ['foulsCommitted', 'Faltas'], ['offsides', 'Impedimentos'], ['yellowCards', 'Cartões amarelos'],
    ['redCards', 'Cartões vermelhos'], ['saves', 'Defesas do goleiro'], ['accuratePasses', 'Passes certos'],
  ];
  const num = v => { const x = parseFloat(String(v == null ? '' : v).replace('%', '').replace(',', '.')); return isNaN(x) ? null : Math.round(x * 10) / 10; };
  const fmt = (v, tipo) => String(v).replace('.', ',') + (tipo === 'pct' ? '%' : ''); // 69,6% (vírgula, como no Brasil)
  const [casa, fora] = [...sec.querySelectorAll('.st-times span')].map(x => x.textContent);

  function desenhar(st, fim) {
    const linhas = ITENS.map(([k, rot, tipo]) => {
      const a = st.casa[k], b = st.fora[k];
      if (a == null || b == null) return '';
      const pa = tipo === 'pct' ? Math.round(a) : a + b ? Math.round(100 * a / (a + b)) : 50;
      const lid = a > b ? 'c' : b > a ? 'f' : '';
      return `<li class="st-l${tipo === 'pct' ? ' st-pct' : ''}${a + b === 0 ? ' st-zero' : ''}" data-k="${k}"><div class="st-n"><b class="${lid === 'c' ? 'lid' : ''}">${fmt(a, tipo)}</b>`
        + `<span>${esc(rot)}</span><b class="${lid === 'f' ? 'lid' : ''}">${fmt(b, tipo)}</b></div>`
        + `<div class="st-b" role="img" aria-label="${esc(rot)}: ${esc(casa)} ${fmt(a, tipo)}, ${esc(fora)} ${fmt(b, tipo)}">`
        + `<i class="st-bc" style="width:${pa}%"></i><i class="st-bf" style="width:${100 - pa}%"></i></div></li>`;
    }).join('');
    if (!linhas) return;
    sec.querySelector('.st-lista').innerHTML = linhas;
    sec.querySelector('h2').innerHTML = 'Estatísticas' + (fim ? '' : ' <small>ao vivo</small>');
    sec.hidden = false;
  }

  function ler(r) {
    const st = {};
    ((r.boxscore || {}).teams || []).forEach(t => {
      const lado = t.homeAway === 'home' ? 'casa' : t.homeAway === 'away' ? 'fora' : null;
      if (!lado) return;
      st[lado] = {};
      (t.statistics || []).forEach(x => { const v = num(x.displayValue != null ? x.displayValue : x.value); if (v != null) st[lado][x.name] = v; });
    });
    if (!st.casa || !st.fora) return null;
    const algum = ITENS.some(([k]) => st.casa[k] || st.fora[k]);
    return algum ? st : null;
  }

  const ini = Date.parse(pl.dataset.ini);
  const url = `https://site.web.api.espn.com/apis/site/v2/sports/soccer/${pl.dataset.lg}/summary?event=${pl.dataset.eid}&region=br&lang=pt`;
  const jaFechado = !sec.hidden && !sec.querySelector('h2 small');
  async function vez() {
    const agora = Date.now();
    if (jaFechado) return; // o robô já gravou as estatísticas finais
    if (agora < ini - 5 * 60e3) { setTimeout(vez, Math.min(ini - 5 * 60e3 - agora, 30 * 60e3)); return; }
    if (agora > ini + 36 * 3600e3) return;
    let fim = false;
    try {
      const r = await (await fetch(url, { cache: 'no-store' })).json();
      const comp = ((r.header || {}).competitions || [])[0] || {};
      fim = (((comp.status || {}).type) || {}).state === 'post';
      const st = ler(r);
      if (st) desenhar(st, fim);
    } catch (_) { /* sem conexão: tenta de novo no próximo minuto */ }
    if (!fim && agora < ini + 4 * 3600e3) setTimeout(vez, 60e3);
  }
  vez();
})();
