#!/bin/bash
# ダブルクリックすると、iPhoneで開くべきアドレスを表示します。
# ・URLをクリップボードにコピー
# ・QRコードを表示（iPhoneのカメラを向けるだけで開けます）
# ・Tailscaleの設定が消えていたら、その場で入れ直します

cd "$(dirname "$0")" || exit 1
export LANG=ja_JP.UTF-8

PORT=8787
HTTPS_PORT=8443

echo
echo "  Kasane — iPhoneで開くアドレス"
echo "  ================================"
echo

# --- Tailscale を探す（PATHに無いことが多いのでアプリの中も見る） ---
TS=""
for c in tailscale /usr/local/bin/tailscale /opt/homebrew/bin/tailscale \
         /Applications/Tailscale.app/Contents/MacOS/Tailscale; do
  if command -v "$c" >/dev/null 2>&1; then TS="$c"; break; fi
done

if [ -z "$TS" ]; then
  echo "  Tailscale が見つかりませんでした。"
  echo "  Tailscale.app がインストールされているか確認してください。"
  echo
  echo "  ※ 同じWi-Fiの中だけなら、次のアドレスでも開けます（オフラインでは使えません）:"
  for ifc in en0 en1 en2 en3; do
    ip=$(ipconfig getifaddr "$ifc" 2>/dev/null)
    [ -n "$ip" ] && echo "      http://$ip:$PORT"
  done
  echo
  read -r -p "  Enterで閉じます " _
  exit 1
fi

# --- 自分のマシン名（tailnet内のドメイン） ---
NAME=$("$TS" status --json 2>/dev/null \
       | python3 -c "import sys,json;print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))" 2>/dev/null)

if [ -z "$NAME" ]; then
  echo "  Tailscale にログインできていないようです。"
  echo "  メニューバーの Tailscale から「Log in」してから、もう一度この $(basename "$0") を開いてください。"
  echo
  read -r -p "  Enterで閉じます " _
  exit 1
fi

URL="https://$NAME:$HTTPS_PORT"

# --- HTTPSの受け口（tailscale serve）が生きているか ---
if ! "$TS" serve status 2>/dev/null | grep -q ":$HTTPS_PORT"; then
  echo "  HTTPSの設定が入っていないので、いま入れます…"
  if "$TS" serve --bg --https=$HTTPS_PORT "http://127.0.0.1:$PORT" >/dev/null 2>&1; then
    echo "  → 設定しました"
  else
    echo "  → 設定できませんでした。手動でこれを実行してください:"
    echo "     $TS serve --bg --https=$HTTPS_PORT http://127.0.0.1:$PORT"
  fi
  echo
fi

# --- サーバー（tools/server.py）が動いているか ---
if ! lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "  ⚠ アプリのサーバーが動いていません（ポート $PORT）。"
  echo "    ログイン時に自動起動する設定です。今すぐ動かすなら:"
  echo "      launchctl bootstrap gui/\$(id -u) ~/Library/LaunchAgents/com.morikastu.kasane.plist"
  echo "    それでも駄目なら start.command をダブルクリックしてください。"
  echo
fi

# --- 表示 ---
printf '%s\n' "$URL" | pbcopy 2>/dev/null && COPIED=1

echo "  ┌────────────────────────────────────────"
echo "  │  $URL"
echo "  └────────────────────────────────────────"
[ -n "$COPIED" ] && echo "  （クリップボードにコピーしました）"
echo
echo "  iPhoneのカメラをこのQRコードに向けてください:"
echo
python3 tools/qr.py "$URL" 2>/dev/null || echo "  （QRコードを表示できませんでした。上のURLを手で入力してください）"
echo
echo "  開いたら Safari の共有ボタン →「ホーム画面に追加」。"
echo "  記録はアドレスごとに別々に保存されます。今後はこのアイコンからだけ開いてください。"
echo
echo "  このMacで使うとき: http://localhost:$PORT"
echo
read -r -p "  Enterで閉じます " _
