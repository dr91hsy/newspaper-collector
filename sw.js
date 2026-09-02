const CACHE_NAME = 'essay-viewer-v1';
const APP_SHELL = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
        )
      )
  );
  self.clients.claim();
});

// data.json / opinions/*.json 은 ?t=timestamp 캐시버스터가 붙어서 매번 URL이 달라지므로,
// 쿼리스트링을 뺀 URL을 캐시 키로 써서 오프라인일 때도 마지막으로 받은 데이터를 찾을 수 있게 한다.
function cacheKeyFor(request) {
  const url = new URL(request.url);
  url.search = '';
  return url.toString();
}

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  const isDataRequest = url.origin === self.location.origin && url.pathname.endsWith('.json');

  if (isDataRequest) {
    // 데이터는 최신이 우선(네트워크 우선), 오프라인이면 마지막으로 캐시된 버전을 대신 보여준다.
    event.respondWith(
      fetch(request)
        .then((response) => {
          const key = cacheKeyFor(request);
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(key, copy));
          return response;
        })
        .catch(() => caches.match(cacheKeyFor(request)))
    );
    return;
  }

  // 정적 자산(HTML/아이콘/manifest 등)은 캐시 우선, 없으면 네트워크에서 받아와 캐시에 채운다.
  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((response) => {
        const copy = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
        return response;
      });
    })
  );
});
