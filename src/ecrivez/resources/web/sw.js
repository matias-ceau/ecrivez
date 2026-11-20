"use strict";
// Keeps the page openable when the house cannot be reached. Never touches /api:
// audio waits in the page's own queue, not here.
const CACHE = "ecrivez-1";
const SHELL = ["/", "/manifest.webmanifest", "/icon-192.png", "/icon-512.png"];
const PATIENCE_MS = 4000;

function keep(path, response) {
  if (!response.ok) return Promise.resolve();
  if (path === "/" && response.headers.get("X-Ecrivez") !== "page") return Promise.resolve();  // access code page
  const copy = response.clone();
  return caches.open(CACHE).then(cache => cache.put(path, copy));
}

self.addEventListener("install", event => event.waitUntil(
  Promise.all(SHELL.map(path => fetch(path, {credentials: "same-origin"}).then(r => keep(path, r))))
    .then(() => self.skipWaiting())
));
self.addEventListener("activate", event => event.waitUntil(self.clients.claim()));

self.addEventListener("fetch", event => {
  const url = new URL(event.request.url);
  if (event.request.method !== "GET" || url.origin !== location.origin || !SHELL.includes(url.pathname)) return;
  const giveUp = new AbortController();
  const timer = setTimeout(() => giveUp.abort(), PATIENCE_MS);
  event.respondWith(
    fetch(event.request, {signal: giveUp.signal})
      .then(response => { event.waitUntil(keep(url.pathname, response)); return response; })
      .catch(() => caches.match(url.pathname).then(kept => kept || Response.error()))
      .finally(() => clearTimeout(timer))
  );
});
