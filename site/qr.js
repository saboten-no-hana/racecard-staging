/* QRコードの生成（★の引き継ぎリンク用、2026-10-19〜）。外部ライブラリを使わずに書いたもの。
   JIS X 0510 / ISO/IEC 18004 の手順どおり: バイトモード（UTF-8）、型番 1〜40 を自動選択、
   誤り訂正は入る範囲で L→M→Q→H と上げる、マスクは減点の一番少ないもの。
   window.makeQR(text) → {size, dark(x,y)}（入りきらなければ null） */
(function(){
  'use strict';
  // 誤り訂正レベルの順 L, M, Q, H（形式情報の2ビットは L=01, M=00, Q=11, H=10）
  const FORMAT = [1, 0, 3, 2];
  // 1ブロックあたりの誤り訂正コード語数（[レベル][型番]、0番は未使用）
  const ECC = [
    [0,7,10,15,20,26,18,20,24,30,18,20,24,26,30,22,24,28,30,28,28,28,28,30,30,26,28,30,30,30,30,30,30,30,30,30,30,30,30,30,30],
    [0,10,16,26,18,24,16,18,22,22,26,30,22,22,24,24,28,28,26,26,26,26,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28,28],
    [0,13,22,18,26,18,24,18,22,20,24,28,26,24,20,30,24,28,28,26,30,28,30,30,30,30,28,30,30,30,30,30,30,30,30,30,30,30,30,30,30],
    [0,17,28,22,16,22,28,26,26,24,28,24,28,22,24,24,30,28,28,26,28,30,24,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30,30]];
  // 誤り訂正ブロック数（[レベル][型番]）
  const BLOCKS = [
    [0,1,1,1,1,1,2,2,2,2,4,4,4,4,4,6,6,6,6,7,8,8,9,9,10,12,12,12,13,14,15,16,17,18,19,19,20,21,22,24,25],
    [0,1,1,1,2,2,4,4,4,5,5,5,8,9,9,10,10,11,13,14,16,17,17,18,20,21,23,25,26,28,29,31,33,35,37,38,40,43,45,47,49],
    [0,1,1,2,2,4,4,6,6,8,8,8,10,12,16,12,17,16,18,21,20,23,23,25,27,29,34,34,35,38,40,43,45,48,51,53,56,59,62,65,68],
    [0,1,1,2,4,4,4,5,6,8,8,11,11,16,16,18,16,19,21,25,25,25,34,30,32,35,37,40,42,45,48,51,54,57,60,63,66,70,74,77,81]];

  // データを置けるモジュール数（機能パターンを除く）
  function rawModules(v){
    let n = (16 * v + 128) * v + 64;
    if (v >= 2){ const a = Math.floor(v / 7) + 2; n -= (25 * a - 10) * a - 55; if (v >= 7) n -= 36; }
    return n;
  }
  const dataCodewords = (v, e) => Math.floor(rawModules(v) / 8) - ECC[e][v] * BLOCKS[e][v];

  // 位置合わせパターンの中心座標
  function alignPositions(v){
    if (v === 1) return [];
    const n = Math.floor(v / 7) + 2, size = v * 4 + 17;
    const step = v === 32 ? 26 : Math.ceil((v * 4 + 4) / (n * 2 - 2)) * 2;
    const out = [6];
    for (let i = 0; i < n - 1; i++) out.splice(1, 0, size - 7 - i * step);
    return out;
  }

  // GF(256)（原始多項式 x^8+x^4+x^3+x^2+1）
  const EXP = new Array(512), LOG = new Array(256);
  for (let i = 0, x = 1; i < 255; i++){ EXP[i] = x; LOG[x] = i; x <<= 1; if (x & 0x100) x ^= 0x11D; }
  for (let i = 255; i < 512; i++) EXP[i] = EXP[i - 255];
  const gmul = (a, b) => (a && b) ? EXP[LOG[a] + LOG[b]] : 0;

  // 生成多項式 (x-α^0)(x-α^1)…(x-α^(n-1)) の係数（最高次の 1 を除き、高い次数から）
  function generator(n){
    let g = [1];
    for (let i = 0; i < n; i++){
      const next = new Array(g.length + 1).fill(0);
      for (let j = 0; j < g.length; j++){ next[j] ^= g[j]; next[j + 1] ^= gmul(g[j], EXP[i]); }
      g = next;
    }
    return g.slice(1);
  }
  function rsRemainder(data, gen){
    const r = new Array(gen.length).fill(0);
    for (const b of data){
      const f = b ^ r.shift(); r.push(0);
      for (let i = 0; i < gen.length; i++) r[i] ^= gmul(gen[i], f);
    }
    return r;
  }

  function makeQR(text){
    const bytes = Array.from(new TextEncoder().encode(String(text)));
    // 入る最小の型番（L で探す）
    let v = 0, e = 0;
    for (let t = 1; t <= 40; t++){
      const bits = 4 + (t < 10 ? 8 : 16) + bytes.length * 8;
      if (bits <= dataCodewords(t, 0) * 8){ v = t; break; }
    }
    if (!v) return null;
    const need = 4 + (v < 10 ? 8 : 16) + bytes.length * 8;
    for (let t = 3; t >= 1; t--) if (need <= dataCodewords(v, t) * 8){ e = t; break; }

    // ビット列: モード（0100=バイト）・文字数・データ・終端・埋め草
    const cap = dataCodewords(v, e) * 8, bb = [];
    const put = (val, len) => { for (let i = len - 1; i >= 0; i--) bb.push((val >>> i) & 1); };
    put(4, 4); put(bytes.length, v < 10 ? 8 : 16); bytes.forEach(b => put(b, 8));
    put(0, Math.min(4, cap - bb.length));
    put(0, (8 - bb.length % 8) % 8);
    for (let p = 0xEC; bb.length < cap; p ^= 0xEC ^ 0x11) put(p, 8);
    const data = [];
    for (let i = 0; i < bb.length; i += 8){ let x = 0; for (let j = 0; j < 8; j++) x = (x << 1) | bb[i + j]; data.push(x); }

    // ブロックに分けて誤り訂正を付け、交互に並べる
    const nb = BLOCKS[e][v], el = ECC[e][v], total = Math.floor(rawModules(v) / 8);
    const nShort = nb - total % nb, shortData = Math.floor(total / nb) - el;
    const gen = generator(el), dBlocks = [], eBlocks = [];
    for (let i = 0, k = 0; i < nb; i++){
      const len = shortData + (i < nShort ? 0 : 1), d = data.slice(k, k + len); k += len;
      dBlocks.push(d); eBlocks.push(rsRemainder(d, gen));
    }
    const words = [];
    for (let i = 0; i <= shortData; i++) dBlocks.forEach(d => { if (i < d.length) words.push(d[i]); });
    for (let i = 0; i < el; i++) eBlocks.forEach(r => words.push(r[i]));

    // 機能パターン
    const size = v * 4 + 17;
    const M = Array.from({length: size}, () => new Array(size).fill(false));
    const F = Array.from({length: size}, () => new Array(size).fill(false));
    const fn = (x, y, d) => { M[y][x] = d; F[y][x] = true; };
    for (let i = 0; i < size; i++){ fn(6, i, i % 2 === 0); fn(i, 6, i % 2 === 0); }
    [[3, 3], [size - 4, 3], [3, size - 4]].forEach(([cx, cy]) => {
      for (let dy = -4; dy <= 4; dy++) for (let dx = -4; dx <= 4; dx++){
        const x = cx + dx, y = cy + dy, d = Math.max(Math.abs(dx), Math.abs(dy));
        if (x >= 0 && x < size && y >= 0 && y < size) fn(x, y, d !== 2 && d !== 4);
      }
    });
    const ap = alignPositions(v);
    ap.forEach((ay, i) => ap.forEach((ax, j) => {
      const last = ap.length - 1;
      if ((i === 0 && j === 0) || (i === 0 && j === last) || (i === last && j === 0)) return;
      for (let dy = -2; dy <= 2; dy++) for (let dx = -2; dx <= 2; dx++) fn(ax + dx, ay + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }));
    const drawFormat = mask => {
      const d = (FORMAT[e] << 3) | mask; let r = d;
      for (let i = 0; i < 10; i++) r = (r << 1) ^ ((r >>> 9) * 0x537);
      const bits = ((d << 10) | r) ^ 0x5412, bit = i => ((bits >>> i) & 1) === 1;
      for (let i = 0; i <= 5; i++) fn(8, i, bit(i));
      fn(8, 7, bit(6)); fn(8, 8, bit(7)); fn(7, 8, bit(8));
      for (let i = 9; i < 15; i++) fn(14 - i, 8, bit(i));
      for (let i = 0; i < 8; i++) fn(size - 1 - i, 8, bit(i));
      for (let i = 8; i < 15; i++) fn(8, size - 15 + i, bit(i));
      fn(8, size - 8, true);
    };
    drawFormat(0);
    if (v >= 7){
      let r = v;
      for (let i = 0; i < 12; i++) r = (r << 1) ^ ((r >>> 11) * 0x1F25);
      const bits = (v << 12) | r;
      for (let i = 0; i < 18; i++){ const d = ((bits >>> i) & 1) === 1, a = size - 11 + i % 3, b = Math.floor(i / 3); fn(a, b, d); fn(b, a, d); }
    }

    // データを右下から2列ずつジグザグに置く
    let k = 0;
    for (let right = size - 1; right >= 1; right -= 2){
      if (right === 6) right = 5;
      for (let vert = 0; vert < size; vert++) for (let j = 0; j < 2; j++){
        const x = right - j, up = ((right + 1) & 2) === 0, y = up ? size - 1 - vert : vert;
        if (!F[y][x] && k < words.length * 8){ M[y][x] = ((words[k >>> 3] >>> (7 - (k & 7))) & 1) === 1; k++; }
      }
    }

    // マスク: 8種類を試して減点の一番少ないもの
    const MASKS = [
      (x, y) => (x + y) % 2 === 0, (x, y) => y % 2 === 0, (x, y) => x % 3 === 0, (x, y) => (x + y) % 3 === 0,
      (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0, (x, y) => x * y % 2 + x * y % 3 === 0,
      (x, y) => (x * y % 2 + x * y % 3) % 2 === 0, (x, y) => ((x + y) % 2 + x * y % 3) % 2 === 0];
    const applyMask = m => { for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) if (!F[y][x] && MASKS[m](x, y)) M[y][x] = !M[y][x]; };
    const penalty = () => {
      let p = 0, dark = 0;
      const line = get => {   // 1行（1列）分: 同色5個以上の連続と、ファインダーに似た並び
        let run = 0, prev = null, s = '';
        for (let i = 0; i < size; i++){
          const c = get(i); s += c ? '1' : '0';
          if (c === prev){ run++; if (run === 5) p += 3; else if (run > 5) p++; } else { run = 1; prev = c; }
        }
        const t = '0000' + s + '0000';
        for (let i = t.indexOf('1011101'); i >= 0; i = t.indexOf('1011101', i + 1))
          if (t.slice(i - 4, i) === '0000' || t.slice(i + 7, i + 11) === '0000') p += 40;
      };
      for (let y = 0; y < size; y++) line(x => M[y][x]);
      for (let x = 0; x < size; x++) line(y => M[y][x]);
      for (let y = 0; y < size - 1; y++) for (let x = 0; x < size - 1; x++){
        const c = M[y][x]; if (c === M[y][x + 1] && c === M[y + 1][x] && c === M[y + 1][x + 1]) p += 3;
      }
      for (let y = 0; y < size; y++) for (let x = 0; x < size; x++) if (M[y][x]) dark++;
      const total = size * size;
      p += Math.max(0, Math.ceil(Math.abs(dark * 20 - total * 10) / total) - 1) * 10;
      return p;
    };
    let best = 0, bestP = Infinity;
    for (let m = 0; m < 8; m++){
      applyMask(m); drawFormat(m);
      const p = penalty(); if (p < bestP){ bestP = p; best = m; }
      applyMask(m);   // 同じマスクをもう一度かけると元に戻る
    }
    applyMask(best); drawFormat(best);
    return {size, version: v, ecl: 'LMQH'[e], dark: (x, y) => M[y][x]};
  }

  /* canvas に描く（周りに4モジュール分の余白） */
  function drawQR(canvas, text, px){
    const q = makeQR(text); if (!q) return false;
    const n = q.size + 8, s = Math.max(1, Math.floor((px || 240) / n));
    canvas.width = canvas.height = n * s;
    const c = canvas.getContext('2d');
    c.fillStyle = '#fff'; c.fillRect(0, 0, n * s, n * s); c.fillStyle = '#000';
    for (let y = 0; y < q.size; y++) for (let x = 0; x < q.size; x++) if (q.dark(x, y)) c.fillRect((x + 4) * s, (y + 4) * s, s, s);
    return true;
  }
  window.makeQR = makeQR; window.drawQR = drawQR;
})();
