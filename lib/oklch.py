# -*- coding: utf-8 -*-
"""OKLab / OKLCH 色彩空间 + 单色相明度阶梯生成。

为什么不用 corkscrew（cubehelix）：
corkscrew 生成的是**彩虹色阶**（黑→蓝→绿→金→粉→白），色相在变。
它原本用于数据可视化，目的是让不同数值视觉可分。
但排版需要的色阶是「**同一色相，只变明度**」——
深海军蓝 / 中蓝 / 浅蓝灰 / 白，四者色相相同。
实测：cubehelix(rotations=-1.5) 生成 #000000 #182E49 #2B6F39 #A07949
#D490C6 #C2D8F3 #FFFFFF —— 明显跨越蓝绿金粉，不能当色阶。

OKLab 是 Björn Ottosson 2020 提出的感知均匀色彩空间，
L 轴即明度，改动 L 时色相与视觉感受保持稳定，正好是「色阶」需要的性质。

参考：https://bottosson.github.io/posts/oklab/
"""

import math

__all__ = ['hex_to_rgb', 'rgb_to_hex', 'rgb_to_oklab', 'oklab_to_rgb',
           'rgb_to_oklch', 'oklch_to_rgb', 'ramp', 'ramp_named', 'contrast_l']


def hex_to_rgb(h):
    s = str(h or '').strip().lstrip('#')
    if len(s) == 3:
        s = ''.join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return None


def rgb_to_hex(rgb):
    r, g, b = (max(0, min(255, int(round(x)))) for x in rgb)
    return '%02X%02X%02X' % (r, g, b)


def _srgb_to_lin(c):
    c = c / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _lin_to_srgb(c):
    c = max(0.0, min(1.0, c))
    return 12.92 * c if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def rgb_to_oklab(rgb):
    r, g, b = (_srgb_to_lin(x) for x in rgb)
    l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b
    l_, m_, s_ = l ** (1 / 3), m ** (1 / 3), s ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def oklab_to_rgb(lab):
    L, a, b = lab
    l_ = L + 0.3963377774 * a + 0.2158037573 * b
    m_ = L - 0.1055613458 * a - 0.0638541728 * b
    s_ = L - 0.0894841775 * a - 1.2914855480 * b
    l, m, s = l_ ** 3, m_ ** 3, s_ ** 3
    r = +4.0767416621 * l - 3.3077115913 * m + 0.2309699292 * s
    g = -1.2684380046 * l + 2.6097574011 * m - 0.3413193965 * s
    bb = -0.0041960863 * l - 0.7034186147 * m + 1.7076147010 * s
    return tuple(int(round(_lin_to_srgb(x) * 255)) for x in (r, g, bb))


def rgb_to_oklch(rgb):
    L, a, b = rgb_to_oklab(rgb)
    C = math.hypot(a, b)
    h = math.degrees(math.atan2(b, a)) % 360.0
    return L, C, h


def oklch_to_rgb(L, C, h):
    rad = math.radians(h)
    return oklab_to_rgb((L, C * math.cos(rad), C * math.sin(rad)))


def contrast_l(L1, L2):
    """WCAG 相对亮度之间的对比度（近似，L 用 OKLab 明度代入 sRGB 亮度不严谨，
    这里只用于排阶梯的粗筛；精确对比度请用 colorkit.contrast）。"""
    hi, lo = (L1, L2) if L1 >= L2 else (L2, L1)
    return (hi + 0.05) / (lo + 0.05)


def ramp(base, count=7, lmin=0.18, lmax=0.97, cscale=1.0):
    """给一个基色，生成一条「同色相、只变明度」的色阶。

    base:  基色 hex，取它的色相
    count: 几档
    lmin/lmax: 明度范围（OKLab L，0~1）
    cscale: 饱和度缩放（>1 更艳，<1 更灰）

    返回 [(hex, L, C, h), ...]，从最深到最浅。
    """
    rgb = hex_to_rgb(base)
    if not rgb:
        return []
    _, C0, h = rgb_to_oklch(rgb)
    out = []
    n = max(1, int(count))
    for i in range(n):
        t = 0.5 if n == 1 else i / (n - 1.0)
        L = lmin + (lmax - lmin) * t
        # 浅色端收一点饱和度，避免「浅而艳」的塑料感
        c = C0 * cscale * (1.0 - 0.55 * max(0.0, (L - 0.6) / 0.4))
        c = max(0.0, min(0.37, c))
        out.append((rgb_to_hex(oklch_to_rgb(L, c, h)), L, c, h))
    return out


def ramp_named(base, count=7, white=0.06):
    """返回角色命名的色阶。

    角色（用途清晰，不用懂色彩学）：
      deep   压照片/深色块的底（配白字）
      mid    次级色块
      veil   半透明蒙版色（配 alpha 用）
      pale   页面/卡片浅底（配黑字）
      paper  接近纯白，留 white 比例的基色味
      ink    正文墨色：浅底文档用深墨，深底文档用浅字
      accent 基色本身

    ★ paper 必须真是「接近白」。早期版本直接取色阶最浅一档，
    得到 #E6F7FF 这种明显带蓝的颜色，当纸色用会显得脏。
    这里单独按 L=0.98、极低饱和度生成。

    ★ ink 的方向看 pale 而不是看基色：文档底色是 pale，
    正文要压在 pale 上，所以按 pale 的明度决定用深墨还是浅字。
    """
    r = ramp(base, count=count, lmin=0.20)
    if not r:
        return {}
    rgbs = [x[0] for x in r]
    n = len(rgbs)
    pick = lambda p: rgbs[min(n - 1, max(0, int(round(p * (n - 1)))))]
    rgb0 = hex_to_rgb(base)
    _, C0, h0 = rgb_to_oklch(rgb0)
    pale = pick(0.80)
    # paper：极浅、去饱和的基色，视觉上就是「带一点色调的白纸」
    pw = max(0.0, min(0.12, float(white)))
    paper = rgb_to_hex(oklch_to_rgb(0.985, C0 * pw, h0))
    # ink：看 pale 明度，压在 pale 上的正文色
    pale_l = rgb_to_oklch(hex_to_rgb(pale))[0]
    ink = '141414' if pale_l > 0.5 else 'F2F4F7'
    return {
        'deep': rgbs[0],
        'mid': pick(0.26),
        'veil': rgb_to_hex(oklch_to_rgb(0.40, C0, h0)),
        'soft': pick(0.52),
        'pale': pale,
        'paper': paper,
        'ink': ink,
        'accent': str(base).lstrip('#').upper(),
    }