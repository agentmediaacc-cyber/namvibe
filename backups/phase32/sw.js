const CACHE_NAME = 'chain-cache-v1';
const ASSETS = [
  '/',
  '/static/css/chain_theme.css',
  '/static/js/main.js',
  '/static/img/default_avatar.png'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS);
    })
  );
});

self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request).then((response) => {
      return response || fetch(event.request);
    })
  );
});
