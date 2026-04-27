// Service worker — Phase 3 PWA shell + push handler.
// Scope: '/' (registered from _mobile_page).
// Responsibilities:
//   - install/activate (no precache yet — keep it light)
//   - 'push' events → display the notification
//   - 'notificationclick' → focus or open the app at the targeted URL

const SW_VERSION = 'v1';

self.addEventListener('install', (event) => {
  // Activate immediately so updates take effect on the next page load.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

// Reform doesn't precache yet; pass requests through to the network.
self.addEventListener('fetch', (event) => {
  // Letting the browser handle it is fine. We register a noop listener so
  // iOS treats this as a "real" service worker (Add to Home Screen prompt).
});

self.addEventListener('push', (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (e) { data = { body: event.data && event.data.text() }; }
  const title = data.title || 'Reform';
  const body  = data.body  || '';
  const url   = data.url   || '/';
  const opts = {
    body,
    icon: '/static/icon-192.png',
    badge: '/static/icon-192.png',
    tag:   data.tag || 'reform',
    data:  { url },
  };
  event.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || '/';
  event.waitUntil((async () => {
    const all = await self.clients.matchAll({ type: 'window', includeUncontrolled: true });
    // Reuse an existing tab if any, otherwise open a new one.
    for (const c of all) {
      if (c.url.includes(self.registration.scope)) {
        c.focus();
        c.navigate(url).catch(() => {});
        return;
      }
    }
    self.clients.openWindow(url);
  })());
});
