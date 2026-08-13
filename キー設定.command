#!/bin/bash
# 写真解析用のAPIキーを設定します。
# console.anthropic.com で作ったキー（sk-ant-...）をコピーしてから、
# このファイルをダブルクリックしてください。貼り付けなくても、
# コピーしたままEnterを押せばクリップボードから自動で読み取ります。

cd "$(dirname "$0")" || exit 1
export LANG=ja_JP.UTF-8

echo
echo "  Kasane — 写真解析のAPIキー設定"
echo "  ================================"
echo
echo "  console.anthropic.com で作ったキー（sk-ant-...）を"
echo "  貼り付けてEnterを押してください。"
echo "  （すでにコピーしてあるなら、何も貼らずにEnterだけでもOKです）"
echo
printf "  キー: "
read -r KEY
KEY=$(printf '%s' "$KEY" | tr -d '[:space:]')

# 空Enter → クリップボードから取る
if [ -z "$KEY" ]; then
  KEY=$(pbpaste 2>/dev/null | tr -d '[:space:]')
  echo "  （クリップボードから読み取りました）"
fi

case "$KEY" in
  sk-ant-*) ;;
  "")
    echo
    echo "  ❌ 何も入力されていませんでした。キーをコピーしてからやり直してください。"
    echo
    read -r -p "  Enterで閉じます " _
    exit 1;;
  *)
    echo
    echo "  ❌ sk-ant- で始まっていません（読み取れたのは ${KEY:0:12}... ）。"
    echo "     console.anthropic.com の API Keys で作ったキーをコピーし直してください。"
    echo
    read -r -p "  Enterで閉じます " _
    exit 1;;
esac

printf '%s\n' "$KEY" > tools/anthropic-key.txt
chmod 600 tools/anthropic-key.txt
echo
echo "  保存しました。実際に使えるか確認しています…（数秒〜30秒）"
echo
python3 tools/check-key.py
echo
read -r -p "  Enterで閉じます " _
