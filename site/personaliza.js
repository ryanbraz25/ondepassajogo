/* Personalização do Onde Passa Jogo, guardada só no aparelho (sem conta, sem servidor):
   - meu estado: canal que só passa em alguns estados (ex.: Globo) mostra se passa para a pessoa;
   - meus canais: o que a pessoa assina, para destacar os jogos que ela consegue ver;
   - compartilhar: texto pronto do jogo ou da lista do dia (janela do aparelho ou WhatsApp/Telegram/copiar).
   Na página inicial este arquivo carrega antes do script principal, que usa window.OPJP.
   Nas páginas estáticas ele mesmo marca os botões de canal (data-canal, data-reg, data-gr). */
(() => {
  'use strict';
  const UFS = [['AC', 'Acre'], ['AL', 'Alagoas'], ['AP', 'Amapá'], ['AM', 'Amazonas'], ['BA', 'Bahia'], ['CE', 'Ceará'],
    ['DF', 'Distrito Federal'], ['ES', 'Espírito Santo'], ['GO', 'Goiás'], ['MA', 'Maranhão'], ['MT', 'Mato Grosso'],
    ['MS', 'Mato Grosso do Sul'], ['MG', 'Minas Gerais'], ['PA', 'Pará'], ['PB', 'Paraíba'], ['PR', 'Paraná'],
    ['PE', 'Pernambuco'], ['PI', 'Piauí'], ['RJ', 'Rio de Janeiro'], ['RN', 'Rio Grande do Norte'],
    ['RS', 'Rio Grande do Sul'], ['RO', 'Rondônia'], ['RR', 'Roraima'], ['SC', 'Santa Catarina'], ['SP', 'São Paulo'],
    ['SE', 'Sergipe'], ['TO', 'Tocantins']];
  const GRATIS = new Set(['TV aberta', 'YouTube', 'App']);
  const PAGOS = ['TV fechada', 'Pay-per-view', 'Streaming'];
  const esc = s => String(s == null ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const ler = (k, padrao) => { try { const v = localStorage.getItem(k); return v === null ? padrao : JSON.parse(v); } catch (_) { return padrao; } };
  const gravar = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} };

  let uf = UFS.some(x => x[0] === ler('pz-uf', '')) ? ler('pz-uf', '') : '';
  let meus = new Set(ler('pz-canais', []));
  const ouvintes = [];
  const mudou = () => { aplicarEstaticos(); ouvintes.forEach(f => { try { f(); } catch (_) {} }); };

  const ufsTxt = l => l.length > 1 ? l.slice(0, -1).join(', ') + ' e ' + l[l.length - 1] : (l[0] || '');
  const nomeUf = s => (UFS.find(x => x[0] === s) || [s, s])[1];

  // ---------------------------------------------------------------- regras (usadas também pela página inicial)
  /** O canal c do jogo g chega até a pessoa? (canal sem restrição de estado, ou estado não escolhido: sim) */
  const alcanca = (c, g) => { const r = g && g.reg && g.reg[c]; return !r || !uf || r.includes(uf); };
  /** Texto da região de um canal regional: null quando o canal passa no Brasil todo. */
  function regiao(c, g) {
    const r = g && g.reg && g.reg[c];
    if (!r || !r.length) return null;
    if (!uf) return { txt: ufsTxt(r), cls: '' };
    return r.includes(uf) ? { txt: 'passa no seu estado', cls: 'ok' } : { txt: 'só em ' + ufsTxt(r), cls: 'fora' };
  }
  const temMeus = () => meus.size > 0;
  const meu = c => meus.has(c);
  /** A pessoa consegue ver o jogo? Canal grátis ou marcado em "meus canais", que chegue ao estado dela.
      livre(c, g) diz se o canal é grátis (a página inicial já sabe, inclusive YouTube grátis de canal pago). */
  const assiste = (g, livre) => (g.canais || []).some(c => alcanca(c, g) && (meus.has(c) || livre(c, g)));

  // ---------------------------------------------------------------- compartilhar
  // Usa a janela de compartilhar do próprio aparelho (celular e computador). Onde ela não existe,
  // abre um menu pequeno junto do botão: WhatsApp, Telegram ou copiar o texto.
  const evento = (metodo, tipo) => { if (window.gtag) { try { window.gtag('event', 'share', { method: metodo, content_type: tipo || 'jogo' }); } catch (_) {} } };
  function compartilhar(texto, tipo, botao) {
    if (navigator.share) {
      navigator.share({ text: texto }).then(() => evento('nativo', tipo))
        .catch(e => { if (e && e.name !== 'AbortError') menuCompartilhar(texto, tipo, botao); });
      return;
    }
    menuCompartilhar(texto, tipo, botao);
  }
  let menuC = null;
  function fecharMenuC() { if (menuC) { menuC.remove(); menuC = null; } }
  function menuCompartilhar(texto, tipo, botao) {
    fecharMenuC();
    const t = encodeURIComponent(texto);
    const url = (texto.match(/https?:\/\/\S+/) || [location.href])[0];
    menuC = document.createElement('div');
    menuC.className = 'shm';
    menuC.setAttribute('role', 'menu');
    menuC.innerHTML = `<a role="menuitem" href="https://wa.me/?text=${t}" target="_blank" rel="noopener" data-m="whatsapp">WhatsApp</a>`
      + `<a role="menuitem" href="https://t.me/share/url?url=${encodeURIComponent(url)}&text=${t}" target="_blank" rel="noopener" data-m="telegram">Telegram</a>`
      + `<button role="menuitem" type="button" data-m="copiar">Copiar texto</button>`;
    document.body.appendChild(menuC);
    const r = (botao || document.body).getBoundingClientRect();
    const w = menuC.offsetWidth, h = menuC.offsetHeight;
    menuC.style.left = Math.max(8, Math.min(innerWidth - w - 8, r.right - w)) + 'px';
    menuC.style.top = (r.bottom + h + 8 < innerHeight ? r.bottom + 6 : Math.max(8, r.top - h - 6)) + 'px';
    menuC.addEventListener('click', async e => {
      const it = e.target.closest('[data-m]'); if (!it) return;
      evento(it.dataset.m, tipo);
      if (it.dataset.m === 'copiar') {
        try { await navigator.clipboard.writeText(texto); avisoC('Copiado! É só colar onde quiser.'); } catch (_) { avisoC('Não deu para copiar aqui.'); }
      }
      fecharMenuC();
    });
    menuC.querySelector('[data-m]').focus();
  }
  function avisoC(msg) {
    const d = document.createElement('div');
    d.className = 'shm-ok'; d.setAttribute('role', 'status'); d.textContent = msg;
    document.body.appendChild(d);
    setTimeout(() => d.remove(), 2600);
  }
  document.addEventListener('click', e => { if (menuC && !menuC.contains(e.target) && !e.target.closest('[data-zap],[data-zapg]')) fecharMenuC(); });
  document.addEventListener('keydown', e => { if (e.key === 'Escape') fecharMenuC(); });
  addEventListener('scroll', fecharMenuC, { passive: true });

  // ---------------------------------------------------------------- janela "Meu estado e meus canais"
  let canaisCfg = null;
  const pegaCanais = () => canaisCfg ? Promise.resolve(canaisCfg) : window.OPJ_CANAIS ? Promise.resolve(canaisCfg = window.OPJ_CANAIS)
    : fetch('/dados/canais.json').then(r => r.json()).then(j => (canaisCfg = j));

  let dlg = null;
  async function abrir(foco) {
    let lista = {};
    try { lista = await pegaCanais(); } catch (_) {}
    if (!dlg) {
      dlg = document.createElement('dialog');
      dlg.className = 'pz';
      dlg.setAttribute('aria-labelledby', 'pz-t');
      document.body.appendChild(dlg);
      dlg.addEventListener('click', e => { if (e.target === dlg) dlg.close(); });
      dlg.addEventListener('close', () => document.documentElement.classList.remove('pz-aberto'));
    }
    const grupos = PAGOS.map(tp => [tp, Object.entries(lista).filter(([, v]) => v.tipo === tp)]).filter(([, l]) => l.length);
    const gratis = Object.values(lista).filter(v => GRATIS.has(v.tipo)).map(v => v.nome);
    dlg.innerHTML = `<form method="dialog" class="pz-f">
      <div class="pz-hd"><b id="pz-t">Meu estado e meus canais</b>
        <button class="pz-x" value="cancelar" aria-label="Fechar"><svg width="20" height="20" viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"/></svg></button></div>
      <div class="pz-bd">
        <section><h3><label for="pz-uf">Seu estado</label></h3>
          <p class="pz-aj">A TV aberta (como a Globo) muda de jogo conforme o estado. Escolha o seu para ver o que passa aí.</p>
          <select id="pz-uf" name="uf"><option value="">Não escolher</option>${UFS.map(([s, n]) => `<option value="${s}"${s === uf ? ' selected' : ''}>${esc(n)}</option>`).join('')}</select></section>
        <section><h3 id="pz-ch">Canais que você tem</h3>
          <p class="pz-aj">Marque o que você assina. Os grátis${gratis.length ? ` (${esc(gratis.slice(0, 4).join(', '))}…)` : ''} sempre contam.</p>
          ${grupos.map(([tp, l]) => `<fieldset><legend>${esc(tp)}</legend><div class="pz-ops">${l.map(([id, v]) =>
            `<label class="pz-op"><input type="checkbox" name="c" value="${esc(id)}"${meus.has(id) ? ' checked' : ''}><span>${esc(v.nome)}</span></label>`).join('')}</div></fieldset>`).join('')}
        </section>
        <p class="pz-priv">Fica guardado só neste aparelho.</p>
      </div>
      <div class="pz-ft"><button class="pz-ok" value="salvar">Salvar</button></div>
    </form>`;
    dlg.querySelector('form').addEventListener('submit', e => {
      if (e.submitter && e.submitter.value !== 'salvar') return;
      const f = e.target;
      uf = f.uf.value;
      meus = new Set([...f.querySelectorAll('input[name=c]:checked')].map(x => x.value));
      gravar('pz-uf', uf); gravar('pz-canais', [...meus]);
      if (window.gtag) { try { window.gtag('event', 'personalizar', { estado: uf || 'nenhum', canais: meus.size }); } catch (_) {} }
      mudou();
    });
    document.documentElement.classList.add('pz-aberto');
    dlg.showModal();
    const alvo = foco === 'canais' ? dlg.querySelector('#pz-ch') : dlg.querySelector('#pz-uf');
    if (alvo) { alvo.scrollIntoView({ block: 'nearest' }); if (foco !== 'canais') alvo.focus(); }
  }

  // ---------------------------------------------------------------- páginas estáticas (jogo, dia, time...)
  function aplicarEstaticos() {
    document.querySelectorAll('.botoes [data-canal]').forEach(b => {
      const c = b.dataset.canal, reg = (b.dataset.reg || '').split(',').filter(Boolean);
      const chega = !reg.length || !uf || reg.includes(uf);
      const rg = b.querySelector('.rg');
      if (rg && reg.length) {
        rg.textContent = !uf ? 'Só em ' + ufsTxt(reg) : chega ? 'Passa no seu estado' : `Não passa em ${uf} (só em ${ufsTxt(reg)})`;
        rg.className = 'rg' + (!uf ? '' : chega ? ' ok' : ' fora');
      }
      // canal grátis que não chega ao estado da pessoa perde o destaque verde e vai para o fim da lista
      b.classList.toggle('pz-fora', !chega);
      if (b.dataset.gr === '1') b.classList.toggle('gratis', chega);
      const vc = temMeus() && chega && (meus.has(c) || b.dataset.gr === '1');
      b.classList.toggle('pz-meu', vc);
      let sel = b.querySelector('.pz-selo');
      if (vc && !sel) { sel = document.createElement('span'); sel.className = 'pz-selo'; sel.textContent = 'Você assiste'; b.querySelector('.cn').appendChild(sel); }
      if (!vc && sel) sel.remove();
    });
    document.querySelectorAll('.botoes').forEach(cx => {
      const bs = [...cx.querySelectorAll(':scope > [data-canal]')];
      bs.forEach((b, i) => { if (!b.dataset.ordem) b.dataset.ordem = i; });
      bs.sort((a, b) => a.classList.contains('pz-fora') - b.classList.contains('pz-fora') || a.dataset.ordem - b.dataset.ordem)
        .forEach(b => cx.appendChild(b));
    });
    document.querySelectorAll('[data-pz-uf]').forEach(p => {
      p.innerHTML = uf ? `Mostrando para <b>${esc(nomeUf(uf))}</b>. <button type="button" class="lnk" data-prefs="uf">Trocar estado</button>`
        : 'Algum canal só passa em alguns estados. <button type="button" class="lnk" data-prefs="uf">Escolher meu estado</button>';
    });
  }

  // cliques que valem em qualquer página: abrir a janela e compartilhar (texto pronto no botão)
  document.addEventListener('click', e => {
    const pr = e.target.closest('[data-prefs]');
    if (pr) {
      e.preventDefault();
      const menu = document.getElementById('menu');
      if (menu && menu.open) menu.close();
      abrir(pr.dataset.prefs);
      return;
    }
    const z = e.target.closest('[data-zap][data-texto]');
    if (z) { e.preventDefault(); compartilhar(z.dataset.texto, z.dataset.zap, z); }
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', aplicarEstaticos); else aplicarEstaticos();
  if (location.hash === '#meus-canais') addEventListener('load', () => abrir('canais'));

  window.OPJP = {
    uf: () => uf, nomeUf, ufsTxt, alcanca, regiao, temMeus, meu, assiste, compartilhar, abrir,
    aoMudar: f => ouvintes.push(f)
  };
})();
