"""テスト環境（racecard-staging）用にページを組み立てる。

site/（本番 racecard のあるコミットの中身をそのまま写したもの）を out/ にコピーし、
本番と混ざらないように次だけを書き換える。本番のコードは一切変えない。

- 保存データ（localStorage）のキー: 'racecard.…' → 'racecard-stg.…'
  （本番とテスト環境は同じドメイン saboten-no-hana.github.io なので、そのままだと★などを共有してしまう）
- Service Worker のキャッシュ名: racecard-… → racecard-stg-…。古いキャッシュの削除もテスト環境の分だけにする
- 全ページ: noindex、タイトルに【テスト】、上部に赤い帯
- manifest: ホーム画面に追加した時に本番と見分けられる名前
- data/races.json: 指定があれば本番の最新に差し替える（JRA にはアクセスしない）
- data/results.json: 本番の最新があれば差し替え、なければ stage/sample/results.json（実際の結果。10/25 日曜の全場・クラブ馬96頭。結果カードの確認用）

書き換えが効かなかった時（本番のコードの形が変わった時）は失敗にする。
使い方: python3 stage/build.py site _site [--races races.json] [--results results.json]
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

PROD_URL = 'https://saboten-no-hana.github.io/racecard/'
KEY_RE = re.compile(r"""(['"`])racecard\.""")


def fail(msg):
    print('組み立てに失敗: ' + msg)
    sys.exit(1)


def sub_once(text, old, new, where):
    if old not in text:
        fail(f'{where} に「{old}」が見つからない（本番のコードの形が変わった？ stage/build.py を直す）')
    return text.replace(old, new)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('out')
    ap.add_argument('--races')
    ap.add_argument('--results')
    a = ap.parse_args()
    src, out = Path(a.src), Path(a.out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out, ignore=shutil.ignore_patterns('.github', '.git'))

    source = (src / 'STAGING_SOURCE.txt').read_text(encoding='utf-8').strip() if (src / 'STAGING_SOURCE.txt').exists() else '不明'
    commit = source.split(' ')[0]

    # 1. 保存データのキー
    keys = 0
    for p in list(out.rglob('*.html')) + list(out.rglob('*.js')):
        if p.name == 'sw.js' or 'tools' in p.relative_to(out).parts:
            continue
        t = p.read_text(encoding='utf-8')
        t2, n = KEY_RE.subn(r'\1racecard-stg.', t)
        if n:
            p.write_text(t2, encoding='utf-8')
            keys += n
        if re.search(r"""['"`]racecard\.(v\d|pclub|result)""", t2):
            fail(f'{p} に本番の保存キーが残っている')
    if keys == 0:
        fail('保存キー racecard.… が1つも見つからない')

    # 2. Service Worker
    sw = out / 'sw.js'
    t = sw.read_text(encoding='utf-8')
    t = sub_once(t, "'racecard-static-", "'racecard-stg-static-", 'sw.js')
    t = sub_once(t, "'racecard-pages-", "'racecard-stg-pages-", 'sw.js')
    t = sub_once(t, 'ks.filter(k => k !== STATIC && k !== PAGES)',
                 "ks.filter(k => k.startsWith('racecard-stg-') && k !== STATIC && k !== PAGES)", 'sw.js')
    sw.write_text(t, encoding='utf-8')

    # 3. 全ページ: noindex・タイトル・帯
    banner = ('<div id="stg-banner" style="background:#b00020;color:#fff;font:13px/1.5 sans-serif;'
              'padding:6px 12px;text-align:center;word-break:break-all">'
              f'テスト環境です（{commit}）。本番は <a href="{PROD_URL}" style="color:#fff">こちら</a>'
              '。★などの保存データは本番と別です。</div>')
    pages = 0
    for p in out.rglob('*.html'):
        if 'tools' in p.relative_to(out).parts:
            continue
        t = p.read_text(encoding='utf-8')
        t = sub_once(t, '<head>', '<head>\n<meta name="robots" content="noindex,nofollow">', str(p))
        t = re.sub(r'<title>', '<title>【テスト】', t, count=1)
        t, n = re.subn(r'(<body[^>]*>)', r'\1' + banner.replace('\\', '\\\\'), t, count=1)
        if not n:
            fail(f'{p} に <body> がない')
        p.write_text(t, encoding='utf-8')
        pages += 1

    # 4. manifest
    mf = out / 'manifest.webmanifest'
    if mf.exists():
        m = json.loads(mf.read_text(encoding='utf-8'))
        m['name'] = '【テスト】' + m.get('name', '')
        m['short_name'] = '出走カード(テスト)'
        mf.write_text(json.dumps(m, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    # 5. 出馬表
    note = '反映したコミットのもの'
    if a.races and Path(a.races).is_file() and Path(a.races).stat().st_size > 0:
        try:
            json.loads(Path(a.races).read_text(encoding='utf-8'))
            shutil.copyfile(a.races, out / 'data' / 'races.json')
            note = '本番の最新'
        except ValueError:
            note = '本番の最新が読めなかったので、反映したコミットのもの'

    # 6. 結果（結果カード用）
    rnote = 'なし'
    def okjson(f):
        try:
            return f and Path(f).is_file() and Path(f).stat().st_size > 0 and json.loads(Path(f).read_text(encoding='utf-8'))
        except ValueError:
            return None
    sample = Path(__file__).parent / 'sample' / 'results.json'
    if okjson(a.results):
        shutil.copyfile(a.results, out / 'data' / 'results.json'); rnote = '本番の最新'
    elif not (out / 'data' / 'results.json').exists() and sample.exists():
        shutil.copyfile(sample, out / 'data' / 'results.json'); rnote = '見本（stage/sample）'
    elif (out / 'data' / 'results.json').exists():
        rnote = '反映したコミットのもの'

    (out / '.nojekyll').touch()
    print(f'元のコミット: {source}')
    print(f'保存キーの書き換え {keys} か所、ページ {pages} 件、races.json は{note}、results.json は{rnote}')


if __name__ == '__main__':
    main()
