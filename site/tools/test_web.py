"""画面側のファイルの簡単なテスト（node が必要。なければ飛ばす）
- index.html の中のスクリプト・qr.js・sw.js・clubs.js・card-core.js の構文チェック
- index.html が card-core.js から読み込む名前が、card-core.js にすべてあるか
- qr.js で作った QR コードを zxing-cpp で読み取れるか（zxing-cpp・numpy がなければ飛ばす）
"""
import json, os, re, shutil, subprocess, tempfile, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NODE = shutil.which('node')


@unittest.skipUnless(NODE, 'node がない')
class TestWeb(unittest.TestCase):
    def check(self, src, name):
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(src)
        r = subprocess.run([NODE, '--check', f.name], capture_output=True, text=True)
        os.unlink(f.name)
        self.assertEqual(r.returncode, 0, f'{name}: {r.stderr}')

    def test_syntax(self):
        html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
        scripts = re.findall(r'<script>(.*?)</script>', html, re.S)
        self.assertTrue(scripts)
        for i, s in enumerate(scripts):
            self.check(s, f'index.html の <script> {i + 1}')
        for n in ('qr.js', 'sw.js', 'clubs.js', 'card-core.js'):
            self.check(open(os.path.join(ROOT, n), encoding='utf-8').read(), n)
        json.load(open(os.path.join(ROOT, 'manifest.webmanifest'), encoding='utf-8'))

    def test_core_exports(self):
        """index.html の const { … } = window.RCCore の名前が、card-core.js の window.RCCore にすべてあるか（読み込んで確かめる）"""
        html = open(os.path.join(ROOT, 'index.html'), encoding='utf-8').read()
        self.assertIn('<script src="card-core.js"></script>', html)
        self.assertLess(html.index('src="clubs.js"'), html.index('src="card-core.js"'))
        self.assertLess(html.index('src="silks-shapes.js"'), html.index('src="card-core.js"'))
        m = re.search(r'const \{([^}]*)\} = window\.RCCore;', html)
        self.assertTrue(m, 'index.html に window.RCCore の読み込みがない')
        need = [n.strip() for n in m.group(1).split(',') if n.strip()]
        js = ("global.window={};class P{addPath(){}};global.Path2D=P;global.DOMMatrix=class{};global.Image=class{};"
              "require(%r);require(%r);require(%r);console.log(JSON.stringify(Object.keys(window.RCCore)))") % tuple(
                  os.path.join(ROOT, n) for n in ('silks-shapes.js', 'clubs.js', 'card-core.js'))
        have = set(json.loads(subprocess.run([NODE, '-e', js], capture_output=True, text=True, check=True).stdout))
        self.assertEqual([n for n in need if n not in have], [], 'card-core.js にない名前')

    def test_qr_roundtrip(self):
        try:
            import numpy as np
            import zxingcpp
        except ImportError:
            self.skipTest('zxing-cpp がない')
        base = 'https://saboten-no-hana.github.io/racecard/#star=RC3%3A'
        texts = [base + 'xfbail', base + ('xfbail_1h012k2c072b14.' * 12), base + ('xfbail_1h012k2c072b14.' * 30), '日本語 ファーヴェント']
        js = ("global.window={};require(%r);const t=JSON.parse(require('fs').readFileSync(0,'utf8'));"
              "console.log(JSON.stringify(t.map(s=>{const q=window.makeQR(s);const r=[];"
              "for(let y=0;y<q.size;y++){let l='';for(let x=0;x<q.size;x++)l+=q.dark(x,y)?'1':'0';r.push(l);}return r;})))") % os.path.join(ROOT, 'qr.js')
        out = subprocess.run([NODE, '-e', js], input=json.dumps(texts), capture_output=True, text=True, check=True).stdout
        for text, rows in zip(texts, json.loads(out)):
            m = np.array([[c == '1' for c in r] for r in rows], dtype=np.uint8)
            img = np.kron(np.pad((1 - m) * 255, 4, constant_values=255).astype(np.uint8), np.ones((6, 6), dtype=np.uint8))
            res = zxingcpp.read_barcodes(img)
            self.assertTrue(res and res[0].text == text, f'読み取れなかった: {text[:40]}…（{len(rows)}×{len(rows)}）')


if __name__ == '__main__':
    unittest.main()
