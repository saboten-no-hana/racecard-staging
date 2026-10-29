"""tools/fetch_races.py のテスト（JRA にはアクセスしない。偽の出馬表ページで動かす）

実行: python3 -m unittest discover -s tools -p 'test_*.py'
GitHub では push のたびに .github/workflows/test.yml が実行する。
data/ は一時ディレクトリに差し替えるので、本物の races.json・cache.json は書き換えない。
"""
import io, json, os, sys, tempfile, unittest, warnings
from contextlib import redirect_stdout
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_races as fr

JST = fr.JST
warnings.simplefilter('ignore', ResourceWarning)   # fetch_races.py の json.dump(open(...)) は CPython ではすぐ閉じられる


class FakeJRA:
    """出馬表トップ → 開催のレース一覧 → 全レースまとめ／個別レース／馬のページ を返す偽物。
    races: [{'date': 'YYYY-MM-DD', 'venue_code': '05', 'r': 1, 'umaban': bool, 'horses': [(馬ID, 馬名, 馬主, 状態)]}]"""

    def __init__(self, races):
        self.races = races
        self.fail = 0          # この回数だけ通信エラーにする
        self.past = []         # トップに載せる終わった週の開催（種別 10 のリンク）の (日付, 場コード)
        self.requests = []

    def meetings(self):
        out = {}
        for r in self.races:
            out.setdefault((r['date'], r['venue_code']), []).append(r)
        return out

    @staticmethod
    def ymd8(d):
        return d.replace('-', '')

    def table(self, race, detail):
        y, m, d = map(int, race['date'].split('-'))
        rows = ''
        for i, (hid, name, owner, status) in enumerate(race['horses'], 1):
            num = str(i) if race['umaban'] else ''
            waku = f'<img alt="枠{i}">' if race['umaban'] else ''
            own = f'<p class="owner">{owner}</p>' if detail and race['umaban'] else ''
            st = f'<td>{status}</td>' if status else ''
            rows += (f'<tr><td class="waku">{waku}</td><td class="num">{num}</td>'
                     f'<td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud00{hid}/AA">{name}</a>{own}</td>'
                     f'<td class="age">牡4</td><td class="weight">57.0<span>kg</span></td>'
                     f'<td class="jockey"><a href="#">騎手 {i}</a></td>{st}</tr>')
        venue = fr.VENUES[race['venue_code']]
        return (f'<table><caption><div class="race_header"><div class="date_line">'
                f'<div class="date">{y}年{m}月{d}日（土曜） 4回{venue}7日</div><div class="time">発走時刻：15時00分</div></div>'
                f'<div class="race_number"><img alt="{race["r"]}レース"></div><div class="race_name">テスト特別</div>'
                f'<div class="cell class">2勝クラス</div><div class="cell course">1,600メートル（芝）</div></div></caption>'
                f'<tbody>{rows}</tbody></table>')

    def get(self, _self, cname, post, path):
        _self.count += 1
        self.requests.append(cname)
        if self.fail > 0:
            self.fail -= 1
            raise RuntimeError('取得できませんでした: ' + cname)
        ms = self.meetings()
        # cname: pw01drl00{場2}{年4}{回2}{日2}{年月日8} / pw01des01{同じ} / pw01dde01{場2}{年4}{回2}{日2}{R2}{年月日8}
        if cname == 'pw01dli00/F3':
            return ''.join(f'<a href="x?CNAME=pw01drl10{vc}20260406{self.ymd8(d)}/16"></a>' for d, vc in self.past) + \
                ''.join(f'<a href="x?CNAME=pw01drl00{vc}20260407{self.ymd8(d)}/AB"></a>' for d, vc in ms)
        for (d, vc), races in ms.items():
            if cname.startswith(f'pw01drl00{vc}20260407{self.ymd8(d)}'):
                return ''.join(f'<a href="x?CNAME=pw01dde01{vc}20260407{r["r"]:02d}{self.ymd8(d)}/CD"></a>' for r in races) + \
                    f'<a href="x?CNAME=pw01des01{vc}20260407{self.ymd8(d)}/EF"></a>'
            if cname.startswith(f'pw01des01{vc}20260407{self.ymd8(d)}'):
                return ''.join(self.table(r, False) for r in races)
            for r in races:
                if cname.startswith(f'pw01dde01{vc}20260407{r["r"]:02d}{self.ymd8(d)}'):
                    return self.table(r, True)
        if cname.startswith('pw01dud00'):
            hid = cname[9:19]
            for r in self.races:
                for h in r['horses']:
                    if h[0] == hid:
                        return f'<dl><dt>馬主名</dt><dd>{h[2]}</dd></dl>'
        return ''


def day(n):
    return (datetime.now(JST).date() + timedelta(days=n)).isoformat()


CARROT = '(有)キャロットファーム'
SILK = '(有)シルクレーシング'


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.patches = [mock.patch.object(fr, 'DATA', d), mock.patch.object(fr, 'OUT', os.path.join(d, 'races.json')),
                        mock.patch.object(fr, 'CACHE', os.path.join(d, 'cache.json')), mock.patch.object(fr, 'WAIT', 0),
                        mock.patch.object(fr, 'SEEN', os.path.join(d, 'seen.json')),
                        mock.patch.object(fr, 'REGIST', os.path.join(d, 'regist.json')),
                        mock.patch.object(fr.time, 'sleep', lambda s: None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_main(self, jra, args, cache=None, races=None, summary=False):
        if cache is not None:
            json.dump({'clubOf': cache}, open(fr.CACHE, 'w'))
        if races is not None:
            json.dump(races, open(fr.OUT, 'w'))
        env = {}
        if summary:
            env['GITHUB_STEP_SUMMARY'] = os.path.join(self.tmp.name, 'summary.md')
        with mock.patch.object(fr.Fetcher, '_get', lambda s, c, p, path: jra.get(s, c, p, path)), \
                mock.patch.object(sys, 'argv', ['fetch_races.py'] + args), mock.patch.dict(os.environ, env), \
                redirect_stdout(io.StringIO()) as out:
            code = fr.main()
        self.log = out.getvalue()
        data = json.load(open(fr.OUT)) if os.path.exists(fr.OUT) else {'horses': [], 'days': []}
        cache = json.load(open(fr.CACHE))['clubOf'] if os.path.exists(fr.CACHE) else {}
        return code, data, cache


class TestFetch(Base):
    def test_jockey_mark(self):
        """騎手の減量記号は「▲ 名前」の形で取り込む（出馬表の書き方は 10/26 に本物の先週分で確認）"""
        html = ('<table><tbody>'
                '<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002023100001/AA">ウマ</a></td>'
                '<td class="jockey"><span class="mark jockey" title="3kg減量">▲</span><a href="#" onclick="return doAction(\'/JRADB/accessK.html\', \'pw04kmk001218/8D\');">遠藤 汰月</a></td></tr>'
                '<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002023100002/AA">ウマ2</a></td>'
                '<td class="jockey"><a href="#">菅原 明良</a></td></tr>'
                '</tbody></table>')
        from bs4 import BeautifulSoup
        rows = fr.parse_rows(BeautifulSoup(html, 'html.parser').select_one('table'))
        self.assertEqual([h['jockey'] for h in rows], ['▲ 遠藤 汰月', '菅原 明良'])

    def test_jockey_without_link(self):
        """短期免許が出たばかりの外国人騎手は、騎手のページへのリンクがなく文字だけ（10/29 の東京の全レースまとめで確認）"""
        html = ('<table><tbody>'
                '<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002023100003/AA">ウマ3</a></td>'
                '<td class="jockey">A.プーシャン</td></tr>'
                '<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002023100004/AA">ウマ4</a></td>'
                '<td class="jockey"><span class="mark jockey" title="3kg減量">▲</span>リンク ナシ</td></tr>'
                '<tr><td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud002023100005/AA">ウマ5</a></td><td class="jockey"></td></tr>'
                '</tbody></table>')
        from bs4 import BeautifulSoup
        rows = fr.parse_rows(BeautifulSoup(html, 'html.parser').select_one('table'))
        self.assertEqual([h['jockey'] for h in rows], ['A.プーシャン', '▲ リンク ナシ', ''])

    def test_club_horses_only_and_fields(self):
        """クラブ名義の馬だけを出力し、性齢・斤量・馬番も入る。個人馬主の名前は保存しない"""
        jra = FakeJRA([{'date': day(1), 'venue_code': '05', 'r': 11, 'umaban': True,
                        'horses': [('2021000001', 'クラブウマ', CARROT, ''), ('2021000002', 'コジンウマ', '山田太郎', '')]}])
        code, data, cache = self.run_main(jra, [])
        self.assertEqual(code, 0)
        self.assertEqual([h['name'] for h in data['horses']], ['クラブウマ'])
        h = data['horses'][0]
        self.assertEqual((h['clubId'], h['sexAge'], h['weight'], h['umaban'], h['r'], h['venue']), ('carrot', '牡4', '57.0', '1', 11, '東京'))
        self.assertEqual(cache, {'2021000001': 'carrot', '2021000002': ''})
        self.assertNotIn('山田', open(fr.CACHE).read() + open(fr.OUT).read())

    def test_thursday_horse_pages(self):
        """馬番なし（木曜）は、未記録の馬だけ馬のページを読む"""
        jra = FakeJRA([{'date': day(2), 'venue_code': '08', 'r': 3, 'umaban': False,
                        'horses': [('2022000001', 'アタラシイウマ', SILK, ''), ('2022000002', 'キロクズミ', CARROT, '')]}])
        code, data, cache = self.run_main(jra, [], cache={'2022000002': 'carrot'})
        self.assertEqual([h['name'] for h in data['horses']], ['アタラシイウマ', 'キロクズミ'])
        self.assertEqual(sum(1 for c in jra.requests if c.startswith('pw01dud')), 1)
        self.assertFalse(any(c.startswith('pw01dde') for c in jra.requests))   # 馬番なしの時は個別ページを読まない

    def regist(self, rows):
        with open(fr.REGIST, 'w', encoding='utf-8') as fp:
            json.dump({'updated': '', 'counts': {'2026-10-22': len(rows)}, 'horses': {'2026-10-22': rows}}, fp, ensure_ascii=False)

    def test_thursday_regist(self):
        """木曜: 競走馬登録の一覧に馬名と生年が一致する馬は馬のページを読まない。判定は cache.json に記録せず、馬番が出た日に確定する"""
        horses = [('2024000001', 'シンバクラブ', CARROT, ''), ('2024000002', 'シンバコジン', '山田太郎', ''),
                  ('2024000003', 'トシチガイ', SILK, ''), ('2024000004', 'イチランニナイ', '鈴木花子', '')]
        self.regist([['シンバクラブ', '2024-03-01', 'carrot', '父', '母'], ['シンバコジン', '2024-04-01', '', '父', '母'],
                     ['トシチガイ', '2023-04-01', '', '父', '母']])   # 生年が違う → 別の馬とみなして馬のページを読む
        jra = FakeJRA([{'date': day(2), 'venue_code': '05', 'r': 1, 'umaban': False, 'horses': horses}])
        code, data, cache = self.run_main(jra, [], summary=True)
        self.assertEqual(code, 0)
        self.assertEqual([h['name'] for h in data['horses']], ['シンバクラブ', 'トシチガイ'])
        self.assertEqual(sorted(c[9:19] for c in jra.requests if c.startswith('pw01dud')), ['2024000003', '2024000004'])
        self.assertEqual(cache, {'2024000003': 'silk', '2024000004': ''})   # 一覧で判定した馬は記録しない
        self.assertIn('登録一覧で判定 2', self.log)
        self.assertIn('競走馬登録の一覧で判定（馬のページを読まなかった）: 2頭（うちクラブ馬 1頭）', open(os.path.join(self.tmp.name, 'summary.md'), encoding='utf-8').read())
        # 馬番が出た日: 記録にない馬がいるので個別レースのページを読み、馬主名で確定する
        jra = FakeJRA([{'date': day(1), 'venue_code': '05', 'r': 1, 'umaban': True, 'horses': horses}])
        code, data, cache = self.run_main(jra, [])
        self.assertTrue(any(c.startswith('pw01dde') for c in jra.requests))
        self.assertEqual(cache['2024000001'], 'carrot')
        self.assertEqual(cache['2024000002'], '')
        self.assertFalse(any(c.startswith('pw01dud') for c in jra.requests))

    def test_thursday_regist_wrong(self):
        """一覧の判定が誤っていても（クラブ馬を「クラブ以外」）、馬番が出た日に個別ページで直る"""
        horses = [('2024000011', 'マチガイ', CARROT, '')]
        self.regist([['マチガイ', '2024-03-01', '', '父', '母']])
        code, data, cache = self.run_main(FakeJRA([{'date': day(2), 'venue_code': '05', 'r': 1, 'umaban': False, 'horses': horses}]), [])
        self.assertEqual(data['horses'], [])
        code, data, cache = self.run_main(FakeJRA([{'date': day(1), 'venue_code': '05', 'r': 1, 'umaban': True, 'horses': horses}]), [])
        self.assertEqual([h['name'] for h in data['horses']], ['マチガイ'])
        self.assertEqual(cache['2024000011'], 'carrot')

    def test_regist_broken(self):
        """regist.json が壊れていても止めず、今までどおり馬のページを読む"""
        with open(fr.REGIST, 'w', encoding='utf-8') as fp:
            fp.write('{壊れている')
        jra = FakeJRA([{'date': day(2), 'venue_code': '05', 'r': 1, 'umaban': False, 'horses': [('2024000021', 'ウマ', CARROT, '')]}])
        code, data, cache = self.run_main(jra, [])
        self.assertEqual(code, 0)
        self.assertEqual([h['name'] for h in data['horses']], ['ウマ'])
        self.assertEqual(cache, {'2024000021': 'carrot'})
        self.assertIn('regist.json を読めなかった', self.log)

    def test_recheck_club_horse_that_left_club(self):
        """クラブ馬と記録済みでも、馬番が出た明日以降のレースでは個別ページで確かめ直す（地方から戻った馬）"""
        jra = FakeJRA([{'date': day(1), 'venue_code': '05', 'r': 1, 'umaban': True,
                        'horses': [('2020000001', 'モドッテキタ', '地方太郎', ''), ('2020000002', 'クラブノママ', CARROT, '')]}])
        code, data, cache = self.run_main(jra, [], cache={'2020000001': 'carrot', '2020000002': 'carrot'})
        self.assertEqual([h['name'] for h in data['horses']], ['クラブノママ'])
        self.assertEqual(cache['2020000001'], '')
        self.assertIn('名義が変わった: モドッテキタ', self.log)

    def test_no_recheck_for_today(self):
        """今日のレースは確かめ直さない（前日の取得で確認済み）"""
        jra = FakeJRA([{'date': day(0), 'venue_code': '05', 'r': 1, 'umaban': True,
                        'horses': [('2020000002', 'クラブノママ', CARROT, '')]}])
        self.run_main(jra, [], cache={'2020000002': 'carrot'})
        self.assertFalse(any(c.startswith('pw01dde') for c in jra.requests))

    def test_scratched_status(self):
        jra = FakeJRA([{'date': day(1), 'venue_code': '09', 'r': 5, 'umaban': True,
                        'horses': [('2021000003', 'トリケシ', CARROT, '取消')]}])
        _, data, _ = self.run_main(jra, [])
        self.assertEqual(data['horses'][0]['status'], '取消')


class TestModes(Base):
    def test_umaban_waits_then_ready(self):
        """馬番待ち → 馬番が出たら取得して終わる。五月雨の取り直しでは確かめ直しの個別ページを読み直さない"""
        race = {'date': day(1), 'venue_code': '05', 'r': 1, 'umaban': False, 'horses': [('2020000002', 'クラブノママ', CARROT, '')]}
        jra = FakeJRA([race])
        calls = {'n': 0}
        orig = jra.get

        def get(s, c, p, path):
            if c == 'pw01dli00/F3':
                calls['n'] += 1
                if calls['n'] == 2:
                    race['umaban'] = True
            return orig(s, c, p, path)
        jra.get = get
        code, data, _ = self.run_main(jra, ['--mode', 'umaban', '--start', '00:00', '--until', '23:59', '--interval', '0'],
                                      cache={'2020000002': 'carrot'})
        self.assertEqual(code, 0)
        self.assertEqual(data['horses'][0]['umaban'], '1')
        self.assertEqual(sum(1 for c in jra.requests if c.startswith('pw01dde')), 1)

    def test_transient_error_recovers(self):
        """見張り中の通信エラーは、その回だけ。次の回で取れれば exit 0"""
        jra = FakeJRA([{'date': day(1), 'venue_code': '05', 'r': 1, 'umaban': True, 'horses': [('2021000001', 'クラブウマ', CARROT, '')]}])
        jra.fail = 2
        code, data, _ = self.run_main(jra, ['--mode', 'umaban', '--start', '00:00', '--until', '23:59', '--interval', '0'])
        self.assertEqual(code, 0)
        self.assertEqual(len(data['horses']), 1)

    def test_single_run_error_fails(self):
        """1回だけの取得（安全網・手動）が通信エラーなら exit 1"""
        jra = FakeJRA([])
        jra.fail = 99
        code, _, _ = self.run_main(jra, [])
        self.assertEqual(code, 1)

    def test_records_kept_when_attempt_fails(self):
        """試行の途中で止まっても（通信エラー）、それまでに分かった名義は cache.json に残す（次の試行で読み直さないため）"""
        jra = FakeJRA([{'date': day(2), 'venue_code': '08', 'r': 3, 'umaban': False,
                        'horses': [('2022000001', 'サキニヨム', SILK, ''), ('2022000002', 'ツギデオチル', CARROT, '')]}])
        orig = jra.get

        def get(s, c, p, path):
            if c.startswith('pw01dud002022000002'):
                raise RuntimeError('取得できませんでした: ' + c)
            return orig(s, c, p, path)
        jra.get = get
        code, data, cache = self.run_main(jra, [])
        self.assertEqual(code, 1)
        self.assertEqual(cache, {'2022000001': 'silk'})   # 1頭目の名義は残っている
        self.assertEqual(data['horses'], [])              # races.json は書かない（途中のものを公開しない）

    def test_persistent_error_fails(self):
        """最後まで通信エラーで一度も取れなければ exit 1"""
        jra = FakeJRA([])
        jra.fail = 10 ** 6
        soon = (datetime.now(JST) + timedelta(minutes=1)).strftime('%H:%M')
        code, _, _ = self.run_main(jra, ['--mode', 'confirm', '--start', '00:00', '--until', soon, '--watch-until', soon, '--interval', '5'])
        self.assertEqual(code, 1)

    def test_confirm_new_day(self):
        """confirm: races.json にない新しい開催日が載ったら取得する"""
        jra = FakeJRA([{'date': day(2), 'venue_code': '05', 'r': r, 'umaban': False,
                        'horses': [(f'20210001{r:02d}', f'ウマ{r}', CARROT, '')]} for r in range(1, 13)])
        code, data, _ = self.run_main(jra, ['--mode', 'confirm', '--start', '00:00', '--until', '23:59', '--interval', '0'],
                                      races={'days': [{'date': day(-5), 'venues': ['東京']}], 'horses': []})
        self.assertEqual(code, 0)
        self.assertEqual(len(data['horses']), 12)

    def at_today(self, hhmm):
        h, m = map(int, hhmm.split(':'))
        return datetime.now(JST).replace(hour=h, minute=m, second=0, microsecond=0).isoformat(timespec='minutes')

    def test_umaban_second_run_skips(self):
        """馬番の見張りが2回目に動いた時（外からの起動と定期実行が重なった時など）は JRA にアクセスしない（10/26〜）"""
        jra = FakeJRA([{'date': day(1), 'venue_code': '05', 'r': 1, 'umaban': True, 'horses': [('2021000001', 'クラブウマ', CARROT, '')]}])
        done = {'updated': self.at_today('10:21'), 'days': [{'date': day(1), 'venues': ['東京']}],
                'horses': [{'date': day(1), 'horseId': '2021000001', 'umaban': '1', 'status': ''},
                           {'date': day(1), 'horseId': '2021000002', 'umaban': '', 'status': '取消'}]}
        code, _, _ = self.run_main(jra, ['--mode', 'umaban', '--start', '00:00', '--until', '23:59', '--interval', '0'], races=done, summary=True)
        self.assertEqual((code, jra.requests), (0, []))
        self.assertIn('取得済み', open(os.path.join(self.tmp.name, 'summary.md'), encoding='utf-8').read())

    def test_umaban_runs_when_not_done_today(self):
        """馬番がそろっていても、今日の取得でなければ（木曜からのGIだけ等）いつも通り読む。馬番が欠けていても読む"""
        race = {'date': day(1), 'venue_code': '05', 'r': 1, 'umaban': True, 'horses': [('2021000001', 'クラブウマ', CARROT, '')]}
        for upd, uma in ((datetime.now(JST) - timedelta(days=1)).isoformat(timespec='minutes'), '1'), (self.at_today('10:21'), ''):
            jra = FakeJRA([race])
            races = {'updated': upd, 'days': [{'date': day(1), 'venues': ['東京']}], 'horses': [{'date': day(1), 'horseId': '2021000001', 'umaban': uma, 'status': ''}]}
            code, data, _ = self.run_main(jra, ['--mode', 'umaban', '--start', '00:00', '--until', '23:59', '--interval', '0'], races=races)
            self.assertEqual(code, 0)
            self.assertTrue(jra.requests)
            self.assertEqual(data['horses'][0]['umaban'], '1')

    def test_confirm_second_run_skips(self):
        """出走確定の見張りが2回目に動いた時（今日15時以降に先の開催日を取得済み）は JRA にアクセスしない（10/26〜）"""
        jra = FakeJRA([{'date': day(2), 'venue_code': '05', 'r': 1, 'umaban': False, 'horses': [('2021000001', 'クラブウマ', CARROT, '')]}])
        done = {'updated': self.at_today('16:02'), 'days': [{'date': day(2), 'venues': ['東京']}, {'date': day(3), 'venues': ['東京']}], 'horses': []}
        code, _, _ = self.run_main(jra, ['--mode', 'confirm', '--start', '00:00', '--until', '23:59', '--interval', '0'], races=done)
        self.assertEqual((code, jra.requests), (0, []))

    def test_confirm_runs_after_morning_update(self):
        """朝の馬番の取得で更新されただけなら（金曜など）、出走確定の見張りはいつも通り動く"""
        jra = FakeJRA([{'date': day(2), 'venue_code': '05', 'r': r, 'umaban': False, 'horses': [(f'20210001{r:02d}', f'ウマ{r}', CARROT, '')]} for r in range(1, 13)])
        races = {'updated': self.at_today('10:15'), 'days': [{'date': day(1), 'venues': ['東京']}], 'horses': []}
        code, data, _ = self.run_main(jra, ['--mode', 'confirm', '--start', '00:00', '--until', '23:59', '--interval', '0'], races=races)
        self.assertEqual(code, 0)
        self.assertTrue(jra.requests)
        self.assertEqual(len(data['horses']), 12)

    def test_format_error(self):
        """出馬表トップにリンクはあるのに形式が読めない → exit 1"""
        jra = FakeJRA([])

        def broken_top(s, c, p, path):
            s.count += 1
            return '<a href="x?CNAME=pw01drlXXXX/AB"></a>'
        jra.get = broken_top
        code, _, _ = self.run_main(jra, [])
        self.assertEqual(code, 1)

    def test_past_week_links_only(self):
        """トップに終わった週の開催（pw01drl10…）だけが載っている平日 → 形式エラーにせず、出馬表は読まない（10/21 の失敗）"""
        jra = FakeJRA([])
        jra.past = [(day(-4), '05'), (day(-4), '08')]
        code, _, _ = self.run_main(jra, [])
        self.assertEqual(code, 0)
        self.assertEqual(jra.requests, ['pw01dli00/F3'])
        with mock.patch.object(fr.Fetcher, '_get', lambda s, c, p, path: jra.get(s, c, p, path)), redirect_stdout(io.StringIO()):
            self.assertEqual(fr.attempt(fr.Fetcher(), [], 'confirm', {'known': set()}), 'waiting')   # 木曜の見張りは続ける

    def test_past_week_links_with_new_day(self):
        """終わった週の開催と新しい開催日が並んで載っている → 新しい開催日だけ読んで取得する"""
        jra = FakeJRA([{'date': day(2), 'venue_code': '05', 'r': r, 'umaban': False,
                        'horses': [(f'20210001{r:02d}', f'ウマ{r}', CARROT, '')]} for r in range(1, 13)])
        jra.past = [(day(-5), '05')]
        code, data, _ = self.run_main(jra, ['--mode', 'confirm', '--start', '00:00', '--until', '23:59', '--interval', '0'],
                                      races={'days': [{'date': day(-5), 'venues': ['東京']}], 'horses': []})
        self.assertEqual(code, 0)
        self.assertEqual(len(data['horses']), 12)
        self.assertFalse(any(c.startswith('pw01drl10') for c in jra.requests))

    def test_stale_club_horse_rechecked_on_thursday(self):
        """木曜: 90日以上中央に載っていなかったクラブ馬は馬のページで名義を確かめる（売却→地方→中央に戻った馬を外す）"""
        jra = FakeJRA([{'date': day(2), 'venue_code': '05', 'r': 1, 'umaban': False,
                        'horses': [('2021000001', 'モドッタウマ', '山田 太郎氏', ''), ('2021000002', 'キュウヨウウマ', CARROT, ''),
                                   ('2021000003', 'ツヅケテウマ', CARROT, ''), ('2021000004', 'ハジメテウマ', CARROT, '')]}])
        json.dump({'2021000001': day(-100), '2021000002': day(-120), '2021000003': day(-30)}, open(fr.SEEN, 'w'))
        cache = {'2021000001': 'carrot', '2021000002': 'carrot', '2021000003': 'carrot', '2021000004': 'carrot'}
        code, data, cache = self.run_main(jra, [], cache=cache)
        self.assertEqual(code, 0)
        self.assertEqual(sorted(h['name'] for h in data['horses']), ['キュウヨウウマ', 'ツヅケテウマ', 'ハジメテウマ'])
        self.assertEqual(cache['2021000001'], '')
        self.assertEqual(sorted(c for c in jra.requests if c.startswith('pw01dud00')), ['pw01dud002021000001/AA', 'pw01dud002021000002/AA'])
        seen = json.load(open(fr.SEEN))
        self.assertEqual(seen, {'2021000002': day(2), '2021000003': day(2), '2021000004': day(2)})   # クラブ馬だけ・今回の日付
        self.assertIn('モドッタウマ', self.log)   # 名義が変わったことをログに出す

    def test_summary(self):
        """Actions の要約にクラブ別の頭数が出る"""
        jra = FakeJRA([{'date': day(1), 'venue_code': '05', 'r': 1, 'umaban': True, 'horses': [('2021000001', 'クラブウマ', CARROT, '')]}])
        self.run_main(jra, [], summary=True)
        s = open(os.path.join(self.tmp.name, 'summary.md'), encoding='utf-8').read()
        self.assertIn('キャロットクラブ | 1', s)
        self.assertIn('リクエスト数', s)


class TestFetcherRetry(unittest.TestCase):
    def test_retry_on_broken_read(self):
        """本文を読んでいる途中の接続切れ（ConnectionResetError・IncompleteRead）も取り直す（10/26〜）"""
        import http.client
        calls = {'n': 0}

        class Resp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                calls['n'] += 1
                if calls['n'] == 1:
                    raise ConnectionResetError(104, 'Connection reset by peer')
                if calls['n'] == 2:
                    raise http.client.IncompleteRead(b'<html>')
                return '<html>読めた</html>'.encode('cp932')
        with mock.patch.object(fr.urllib.request, 'urlopen', lambda *a, **k: Resp()), mock.patch.object(fr.time, 'sleep', lambda s: None), \
                redirect_stdout(io.StringIO()):
            f = fr.Fetcher()
            self.assertIn('読めた', f.get('pw01dli00/F3', post=True))
        self.assertEqual((calls['n'], f.count), (3, 3))

    def test_gives_up_after_three(self):
        with mock.patch.object(fr.urllib.request, 'urlopen', mock.Mock(side_effect=ConnectionResetError(104, 'reset'))), \
                mock.patch.object(fr.time, 'sleep', lambda s: None), redirect_stdout(io.StringIO()):
            f = fr.Fetcher()
            with self.assertRaises(RuntimeError):
                f.get('pw01dli00/F3', post=True)
        self.assertEqual(f.count, 3)


class TestExitCode(unittest.TestCase):
    def test_thursday_waiting(self):
        thu = datetime(2026, 10, 22, 18, 31, tzinfo=JST)
        self.assertEqual(fr.exit_code('confirm', 'waiting', {'known': {'2026-10-18'}}, thu), 1)
        self.assertEqual(fr.exit_code('confirm', 'waiting', {'known': {'2026-10-24'}}, thu), 0)     # 取得済み
        self.assertEqual(fr.exit_code('confirm', 'waiting', {'known': set()}, datetime(2026, 12, 24, 18, 31, tzinfo=JST)), 0)  # 年末年始
        self.assertEqual(fr.exit_code('confirm', 'waiting', {'known': set()}, datetime(2026, 10, 21, 16, 36, tzinfo=JST)), 0)  # 水曜


if __name__ == '__main__':
    unittest.main()
