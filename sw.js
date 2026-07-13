/*
 * Dept. Q. Bank — Service Worker
 * ================================================================
 * Strategy:
 *  - App shell (HTML/CSS/JS/icons)  → cache-first, refreshed in the background
 *  - Question data (data/*.json,
 *    config/modules.json)           → network-first, falls back to cache
 *    when offline. This means: online, you always get the newest
 *    professor guidance questions; offline, whatever you've already
 *    opened once still works.
 *
 * We deliberately do NOT hardcode every data/*.json path here — new
 * topic files get added constantly, and a stale precache list would
 * silently serve outdated exams. Instead, question files are cached
 * the first time they're fetched (runtime caching), so anything a
 * student has already opened once keeps working offline.
 * ================================================================
 */

const CACHE_VERSION = 'dqb-v1';
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const DATA_CACHE = `${CACHE_VERSION}-data`;

const SHELL_URLS = [
  './',
  './index.html',
  './manifest.json',
  './assets/css/styles.css',
  './assets/js/storage.js',
  './assets/js/exam.js',
  './assets/js/ui.js',
  './assets/js/app.js',
  './assets/images/icon.svg',
  './assets/images/icon-192.png',
  './assets/images/icon-512.png',
  './assets/images/favicon.png',
  './config/modules.json',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key.startsWith('dqb-') && key !== SHELL_CACHE && key !== DATA_CACHE)
          .map((key) => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

function isDataRequest(url) {
  return url.pathname.includes('/data/') || url.pathname.endsWith('config/modules.json');
}

async function networkFirst(request, cacheName) {
  try {
    const fresh = await fetch(request);
    const cache = await caches.open(cacheName);
    cache.put(request, fresh.clone());
    return fresh;
  } catch (err) {
    const cached = await caches.match(request);
    if (cached) return cached;
    throw err;
  }
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) {
    // Refresh in the background so the next visit gets the latest asset.
    fetch(request).then((fresh) => {
      caches.open(cacheName).then((cache) => cache.put(request, fresh));
    }).catch(() => {});
    return cached;
  }
  const fresh = await fetch(request);
  const cache = await caches.open(cacheName);
  cache.put(request, fresh.clone());
  return fresh;
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // don't touch cross-origin (fonts CDN, etc.)

  if (isDataRequest(url)) {
    event.respondWith(networkFirst(request, DATA_CACHE));
    return;
  }

  if (request.mode === 'navigate') {
    event.respondWith(
      networkFirst(request, SHELL_CACHE).catch(() => caches.match('./index.html'))
    );
    return;
  }

  event.respondWith(cacheFirst(request, SHELL_CACHE));
});
