"""tools/fetch_results.py のテスト（JRA にはアクセスしない。時刻を進められる偽の結果ページで動かす）

偽のページの形は、10/24 の見張りで保存した本物のページ（結果トップ・開催のページ・全レースまとめ）に合わせている。
結果は発走の10分後に上位5頭だけ（2着以下のタイム・推定上りは空）、13分後に全頭が載る（10/24 の見張りの結果）。
"""
import json, os, sys, tempfile, unittest, warnings
from datetime import datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_results as fx

JST = fx.JST
warnings.simplefilter('ignore', ResourceWarning)
DAY = '2026-10-24'


class FakeClock:
    def __init__(self, hhmm):
        h, m = map(int, hhmm.split(':'))
        self.t = datetime(2026, 10, 24, h, m, tzinfo=JST)

    def now(self):
        return self.t

    def sleep(self, sec):
        self.t += timedelta(seconds=max(1, sec))


class FakeJRA:
    """races: {(場コード, R): {'time': 'HH:MM', 'horses': [馬ID...], 'finish': {馬ID: 着順}, 'late': 分}}"""
    def __init__(self, clock, races, ses_from=None):
        self.clock, self.races, self.requests, self.memo, self.count = clock, races, [], {}, 0
        self.ses_from = ses_from     # この時刻より前は開催のページに全レースまとめのリンクを出さない
        self.top_all = False         # True なら結果トップに最初から全部の開催を載せる

    def get(self, cname, post=False, path=''):
        self.count += 1
        self.requests.append(cname)
        ymd8 = DAY.replace('-', '')
        if cname == fx.TOP:   # 本物と同じく、その場のレースが1つ終わってから（発走10分後から）開催が載る
            first = {}
            for (c, _), race in self.races.items():
                h, m = map(int, race['time'].split(':'))
                t = self.clock.now().replace(hour=h, minute=m, second=0) + timedelta(minutes=10)
                first[c] = min(first.get(c, t), t)
            codes = sorted(c for c, t in first.items() if self.top_all or self.clock.now() >= t)
            return ''.join(f"<a onclick=\"return doAction('/JRADB/accessS.html', 'pw01srl00{c}20260408{ymd8}/A{i}');\">開催</a>" for i, c in enumerate(codes)) + \
                "<a onclick=\"return doAction('/JRADB/accessS.html', 'pw01srl10052026040720261018/C0');\">先週</a>"
        if cname.startswith('pw01srl'):
            c = cname[9:11]
            if self.ses_from and self.clock.now() < self.ses_from:
                return '<p>まだ</p>'
            return f"<a onclick=\"return doAction('/JRADB/accessS.html', 'pw01ses01{c}20260408{ymd8}/B{c}');\">全レース</a>"
        if cname.startswith('pw01ses'):
            return self.ses(cname[9:11])
        raise AssertionError(cname)

    def ses(self, code):
        now = self.clock.now(); out = ''
        venue = fx.VENUES[code]
        for (c, r), race in sorted(self.races.items()):
            if c != code:
                continue
            h, m = map(int, race['time'].split(':'))
            post = now.replace(hour=h, minute=m, second=0) + timedelta(minutes=race.get('late', 0))
            if now < post + timedelta(minutes=10):
                continue
            full = now >= post + timedelta(minutes=13)
            others = [f'99{r:02d}{i:06d}' for i in range(12)]
            fin = race['finish']
            special = [x for x in race['horses'] if x in fin and not fin[x].isdigit()]
            fill = others + [x for x in race['horses'] if x not in fin]
            order = [None] * (len(race['horses']) + len(others))
            for x in race['horses']:
                if fin.get(x, '').isdigit():
                    order[int(fin[x]) - 1] = x
            for i in range(len(order) - len(special)):
                if order[i] is None:
                    order[i] = fill.pop(0)
            order[len(order) - len(special):] = special
            rows = ''
            for pos, hid in enumerate(order, 1):
                if not full and pos > 5:
                    break
                f = race['finish'].get(hid, str(pos)) if hid in race['horses'] else str(pos)
                num = f.isdigit()
                tm = '1:35.8' if num and (full or pos == 1) else ''
                f3 = '34.6' if num and full else ''
                corner = '<div class="corner_list"><ul><li>4</li><li>2</li></ul></div>' if full and num else ''
                rows += (f'<tr><td class="place">{f}</td><td class="waku"><img alt="枠{(pos - 1) % 8 + 1}緑"></td><td class="num">{pos}</td>'
                         f'<td class="horse"><a href="/JRADB/accessU.html?CNAME=pw01dud00{hid}/8F">馬{hid[-3:]}</a></td>'
                         f'<td class="age">牝2</td><td class="weight">55.0</td><td class="jockey"><a href="#">騎手</a></td>'
                         f'<td class="time">{tm}</td><td class="margin">{"" if pos == 1 else "１ 1/4"}</td><td class="corner">{corner}</td>'
                         f'<td class="f_time">{f3}</td><td class="h_weight">470<span>(+6)</span></td><td class="trainer">調教師</td><td class="pop">{pos}</td></tr>')
            out += (f'<div class="race_result_unit" id="race_result_{r}R"><table class="basic narrow-xy striped"><caption><div class="race_header">'
                    f'<div class="date_line"><div class="inner"><div class="cell date">2026年10月24日（土曜） 4回{venue}8日</div>'
                    f'<div class="cell time">発走時刻：<strong>{race["time"].replace(":", "時")}分</strong></div></div></div></div></caption>'
                    f'<tbody>{rows}</tbody></table></div>')
        return f'<html><body>{out}</body></html>'


def horse(code, r, hid, t):
    return {'key': f'{DAY}|{fx.VENUES[code]}|{r}|{hid}', 'horseId': hid, 'name': f'クラブウマ{hid[-2:]}', 'clubId': 'carrot', 'date': DAY,
            'venue': fx.VENUES[code], 'r': r, 'time': t, 'raceName': 'テスト特別', 'grade': '', 'cls': '2勝クラス', 'surface': '芝', 'dist': 1600, 'status': ''}


class TestFetchResults(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = [mock.patch.object(fx, 'DATA', self.tmp.name), mock.patch.object(fx, 'RACES', os.path.join(self.tmp.name, 'races.json')),
                  mock.patch.object(fx, 'RESULTS', os.path.join(self.tmp.name, 'results.json'))]
        for p in self.p:
            p.start()
        self.logs = []

    def tearDown(self):
        for p in self.p:
            p.stop()
        self.tmp.cleanup()

    def write_races(self, horses, days=None):
        days = days or [{'date': DAY, 'venues': ['東京', '京都', '新潟']}]
        json.dump({'days': days, 'horses': horses}, open(fx.RACES, 'w', encoding='utf-8'), ensure_ascii=False)

    def results(self):
        return json.load(open(fx.RESULTS, encoding='utf-8'))

    def run_(self, clock, jra, publish=None, **kw):
        return fx.Run(jra, clock, publish, log=self.logs.append).run(**kw)

    def test_no_races_no_request(self):
        """今日クラブ馬の出るレースがない日は JRA に1回もアクセスしない"""
        self.write_races([horse('05', 1, '2024000001', '10:05') | {'date': '2026-10-25'}])
        c = FakeClock('07:40'); j = FakeJRA(c, {})
        self.assertEqual(self.run_(c, j, until=c.now().replace(hour=13)), {'pending': 0})
        self.assertEqual(j.count, 0)

    def test_progressive(self):
        """発走13分後に読み、上位5頭だけの段階は完了にせず、全頭そろったら取り込む。リクエストは最小限"""
        hs = [horse('05', 1, '2024000001', '10:05'), horse('05', 1, '2024000002', '10:05'),
              horse('05', 5, '2024000003', '12:25'), horse('08', 2, '2024000004', '10:25')]
        self.write_races(hs)
        c = FakeClock('07:40')
        j = FakeJRA(c, {('05', 1): {'time': '10:05', 'horses': ['2024000001', '2024000002'], 'finish': {'2024000001': '1', '2024000002': '中止'}},
                        ('05', 5): {'time': '12:25', 'horses': ['2024000003'], 'finish': {'2024000003': '8'}, 'late': 2},   # 載るのが2分遅い
                        ('08', 2): {'time': '10:25', 'horses': ['2024000004'], 'finish': {'2024000004': '3'}}})
        pushed = []
        st = self.run_(c, j, publish=lambda label: pushed.append((c.now().strftime('%H:%M'), label)) or True, until=c.now().replace(hour=13))
        self.assertEqual(st, {'pending': 0})
        res = {h['horseId']: h for h in self.results()['horses']}
        self.assertEqual(res['2024000001']['finish'], '1')
        self.assertEqual(res['2024000001']['last3f'], '34.6')
        self.assertEqual(res['2024000002']['finish'], '中止')
        self.assertEqual(res['2024000003']['finish'], '8')
        self.assertEqual(res['2024000004']['finish'], '3')
        self.assertEqual(res['2024000004']['raceName'], 'テスト特別')   # レースの情報は races.json から
        self.assertEqual(res['2024000001']['runners'], 14)
        # トップ1・開催2（東京・京都）・まとめ: 東京1R 1回、京都2R 1回、東京5R は 12:38 に未掲載 → 12:41 に取得で2回
        self.assertEqual(j.requests.count(fx.TOP), 2)   # 10:18 は東京だけ載っている → 京都は 10:38 に読み直して見つける（10/25 の試しで分かった）
        self.assertEqual(sum(1 for x in j.requests if x.startswith('pw01srl')), 2)
        self.assertEqual(sum(1 for x in j.requests if x.startswith('pw01ses')), 4)
        self.assertEqual([p[0] for p in pushed], ['10:18', '10:38', '12:41'])   # 1レースごとに push

    def test_partial_then_full(self):
        """上位5頭だけの段階（2着以下のタイム・上りが空）を読んだら3分後に読み直す"""
        self.write_races([horse('05', 11, '2024000011', '15:45')])
        c = FakeClock('13:00')
        j = FakeJRA(c, {('05', 11): {'time': '15:45', 'horses': ['2024000011'], 'finish': {'2024000011': '2'}, 'late': -2}})   # 15:53 に上位5頭、15:56 に全頭
        self.run_(c, j, until=c.now().replace(hour=18))
        ses = [x for x in j.requests if x.startswith('pw01ses')]
        self.assertEqual(len(ses), 1)   # 15:58 には全頭そろっている
        c2 = FakeClock('13:00')
        j2 = FakeJRA(c2, {('05', 11): {'time': '15:45', 'horses': ['2024000011'], 'finish': {'2024000011': '2'}, 'late': 1}})   # 15:56 上位5頭、15:59 全頭
        os.remove(fx.RESULTS)
        self.run_(c2, j2, until=c2.now().replace(hour=18))
        self.assertEqual(sum(1 for x in j2.requests if x.startswith('pw01ses')), 2)   # 15:58 は上位5頭だけ → 16:01 に全頭
        self.assertEqual(self.results()['horses'][0]['rtime'], '1:35.8')

    def test_give_up_and_until(self):
        """発走40分後までにそろわなければあきらめる。--until を過ぎる読みは次の回に残す"""
        self.write_races([horse('05', 3, '2024000021', '11:05'), horse('05', 9, '2024000022', '14:25')])
        c = FakeClock('09:00')
        j = FakeJRA(c, {('05', 3): {'time': '11:05', 'horses': ['2024000021'], 'finish': {}, 'late': 60}})   # 載らない
        st = fx.Run(j, c, None, log=self.logs.append)
        out = st.run(until=c.now().replace(hour=13))
        self.assertEqual(out, {'pending': 1})   # 14:25 のレースは午後の回へ
        self.assertTrue(any('40分後' in n for n in st.notes))
        self.assertLessEqual(sum(1 for x in j.requests if x.startswith('pw01ses')), 10)

    def test_ses_link_later(self):
        """開催のページに全レースまとめのリンクがまだない時は、次に読む時に開催のページを読み直す"""
        self.write_races([horse('04', 1, '2024000031', '09:45')])
        c = FakeClock('08:00')
        j = FakeJRA(c, {('04', 1): {'time': '09:45', 'horses': ['2024000031'], 'finish': {'2024000031': '5'}}}, ses_from=c.now().replace(hour=9, minute=59))
        j.races[('04', 1)]['time'] = '09:45'
        self.assertEqual(self.run_(c, j, until=c.now().replace(hour=13)), {'pending': 0})
        self.assertEqual(sum(1 for x in j.requests if x.startswith('pw01srl')), 3)   # 9:58 に開催のページ（リンクなし）→ 読み直しても まだ → 10:01 に読み直してリンクあり

    def test_new_week_clears_old(self):
        """新しい開催週の最初の取得で、前の週の結果は消す（ページも最新の開催週だけを出す）"""
        json.dump({'days': [{'date': '2026-10-18', 'venues': ['東京']}], 'horses': [horse('05', 1, '2023000001', '10:05') | {'date': '2026-10-18', 'finish': '1'}]},
                  open(fx.RESULTS, 'w', encoding='utf-8'), ensure_ascii=False)
        self.write_races([horse('05', 1, '2024000001', '10:05') | {'date': '2026-10-25'}],
                         days=[{'date': DAY, 'venues': ['東京']}, {'date': '2026-10-25', 'venues': ['東京']}])
        c = FakeClock('08:00')
        self.run_(c, FakeJRA(c, {}), until=c.now().replace(hour=13))
        r = self.results()
        self.assertEqual(r['horses'], [])
        self.assertEqual([d['date'] for d in r['days']], [DAY])

    def test_push_limit(self):
        """push は1時間に8回まで（終わる時の1回を除く）。超える分は次の機会にまとめる"""
        hm = lambda m: f'{m // 60}:{m % 60:02d}'   # noqa: E731
        hs = [horse(code, r, f'2024{code}{r:04d}', hm(600 + 15 * r + k * 5)) for k, code in enumerate(('05', '08', '04')) for r in range(1, 9)]   # 3場が5分ずつずれて15分おき
        self.write_races(hs)
        c = FakeClock('08:00')
        races = {(fx.CODE[h['venue']], h['r']): {'time': h['time'], 'horses': [h['horseId']], 'finish': {h['horseId']: '4'}} for h in hs}
        pushed = []
        self.run_(c, FakeJRA(c, races), publish=lambda label: pushed.append(c.now()) or True, until=c.now().replace(hour=17))
        self.assertGreater(len(pushed), 8)
        for t in pushed:
            self.assertLessEqual(sum(1 for u in pushed if timedelta(0) <= t - u < timedelta(hours=1)), fx.PUSH_PER_HOUR + 1)   # 終わる時の1回は残さず push
        self.assertEqual(len(self.results()['horses']), len(hs))

    def test_final_only_incomplete(self):
        """仕上げは、まだそろっていないレースのある場だけ読む"""
        self.write_races([horse('05', 1, '2024000001', '10:05'), horse('08', 1, '2024000002', '10:00')])
        json.dump({'days': [{'date': DAY, 'venues': ['東京', '京都']}], 'horses': [horse('05', 1, '2024000001', '10:05') | {'finish': '1', 'rtime': '1:35.8', 'last3f': '34.0'}]},
                  open(fx.RESULTS, 'w', encoding='utf-8'), ensure_ascii=False)
        c = FakeClock('19:07')
        j = FakeJRA(c, {('08', 1): {'time': '10:00', 'horses': ['2024000002'], 'finish': {'2024000002': '12'}}})
        self.assertEqual(self.run_(c, j, final=True), {'pending': 0})
        self.assertEqual([x for x in j.requests if not x.startswith('pw01sli')][0][9:11], '08')
        self.assertEqual(len(j.requests), 3)   # トップ・京都の開催・京都のまとめ
        self.assertEqual({h['horseId']: h['finish'] for h in self.results()['horses']}, {'2024000001': '1', '2024000002': '12'})

    def test_parse_partial_not_done(self):
        """上位5頭だけの段階の1着（タイムはあるが推定上りが空）は、そろったとみなさない"""
        self.assertFalse(fx.row_done({'finish': '1', 'rtime': '1:35.8', 'last3f': ''}))
        self.assertTrue(fx.row_done({'finish': '中止'}))
        self.assertTrue(fx.row_done({'finish': '3', 'rtime': '1:36.0', 'last3f': '34.5'}))
        self.assertEqual(fx.meet_week('2026-10-24'), '2026-10-20')
        self.assertEqual(fx.meet_week('2026-10-26'), '2026-10-20')   # 3日間開催の月曜は同じ週
        self.assertEqual(fx.meet_week('2026-10-27'), '2026-10-27')


if __name__ == '__main__':
    unittest.main()
