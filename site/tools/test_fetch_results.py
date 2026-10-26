"""tools/fetch_results.py のテスト（JRA にはアクセスしない。時刻を進められる偽の結果ページで動かす）

偽のページの形は、10/24 の見張りで保存した本物のページ（結果トップ・開催のページ・全レースまとめ）に合わせている。
結果は発走の10分後に上位5頭だけ（2着以下のタイム・推定上りは空）、13分後に全頭が載る（10/24 の見張りの結果）。
"""
import json, os, subprocess, sys, tempfile, unittest, warnings
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
                t = datetime(2026, 10, 24, h, m, tzinfo=JST) + timedelta(minutes=10)
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
            post = datetime(2026, 10, 24, h, m, tzinfo=JST) + timedelta(minutes=race.get('late', 0))   # レースは DAY（10/24）
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
        self.p.append(mock.patch.object(fx, 'START_AFTER', 13))   # 下の時刻は13分後から読む前提で書いている（本番は18分後。test_start_after）
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

    def old_results(self, *dates):
        json.dump({'days': [{'date': d, 'venues': ['東京']} for d in dates],
                   'horses': [horse('05', 1, f'202300000{i}', '10:05') | {'date': d, 'finish': '1', 'rtime': '1:35.8', 'last3f': '34.0'} for i, d in enumerate(dates)]},
                  open(fx.RESULTS, 'w', encoding='utf-8'), ensure_ascii=False)

    def test_new_group_clears_old(self):
        """前の開催日から4日以上あいた日にクラブ馬が走る時、その日の最初の取得で前の開催の結果を消す"""
        self.old_results('2026-10-17', '2026-10-18')
        self.write_races([horse('05', 1, '2024000001', '10:05')])   # 今日（10/24 土）
        c = FakeClock('08:00')
        pushed = []
        self.run_(c, FakeJRA(c, {}), publish=lambda label: pushed.append(label) or True, until=c.now())
        r = self.results()
        self.assertEqual(r['horses'], [])
        self.assertEqual([d['date'] for d in r['days']], [DAY])
        self.assertEqual(len(pushed), 1)

    def test_keep_until_next_meeting(self):
        """レースのない日（火曜〜金曜）は前の開催の結果を消さない（10/26 修正。以前は火曜の朝に消していた）"""
        self.old_results('2026-10-17', '2026-10-18')
        self.write_races([horse('05', 1, '2024000001', '10:05') | {'date': '2026-10-25'}],
                         days=[{'date': '2026-10-25', 'venues': ['東京']}])
        for day in range(19, 24):   # 10/19（月）〜10/23（金）、10/24（土）もクラブ馬がいなければ消さない
            c = FakeClock('07:40'); c.t = c.t.replace(day=day)
            pushed = []
            self.assertEqual(self.run_(c, FakeJRA(c, {}), publish=lambda label: pushed.append(label) or True, until=c.now().replace(hour=13)), {'pending': 0})
            self.assertEqual(pushed, [], day)
            self.assertEqual(sorted(h['date'] for h in self.results()['horses']), ['2026-10-17', '2026-10-18'], day)

    def test_substitute_tuesday_same_group(self):
        """代替開催の火曜（日曜から2日）は前の土日と同じまとまり。土日の結果を残したまま火曜の分を足す"""
        self.old_results('2026-10-17', '2026-10-18')
        tue = '2026-10-20'
        self.write_races([horse('05', 1, '2024000001', '10:05') | {'date': tue}], days=[{'date': tue, 'venues': ['東京']}])
        c = FakeClock('08:00'); c.t = c.t.replace(day=20)
        run = fx.Run(FakeJRA(c, {}), c, None, log=self.logs.append)
        run.run(until=c.now())
        self.assertEqual(sorted(h['date'] for h in run.res), ['2026-10-17', '2026-10-18'])
        self.assertEqual([d['date'] for d in run.days], ['2026-10-17', '2026-10-18', tue])
        self.assertEqual(sorted(h['date'] for h in self.results()['horses']), ['2026-10-17', '2026-10-18'])

    def test_new_group_rule(self):
        """新しい開催のまとまりかどうかは日付の間隔（4日以上）だけで決める"""
        self.assertTrue(fx.new_group('2026-10-18', '2026-10-24'))    # 日曜 → 次の土曜
        self.assertTrue(fx.new_group('2026-10-26', '2026-10-31'))    # 3日間開催の月曜 → 次の土曜
        self.assertTrue(fx.new_group('2026-10-20', '2026-10-24'))    # 代替の火曜 → 次の土曜
        self.assertTrue(fx.new_group('2026-12-28', '2027-01-04'))    # 年末 → 年始
        self.assertFalse(fx.new_group('2026-10-24', '2026-10-26'))   # 土曜 → 3日間開催の月曜
        self.assertFalse(fx.new_group('2026-10-17', '2026-10-20'))   # 土曜 → 代替の火曜（日曜が中止）
        self.assertFalse(fx.new_group('2026-10-25', '2026-10-24'))   # 前の日を取り直す仕上げ
        self.assertFalse(fx.new_group('', '2026-10-24'))

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

    def test_start_after(self):
        """本番の設定（発走18分後から）では、13分後・16分後の読み直しをせずに1回で取れる"""
        self.p[-1].stop(); self.p.pop()
        self.assertEqual(fx.START_AFTER, 18)
        self.write_races([horse('04', 1, '2024000041', '09:40')])
        c = FakeClock('08:00')
        j = FakeJRA(c, {('04', 1): {'time': '09:40', 'horses': ['2024000041'], 'finish': {'2024000041': '2'}, 'late': 4}})   # 9:54 上位5頭、9:57 全頭
        self.assertEqual(self.run_(c, j, until=c.now().replace(hour=13)), {'pending': 0})
        self.assertEqual(sum(1 for x in j.requests if x.startswith('pw01ses')), 1)   # 9:58 に1回だけ

    def test_final_with_date(self):
        """日付を指定した仕上げ・日付をまたいで動いた仕上げは、その日（前の日）の分を取る"""
        self.write_races([horse('05', 1, '2024000051', '10:05'), horse('05', 2, '2024000052', '10:35')])
        for when, kw in (('00:11', {}), ('20:00', {'date': DAY})):
            c = FakeClock(when); c.t += timedelta(days=1)   # 10/25（日付をまたいだ後・次の日）
            j = FakeJRA(c, {('05', 1): {'time': '10:05', 'horses': ['2024000051'], 'finish': {'2024000051': '4'}},
                            ('05', 2): {'time': '10:35', 'horses': ['2024000052'], 'finish': {'2024000052': '1'}}})
            if os.path.exists(fx.RESULTS):
                os.remove(fx.RESULTS)
            self.assertEqual(self.run_(c, j, final=True, **kw), {'pending': 0}, when)
            self.assertEqual(len(j.requests), 3)
            self.assertEqual({h['horseId']: h['finish'] for h in self.results()['horses']}, {'2024000051': '4', '2024000052': '1'})
        c = FakeClock('20:00'); c.t += timedelta(days=1)   # 次の日の夜に日付なし → その日（レースなし）は何もしない
        j = FakeJRA(c, {}); self.assertEqual(self.run_(c, j, final=True), {'pending': 0}); self.assertEqual(j.count, 0)
        with self.assertRaises(ValueError):
            fx.Run(j, c, None, log=self.logs.append).run(until=c.now(), date=DAY)

    def test_read_uses_target_day(self):
        """日付を指定した仕上げで、結果トップから開催を探し直す時も、指定した日（今日ではなく）で探す（10/26 修正）"""
        self.write_races([horse('05', 1, '2024000051', '10:05')])
        c = FakeClock('20:00'); c.t += timedelta(days=1)   # 10/25 の夜に 10/24 の分を取り直す
        j = FakeJRA(c, {('05', 1): {'time': '10:05', 'horses': ['2024000051'], 'finish': {'2024000051': '4'}}})
        run = fx.Run(j, c, None, log=self.logs.append)
        run.day = DAY; run.load(DAY)
        self.assertEqual(run.read('東京', {}, run.races()), [1])

    def test_auto_until(self):
        """--auto は起動から5時間半か 18:00 の早い方まで。時間切れの時だけ次の回を起動する"""
        at = lambda hm: datetime(2026, 10, 24, *map(int, hm.split(':')), tzinfo=JST)   # noqa: E731
        self.assertEqual(fx.auto_until(at('07:40')), (at('13:10'), True))
        self.assertEqual(fx.auto_until(at('11:20')), (at('16:50'), True))
        self.assertEqual(fx.auto_until(at('13:20')), (at('18:00'), False))
        self.assertEqual(fx.auto_until(at('19:30')), (at('18:00'), False))   # 遅れて 18 時以降に起動した予備の回は、読める分だけ読んで終わる

    def test_auto_backup_run_does_nothing_when_done(self):
        """予備の回は、その日のレースがすべて取得済みなら JRA にアクセスしない"""
        self.write_races([horse('05', 1, '2024000001', '10:05')])
        json.dump({'days': [{'date': DAY, 'venues': ['東京']}], 'horses': [horse('05', 1, '2024000001', '10:05') | {'finish': '1', 'rtime': '1:35.8', 'last3f': '34.0'}]},
                  open(fx.RESULTS, 'w', encoding='utf-8'), ensure_ascii=False)
        c = FakeClock('11:20'); j = FakeJRA(c, {})
        self.assertEqual(self.run_(c, j, until=fx.auto_until(c.now())[0]), {'pending': 0})
        self.assertEqual(j.count, 0)

    def test_on_main(self):
        """main 以外のブランチで動いた時は push しない（GITHUB_REF で判定）"""
        with mock.patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/main'}):
            self.assertTrue(fx.on_main())
        with mock.patch.dict(os.environ, {'GITHUB_REF': 'refs/heads/result-card'}):
            self.assertFalse(fx.on_main())

    def test_parse_partial_not_done(self):
        """上位5頭だけの段階の1着（タイムはあるが推定上りが空）は、そろったとみなさない"""
        self.assertFalse(fx.row_done({'finish': '1', 'rtime': '1:35.8', 'last3f': ''}))
        self.assertTrue(fx.row_done({'finish': '中止'}))
        self.assertTrue(fx.row_done({'finish': '3', 'rtime': '1:36.0', 'last3f': '34.5'}))


class TestGitPublish(unittest.TestCase):
    """git_publish: push に失敗したコミットを、次の機会に（中身が同じでも）送る（10/26 修正）"""
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); t = self.tmp.name
        env = {'GIT_AUTHOR_NAME': 't', 'GIT_AUTHOR_EMAIL': 't@users.noreply.github.com', 'GIT_COMMITTER_NAME': 't',
               'GIT_COMMITTER_EMAIL': 't@users.noreply.github.com', 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
        self.env = mock.patch.dict(os.environ, env); self.env.start()
        sh = lambda *a, cwd=t: subprocess.run(a, cwd=cwd, check=True, capture_output=True)   # noqa: E731
        self.sh = sh
        sh('git', 'init', '-q', '--bare', '-b', 'main', 'origin.git')
        sh('git', 'clone', '-q', 'origin.git', 'w')
        self.w = os.path.join(t, 'w'); os.makedirs(os.path.join(self.w, 'data'))
        self.write('{}')
        sh('git', 'add', '-A', cwd=self.w); sh('git', 'commit', '-qm', 'init', cwd=self.w); sh('git', 'push', '-q', 'origin', 'HEAD:main', cwd=self.w)
        self.cwd = os.getcwd(); os.chdir(self.w)
        self.sleep = mock.patch.object(fx.time, 'sleep', lambda s: None); self.sleep.start()

    def tearDown(self):
        os.chdir(self.cwd); self.sleep.stop(); self.env.stop(); self.tmp.cleanup()

    def write(self, s):
        open(os.path.join(self.w, 'data', 'results.json'), 'w').write(s)

    def remote(self):
        return subprocess.run(['git', '--git-dir', os.path.join(self.tmp.name, 'origin.git'), 'show', 'main:data/results.json'],
                              capture_output=True, text=True, check=True).stdout

    def test_retry_unpushed_commit(self):
        hook = os.path.join(self.tmp.name, 'origin.git', 'hooks', 'pre-receive')
        open(hook, 'w').write('#!/bin/sh\nexit 1\n'); os.chmod(hook, 0o755)
        self.write('{"a":1}')
        with mock.patch('builtins.print'):
            self.assertFalse(fx.git_publish('結果を更新'))   # 拒否される
        os.remove(hook)
        self.assertEqual(self.remote(), '{}')
        self.assertTrue(fx.git_publish('結果を更新'))      # 中身は同じでも、残っているコミットを送る
        self.assertEqual(self.remote(), '{"a":1}')
        self.assertTrue(fx.git_publish('結果を更新'))      # 何もなければ何もしない
        self.assertEqual(self.remote(), '{"a":1}')


if __name__ == '__main__':
    unittest.main()
