/* NamVibe Service Worker v1 — offline cache foundation */
var CACHE_NAME = "namvibe-cache-v3";
var STATIC_ASSETS = [
  "/",
  "/static/css/chain_theme.css",
  "/static/css/namvibe_home_pro.css",
  "/static/css/namvibe_camera_creator.css",
  "/static/css/business_flyer_generator.css",
  "/static/js/namvibe_home_pro.js",
  "/static/js/namvibe_camera_creator.js",
  "/static/js/namvibe_offline_cache.js",
  "/static/js/business_flyer_generator.js",
  "/static/img/icon-192.png",
  "/static/img/icon-512.png",
  "/static/img/default_avatar.png",
  "/static/manifest.json",
];

self.addEventListener("install", function (e) {
  e.waitUntil(
    caches.open(CACHE_NAME).then(function (cache) {
      return cache.addAll(STATIC_ASSETS).catch(function (err) {
        console.error("SW: cache addAll failed", err);
      });
    }).then(function () {
      return self.skipWaiting();
    })
  );
});

self.addEventListener("activate", function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(
        keys.filter(function (k) { return k !== CACHE_NAME; }).map(function (k) { return caches.delete(k); })
      );
    }).then(function () {
      return self.clients.claim();
    })
  );
});

self.addEventListener("fetch", function (e) {
  var url = new URL(e.request.url);

  /* Skip non-GET and non-HTTP(S) requests */
  if (e.request.method !== "GET" || !url.protocol.startsWith("http")) return;

  /* Never cache API responses */
  if (url.pathname.startsWith("/api/")) return;

  /* Never cache auth/profile pages */
  if (url.pathname.startsWith("/auth/") || url.pathname.startsWith("/profile/settings")) return;

  /* Cache-first for static assets */
  if (url.pathname.startsWith("/static/")) {
    e.respondWith(
      caches.match(e.request).then(function (cached) {
        return cached || fetch(e.request).then(function (resp) {
          return caches.open(CACHE_NAME).then(function (cache) {
            if (resp.ok) cache.put(e.request, resp.clone());
            return resp;
          });
        });
      })
    );
    return;
  }

  /* Network-first for HTML pages */
  e.respondWith(
    fetch(e.request).then(function (resp) {
      if (resp.ok && resp.headers.get("Content-Type") && resp.headers.get("Content-Type").includes("text/html")) {
        var clone = resp.clone();
        caches.open(CACHE_NAME).then(function (cache) { cache.put(e.request, clone); });
      }
      return resp;
    }).catch(function () {
      return caches.match(e.request).then(function (cached) {
        return cached || caches.match("/");
      });
    })
  );
});

/* Push notifications */
self.addEventListener("push", function (e) {
  if (!e.data) return;
  try {
    var data = e.data.json();
    var options = {
      body: data.body || "",
      icon: "/static/img/icon-192.png",
      badge: "/static/img/icon-192.png",
      data: { url: data.url || "/" },
      actions: data.actions || [],
    };
    e.waitUntil(self.registration.showNotification(data.title || "NamVibe", options));
  } catch (err) {
    e.waitUntil(self.registration.showNotification("NamVibe", { body: "New notification", icon: "/static/img/icon-192.png" }));
  }
});

self.addEventListener("notificationclick", function (e) {
  e.notification.close();
  var url = e.notification.data && e.notification.data.url ? e.notification.data.url : "/";
  e.waitUntil(clients.openWindow(url));
});