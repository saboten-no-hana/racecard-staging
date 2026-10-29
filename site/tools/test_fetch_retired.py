"""tools/fetch_retired.py のテスト（JRA にはアクセスしない。偽の「競走馬登録・抹消一覧」で動かす）

実行: python3 -m unittest discover -s tools -p 'test_*.py'
data/ は一時ディレクトリに差し替えるので、本物の retired.json は書き換えない。
"""
import io, json, os, sys, tempfile, unittest
from contextlib import redirect_stdout
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_races as fr
import fetch_retired as rt


class FakeV:
    """入口（pv156liH1/98）→ 抹消日のページ（pv16mdj10YYYYMMDD/XX）。days: {YYYY-MM-DD: [(馬名, 父, 母)]}"""

    def __init__(self, days):
        self.days = days
        self.requests = []
        self.entry = 'pv156liH1/98'   # 入口の値（変わった時の試験用）
        self.counts = {}               # リンクに書く頭数を上書き（表と食い違う時の試験用）

    @staticmethod
    def cname(d):
        return f'pv16mdj10{d.replace("-", "")}/{d[-2:]}'

    def entry_html(self):
        links = ''.join(f"""<li><a href="#" onclick="doAction('/JRADB/accessV.html','{self.cname(d)}');return false">"""
                        f"""{int(d[:4])}年{int(d[5:7])}月{int(d[8:])}日抹消（{self.counts.get(d, len(v))}頭）</a></li>"""
                        for d, v in sorted(self.days.items(), reverse=True))
        reg = """<a href="#" onclick="doAction('/JRADB/accessV.html','pv15udj1020261022/9F');return false">2026年10月22日登録（80頭）</a>"""
        return f'<html><body><div id="contentsBody">{reg}<ul>{links}</ul></div></body></html>'

    def day_html(self, d):
        rows = ''.join(f'<tr><th scope="row">{n}</th><td>調教師</td><td class="race">2026年4回東京7日8<span>レース</span></td>'
                       f'<td class="family"><div class="parent">{s}<br>{m}</div></td><td class="prize">300<span class="yen">万円</span></td>'
                       f'<td class="prize"></td></tr>' for n, s, m in self.days[d])
        return (f'<html><body><div id="contentsBody"><table class="basic narrow-xy striped mt15"><caption>抹消一覧 {d}抹消分</caption>'
                f'<thead><tr><th>抹消馬名</th><th>調教師名</th><th>最近のレース</th><th>父 母</th><th>収得賞金</th><th>入着賞金</th></tr></thead>'
                f'<tbody>{rows}</tbody></table></div></body></html>')

    def menu_html(self):
        return f"""<html><body><a href="#" onclick="doAction('/JRADB/accessV.html','{self.entry}');return false">競走馬登録・抹消一覧</a></body></html>"""

    def get(self, _self, cname, post, path):
        _self.count += 1
        self.requests.append(cname)
        if cname == 'pw01dli00/F3':
            return self.menu_html()
        if cname.startswith('pv156li'):
            return self.entry_html() if cname == self.entry else '<html><title>パラメータエラー</title></html>'
        for d in self.days:
            if cname == self.cname(d):
                return self.day_html(d)
        return '<html><title>パラメータエラー</title></html>'


class TestFetchRetired(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = os.path.join(self.tmp.name, 'retired.json')
        self.patches = [mock.patch.object(rt, 'OUT', self.out), mock.patch.object(fr, 'WAIT', 0),
                        mock.patch.object(fr.time, 'sleep', lambda s: None)]
        for p in self.patches:
            p.start()

    def tearDown(self):
        for p in self.patches:
            p.stop()
        self.tmp.cleanup()

    def run_main(self, jra, today='2026-10-29'):
        out = io.StringIO()
        with mock.patch.object(fr.Fetcher, '_get', lambda s, c, p, path: jra.get(s, c, p, path)), \
                mock.patch.object(rt, 'now_jst', lambda: fr.datetime.strptime(today + ' 18:40', '%Y-%m-%d %H:%M').replace(tzinfo=fr.JST)), \
                mock.patch.object(sys, 'argv', ['fetch_retired.py']), mock.patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}), \
                redirect_stdout(out):
            code = rt.main()
        return code, out.getvalue()

    def data(self):
        with open(self.out, encoding='utf-8') as fp:
            return json.load(fp)

    def test_first_and_incremental(self):
        jra = FakeV({'2026-10-22': [('アグラード', 'ニューイヤーズデイ', 'ヴィータアレグリア'), ('ケルピー', 'カレンブラックヒル', 'ニシケンイチリン')],
                     '2026-10-25': [('ヨシヒロ', 'ルヴァンスレーヴ', 'デオ')]})
        code, _ = self.run_main(jra)
        self.assertEqual(code, 0)
        d = self.data()
        self.assertEqual(d['counts'], {'2026-10-25': 1, '2026-10-22': 2})
        self.assertEqual(d['horses']['2026-10-22'][0], ['アグラード', 'ニューイヤーズデイ', 'ヴィータアレグリア'])
        self.assertEqual(list(d['horses']), ['2026-10-25', '2026-10-22'])   # 新しい日が先
        self.assertEqual(len(jra.requests), 3)                              # 入口＋2日分
        # 2回目: 同じ頭数の日は読まない（入口だけ）。更新時刻も書き換えない
        upd = d['updated']
        jra.requests.clear()
        self.run_main(jra)
        self.assertEqual(jra.requests, ['pv156liH1/98'])
        self.assertEqual(self.data()['updated'], upd)
        # 新しい抹消日が載った・同じ日の頭数が増えた時だけ、その日を読む
        jra.days['2026-10-26'] = [('フジレイメイ', 'サンダースノー', 'リアライズノユメ')]
        jra.days['2026-10-25'].append(('トム', 'アルクトス', 'エイシンエルヴァー'))
        jra.requests.clear()
        self.run_main(jra)
        self.assertEqual(sorted(jra.requests), sorted(['pv156liH1/98', jra.cname('2026-10-26'), jra.cname('2026-10-25')]))
        d = self.data()
        self.assertEqual([h[0] for h in d['horses']['2026-10-25']], ['ヨシヒロ', 'トム'])
        self.assertEqual(d['counts']['2026-10-25'], 2)

    def test_keep_one_year(self):
        jra = FakeV({'2026-10-22': [('アグラード', '父', '母')]})
        with open(self.out, 'w', encoding='utf-8') as fp:
            json.dump({'updated': '', 'counts': {'2025-10-01': 1, '2025-11-01': 1},
                       'horses': {'2025-10-01': [['オールド', '父', '母']], '2025-11-01': [['ノコル', '父', '母']]}}, fp)
        self.run_main(jra, today='2026-10-29')
        d = self.data()
        self.assertNotIn('2025-10-01', d['horses'])   # 抹消から365日を過ぎたら消す
        self.assertIn('2025-11-01', d['horses'])
        self.assertNotIn('2025-10-01', d['counts'])

    def test_entry_changed(self):
        """入口の値が変わっても、出馬表トップのメニューから拾い直して読む（ログに直す値を出す）"""
        jra = FakeV({'2026-10-22': [('アグラード', '父', '母')]})
        jra.entry = 'pv156liH1/A1'
        code, out = self.run_main(jra)
        self.assertEqual(code, 0)
        self.assertIn('pv156liH1/A1', out)
        self.assertIn('2026-10-22', self.data()['horses'])

    def test_format_error(self):
        jra = FakeV({})
        code, out = self.run_main(jra)
        self.assertEqual(code, 1)
        self.assertIn('形式が読めない', out)
        self.assertFalse(os.path.exists(self.out))

    def test_count_mismatch(self):
        """リンクの頭数と表の行数が違っても止めない（リンクの頭数を控えるので、次回は読み直さない）"""
        jra = FakeV({'2026-10-22': [('アグラード', '父', '母')]})
        jra.counts['2026-10-22'] = 2
        code, out = self.run_main(jra)
        self.assertEqual(code, 0)
        self.assertIn('リンクは2頭、表は1頭', out)
        jra.requests.clear()
        self.run_main(jra)
        self.assertEqual(jra.requests, ['pv156liH1/98'])

    def test_comm_error(self):
        jra = FakeV({'2026-10-22': [('アグラード', '父', '母')]})
        def boom(s, c, p, path):
            raise RuntimeError('取得できませんでした: ' + c)
        with mock.patch.object(fr.Fetcher, '_get', boom), mock.patch.object(sys, 'argv', ['fetch_retired.py']), \
                mock.patch.dict(os.environ, {'GITHUB_STEP_SUMMARY': ''}), redirect_stdout(io.StringIO()) as out:
            code = rt.main()
        self.assertEqual(code, 1)
        self.assertIn('通信エラー', out.getvalue())


if __name__ == '__main__':
    unittest.main()
