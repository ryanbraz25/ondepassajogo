/* Jogos por rodada: setas e lista para trocar de rodada sem recarregar, e placar ao vivo dos jogos da rodada.
   O HTML de cada rodada vem pronto do robô em /dados/rod-<campeonato>.json. */
(() => {
  'use strict';
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const arquivos = {};
  const escolhida = {}; // rodada que a pessoa abriu, por campeonato (a página inicial redesenha a lista às vezes)
  const carregar = s => arquivos[s] || (arquivos[s] = fetch(`/dados/rod-${s}.json`, { cache: 'no-cache' })
    .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); })
    .catch(e => { delete arquivos[s]; throw e; }));

  const SETA = d => `<svg width="22" height="22" viewBox="0 0 24 24" aria-hidden="true"><path d="${d}" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

  // caixa completa, para quando não veio desenhada do robô (aba "Rodadas" da página inicial)
  function caixa(s, d, i) {
    const r = d.rodadas[i], id = 'rd-sel-' + s;
    return `<div class="rdx" data-rod="${esc(s)}" data-i="${i}" data-total="${d.rodadas.length}">
      <div class="rd-nav"><button class="rd-b rd-ant" type="button" aria-label="Rodada anterior"${i === 0 ? ' disabled' : ''}>${SETA('M15 5l-7 7 7 7')}</button>
      <div class="rd-t"><b>${esc(r.nome)}</b><small>${esc(r.periodo)}</small><label class="so-leitor" for="${id}">Escolher a rodada</label>
      <select class="rd-sel" id="${id}">${d.rodadas.map((x, n) => `<option value="${n}"${n === i ? ' selected' : ''}>${esc(x.nome)}</option>`).join('')}</select></div>
      <button class="rd-b rd-prox" type="button" aria-label="Próxima rodada"${i === d.rodadas.length - 1 ? ' disabled' : ''}>${SETA('M9 5l7 7-7 7')}</button></div>
      <ul class="rd-l" aria-live="polite">${r.html}</ul></div>`;
  }

  function mostrar(box, d, i) {
    i = Math.max(0, Math.min(d.rodadas.length - 1, i));
    const r = d.rodadas[i];
    box.dataset.i = i;
    escolhida[box.dataset.rod] = i;
    box.querySelector('.rd-t b').textContent = r.nome;
    box.querySelector('.rd-t small').textContent = r.periodo;
    box.querySelector('.rd-l').innerHTML = r.html;
    box.querySelector('.rd-sel').value = String(i);
    box.querySelector('.rd-ant').disabled = i === 0;
    box.querySelector('.rd-prox').disabled = i === d.rodadas.length - 1;
    aoVivo(box);
  }

  function ligar(box) {
    if (!box || box.dataset.ligada) return;
    box.dataset.ligada = '1';
    const s = box.dataset.rod;
    const ir = async passo => {
      box.classList.add('carregando');
      try {
        const d = await carregar(s);
        const atual = +box.dataset.i;
        mostrar(box, d, passo === null ? +box.querySelector('.rd-sel').value : atual + passo);
      } catch (_) { /* sem conexão: fica na rodada que está */ }
      box.classList.remove('carregando');
    };
    box.querySelector('.rd-ant').addEventListener('click', () => ir(-1));
    box.querySelector('.rd-prox').addEventListener('click', () => ir(1));
    box.querySelector('.rd-sel').addEventListener('change', () => ir(null));
    // deslizar o dedo para o lado também troca de rodada
    let x0 = null, y0 = 0;
    const lista = box.querySelector('.rd-l');
    lista.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; y0 = e.touches[0].clientY; }, { passive: true });
    lista.addEventListener('touchend', e => {
      if (x0 === null) return;
      const dx = e.changedTouches[0].clientX - x0, dy = e.changedTouches[0].clientY - y0;
      x0 = null;
      if (Math.abs(dx) > 70 && Math.abs(dx) > 2 * Math.abs(dy)) ir(dx < 0 ? 1 : -1);
    }, { passive: true });
    if ('requestIdleCallback' in window) requestIdleCallback(() => carregar(s).catch(() => {}));
    aoVivo(box);
  }

  // ---------- placar ao vivo (ESPN, direto do navegador) dos jogos da rodada que está na tela
  const timers = new WeakMap();
  function aoVivo(box) {
    clearTimeout(timers.get(box));
    if (!box.isConnected) return;
    const agora = Date.now();
    const vivos = [...box.querySelectorAll('.rjx[data-eid][data-lg][data-ed]')].filter(li => {
      const t = Date.parse((li.querySelector('time') || {}).dateTime || '');
      return t && !li.classList.contains('fim') && agora > t - 10 * 60e3 && agora < t + 165 * 60e3;
    });
    if (!vivos.length) return;
    const grupos = {};
    vivos.forEach(li => { (grupos[li.dataset.lg + '|' + li.dataset.ed] = grupos[li.dataset.lg + '|' + li.dataset.ed] || []).push(li); });
    Promise.all(Object.entries(grupos).map(async ([k, lis]) => {
      const [lg, ed] = k.split('|');
      try {
        const r = await (await fetch(`https://site.api.espn.com/apis/site/v2/sports/soccer/${lg}/scoreboard?dates=${ed}`, { cache: 'no-store' })).json();
        const evs = {}; (r.events || []).forEach(ev => { evs[ev.id] = ev; });
        lis.forEach(li => atualizar(li, evs[li.dataset.eid]));
      } catch (_) {}
    })).finally(() => timers.set(box, setTimeout(() => aoVivo(box), 60e3)));
  }
  function atualizar(li, ev) {
    if (!ev) return;
    const cp = ev.competitions && ev.competitions[0];
    const st = ((ev.status || (cp && cp.status) || {}).type) || {};
    if (!cp || st.state === 'pre') return;
    const t = {}; (cp.competitors || []).forEach(c => { t[c.homeAway] = c; });
    if (!t.home || !t.away) return;
    const p = li.querySelector('.rj-p');
    p.classList.remove('rj-x');
    p.innerHTML = `<b>${esc(t.home.score)}</b><i>x</i><b>${esc(t.away.score)}</b>`;
    const tv = li.querySelector('.rj-tv') || li.appendChild(Object.assign(document.createElement('p'), { className: 'rj-tv' }));
    if (st.state === 'post') {
      li.classList.remove('vivo'); li.classList.add('fim');
      tv.className = 'rj-tv rj-s'; tv.textContent = 'Encerrado';
    } else {
      li.classList.add('vivo');
      const det = st.shortDetail || st.detail || '';
      const marca = tv.querySelector('.rj-vivo') || tv.insertBefore(Object.assign(document.createElement('span'), { className: 'rj-vivo' }), tv.firstChild);
      marca.textContent = 'Ao vivo' + (det && !/^\d+\/\d+/.test(det) ? ' · ' + det.replace('Halftime', 'Intervalo') : '');
    }
  }

  document.querySelectorAll('.rdx[data-rod]').forEach(ligar);
  window.OPJRodadas = {
    montar(el, s) {
      el.innerHTML = '<p class="rj-vazio">Carregando os jogos…</p>';
      return carregar(s).then(d => {
        const i = Math.min(escolhida[s] ?? d.atual, d.rodadas.length - 1);
        el.innerHTML = caixa(s, d, i); ligar(el.querySelector('.rdx'));
      })
        .catch(() => { el.innerHTML = '<p class="rj-vazio">Não foi possível carregar os jogos agora.</p>'; });
    }
  };
  // a página inicial pode ter pedido a caixa antes deste arquivo carregar
  document.querySelectorAll('[data-rodhome]').forEach(el => { if (!el.querySelector('.rdx')) window.OPJRodadas.montar(el, el.dataset.rodhome); });
})();
