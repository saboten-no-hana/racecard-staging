"""
JRAホームページの「競走馬登録・抹消一覧」から、登録抹消になった馬の 馬名・抹消日・父・母 を集めて data/retired.json に保存する。
画面（出走カード）は、★を付けた馬（馬IDの★・出走待ちの馬名の★）を馬名で照合し、登録抹消になった馬をバナーで知らせる
（★を外すのは利用者。10/29 決定、claude/10_登録抹消一覧の調査.md）。

- 抹消一覧は抹消日ごとのページに分かれていて、約1か月分が載る。掲載は通常、月曜11時頃と木曜18時頃
- 入口（POST /JRADB/accessV.html cname=pv156liH1/98）で抹消日ごとのリンクと頭数を読み、
  まだ読んでいない日・頭数が変わった日だけ読む。1回あたり 入口1＋新しい日のページ（ふだん3〜5）
- 一覧には馬IDも馬主もない。照合は馬名で行う（中央の現役の登録馬名は重複しない）。父・母は利用者の確認用
- クラブ馬以外の抹消馬も含めて公開する（JRA のページで誰でも見られる情報で、馬主・調教師・賞金は入れない。10/29 私の判断）
- 残すのは抹消日から KEEP_DAYS 日まで
- リクエストの間は2秒以上あける（fetch_races.py の Fetcher）

使い方:
  python3 tools/fetch_retired.py               # JRAから1回取得
  python3 tools/fetch_retired.py --offline DIR  # 保存済みHTMLで動作確認（DIR/<cname の / を _ にしたもの>.html）

終了コード: 1 = 入口・抹消日のページの形式が読めない（ページ構造の変更）／通信エラーで読めなかった。それ以外は 0
"""
import argparse, json, os, re, sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fetch_races as fr
from bs4 import BeautifulSoup

OUT = os.path.join(fr.DATA, 'retired.json')
PATH = '/JRADB/accessV.html'
ENTRY = 'pv156liH1/98'      # 競走馬登録・抹消一覧（どのページのメニューにもある doAction の値。10/29 確認）
MENU_PAGE = 'pw01dli00/F3'  # 入口が読めない時に、メニューから入口の値を拾い直すページ（出馬表トップ）
KEEP_DAYS = 365
MAX_DAYS = 35               # 1回に読む抹消日の上限（初回は一覧の約1か月分＝28日前後を読む）

DAY_LINK = re.compile(r"doAction\('/JRADB/accessV\.html'\s*,\s*'(pv16mdj\d{2}(\d{8})/\w{2})'\)")
ENTRY_LINK = re.compile(r"doAction\('/JRADB/accessV\.html'\s*,\s*'(pv156li[^']+)'\)")


class FormatError(Exception):
    pass


def now_jst():
    return datetime.now(fr.JST)


def load():
    try:
        with open(OUT, encoding='utf-8') as fp:
            d = json.load(fp)
        if isinstance(d.get('horses'), dict) and isinstance(d.get('counts'), dict):
            return d
    except (OSError, ValueError):
        pass
    return {'updated': '', 'counts': {}, 'horses': {}}


def parse_entry(html):
    """入口のページから [(日付 YYYY-MM-DD, cname, 頭数)]（新しい順）"""
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for a in soup.find_all('a'):
        m = DAY_LINK.search((a.get('onclick') or '') + ' ' + (a.get('href') or ''))
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


def entry_page(f, log):
    """入口のページ。読めない・形が違う時は、出馬表トップのメニューから入口の値を拾い直して1回だけ読み直す"""
    html = f.get(ENTRY, post=True, path=PATH)
    days = parse_entry(html)
    if days:
        return days
    log.append('入口の値が変わった可能性があるので、メニューから拾い直す')
    m = ENTRY_LINK.search(f.get(MENU_PAGE, post=True))
    if m and m.group(1) != ENTRY:
        days = parse_entry(f.get(m.group(1), post=True, path=PATH))
        if days:
            log.append(f'入口の値: {m.group(1)}（fetch_retired.py の ENTRY を直す）')
            return days
    raise FormatError('入口のページに抹消日のリンクがない')


def run(f, today=None):
    """1回の取得。戻り値 (data, changed, info)
    data = {updated, counts: {抹消日: リンクの頭数}, horses: {抹消日: [[馬名, 父, 母], …]}}（新しい日が先）。
    1年分で約4,800頭になるので、1頭1行の辞書ではなく抹消日ごとの配列にして小さくしている"""
    today = today or now_jst().strftime('%Y-%m-%d')
    data = load()
    log, new_days = [], []
    days = entry_page(f, log)
    for ymd, cname, n in days:
        if len(new_days) >= MAX_DAYS:
            log.append(f'抹消日の上限（{MAX_DAYS}）に達したので {ymd} より前は次回')
            break
        if n is not None and data['counts'].get(ymd) == n:
            continue
        rows = parse_day(f.get(cname, post=True, path=PATH))
        data['horses'][ymd] = [[r['name'], r['sire'], r['dam']] for r in rows]
        data['counts'][ymd] = n if n is not None else len(rows)
        new_days.append((ymd, len(rows)))
        if n is not None and n != len(rows):
            log.append(f'{ymd}: リンクは{n}頭、表は{len(rows)}頭')
    limit = (datetime.strptime(today, '%Y-%m-%d') - timedelta(days=KEEP_DAYS)).strftime('%Y-%m-%d')
    dropped = [k for k in data['counts'] if k < limit] + [k for k in data['horses'] if k < limit]
    data['counts'] = {k: v for k, v in sorted(data['counts'].items(), reverse=True) if k >= limit}
    data['horses'] = {k: v for k, v in sorted(data['horses'].items(), reverse=True) if k >= limit}
    changed = bool(new_days) or bool(dropped)
    return data, changed, {'new_days': new_days, 'log': log, 'listed': len(days)}


def write(data):
    data['updated'] = now_jst().isoformat(timespec='seconds')
    tmp = OUT + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as fp:
        fp.write('{"updated":%s,\n"counts":%s,\n"horses":{\n' % (json.dumps(data['updated']), json.dumps(data['counts'], separators=(',', ':'))))
        fp.write(',\n'.join('%s:%s' % (json.dumps(k), json.dumps(v, ensure_ascii=False, separators=(',', ':'))) for k, v in data['horses'].items()))
        fp.write('}}\n')
    with open(tmp, encoding='utf-8') as fp:
        json.load(fp)   # 書いたものが JSON として読めることを確かめる
    os.replace(tmp, OUT)


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
    code, info, changed, data = 0, {'new_days': [], 'log': [], 'listed': 0}, False, None
    try:
        data, changed, info = run(f)
        if changed:
            write(data)
        result = f'抹消日 {info["listed"]}日分が載っていて、{len(info["new_days"])}日分を新しく読んだ' + ('（retired.json を更新）' if changed else '（変更なし）')
    except FormatError as e:
        code, result = 1, f'形式が読めない: {e}'
    except RuntimeError as e:   # Fetcher が3回取り直しても読めなかった
        code, result = 1, f'通信エラー: {e}'
    for line in info['log']:
        print(line)
    print(f'{result}／リクエスト {f.count} 回')
    print(f'::notice title=登録抹消の取得::{result}／リクエスト {f.count} 回' + ''.join(f'／{d} {n}頭' for d, n in info['new_days']), flush=True)
    summary(['## 登録抹消の取得', '', f'- 結果: {result}', f'- リクエスト: {f.count} 回',
             *(f'- {d}: {n}頭' for d, n in info['new_days']),
             *(f'- 保存している頭数: {sum(map(len, data["horses"].values()))}頭' for _ in [0] if data), *(f'- {l}' for l in info['log'])])
    return code


if __name__ == '__main__':
    sys.exit(main())
