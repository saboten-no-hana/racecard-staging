/*
  一口馬主クラブの固定データ
  - name   : 募集クラブ名（画像に表示する名前）
  - owner  : JRA出馬表に載る馬主名義（自動取得で出資馬を見つけるのに使う）
  - silks  : 勝負服。色はJRAの勝負服で使われる13色の名前で書く
             body=胴の色 / pattern=胴の柄 / pc=胴の柄の色
             sleeve=袖の色 / sp=袖の柄 / spc=袖の柄の色
             null は「未登録」（画面で個別に設定できる）
  - img    : 勝負服画像（Wikimedia Commons の CC0 画像。.github/workflows/fetch-silks.yml が silks/ に取得する）
             画像がある場合は画像を優先し、silks は画像が読めない時の代わりに使う
  - text   : 勝負服の登録表記（確認用）
  勝負服の出典: Wikipedia の各クラブ法人の記事とその掲載画像（2026年10月時点）。
  ブルーミングホースクラブ（2025年発足、クラブ法人 Blooming Racing）は Wikipedia の記事がないため画像なし。
  勝負服は会員提供の画像から判定して手描き（胴 赤・白鋸歯形、袖 白・赤二本輪）。text は JRA の表記順に沿って組んだもの。
  ゴールドホースクラブ（ゴールドレーシング）はほぼ休眠のため入れていない。

  柄の値（JRA の標示。形は silks-shapes.js＝Wikipedia「勝負服 (競馬)」の参考画像。index.html の BODY_PATTERNS / SLEEVE_PATTERNS と同じ）:
          胴: plain 無地 / wa1〜wa3 一〜三本輪 / ichimonji 一文字（胴と袖） / obi 帯 / yamagatawa1 山形一本輪 /
              yamagata 山形二本輪 / yamagata3 山形三本輪 / yamagata1 山形一文字（胴と袖） / yamagataobi 山形帯 /
              hishiyamagata 菱山形 / kyoshi 鋸歯形（胴と袖） / tasuki 襷 / jujitasuki 十字襷 / tate 縦縞 / check 格子 /
              genroku 元禄 / diamond ダイヤモンド / uroko うろこ / igeta 井桁絣 / dots 玉霰 / stars 星散 / janome 蛇目散 / zenigata 銭形散
          袖: plain / wa1〜wa3 / yamagatawa1 / yamagata / yamagata3 / hishiyamagata / tate / check / genroku / diamond / uroko /
              igeta / dots / stars / janome / zenigata
*/
window.CLUBS = [
  {id:'carrot', img:'silks/Owner_Carrot_Farm.svg',   name:'キャロットクラブ',               owner:'キャロットファーム',             text:'緑、白二本輪、白袖赤一本輪',   silks:{body:'緑',pattern:'wa2',pc:'白',sleeve:'白',sp:'wa1',spc:'赤'}},
  {id:'silk', img:'silks/Owner_Silk_Racing.svg',     name:'シルク・ホースクラブ',           owner:'シルクレーシング',               text:'水色、赤玉霰、袖赤一本輪',     silks:{body:'水色',pattern:'dots',pc:'赤',sleeve:'水色',sp:'wa1',spc:'赤'}},
  {id:'sunday', img:'silks/Owner_Sunday_Racing.svg',   name:'サンデーサラブレッドクラブ',     owner:'サンデーレーシング',             text:'黒、赤十字襷、袖黄縦縞',       silks:{body:'黒',pattern:'jujitasuki',pc:'赤',sleeve:'黒',sp:'tate',spc:'黄'}},
  {id:'shadai', img:'silks/Owner_Shadai_Race_Horse.svg',   name:'社台サラブレッドクラブ',         owner:'社台レースホース',               text:'黄、黒縦縞、袖青一本輪',       silks:{body:'黄',pattern:'tate',pc:'黒',sleeve:'黄',sp:'wa1',spc:'青'}},
  {id:'g1', img:'silks/Owner_G1_Racing.svg',       name:'G1サラブレッドクラブ',           owner:'G1レーシング',                   text:'黒、赤襷、袖赤一本輪',         silks:{body:'黒',pattern:'tasuki',pc:'赤',sleeve:'黒',sp:'wa1',spc:'赤'}},
  {id:'tokyo', img:'silks/Owner_Tokyo_Racing.svg',    name:'東京サラブレッドクラブ',         owner:'東京ホースレーシング',           text:'赤、白星散、袖白一本輪',       silks:{body:'赤',pattern:'stars',pc:'白',sleeve:'赤',sp:'wa1',spc:'白'}},
  {id:'normandy', img:'silks/Owner_Normandy_Thoroughbred_Racing.svg', name:'ノルマンディーオーナーズクラブ', owner:'ノルマンディーサラブレッドレーシング', text:'水色、白山形二本輪、袖白縦縞', silks:{body:'水色',pattern:'yamagata',pc:'白',sleeve:'水色',sp:'tate',spc:'白'}},
  {id:'hiroo', img:'silks/Owner_Hiroo_Race_002.svg',    name:'広尾サラブレッド倶楽部',         owner:'広尾レース',                     text:'青、袖緑一本輪',               silks:{body:'青',pattern:'plain',pc:'青',sleeve:'青',sp:'wa1',spc:'緑'}},
  {id:'dmm', img:'silks/Owner_DMMDreamclub.svg',      name:'DMMバヌーシー',                  owner:'DMMドリームクラブ',              text:'黒、緑山形一文字',             silks:{body:'黒',pattern:'yamagata1',pc:'緑',sleeve:'黒',sp:'plain',spc:'黒'}},
  {id:'lord', img:'silks/Owner_Lord_Horse_Club.svg',     name:'ロードサラブレッドオーナーズ',   owner:'ロードホースクラブ',             text:'白、青一本輪、青袖',           silks:{body:'白',pattern:'wa1',pc:'青',sleeve:'青',sp:'plain',spc:'青'}},
  {id:'insel', img:'silks/Owner_Insel_Racing.svg',    name:'インゼルサラブレッドクラブ',     owner:'インゼルレーシング',             text:'白、鼠元禄',                   silks:{body:'白',pattern:'genroku',pc:'鼠',sleeve:'白',sp:'genroku',spc:'鼠'}},
  {id:'ruffian', img:'silks/Owner_Thoroughbred_Club_Ruffian.svg',  name:'ラフィアンターフマンクラブ',     owner:'サラブレッドクラブ・ラフィアン', text:'赤、緑袖赤一本輪',             silks:{body:'赤',pattern:'plain',pc:'赤',sleeve:'緑',sp:'wa1',spc:'赤'}},
  {id:'win', img:'silks/Owner_Win.svg',      name:'ウインレーシングクラブ',         owner:'ウイン',                         text:'',                             silks:null},
  {id:'ygg', img:'silks/Owner_YGG_Horse_Club.svg',      name:'YGGオーナーズクラブ',            owner:'YGGホースクラブ',                text:'',                             silks:null},
  {id:'union', img:'silks/Owner_Hidaka_Breeders_Union.svg',    name:'ユニオンオーナーズクラブ',       owner:'ヒダカ・ブリーダーズ・ユニオン', text:'緑、赤襷、赤袖白一本輪',       silks:{body:'緑',pattern:'tasuki',pc:'赤',sleeve:'赤',sp:'wa1',spc:'白'}},
  {id:'taiki', img:'silks/Owner_Taiki_Farm.svg',    name:'大樹レーシングクラブ',           owner:'大樹ファーム',                   text:'緑、白星散、袖白縦縞',         silks:{body:'緑',pattern:'stars',pc:'白',sleeve:'緑',sp:'tate',spc:'白'}},
  {id:'lion', img:'silks/Owner_Lion_Race_Horse.svg',     name:'ライオンレースホース',           owner:'ライオンレースホース',           text:'黄、黒山形二本輪、白袖赤一本輪', silks:{body:'黄',pattern:'yamagata',pc:'黒',sleeve:'白',sp:'wa1',spc:'赤'}},
  {id:'yushun', img:'silks/Owner_Yushun_Horse_Club_002.svg',   name:'友駿ホースクラブ',               owner:'友駿ホースクラブ',               text:'青、赤袖、白三本輪',           silks:{body:'青',pattern:'wa3',pc:'白',sleeve:'赤',sp:'wa3',spc:'白'}},
  {id:'laurel', img:'silks/Owner_Laurel_Racing_Club.svg',   name:'ローレルクラブ',                 owner:'ローレルレーシング',             text:'海老、白玉霰',                 silks:{body:'海老',pattern:'dots',pc:'白',sleeve:'海老',sp:'dots',spc:'白'}},
  {id:'turfite', img:'silks/Owner_Turf_Sport.svg',  name:'ターファイトクラブ',             owner:'ターフ・スポート',               text:'黒、桃格子、桃袖',             silks:{body:'黒',pattern:'check',pc:'桃',sleeve:'桃',sp:'plain',spc:'桃'}},
  {id:'green', img:'silks/Owner_Green_Farm.svg',    name:'グリーンファーム愛馬会',         owner:'グリーンファーム',               text:'',                             silks:null},
  {id:'waraukado', img:'silks/Owner_Fukukitaru.svg',name:'ワラウカド',                     owner:'フクキタル',                     text:'',                             silks:null},
  {id:'kyoto', img:'silks/Owner_Kyoto_Horse_Racing.svg',    name:'京都サラブレッドクラブ',         owner:'京都ホースレーシング',           text:'',                             silks:null},
  {id:'blooming', img:'',                                name:'ブルーミングホースクラブ',       owner:'Blooming Racing',               text:'赤、白袖赤二本輪、白鋸歯形',   silks:{body:'赤',pattern:'kyoshi',pc:'白',sleeve:'白',sp:'wa2',spc:'赤'}}
];

/* JRAの勝負服に使われる13色 */
window.SILK_COLORS = {
  '白':'#ffffff','黒':'#1b1b1d','赤':'#d4252b','青':'#1f4fa8','黄':'#f5cf1d','緑':'#1b7a3e','桃':'#f2a2c0',
  '水色':'#71c4ea','紫':'#6a2e8f','薄紫':'#b9a2d6','茶':'#7a4a24','海老':'#7b2232','鼠':'#8e8e90'
};
