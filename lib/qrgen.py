# -*- coding: utf-8 -*-
"""QR 码生成器（零依赖，自包含）

只做最常用的场景：字节模式 + 纠错等级 M/L + 自动选版本。
输出 PNG（用 PIL 画）。

参考 ISO/IEC 18004。实现的子集：
- 模式：Byte（UTF-8 字节）
- 纠错：L / M / Q / H
- 版本：1-10（足够放 URL 和短文本）
- 掩码：全部 8 种都算，按惩罚分选最优
"""
import io

# ---------- 纠错码参数表（版本 1-10） ----------
# 每项：(L, M, Q, H) 各自 (总码字, 数据码字, 每块纠错码字, 块数)
# 格式：[(总码字, 每块EC, [块数据长度...]) ...]
# 简化：用 (ec_codewords_per_block, num_blocks_group1, num_blocks_group2, block_len_g1, block_len_g2)

# 数据码字容量表：version -> {level: (total_codewords, total_data_codewords)}
CAP = {
    1: {'L': (26, 19), 'M': (26, 16), 'Q': (26, 13), 'H': (26, 9)},
    2: {'L': (44, 34), 'M': (44, 28), 'Q': (44, 22), 'H': (44, 16)},
    3: {'L': (70, 55), 'M': (70, 44), 'Q': (70, 34), 'H': (70, 26)},
    4: {'L': (100, 80), 'M': (100, 64), 'Q': (100, 48), 'H': (100, 36)},
    5: {'L': (134, 108), 'M': (134, 86), 'Q': (134, 62), 'H': (134, 46)},
    6: {'L': (172, 136), 'M': (172, 108), 'Q': (172, 76), 'H': (172, 60)},
    7: {'L': (196, 156), 'M': (196, 124), 'Q': (196, 88), 'H': (196, 66)},
    8: {'L': (242, 194), 'M': (242, 154), 'Q': (242, 110), 'H': (242, 86)},
    9: {'L': (292, 232), 'M': (292, 182), 'Q': (292, 132), 'H': (292, 100)},
    10: {'L': (346, 274), 'M': (346, 216), 'Q': (346, 154), 'H': (346, 122)},
}

# 纠错块结构表：version -> {level: (ec_per_block, [(块数, 该块数据长度), ...])}
EC_BLOCKS = {
    1: {'L': (7, [(1, 19)]), 'M': (10, [(1, 16)]), 'Q': (13, [(1, 13)]), 'H': (17, [(1, 9)])},
    2: {'L': (10, [(1, 34)]), 'M': (16, [(1, 28)]), 'Q': (22, [(1, 22)]), 'H': (28, [(1, 16)])},
    3: {'L': (15, [(1, 55)]), 'M': (26, [(1, 44)]), 'Q': (18, [(2, 17)]), 'H': (22, [(2, 13)])},
    4: {'L': (20, [(1, 80)]), 'M': (18, [(2, 32)]), 'Q': (26, [(2, 24)]), 'H': (16, [(4, 9)])},
    5: {'L': (26, [(1, 108)]), 'M': (24, [(2, 43)]), 'Q': (18, [(2, 15), (2, 16)]), 'H': (22, [(2, 11), (2, 12)])},
    6: {'L': (18, [(2, 68)]), 'M': (16, [(4, 27)]), 'Q': (24, [(4, 19)]), 'H': (28, [(4, 15)])},
    7: {'L': (20, [(2, 78)]), 'M': (18, [(4, 31)]), 'Q': (18, [(2, 14), (4, 15)]), 'H': (26, [(4, 13), (1, 14)])},
    8: {'L': (24, [(2, 97)]), 'M': (22, [(2, 38), (2, 39)]), 'Q': (22, [(4, 18), (2, 19)]), 'H': (26, [(4, 14), (2, 15)])},
    9: {'L': (30, [(2, 116)]), 'M': (22, [(3, 36), (2, 37)]), 'Q': (20, [(4, 16), (4, 17)]), 'H': (24, [(4, 12), (4, 13)])},
    10: {'L': (18, [(2, 68), (2, 69)]), 'M': (26, [(4, 43), (1, 44)]), 'Q': (24, [(6, 19), (2, 20)]), 'H': (28, [(6, 15), (2, 16)])},
}

ALIGN_POS = {
    1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30],
    6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
}


# ---------- GF(256) 运算 ----------
_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _gf_mul(a, b):
    if a == 0 or b == 0:
        return 0
    return _EXP[_LOG[a] + _LOG[b]]


def _rs_generator(n):
    g = [1]
    for i in range(n):
        ng = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            ng[j] ^= c
            ng[j + 1] ^= _gf_mul(c, _EXP[i])
        g = ng
    return g


def _rs_encode(data, ec_len):
    gen = _rs_generator(ec_len)
    res = list(data) + [0] * ec_len
    for i in range(len(data)):
        coef = res[i]
        if coef:
            for j, g in enumerate(gen):
                res[i + j] ^= _gf_mul(g, coef)
    return res[len(data):]


# ---------- 位流 ----------
class BitBuf:
    def __init__(self):
        self.bits = []

    def put(self, val, n):
        for i in range(n - 1, -1, -1):
            self.bits.append((val >> i) & 1)

    def __len__(self):
        return len(self.bits)


def _encode_data(payload, version, level):
    total_cw, data_cw = CAP[version][level]
    bb = BitBuf()
    bb.put(0b0100, 4)              # Byte 模式
    bb.put(len(payload), 8 if version <= 9 else 16)
    for b in payload:
        bb.put(b, 8)
    cap_bits = data_cw * 8
    if len(bb) > cap_bits:
        return None
    # 终止符
    bb.put(0, min(4, cap_bits - len(bb)))
    # 补齐到字节
    while len(bb) % 8:
        bb.bits.append(0)
    # 填充码字
    pad = [0xEC, 0x11]
    i = 0
    while len(bb) < cap_bits:
        bb.put(pad[i % 2], 8)
        i += 1
    # 转字节
    out = bytearray()
    for i in range(0, len(bb.bits), 8):
        v = 0
        for j in range(8):
            v = (v << 1) | bb.bits[i + j]
        out.append(v)
    return bytes(out)


# ---------- 矩阵构建 ----------
def _new_matrix(size):
    return [[None] * size for _ in range(size)]


def _place_finder(m, r, c):
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            rr, cc = r + dr, c + dc
            if 0 <= rr < len(m) and 0 <= cc < len(m):
                if 0 <= dr <= 6 and 0 <= dc <= 6:
                    edge = dr in (0, 6) or dc in (0, 6)
                    core = 2 <= dr <= 4 and 2 <= dc <= 4
                    m[rr][cc] = 1 if (edge or core) else 0
                else:
                    m[rr][cc] = 0


def _place_alignment(m, version):
    pos = ALIGN_POS.get(version, [])
    for r in pos:
        for c in pos:
            if m[r][c] is not None:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    m[r + dr][c + dc] = 1 if (abs(dr) == 2 or abs(dc) == 2 or (dr == 0 and dc == 0)) else 0


def _place_timing(m):
    size = len(m)
    for i in range(8, size - 8):
        if m[6][i] is None:
            m[6][i] = 1 if i % 2 == 0 else 0
        if m[i][6] is None:
            m[i][6] = 1 if i % 2 == 0 else 0


def build_matrix(payload, level='M', version=None):
    if version is None:
        for v in range(1, 11):
            if CAP[v][level][1] * 8 >= 4 + (8 if v <= 9 else 16) + len(payload) * 8:
                version = v
                break
        if version is None:
            return None
    data = _encode_data(payload, version, level)
    if data is None:
        return None

    ec_per, groups = EC_BLOCKS[version][level]
    blocks = []
    idx = 0
    for cnt, blen in groups:
        for _ in range(cnt):
            blocks.append(bytearray(data[idx:idx + blen]))
            idx += blen
    ecs = [_rs_encode(b, ec_per) for b in blocks]
    # 交织
    final = bytearray()
    maxlen = max(len(b) for b in blocks)
    for i in range(maxlen):
        for b in blocks:
            if i < len(b):
                final.append(b[i])
    for i in range(ec_per):
        for e in ecs:
            final.append(e[i])

    size = version * 4 + 17
    m = _new_matrix(size)
    _place_finder(m, 0, 0)
    _place_finder(m, 0, size - 7)
    _place_finder(m, size - 7, 0)
    _place_alignment(m, version)
    _place_timing(m)

    # 预留格式信息区（先占位）
    for i in range(9):
        if m[8][i] is None:
            m[8][i] = 0
        if m[i][8] is None:
            m[i][8] = 0
    for i in range(8):
        if m[8][size - 1 - i] is None:
            m[8][size - 1 - i] = 0
        if m[size - 1 - i][8] is None:
            m[size - 1 - i][8] = 0
    m[size - 8][8] = 1  # dark module

    # 数据位流
    bitstream = []
    for byte in final:
        for i in range(7, -1, -1):
            bitstream.append((byte >> i) & 1)

    # 蛇形填充
    bi = 0
    upward = True
    col = size - 1
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (col, col - 1):
                if m[row][c] is None:
                    if bi < len(bitstream):
                        m[row][c] = bitstream[bi]
                        bi += 1
                    else:
                        m[row][c] = 0
        upward = not upward
        col -= 2
    return m, version


# ---------- 掩码 ----------
def _mask_fn(idx):
    return [
        lambda r, c: (r + c) % 2 == 0,
        lambda r, c: r % 2 == 0,
        lambda r, c: c % 3 == 0,
        lambda r, c: (r + c) % 3 == 0,
        lambda r, c: (r // 2 + c // 3) % 2 == 0,
        lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
        lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
        lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0,
    ][idx]


def _reserved(size, version):
    """哪些位置是功能图案（不能参与掩码）。

    关键：必须和 build_matrix 里的占位流程**完全一致**。
    之前这里手写了一遍判定，漏标了格式信息的右半和第 8 列下半段，
    导致 16 个格子被当成数据区，生成的码扫不出来。
    现在改成「跑一遍占位流程，非 None 即保留」，单一真源。
    """
    tmp = _new_matrix(size)
    _place_finder(tmp, 0, 0)
    _place_finder(tmp, 0, size - 7)
    _place_finder(tmp, size - 7, 0)
    _place_alignment(tmp, version)
    _place_timing(tmp)
    # 格式信息占位（与 build_matrix 同一段逻辑）
    for i in range(9):
        if tmp[8][i] is None:
            tmp[8][i] = 0
        if tmp[i][8] is None:
            tmp[i][8] = 0
    for i in range(8):
        if tmp[8][size - 1 - i] is None:
            tmp[8][size - 1 - i] = 0
        if tmp[size - 1 - i][8] is None:
            tmp[size - 1 - i][8] = 0
    tmp[size - 8][8] = 1
    return [[tmp[r][c] is not None for c in range(size)] for r in range(size)]


def _apply_mask(m, mask_idx, reserved):
    size = len(m)
    f = _mask_fn(mask_idx)
    out = [row[:] for row in m]
    for r in range(size):
        for c in range(size):
            if not reserved[r][c] and f(r, c):
                out[r][c] ^= 1
    return out


def _penalty(m):
    size = len(m)
    score = 0
    # 规则1：连续同色
    for lines in (m, [[m[r][c] for r in range(size)] for c in range(size)]):
        for line in lines:
            run = 1
            for i in range(1, size):
                if line[i] == line[i - 1]:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + (run - 5)
                    run = 1
            if run >= 5:
                score += 3 + (run - 5)
    # 规则2：2x2 同色
    for r in range(size - 1):
        for c in range(size - 1):
            v = m[r][c]
            if v == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    # 规则3：类似 finder 的图案
    pat1 = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0]
    pat2 = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1]
    for lines in (m, [[m[r][c] for r in range(size)] for c in range(size)]):
        for line in lines:
            for i in range(size - 10):
                seg = line[i:i + 11]
                if seg == pat1 or seg == pat2:
                    score += 40
    # 规则4：暗模块比例
    dark = sum(sum(r) for r in m)
    ratio = dark * 100 // (size * size)
    score += abs(ratio - 50) // 5 * 10
    return score


def _format_bits(level, mask):
    lv = {'L': 1, 'M': 0, 'Q': 3, 'H': 2}[level]
    data = (lv << 3) | mask
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    return ((data << 10) | rem) ^ 0x5412


def _write_format(m, level, mask):
    size = len(m)
    bits = _format_bits(level, mask)
    for i in range(15):
        b = (bits >> i) & 1
        # 左上
        if i < 6:
            m[8][i] = b
        elif i < 8:
            m[8][i + 1] = b
        else:
            m[8][size - 15 + i] = b
        if i < 8:
            m[size - 1 - i][8] = b
        elif i < 9:
            m[15 - i][8] = b
        else:
            m[15 - i][8] = b
    m[size - 8][8] = 1


def render_png(text, level='M', box=8, border=4):
    if isinstance(text, str):
        payload = text.encode('utf-8')
    else:
        payload = text
    r = build_matrix(payload, level)
    if r is None:
        return None
    base, version = r
    reserved = _reserved(len(base), version)
    best = None
    best_score = None
    for mi in range(8):
        cand = _apply_mask(base, mi, reserved)
        _write_format(cand, level, mi)
        s = _penalty(cand)
        if best_score is None or s < best_score:
            best_score, best = s, cand
    size = len(best)
    dim = (size + border * 2) * box
    try:
        from PIL import Image
    except Exception:
        return None
    img = Image.new('L', (dim, dim), 255)
    px = img.load()
    for r_ in range(size):
        for c_ in range(size):
            if best[r_][c_]:
                for dy in range(box):
                    for dx in range(box):
                        px[(c_ + border) * box + dx, (r_ + border) * box + dy] = 0
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue(), dim, version