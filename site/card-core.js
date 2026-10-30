/* 出資馬出走カードメーカー: 出走カード・結果カードで共通の描画部品（2026-10-23〜）
   index.html（出走カード）と result/（結果カード）の両方から読み込む。clubs.js・silks-shapes.js の後に読むこと。
   中身は index.html から切り出したもので、出走カードの描画は切り出す前と同じ（画素単位で同一を確認済み）。
   ここを変えると両方のカードの見た目が変わるので、変えた時は両方を描いて確かめる。 */
(() => {
// 画像内の文字はすべて IPAexゴシック（1ウェイトのみのため、太字はブラウザが太らせて表示）
const IPA='"IPAexGothic","Hiragino Sans","Noto Sans JP",sans-serif';
const F = { body:IPA, num:IPA, display:IPA };
const CLUBS = window.CLUBS || [];
const COLORS = window.SILK_COLORS || {'白':'#ffffff'};
const clubById = id => CLUBS.find(c=>c.id===id);
const SIZES = {'4:5':[1080,1350],'16:9':[1600,900]}; /* 正方形（1:1、1200×1200）は10/24に廃止（私の判断。縦長が1〜2頭で正方形まで縮むため） */
const WD = ['日','月','火','水','木','金','土'];
const WD_EN = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
const WAKU = {
  1:{bg:'#ffffff',fg:'#111111',border:true},2:{bg:'#151515',fg:'#ffffff'},3:{bg:'#e60012',fg:'#ffffff'},
  4:{bg:'#0068b7',fg:'#ffffff'},5:{bg:'#ffe100',fg:'#111111'},6:{bg:'#00a040',fg:'#ffffff'},
  7:{bg:'#f39800',fg:'#111111'},8:{bg:'#f19ec2',fg:'#111111'}
};
const DEFAULT_SILKS = {body:'白',pattern:'plain',pc:'白',sleeve:'白',sp:'plain',spc:'白'};
const THEMES = {
  turf:{bg:'#123d2b',bg2:'#0b2a1d',fg:'#f4efe1',sub:'#b7c8b6',accent:'#e2bd5c',accentInk:'#1c1606',row:'rgba(255,255,255,0.075)',rowLine:'rgba(255,255,255,0.10)',chipBg:'rgba(255,255,255,0.14)',chipFg:'#f4efe1',sat:'#9cc4ff',sun:'#ff9c8f',halo:'rgba(255,255,255,0.45)'},
  dirt:{bg:'#caa77b',bg2:'#b38c5b',fg:'#2b1d10',sub:'#5b4228',accent:'#7a2e1a',accentInk:'#fff4e6',row:'rgba(255,248,236,0.5)',rowLine:'rgba(60,35,15,0.16)',chipBg:'#2b1d10',chipFg:'#f6ead8',sat:'#1d4f9e',sun:'#a8261b',halo:null},
  night:{bg:'#101a3a',bg2:'#060a19',fg:'#eef1fa',sub:'#a5aecb',accent:'#f2c94c',accentInk:'#1a1300',row:'rgba(255,255,255,0.06)',rowLine:'rgba(255,255,255,0.09)',chipBg:'rgba(242,201,76,0.18)',chipFg:'#f6dc8c',sat:'#8fb4ff',sun:'#ff8f8f',halo:'rgba(255,255,255,0.45)'},
  paper:{bg:'#fbfaf6',bg2:'#f1efe8',fg:'#16181d',sub:'#5c616b',accent:'#c62828',accentInk:'#ffffff',row:'#ffffff',rowLine:'#e0ddd3',chipBg:'#16181d',chipFg:'#ffffff',sat:'#1f56c4',sun:'#c62828',halo:null},
  gold:{bg:'#12100c',bg2:'#030302',fg:'#f7f0de',sub:'#bdb29a',accent:'#d6b25e',accentInk:'#1a1405',row:'rgba(214,178,94,0.07)',rowLine:'rgba(214,178,94,0.24)',chipBg:'rgba(214,178,94,0.16)',chipFg:'#f1dca4',sat:'#9cc4ff',sun:'#ff9c8f',halo:'rgba(255,255,255,0.4)'},
  sakura:{bg:'#fbeef2',bg2:'#f5dbe4',fg:'#3b1f2b',sub:'#7a5563',accent:'#c8436f',accentInk:'#ffffff',row:'rgba(255,255,255,0.66)',rowLine:'rgba(120,40,70,0.14)',chipBg:'#3b1f2b',chipFg:'#ffffff',sat:'#2f5fb3',sun:'#c8436f',halo:null},
  summer:{bg:'#0b6a98',bg2:'#063f5e',fg:'#f4fbff',sub:'#b9dcee',accent:'#ffd25e',accentInk:'#1d1600',row:'rgba(255,255,255,0.09)',rowLine:'rgba(255,255,255,0.15)',chipBg:'rgba(255,255,255,0.17)',chipFg:'#f4fbff',sat:'#d3e8ff',sun:'#ffb4a8',halo:'rgba(255,255,255,0.45)'},
  autumn:{bg:'#6a2e17',bg2:'#2f130a',fg:'#fff5e8',sub:'#e6c7a6',accent:'#f2a93b',accentInk:'#2a1400',row:'rgba(255,238,215,0.08)',rowLine:'rgba(255,215,170,0.17)',chipBg:'rgba(255,238,215,0.16)',chipFg:'#fff5e8',sat:'#bfd8ff',sun:'#ffad9c',halo:'rgba(255,255,255,0.45)'},
  winter:{bg:'#eef3f8',bg2:'#d5e1ed',fg:'#142338',sub:'#4f6178',accent:'#b3303e',accentInk:'#ffffff',row:'rgba(255,255,255,0.74)',rowLine:'rgba(20,35,56,0.12)',chipBg:'#142338',chipFg:'#ffffff',sat:'#2c6cb0',sun:'#b3303e',halo:null}
};
/* カスタム背景: 背景色・アクセント色・背景画像から配色を作る */
const DEFAULT_CUSTOM={bg:'#1d3557',accent:'#f4a261',image:'',dim:45};
function hexRgb(h){ h=(h||'#000').replace('#',''); if(h.length===3) h=h.split('').map(c=>c+c).join(''); const n=parseInt(h,16)||0; return [n>>16&255,n>>8&255,n&255]; }
function rgbHex(r,g,b){ return '#'+[r,g,b].map(v=>Math.round(clamp(v,0,255)).toString(16).padStart(2,'0')).join(''); }
function mix(a,b,t){ const A=hexRgb(a),B=hexRgb(b); return rgbHex(A[0]+(B[0]-A[0])*t,A[1]+(B[1]-A[1])*t,A[2]+(B[2]-A[2])*t); }
function luminance(h){ const c=hexRgb(h).map(v=>{ v/=255; return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4); }); return .2126*c[0]+.7152*c[1]+.0722*c[2]; }
function customTheme(c){
  c={...DEFAULT_CUSTOM,...(c||{})};
  const dark=!!c.image || luminance(c.bg)<.4;
  const fg=dark?'#f6f4ee':'#17191d', base=c.image?'#000000':c.bg;
  const acc=c.accent, accInk=luminance(acc)>.45?'#141414':'#ffffff';
  return { bg:c.bg, bg2:mix(c.bg,'#000000',dark?.45:.08), fg, sub:mix(fg,base,dark?.3:.38), accent:acc, accentInk:accInk,
    row:dark?'rgba(255,255,255,0.08)':'rgba(255,255,255,0.7)', rowLine:dark?'rgba(255,255,255,0.14)':'rgba(0,0,0,0.12)',
    chipBg:dark?'rgba(255,255,255,0.16)':'#17191d', chipFg:dark?fg:'#ffffff',
    sat:dark?'#a9c9ff':'#1f56c4', sun:dark?'#ffa7a0':'#c62828', halo:dark?'rgba(255,255,255,0.45)':null, custom:c };
}
const pad2 = n => String(n).padStart(2,'0');
 /* 先週までの馬 */
const STATUS_LABEL = {'取消':'出走取消','除外':'競走除外'};
const runCount = hs => hs.filter(h=>!h.status).length;
const clamp = (v,a,b) => Math.max(a,Math.min(b,v));
function parseDate(d){ if(!d) return null; const [y,m,dd]=d.split('-').map(Number); if(!y) return null; const dt=new Date(y,m-1,dd); return {y,m,d:dd,wd:dt.getDay()}; }
function clubLabel(h){ if(h.clubId==='other') return h.ownerLabel||''; const c=clubById(h.clubId); return c?c.name:''; }
function silksSpec(h){ if(h.customSilks) return h.customSilks; const c=clubById(h.clubId); return (c&&c.silks)||DEFAULT_SILKS; }
function silksImgSrc(h){ if(h.customSilks) return ''; const c=clubById(h.clubId); return (c&&c.img)||''; }
function silksHex(h){ const s=silksSpec(h), C=n=>COLORS[n]||n||'#ffffff'; return {body:C(s.body),pattern:s.pattern,pc:C(s.pc),sleeve:C(s.sleeve),sp:s.sp,spc:C(s.spc)}; }

/* ---------- drawing helpers ---------- */
function rr(ctx,x,y,w,h,r){ r=Math.min(r,w/2,h/2); ctx.beginPath(); ctx.moveTo(x+r,y); ctx.arcTo(x+w,y,x+w,y+h,r); ctx.arcTo(x+w,y+h,x,y+h,r); ctx.arcTo(x,y+h,x,y,r); ctx.arcTo(x,y,x+w,y,r); ctx.closePath(); }
function ls(ctx,px){ if('letterSpacing' in ctx) ctx.letterSpacing = px+'px'; }
function fit(ctx,text,weight,family,size,maxW,minRatio=0.62){
  let s=Math.round(size); const min=Math.max(9,Math.round(size*minRatio));
  ctx.font=`${weight} ${s}px ${family}`;
  while(ctx.measureText(text).width>maxW && s>min){ s--; ctx.font=`${weight} ${s}px ${family}`; }
  let t=text;
  if(ctx.measureText(t).width>maxW){ let a=Array.from(t); while(a.length>1 && ctx.measureText(a.join('')+'…').width>maxW) a.pop(); t=a.join('')+'…'; }
  return {t,s};
}
function mulberry(a){ return ()=>{ a|=0; a=a+0x6D2B79F5|0; let t=Math.imul(a^a>>>15,1|a); t=t+Math.imul(t^t>>>7,61|t)^t; return ((t^t>>>14)>>>0)/4294967296; }; }

/* ---------- 勝負服（手描き） ----------
   形と柄は Wikipedia「勝負服 (競馬)」の標示の参考画像（Commons、CC0）そのもの。silks-shapes.js に図形として持ち、
   色だけ差し替えて描く（生成: tools/extract_silks.py）。座標は 0〜1000 の正方形。
   見本は胴と袖の柄が一体なので、胴の範囲（BODY_CLIP）で切り抜いて胴の柄、それ以外を袖の柄として描く。
   見本に袖の柄がない散らし柄（玉霰・星散・蛇目散・銭形散・井桁絣）は、見本の1個分を袖に沿って並べる。 */
const SHAPES = window.SILK_SHAPES || null;
const OUTLINE = 'rgba(10,12,14,0.85)';
// 胴の範囲: 脇線（x=264/736、脇の下 y=447 から下）を肩（216,103）まで曲線で延ばした内側
const BODY_CLIP = new Path2D('M264 1000L264 447C262 330 240 180 216 103L216 0L784 0L784 103C760 180 738 330 736 447L736 1000Z');
const SEAM = new Path2D('M264 447C262 330 240 180 216 103M736 447C738 330 760 180 784 103');
const SLEEVE_AXIS = { top:[203,250], cuff:[116,905], width:118 };
   // 左袖の中心線（右袖は左右反転）
const SPAN_KEYS = { ichimonji:'wa1', yamagata1:'yamagatawa1', kyoshi:'kyoshi' };
   // 胴と袖にまたがる柄（同じ色で袖にも描く）
const ALIAS = { yoko:'wa3' };
                                                      // 旧データ（JRA の標示にない横縞）
const ARM_FROM_REF = new Set(['wa1','wa2','wa3','yamagatawa1','yamagata','yamagata3','hishiyamagata','tate','check','genroku','diamond','uroko']);
const _p2d = new Map();
function p2d(it){ let p=_p2d.get(it); if(!p){ p=new Path2D(); p.addPath(new Path2D(it.d), new DOMMatrix(it.m)); _p2d.set(it,p); } return p; }
function p2dAll(list){ let p=_p2d.get(list); if(!p){ p=new Path2D(); for(const it of list) p.addPath(p2d(it)); _p2d.set(list,p); } return p; }
function star(ctx,cx,cy,r){ ctx.beginPath(); for(let i=0;i<10;i++){ const a=-Math.PI/2+i*Math.PI/5, rad=i%2?r*.42:r; ctx.lineTo(cx+Math.cos(a)*rad,cy+Math.sin(a)*rad); } ctx.closePath(); ctx.fill(); }
/* 見本の柄を描く（w=1 の図形は地色で塗る） */
function drawRefPattern(ctx,key,color,base,only){
  const list=SHAPES.patterns[key]; if(!list) return;
  (only? only.map(i=>list[i]) : list).forEach(it=>{ ctx.fillStyle=it.w?base:color; ctx.fill(p2d(it)); });
}
/* 散らし柄を袖に並べる（見本の1個分を、袖の幅に収まる大きさで袖口へ向かって3つ） */
function drawSleeveMotif(ctx,key,color,base){
  const m=SHAPES.motifs[key]; if(!m) return; const A=SLEEVE_AXIS, k=Math.min(1,A.width/m.size);
  for(const right of [false,true]) for(const t of [.30,.56,.82]){
    const px=A.top[0]+(A.cuff[0]-A.top[0])*t, py=A.top[1]+(A.cuff[1]-A.top[1])*t;
    ctx.save(); ctx.translate(right?1000-px:px,py); ctx.scale(k,k); ctx.translate(-m.c[0],-m.c[1]); drawRefPattern(ctx,key,color,base,m.i); ctx.restore();
  }
}
function drawSilks(ctx,x,y,s,sk,halo){
  if(!SHAPES){ ctx.fillStyle=sk.body; ctx.fillRect(x+s*.27,y+s*.08,s*.46,s*.88); return; }
  const S=SHAPES, G=p2dAll(S.garment), C=p2dAll(S.cuffs), H=p2dAll(S.hem);
  const span=SPAN_KEYS[sk.pattern], bodyKey=span||ALIAS[sk.pattern]||sk.pattern, spKey=ALIAS[sk.sp]||sk.sp;
  const lw=Math.max(12, 1000/s*1.0);                     // 輪郭は 1.2%（小さい時も1px以上）
  ctx.save(); ctx.translate(x,y); ctx.scale(s/1000,s/1000); ctx.lineJoin='round'; ctx.lineCap='round';
  if(halo){ ctx.lineWidth=50; ctx.strokeStyle=halo; ctx.stroke(G); ctx.stroke(C); ctx.stroke(H); }
  ctx.lineWidth=lw; ctx.strokeStyle=OUTLINE;
  ctx.fillStyle=sk.sleeve; ctx.fill(C); ctx.stroke(C);                 // 袖口
  ctx.fillStyle=sk.body; ctx.fill(H); ctx.stroke(H);                   // 裾の縁
  // 袖（シルエット全体を袖の色で塗り、袖の柄を描く。胴はこの上に重ねる）
  ctx.save(); ctx.clip(G); ctx.fillStyle=sk.sleeve; ctx.fill(G);
  if(spKey && spKey!=='plain'){ if(ARM_FROM_REF.has(spKey)) drawRefPattern(ctx,spKey,sk.spc,sk.sleeve); else drawSleeveMotif(ctx,spKey,sk.spc,sk.sleeve); }
  if(span) drawRefPattern(ctx,bodyKey,sk.pc,sk.sleeve);
  ctx.restore();
  // 胴
  ctx.save(); ctx.clip(G); ctx.clip(BODY_CLIP); ctx.fillStyle=sk.body; ctx.fill(G);
  if(bodyKey && bodyKey!=='plain') drawRefPattern(ctx,bodyKey,sk.pc,sk.body);
  ctx.restore();
  if(bodyKey && bodyKey!=='plain'){ ctx.save(); ctx.clip(H); ctx.clip(BODY_CLIP); drawRefPattern(ctx,bodyKey,sk.pc,sk.body); ctx.restore(); ctx.stroke(H); }
  if(sk.sleeve!==sk.body || spKey!==bodyKey){ ctx.lineWidth=lw*.8; ctx.stroke(SEAM); ctx.lineWidth=lw; }   // 袖と胴の境目
  // 襟・ボタン・輪郭
  const collar = bodyKey==='kyoshi' ? sk.pc : sk.body;   // 鋸歯形は肩から胸が柄の色なので襟も柄の色（見本10・実物とも）
  for(const it of S.neck){ const p=p2d(it); ctx.fillStyle=it.dark?OUTLINE:collar; ctx.fill(p); if(!it.dark){ ctx.lineWidth=lw*.8; ctx.stroke(p); } }
  ctx.lineWidth=lw;
  if(s>=80){ ctx.fillStyle=OUTLINE; for(const it of S.buttons) ctx.fill(p2d(it)); }
  for(const it of S.outline) ctx.stroke(p2d(it));
  ctx.restore();
}

function drawSilksImg(ctx,img,x,y,s,halo){
  const iw=img.naturalWidth||1, ih=img.naturalHeight||1, k=Math.min(s/iw,s/ih), w=iw*k, h=ih*k, dx=x+(s-w)/2, dy=y+(s-h)/2;
  ctx.save(); if(halo){ ctx.shadowColor=halo; ctx.shadowBlur=s*.08*(ctx.getTransform?ctx.getTransform().a:1); } /* 影のぼかしは拡大の影響を受けないので、書き出しの倍率を掛ける */ ctx.drawImage(img,dx,dy,w,h); ctx.restore();
}

/* ---------- background ---------- */
function drawBg(ctx,W,H,T,theme,pad){
  ctx.fillStyle=T.bg; ctx.fillRect(0,0,W,H);
  if(theme==='turf'){
    ctx.save(); ctx.translate(W/2,H/2); ctx.rotate(-0.38); const bw=W*.085, D=Math.hypot(W,H);
    ctx.fillStyle='rgba(255,255,255,0.035)'; for(let i=-20;i<20;i+=2) ctx.fillRect(i*bw,-D,bw,D*2); ctx.restore();
    const g=ctx.createLinearGradient(0,H*.5,0,H); g.addColorStop(0,'rgba(0,0,0,0)'); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
  } else if(theme==='dirt'){
    const g=ctx.createLinearGradient(0,0,0,H); g.addColorStop(0,T.bg); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    const rnd=mulberry(7); for(let i=0;i<2600;i++){ const r=.6+rnd()*1.8; ctx.fillStyle= rnd()<.6?'rgba(60,35,10,0.14)':'rgba(255,245,225,0.22)'; ctx.beginPath(); ctx.arc(rnd()*W,rnd()*H,r,0,Math.PI*2); ctx.fill(); }
  } else if(theme==='night'){
    const g=ctx.createLinearGradient(0,0,0,H); g.addColorStop(0,T.bg); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    const r=ctx.createRadialGradient(W*.92,-H*.05,0,W*.92,-H*.05,W*.75); r.addColorStop(0,'rgba(242,201,76,0.20)'); r.addColorStop(1,'rgba(242,201,76,0)'); ctx.fillStyle=r; ctx.fillRect(0,0,W,H);
  } else if(theme==='gold'){
    const g=ctx.createLinearGradient(0,0,0,H); g.addColorStop(0,T.bg); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    const r=ctx.createRadialGradient(W*.5,-H*.1,0,W*.5,-H*.1,H*.8); r.addColorStop(0,'rgba(214,178,94,0.22)'); r.addColorStop(1,'rgba(214,178,94,0)'); ctx.fillStyle=r; ctx.fillRect(0,0,W,H);
    ctx.save(); ctx.strokeStyle='rgba(214,178,94,0.06)'; ctx.lineWidth=1; for(let x=-H;x<W;x+=14){ ctx.beginPath(); ctx.moveTo(x,0); ctx.lineTo(x+H,H); ctx.stroke(); } ctx.restore();
    ctx.strokeStyle='rgba(214,178,94,0.75)'; ctx.lineWidth=2; ctx.strokeRect(pad*.4,pad*.4,W-pad*.8,H-pad*.8);
    ctx.strokeStyle='rgba(214,178,94,0.35)'; ctx.lineWidth=1; ctx.strokeRect(pad*.4+7,pad*.4+7,W-pad*.8-14,H-pad*.8-14);
  } else if(theme==='sakura'){
    const g=ctx.createLinearGradient(0,0,W,H); g.addColorStop(0,T.bg); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    const rnd=mulberry(11), s0=W/1080;
    for(let i=0;i<70;i++){ const x=rnd()*W, y=rnd()*H, r=(10+rnd()*16)*s0, a=rnd()*Math.PI*2;
      ctx.save(); ctx.translate(x,y); ctx.rotate(a); ctx.fillStyle=`rgba(232,128,163,${.12+rnd()*.22})`;
      ctx.beginPath(); ctx.moveTo(0,-r); ctx.bezierCurveTo(r*.9,-r*.6,r*.6,r*.7,0,r); ctx.bezierCurveTo(-r*.6,r*.7,-r*.9,-r*.6,0,-r); ctx.fill();
      ctx.fillStyle=T.bg; ctx.beginPath(); ctx.moveTo(-r*.18,-r*1.02); ctx.lineTo(0,-r*.7); ctx.lineTo(r*.18,-r*1.02); ctx.fill(); ctx.restore(); }
  } else if(theme==='summer'){
    const g=ctx.createLinearGradient(0,0,0,H); g.addColorStop(0,'#1592c4'); g.addColorStop(.55,T.bg); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    const r=ctx.createRadialGradient(W*.88,H*.04,0,W*.88,H*.04,W*.55); r.addColorStop(0,'rgba(255,230,140,0.45)'); r.addColorStop(1,'rgba(255,230,140,0)'); ctx.fillStyle=r; ctx.fillRect(0,0,W,H);
    ctx.strokeStyle='rgba(255,255,255,0.07)'; ctx.lineWidth=Math.max(2,W*.003);
    for(let y=H*.18;y<H;y+=H*.045){ ctx.beginPath(); for(let x=0;x<=W;x+=W/60){ const yy=y+Math.sin(x/W*Math.PI*6+y)*H*.008; x?ctx.lineTo(x,yy):ctx.moveTo(x,yy); } ctx.stroke(); }
  } else if(theme==='autumn'){   /* 秋: 紅葉と銀杏の葉が舞う */
    const g=ctx.createLinearGradient(0,0,W*.4,H); g.addColorStop(0,'#8a3b18'); g.addColorStop(.45,T.bg); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    const r=ctx.createRadialGradient(W*.9,H*.02,0,W*.9,H*.02,W*.6); r.addColorStop(0,'rgba(255,190,90,0.30)'); r.addColorStop(1,'rgba(255,190,90,0)'); ctx.fillStyle=r; ctx.fillRect(0,0,W,H);
    const rnd=mulberry(23), s0=W/1080, cols=['224,72,40','240,120,40','236,170,50','200,50,40'];
    const maple=(R)=>{ ctx.beginPath(); for(let k=0;k<=10;k++){ const a=-Math.PI/2+k*Math.PI/5, rr3=k%2?R*.42:R*(k===0||k===10?1:k===2||k===8?.92:.78); const px=Math.cos(a)*rr3, py=Math.sin(a)*rr3; k?ctx.lineTo(px,py):ctx.moveTo(px,py); } ctx.closePath(); ctx.fill(); ctx.fillRect(-R*.04,R*.3,R*.08,R*.55); };
    const ginkgo=(R)=>{ ctx.beginPath(); ctx.moveTo(0,R*.55); ctx.lineTo(-R*.85,-R*.35); ctx.quadraticCurveTo(-R*.4,-R*.8,0,-R*.62); ctx.quadraticCurveTo(R*.4,-R*.8,R*.85,-R*.35); ctx.closePath(); ctx.fill(); ctx.fillRect(-R*.035,R*.5,R*.07,R*.45); };
    for(let i=0;i<46;i++){ const x=rnd()*W, y=rnd()*H, R=(14+rnd()*22)*s0, a=rnd()*Math.PI*2, c=cols[Math.floor(rnd()*cols.length)], al=.10+rnd()*.20, gk=rnd()<.3;
      ctx.save(); ctx.translate(x,y); ctx.rotate(a); ctx.fillStyle=gk?`rgba(240,196,60,${al})`:`rgba(${c},${al})`; gk?ginkgo(R):maple(R); ctx.restore(); }
  } else if(theme==='winter'){   /* 冬: 冬晴れの空と寒椿（雪は降らせない） */
    const g=ctx.createLinearGradient(0,0,0,H); g.addColorStop(0,T.bg); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    const r=ctx.createRadialGradient(W*.9,H*.03,0,W*.9,H*.03,W*.55); r.addColorStop(0,'rgba(255,236,190,0.55)'); r.addColorStop(1,'rgba(255,236,190,0)'); ctx.fillStyle=r; ctx.fillRect(0,0,W,H);
    const rnd=mulberry(31), s0=W/1080;   /* 寒椿は濃い紅で、タイトルと左の見出しを避けて右寄りに置く */
    for(let i=0;i<10;i++){ const x=W*(.58+rnd()*.46), y=H*(.24+rnd()*.8), R=(18+rnd()*18)*s0, a=rnd()*Math.PI*2, al=.32+rnd()*.16;
      ctx.save(); ctx.translate(x,y); ctx.rotate(a);
      ctx.fillStyle=`rgba(28,86,52,${al})`; for(const sgn of [-1,1]){ ctx.beginPath(); ctx.ellipse(sgn*R*1.05,R*.55,R*.62,R*.28,sgn*-.5,0,Math.PI*2); ctx.fill(); }
      ctx.fillStyle=`rgba(172,22,44,${al})`; for(let k=0;k<5;k++){ const pa=k*Math.PI*2/5; ctx.beginPath(); ctx.arc(Math.cos(pa)*R*.5,Math.sin(pa)*R*.5,R*.52,0,Math.PI*2); ctx.fill(); }
      ctx.fillStyle=`rgba(236,186,50,${Math.min(1,al*1.8)})`; ctx.beginPath(); ctx.arc(0,0,R*.26,0,Math.PI*2); ctx.fill(); ctx.restore(); }
  } else if(theme==='custom'){
    const c=T.custom||DEFAULT_CUSTOM, img=c.image&&imgCache[c.image];
    const g=ctx.createLinearGradient(0,0,0,H); g.addColorStop(0,T.bg); g.addColorStop(1,T.bg2); ctx.fillStyle=g; ctx.fillRect(0,0,W,H);
    if(img&&img.naturalWidth){ const k=Math.max(W/img.naturalWidth,H/img.naturalHeight), w=img.naturalWidth*k, h=img.naturalHeight*k;
      ctx.drawImage(img,(W-w)/2,(H-h)/2,w,h); ctx.fillStyle=`rgba(0,0,0,${(c.dim??45)/100})`; ctx.fillRect(0,0,W,H);
      const b=ctx.createLinearGradient(0,H*.45,0,H); b.addColorStop(0,'rgba(0,0,0,0)'); b.addColorStop(1,'rgba(0,0,0,0.35)'); ctx.fillStyle=b; ctx.fillRect(0,0,W,H); }
  } else {
    ctx.strokeStyle=T.fg; ctx.lineWidth=2; ctx.strokeRect(pad*.45,pad*.45,W-pad*.9,H-pad*.9);
  }
}

/* ---------- layout ---------- */
// 競馬場の並び: 関東主場 → 関西主場 → 第3場（→ 第4場以降）
// 関東主場 = 東京・中山（なければ新潟・福島）、関西主場 = 京都・阪神（なければ中京・小倉）。札幌・函館は常に第3場以降。
// heldVenues に「その日に開催している競馬場」を渡すと、出資馬がいない主場も考慮して正しく判定する（自動取得で使う予定）
const VENUE_ORDER=['札幌','函館','福島','新潟','東京','中山','中京','京都','阪神','小倉'];
const EAST_MAIN=['東京','中山','新潟','福島'], WEST_MAIN=['京都','阪神','中京','小倉'];
const num=v=>{ const n=parseInt(v,10); return isNaN(n)?99:n; };
function venueRanker(venues){
  const set=new Set(venues.map(v=>(v||'').trim()).filter(Boolean));
  const east=EAST_MAIN.find(v=>set.has(v)), west=WEST_MAIN.find(v=>set.has(v));
  return v=>{ v=(v||'').trim(); if(!v) return 999; if(v===east) return 0; if(v===west) return 1;
    const i=VENUE_ORDER.indexOf(v); return i<0?500:10+i; };
}
function entriesOf(horses,order,heldVenues){
  let hs=horses.slice();
  const byDate=(a,b)=>(a.date||'9999').localeCompare(b.date||'9999');
  const rankers={};
  const rankOf=h=>{ const d=h.date||''; if(!rankers[d]) rankers[d]=venueRanker((heldVenues&&heldVenues[d])||horses.filter(x=>(x.date||'')===d).map(x=>x.venue)); return rankers[d](h.venue); };
  if(order==='venue') hs.sort((a,b)=>byDate(a,b)||rankOf(a)-rankOf(b)||(a.venue||'').localeCompare(b.venue||'')||num(a.r)-num(b.r)||(a.time||'99:99').localeCompare(b.time||'99:99'));
  else if(order==='time') hs.sort((a,b)=>byDate(a,b)||(a.time||'99:99').localeCompare(b.time||'99:99')||rankOf(a)-rankOf(b));
  else hs.sort(byDate);
  const out=[]; let cur, curV;
  hs.forEach((h,i)=>{
    if(i===0||h.date!==cur){ out.push({t:'day',date:h.date}); cur=h.date; curV=undefined; }
    if(order==='venue' && (h.venue||'')!==curV){ curV=h.venue||''; out.push({t:'venue',venue:curV}); }
    out.push({t:'horse',h}); });
  return out;
}
const GAP=.11, DAY=.5, VEN=.46;
 /* 行の高さを1とした時の、行間・日付見出し・競馬場見出しの高さ */
const colUnits=p=>p.reduce((u,e)=>u+(e.t==='horse'?1+GAP:e.t==='day'?DAY:VEN),0);
/* 2列の時は日ごと・競馬場ごとに上下の段に分け、各段の中を2列にする（10/18）。
   日付・競馬場の見出しは段の幅いっぱいに出す（発走時刻順・入力順では競馬場の見出しがないので日ごとの段）。
   1列の時は段に分けず、見出しも列の中に並べる */
function bandsOf(entries,cols){
  if(cols===1) return [{day:null,venue:null,cols:[entries]}];
  const bands=[]; let cur=null, day=null;
  entries.forEach(e=>{
    if(e.t==='day'){ day=e; cur=null; }
    else if(e.t==='venue'){ cur={day,venue:e,items:[]}; day=null; bands.push(cur); }
    else { if(!cur){ cur={day,venue:null,items:[]}; day=null; bands.push(cur); } cur.items.push(e); } });
  /* 同じ日の中で、1頭だけの競馬場が続く時は左右に並べる（見出しはそれぞれの列の中。10/18） */
  const out=[];
  for(let i=0;i<bands.length;i++){ const a=bands[i], b=bands[i+1];
    if(a.venue && a.items.length===1 && b && !b.day && b.venue && b.items.length===1){
      out.push({day:a.day,venue:null,cols:[[a.venue,...a.items],[b.venue,...b.items]]}); i++; continue; }
    out.push({day:a.day,venue:a.venue,cols:splitRows(a.items)}); }
  return out;
}
/* 画像の大きさと並べ方を決める（10/18〜）。
   縦長: 幅1080固定。行が ROW_PREF より小さくなる時は、行の大きさを保ったまま画像を縦に伸ばす（最小 4:5）
   横長: 列を左から上→下に埋め、入りきらなければ列を増やす。高さも伸ばして 16:9 に近い形を保つ（最小 1600×900）。日ごとに新しい列から始める
   正方形（1200×1200固定）は10/24に廃止 */
const ROW_PREF={tall1:.135, tall2:.25, wide:118, wideColW:520};
 /* 縦長1列は幅×0.135、縦長2列は列幅×0.25、横長は行118px（列が減るなら100pxまで）・列幅520px */
function headerTop(W0,H0,S,hs){
  const ts=Math.round(Math.min(W0*.06,H0*.068)), pad=Math.round(W0*.05), ds=Math.round(ts*.46);
  let y=pad+ts*1.08; if(rangeText(hs)||(S.showCount&&runCount(hs))||S.handle) y+=ds*1.5;
  return {ts,pad,top:y+ts*.3+ts*.55};
}
function flowCols(entries,cap,unit){ /* 横長用: 列の高さ cap（行の高さ単位）に詰める。日が変わる時と、見出しの後に1行も入らない時は次の列へ */
  const cols=[]; let cur=[], used=0, day=null, ven=null;
  const next=()=>{ if(cur.length) cols.push(cur); cur=[]; used=0; };
  const cont=e=>{ /* 同じ日・競馬場の続きで列を移る時は、見出しは描かずに高さだけ取って行の位置を左の列とそろえる（10/18） */
    next(); if(day){ cur.push({...day,blank:true}); used+=unit(day); }
    if(e.t==='horse' && ven){ cur.push({...ven,blank:true}); used+=unit(ven); } };
  entries.forEach((e,i)=>{
    if(e.t==='day' && cur.length) next();
    let need=unit(e);
    if(e.t!=='horse'){ /* 見出しの時は、その競馬場の馬がまとめて入るか見る（入らなければ次の列から。10/18〜）。
         まとめて1列に入らないほど多い時だけ、途中で次の列へ続ける */
      let block=unit(e), first=0;
      for(let j=i+1;j<entries.length;j++){ const x=entries[j]; if(x.t==='day'||(x.t==='venue'&&e.t==='venue')) break; block+=unit(x); if(x.t==='horse'&&!first) first=block; }
      need=block<=cap+1e-6?block:first; }
    if(used+need>cap+1e-6 && cur.length) cont(e);
    if(e.t==='day'){ day=e; ven=null; } else if(e.t==='venue') ven=e;
    cur.push(e); used+=unit(e);
  });
  next(); return cols;
}
function layoutOf(hs,S,held){ /* held: 日付→その日の開催場の一覧（出馬表から。なければ null） */
  const mode=S.size==='16:9'?'wide':'tall'; /* 正方形は廃止（10/24）。古い設定の '1:1' も縦長で描く */
  const [W0,H0]=SIZES[S.size]||SIZES['4:5'];
  const {ts,pad,top}=headerTop(W0,H0,S,hs), gap=pad*.6;
  const L={W:W0,H:H0,ts,pad,top,gap};
  if(!hs.length) return L;
  const entries=entriesOf(hs,S.order,held), n=hs.length;
  if(mode==='wide' && n>3){
    /* 横長（10/18〜）: 高さを900から少しずつ伸ばして試し、幅（列数で決まる）との比が 16:9 に一番近い高さを選ぶ。
       頭数が少なければ 1600×900 のまま、多ければ縦横両方に伸びる */
    const unit=e=>e.t==='horse'?1+GAP:e.t==='day'?DAY:VEN;
    const plan=H=>{ const avail=H-pad-top;
      /* 列数が減るなら行を少し（最大15%）小さくしてよい。同じ列数になる中で一番大きい行を選ぶ */
      const minC=flowCols(entries,avail/(ROW_PREF.wide*.85),unit).length;
      let flow; for(let r=ROW_PREF.wide;r>=ROW_PREF.wide*.85-1e-6;r-=2){ flow=flowCols(entries,avail/r,unit); if(flow.length<=minC) break; }
      if(flow.length===1){ /* 1列に収まる頭数でも、横長は2列に分けて行を大きくする */
        const u=colUnits(flow[0]); for(let k=.5;k<1;k+=.05){ const f2=flowCols(entries,u*k+1.2,unit); if(f2.length===2){ flow=f2; break; } } }
      const c=flow.length, W=Math.max(W0,Math.round(pad*2+c*ROW_PREF.wideColW+(c-1)*gap));
      return {H,W,flow,avail,score:Math.abs(Math.log((W/H)/(16/9)))}; };
    let best=plan(H0);
    for(let H=H0+30;H<=H0*4 && best.score>.02;H+=30){ const p=plan(H); if(p.score<best.score-.01) best=p; }
    const {W,H,flow,avail}=best, c=flow.length;
    L.W=W; L.H=H; L.colW=(W-pad*2-gap*(c-1))/c;
    L.rowH=Math.min(avail/Math.max(...flow.map(colUnits)), L.colW*.27);
    L.flow=flow; return L;
  }
  const cols=(mode==='wide'||n<=5)?1:2; /* 縦長は5頭まで1列・6頭以上で2列（10/18〜。以前は9頭以上で2列） */
  L.colW=(W0-pad*2-gap*(cols-1))/cols;
  L.bands=bandsOf(entries,cols);
  const units=L.bands.reduce((u,b)=>u+bandUnits(b),0);
  const capR=cols===1?W0*.165:L.colW*.27;
  L.rowH=Math.min((H0-pad-top)/units, capR);
  if(mode==='tall'){ /* 縦長は内容に合わせて高さを決める（10/18〜）:
       行を最大の大きさにして 4:5 に収まるなら、その高さまで縮める（ただし正方形より低くはしない）。
       4:5 に収まらなければ行を ROW_PREF まで小さくし、それでも入らなければ下に伸ばす */
    const pref=cols===1?W0*ROW_PREF.tall1:L.colW*ROW_PREF.tall2, need=r=>top+units*r+pad;
    if(need(capR)<=H0){ L.rowH=capR; /* 下限は正方形。2列は行を大きくしすぎると馬名が入らなくなるので、拡大は少しだけ（余りは下の余白） */
      const minH=W0;
      L.H=Math.ceil(Math.max(minH,need(capR)));
      if(need(capR)<minH) L.rowH=Math.min((minH-top-pad)/units, capR*(cols===1?1.3:1)); }
    else if(L.rowH<pref){ L.rowH=pref; L.H=Math.ceil(need(pref)); } }
  return L;
}
const bandUnits=b=>(b.day?DAY:0)+(b.venue?VEN:0)+Math.max(...b.cols.map(colUnits));
function splitRows(items){ /* 段の中は左の列を上から埋めてから右の列へ（1 4 / 2 5 / 3。10/24〜、私の指定。発走順に縦に読めるように）。
     10/18〜10/24 は左→右→次の行（1 2 / 3 4 / 5）だった。頭数が奇数の時は左の列が1頭多い */
  const k=Math.ceil(items.length/2); return [items.slice(0,k),items.slice(k)];
}

function drawVenue(ctx,x,y,w,vh,e,T){
  if(e.blank) return;
  const s=Math.round(clamp(vh*.66,12,32)); const base=y+vh*.76;
  ctx.textAlign='left'; ctx.textBaseline='alphabetic';
  ctx.fillStyle=T.accent; ctx.fillRect(x+2,base-s*.86,Math.max(3,s*.16),s*.92);
  let cx=x+2+Math.max(3,s*.16)+s*.4;
  ctx.font=`900 ${s}px ${F.body}`; ctx.fillStyle=T.fg; const t=e.venue||'競馬場未定'; ctx.fillText(t,cx,base); cx+=ctx.measureText(t).width;
  if(e.cont){ ctx.font=`700 ${Math.round(s*.66)}px ${F.body}`; ctx.fillStyle=T.sub; ctx.fillText('　つづき',cx,base); }
}
function drawDay(ctx,x,y,w,dh,e,T){
  if(e.blank) return;
  const s=Math.round(clamp(dh*.6,12,34)); const base=y+dh*.72; const p=parseDate(e.date);
  ctx.textAlign='left'; ctx.textBaseline='alphabetic'; let cx=x;
  ctx.font=`900 ${s}px ${F.body}`;
  if(p){
    ctx.fillStyle=T.fg; const t1=`${p.m}/${p.d}`; ctx.fillText(t1,cx,base); cx+=ctx.measureText(t1).width+s*.15;
    ctx.fillStyle=p.wd===6?T.sat:p.wd===0?T.sun:T.fg; const t2=`(${WD[p.wd]})`; ctx.fillText(t2,cx,base); cx+=ctx.measureText(t2).width;
  } else { ctx.fillStyle=T.fg; ctx.fillText('日付未定',cx,base); cx+=ctx.measureText('日付未定').width; }
  if(e.cont){ ctx.font=`700 ${Math.round(s*.6)}px ${F.body}`; ctx.fillStyle=T.sub; ctx.fillText('　つづき',cx,base); cx+=ctx.measureText('　つづき').width; }
  cx+=s*.5; ctx.fillStyle=T.rowLine; ctx.fillRect(cx,base-s*.33,Math.max(0,x+w-cx),2);
}

function drawRow(ctx,x,y,w,h,hr,T,S,imgs){
  ctx.fillStyle=T.row; rr(ctx,x,y,w,h,h*.12); ctx.fill(); ctx.strokeStyle=T.rowLine; ctx.lineWidth=1.5; ctx.stroke();
  const ip=h*.11;
  const showVenue=true; // 競馬場の小見出しがあっても、レース番号の上に場名を表示する
  const bw=h*(showVenue?.5:.58), bh=h*.62, bx=x+ip, by=y+(h-bh)/2;
  const hasUma=!!hr.umaban;
  // venue + race number (always shown)
  rr(ctx,bx,by,bw,bh,h*.06); ctx.fillStyle=T.chipBg; ctx.fill();
  ctx.fillStyle=T.chipFg; ctx.textAlign='center'; ctx.textBaseline='alphabetic';
  if(showVenue && hr.venue){ const f=fit(ctx,hr.venue,900,F.body,bh*.24,bw*.86); ctx.fillText(f.t,bx+bw/2,by+bh*.34); }
  if(hr.r){ let ns=Math.round(bh*(showVenue?.5:.62)); const base=by+bh*(showVenue?.86:.74), num=String(hr.r); let nw, rw;
    const measure=()=>{ ctx.font=`700 ${ns}px ${F.num}`; nw=ctx.measureText(num).width; ctx.font=`700 ${Math.round(ns*.5)}px ${F.num}`; rw=ctx.measureText('R').width; };
    const fitW=()=>{ ctx.font=`700 ${ns}px ${F.num}`; const w=ctx.measureText('12').width; ctx.font=`700 ${Math.round(ns*.5)}px ${F.num}`; return w+ctx.measureText('R').width+1; };
    while(fitW()>bw*.86 && ns>8) ns--; measure();
    const sx0=bx+bw/2-(nw+rw+1)/2;
    ctx.textAlign='left'; ctx.font=`700 ${ns}px ${F.num}`; ctx.fillText(num,sx0,base); ctx.font=`700 ${Math.round(ns*.5)}px ${F.num}`; ctx.fillText('R',sx0+nw+1,base); }
  if(!hr.r && !(showVenue&&hr.venue)){ ctx.textAlign='center'; ctx.font=`700 ${Math.round(bh*.5)}px ${F.num}`; ctx.fillText('–',bx+bw/2,by+bh*.68); }
  let nextX=bx+bw;
  if(hasUma||S._anyUma){ // after 枠順確定 (Friday): waku-colored number next to the race block (slot kept on every row for alignment)
    const uw=h*.44, ux=bx+bw+ip*.45, wk=hasUma?WAKU[hr.waku]:null;
    rr(ctx,ux,by,uw,bh,h*.06); ctx.fillStyle=wk?wk.bg:T.chipBg; ctx.fill();
    if(wk&&wk.border){ ctx.strokeStyle='rgba(0,0,0,.3)'; ctx.lineWidth=1.5; ctx.stroke(); }
    ctx.fillStyle=wk?wk.fg:T.chipFg; ctx.textAlign='center'; ctx.textBaseline='middle';
    const us=hasUma?String(hr.umaban):'–'; const f=fit(ctx,us,700,F.num,bh*.62,uw*.88); ctx.fillText(f.t,ux+uw/2,by+bh/2+bh*.04);
    nextX=ux+uw;
  }
  ctx.textBaseline='alphabetic'; ctx.textAlign='left';
  const ss=h*.72, sx=nextX+ip*.8, sy=y+(h-ss)/2;
  const simg=imgs[silksImgSrc(hr)];
  const scr=STATUS_LABEL[hr.status]||''; /* 出走取消・競走除外: 赤いバッジ＋馬名に取り消し線、勝負服を薄く（10/18〜） */
  if(scr) ctx.globalAlpha=.45;
  if(simg) drawSilksImg(ctx,simg,sx,sy,ss,T.halo); else drawSilks(ctx,sx,sy,ss,silksHex(hr),T.halo);
  ctx.globalAlpha=1;
  /* 命名馬（10/30〜）: 勝負服の裾に「命名馬」バッジを重ねる（馬名の右に置く案は縦長2列で窮屈だったため、私の判断で変更） */
  if(S._named&&hr.name&&S._named.has(hr.name)) drawNamedOnSilks(ctx,sx,sy,ss,clamp(h*.105,8,21),T,!!scr);
  const tx=sx+ss+ip*.8; let right=x+w-ip;
  const img=hr.photo&&imgs[hr.photo];
  if(img){ const ps=h-ip*1.4, px=right-ps, py=y+(h-ps)/2; const sw=img.naturalWidth, sh=img.naturalHeight, m=Math.min(sw,sh);
    ctx.save(); rr(ctx,px,py,ps,ps,h*.08); ctx.clip(); ctx.drawImage(img,(sw-m)/2,(sh-m)/2,m,m,px,py,ps,ps); ctx.restore(); right=px-ip*.8; }
  const label=scr||((S.showKuchi && hr.kuchi && hr.kuchi!=='none')?{win:'口取り 当選',wait:'口取り 抽選待ち',lose:'口取り 落選'}[hr.kuchi]:'');
  let inlineBadge=false;
  const paintBadge=(px,py,pw,ph,fs)=>{ rr(ctx,px,py,pw,ph,ph/2);
    if(scr){ ctx.fillStyle='#d32f2f'; ctx.fill(); ctx.fillStyle='#ffffff'; }
    else if(hr.kuchi==='win'){ ctx.fillStyle=T.accent; ctx.fill(); ctx.fillStyle=T.accentInk; }
    else { ctx.lineWidth=2; ctx.strokeStyle=hr.kuchi==='wait'?T.accent:T.sub; ctx.stroke(); ctx.fillStyle=hr.kuchi==='wait'?T.accent:T.sub; }
    ctx.font=`900 ${fs}px ${F.body}`; ctx.textAlign='center'; ctx.fillText(label,px+pw/2,py+ph/2+fs*.36); ctx.textAlign='left'; };
  if(label){
    const fs=Math.round(clamp(h*.115,11,22)); ctx.font=`900 ${fs}px ${F.body}`; const lw=ctx.measureText(label).width;
    const pw=lw+fs*1.3, ph=fs*1.9;
    if(right-pw-tx >= w*.5){ paintBadge(right-pw,y+(h-ph)/2,pw,ph,fs); right=right-pw-ip*.7; } else inlineBadge=true;
  }
  const tw=Math.max(40,right-tx);
  const sA=clamp(h*.105,8,21), sB=clamp(h*.25,11,52), sC=clamp(h*.125,8,26), sD=clamp(h*.108,8,22), g=h*.035;
  const chipH=sA*1.55; const block=chipH+g+sB+g+sC+g*.7+sD; let cy=y+(h-block)/2;
  const club=clubLabel(hr);
  const inlineB=(x0)=>{ const fs=Math.round(sA); ctx.font=`900 ${fs}px ${F.body}`; const pw=ctx.measureText(label).width+fs*1.2; if(x0+pw<=right){ paintBadge(x0,cy,pw,chipH,fs); return x0+pw; } return 0; };
  let cx0=tx, chipEnd=tx;
  if(inlineBadge&&scr){ /* 取消・除外は必ず見せたいので、狭い時はクラブ名より前に置く */
    const fs=Math.round(sA); ctx.font=`900 ${fs}px ${F.body}`; const pw=ctx.measureText(label).width+fs*1.2; paintBadge(tx,cy,pw,chipH,fs); cx0=tx+pw+sA*.6; chipEnd=cx0; }
  /* 性齢・斤量（10/19〜、設定で切替）: 性齢はクラブ名の右、斤量は3行目の騎手名の前（10/22〜、私の指定。3行目の項目の区切りは「 / 」をやめて全角スペース。以前は「牡4 57kg」をクラブ名の右）。
     性齢の場所が足りなければクラブ名を少し（15%まで）縮める。それでも入らない時（狭い行で口取りバッジもある時など）だけ3行目の最後 */
  const showAw=S.showAgeWeight!==false, kg=showAw?kgText(hr.weight):'';
  const aw=showAw?(hr.sexAge||''):''; let awLine='';
  const awFs=Math.round(sA); ctx.font=`700 ${awFs}px ${F.body}`; const awW=aw?ctx.measureText(aw).width:0, awGap=sA*.6;
  const kuchiInline=inlineBadge&&!scr&&label;
  /* 狭い行の口取りバッジ: クラブ名の右に必ず入るよう、その分クラブ名を縮める（10/19 修正。以前は入る時だけ描いていて、縦長2列ではほぼ出ていなかった） */
  let kbw=0; if(kuchiInline){ ctx.font=`900 ${Math.round(sA)}px ${F.body}`; kbw=ctx.measureText(label).width+Math.round(sA)*1.2; }
  let awInChip=!!aw&&!kuchiInline;
  if(club){
    const textMax=Math.max(20,tx+tw-cx0-sA*1.15-(kbw?kbw+sA*.6:0)), roomWithAw=textMax-awW-awGap;
    if(awInChip){ ctx.font=`700 ${Math.round(sA)}px ${F.body}`; if(ctx.measureText(club).width*.85>roomWithAw) awInChip=false; }
    const f=fit(ctx,club,700,F.body,sA,awInChip?Math.max(20,roomWithAw):textMax); const cw=ctx.measureText(f.t).width+sA*1.1;
    rr(ctx,cx0,cy,cw,chipH,chipH*.25); ctx.fillStyle=T.chipBg; ctx.fill(); ctx.fillStyle=T.chipFg; ctx.fillText(f.t,cx0+sA*.55,cy+chipH*.5+f.s*.36);
    chipEnd=cx0+cw; if(kuchiInline) chipEnd=inlineB(cx0+cw+sA*.6)||chipEnd; }
  else if(kuchiInline) chipEnd=inlineB(tx)||tx;
  if(aw){ const ax=chipEnd>tx?chipEnd+awGap:tx;
    if(ax+awW<=right){ ctx.font=`700 ${awFs}px ${F.body}`; ctx.fillStyle=scr?T.sub:T.fg; ctx.globalAlpha=scr?1:.85; ctx.fillText(aw,ax,cy+chipH*.5+awFs*.36); ctx.globalAlpha=1; }
    else awLine=aw; }
  cy+=chipH+g;
  /* 馬名は省略しない（10/30〜、結果カードと同じ drawNameNoCut。以前は入らない時「…」で切っていた） */
  const nm=drawNameNoCut(ctx,hr.name||'（馬名）',sB,tx,cy+sB*.86,tw,scr?T.sub:T.fg);
  if(scr){ ctx.fillRect(tx,cy+sB*.86-nm.s*.34,nm.w,Math.max(2,nm.s*.07)); }
  cy+=sB+g;
  const lc=hr.raceName||'';
  const c=fit(ctx,lc,700,F.body,sC,tw); ctx.fillStyle=T.fg; ctx.fillText(c.t,tx,cy+sC*.86); cy+=sC+g*.7;
  /* 性齢を3行目に回した時は、距離と斤量の間に置き（10/22、私の指定）、「発走」を省いて文字が小さくなりすぎないようにする */
  const ld=[hr.time?hr.time+(awLine?'':' 発走'):'', (hr.surface||'')+(hr.dist?hr.dist+'m':''), awLine, kg, hr.jockey].filter(Boolean).join('　');
  const d=fit(ctx,ld,500,F.body,sD,tw); ctx.fillStyle=T.sub; ctx.fillText(d.t,tx,cy+sD*.86);
}

/* 馬名を省略せずに描く（結果カードから移した。10/30〜出走カードも）: 72%まで縮め、それでも入らなければ横に詰める。戻り値 {w: 描いた幅, s: 文字の大きさ} */
function drawNameNoCut(ctx,t,size,x,base,maxW,color){
  let s=Math.round(size); ctx.font=`900 ${s}px ${F.body}`; let w=ctx.measureText(t).width;
  const min=Math.round(size*.72);
  while(w>maxW && s>min){ s--; ctx.font=`900 ${s}px ${F.body}`; w=ctx.measureText(t).width; }
  ctx.fillStyle=color;
  if(w<=maxW){ ctx.fillText(t,x,base); return {w,s}; }
  ctx.save(); ctx.translate(x,base); ctx.scale(maxW/w,1); ctx.fillText(t,0,0); ctx.restore(); return {w:maxW,s};
}
/* 命名馬のバッジ（10/30〜）: アクセント色の塗り。角を小さく丸めて、丸い口取りのバッジと見分けられるようにする */
const NAMED_LABEL='命名馬';
function namedBadgeW(ctx,fs){ ctx.font=`900 ${fs}px ${F.body}`; return ctx.measureText(NAMED_LABEL).width+fs*1.1; }
function drawNamedBadge(ctx,x,mid,fs,T){
  const w=namedBadgeW(ctx,fs), h=fs*1.55; rr(ctx,x,mid-h/2,w,h,h*.22); ctx.fillStyle=T.accent; ctx.fill();
  ctx.fillStyle=T.accentInk; ctx.textAlign='left'; ctx.fillText(NAMED_LABEL,x+fs*.55,mid+fs*.36); return w; }
/* 勝負服に重ねる命名馬のバッジ（10/30〜）: 勝負服の幅の中央、裾に重ねる。
   勝負服の柄と混ざらないよう背景の色で縁取る。文字は勝負服の幅に入るまで縮める。dim は取消・除外・競走中止など（薄く） */
function drawNamedOnSilks(ctx,sx,sy,ss,fsBase,T,dim){
  let fs=Math.round(fsBase); while(fs>7&&namedBadgeW(ctx,fs)>ss*.92) fs--;
  const w=namedBadgeW(ctx,fs), h=fs*1.55, x=sx+(ss-w)/2, mid=sy+ss*.9;
  if(dim) ctx.globalAlpha=.55;
  rr(ctx,x,mid-h/2,w,h,h*.22); ctx.lineWidth=Math.max(2,fs*.22); ctx.strokeStyle=T.bg; ctx.stroke();
  drawNamedBadge(ctx,x,mid,fs,T); ctx.globalAlpha=1; }

/* 斤量の表示: 57.0 → 57kg、57.5 → 57.5kg */
function kgText(w){ const n=parseFloat(String(w||'').replace(/[^\d.]/g,'')); return n?(Number.isInteger(n)?n:n.toFixed(1))+'kg':''; }
function rangeText(horses){
  const ds=horses.map(h=>h.date).filter(Boolean).sort(); if(!ds.length) return '';
  const a=parseDate(ds[0]), b=parseDate(ds[ds.length-1]); if(!a) return '';
  const fa=`${a.y}.${pad2(a.m)}.${pad2(a.d)} ${WD_EN[a.wd]}`;
  if(ds[0]===ds[ds.length-1]) return fa;
  return `${fa}  –  ${pad2(b.m)}.${pad2(b.d)} ${WD_EN[b.wd]}`;
}

/* ---------- render ---------- */
const imgCache={};
function loadImg(src){ if(imgCache[src]) return Promise.resolve(imgCache[src]); return new Promise(r=>{ const i=new Image(); i.onload=()=>{imgCache[src]=i;r(i);}; i.onerror=()=>r(null); i.src=src; }); }

window.RCCore = { IPA, F, CLUBS, COLORS, clubById, SIZES, WD, WD_EN, WAKU, DEFAULT_SILKS, THEMES, DEFAULT_CUSTOM, hexRgb, rgbHex, mix, luminance, customTheme, pad2, STATUS_LABEL, runCount, clamp, parseDate, clubLabel, silksSpec, silksImgSrc, silksHex, rr, ls, fit, mulberry, SHAPES, OUTLINE, BODY_CLIP, SEAM, SLEEVE_AXIS, SPAN_KEYS, ALIAS, ARM_FROM_REF, _p2d, p2d, p2dAll, star, drawRefPattern, drawSleeveMotif, drawSilks, drawSilksImg, drawBg, VENUE_ORDER, EAST_MAIN, WEST_MAIN, num, venueRanker, entriesOf, GAP, DAY, VEN, colUnits, bandsOf, ROW_PREF, headerTop, flowCols, layoutOf, bandUnits, splitRows, drawVenue, drawDay, drawRow, drawNameNoCut, NAMED_LABEL, namedBadgeW, drawNamedBadge, drawNamedOnSilks, kgText, rangeText, imgCache, loadImg };
})();
