"""
JRAホームページの「競走馬登録・抹消一覧」を読み、次の2つを保存する（10/29〜、claude/10_登録抹消一覧の調査.md）。

data/retired.json — 登録抹消になった馬の 馬名・抹消日・父・母（抹消日から1年分）
  画面（出走カード）は、★を付けた馬（馬IDの★・出走待ちの馬名の★）を馬名で照合し、登録抹消になった馬をバナーで知らせる（★を外すのは利用者）
  - 抹消一覧には馬IDも馬主もない。照合は馬名で行う（中央の現役の登録馬名は重複しない）。父・母は利用者の確認用
  - クラブ馬以外の抹消馬も含めて公開する（JRA のページで誰でも見られる情報で、馬主・調教師・賞金は入れない。10/29 私の判断）
  - 抹消のあとに競走馬登録の一覧に同じ馬名・父・母で載った馬（地方から戻ってきた再登録など）は外す

data/regist.json — 競走馬登録の一覧に載った馬の 馬名・生年月日・クラブID（クラブ以外は空）・父・母（登録日から1年分）
  木曜の出馬表の取得（fetch_races.py）が、記録（cache.json）にない馬を馬のページを読まずに判定するのに使う
  - 馬主名は保存しない（clubs.js の名義と照合した結果のクラブIDか空文字だけ）

- 入口（POST /JRADB/accessV.html cname=pv156liH1/98）に、抹消日ごとのリンク（約1か月分、掲載は通常 月曜11時頃・木曜18時頃）と
  登録日ごとのリンク（5週分、毎週木曜受付・翌週月曜11時頃掲載）が頭数つきで並ぶ。まだ読んでいない日・頭数が変わった日だけ読む
- 1回あたり 入口1＋新しい抹消日（ふだん3〜5）＋新しい登録日（月曜だけ1）。初回は約1か月分で35前後
- リクエストの間は2秒以上あける（fetch_races.py の Fetcher）

使い方:
  python3 tools/fetch_retired.py               # JRAから1回取得
  python3 tools/fetch_retired.py --offline DIR  # 保存済みHTMLで動作確認（DIR/<cname の / を _ にしたもの>.html）

終了コード: 1 = 入口・各ページの形式が読めない（ページ構造の変更）／通信エラーで読めなかった。それ以外は 0
"""
import argparse, json, os, re, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_races as fr
from bs4 import BeautifulSoup

OUT = os.path.join(fr.DATA, 'retired.json')
REG_OUT = os.path.join(fr.DATA, 'regist.json')
PATH = '/JRADB/accessV.html'
ENTRY = 'pv156liH1/98'      # 競走馬登録・抹消一覧（どのページのメニューにもある doAction の値。10/29 確認）
MENU_PAGE = 'pw01dli00/F3'  # 入口が読めない時に、メニューから入口の値を拾い直すページ（出馬表トップ）
KEEP_DAYS = 365
MAX_DAYS = 35               # 1回に読む抹消日の上限（初回は一覧の約1か月分＝28日前後を読む）

DAY_LINK = re.compile(r"doAction\('/JRADB/accessV\.html'\s*,\s*'(pv16mdj\d{2}(\d{8})/\w{2})'\)")
REG_LINK = re.compile(r"doAction\('/JRADB/accessV\.html'\s*,\s*'(pv15udj\d{2}(\d{8})/\w{2})'\)")
ENTRY_LINK = re.compile(r"doAction\('/JRADB/accessV\.html'\s*,\s*'(pv156li[^']+)'\)")


class FormatError(Exception):
    pass


def now_jst():
    return datetime.now(fr.JST)


def load(path=None):
    try:
        with open(path or OUT, encoding='utf-8') as fp:
            d = json.load(fp)
        if isinstance(d.get('horses'), dict) and isinstance(d.get('counts'), dict):
            return d
    except (OSError, ValueError):
        pass
    return {'updated': '', 'counts': {}, 'horses': {}}


def parse_entry(html, link=DAY_LINK):
    """入口のページから [(日付 YYYY-MM-DD, cname, 頭数)]（新しい順）。link=DAY_LINK は抹消日、REG_LINK は登録日"""
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for a in soup.find_all('a'):
        m = link.search((a.get('onclick') or '') + ' ' + (a.get('href') or ''))
        if not m:
            continue
        ymd = m.group(2)
        n = re.search(r'（\s*(\d+)\s*頭\s*）|\(\s*(\d+)\s*頭\s*\)', fr.text(a))
        out.append((f'{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}', m.group(1), int(next(g for g in n.groups() if g)) if n else None))
    return out


def parse_day(html):
    """抹消日のページから [{name, sire, dam}]。表が見つからなければ FormatError"""
    soup = BeautifulSoup(html, 'html.parser')
    table = None
    for t in soup.find_all('table'):
        if '抹消' in fr.text(t.caption) or t.find('th', string=re.compile('抹消馬名')):
            table = t
            break
    if table is None:
        raise FormatError('抹消日のページに抹消一覧の表がない')
    out = []
    for tr in table.find_all('tr'):
        th = tr.find('th', attrs={'scope': 'row'})
        if not th:
            continue
        name = fr.text(th)
        if not name:
            continue
        par = tr.select_one('td.family .parent') or tr.select_one('td.family')
        ps = [s.strip() for s in par.get_text('\n').split('\n') if s.strip()] if par else []
        out.append({'name': name, 'sire': ps[0] if ps else '', 'dam': ps[1] if len(ps) > 1 else ''})
    return out


def parse_regist(html, clubs):
    """登録日のページから [{name, birth, club, sire, dam}]。馬主名はクラブIDに置き換え、名前そのものは返さない。
    列: 馬名（th）／性別・毛色、生年月日（td.data）／（美浦・栗東）調教師、産地・生産牧場、馬主名（td.stable）／父・母（div.parent）／母の父・母の母"""
    soup = BeautifulSoup(html, 'html.parser')
    table = None
    for t in soup.find_all('table'):
        if '競走馬登録' in fr.text(t.caption) or t.find('th', string=re.compile('^馬名$')):
            table = t
            break
    if table is None:
        raise FormatError('登録日のページに競走馬登録の表がない')
    out = []
    for tr in table.find_all('tr'):
        th = tr.find('th', attrs={'scope': 'row'})
        if not th or not fr.text(th):
            continue
        lines = lambda el: [x.strip() for x in el.get_text('\n').split('\n') if x.strip()] if el else []
        data, stable = lines(tr.select_one('td.data')), lines(tr.select_one('td.stable'))
        m = re.search(r'(\d{4})年(\d{1,2})月(\d{1,2})日', ' '.join(data))
        if not m or len(stable) < 3:
            raise FormatError(f'登録日のページの行の形が違う: {fr.text(tr)[:60]}')
        par = [fr.text(x) for x in tr.select('div.parent span')] or lines(tr.select_one('div.parent'))
        out.append({'name': fr.text(th), 'birth': f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}',
                    'club': clubs.get(fr.norm_owner(stable[-1]), ''),
                    'sire': par[0] if par else '', 'dam': par[1] if len(par) > 1 else ''})
    return out


def entry_page(f, log):
    """入口のページの HTML。読めない・形が違う時は、出馬表トップのメニューから入口の値を拾い直して1回だけ読み直す"""
    html = f.get(ENTRY, post=True, path=PATH)
    if parse_entry(html):
        return html
    log.append('入口の値が変わった可能性があるので、メニューから拾い直す')
    m = ENTRY_LINK.search(f.get(MENU_PAGE, post=True))
    if m and m.group(1) != ENTRY:
        html = f.get(m.group(1), post=True, path=PATH)
        if parse_entry(html):
            log.append(f'入口の値: {m.group(1)}（fetch_retired.py の ENTRY を直す）')
            return html
    raise FormatError('入口のページに抹消日のリンクがない')


def read_days(f, data, days, parse, max_days, log, label):
    """まだ読んでいない日・頭数が変わった日だけ読んで data に入れる。戻り値 [(日付, 頭数)]"""
    new_days = []
    for ymd, cname, n in days:
        if len(new_days) >= max_days:
            log.append(f'{label}の上限（{max_days}）に達したので {ymd} より前は次回')
            break
        if n is not None and data['counts'].get(ymd) == n:
            continue
        rows = parse(f.get(cname, post=True, path=PATH))
        data['horses'][ymd] = rows
        data['counts'][ymd] = n if n is not None else len(rows)
        new_days.append((ymd, len(rows)))
        if n is not None and n != len(rows):
            log.append(f'{label} {ymd}: リンクは{n}頭、表は{len(rows)}頭')
    return new_days


def prune(data, limit):
    """limit より前の日を消す。消した日があれば True"""
    dropped = any(k < limit for k in data['counts']) or any(k < limit for k in data['horses'])
    data['counts'] = {k: v for k, v in sorted(data['counts'].items(), reverse=True) if k >= limit}
    data['horses'] = {k: v for k, v in sorted(data['horses'].items(), reverse=True) if k >= limit}
    return dropped


def reregistered(ret, reg):
    """抹消のあとに競走馬登録の一覧に同じ馬名・父・母で載った馬を retired から外す（地方から戻ってきた再登録など）。
    消した馬の [(馬名, 抹消日, 登録日)] を返す。抹消日の頭数（counts）はそのまま残すので、その日を読み直すことはない"""
    idx = {}
    for rd, rows in reg['horses'].items():
        for name, _birth, _club, sire, dam in rows:
            idx.setdefault(name, []).append((rd, sire, dam))
    removed = []
    for d, rows in ret['horses'].items():
        keep = []
        for name, sire, dam in rows:
            back = [rd for rd, s2, m2 in idx.get(name, ()) if rd > d and (not sire or not s2 or sire == s2) and (not dam or not m2 or dam == m2)]
            if back:
                removed.append((name, d, min(back)))
            else:
                keep.append([name, sire, dam])
        ret['horses'][d] = keep
    return removed


def run(f, today=None, clubs=None):
    """1回の取得。戻り値 (retired, regist, changed, info)
    どちらも {updated, counts: {日付: リンクの頭数}, horses: {日付: [[…], …]}}（新しい日が先）。
    retired の1頭は [馬名, 父, 母]、regist の1頭は [馬名, 生年月日, クラブID か '', 父, 母]。
    1年分で数千頭になるので、1頭1行の辞書ではなく日ごとの配列にして小さくしている"""
    today = today or now_jst().strftime('%Y-%m-%d')
    clubs = clubs if clubs is not None else fr.load_clubs()
    ret, reg = load(OUT), load(REG_OUT)
    log = []
    html = entry_page(f, log)
    rdays, gdays = parse_entry(html, DAY_LINK), parse_entry(html, REG_LINK)
    new_ret = read_days(f, ret, rdays, lambda h: [[r['name'], r['sire'], r['dam']] for r in parse_day(h)], MAX_DAYS, log, '抹消日')
    if gdays:
        new_reg = read_days(f, reg, gdays, lambda h: [[r['name'], r['birth'], r['club'], r['sire'], r['dam']] for r in parse_regist(h, clubs)],
                            MAX_DAYS, log, '登録日')
    else:
        new_reg = []
        log.append('入口のページに登録日のリンクがない（ページの形が変わった？ 抹消一覧だけ更新した）')
    limit = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
    ch_ret = prune(ret, limit) or bool(new_ret)
    ch_reg = prune(reg, limit) or bool(new_reg)
    removed = reregistered(ret, reg)
    for name, d, rd in removed:
        log.append(f'再登録のため抹消一覧から外した: {name}（{d} 抹消 → {rd} 登録）')
    ch_ret = ch_ret or bool(removed)
    return ret, reg, {'retired': ch_ret, 'regist': ch_reg}, {
        'new_days': new_ret, 'new_reg': new_reg, 'log': log, 'listed': len(rdays), 'listed_reg': len(gdays), 'removed': removed}


def write(data, path=None):
    path = path or OUT
    data['updated'] = now_jst().isoformat(timespec='seconds')
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        fp.write('{"updated":%s,\n"counts":%s,\n"horses":{\n' % (json.dumps(data['updated']), json.dumps(data['counts'], separators=(',', ':'))))
        fp.write(',\n'.join('%s:%s' % (json.dumps(k), json.dumps(v, ensure_ascii=False, separators=(',', ':'))) for k, v in data['horses'].items()))
        fp.write('}}\n')
    with open(tmp, encoding='utf-8') as fp:
        json.load(fp)   # 書いたものが JSON として読めることを確かめる
    os.replace(tmp, path)


def summary(lines):
    p = os.environ.get('GITHUB_STEP_SUMMARY')
    if p:
        with open(p, 'a', encoding='utf-8') as fp:
            fp.write('\n'.join(lines) + '\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--offline')
    a = ap.parse_args()
    f = fr.Fetcher(offline=a.offline)
    code, ret = 0, None
    info = {'new_days': [], 'new_reg': [], 'log': [], 'listed': 0, 'listed_reg': 0, 'removed': []}
    try:
        ret, reg, changed, info = run(f)
        if changed['retired']:
            write(ret, OUT)
        if changed['regist']:
            write(reg, REG_OUT)
        result = (f'抹消日 {info["listed"]}日分のうち{len(info["new_days"])}日分・登録日 {info["listed_reg"]}日分のうち{len(info["new_reg"])}日分を新しく読んだ'
                  + '（' + '・'.join([n for n, c in (('retired.json', changed['retired']), ('regist.json', changed['regist'])) if c]) + ' を更新）'
                  if any(changed.values()) else '（変更なし）')
        if not any(changed.values()):
            result = f'抹消日 {info["listed"]}日分・登録日 {info["listed_reg"]}日分が載っていて、新しい日はなかった（変更なし）'
        clubn = sum(1 for d, n in info['new_reg'] for r in reg['horses'].get(d, []) if r[2])
        if info['new_reg']:
            result += f'／新しく登録された馬のうちクラブ馬 {clubn}頭'
    except FormatError as e:
        code, result = 1, f'形式が読めない: {e}'
    except RuntimeError as e:   # Fetcher が3回取り直しても読めなかった
        code, result = 1, f'通信エラー: {e}'
    for line in info['log']:
        print(line)
    print(f'{result}／リクエスト {f.count} 回')
    print(f'::notice title=登録抹消・競走馬登録の取得::{result}／リクエスト {f.count} 回'
          + ''.join(f'／抹消 {d} {n}頭' for d, n in info['new_days']) + ''.join(f'／登録 {d} {n}頭' for d, n in info['new_reg']), flush=True)
    summary(['## 登録抹消・競走馬登録の取得', '', f'- 結果: {result}', f'- リクエスト: {f.count} 回',
             *(f'- 抹消 {d}: {n}頭' for d, n in info['new_days']), *(f'- 登録 {d}: {n}頭' for d, n in info['new_reg']),
             *(f'- 保存している抹消馬: {sum(map(len, ret["horses"].values()))}頭' for _ in [0] if ret), *(f'- {l}' for l in info['log'])])
    return code


if __name__ == '__main__':
    sys.exit(main())
