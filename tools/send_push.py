#!/usr/bin/env python3
"""登録済みの全端末にWeb Push通知を送る。

毎朝 launchd(com.morikastu.kasane-push) が7:00に実行する。
設定タブの「テスト通知」も server.py 経由でこれを呼ぶ。

使い方: python3 send_push.py [--title タイトル] [--body 本文]
省略時は毎朝の体重リマインダーの文面になる。
"""
import json, os, sys, random

TOOLS = os.path.dirname(os.path.abspath(__file__))
SUBS = os.path.join(TOOLS, 'push-subs.json')
VAPID = os.path.join(TOOLS, 'vapid.json')

# 毎朝の文面。毎日同じだと読み飛ばされるのでいくつか用意して日替わりにする
MORNING = [
    'おはようございます。体重を測って記録しましょう',
    '起きてトイレのあとが一番ブレません。体重どうぞ',
    '今日の体重、まだのようです。10秒で終わります',
    '毎朝の1タップが折れ線グラフになります。体重をどうぞ',
]


def main():
    args = sys.argv[1:]
    def opt(name, default):
        return args[args.index(name) + 1] if name in args else default
    title = opt('--title', 'Kasane')
    body = opt('--body', random.choice(MORNING))

    try:
        subs = json.load(open(SUBS))
    except Exception:
        subs = []
    if not subs:
        print('購読なし（アプリの設定タブで通知をオンにしてください）')
        return 1
    vapid = json.load(open(VAPID))
    pem = os.path.join(TOOLS, 'vapid.pem')   # pywebpushにはPEMのファイルパスで渡す

    from pywebpush import webpush, WebPushException
    sent, alive = 0, []
    for sub in subs:
        try:
            webpush(subscription_info=sub,
                    data=json.dumps({'title': title, 'body': body}),
                    vapid_private_key=pem,
                    vapid_claims={'sub': vapid['sub']})
            sent += 1
            alive.append(sub)
        except WebPushException as e:
            code = getattr(e.response, 'status_code', None)
            if code in (404, 410):
                # 端末側で購読が無効になっている（アプリ削除など）→ リストから外す
                print(f'失効した購読を削除: {sub["endpoint"][:60]}…')
            else:
                print(f'送信失敗({code}): {e}')
                alive.append(sub)   # 一時的な失敗かもしれないので残す
    json.dump(alive, open(SUBS, 'w'), indent=1)
    print(f'{sent}/{len(subs)} 件に送信')
    return 0 if sent else 1


if __name__ == '__main__':
    sys.exit(main())
