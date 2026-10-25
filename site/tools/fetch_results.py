"""JRA のレース結果からクラブ馬の着順などを集めて data/results.json を更新する（結果カード用、10/24〜）。

設計（ナレッジ「08 結果カード」、10/24 決定）:
- 読むのは競馬場ごとの「全レースまとめ」（pw01ses01…）だけ。1回1リクエストで、その開催の終わったレースがすべて載っている。
  まとめのリンクは同じ日の中で変わらないので、最初に 結果トップ（1）→ 開催のページ（クラブ馬の出る場だけ、最大3）を読む
- クラブ馬の出るレースだけ、発走の18分後に読み始める（10/25 の試しの結果から。最初は13分後だった）。全頭の結果（タイム・推定上り）がそろっていなければ3分おきに読み直し、
  発走の40分後であきらめる（19時の仕上げで拾う）。上位5頭だけが先に載る段階では完了にしない
- races.json に今日の開催がない日は JRA に1回もアクセスしない
- 結果が取れるたびに results.json を書き、--push の時は1レースごとにコミットして push する（10/24、私の指定）。
  Pages の反映は1時間に10回までの目安があるので、1時間に8回を超えそうな時は次の機会にまとめる（終わる時の1回は残さず push）
- 1開催日のリクエスト数の見込み: 40〜45（結果トップ・開催のページ 最大7＋クラブ馬の出るレース30〜35＋読み直し数回）

使い方:
  python3 tools/fetch_results.py --until 13:00 [--push] [--pending-flag PATH]   午前の回（終わった時に残りがあれば PATH を作る）
  python3 tools/fetch_results.py --until 18:00 [--push]                          午後の回
  python3 tools/fetch_results.py --final [--push]                                仕上げ（まだそろっていないレースの場だけ1回ずつ読む）
  python3 tools/fetch_results.py --final --date 2026-10-25 [--push]              日付を指定して仕上げ（定期実行が来なかった日の取り直し）
仕上げは、日付を指定しない時は「その日」の分。正午より前に動いた時は前の日の分とみなす（10/25 の 19:07 の定期実行は
4時間遅れて 23:15 に起動した。日付をまたぐと何も取らずに終わってしまうため）
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_races import Fetcher, JST, VENUES, DATA, OUT as RACES   # noqa: E402

RESULTS = os.path.join(DATA, 'results.json')
PATH = '/JRADB/accessS.html'
TOP = 'pw01sli00/AF'
START_AFTER = 18     # 発走から何分後に読み始めるか。10/25 の試しで全頭が載るのは平均18分（13〜34分）。13分後だと読み直しがかさんだ（1日68回）
                     # ため、18分後にした（10/25、私が許可。読む回数はほぼ半分、取れるのは平均1分ほど遅れるだけ）
RETRY = 3            # 読み直しの間隔（分）
GIVE_UP = 40         # 発走から何分であきらめるか（あとは仕上げ）
PUSH_PER_HOUR = 8    # Pages の反映の目安（1時間に10回）より少なめ
CODE = {v: k for k, v in VENUES.items()}
RACE_FIELDS = ('key', 'horseId', 'name', 'clubId', 'date', 'venue', 'r', 'time', 'raceName', 'grade', 'cls', 'surface', 'dist', 'status')


# ---------------------------------------------------------------- 日付
def meet_week(ymd):
    """開催週（火曜〜翌月曜）の火曜の日付。ページ側（meetWeek）と同じ"""
    d = datetime.strptime(ymd, '%Y-%m-%d').date()
    return (d - timedelta(days=(d.weekday() - 1) % 7)).isoformat()


# ---------------------------------------------------------------- ページの読み取り
def s_links(html, prefix):
    found = re.findall(r"doAction\('/JRADB/accessS\.html',\s*'(%s[^']*)'\)" % prefix, html)
    found += re.findall(r'CNAME=(%s[^"&\']+)' % prefix, html)
    return list(dict.fromkeys(found))


def _txt(el):
    return re.sub(r'\s+', ' ', el.get_text(' ', strip=True)).strip() if el else ''


def parse_ses(html):
    """全レースまとめ → {R: {'date', 'venue', 'rows': {馬ID: {...}}}}（載っているレースだけ）"""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')
    out = {}
    for u in soup.select('div.race_result_unit'):
        m = re.search(r'(\d+)', u.get('id') or '')
        if not m:
            continue
        r = int(m.group(1))
        dl = _txt(u.select_one('.date_line .date')) or _txt(u.select_one('.date_line'))
        dm = re.search(r'(\d{4})年(\d+)月(\d+)日.*?\d+回(\S+?)\d+日', dl)
        rows = {}
        for tr in u.select('table.basic tbody tr'):
            a = tr.select_one('td.horse a')
            hm = re.search(r'pw01dud\d{2}(\d{10})', a.get('href', '')) if a else None
            if not hm:
                continue
            g = lambda c: _txt(tr.select_one('td.' + c))   # noqa: E731
            w = tr.select_one('td.waku img')
            wk = re.search(r'枠(\d)', w.get('alt', '')) if w else None
            rows[hm.group(1)] = {
                'finish': g('place'), 'waku': wk.group(1) if wk else '', 'umaban': g('num'), 'sexAge': g('age'),
                'weight': g('weight'), 'jockey': g('jockey'), 'rtime': g('time'), 'margin': g('margin'),
                'corner': '-'.join(li.get_text(strip=True) for li in tr.select('td.corner li')) or g('corner'),
                'last3f': g('f_time'), 'hweight': re.sub(r'\s+', '', g('h_weight')), 'pop': g('pop')}
        for v in rows.values():
            v['runners'] = len(rows)
        out[r] = {'date': f'{dm.group(1)}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}' if dm else '',
                  'venue': dm.group(4) if dm else '', 'rows': rows}
    return out


def row_done(row):
    """その馬の結果がそろったか。着順が数字の馬は、タイムと推定上りまで（上位5頭だけの段階では空）"""
    f = row.get('finish', '')
    if not f:
        return False
    if not f.isdigit():
        return True   # 中止・失格・取消・除外
    return bool(row.get('rtime') and row.get('last3f'))


# ---------------------------------------------------------------- 本体
class Clock:
    def now(self):
        return datetime.now(JST)

    def sleep(self, sec):
        time.sleep(max(0, sec))


class Run:
    def __init__(self, fetch, clock=None, publish=None, log=print):
        self.f = fetch
        self.clock = clock or Clock()
        self.publish = publish            # 結果が増えた時に呼ぶ（コミットと push）。None なら書くだけ
        self.log = log
        self.pushes = []                  # push した時刻（1時間の回数を数える）
        self.dirty = False
        self.done_at = {}                 # (場, R) → 発走から何分で取れたか
        self.notes = []
        self.kai_of = {}                  # 場 → 開催のページ（全レースまとめのリンクがまだなかった時に読み直す）

    # ---- データ
    def load(self, today):
        races = {}
        if os.path.exists(RACES):
            with open(RACES, encoding='utf-8') as fp:
                races = json.load(fp)
        self.held = {d['date']: d['venues'] for d in races.get('days', [])}
        self.mine = [h for h in races.get('horses', []) if h.get('date') == today]
        res = {}
        if os.path.exists(RESULTS):
            with open(RESULTS, encoding='utf-8') as fp:
                res = json.load(fp)
        wk = meet_week(today)
        self.res = [h for h in res.get('horses', []) if meet_week(h['date']) == wk]   # 新しい開催週になったら前の週は消す
        self.days = [d for d in res.get('days', []) if meet_week(d['date']) == wk]
        if today in self.held and not any(d['date'] == today for d in self.days):
            self.days.append({'date': today, 'venues': self.held[today]})
            self.days.sort(key=lambda d: d['date'])
        if len(self.res) != len(res.get('horses', [])):
            self.dirty = True
        self.updated = res.get('updated', '')

    def entry(self, h):
        return next((x for x in self.res if x['horseId'] == h['horseId'] and x['date'] == h['date']), None)

    def races(self):
        """今日のクラブ馬の出るレース: {(場, R): {'time': datetime, 'horses': [...]}}"""
        out = {}
        for h in self.mine:
            k = (h['venue'], int(h['r']))
            hh, mm = map(int, (h.get('time') or '23:59').split(':'))
            y, mo, d = map(int, h['date'].split('-'))
            t = self.clock.now().replace(year=y, month=mo, day=d, hour=hh, minute=mm, second=0, microsecond=0)
            out.setdefault(k, {'time': t, 'horses': []})['horses'].append(h)
        return out

    def complete(self, race):
        for h in race['horses']:
            e = self.entry(h)
            if not e or not row_done(e):
                return False
        return True

    def save(self):
        now = self.clock.now()
        doc = {'source': 'JRAホームページ レース結果', 'updated': now.strftime('%Y-%m-%dT%H:%M+09:00'),
               'days': self.days, 'horses': sorted(self.res, key=lambda x: (x['date'], CODE.get(x['venue'], '99'), int(x['r']), x['horseId']))}
        os.makedirs(DATA, exist_ok=True)
        with open(RESULTS, 'w', encoding='utf-8') as fp:
            json.dump(doc, fp, ensure_ascii=False, indent=1)
            fp.write('\n')

    def flush(self, label, force=False):
        """results.json を書き、push する（1時間に PUSH_PER_HOUR 回まで。超えそうなら次の機会にまとめる）"""
        if not self.dirty:
            return
        self.save()
        if not self.publish:
            self.dirty = False
            return
        now = self.clock.now()
        self.pushes = [t for t in self.pushes if (now - t).total_seconds() < 3600]
        if len(self.pushes) >= PUSH_PER_HOUR and not force:
            self.log(f'  push は1時間に{PUSH_PER_HOUR}回まで。次の機会にまとめる')
            return
        if self.publish(label):
            self.pushes.append(now)
            self.dirty = False

    # ---- JRA
    def meetings(self, venues, today):
        """結果トップ → 今日の開催のページ → {場: 全レースまとめの cname}（クラブ馬の出る場だけ）"""
        ymd8 = today.replace('-', '')
        top = self.f.get(TOP, post=True, path=PATH)
        kai = [c for c in s_links(top, 'pw01srl') if c.split('/')[0].endswith(ymd8)]
        if not s_links(top, 'pw01srl'):
            self.notes.append('結果トップに開催のリンクが1つもない（ページの形式が変わった？）')
        ses = {}
        self.kai_of = {}
        for v in venues:
            c = next((k for k in kai if k[9:11] == CODE.get(v)), None)
            if not c:
                ses[v] = None   # その場のレースがまだ1つも終わっていないと、結果トップに載っていない（10/25 確認）→ 後で読み直す
                continue
            page = self.f.get(c, post=True, path=PATH)
            s = [x for x in s_links(page, 'pw01ses') if x.split('/')[0].endswith(ymd8)]
            if s:
                ses[v] = s[0]
            else:
                ses[v] = None   # まだ1レースも終わっていない時は出ていないかもしれない → 後で開催のページを読み直す
                self.kai_of[v] = c
        return ses

    def read(self, v, ses, races):
        """場 v の全レースまとめを1回読み、クラブ馬の結果を取り込む。新しくそろったレースの一覧を返す"""
        if not ses.get(v):
            ymd8 = self.clock.now().strftime('%Y%m%d')
            c = self.kai_of.get(v)
            if not c:   # 結果トップに まだ載っていなかった場 → トップを読み直す
                self.f.memo = {}
                top = self.f.get(TOP, post=True, path=PATH)
                c = next((k for k in s_links(top, 'pw01srl') if k.split('/')[0].endswith(ymd8) and k[9:11] == CODE.get(v)), None)
                if c:
                    self.kai_of[v] = c
            if c:
                self.f.memo = {}
                page = self.f.get(c, post=True, path=PATH)
                s = [x for x in s_links(page, 'pw01ses') if x.split('/')[0].endswith(ymd8)]
                ses[v] = s[0] if s else None
            if not ses.get(v):
                return []
        self.f.memo = {}
        got = parse_ses(self.f.get(ses[v], post=True, path=PATH))
        newly = []
        for (vv, r), race in races.items():
            if vv != v or r not in got:
                continue
            before = self.complete(race)
            rows = got[r]['rows']
            for h in race['horses']:
                row = rows.get(h['horseId'])
                if not row:
                    continue
                e = self.entry(h)
                new = {**{k: h.get(k, '') for k in RACE_FIELDS}, **row}
                if e is None:
                    self.res.append(new); self.dirty = True
                elif any(e.get(k) != new.get(k) for k in row):
                    e.update(new); self.dirty = True
            if not before and self.complete(race):
                newly.append(r)
                self.done_at[(v, r)] = int((self.clock.now() - race['time']).total_seconds() // 60)
        return newly

    def run(self, until=None, final=False, date=None):
        now = self.clock.now(); today = now.date().isoformat()
        if final and not date and now.hour < 12:
            date = (now.date() - timedelta(days=1)).isoformat()   # 仕上げが日付をまたいで動いた時は前の日の分
        if date:
            if not final:
                raise ValueError('日付の指定は仕上げ（--final）の時だけ')
            today = date
            self.log(f'{date} の分を取る（仕上げ）')
        self.load(today)
        races = self.races()
        if not races:
            self.log('今日はクラブ馬の出るレースがない（JRA にはアクセスしない）')
            self.flush('結果を整理')
            return {'pending': 0}
        pending = {k: v for k, v in races.items() if not self.complete(v)}
        self.log(f'今日のクラブ馬の出るレース {len(races)}（まだ {len(pending)}）')
        if not pending:
            self.flush('結果を整理')
            return {'pending': 0}
        venues = sorted({v for v, _ in pending}, key=lambda v: CODE.get(v, '99'))
        if final:
            ses = self.meetings(venues, today)
            for v in venues:
                newly = self.read(v, ses, pending)
                if newly:
                    self.log(f'  {v} {"・".join(f"{r}R" for r in sorted(newly))} を取得（仕上げ）')
            self.flush('結果を更新（仕上げ）', force=True)
            left = [k for k, v in pending.items() if not self.complete(v)]
            if left:
                self.notes.append('仕上げでもそろわなかった: ' + '、'.join(f'{v}{r}R' for v, r in sorted(left)))
            return {'pending': len(left)}
        next_try = {k: v['time'] + timedelta(minutes=START_AFTER) for k, v in pending.items()}
        ses = None
        while pending:
            now = self.clock.now()
            due = [k for k, t in next_try.items() if t <= now]
            if not due:
                wake = min(next_try.values())
                if until and wake > until:
                    break
                self.clock.sleep((wake - now).total_seconds())
                continue
            if ses is None:
                ses = self.meetings(venues, today)
            for v in sorted({v for v, _ in due}, key=lambda v: CODE.get(v, '99')):
                newly = self.read(v, ses, pending)
                if newly:
                    self.log(f'  {now:%H:%M} {v} {"・".join(f"{r}R" for r in sorted(newly))} を取得')
                    self.flush(f'結果を更新 {v}{"・".join(f"{r}R" for r in sorted(newly))}')
            now = self.clock.now()
            for k in list(pending):
                if self.complete(pending[k]):
                    del pending[k]; del next_try[k]
                elif next_try[k] <= now:
                    if now - pending[k]['time'] >= timedelta(minutes=GIVE_UP):
                        self.notes.append(f'{k[0]}{k[1]}R: 発走{GIVE_UP}分後までにそろわなかった（仕上げで拾う）')
                        del pending[k]; del next_try[k]
                    else:
                        next_try[k] = now + timedelta(minutes=RETRY)
            if self.dirty:
                self.flush('結果を更新')
        self.flush('結果を更新', force=True)
        return {'pending': len(pending)}


# ---------------------------------------------------------------- git
def git_publish(label):
    """data/results.json だけをコミットして push（出馬表の取得とぶつかったら取り直して最大3回）"""
    def git(*a, check=True):
        return subprocess.run(['git', *a], capture_output=True, text=True, check=check)
    git('add', 'data/results.json')
    if git('diff', '--cached', '--quiet', check=False).returncode == 0:
        return True
    git('commit', '-q', '-m', f'{label} {datetime.now(JST):%m/%d %H:%M}')
    for i in range(3):
        git('pull', '--rebase', '-q', 'origin', 'main', check=False)
        if git('push', '-q', 'origin', 'HEAD:main', check=False).returncode == 0:
            return True
        time.sleep(5 * (i + 1))
    print('::warning::results.json の push に失敗（次の機会にまとめる）', flush=True)
    return False


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else default


def main():
    clock = Clock()
    until = None
    if arg('--until'):
        h, m = map(int, arg('--until').split(':'))
        until = clock.now().replace(hour=h, minute=m, second=0, microsecond=0)
    f = Fetcher(arg('--offline'))
    run = Run(f, clock, git_publish if '--push' in sys.argv else None)
    try:
        date = arg('--date')
        if date and not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date):
            raise ValueError(f'日付の形が違う: {date}（YYYY-MM-DD）')
        st = run.run(until=until, final='--final' in sys.argv, date=date or None)
        code = 0
    except Exception as e:   # 通信エラーなど。取れた分は書いておく
        print(f'::error::結果の取得中にエラー: {e!r}', flush=True)
        run.flush('結果を更新', force=True)
        st, code = {'pending': -1}, 1
    if arg('--pending-flag') and st['pending'] > 0:
        open(arg('--pending-flag'), 'w').write(str(st['pending']))
    mins = '、'.join(f'{v}{r}R {m}分' for (v, r), m in sorted(run.done_at.items(), key=lambda kv: (CODE.get(kv[0][0], '99'), kv[0][1])))
    print(f'::notice::リクエスト数 {f.count}／取得したレース {len(run.done_at)}／残り {st["pending"]}', flush=True)
    if mins:
        print(f'::notice::発走から取得までの分数: {mins}', flush=True)
    for n in run.notes:
        print(f'::warning::{n}', flush=True)
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if path:
        L = ['## 結果の取得', '', f'- リクエスト数: {f.count}／取得したレース: {len(run.done_at)}／残り: {st["pending"]}']
        if mins:
            L.append(f'- 発走から取得までの分数: {mins}')
        L += [f'- {n}' for n in run.notes]
        with open(path, 'a', encoding='utf-8') as fp:
            fp.write('\n'.join(L) + '\n')
    return code


if __name__ == '__main__':
    sys.exit(main())
