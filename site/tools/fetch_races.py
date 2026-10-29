"""
JRAホームページの出馬表から、一口クラブ名義の出走馬だけを取り出して data/races.json に保存する。

- 木曜16時すぎ: 馬番なしの出馬表（出走確定）
- レース前日10時すぎ: 枠番・馬番つきの出馬表
が公開されるので、GitHub Actions で毎日 15:45〜（16時前に載ることもあるので早めに）と 10:05〜 に確認する（.github/workflows/fetch-races.yml）。

馬番なしの出馬表には馬主名が載らないため、馬ごとに「どのクラブの馬か（クラブ以外なら空）」を
data/cache.json に記録して週をまたいで使い回す（個人馬主の名前は保存しない）。
- 1日分をまとめた出馬表ページで、出走馬・枠番・馬番・騎手を読む（競馬場ごとに1ページ）
- 記録にない馬がいて、馬番つきの出馬表が出ているレースは、そのレースの出馬表（馬主名つき）で確認する
- それでも分からない馬（主に木曜）は、馬のページで馬主名を確認する
  ただし競走馬登録の一覧（data/regist.json、tools/fetch_retired.py が作る）に馬名と生年が一致する馬は、馬のページを読まずに
  その判定で載せる・載せないを決める（cache.json には記録せず、馬番が出た日に個別レースのページで確定する。10/29〜）
- リクエストの間は2秒以上あける

使い方:
  python3 tools/fetch_races.py            # JRAから1回取得
  python3 tools/fetch_races.py --offline DIR  # 保存済みHTMLで動作確認（DIR/*.html）
  python3 tools/fetch_races.py --mode confirm --start 15:45 --until 18:30 [--watch-until 16:35]
      # 15:45（日本時間）から、races.json にない開催日の出走確定の出馬表が載るのを5分おきに確認して取得。
      # 木曜は週末分を 18:30 まで待つ。ほかの曜日は年末年始・代替競馬などの平日開催に備えて
      # --watch-until まで確認し、何も載らなければ終了（トップを数回読むだけ）
  python3 tools/fetch_races.py --mode umaban --start 10:05 --until 12:00
      # 翌日分の馬番つき出馬表が出るまで5分おきに確認して取得。翌日に開催がなく、新しい開催日もなければ何もしない
  確認は軽く（トップと対象の開催1つ＝最大3リクエスト）行い、出ていたら全体を取得する。
  出馬表は少しずつ載ることがあるので、全体を取得しても揃っていなければ5分後に取り直す。

終了コード（GitHub Actions の失敗通知メールで気づけるように）:
  1 = 出馬表トップのリンクの形式が読めなかった（ページ構造の変更）
  1 = 木曜の --mode confirm で、締め切りまでに新しい開催日の出馬表を1つも取れなかった
      （年末年始 12/24〜1/7 は開催の曜日が不規則なので除く）
  それ以外は 0（平日の見張りで何も出ない・馬番待ちの打ち切りなどは正常として扱う）
"""
import http.client, json, os, re, sys, time, unicodedata, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'races.json')
CACHE = os.path.join(DATA, 'cache.json')
SEEN = os.path.join(DATA, 'seen.json')     # クラブ馬が最後に中央の出馬表に載った日（馬ID → YYYY-MM-DD）
REGIST = os.path.join(DATA, 'regist.json') # 競走馬登録の一覧（tools/fetch_retired.py が作る。馬名・生年月日・クラブID か空文字）
STATUS = os.path.join(DATA, 'status.json') # 出馬表の集計の状態（画面の「集計中」の表示用。10/29〜）
STALE_DAYS = 90                            # これ以上空いたクラブ馬は、馬番の出る前（木曜）にも馬のページで名義を確かめる
BASE = 'https://www.jra.go.jp'
UA = 'Mozilla/5.0 (compatible; racecard/1.0; +https://github.com/saboten-no-hana/racecard)'
JST = timezone(timedelta(hours=9))
WAIT = 2.0
VENUES = {'01': '札幌', '02': '函館', '03': '福島', '04': '新潟', '05': '東京', '06': '中山', '07': '中京', '08': '京都', '09': '阪神', '10': '小倉'}

# ---------------------------------------------------------------- clubs
def load_clubs():
    """clubs.js から {正規化した馬主名: クラブid} を作る"""
    src = open(os.path.join(ROOT, 'clubs.js'), encoding='utf-8').read()
    out = {}
    for m in re.finditer(r"\{id:'([^']+)'[^\n]*?owner:'([^']+)'", src):
        out[norm_owner(m.group(2))] = m.group(1)
    if len(out) < 10:
        raise SystemExit('clubs.js からクラブを読み取れませんでした')
    return out

def days_between(a, b):
    return (datetime.strptime(b, '%Y-%m-%d') - datetime.strptime(a, '%Y-%m-%d')).days

def load_club_list():
    """clubs.js から [{id, name}]（要約の表示用）"""
    src = open(os.path.join(ROOT, 'clubs.js'), encoding='utf-8').read()
    return [{'id': m.group(1), 'name': m.group(2)} for m in re.finditer(r"\{id:'([^']+)'[^\n]*?name:'([^']+)'", src)]

def norm_owner(s):
    s = unicodedata.normalize('NFKC', s or '')
    s = re.sub(r'\((株|有|合|同)\)|株式会社|有限会社|合同会社|一般社団法人', '', s)
    return re.sub(r'[\s・]', '', s).casefold()   # 英字の名義（Blooming Racing など）は大文字小文字・全角半角を区別しない

# ---------------------------------------------------------------- http
class Fetcher:
    def __init__(self, offline=None):
        self.offline = offline
        self.count = 0
        self.last = 0.0
        self.memo = {}   # 1回の試行の中だけで同じページを読み直さないため（試行ごとに空にする）

    def _decode(self, raw):
        m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000])
        enc = m.group(1).decode() if m else 'shift_jis'
        if enc.lower() in ('shift_jis', 'sjis', 'x-sjis'):
            enc = 'cp932'
        return raw.decode(enc, errors='replace')

    def get(self, cname, post=False, path='/JRADB/accessD.html'):
        key = (cname, post, path)
        if key not in self.memo:
            self.memo[key] = self._get(cname, post, path)
        return self.memo[key]

    def _get(self, cname, post, path):
        if self.offline:
            path = os.path.join(self.offline, cname.replace('/', '_') + '.html')
            return open(path, encoding='utf-8').read() if os.path.exists(path) else ''
        wait = WAIT - (time.time() - self.last)
        if wait > 0:
            time.sleep(wait)
        url = BASE + path
        headers = {'User-Agent': UA, 'Referer': BASE + '/JRADB/accessD.html', 'Accept-Language': 'ja'}
        data = None
        if post:
            data = urllib.parse.urlencode({'cname': cname}).encode()
            headers['Content-Type'] = 'application/x-www-form-urlencoded'
        else:
            url += '?CNAME=' + cname
        for attempt in range(3):
            try:
                self.count += 1
                with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers), timeout=40) as r:
                    raw = r.read()
                self.last = time.time()
                return self._decode(raw)
            # 接続できない時（URLError）だけでなく、本文を読んでいる途中の接続切れ（ConnectionResetError など OSError、
            # IncompleteRead など HTTPException）も取り直す（10/26〜。以前は読み込み中の切断は1回目で例外になっていた）
            except (OSError, http.client.HTTPException) as e:
                self.last = time.time()
                print(f'  retry {cname}: {e}', flush=True)
                time.sleep(10 * (attempt + 1))
        raise RuntimeError(f'取得できませんでした: {cname}')

# ---------------------------------------------------------------- parsing
def text(el):
    return re.sub(r'\s+', ' ', el.get_text(' ', strip=True)).strip() if el else ''

def parse_header(cap):
    """出馬表テーブルの caption からレース情報を読む"""
    info = {}
    d = text(cap.select_one('.date_line .date'))
    m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', d)
    if m:
        info['date'] = f'{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    m = re.search(r'\d+回(\D+?)\d+日', d)
    if m:
        info['venue'] = m.group(1).strip()
    t = text(cap.select_one('.date_line .time'))
    m = re.search(r'(\d{1,2})時(\d{2})分', t)
    if m:
        info['time'] = f'{int(m.group(1)):02d}:{m.group(2)}'
    img = cap.select_one('.race_number img')
    m = re.search(r'(\d+)', img.get('alt', '') if img else '')
    if m:
        info['r'] = int(m.group(1))
    rn = cap.select_one('.race_name')
    if rn:
        grade = ''
        for g in rn.select('img'):
            alt = g.get('alt', '')
            if re.search(r'G|J', alt):
                grade = unicodedata.normalize('NFKC', alt).replace('Ⅰ', 'I')
            elif 'リステッド' in alt:
                grade = 'L'
            g.decompose()
        info['raceName'] = text(rn)
        info['grade'] = grade
    info['cls'] = text(cap.select_one('.cell.class'))   # 新馬／未勝利／1勝クラス／2勝クラス／3勝クラス／オープン
    c = text(cap.select_one('.cell.course'))
    m = re.search(r'([\d,]+)\s*メートル', c)
    if m:
        info['dist'] = int(m.group(1).replace(',', ''))
    m = re.search(r'（(芝|ダート|障害)', c)
    if m:
        info['surface'] = {'芝': '芝', 'ダート': 'ダ', '障害': '障'}[m.group(1)]
    return info

def parse_rows(table):
    horses = []
    for tr in table.select('tbody > tr'):
        a = tr.select_one('td.horse a[href*="CNAME=pw01dud"]')
        if not a:
            continue
        m = re.search(r'pw01dud\d{2}(\d{10})', a['href'])
        hc = re.search(r'CNAME=(pw01dud[^"&\']+)', a['href'])
        h = {'horseId': m.group(1) if m else '', 'name': text(a), 'horseCname': hc.group(1) if hc else ''}
        w = tr.select_one('td.waku img')
        m = re.search(r'枠(\d)', w.get('alt', '') if w else '')
        h['waku'] = m.group(1) if m else ''
        num = tr.select_one('td.num')
        m = re.match(r'\s*(\d+)', num.get_text() if num else '')
        h['umaban'] = m.group(1) if m else ''
        h['owner'] = text(tr.select_one('p.owner'))
        # 騎手の欄。名前はふつう騎手のページへのリンクだが、短期免許が出たばかりの外国人騎手（10/29 の A.プーシャン など）は
        # 騎手のページがまだなく、リンクのない文字だけになる（以前はリンクだけを読んでいたので空になっていた。10/29 修正）
        cands = [x for x in (tr.select_one('p.jockey'), tr.select_one('td.jockey')) if x]
        jc = next((x for x in cands if x.select_one('a')), cands[0] if cands else None)
        mark = text(jc.select_one('span.mark')) if jc else ''   # 減量記号（▲△☆◇★）。<span class="mark jockey" title="3kg減量">▲</span><a>名前</a>
        a = jc.select_one('a') if jc else None
        name = text(a) if a else (text(jc).replace(mark, '', 1).strip() if jc else '')
        h['jockey'] = f'{mark} {name}' if mark and name else name   # 結果ページと同じ「▲ 遠藤 汰月」の形（10/26〜。以前は記号を読んでいなかった）
        age = tr.select_one('p.age') or tr.select_one('td.age')
        h['sexAge'] = text(age).split('/')[0]
        m = re.search(r'(\d+(?:\.\d)?)', text(tr.select_one('td.weight')))   # 負担重量（斤量）「55.0 kg」
        h['weight'] = m.group(1) if m else ''
        rowtxt = text(tr)
        h['status'] = '取消' if '取消' in rowtxt else ('除外' if '除外' in rowtxt else '')
        horses.append(h)
    return horses

def parse_race_tables(html):
    soup = BeautifulSoup(html, 'html.parser')
    races = []
    for table in soup.select('table'):
        cap = table.select_one('caption .race_header')
        if not cap:
            continue
        info = parse_header(cap)
        if 'r' not in info:
            continue
        info['horses'] = parse_rows(table)
        races.append(info)
    return races

def horse_owner(html):
    soup = BeautifulSoup(html, 'html.parser')
    for dt in soup.select('dt'):
        if text(dt) == '馬主名':
            return text(dt.find_next_sibling('dd'))
    return None

def links(html, prefix):
    found = re.findall(r"doAction\('/JRADB/accessD\.html',\s*'(%s[^']*)'\)" % prefix, html)
    found += re.findall(r'CNAME=(%s[^"&\']+)' % prefix, html)
    return list(dict.fromkeys(found))

# ---------------------------------------------------------------- main
def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else default

def at_jst(hhmm):
    h, m = map(int, hhmm.split(':'))
    return datetime.now(JST).replace(hour=h, minute=m, second=0, microsecond=0)

def already_fetched(mode, now, races):
    """同じ見張りがもう済んでいるか（10/26〜）。外からの起動と定期実行の両方で同じ見張りが2回動くことがあるため、
    2回目は JRA を読み直さずに終わる（同じグループの実行は順に動くので、2回目は1回目が終わってから始まる）。
    - umaban: 今日10時以降に races.json が更新されていて、翌日のクラブ馬（取消・除外を除く）に1頭以上いて全頭に馬番がある
    - confirm: 今日15時以降に races.json が更新されていて、今日より後の開催日がある（木曜の週末分は取得済み）
    races.json は変化がなければ書き換えないので、「今日更新された」は今日の取得で何かが入ったことを表す。
    返り値は理由の文（済んでいなければ None）"""
    try:
        upd = datetime.fromisoformat(races.get('updated', '')).astimezone(JST)
    except (TypeError, ValueError):
        return None
    if upd.date() != now.date():
        return None
    today = now.date().isoformat()
    tomorrow = (now.date() + timedelta(days=1)).isoformat()
    if mode == 'umaban' and upd.hour >= 10:
        hs = [h for h in races.get('horses', []) if h.get('date') == tomorrow and not h.get('status')]
        if hs and all(h.get('umaban') for h in hs):
            return f'{tomorrow} のクラブ馬 {len(hs)}頭の馬番は {upd:%H:%M} に取得済み'
    if mode == 'confirm' and upd.hour >= 15:
        later = sorted(d['date'] for d in races.get('days', []) if d.get('date', '') > today)
        if later:
            return f'{"・".join(later)} の出馬表は {upd:%H:%M} に取得済み'
    return None

def main():
    offline = arg('--offline')
    mode = arg('--mode')                     # None（1回だけ）/ confirm（新しい開催日の出走確定）/ umaban（翌日の馬番）
    interval = int(arg('--interval', '5')) * 60
    clubs = load_clubs()
    f = Fetcher(offline)
    os.makedirs(DATA, exist_ok=True)
    # 起動時点で races.json にある開催日。これにない日が出馬表トップに載ったら「新しい開催日」
    known, races0 = set(), {}
    if os.path.exists(OUT):
        races0 = json.load(open(OUT, encoding='utf-8'))
        known = {d['date'] for d in races0.get('days', [])}
    ctx = {'known': known, 'prev': {}, 'verified': set()}
    done = already_fetched(mode, datetime.now(JST), races0) if mode and not offline else None
    if done:
        # 同じ見張りが2回目に動いた時（外からの起動と定期実行が重なった時など）は JRA にアクセスせずに終わる（10/26〜）
        print(f'{done}。同じ見張りは済んでいるので何もしない（JRA にはアクセスしない）', flush=True)
        print(f'::notice::{done}（2回目の見張りなので JRA にはアクセスしていない）', flush=True)
        ctx['done'] = done
        write_summary(mode, 'skip', 0, 0, ctx)
        return 0
    if mode and not offline:
        start = at_jst(arg('--start', '00:00'))
        until = at_jst(arg('--until', '23:59'))
        watch = at_jst(arg('--watch-until')) if arg('--watch-until') else until
        wait = (start - datetime.now(JST)).total_seconds()
        if wait > 0:
            print(f'{start:%H:%M} まで待機（{int(wait // 60)}分）', flush=True)
            time.sleep(wait)
    state = None
    while True:
        f.memo = {}
        try:
            state = attempt(f, clubs, mode, ctx)
            ctx['last_error'] = False
        except Exception as e:   # 一時的な通信エラーで見張りごと止めない（5分後に取り直す）
            print(f'::warning::取得中にエラー: {e!r}', flush=True)
            ctx['last_error'] = True
            ctx['errors'] = ctx.get('errors', 0) + 1
            # まだ一度も取れていなければ「未発表」と同じ扱い（平日の見張りは --watch-until で終わる）
            state = 'error' if not mode else ('notready' if ctx.get('ok') else 'waiting')
        print(f'  → {state}（ここまでのリクエスト数: {f.count}）', flush=True)
        if state not in ('waiting', 'notready') or not mode or offline:
            break
        nxt = datetime.now(JST).timestamp() + interval
        if state == 'waiting' and nxt > watch.timestamp():
            print(f'{watch:%H:%M} までに新しい出馬表は出なかった', flush=True)
            break
        if nxt > until.timestamp():
            print(f'{until:%H:%M} までに出馬表が揃わなかったので打ち切り（ページの形式が変わった可能性もある）', flush=True)
            break
        time.sleep(interval)
    print(f'リクエスト数: {f.count}')
    code = exit_code(mode, state, ctx, datetime.now(JST))
    write_summary(mode, state, code, f.count, ctx)
    return code

def write_summary(mode, state, code, count, ctx):
    """Actions の実行結果のページに要約を出す（保守用。GITHUB_STEP_SUMMARY がある時だけ）"""
    path = os.environ.get('GITHUB_STEP_SUMMARY')
    if not path:
        return
    names = {}
    try:
        names = {c['id']: c['name'] for c in load_club_list()}
    except Exception:
        pass
    last = ctx.get('last')
    L = ['## 出馬表の取得', '',
         f"- モード: {mode or '1回だけ'}／結果: {state}／終了コード: {code}／リクエスト数: {count}"]
    if ctx.get('errors'):
        L.append(f"- 通信エラー: {ctx['errors']}回")
    if last:
        L += [f"- 開催: {'、'.join(last['meetings'])}",
              f"- races.json: {'更新' if last['changed'] else '変更なし'}／クラブ馬 {last['total']}頭（馬番あり {last['umaban']}頭）"]
        if last['scratched']:
            L.append(f"- 取消・除外: {'、'.join(last['scratched'])}")
        if last.get('regist'):
            L.append(f"- 競走馬登録の一覧で判定（馬のページを読まなかった）: {last['regist']}頭（うちクラブ馬 {last['regist_club']}頭）／馬のページ: {last['horse_pages']}回")
        L += ['', '| クラブ | 頭数 |', '|---|---:|']
        L += [f"| {names.get(k, k)} | {v} |" for k, v in sorted(last['hits'].items(), key=lambda kv: -kv[1])]
        L += ['', f"一致しなかったクラブらしい名義: {'、'.join(last['miss']) or 'なし'}"]
    elif ctx.get('done'):
        L.append(f"- 出馬表は取得していない（{ctx['done']}。2回目の見張りなので JRA にはアクセスしていない）")
    else:
        L.append('- 出馬表は取得していない（未発表・対象なし・エラー）')
    if ctx.get('changed'):
        L += ['', f"名義が変わった馬: {'、'.join(ctx['changed'])}"]
    with open(path, 'a', encoding='utf-8') as fp:
        fp.write('\n'.join(L) + '\n')

def year_end(now):
    """年末年始（有馬記念・ホープフルSのあと〜金杯のころ）は開催の曜日が不規則なので、木曜の失敗判定から外す"""
    return (now.month == 12 and now.day >= 24) or (now.month == 1 and now.day <= 7)

def exit_code(mode, state, ctx, now):
    """取得が止まったことに Actions の失敗（GitHub からのメール）で気づけるようにする"""
    if ctx.get('format_error') or state == 'error':
        return 1
    if ctx.get('last_error') and not ctx.get('ok'):
        print('::error::最後まで通信エラーで、一度も取得できなかった', flush=True)
        return 1
    already = any(d > now.date().isoformat() for d in ctx.get('known', ()))   # 手動実行などで既に取得済み
    if mode == 'confirm' and state == 'waiting' and now.weekday() == 3 and not year_end(now) and not already:
        print('::error::木曜なのに、締め切りまでに週末の出馬表（新しい開催日）を取れなかった。'
              'ページ構造の変更か、発表の遅れの可能性。19:05 の安全網の結果も確認すること', flush=True)
        return 1
    return 0

def read_meeting(f, mt):
    """開催1つ分: ({R: 個別レースのcname}, まとめページのレース) を返す"""
    rl = f.get(mt['cname'], post=True)
    race_pages = {}
    for c in links(rl, 'pw01dde'):
        m = re.match(r'pw01dde\d{2}\d{2}\d{4}\d{2}\d{2}(\d{2})\d{8}', c)
        if m:
            race_pages[int(m.group(1))] = c
    all_pages = links(rl, 'pw01des')
    races = parse_race_tables(f.get(all_pages[0], post=True)) if all_pages else []
    return race_pages, races

# 出馬表は一斉ではなく少しずつ載ることがあるので、揃ったかを確かめてから終える
# 1日のレース数は12とは限らない（2027年夏の新潟・中京は1日7競走）ので、
# 12レース載るか、出走馬の載ったレース数が前回（5分前）から増えていなければ揃ったとみなす
RACES_PER_DAY = 12

def runners(races):
    return sum(1 for r in races if r['horses'])

def confirm_complete(key, race_pages, races, prev):
    n = runners(races); before = prev.get(key); prev[key] = n
    if len(race_pages) > n:   # レース一覧にあるのに出走馬が載っていないレースがある
        return False
    return n >= RACES_PER_DAY or (n > 0 and n == before)

def umaban_complete(races):
    """取消・除外を除く全出走馬に馬番が入っているか"""
    hs = [h for r in races for h in r['horses'] if not h['status']]
    return bool(hs) and all(h['umaban'] for h in hs)

def load_regist():
    """競走馬登録の一覧（regist.json）から {馬名: {(生年4桁, クラブID か '')}}。
    ファイルがない・壊れている時は空にする（今までどおり馬のページを読む）"""
    try:
        with open(REGIST, encoding='utf-8') as fp:
            d = json.load(fp)
        out = {}
        for rows in d['horses'].values():
            for r in rows:
                if isinstance(r, list) and len(r) >= 3 and isinstance(r[0], str) and isinstance(r[1], str) and isinstance(r[2], str):
                    out.setdefault(r[0], set()).add((r[1][:4], r[2]))
        return out
    except FileNotFoundError:
        return {}
    except Exception as e:   # 壊れていても出馬表の取得は止めない
        print(f'regist.json を読めなかったので使わない: {e}', flush=True)
        return {}

def write_status(st, push=False):
    """data/status.json を書く。push=True で、GitHub Actions の main の上（環境変数 RACECARD_PUSH_STATUS=1）なら、
    すぐにコミットして push する（取得の終わりを待たずに画面に「集計中」を出すため）。失敗しても出馬表の取得は止めない"""
    try:
        with open(STATUS, 'w', encoding='utf-8') as fp:
            json.dump(st, fp, ensure_ascii=False)
    except OSError as e:
        print(f'status.json を書けなかった: {e}', flush=True)
        return False
    if not push or os.environ.get('RACECARD_PUSH_STATUS') != '1':
        return False
    import subprocess
    def git(*a):
        return subprocess.run(['git', *a], cwd=ROOT, capture_output=True, text=True, timeout=120).returncode
    try:
        git('add', 'data/status.json')
        if git('commit', '-q', '-m', f"出馬表の集計を開始 {datetime.now(JST):%m/%d %H:%M}") != 0:
            return False
        for i in range(3):   # 結果の取得の push と重なることがあるので、取り込み直して3回まで
            if git('pull', '--rebase', '--autostash', '-q', 'origin', 'main') == 0 and git('push', '-q') == 0:
                print('集計中の表示（status.json）を push した', flush=True)
                return True
            git('rebase', '--abort')
            time.sleep(5 * (i + 1))
    except Exception as e:
        print(f'集計中の表示の push でエラー: {e!r}', flush=True)
    print('::warning::集計中の表示（status.json）を push できなかった（取得は続ける）', flush=True)
    return False

def estimate_pages(f, meetings, club_of, regist, seen, today):
    """これから読む個別レース・馬のページのおよその数（集計中の表示の見込み時刻用）。
    開催のページは read_meeting で読む（同じ試行の中では読み直さないので、このあとの取得でリクエストは増えない）"""
    n = 0
    for mt in meetings:
        race_pages, races = read_meeting(f, mt)
        for race in races:
            hs = race['horses']
            unknown = [h for h in hs if h['horseId'] not in club_of]
            rdate = race.get('date', mt['date'])
            if any(h['umaban'] for h in hs):
                n += 1 if (unknown or (rdate > today and any(club_of.get(h['horseId']) for h in hs))) and race['r'] in race_pages else 0
                continue
            n += sum(1 for h in unknown if h['horseCname'] and len({c for y, c in regist.get(h['name'], ()) if y == h['horseId'][:4]}) != 1)
            if rdate > today:
                n += sum(1 for h in hs if club_of.get(h['horseId']) and seen.get(h['horseId']) and days_between(seen[h['horseId']], rdate) >= STALE_DAYS)
    return n

def save_records(cache, seen, club_of):
    """名義の記録（cache.json: 馬ID → クラブID か空文字）と、クラブ馬が最後に載った日（seen.json）を書く"""
    json.dump(cache, open(CACHE, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'), sort_keys=True)
    json.dump({k: v for k, v in seen.items() if club_of.get(k)}, open(SEEN, 'w', encoding='utf-8'), separators=(',', ':'), sort_keys=True)

def attempt(f, clubs, mode, ctx):
    """1回分の取得。返り値:
    'ready'（取得して揃っていた）/ 'notready'（取得したが反映途中）/ 'waiting'（まだ発表されていない）/ 'skip'（対象なし）"""
    top = f.get('pw01dli00/F3', post=True)
    lists = links(top, 'pw01drl')
    if not lists:
        print('出馬表の開催一覧が見つかりませんでした（開催がない週、またはページの形式が変わった可能性）')
        return 'waiting' if mode == 'confirm' else 'skip'
    # 開催へのリンクは pw01drl{種別2}{場2}{年4}{回2}{日2}{年月日8}。種別 00 が出馬表を読める開催。
    # 平日はレースの終わった前の週の開催が種別 10 で載っていることがある（10/21 水曜に確認）ので、それは読まずに飛ばす
    meetings, others = [], []
    for c in lists:
        m = re.match(r'pw01drl(\d{2})(\d{2})\d{4}\d{2}\d{2}(\d{8})', c)
        if not m:
            continue
        if m.group(1) != '00':
            others.append(c)
            continue
        d = m.group(3)
        meetings.append({'cname': c, 'venue': VENUES.get(m.group(2), m.group(2)), 'date': f'{d[:4]}-{d[4:6]}-{d[6:]}'})
    if others:
        print('出馬表を読まない開催のリンク（終わった週など）:', others[:3], flush=True)
    if not meetings:
        if others:
            print('出馬表を読める開催はまだ載っていない')
            return 'waiting' if mode == 'confirm' else 'skip'
        print('::error::出馬表トップに開催へのリンクはあるが、形式が読めなかった（ページ構造の変更）:', lists[:3], flush=True)
        ctx['format_error'] = True
        return 'skip'
    dates = sorted({x['date'] for x in meetings})
    print(datetime.now(JST).strftime('%H:%M'), '開催:', ', '.join(f"{x['date']} {x['venue']}" for x in meetings), flush=True)

    # 発表されたかを軽く確認（対象の開催1つだけ読む）
    today = datetime.now(JST).date().isoformat()
    tomorrow = (datetime.now(JST).date() + timedelta(days=1)).isoformat()
    new_dates = sorted(d for d in dates if d > today and d not in ctx['known'])
    check = []   # 揃ったかを確かめる開催
    if mode == 'confirm':
        # 新しい開催日（木曜の週末分、年末年始・代替競馬などの平日開催も）が載るのを待つ
        check = [m for m in meetings if m['date'] in new_dates]
        if not check:
            print('新しい開催日の出馬表はまだ載っていない')
            return 'waiting'
        if runners(read_meeting(f, check[0])[1]) < 2:   # GI週の木曜14時はGIの1レースだけ載る
            print('出走確定の出馬表がまだ出ていない')
            return 'waiting'
    elif mode == 'umaban':
        check = [m for m in meetings if m['date'] == tomorrow]
        if not check:
            if not new_dates:
                print(f'{tomorrow} の開催も新しい開催日もないので何もしない')
                return 'skip'
            print('新しい開催日があるので取得:', ', '.join(new_dates))
        elif not any(h['umaban'] for r in read_meeting(f, check[0])[1] for h in r['horses']):
            print('馬番つきの出馬表がまだ出ていない')
            return 'waiting'

    cache = {}
    if os.path.exists(CACHE):
        cache = json.load(open(CACHE, encoding='utf-8'))
    club_of = cache.setdefault('clubOf', {})   # horseId -> clubId（クラブ以外は ''）
    seen_owners = {}                           # 確認用（保存しない）
    def remember(h, owner):
        seen_owners[h['horseId']] = owner
        club_of[h['horseId']] = clubs.get(norm_owner(owner), '')

    # 馬番が出る前（木曜）に記録にない馬は、競走馬登録の一覧（regist.json）に馬名と生年（馬IDの先頭4桁）が一致すれば、
    # 馬のページを読まずにその判定で載せる・載せないを決める（10/29〜）。判定は cache.json には記録しない
    # （馬番が出た日に、記録にない馬として個別レースのページを読み、馬主名で確定する。万一判定を誤っても木曜〜翌朝の1回分で直る）
    regist = load_regist()
    guess = {}   # 馬ID → クラブID か ''（この回だけ。保存しない）
    result = []
    stats = {'detail': 0, 'horse': 0, 'stale': 0, 'regist': 0}
    seen = json.load(open(SEEN, encoding='utf-8')) if os.path.exists(SEEN) else {}
    complete = True
    # 新しい開催日の出走確定を見つけたら、読むページの数から終わる時刻を見積もり、画面に「集計中」を出す（10/29〜。1回の実行で1回だけ）
    if mode == 'confirm' and new_dates and not ctx.get('status'):
        try:
            pages = estimate_pages(f, meetings, club_of, regist, seen, today)
            now = datetime.now(JST)
            eta = now + timedelta(seconds=pages * (WAIT + 0.6) + 120)   # 1ページ約2.6秒＋公開ページへの反映
            ctx['status'] = {'state': 'collecting', 'dates': new_dates, 'since': now.isoformat(timespec='seconds'),
                             'eta': eta.isoformat(timespec='seconds'), 'pages': pages}
            print(f'集計を開始: 読むページ 約{pages}／見込み {eta:%H:%M}', flush=True)
            write_status(ctx['status'], push=True)
        except Exception as e:   # 見積もり・表示で失敗しても取得は続ける
            print(f'::warning::集計中の表示でエラー: {e!r}', flush=True)
            ctx['status'] = {'state': 'error'}
    try:
        for mt in meetings:
            race_pages, races = read_meeting(f, mt)
            if not races:  # まとめページがない場合は各レースのページを読む
                races = [r for c in race_pages.values() for r in parse_race_tables(f.get(c))]
            for race in races:
                rno = race['r']
                unknown = [h for h in race['horses'] if h['horseId'] not in club_of]
                # クラブ馬として記録済みの馬も、馬番が出た明日以降のレースでは個別ページの馬主名で確かめ直す
                # （クラブを離れて地方に移った馬が中央に戻ってきた時に、クラブ馬として載せないため）。1回の実行で1レース1回だけ
                rdate = race.get('date', mt['date'])
                recheck = rdate > today and (mt['cname'], rno) not in ctx['verified'] and any(club_of.get(h['horseId']) for h in race['horses'])
                if (unknown or recheck) and any(h['umaban'] for h in race['horses']) and rno in race_pages:
                    detail = parse_race_tables(f.get(race_pages[rno]))
                    ctx['verified'].add((mt['cname'], rno))   # 読めてから記録する（通信エラーで止まった時は次の試行で確かめ直す）
                    stats['detail'] += 1
                    for d in (detail[0]['horses'] if detail else []):
                        if d['owner']:
                            was = club_of.get(d['horseId'])
                            remember(d, d['owner'])
                            if was and club_of[d['horseId']] != was:
                                print(f"    名義が変わった: {d['name']}（{was} → {club_of[d['horseId']] or 'クラブ以外'}）", flush=True)
                                ctx.setdefault('changed', []).append(f"{d['name']}（{was} → {club_of[d['horseId']] or 'クラブ以外'}）")
                    unknown = [h for h in race['horses'] if h['horseId'] not in club_of]
                for h in unknown:
                    if not h['horseCname']:
                        continue
                    if regist and not any(x['umaban'] for x in race['horses']):
                        hit = {c for y, c in regist.get(h['name'], ()) if y == h['horseId'][:4]}
                        if len(hit) == 1:
                            guess[h['horseId']] = hit.pop()
                            stats['regist'] += 1
                            continue
                    owner = horse_owner(f.get(h['horseCname'], path='/JRADB/accessU.html'))
                    stats['horse'] += 1
                    if owner is not None:
                        remember(h, owner)
                # 馬番が出る前（木曜）のレースで、しばらく中央の出馬表に載っていなかったクラブ馬は、馬のページで名義を確かめる
                # （売却されて地方へ移り、中央に再登録されて戻ってきた馬をクラブ馬として載せないため。最速でも2か月ほどかかる）
                if rdate > today and not any(h['umaban'] for h in race['horses']):
                    for h in race['horses']:
                        last = seen.get(h['horseId'])
                        if not club_of.get(h['horseId']) or not last or days_between(last, rdate) < STALE_DAYS or not h['horseCname']:
                            continue
                        owner = horse_owner(f.get(h['horseCname'], path='/JRADB/accessU.html'))
                        stats['stale'] += 1
                        if owner is not None:
                            was = club_of[h['horseId']]
                            remember(h, owner)
                            if club_of[h['horseId']] != was:
                                print(f"    名義が変わった: {h['name']}（{was} → {club_of[h['horseId']] or 'クラブ以外'}）", flush=True)
                                ctx.setdefault('changed', []).append(f"{h['name']}（{was} → {club_of[h['horseId']] or 'クラブ以外'}）")
                for h in race['horses']:
                    club = club_of.get(h['horseId']) if h['horseId'] in club_of else guess.get(h['horseId'], '')
                    if not club:
                        continue
                    if seen.get(h['horseId'], '') < rdate:
                        seen[h['horseId']] = rdate
                    result.append({
                        'key': f"{mt['date']}|{mt['venue']}|{rno}|{h['horseId']}", 'horseId': h['horseId'], 'name': h['name'],
                        'clubId': club,
                        'date': race.get('date', mt['date']), 'venue': race.get('venue', mt['venue']), 'r': rno,
                        'time': race.get('time', ''), 'raceName': race.get('raceName', ''), 'grade': race.get('grade', ''), 'cls': race.get('cls', ''),
                        'surface': race.get('surface', ''), 'dist': race.get('dist', ''),
                        'jockey': h['jockey'], 'waku': h['waku'], 'umaban': h['umaban'], 'sexAge': h['sexAge'], 'weight': h['weight'], 'status': h['status'],
                    })
            print(f"  {mt['date']} {mt['venue']}: {len(races)}R / 累計 {len(result)} 頭 / 詳細 {stats['detail']} / 馬ページ {stats['horse']} / 久々の確認 {stats['stale']} / 登録一覧で判定 {stats['regist']}", flush=True)
            if mt in check:
                ok = confirm_complete(mt['cname'], race_pages, races, ctx['prev']) if mode == 'confirm' else umaban_complete(races)
                if not ok:
                    got = runners(races) if mode == 'confirm' else sum(1 for r in races if r['horses'] and all(h['umaban'] or h['status'] for h in r['horses']))
                    print(f"    {mt['date']} {mt['venue']} はまだ揃っていない（{'出走馬' if mode == 'confirm' else '馬番'}の載ったレース {got}）", flush=True)
                    complete = False

    except Exception:
        # 途中で止まっても（通信エラーなど）、それまでに分かった名義の記録は残す（10/26〜）。
        # 以前は試行の最後にしか保存しなかったため、木曜の初回（約900リクエスト）の途中で止まると5分後に最初から読み直していた
        save_records(cache, seen, club_of)
        raise
    # 確認用: クラブらしい名義なのに一致しなかったもの
    hits = {}
    for x in result:
        hits[x['clubId']] = hits.get(x['clubId'], 0) + 1
    print('クラブ別:', hits)
    miss = sorted({o for o in seen_owners.values() if re.search(r'レーシング|ホース|クラブ|サラブレッド|ファーム|racing|horse|club', o, re.I) and not clubs.get(norm_owner(o))})
    print('一致しなかったクラブらしい名義:', miss)
    order = {v: i for i, v in enumerate(VENUES.values())}
    result.sort(key=lambda x: (x['date'], order.get(x['venue'], 99), x['r'], int(x['umaban'] or 99)))
    days = [{'date': d, 'venues': [m['venue'] for m in meetings if m['date'] == d]} for d in dates]
    out = {
        'source': 'JRAホームページ 出馬表',
        'updated': datetime.now(JST).isoformat(timespec='minutes'),
        'days': days,
        'horses': result,
    }
    old = json.load(open(OUT, encoding='utf-8')) if os.path.exists(OUT) else {}
    if {k: v for k, v in old.items() if k != 'updated'} == {k: v for k, v in out.items() if k != 'updated'}:
        print('変更なし')
        changed = False
    else:
        json.dump(out, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'data/races.json を更新: {len(result)} 頭')
        changed = True
    ctx['last'] = {'meetings': [f"{x['date']} {x['venue']}" for x in meetings], 'total': len(result), 'hits': hits,
                   'miss': miss, 'changed': changed, 'umaban': sum(1 for x in result if x['umaban']),
                   'scratched': [f"{x['name']}（{x['status']}）" for x in result if x['status']],
                   'regist': stats['regist'], 'regist_club': sum(1 for x in result if x['horseId'] not in club_of and x['horseId'] in guess),
                   'horse_pages': stats['horse']}
    save_records(cache, seen, club_of)
    if ctx.get('status', {}).get('state') == 'collecting' and complete:
        # 集計が終わった（最後のコミットで races.json と一緒に公開される）
        write_status({'state': 'done', 'dates': ctx['status']['dates'], 'since': ctx['status']['since'],
                      'updated': datetime.now(JST).isoformat(timespec='seconds')})
        ctx['status']['state'] = 'done'
    ctx['ok'] = True
    if not complete:
        print('まだ揃っていない開催がある（JRAのサイトへの反映途中）')
        return 'notready'
    return 'ready'

if __name__ == '__main__':
    sys.exit(main())
