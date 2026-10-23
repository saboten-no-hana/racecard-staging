# racecard-staging（出資馬出走カードメーカーのテスト環境）

本番（https://saboten-no-hana.github.io/racecard/ 、リポジトリ saboten-no-hana/racecard）に入れる前の変更を、
実際の GitHub Pages で確かめるための場所です。**利用者向けではありません。**

- テスト環境: https://saboten-no-hana.github.io/racecard-staging/
- ページの上部に赤い帯（テスト環境・元のコミット）が出ます。検索エンジンには載せません（noindex）

## しくみ
- `site/` … 本番リポジトリのあるコミットの中身をそのまま写したもの（`sync.sh` で作る。`.github/` は写さない）
- `stage/build.py` … `site/` をコピーして、本番と混ざらないように次だけ書き換える（本番のコードは変えない）
  - 保存データのキー `racecard.…` → `racecard-stg.…`（本番と同じドメインなので、そのままだと★などを共有してしまう）
  - Service Worker のキャッシュ名 `racecard-…` → `racecard-stg-…`
  - noindex・タイトルの【テスト】・上部の帯、ホーム画面に追加した時の名前
  - `data/races.json` を本番の最新に差し替え（本番リポジトリから取る。JRA にはアクセスしない）
- `.github/workflows/deploy.yml` … push・手動・1日2回（11:20・18:20 JST、races.json を本番にそろえる）に反映
- 出馬表の取得（fetch-races）はテスト環境では動かしません

## 反映のしかた
```sh
./sync.sh ../racecard <コミットまたはブランチ>
git add -A && git commit -m "テスト環境に反映: <コミット> <内容>" && git push
```
確かめて問題なければ、**同じコミット**を本番の main に入れます。

## テスト環境で★を使う
保存データは本番と別なので、最初は★がありません。本番の「★を他の端末に引き継ぐ」のリンク（`#star=…`）の
`/racecard/` を `/racecard-staging/` に変えて開けば、本番の★をテスト環境に読み込めます（本番側は変わりません）。

## 注意
- コミットの作成者のメールアドレスは本番と同じ決まり（saboten.github@gmail.com・GitHub の noreply・Anthropic の noreply だけ）。push の前に `python3 stage/check_authors.py`
