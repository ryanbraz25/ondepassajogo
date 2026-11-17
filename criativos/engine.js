// Motor simples: cada elemento tem quadros-chave {t, o, x, y, s, r}; render(t) interpola tudo.
const E = (a, b, p) => a + (b - a) * p;
const ease = {
  lin: p => p,
  out: p => 1 - Math.pow(1 - p, 3),
  inout: p => p < .5 ? 4 * p * p * p : 1 - Math.pow(-2 * p + 2, 3) / 2,
  back: p => { const c1 = 1.70158, c3 = c1 + 1; return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2); },
};
const ELS = [];
// add(html, css, keys, parent) — keys: [[t, {o,x,y,s,r}, easing]]
function add(html, css, keys, parent) {
  const d = document.createElement('div');
  d.className = 'el';
  d.innerHTML = html;
  if (css) d.style.cssText += css;
  (parent || document.getElementById('stage')).appendChild(d);
  const k = keys.map(([t, v, e]) => [t, Object.assign({ o: 1, x: 0, y: 0, s: 1, r: 0 }, v), e || 'out']);
  ELS.push({ d, k });
  return d;
}
// atalho: aparece em t1 (pop), some em t2
function pop(html, css, t1, t2, opt = {}) {
  const dy = opt.dy ?? 40, s0 = opt.s0 ?? .85, e = opt.e || 'back';
  const k = [[t1, { o: 0, y: dy, s: s0 }], [t1 + (opt.dur || .35), { o: 1 }, e]];
  if (t2 != null) k.push([t2 - .25, { o: 1 }], [t2, { o: 0, y: opt.outY ?? -30 }, 'inout']);
  return add(html, css, k, opt.parent);
}
const HOOKS = [];
function render(t) {
  for (const { d, k } of ELS) {
    let v;
    if (t <= k[0][0]) v = k[0][1];
    else if (t >= k[k.length - 1][0]) v = k[k.length - 1][1];
    else {
      for (let i = 1; i < k.length; i++) if (t <= k[i][0]) {
        const [t0, a] = k[i - 1], [t1, b, e] = k[i];
        const p = ease[e]((t - t0) / Math.max(t1 - t0, 1e-6));
        v = {}; for (const q in b) v[q] = E(a[q], b[q], p);
        break;
      }
    }
    d.style.opacity = v.o;
    d.style.visibility = v.o <= 0.001 ? 'hidden' : 'visible';
    d.style.transform = `translate(${v.x}px,${v.y}px) scale(${v.s}) rotate(${v.r}deg)`;
  }
  for (const h of HOOKS) h(t);
}
window.render = render;
window.READY = Promise.all([
  document.fonts.load('60px "Noto Color Emoji"', '😩📌✅⚽👀🙄💸👇🔥📲🔔⏱'),
  document.fonts.load('900 italic 60px "Barlow Condensed"'),
  document.fonts.load('800 60px Barlow'),
]).then(() => document.fonts.ready);
