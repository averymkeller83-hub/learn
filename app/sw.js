/* Showwork service worker — the app shell opens even offline.
   Network first for the page (so a new deploy shows up on the next open),
   cache as the fallback. Model calls are never cached. */
const CACHE = 'showwork-shell-v1';
const SHELL = ['/', '/prompts.json', '/manifest.webmanifest', '/icon-192.png', '/icon-512.png'];
self.addEventListener('install', e => { e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const u = new URL(e.request.url);
  if (e.request.method !== 'GET' || u.origin !== location.origin) return;         /* Gemini, Graph, CDNs: straight through */
  if (!SHELL.includes(u.pathname)) return;
  e.respondWith(fetch(e.request).then(r => { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); return r; })
                              .catch(() => caches.match(e.request, {ignoreSearch: true})));
});
