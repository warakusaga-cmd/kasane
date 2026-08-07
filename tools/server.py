#!/usr/bin/env python3
"""Kasane 配信サーバー（python -m http.server の置き換え）。

これまでの静的配信に加えて、毎朝の通知（Web Push）のために2つだけ受け口を足したもの。
  POST /subscribe  … iPhoneからの購読情報を push-subs.json に保存する
  POST /push-test  … 登録済みの全端末にテスト通知を送る（設定タブの「テスト通知」ボタン用）
それ以外のリクエストは従来どおり ~/kasane を配信する。

launchd(com.morikastu.kasane)がこのスクリプトを8787で起動し、
Tailscale の HTTPS(8443) がここに転送している。
"""
import json, os, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)                     # ~/kasane
SUBS = os.path.join(TOOLS, 'push-subs.json')      # 購読の保存先（gitに上げない）
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787


def load_subs():
    try:
        return json.load(open(SUBS))
    except Exception:
        return []


def save_subs(subs):
    json.dump(subs, open(SUBS, 'w'), indent=1)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        raw = self.rfile.read(n) if n else b'{}'
        if self.path == '/subscribe':
            try:
                sub = json.loads(raw)
                assert sub.get('endpoint', '').startswith('https://')
            except Exception:
                return self._json(400, {'ok': False, 'error': 'bad subscription'})
            subs = [s for s in load_subs() if s.get('endpoint') != sub['endpoint']]
            subs.append(sub)
            save_subs(subs)
            return self._json(200, {'ok': True, 'count': len(subs)})
        if self.path == '/unsubscribe':
            try:
                ep = json.loads(raw).get('endpoint', '')
            except Exception:
                ep = ''
            subs = [s for s in load_subs() if s.get('endpoint') != ep]
            save_subs(subs)
            return self._json(200, {'ok': True, 'count': len(subs)})
        if self.path == '/push-test':
            # 送信処理は send_push.py に任せる（VAPID読み込み・失敗purge込み）
            import subprocess
            r = subprocess.run([sys.executable, os.path.join(TOOLS, 'send_push.py'),
                                '--title', 'Kasane', '--body', 'テスト通知です。届いていれば設定は完了です 🎉'],
                               capture_output=True, text=True, timeout=60)
            ok = r.returncode == 0
            return self._json(200 if ok else 500,
                              {'ok': ok, 'detail': (r.stdout or r.stderr).strip()[-300:]})
        return self._json(404, {'ok': False})

    def log_message(self, fmt, *args):
        # launchdのログが体重記録のGETで埋まらない程度に間引く（POSTとエラーだけ残す）
        if self.command == 'POST' or (args and str(args[1]).startswith(('4', '5'))):
            super().log_message(fmt, *args)


if __name__ == '__main__':
    ThreadingHTTPServer(('', PORT), Handler).serve_forever()
