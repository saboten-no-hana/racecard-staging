/* Service Worker（ホーム画面に追加して使う時・電波が弱い時のため、2026-10-19〜）
   - ページ本体（出走カード・結果カード）・JS・出馬表（races.json）・結果（results.json）: ネットワーク優先（更新をすぐ反映）。つながらない時だけ保存済みのものを使う
   - フォント・勝負服・アイコン: 保存済みを優先（めったに変わらない）。中身を差し替えた時は STATIC の番号を上げる
   利用者のデータ（★・入力内容）は扱わない（localStorage のまま） */
const STATIC = 'racecard-static-v1';
const PAGES = 'racecard-pages-v1';
const PRECACHE_PAGES = ['./', 'index.html', 'result/', 'clubs.js', 'silks-shapes.js', 'qr.js', 'card-core.js', 'manifest.webmanifest'];  // result/ は結果カード（10/24〜）
const PRECACHE_STATIC = ['fonts/ipaexg.ttf', 'icon.svg'];

self.addEventListener('install', e => {
  // フォントは直前にページが読んだものがブラウザのキャッシュから入るので、二重に通信はしない
  e.waitUntil(Promise.all([caches.open(PAGES).then(c => c.addAll(PRECACHE_PAGES)), caches.open(STATIC).then(c => c.addAll(PRECACHE_STATIC))])
    .then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  // 消すのはこのページの古いキャッシュだけ（10/26〜）。同じドメインのテスト環境（racecard-stg-…）や、ほかのページのキャッシュは残す
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => /^racecard-(?!stg-)/.test(k) && k !== STATIC && k !== PAGES).map(k => caches.delete(k))))
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
  }).catch(() => caches.match(req, {ignoreSearch: true}).then(hit => hit || (req.mode === 'navigate'
    // 保存がない時は、結果カードの中なら保存済みの結果カード、それ以外は出走カードを返す（10/26〜。以前は結果カードでも出走カードを返していた）
    ? caches.match(/\/result\/?$/.test(url.pathname) || url.pathname.includes('/result/') ? 'result/' : 'index.html')
    : Response.error()))));
});
