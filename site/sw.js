/* Onde Passa Jogo: recebe os avisos (Firebase Cloud Messaging) e abre o site ao tocar. */
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));

self.addEventListener('push', e => {
  let p = {};
  try { p = e.data ? e.data.json() : {}; } catch (_) { p = { data: { body: e.data && e.data.text() } }; }
  const d = p.data || (p.notification ? { title: p.notification.title, body: p.notification.body } : p);
  const title = d.title || 'Onde Passa Jogo';
  e.waitUntil(self.registration.showNotification(title, {
    body: d.body || 'Veja os jogos de hoje e onde passam.',
    icon: '/icone-192.png',
    badge: '/badge-96.png',
    tag: d.tag || 'resumo-do-dia',
    renotify: true,
    data: { url: d.url || '/' }
  }));
});

self.addEventListener('notificationclick', e => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || '/', self.location.origin).href;
  e.waitUntil((async () => {
    const abertas = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    for (const c of abertas) {
      if (c.url.startsWith(self.location.origin) && 'focus' in c) { await c.navigate(url).catch(() => {}); return c.focus(); }
    }
    return self.clients.openWindow(url);
  })());
});
