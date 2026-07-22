#!/bin/bash
# ダブルクリックで Kasane のサーバーを起動します
cd "$(dirname "$0")"
PORT=8787
echo "Kasane を起動中..."
echo
echo "  このMac            : http://localhost:$PORT"

# Wi-Fiが en0 とは限らない（有線やUSBテザリングがあると en1 以降になる）のでまとめて調べる
for ifc in en0 en1 en2 en3 en4 en5 en6 en7; do
  ip=$(ipconfig getifaddr "$ifc" 2>/dev/null)
  [ -n "$ip" ] && echo "  スマホ（同じWi-Fi）: http://$ip:$PORT"
done

TS=$(tailscale ip -4 2>/dev/null || /Applications/Tailscale.app/Contents/MacOS/Tailscale ip -4 2>/dev/null)
[ -n "$TS" ] && echo "  スマホ（外出先でも）: http://$TS:$PORT"
echo
# すでに起動している場合は二重起動しない（ポート衝突でエラーにならないように）
if lsof -nP -iTCP:$PORT -sTCP:LISTEN >/dev/null 2>&1; then
  echo "すでに起動しています。ブラウザを開きます。"
  open "http://localhost:$PORT"
  exit 0
fi

echo "止めるときはこのウィンドウで Control+C"
echo
sleep 1
open "http://localhost:$PORT"
exec python3 -m http.server $PORT
