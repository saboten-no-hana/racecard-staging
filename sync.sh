#!/bin/sh
# 本番リポジトリ（racecard）のあるコミットの中身を site/ に写す。
# 使い方: ./sync.sh <racecard のクローン> [コミットまたはブランチ（既定 HEAD）]
# そのあと site/ をコミットして push すると、Actions がテスト環境に反映する。
# 本番のワークフロー（.github/）は写さない（出馬表の取得をテスト環境で動かさないため）。
set -eu
SRC=$1
REV=${2:-HEAD}
HERE=$(cd "$(dirname "$0")" && pwd)
rm -rf "$HERE/site"
mkdir "$HERE/site"
git -C "$SRC" archive "$REV" | tar -x -C "$HERE/site"
rm -rf "$HERE/site/.github"
git -C "$SRC" log -1 --format='%h %s' "$REV" > "$HERE/site/STAGING_SOURCE.txt"
echo "site/ に写した: $(cat "$HERE/site/STAGING_SOURCE.txt")"
