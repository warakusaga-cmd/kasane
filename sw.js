const CACHE = 'kasane-v53';
const ASSETS = ['./', './index.html', './figures.js', './data.js', './foods.js',
                './manifest.json', './icon.png', './icon-192.png',
                './apple-touch-icon.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(ASSETS)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

// network-first so updates land, cache fallback so it works offline
self.addEventListener('fetch', e => {
  if (e.request.method !== 'GET') return;
  e.respondWith(
    fetch(e.request)
      .then(r => {
        const copy = r.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
        return r;
      })
      // ignoreSearch: data.js?v=3.1.2 のようにバージョン付きで来ても、
      // キャッシュ済みの data.js を返せるようにする（オフライン時の保険）
      .catch(() => caches.match(e.request, { ignoreSearch: true })
        .then(r => r || caches.match('./index.html')))
  );
});

// ===== 毎朝の通知（Web Push） =====
// iMac側の send_push.py が送ってくる。アプリを閉じていてもここが受けて通知を出す
self.addEventListener('push', e => {
  let d = { title: 'Kasane', body: '体重を測って記録しましょう' };
  try { Object.assign(d, e.data.json()); } catch (_) {}
  e.waitUntil(self.registration.showNotification(d.title, {
    body: d.body, icon: './icon-192.png', badge: './icon-192.png',
    tag: 'kasane-morning',            // 同じ通知が溜まらないよう上書きする
    data: { url: './' }
  }));
});

// 通知タップ → アプリを開く（既に開いていればそれを前に出す）
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil(clients.matchAll({ type: 'window', includeUncontrolled: true }).then(ws => {
    for (const w of ws) if ('focus' in w) return w.focus();
    return clients.openWindow('./');
  }));
});
