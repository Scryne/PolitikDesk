/* PolitikDesk Service Worker (PWA & Offline Workstation) */
const CACHE_NAME = 'politikdesk-shell-v1';
const STATIC_ASSETS = [
  '/static/manifest.webmanifest',
  '/static/icon-192.svg',
  '/static/icon-512.svg',
  '/static/fonts/ibm-plex-mono-latin-ext.woff2',
  '/static/fonts/ibm-plex-mono-latin.woff2',
  '/static/fonts/instrument-serif-latin-ext.woff2',
  '/static/fonts/instrument-serif-latin.woff2',
  '/static/fonts/inter-tight-latin-ext.woff2',
  '/static/fonts/inter-tight-latin.woff2'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('SW static precache error:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Sadece aynı origin isteklerine bak
  if (url.origin !== self.location.origin) return;

  // Statik varlıklar: Cache-first
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        return cached || fetch(event.request).then((response) => {
          if (response && response.status === 200) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, responseClone);
            });
          }
          return response;
        });
      })
    );
    return;
  }

  // HTML Gezinmesi / API: Network-first
  if (event.request.mode === 'navigate') {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(event.request).then((cached) => {
          if (cached) return cached;
          return new Response(
            '<!doctype html><html lang="tr"><head><meta charset="utf-8"><title>Çevrimdışı · PolitikDesk</title>' +
            '<style>body{background:#0b0d0e;color:#e6edf3;font-family:sans-serif;display:flex;align-items:center;justify-content:center;height:100vh;margin:0;text-align:center;}' +
            '.box{padding:2rem;border:1px solid #2a313a;border-radius:8px;background:#111418;max-width:400px;}' +
            'h1{font-size:1.25rem;margin-bottom:0.5rem;}p{color:#8b949e;font-size:0.9rem;}</style></head>' +
            '<body><div class="box"><h1>Çevrimdışı Çalışma Modu</h1><p>İnternet bağlantısı kesildi. Bağlantı sağlandığında akış otomatik yenilenecektir.</p></div></body></html>',
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        });
      })
    );
  }
});
