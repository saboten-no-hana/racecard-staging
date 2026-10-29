"""OGP 画像（og.png、1200×630）を作り直す

左に説明文、右に「縦長」の出走カード、その左奥に作成ページ（スマホ幅のタブと「今週の出走馬から選ぶ」）を重ねた
1200×630 の画像を作る。カードとページは画面と同じ描画処理で、架空の馬名を使う
（X のカードは横長 1.91:1 で表示されるため、縦長のカードを丸ごと見せる形にしている）。

使い方（リポジトリ直下で）:
    pip install playwright && python3 -m playwright install chromium
    python3 tools/make_og.py            # og.png を上書き
    python3 tools/make_og.py out.png    # 別のファイルに書き出す

- 画像内の文字は同梱の IPAexゴシック。勝負服はクラブの CC0 画像（silks/）
- data/races.json は読まず、下の架空の出馬表（RACES）を返す。日時は 2026-10-23（金）12:00 に固定（枠順確定後の見た目）
- 作成ページは、折りたたみ欄（★の引き継ぎ・馬名をまとめて★）・「★だけ表示」・下の説明文を隠してリストが見えるようにしている
- 画面の描画を変えたら、これを実行して og.png も作り直し、index.html の og:image の ?v= の番号を上げる
"""
import base64, functools, http.server, json, os, sys, threading

from playwright.sync_api import sync_playwright

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, 'og.png')
NOW = '2026-10-23T12:00:00+09:00'

# 架空の馬（クラブは実在、勝負服は CC0 画像）。races.json と同じ形（raceName は格なし、grade・cls 別）
RACE_HORSES = [
    dict(name='ミホンノウマ', clubId='silk', date='2026-10-24', venue='東京', r=9, time='14:25', raceName='〇〇特別', grade='', cls='2勝クラス',
         surface='芝', dist=1800, sexAge='牡3', weight='56.0', waku='2', umaban='3'),
    dict(name='サンプルホース', clubId='carrot', date='2026-10-24', venue='東京', r=11, time='15:45', raceName='〇〇ステークス', grade='GII', cls='オープン',
         surface='芝', dist=1800, sexAge='牝4', weight='55.0', waku='4', umaban='7'),
    dict(name='ダミーステップ', clubId='normandy', date='2026-10-25', venue='京都', r=10, time='15:05', raceName='〇〇ステークス', grade='L', cls='オープン',
         surface='芝', dist=2000, sexAge='牡5', weight='57.0', waku='7', umaban='15'),
    dict(name='カセツノホシ', clubId='lion', date='2026-10-25', venue='東京', r=8, time='13:50', raceName='3歳以上1勝クラス', grade='', cls='1勝クラス',
         surface='ダ', dist=1800, sexAge='牝3', weight='55.0', waku='5', umaban='9'),
    dict(name='ホシノカケラ', clubId='sunday', date='2026-10-24', venue='東京', r=5, time='12:20', raceName='2歳新馬', grade='', cls='新馬',
         surface='芝', dist=1600, sexAge='牝2', weight='55.0', waku='1', umaban='2'),
    dict(name='ミドリノカゼ', clubId='shadai', date='2026-10-24', venue='京都', r=6, time='12:50', raceName='3歳以上1勝クラス', grade='', cls='1勝クラス',
         surface='ダ', dist=1400, sexAge='牡3', weight='57.0', waku='6', umaban='11'),
    dict(name='アサギリノオカ', clubId='g1', date='2026-10-24', venue='新潟', r=10, time='14:50', raceName='〇〇特別', grade='', cls='2勝クラス',
         surface='芝', dist=1000, sexAge='牝4', weight='55.0', waku='3', umaban='5'),
    dict(name='ハルカナミチ', clubId='tokyo', date='2026-10-25', venue='東京', r=4, time='11:35', raceName='2歳未勝利', grade='', cls='未勝利',
         surface='芝', dist=2000, sexAge='牡2', weight='56.0', waku='8', umaban='16'),
]
for i, x in enumerate(RACE_HORSES):
    x.update(horseId=f'20221090{i:02d}', jockey='騎手名', status='')
    x['key'] = f"{x['date']}|{x['venue']}|{x['r']}|{x['horseId']}"
RACES = {'source': 'JRAホームページ 出馬表', 'updated': '2026-10-23T10:21+09:00',
         'days': [{'date': '2026-10-24', 'venues': ['東京', '京都', '新潟']}, {'date': '2026-10-25', 'venues': ['東京', '京都', '新潟']}],
         'horses': sorted(RACE_HORSES, key=lambda x: (x['date'], x['r']))}


def label(x):  # index.html の raceLabel() と同じ
    if x['grade']:
        return f"{x['raceName']}（{x['grade']}）"
    c = x['cls']
    if not c or c in ('新馬', '未勝利') or c in x['raceName']:
        return x['raceName']
    return f"{x['raceName']}（{'OP' if c == 'オープン' else c}）"


# カードに載せる4頭（口取りの表示も見せる）と、★を付けたが未追加の2頭（★のまとめて追加のバナー用）
KUCHI = {'ミホンノウマ': 'none', 'サンプルホース': 'win', 'ダミーステップ': 'wait', 'カセツノホシ': 'none'}
CARD = [x for x in RACE_HORSES if x['name'] in KUCHI]
STATE = {
    'settings': {'title': '今週の出走予定', 'post': None, 'handle': '@your_account', 'theme': 'turf', 'size': '4:5',
                 'showKuchi': True, 'order': 'venue', 'showCount': True, 'showAgeWeight': True, 'skipPostGuide': True},
    'horses': [dict(id=f'og{i}', horseId=x['horseId'], name=x['name'], clubId=x['clubId'], ownerLabel='', date=x['date'], venue=x['venue'],
                    r=str(x['r']), time=x['time'], raceName=label(x), surface=x['surface'], dist=str(x['dist']), jockey=x['jockey'],
                    sexAge=x['sexAge'], weight=x['weight'], waku=x['waku'], umaban=x['umaban'], status='', kuchi=KUCHI[x['name']],
                    photo='', customSilks=None) for i, x in enumerate(CARD)],
    'myHorses': [x['horseId'] for x in CARD] + [x['horseId'] for x in RACE_HORSES if x['name'] in ('ホシノカケラ', 'ハルカナミチ')],
    'myNames': {x['horseId']: x['name'] for x in RACE_HORSES},
}

# 背景（「芝」のデザイン）→ 作成ページ（左奥）→ カード（右・手前）→ 左の説明文。文字は IPAexゴシック
COMPOSE = r"""
(shot) => new Promise(res => { const im = new Image(); im.onload = () => {
  const card = document.getElementById('cv');
  const W = 1200, H = 630, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
  const c = cv.getContext('2d'), IPA = '"IPAexGothic",sans-serif';
  c.fillStyle = '#123d2b'; c.fillRect(0, 0, W, H);
  c.save(); c.translate(W/2, H/2); c.rotate(-0.38); const bw = W*.085, D = Math.hypot(W, H);
  c.fillStyle = 'rgba(255,255,255,0.035)'; for (let i = -20; i < 20; i += 2) c.fillRect(i*bw, -D, bw, D*2); c.restore();
  const g = c.createLinearGradient(0, H*.45, 0, H); g.addColorStop(0, 'rgba(0,0,0,0)'); g.addColorStop(1, '#0b2a1d'); c.fillStyle = g; c.fillRect(0, 0, W, H);
  const panel = (img, sh, x, y, w, h, r) => {  /* 画像の上から sh px 分を、角丸・影・縁つきで置く */
    const rect = () => { c.beginPath(); c.roundRect(x, y, w, h, r); };
    c.save(); c.shadowColor = 'rgba(0,0,0,0.5)'; c.shadowBlur = 30; c.shadowOffsetY = 10; rect(); c.fillStyle = '#0b2a1d'; c.fill(); c.restore();
    c.save(); rect(); c.clip(); c.imageSmoothingQuality = 'high'; c.drawImage(img, 0, 0, img.width, sh, x, y, w, h); c.restore();
    c.save(); rect(); c.strokeStyle = 'rgba(255,255,255,0.22)'; c.lineWidth = 2; c.stroke(); c.restore();
  };
  const ch = H - 80, cw = Math.round(card.width * ch / card.height), cx = W - 40 - cw, cy = 40;
  const pw = 250, ph = H - 120, px = cx - pw + 60, py = 76;
  panel(im, Math.min(Math.round(im.width * ph / pw), im.height), px, py, pw, ph, 18);
  panel(card, card.height, cx, cy, cw, ch, 14);
  const x = 56, maxW = px - x - 32;
  const fit = (t, w, size, mw = maxW) => { let s = size; do { c.font = `${w} ${s}px ${IPA}`; } while (c.measureText(t).width > mw && --s > 10); return s; };
  c.textBaseline = 'alphabetic';
  let y = 100;
  c.fillStyle = '#e2bd5c'; fit('出資馬の出走告知画像をカンタン生成', 700, 22); c.fillText('出資馬の出走告知画像をカンタン生成', x, y);
  y += 26; c.fillStyle = '#f4efe1';
  const s1 = fit('カードメーカー', 700, 70); c.font = `700 ${s1}px ${IPA}`; c.fillText('出資馬出走', x, y + s1);
  y += s1 * 1.18; c.fillText('カードメーカー', x, y + s1);
  y += s1 + 28; c.fillStyle = '#e2bd5c'; c.fillRect(x, y, 70, 4); c.fillStyle = 'rgba(255,255,255,0.10)'; c.fillRect(x + 80, y + 1, maxW - 80, 2);
  const lines = ['一口クラブ馬を自動でリストアップ', 'レース名・騎手名・馬番（決定後）なども自動表示', '背景などのカスタムも可能', 'レース終了後には出走結果のカードも生成可能', '複数クラブ対応・無料・登録不要'];
  const ls = Math.min(...lines.map(t => fit(t, 700, 25, maxW - 22)));  /* 箇条書きは同じ大きさにそろえる */
  y += Math.round(((H - 56 - 22 - y) - ls * 1.75 * (lines.length - 1)) / 2 + ls * .4);  /* 区切り線と URL の間の中央に */
  for (const t of lines) { c.fillStyle = '#e2bd5c'; c.beginPath(); c.arc(x + 6, y - ls*.36, 4.5, 0, Math.PI*2); c.fill();
    c.fillStyle = '#f4efe1'; c.font = `700 ${ls}px ${IPA}`; c.fillText(t, x + 22, y); y += ls * 1.75; }
  c.fillStyle = '#b7c8b6'; fit('saboten-no-hana.github.io/racecard', 700, 22); c.fillText('saboten-no-hana.github.io/racecard', x, H - 56);
  res(cv.toDataURL('image/png'));
}; im.src = shot; })
"""


def main():
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Quiet, directory=ROOT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{srv.server_address[1]}/index.html'
    body = json.dumps(RACES, ensure_ascii=False)
    init = 'localStorage.setItem("racecard.v2", %s)' % json.dumps(json.dumps(STATE, ensure_ascii=False))
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()

            def open_page(vp, scale):
                pg = b.new_page(viewport=vp, device_scale_factor=scale)
                pg.clock.install(time=NOW)
                pg.route('**/data/races.json*', lambda r: r.fulfill(status=200, body=body, content_type='application/json'))
                pg.route('**/fonts.googleapis.com/**', lambda r: r.abort())
                pg.route('**/fonts.gstatic.com/**', lambda r: r.abort())
                pg.add_init_script(init)
                pg.goto(url)
                pg.wait_for_function("document.getElementById('out').src.startsWith('blob:')")
                pg.wait_for_function("document.fonts.check('40px IPAexGothic', '出資馬')")
                pg.wait_for_timeout(1000)  # 勝負服画像の読み込み後の描き直しを待つ
                return pg

            mob = open_page({'width': 390, 'height': 900}, 2)
            mob.add_style_tag(content='#picker details,#picker>.hint,#picker .checks{display:none!important}')
            mob.wait_for_timeout(200)
            # ページ上部のタブ（出走カード｜結果カード）から「今週の出走馬から選ぶ」の下端までを切り出す（左右と上に少し余白）
            box = mob.evaluate("""() => { const t = document.querySelector('nav.tabs').getBoundingClientRect(), p = document.getElementById('picker').getBoundingClientRect();
              return {x: p.left - 8, y: t.top + scrollY - 12, width: p.width + 16, height: p.bottom - t.top + 12}; }""")
            shot = mob.screenshot(clip=box, full_page=True)
            pg = open_page({'width': 1280, 'height': 900}, 1)
            data = pg.evaluate(COMPOSE, 'data:image/png;base64,' + base64.b64encode(shot).decode())
            b.close()
    finally:
        srv.shutdown()
    with open(OUT, 'wb') as f:
        f.write(base64.b64decode(data.split(',', 1)[1]))
    print('書き出した:', OUT)


if __name__ == '__main__':
    main()
