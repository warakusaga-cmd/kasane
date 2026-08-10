#!/usr/bin/env python3
"""Kasane 配信サーバー（python -m http.server の置き換え）。

これまでの静的配信に加えて、毎朝の通知（Web Push）のために2つだけ受け口を足したもの。
  POST /subscribe  … iPhoneからの購読情報を push-subs.json に保存する
  POST /push-test  … 登録済みの全端末にテスト通知を送る（設定タブの「テスト通知」ボタン用）
  POST /backup     … iPhone側の記録を backups/ に丸ごと保存する（自動バックアップ）
  GET  /inbox      … クロコが用意した入力待ちの記録（tools/inbox.json）をアプリへ渡す
  POST /inbox-done … アプリが取り込み終えたら inbox.json を消す（二重取り込み防止）
それ以外のリクエストは従来どおり ~/kasane を配信する。

launchd(com.morikastu.kasane)がこのスクリプトを8787で起動し、
Tailscale の HTTPS(8443) がここに転送している。
"""
import json, os, sys, time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)                     # ~/kasane
SUBS = os.path.join(TOOLS, 'push-subs.json')      # 購読の保存先（gitに上げない）
BACKUPS = os.path.join(ROOT, 'backups')           # 記録の保存先（gitに上げない）
KEEP = 30                                         # 残す世代数（1日1ファイル＝約1か月分）
MAX_BODY = 20 * 1024 * 1024                       # 受け取る上限。壊れた巨大POSTでディスクを埋めない
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787


def load_subs():
    try:
        return json.load(open(SUBS))
    except Exception:
        return []


def save_subs(subs):
    json.dump(subs, open(SUBS, 'w'), indent=1)


def volume(d):
    """バックアップに入っている記録の量。世代を比べて「減っていないか」を見るためだけに使う。"""
    return (len(d.get('workouts') or []) + len(d.get('weights') or {})
            + len(d.get('walks') or {}))


def save_backup(data):
    """その日のファイルに上書き保存し、古い世代を間引く。戻り値は (ファイル名, 記録件数, 保存したか)。

    1日1ファイルなのは、同じ日に何度も開いても世代が無駄に増えないようにするため。
    中身は設定タブの「バックアップを書き出す」と同じ形なので、そのまま読み込みに使える。

    記録が減る上書きは拒否する。記録の入っていない端末（PCのブラウザなど）で
    同じURLを開くと、その日のせっかくのバックアップが空で潰れてしまうため。
    """
    os.makedirs(BACKUPS, exist_ok=True)
    name = 'kasane-%s.json' % time.strftime('%Y-%m-%d')
    cnt = len(data.get('workouts') or [])
    try:
        prev = json.load(open(os.path.join(BACKUPS, name)))
        # トレーニングだけでなく体重・ウォーキングも数える。
        # 体重しか付けていない日に、空の端末で上書きされるのを防ぐため
        if volume(prev) > volume(data):
            return name, cnt, False
    except Exception:
        pass                                          # 初回・壊れている場合はそのまま保存する
    tmp = os.path.join(BACKUPS, name + '.tmp')
    # 書き込み途中で落ちても前回分が壊れないように、一時ファイルに書いてから置き換える
    with open(tmp, 'w') as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(tmp, os.path.join(BACKUPS, name))
    old = sorted(n for n in os.listdir(BACKUPS) if n.endswith('.json'))
    for n in old[:-KEEP]:
        try:
            os.remove(os.path.join(BACKUPS, n))
        except OSError:
            pass
    return name, cnt, True


INBOX = os.path.join(TOOLS, 'inbox.json')          # クロコが書く入力待ちファイル（gitに上げない）


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def do_GET(self):
        if self.path == '/inbox':
            try:
                body = open(INBOX, 'rb').read()
                json.loads(body)                   # 壊れたファイルを配らない
            except Exception:
                return self._json(404, {'ok': False})
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_BODY:
            return self._json(413, {'ok': False, 'error': 'too large'})
        raw = self.rfile.read(n) if n else b'{}'
        if self.path == '/backup':
            try:
                data = json.loads(raw)
                # 記録が入っていることだけ確かめる。空データで上書きして前日分を潰さないため
                assert isinstance(data, dict) and isinstance(data.get('workouts'), list)
            except Exception:
                return self._json(400, {'ok': False, 'error': 'bad backup'})
            try:
                name, cnt, wrote = save_backup(data)
            except OSError as e:
                return self._json(500, {'ok': False, 'error': str(e)})
            return self._json(200, {'ok': True, 'saved': name if wrote else None,
                                    'workouts': cnt, 'skipped': not wrote})
        if self.path == '/inbox-done':
            try:
                os.remove(INBOX)
            except OSError:
                pass
            return self._json(200, {'ok': True})
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
