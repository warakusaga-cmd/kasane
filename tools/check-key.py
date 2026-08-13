#!/usr/bin/env python3
"""APIキーが実際に使える状態かを確かめて、結果を日本語で表示する。

キー設定.command から呼ばれる。Claude APIに最小のリクエスト（1トークン）を送り、
「キーが違う」「クレジット未購入」「ネットに繋がらない」を切り分けて案内する。
費用はほぼゼロ（0.1円未満）。標準ライブラリのみで動く。
"""
import json, os, sys
import urllib.request, urllib.error

TOOLS = os.path.dirname(os.path.abspath(__file__))
KEY_FILE = os.path.join(TOOLS, 'anthropic-key.txt')
API_URL = os.environ.get('ANTHROPIC_API_URL', 'https://api.anthropic.com/v1/messages')
MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-opus-5')


def key():
    k = os.environ.get('ANTHROPIC_API_KEY', '').strip()
    if k:
        return k
    try:
        return open(KEY_FILE).read().strip()
    except OSError:
        return ''


def main():
    k = key()
    if not k:
        print('❌ キーが見つかりません。もう一度 キー設定.command を実行してください。')
        return 1
    if not k.startswith('sk-ant-'):
        print('❌ 保存されている文字列が sk-ant- で始まっていません。')
        print('   コピーし直して、もう一度 キー設定.command を実行してください。')
        return 1
    body = json.dumps({
        'model': MODEL, 'max_tokens': 1,
        'messages': [{'role': 'user', 'content': 'こんにちは'}],
    }).encode()
    req = urllib.request.Request(API_URL, data=body, method='POST', headers={
        'x-api-key': k, 'anthropic-version': '2023-06-01',
        'content-type': 'application/json',
    })
    try:
        with urllib.request.urlopen(req, timeout=60):
            pass
    except urllib.error.HTTPError as e:
        try:
            msg = json.load(e)['error']['message']
        except Exception:
            msg = ''
        low = msg.lower()
        if e.code == 401:
            print('❌ キーが正しくないようです。')
            print('   コピーのときに欠けたり、前後に余計な文字が付いたりしていないか確認して、')
            print('   console.anthropic.com でキーを作り直し、もう一度実行してください。')
        elif 'credit' in low or 'billing' in low or 'purchase' in low:
            print('⚠️ キーは合っていますが、クレジット（前払い残高）がありません。')
            print('   console.anthropic.com の Billing で $5 など最小額をチャージすると使えます。')
            print('   （写真1枚は数円なので、$5でかなり持ちます）')
        else:
            print('❌ APIがエラーを返しました: %s' % (msg[:150] or 'HTTP %s' % e.code))
        return 1
    except Exception as e:
        print('❌ ネットに繋がりませんでした（%s）。' % type(e).__name__)
        print('   Wi-Fiを確認して、もう一度実行してください。')
        return 1
    print('✅ 設定完了！ キーは正しく動いています。')
    print('   iPhoneの食事タブ →「＋ 追加」→「📷 写真から入力」が使えます。')
    return 0


if __name__ == '__main__':
    sys.exit(main())
