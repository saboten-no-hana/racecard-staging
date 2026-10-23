#!/usr/bin/env python3
"""勝負服の見本 SVG（silks/examples/、Wikimedia Commons の CC0 画像）から、
表示されている図形だけを取り出して silks-shapes.js を作る。

見本は Wikipedia「勝負服 (競馬)」の Example_of_Horse_Racing_Colours_of_Japan_01〜22.svg。
どれも同じ形の勝負服で、レイヤーは次のとおり:
  baselayer : 袖口（rect）、裾の縁（use4506-00）、胴と袖のシルエット全体（label=body）、襟（label=neck）
  pattern   : 柄（#e60033 の赤。縦縞の袖などに白 #ffffff の図形もある）、ボタン（ellipse）、輪郭（label=outline）
見本では胴と袖の境目は脇の下から下にしかなく（胴の脇線は x=264 / 736、脇の下 y=447）、柄も胴と袖が
一緒に描かれている。描画時に胴の範囲（index.html の BODY_CLIP）で切り抜いて胴の柄・袖の柄に分ける。

使い方: python3 tools/extract_silks.py   （silks/examples/ を読み、silks-shapes.js を書く）
"""
import json, math, os, re, sys
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'silks', 'examples')
OUT = os.path.join(ROOT, 'silks-shapes.js')
NS = '{http://www.w3.org/2000/svg}'
INK = '{http://www.inkscape.org/namespaces/inkscape}'
FILE = 'Example_of_Horse_Racing_Colours_of_Japan_{:02d}.svg'

# 見本の番号 → 柄のキー（index.html の BODY_PATTERNS / SLEEVE_PATTERNS と同じ）
PATTERNS = {
    1: 'wa1', 2: 'wa2', 3: 'wa3', 4: 'yamagatawa1', 5: 'yamagata', 6: 'yamagata3', 7: 'hishiyamagata',
    8: 'tasuki', 9: 'jujitasuki', 10: 'kyoshi', 11: 'tate', 12: 'check', 13: 'obi', 14: 'yamagataobi',
    15: 'dots', 16: 'janome', 17: 'zenigata', 18: 'stars', 19: 'igeta', 20: 'diamond', 21: 'genroku', 22: 'uroko',
}

# ---------------------------------------------------------------- transform
def mul(a, b):
    return [a[0]*b[0]+a[2]*b[1], a[1]*b[0]+a[3]*b[1], a[0]*b[2]+a[2]*b[3], a[1]*b[2]+a[3]*b[3],
            a[0]*b[4]+a[2]*b[5]+a[4], a[1]*b[4]+a[3]*b[5]+a[5]]

def parse_tr(s):
    m = [1, 0, 0, 1, 0, 0]
    for name, args in re.findall(r'(\w+)\s*\(([^)]*)\)', s or ''):
        v = [float(x) for x in re.split(r'[\s,]+', args.strip()) if x]
        if name == 'translate':
            t = [1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0]
        elif name == 'scale':
            t = [v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0]
        elif name == 'rotate':
            a = math.radians(v[0]); c, s_ = math.cos(a), math.sin(a)
            t = [c, s_, -s_, c, 0, 0]
            if len(v) == 3:
                t = mul(mul([1, 0, 0, 1, v[1], v[2]], t), [1, 0, 0, 1, -v[1], -v[2]])
        elif name == 'matrix':
            t = v
        else:
            raise SystemExit('未対応の transform: ' + name)
        m = mul(m, t)
    return m

def apply(m, x, y):
    return m[0]*x + m[2]*y + m[4], m[1]*x + m[3]*y + m[5]

# ---------------------------------------------------------------- shapes
def num(x):
    s = ('%.2f' % x).rstrip('0').rstrip('.')
    return '0' if s in ('-0', '') else s

def compact(d):
    """パスの数値を小数2桁に丸める（コマンドと数値をトークンに分けて空白でつなぎ直す）"""
    toks = re.findall(r'[A-Za-z]|-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', d)
    return ' '.join(t if t.isalpha() else num(float(t)) for t in toks)

def shape_d(e):
    tag = e.tag.replace(NS, '')
    f = lambda k, dv=0.0: float(e.get(k, dv))
    if tag == 'path':
        return e.get('d')
    if tag == 'rect':
        x, y, w, h = f('x'), f('y'), f('width'), f('height')
        return f'M{x} {y}H{x+w}V{y+h}H{x}Z'
    if tag in ('ellipse', 'circle'):
        cx, cy = f('cx'), f('cy')
        rx = f('r') if tag == 'circle' else f('rx'); ry = f('r') if tag == 'circle' else f('ry')
        return f'M{cx-rx} {cy}A{rx} {ry} 0 1 0 {cx+rx} {cy}A{rx} {ry} 0 1 0 {cx-rx} {cy}Z'
    return None

def style(e, k):
    m = re.search(k + r':([^;]+)', e.get('style', ''))
    return (m.group(1) if m else e.get(k) or '').strip()

def hidden(e):
    return 'display:none' in e.get('style', '').replace(' ', '') or e.get('display') == 'none'

def collect(e, m, out, path):
    """表示されている図形を {d, m, fill, label, path} で集める（m は SVG 座標系への変換行列）"""
    for c in e:
        if not c.tag.startswith(NS) or hidden(c):
            continue
        tag = c.tag.replace(NS, '')
        if tag in ('metadata', 'defs', 'title', 'desc', 'flowRoot', 'text'):
            continue
        cm = mul(m, parse_tr(c.get('transform')))
        lab = c.get(INK + 'label') or ''
        if tag == 'g':
            collect(c, cm, out, path + [lab])
            continue
        d = shape_d(c)
        if d is None:
            raise SystemExit(f'未対応の要素: {tag} {c.get("id")}')
        if c.get('clip-path') or c.get('mask'):
            raise SystemExit(f'clip-path / mask は未対応: {c.get("id")}')
        out.append({'d': d, 'm': cm, 'fill': style(c, 'fill'), 'stroke': style(c, 'stroke'),
                    'label': lab, 'id': c.get('id'), 'tag': tag, 'path': path})

def layers(fn):
    root = ET.parse(fn).getroot()
    res = {}
    for g in root:
        if g.tag == NS + 'g' and not hidden(g):
            items = []
            collect(g, parse_tr(g.get('transform')), items, [])
            res[g.get(INK + 'label')] = items
    return res

def bbox(items):
    from svgpathtools import parse_path
    xs, ys = [], []
    for it in items:
        x0, x1, y0, y1 = parse_path(it['d']).bbox()
        for x, y in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
            X, Y = apply(it['m'], x, y); xs.append(X); ys.append(Y)
    return min(xs), min(ys), max(xs), max(ys)

def is_white(f):
    return f.lower() in ('#ffffff', '#fff', 'white')

def main():
    first = layers(os.path.join(SRC, FILE.format(1)))
    base, pat1 = first['baselayer'], first['pattern']
    cuffs = [i for i in base if i['tag'] == 'rect' or i['id'].startswith('rect')]
    hem = [i for i in base if i['id'] == 'use4506-00']
    garment = [i for i in base if i['label'] == 'body']
    neck = [i for i in base if 'neck' in i['path']]
    outline = [i for i in pat1 if i['label'] == 'outline']
    buttons = [i for i in pat1 if i['tag'] == 'ellipse']
    if not (cuffs and hem and garment and neck and outline and buttons):
        raise SystemExit('見本01 の土台の図形が見つかりません')

    # 全体を 0〜1000 の正方形に収める（横は中央寄せ）
    x0, y0, x1, y1 = bbox(garment + hem + cuffs + neck)
    k = 1000 / max(x1 - x0, y1 - y0)
    ox = -x0 * k + (1000 - (x1 - x0) * k) / 2
    oy = -y0 * k + (1000 - (y1 - y0) * k) / 2
    norm = [k, 0, 0, k, ox, oy]

    def pack(items, with_fill=False):
        out = []
        for it in items:
            m = mul(norm, it['m'])
            e = {'d': compact(it['d']), 'm': [round(v, 5) for v in m]}
            if with_fill:
                e['w'] = 1 if is_white(it['fill']) else 0
                e['b'] = [round(v) for v in bbox([dict(it, m=m)])]
            out.append(e)
        return out

    def motif(items):
        """散らし柄の1個分（いちばん上・左の図形と、その近くの図形）"""
        cen = lambda e: ((e['b'][0]+e['b'][2])/2, (e['b'][1]+e['b'][3])/2)
        first = min(range(len(items)), key=lambda i: (round(cen(items[i])[1] / 40), cen(items[i])[0]))
        fx, fy = cen(items[first])
        idx = [i for i, e in enumerate(items) if math.hypot(cen(e)[0]-fx, cen(e)[1]-fy) < 60]
        b = [min(items[i]['b'][0] for i in idx), min(items[i]['b'][1] for i in idx),
             max(items[i]['b'][2] for i in idx), max(items[i]['b'][3] for i in idx)]
        return {'i': idx, 'c': [round((b[0]+b[2])/2), round((b[1]+b[3])/2)], 'size': max(b[2]-b[0], b[3]-b[1])}

    shapes = {
        'source': 'Wikimedia Commons「Example of Horse Racing Colours of Japan 01〜22」（CC0）を tools/extract_silks.py で変換',
        'cuffs': pack(cuffs), 'hem': pack(hem), 'garment': pack(garment),
        'neck': [dict(e, dark=1 if style(it, 'fill').lower() in ('#000000', '#000') else 0)
                 for e, it in zip(pack(neck), neck)],
        'outline': pack(outline), 'buttons': pack(buttons), 'patterns': {}, 'motifs': {},
    }
    for n, key in PATTERNS.items():
        L = layers(os.path.join(SRC, FILE.format(n)))
        items = [i for i in L['pattern'] if i['label'] != 'outline' and i['tag'] != 'ellipse']
        bad = [i['fill'] for i in items if not (is_white(i['fill']) or i['fill'].lower() == '#e60033')]
        if bad:
            raise SystemExit(f'{n:02d}: 想定外の色 {bad}')
        shapes['patterns'][key] = pack(items, with_fill=True)
        extra = ''
        if key in ('dots', 'janome', 'zenigata', 'stars', 'igeta'):
            shapes['motifs'][key] = motif(shapes['patterns'][key]); extra = f"  1個分 {shapes['motifs'][key]}"
        print(f'{n:02d} {key:14s} 図形 {len(items):3d}{extra}')

    js = ('/* 勝負服の形（自動生成。手で編集しない）\n'
          '   出典: Wikimedia Commons「Example of Horse Racing Colours of Japan 01〜22」（Wikipedia「勝負服 (競馬)」の標示の参考画像、CC0）\n'
          '   生成: python3 tools/extract_silks.py\n'
          '   座標: 0〜1000 の正方形。各図形は d（SVG パス）と m（変換行列 a,b,c,d,e,f）。柄の w=1 は地色で塗る図形、b は外接枠。\n'
          '   motifs は袖に置く散らし柄の1個分（patterns の何番目の図形か・中心・大きさ） */\n'
          'window.SILK_SHAPES = ' + json.dumps(shapes, ensure_ascii=False, separators=(',', ':')) + ';\n')
    open(OUT, 'w', encoding='utf-8').write(js)
    print('書き出し:', os.path.relpath(OUT, ROOT), f'{len(js)//1024} KB')

if __name__ == '__main__':
    main()
