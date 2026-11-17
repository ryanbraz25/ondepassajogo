// valor interpolado por quadros-chave [[t, v, easing]]
function at(keys, t) {
  if (t <= keys[0][0]) return keys[0][1];
  const L = keys[keys.length - 1]; if (t >= L[0]) return L[1];
  for (let i = 1; i < keys.length; i++) if (t <= keys[i][0]) {
    const [t0, a] = keys[i - 1], [t1, b, e] = keys[i];
    return E(a, b, ease[e || 'inout']((t - t0) / (t1 - t0)));
  }
}
// celular com a tela do site; shots: [{src, from, to}] (troca com fade); scroll: [[t, y]] em px da tela (600 de largura)
function phone(top, keys, shots, scroll) {
  const d = add(`<div class="phone" style="top:${top}px"><div class="notch"></div><div class="scr"><div class="pg" style="position:absolute;left:0;top:0;width:600px"></div></div></div>`, 'height:1920px', keys);
  const scr = d.querySelector('.pg');
  const imgs = shots.map(s => { const i = document.createElement('img'); i.className = 'shot'; i.src = s.src; scr.appendChild(i); return [i, s]; });
  HOOKS.push(t => {
    scr.style.transform = `translateY(${-(scroll ? at(scroll, t) : 0)}px)`;
    for (const [i, s] of imgs) {
      let o = 1;
      if (s.from > 0) o = t < s.from - .2 ? 0 : t < s.from ? (t - (s.from - .2)) / .2 : 1;
      if (s.to != null && t > s.to) o = 0;
      i.style.opacity = o;
    }
  });
  return { el: d, scr };
}
// toque: círculo amarelo que pulsa em (x,y) da tela do celular, no instante t
function tap(scr, x, y, t) {
  const c = document.createElement('div'); c.className = 'tap'; c.style.left = x + 'px'; c.style.top = y + 'px'; scr.appendChild(c);
  HOOKS.push(tt => { const p = (tt - t) / .55; c.style.opacity = p < 0 || p > 1 ? 0 : (p < .3 ? 1 : 1 - (p - .3) / .7); c.style.transform = `scale(${p < 0 ? .4 : .55 + Math.min(p, 1) * .7})`; });
}
// destaque: moldura amarela em volta de uma área da tela entre t1 e t2
function box(scr, x, y, w, h, t1, t2) {
  const b = document.createElement('div'); b.className = 'box';
  Object.assign(b.style, { left: x + 'px', top: y + 'px', width: w + 'px', height: h + 'px' }); scr.appendChild(b);
  HOOKS.push(t => { const o = t < t1 ? 0 : t < t1 + .25 ? (t - t1) / .25 : (t2 && t > t2 ? Math.max(0, 1 - (t - t2) / .25) : 1); b.style.opacity = o; b.style.transform = `scale(${1 + (1 - Math.min(1, o)) * .08})`; });
}
const LOGO = '<img src="logo.svg" width="118" height="155" alt="">';
function endCard(t0, sub) {
  add(`<div class="endlogo"><div class="brand">${LOGO}<span>ONDE PASSA <em>JOGO</em></span></div>
       <div class="url">ondepassajogo.com.br</div><div class="sub">${sub}</div></div>`,
      'top:700px', [[t0, { o: 0, s: .8, y: 30 }], [t0 + .45, { o: 1, s: 1, y: 0 }, 'back']]);
}
// marca pequena fixa no rodapé durante o vídeo
function marca(t1, t2) {
  add(`<div class="center"><div style="display:flex;align-items:center;gap:12px;font:900 italic 44px 'Barlow Condensed';opacity:.9"><img src="logo.svg" width="34" height="45"><span style="transform:skewX(-6deg)">ondepassajogo.com.br</span></div></div>`,
      'top:1600px', [[t1, { o: 0 }], [t1 + .3, { o: 1 }], [t2 - .3, { o: 1 }], [t2, { o: 0 }]]);
}
const K = 600 / 390; // px do site (CSS) -> px da tela do celular no vídeo
const tapS = (scr, x, y, t) => tap(scr, x * K, y * K, t);
const boxS = (scr, x, y, w, h, t1, t2) => box(scr, x * K - 8, y * K - 8, w * K + 16, h * K + 16, t1, t2);

const ICO = {
  check: '<svg width="46" height="46" viewBox="0 0 24 24" style="vertical-align:-10px;margin-right:12px"><circle cx="12" cy="12" r="11" fill="#0a6d35"/><path d="M6.5 12.5l3.6 3.6L17.6 8.6" fill="none" stroke="#fff" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  down: '<svg width="120" height="120" viewBox="0 0 24 24"><path d="M12 3v16m0 0l-7-7m7 7l7-7" fill="none" stroke="#ffd400" stroke-width="3.2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  bell: '<svg width="70" height="70" viewBox="0 0 24 24" style="vertical-align:-12px"><path d="M6 17V11a6 6 0 0 1 12 0v6l1.6 2H4.4Z" fill="#ffd400"/><path d="M10 21.5h4" stroke="#ffd400" stroke-width="2.2" stroke-linecap="round"/></svg>',
  pin: '<svg width="40" height="40" viewBox="0 0 24 24" style="vertical-align:-8px"><path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7Zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5Z" fill="#ffd400"/></svg>',
};
