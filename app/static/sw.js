// Deliberately minimal. Its only real job is to exist -- Chrome/Edge
// won't offer the native "Install" prompt for a page without an active
// service worker, even one that does no caching. If you want the widget
// to keep showing last-known data while offline, that's a real feature
// to add here later (cache the last /api/widget/today response), not
// something this version does.

self.addEventListener("install", (event) => {
    self.skipWaiting();
});

self.addEventListener("activate", (event) => {
    self.clients.claim();
});

self.addEventListener("fetch", (event) => {
    // Pass-through only -- always hits the network, no offline caching yet.
    event.respondWith(fetch(event.request));
});
