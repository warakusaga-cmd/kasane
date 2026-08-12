#!/usr/bin/env python3
"""ターミナルにQRコードを表示する（外部ライブラリなし）。

Macに最初から入っているものだけで動かしたいので、pip も qrencode も使わず自前で組んでいます。
用途はKasaneのURLを出すことだけなので、8bitバイトモード・誤り訂正M・バージョン1〜6に絞っています。
バージョン6で106文字まで入り、Tailscaleのアドレスは40文字前後なので十分です。
（バージョン7以上は「バージョン情報」の埋め込みが必要になり、実機デコーダで確認できていないので
　わざと対応していません。長すぎる場合は例外にして、間違ったQRを出さないようにしています）

    python3 tools/qr.py "https://example.ts.net:8443"
"""

import sys

# ---- 誤り訂正レベルM のブロック構成 ----
# バージョン: (ブロックあたりの誤り訂正コード語数, [(ブロック数, ブロックあたりのデータコード語数), ...])
EC_M = {
    1:  (10, [(1, 16)]),
    2:  (16, [(1, 28)]),
    3:  (26, [(1, 44)]),
    4:  (18, [(2, 32)]),
    5:  (24, [(2, 43)]),
    6:  (16, [(4, 27)]),
}
# 位置合わせパターンの中心座標
ALIGN = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30],
    6: [6, 34],
}

# ---- GF(256) ----
EXP = [0] * 512
LOG = [0] * 256
_x = 1
for _i in range(255):
    EXP[_i] = _x
    LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    EXP[_i] = EXP[_i - 255]


def gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return EXP[LOG[a] + LOG[b]]


def rs_generator(n):
    """n個の誤り訂正コード語を作るための生成多項式"""
    g = [1]
    for i in range(n):
        g = poly_mul(g, [1, EXP[i]])
    return g


def poly_mul(a, b):
    out = [0] * (len(a) + len(b) - 1)
    for i, ai in enumerate(a):
        for j, bj in enumerate(b):
            out[i + j] ^= gf_mul(ai, bj)
    return out


def rs_encode(data, n):
    gen = rs_generator(n)
    rem = list(data) + [0] * n
    for i in range(len(data)):
        c = rem[i]
        if c:
            for j, g in enumerate(gen):
                rem[i + j] ^= gf_mul(g, c)
    return rem[len(data):]


# ---- データの並べ方 ----
def encode_data(text, version):
    ec_per_block, groups = EC_M[version]
    total_data = sum(n * c for n, c in groups)
    body = text.encode('utf-8')

    bits = []

    def put(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    put(0b0100, 4)                      # バイトモード
    put(len(body), 8)
    for byte in body:
        put(byte, 8)

    cap = total_data * 8
    if len(bits) > cap:
        raise ValueError('データが長すぎます')
    put(0, min(4, cap - len(bits)))     # 終端
    while len(bits) % 8:
        bits.append(0)
    codewords = [int(''.join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]
    pad = [0xEC, 0x11]
    while len(codewords) < total_data:
        codewords.append(pad[(len(codewords) - len(bits) // 8) % 2])

    # ブロックに切り分けて、それぞれに誤り訂正を付ける
    blocks, ecs, pos = [], [], 0
    for count, size in groups:
        for _ in range(count):
            blk = codewords[pos:pos + size]
            pos += size
            blocks.append(blk)
            ecs.append(rs_encode(blk, ec_per_block))

    # 交互に取り出して1本に並べ直す（バーストエラーに強くするため）
    out = []
    for i in range(max(len(b) for b in blocks)):
        for b in blocks:
            if i < len(b):
                out.append(b[i])
    for i in range(ec_per_block):
        for e in ecs:
            out.append(e[i])
    return out


# ---- 配置 ----
def skeleton(version):
    """機能パターン（位置検出・タイミング・位置合わせ）だけを置いた盤面を返す。
    データを入れるマスは None のまま"""
    size = version * 4 + 17
    mat = [[None] * size for _ in range(size)]

    def put_finder(r, c):
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                rr, cc = r + dr, c + dc
                if not (0 <= rr < size and 0 <= cc < size):
                    continue
                edge = dr in (0, 6) or dc in (0, 6)
                inner = 2 <= dr <= 4 and 2 <= dc <= 4
                mat[rr][cc] = 1 if (0 <= dr <= 6 and 0 <= dc <= 6 and (edge or inner)) else 0

    put_finder(0, 0)
    put_finder(0, size - 7)
    put_finder(size - 7, 0)

    for i in range(8, size - 8):        # タイミングパターン
        v = 1 if i % 2 == 0 else 0
        mat[6][i] = v
        mat[i][6] = v

    for r in ALIGN[version]:            # 位置合わせパターン
        for c in ALIGN[version]:
            if mat[r][c] is not None:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    mat[r + dr][c + dc] = 1 if max(abs(dr), abs(dc)) != 1 else 0

    mat[size - 8][8] = 1                # 常に暗いマス

    reserved = [[False] * size for _ in range(size)]
    for i in range(9):                  # 形式情報の場所
        for (r, c) in ((8, i), (i, 8)):
            if 0 <= r < size and 0 <= c < size:
                reserved[r][c] = True
    for i in range(8):
        reserved[8][size - 1 - i] = True
        reserved[size - 1 - i][8] = True
    return mat, reserved


def place_data(mat, reserved, codewords):
    size = len(mat)

    def free(r, c):
        return mat[r][c] is None and not reserved[r][c]

    bits = [(cw >> i) & 1 for cw in codewords for i in range(7, -1, -1)]
    idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:                    # 6列目は縦のタイミングパターン
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (col, col - 1):
                if free(row, c):
                    mat[row][c] = bits[idx] if idx < len(bits) else 0
                    idx += 1
        upward = not upward
        col -= 2
    return mat


MASKS = [
    lambda r, c: (r + c) % 2 == 0,
    lambda r, c: r % 2 == 0,
    lambda r, c: c % 3 == 0,
    lambda r, c: (r + c) % 3 == 0,
    lambda r, c: (r // 2 + c // 3) % 2 == 0,
    lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
    lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
    lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
]


def bch_format(fmt):
    v = fmt << 10
    for i in range(4, -1, -1):
        if v & (1 << (i + 10)):
            v ^= 0x537 << i
    return ((fmt << 10) | v) ^ 0x5412


def penalty(m):
    size = len(m)
    score = 0
    for line in list(m) + [list(col) for col in zip(*m)]:
        run, prev = 0, None
        for v in line:
            if v == prev:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, prev = 1, v
        if run >= 5:
            score += 3 + (run - 5)
    for r in range(size - 1):
        for c in range(size - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    pat = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    for line in list(m) + [list(col) for col in zip(*m)]:
        for i in range(size - 10):
            if line[i:i + 11] == pat or line[i:i + 11] == pat[::-1]:
                score += 40
    dark = sum(sum(row) for row in m)
    score += abs(dark * 100 // (size * size) - 50) // 5 * 10
    return score


def make(text):
    for version in sorted(EC_M):
        try:
            codewords = encode_data(text, version)
        except ValueError:
            continue
        base, reserved = skeleton(version)
        size = len(base)
        # マスクをかけてよいのはデータのマスだけ。位置検出などの機能パターンを
        # 反転させてしまうと読み取れなくなるので、データを置く前に印を取っておく
        is_data = [[base[r][c] is None and not reserved[r][c] for c in range(size)]
                   for r in range(size)]
        place_data(base, reserved, codewords)
        best = None
        for mask_i, mask in enumerate(MASKS):
            m = [row[:] for row in base]
            for r in range(size):
                for c in range(size):
                    if is_data[r][c] and mask(r, c):
                        m[r][c] ^= 1
            fmt = bch_format((0b00 << 3) | mask_i)   # 00 = レベルM
            # 形式情報は上位ビットから並べる（bit14 が (8,0)）
            for i in range(15):
                bit = (fmt >> (14 - i)) & 1
                if i < 6:
                    m[8][i] = bit
                elif i == 6:
                    m[8][7] = bit
                elif i == 7:
                    m[8][8] = bit
                elif i == 8:
                    m[7][8] = bit
                else:
                    m[14 - i][8] = bit
                # 2枚目の形式情報。下7マスは (size-1,8)〜(size-7,8) で、
                # (size-8,8) は「常に暗いマス」なので触らない
                if i < 7:
                    m[size - 1 - i][8] = bit
                else:
                    m[8][size - 15 + i] = bit
            p = penalty(m)
            if best is None or p < best[0]:
                best = (p, m)
        return best[1]
    raise ValueError('QRコードにするには長すぎます（106文字まで）')


def render_invert(matrix, quiet=4, ansi=True):
    """ターミナル用。上下2段を1文字にまとめて、正方形に近い形で描く。

    色は必ず指定する（白文字＋黒背景）。ターミナルの配色は人それぞれで、
    白背景の設定だと明暗が逆のQRになってカメラが読めないことがあるため。
    quiet=4 は規格が求める余白（4マス）。これが無いと読み取り率が落ちます。"""
    size = len(matrix)
    rows = [[0] * (size + quiet * 2) for _ in range(quiet)]
    for row in matrix:
        rows.append([0] * quiet + list(row) + [0] * quiet)
    rows += [[0] * (size + quiet * 2) for _ in range(quiet)]
    if len(rows) % 2:
        rows.append([0] * len(rows[0]))
    out = []
    for i in range(0, len(rows), 2):
        line = ''
        for top, bottom in zip(rows[i], rows[i + 1]):
            if top and bottom:
                line += ' '
            elif top:
                line += '▄'
            elif bottom:
                line += '▀'
            else:
                line += '█'
        out.append(('\033[97;40m' + line + '\033[0m') if ansi else line)
    return '\n'.join(out)


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    print(render_invert(make(sys.argv[1])))
