/* Dendrite service worker.
 *
 * Bewust conservatief. Een agressieve cache in een app die met een API praat levert
 * stale data en spookbugs op, dus:
 *   - /api/**            : NOOIT cachen. Altijd netwerk.
 *   - /_next/static/**   : cache-first. Die bestanden hebben een hash in de naam en
 *                          zijn onveranderlijk, dus dit is veilig en maakt starten snel.
 *   - navigaties         : network-first met de cache als terugval, zodat de app opent
 *                          zonder verbinding en je een shell ziet i.p.v. de dino.
 *   - de rest            : netwerk, cache als terugval.
 *
 * CACHE bevat de versie. Bij een nieuwe deploy bump je die en ruimt activate de oude op.
 */
const CACHE = "dendrite-v2";
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
  if (url.pathname.startsWith("/api/")) return;   // data gaat nooit in de cache

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
