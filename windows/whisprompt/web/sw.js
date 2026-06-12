// Minimal service worker: network-first, required only for PWA installability.
self.addEventListener("fetch", (event) => {
  event.respondWith(fetch(event.request));
});
