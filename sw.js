const CACHE_NAME = 'essay-viewer-v2';
const APP_SHELL = [
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
  const isSameOrigin = url.origin === self.location.origin;
  const isDataRequest = isSameOrigin && url.pathname.endsWith('.json');
  const isPageRequest = request.mode === 'navigate' || (isSameOrigin && url.pathname.endsWith('.html'));

  if (isDataRequest || isPageRequest) {
    // 데이터(json)와 페이지(html)는 항상 최신이 우선(네트워크 우선).
    // 새 버전을 배포해도 캐시된 옛 화면이 계속 보이지 않도록, 온라인일 땐 무조건 서버 응답을 쓰고
    // 오프라인일 때만 마지막으로 캐시된 버전을 대신 보여준다.
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
