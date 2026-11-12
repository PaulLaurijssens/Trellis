/* Trellis service worker.
 *
 * Conservative on purpose. An aggressive cache in an app that talks to an API gives
 * stale data and ghost bugs, so:
 *   - /api/**            : NEVER cached. Always the network.
 *   - /_next/static/**   : cache-first. These files have a hash in their name and never
 *                          change, so this is safe and makes starting fast.
 *   - navigations        : network-first with the cache as fallback, so the app opens
 *                          offline and you see a shell instead of the dinosaur.
 *   - the rest           : network, cache as fallback.
 *
 * CACHE holds the version. Bump it on a new deploy and activate cleans up the old one.
 */
const CACHE = "trellis-v6";
const PRECACHE = ["/", "/manifest.webmanifest", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((c) => c.addAll(PRECACHE)).catch(() => {}).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("message", (event) => {
  if (event.data === "SKIP_WAITING") self.skipWaiting();
});

function isImmutableAsset(url) {
  return url.pathname.startsWith("/_next/static/") ||
         url.pathname.startsWith("/icons/") ||
         url.pathname.startsWith("/fonts/");
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith("/api/")) return;   // data never goes into the cache

  if (isImmutableAsset(url)) {
    event.respondWith(
      caches.match(req).then((hit) => hit || fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
        return res;
      }))
    );
    return;
  }

  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => caches.match(req).then((hit) => hit || caches.match("/")))
    );
    return;
  }

  event.respondWith(fetch(req).catch(() => caches.match(req)));
});
