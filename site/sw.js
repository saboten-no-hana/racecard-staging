/* Service Worker（ホーム画面に追加して使う時・電波が弱い時のため、2026-10-19〜）
   - ページ本体・JS・出馬表（races.json）: ネットワーク優先（更新をすぐ反映）。つながらない時だけ保存済みのものを使う
   - フォント・勝負服・アイコン: 保存済みを優先（めったに変わらない）。中身を差し替えた時は STATIC の番号を上げる
   利用者のデータ（★・入力内容）は扱わない（localStorage のまま） */
const STATIC = 'racecard-static-v1';
const PAGES = 'racecard-pages-v1';
const PRECACHE_PAGES = ['./', 'index.html', 'clubs.js', 'silks-shapes.js', 'qr.js', 'card-core.js', 'manifest.webmanifest'];
const PRECACHE_STATIC = ['fonts/ipaexg.ttf', 'icon.svg'];

self.addEventListener('install', e => {
  // フォントは直前にページが読んだものがブラウザのキャッシュから入るので、二重に通信はしない
  e.waitUntil(Promise.all([caches.open(PAGES).then(c => c.addAll(PRECACHE_PAGES)), caches.open(STATIC).then(c => c.addAll(PRECACHE_STATIC))])
    .then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== STATIC && k !== PAGES).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
const isStatic = p => /\/(fonts|silks)\/|\.(png|svg|ttf)$/.test(p);
self.addEventListener('fetch', e => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;   // Google Fonts など他のサイトは触らない
  if (isStatic(url.pathname)) {
    e.respondWith(caches.match(req).then(hit => hit || fetch(req).then(res => {
      if (res.ok) { const cp = res.clone(); caches.open(STATIC).then(c => c.put(req, cp)); }
      return res;
    })));
    return;
  }
  e.respondWith(fetch(req).then(res => {
    if (res.ok) { const cp = res.clone(); caches.open(PAGES).then(c => c.put(req, cp)); }
    return res;
  }).catch(() => caches.match(req, {ignoreSearch: true}).then(hit => hit || (req.mode === 'navigate' ? caches.match('index.html') : Response.error()))));
});
