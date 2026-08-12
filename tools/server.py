#!/usr/bin/env python3
"""Kasane 配信サーバー（python -m http.server の置き換え）。

これまでの静的配信に加えて、毎朝の通知（Web Push）のために2つだけ受け口を足したもの。
  POST /subscribe  … iPhoneからの購読情報を push-subs.json に保存する
  POST /push-test  … 登録済みの全端末にテスト通知を送る（設定タブの「テスト通知」ボタン用）
  POST /backup     … iPhone側の記録を backups/ に丸ごと保存する（自動バックアップ）
  POST /analyze    … 食事の写真をClaudeに送り、カロリーとPFCの推定を返す（食事タブの「写真から入力」）
それ以外のリクエストは従来どおり ~/kasane を配信する。

launchd(com.morikastu.kasane)がこのスクリプトを8787で起動し、
Tailscale の HTTPS(8443) がここに転送している。
"""
import json, os, sys, time
import urllib.request, urllib.error
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

TOOLS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TOOLS)                     # ~/kasane
SUBS = os.path.join(TOOLS, 'push-subs.json')      # 購読の保存先（gitに上げない）
BACKUPS = os.path.join(ROOT, 'backups')           # 記録の保存先（gitに上げない）
KEEP = 30                                         # 残す世代数（1日1ファイル＝約1か月分）
KEY_FILE = os.path.join(TOOLS, 'anthropic-key.txt')  # 写真解析用のAPIキー（gitに上げない）
# 解析はテストで差し替えられるようURLを環境変数で上書きできる。普段は触らない
API_URL = os.environ.get('ANTHROPIC_API_URL', 'https://api.anthropic.com/v1/messages')
MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-opus-5')
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


def anthropic_key():
    """環境変数 → tools/anthropic-key.txt の順で探す。無ければ None"""
    k = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if k:
        return k
    try:
        return open(KEY_FILE).read().strip() or None
    except OSError:
        return None


# 写真から返してもらう項目。JSONスキーマで縛るので、返答のパースに失敗することがない
ANALYZE_SCHEMA = {
    'type': 'object',
    'properties': {
        'is_food': {'type': 'boolean', 'description': '写真に食べ物・飲み物が写っているか'},
        'name': {'type': 'string', 'description': '料理の短い名前（日本語、20文字以内）'},
        'kcal': {'type': 'integer', 'description': '写っている食事全体の推定カロリー'},
        'p': {'type': 'number', 'description': 'タンパク質g'},
        'f': {'type': 'number', 'description': '脂質g'},
        'c': {'type': 'number', 'description': '炭水化物g'},
        'note': {'type': 'string', 'description': '内訳と推定の根拠を日本語で1〜2文'},
    },
    'required': ['is_food', 'name', 'kcal', 'p', 'f', 'c', 'note'],
    'additionalProperties': False,
}

ANALYZE_PROMPT = (
    'この写真に写っている食事の栄養を推定してください。'
    '複数の品が写っていれば合計で出してください。'
    '量が判別しづらい場合は、日本の一般的な1人前として見積もってください。'
    'note には内訳（何をどれくらいと見たか）を短く書いてください。'
    '食べ物や飲み物が写っていなければ is_food を false にしてください。'
)


def analyze_photo(image_b64, media_type):
    """写真をClaude APIに送ってカロリーとPFCの推定を受け取る。

    Anthropic公式のSDKではなく標準ライブラリのurllibで呼んでいるのは、
    tools/ を「Macに最初から入っているものだけで動く」状態に保つため（qr.py と同じ方針）。
    写真はAPIに送るだけで、このサーバーには保存しない。
    戻り値は (HTTPステータス, レスポンスdict)。
    """
    key = anthropic_key()
    if not key:
        return 503, {'ok': False, 'code': 'no_key',
                     'error': 'APIキーが設定されていません。iMacの tools/anthropic-key.txt にキーを保存してください（READMEの「写真から入力」参照）'}
    body = json.dumps({
        'model': MODEL,
        'max_tokens': 4000,   # 考える途中のぶんも含む上限。回答自体は短い
        'output_config': {
            'effort': 'low',  # 一枚の写真の見積もりに深い思考は要らない。待ち時間を優先
            'format': {'type': 'json_schema', 'schema': ANALYZE_SCHEMA},
        },
        'messages': [{'role': 'user', 'content': [
            {'type': 'image', 'source': {'type': 'base64',
                                         'media_type': media_type, 'data': image_b64}},
            {'type': 'text', 'text': ANALYZE_PROMPT},
        ]}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, method='POST', headers={
        'x-api-key': key,
        'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e)['error']['message']
        except Exception:
            msg = 'HTTP %s' % e.code
        if e.code == 401:
            return 502, {'ok': False, 'code': 'auth', 'error': 'APIキーが正しくないようです。tools/anthropic-key.txt を確認してください'}
        if e.code == 429:
            return 502, {'ok': False, 'code': 'rate', 'error': '少し時間をおいてもう一度試してください'}
        return 502, {'ok': False, 'code': 'api', 'error': msg[:200]}
    except Exception as e:
        return 502, {'ok': False, 'code': 'network', 'error': 'iMacからAPIに接続できませんでした（%s）' % type(e).__name__}
    # 安全側の判定で断られることがある（stop_reason=refusal）。食事の写真ではまず起きない
    if resp.get('stop_reason') == 'refusal':
        return 200, {'ok': False, 'code': 'refusal', 'error': 'この写真は解析できませんでした'}
    text = next((b.get('text') for b in resp.get('content', [])
                 if b.get('type') == 'text'), None)
    if not text:
        return 502, {'ok': False, 'code': 'empty', 'error': '解析結果を受け取れませんでした'}
    data = json.loads(text)   # スキーマで縛っているので失敗しない
    if not data.get('is_food'):
        return 200, {'ok': False, 'code': 'not_food', 'error': '食べ物が写っていないようです。もう一度撮ってみてください'}
    return 200, {'ok': True, 'name': data['name'][:40], 'kcal': int(data['kcal']),
                 'p': round(float(data['p']), 1), 'f': round(float(data['f']), 1),
                 'c': round(float(data['c']), 1), 'note': data['note'][:200]}


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
        if self.path == '/analyze':
            try:
                d = json.loads(raw)
                img = d['image']
                mt = d.get('media_type', 'image/jpeg')
                assert mt in ('image/jpeg', 'image/png', 'image/webp') and len(img) > 100
            except Exception:
                return self._json(400, {'ok': False, 'error': 'bad request'})
            try:
                code, resp = analyze_photo(img, mt)
            except Exception as e:
                return self._json(500, {'ok': False, 'error': '解析に失敗しました（%s）' % type(e).__name__})
            return self._json(code, resp)
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
