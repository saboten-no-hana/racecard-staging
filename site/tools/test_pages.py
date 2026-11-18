"""公開ページ（出走カード・結果カード）を実際のブラウザで開くテスト（11/18〜）
- ページのスクリプトがエラーで止まらないこと（card-core.js と画面の食い違いなど。11/06 の文字色の不具合のような止まり方を push の時点で見つける）
- 画像（PNG）が描かれること（縦長・横長）、2倍の解像度で書き出されること
- 以前の既定値のアカウント名「@your_account」が空になり、描画用の値（_anyUma）が保存データに入らないこと
- 結果カードが出走カードの保存データ（racecard.v2）を書き換えないこと
- スマホ幅（390px）で折りたたみを開いても横スクロールが出ないこと
画素までは比べない（作業環境と GitHub Actions でフォントの細部が違い、誤って失敗しやすいため。描画を変えた時は作業環境で前後を画素で比べる）。

Playwright（と Chromium）がなければ飛ばす。GitHub Actions では RACECARD_REQUIRE_BROWSER=1 にして、ない時は失敗にする（.github/workflows/test.yml）。
データ（races.json など）はテストの中で作った架空のものを返す。JRA・Google Fonts にはアクセスしない。
"""
import base64, functools, http.server, json, os, struct, tempfile, threading, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REQUIRE = os.environ.get('RACECARD_REQUIRE_BROWSER') == '1'
NOW = '2026-11-13T12:00:00+09:00'   # 金曜の昼（土日の馬番が出たあと）

try:
    from playwright.sync_api import sync_playwright
except ImportError:   # pragma: no cover
    sync_playwright = None


def horse(i, d, venue, r, club, **kw):
    h = {'key': f'{d}|{venue}|{r}|20220000{i:02d}', 'horseId': f'20220000{i:02d}', 'name': f'テストホース{"アイウエオカ"[i % 6]}', 'clubId': club,
         'date': d, 'venue': venue, 'r': r, 'time': f'{9 + r}:{(i * 7) % 60:02d}', 'raceName': 'テスト特別', 'grade': '', 'cls': '2勝クラス',
         'surface': '芝', 'dist': 1600, 'jockey': '▲ 騎手 太郎' if i % 3 == 0 else '騎手 次郎', 'waku': str(i % 8 + 1), 'umaban': str(i + 1),
         'sexAge': '牡3', 'weight': '57.0', 'status': ''}
    h.update(kw)
    return h


CLUBS = ['carrot', 'silk', 'sunday', 'normandy', 'blooming', 'lord', 'win', 'g1']
RACES = {'source': 'test', 'updated': '2026-11-13T10:12+09:00',
         'days': [{'date': '2026-11-14', 'venues': ['東京', '京都']}, {'date': '2026-11-15', 'venues': ['東京', '京都']}],
         'horses': [horse(i, '2026-11-14' if i < 5 else '2026-11-15', '東京' if i % 2 else '京都', i + 1, CLUBS[i],
                          **({'status': '取消'} if i == 3 else {})) for i in range(8)]}
RESULTS = {'source': 'test', 'updated': '2026-11-15T16:43+09:00', 'days': RACES['days'],
           'horses': [{**h, 'finish': str(i + 1), 'pop': str(8 - i), 'rtime': '1:34.5', 'last3f': '34.0', 'runners': 16}
                      for i, h in enumerate(RACES['horses'])]}
RETIRED = {'updated': '2026-11-12T18:44+09:00', 'counts': {'2026-11-10': 1}, 'horses': {'2026-11-10': [['インタイホース', '父', '母']]}}


def card_state(n, size, handle='@your_account'):
    hs = []
    for i, x in enumerate(RACES['horses'][:n]):
        hs.append({'id': f'h{i}', 'horseId': x['horseId'], 'name': x['name'], 'clubId': x['clubId'], 'ownerLabel': '', 'date': x['date'],
                   'venue': x['venue'], 'r': str(x['r']), 'time': x['time'], 'raceName': x['raceName'], 'surface': x['surface'], 'dist': str(x['dist']),
                   'jockey': x['jockey'], 'sexAge': x['sexAge'], 'weight': x['weight'], 'waku': x['waku'], 'umaban': x['umaban'], 'status': x['status'],
                   'kuchi': ['none', 'win', 'wait', 'lose'][i % 4], 'photo': '', 'customSilks': None})
    return {'settings': {'title': '今週の出走予定', 'post': None, 'handle': handle, 'theme': 'turf', 'size': size, 'showKuchi': True, 'order': 'venue',
                         'showCount': True, '_anyUma': True},
            'horses': hs, 'myHorses': [RACES['horses'][0]['horseId']], 'myNames': {RACES['horses'][0]['horseId']: RACES['horses'][0]['name']},
            'myPending': ['インタイホース'], 'myNamed': [RACES['horses'][1]['name']]}


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def png_size(b):
    return struct.unpack('>II', b[16:24])


@unittest.skipUnless(sync_playwright or REQUIRE, 'playwright がない')
class TestPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.symlink(ROOT, os.path.join(cls.tmp.name, 'racecard'))   # 公開ページと同じ /racecard/ の形で配信する（結果カードの <base href="../"> のため）
        handler = functools.partial(Quiet, directory=cls.tmp.name)
        cls.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f'http://127.0.0.1:{cls.httpd.server_address[1]}/racecard/'
        cls.pw = sync_playwright().start()
        try:
            cls.browser = cls.pw.chromium.launch()
        except Exception as e:   # ブラウザが入っていない
            cls.pw.stop()
            cls.tearDownServer()
            if REQUIRE:
                raise
            raise unittest.SkipTest(f'Chromium を起動できない: {e}')

    @classmethod
    def tearDownServer(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.tmp.cleanup()

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.pw.stop()
        cls.tearDownServer()

    def open(self, path, storage, width=1280, mobile=False):
        ctx = self.browser.new_context(viewport={'width': width, 'height': 900}, has_touch=mobile, is_mobile=mobile,
                                       timezone_id='Asia/Tokyo', locale='ja-JP')
        self.addCleanup(ctx.close)
        page = ctx.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.route('**/fonts.googleapis.com/**', lambda r: r.abort())
        page.route('**/fonts.gstatic.com/**', lambda r: r.abort())
        def fulfill(body):   # 引数が2つの関数は Playwright が (route, request) で呼ぶので、1つにする
            text = json.dumps(body, ensure_ascii=False)
            return lambda r: r.fulfill(status=200, content_type='application/json', body=text)
        for name, body in (('races', RACES), ('results', RESULTS), ('retired', RETIRED)):
            page.route(f'**/data/{name}.json', fulfill(body))
        page.route('**/data/status.json', lambda r: r.fulfill(status=404, body=''))
        page.clock.install(time=NOW)
        init = ''.join(f'localStorage.setItem({json.dumps(k)}, {json.dumps(json.dumps(v, ensure_ascii=False))});' for k, v in storage.items())
        page.add_init_script("if(!sessionStorage.getItem('_init')){sessionStorage.setItem('_init','1');" + init + '}')
        page.goto(self.base + path)
        page.wait_for_selector('#p-list .prow', timeout=20000)
        return page, errors

    def image(self, page):
        """#out に描かれた PNG（新しく描き直されたもの）の (幅, 高さ)"""
        page.wait_for_function("document.querySelector('#out').src.startsWith('blob:')", timeout=20000)
        page.wait_for_timeout(600)   # 描き直しの待ち（schedule は 140ms 後）
        b64 = page.evaluate("""async () => { const b = await (await fetch(document.querySelector('#out').src)).blob();
          return await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result.split(',')[1]); f.readAsDataURL(b); }); }""")
        return png_size(base64.b64decode(b64))

    def no_hscroll(self, page):
        page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
        page.wait_for_timeout(200)
        sw, cw = page.evaluate('[document.documentElement.scrollWidth, document.documentElement.clientWidth]')
        self.assertLessEqual(sw, cw, '横スクロールが出ている')

    def test_card_page(self):
        page, errors = self.open('', {'racecard.v2': card_state(6, '4:5')})
        w, h = self.image(page)
        self.assertEqual(w, 2160)                          # 縦長（幅1080）を2倍の解像度で
        self.assertGreaterEqual(h, 2160)                   # 正方形より低くはならない
        page.wait_for_timeout(400)   # 保存（300ms 後）
        saved = json.loads(page.evaluate("localStorage.getItem('racecard.v2')"))
        self.assertEqual(saved['settings']['handle'], '', '以前の既定値 @your_account が空になっていない')
        self.assertNotIn('_anyUma', saved['settings'], '描画用の値が保存データに入っている')
        self.assertEqual(page.input_value('#s-handle'), '')
        page.check('input[name=size][value="16:9"]', force=True)
        w, h = self.image(page)
        self.assertGreater(w, h)                           # 横長
        page.locator('#p-list button.add:not([disabled])').first.click()
        self.assertEqual(page.inner_text('#count'), '7')   # 一覧から追加できる
        self.assertIn('登録抹消', page.inner_text('#p-retired'))   # 出走待ちの★の馬の登録抹消のバナー
        self.assertEqual(errors, [])

    def test_card_page_new_user(self):
        """初めての人: アカウント名は空、出走馬なしでも画像が出る"""
        page, errors = self.open('', {})
        self.assertEqual(self.image(page), (2160, 2700))
        self.assertEqual(page.input_value('#s-handle'), '')
        self.assertEqual(errors, [])

    def test_result_page(self):
        card = card_state(3, '16:9')
        res = {'settings': {'title': '出走結果', 'handle': '@your_account', 'theme': 'night', 'size': '4:5', 'order': 'venue',
                            'showCount': True, 'showTally': True},
               'horses': [{**card_state(8, '4:5')['horses'][i], 'finish': str(i + 1), 'pop': '3', 'kuchi': None} for i in range(8)]}
        page, errors = self.open('result/', {'racecard.v2': card, 'racecard.result.v1': res})
        self.assertEqual(self.image(page)[0], 2160)
        page.wait_for_timeout(400)
        self.assertEqual(json.loads(page.evaluate("localStorage.getItem('racecard.result.v1')"))['settings']['handle'], '')
        self.assertEqual(json.loads(page.evaluate("localStorage.getItem('racecard.v2')")), card, '結果カードが racecard.v2 を書き換えた')
        self.assertEqual(errors, [])

    def test_result_page_inherits_handle(self):
        """結果カードを初めて開いた時、出走カードのアカウント名を引き継ぐ（以前の既定値 @your_account は引き継がない）"""
        for handle, want in (('@saboten_test', '@saboten_test'), ('@your_account', '')):
            with self.subTest(handle=handle):
                page, errors = self.open('result/', {'racecard.v2': card_state(2, '4:5', handle)})
                self.assertEqual(page.input_value('#s-handle'), want)
                self.assertEqual(errors, [])

    def test_phone_width(self):
        for path in ('', 'result/'):
            with self.subTest(path=path or 'index'):
                page, errors = self.open(path, {'racecard.v2': card_state(8, '4:5')}, width=390, mobile=True)
                self.image(page)
                self.no_hscroll(page)
                self.assertEqual(errors, [])


if __name__ == '__main__':
    unittest.main()
