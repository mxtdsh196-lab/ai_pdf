# -*- coding: utf-8 -*-
"""颜色工具：相对亮度 + WCAG 对比度 + 自动前景色。

为什么在 Python 侧做而不是 Typst：
1. Typst 的 color.components() 返回 ratio 类型，转 float 有陷阱（实测会算错）
2. 只有 Python 侧才能提前告警/自动修正
3. _col() 本来就在 Python 侧

WCAG 2.1 公式（https://www.w3.org/TR/WCAG21/#dfn-relative-luminance）：
  L = 0.2126*R + 0.7152*G + 0.0722*B   （R/G/B 为线性化后的值）
  线性化：c <= 0.03928 ? c/12.92 : ((c+0.055)/1.055)^2.4
  对比度 = (L1 + 0.05) / (L2 + 0.05)，L1 为较亮者
"""


def hex_to_rgb(h):
    """'1F3A5F' 或 '#1F3A5F' -> (r, g, b)，每项 0~1。"""
    s = str(h or '').strip().lstrip('#')
    if len(s) == 3:
        s = ''.join(c * 2 for c in s)
    if len(s) != 6:
        return None
    try:
        return tuple(int(s[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    except Exception:
        return None


def _lin(c):
    """sRGB 分量线性化。"""
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def rel_lum(h):
    """相对亮度 0~1。黑=0，白=1。"""
    rgb = hex_to_rgb(h)
    if rgb is None:
        return None
    r, g, b = (_lin(x) for x in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(h1, h2):
    """两色对比度，范围 1~21。WCAG AA 正文要求 >= 4.5，大字 >= 3.0。"""
    a, b = rel_lum(h1), rel_lum(h2)
    if a is None or b is None:
        return None
    hi, lo = (a, b) if a >= b else (b, a)
    return (hi + 0.05) / (lo + 0.05)


# 两个候选前景色：几乎纯黑 / 纯白（不用纯黑，视觉更柔）
FG_DARK = '141414'
FG_LIGHT = 'FFFFFF'


def best_fg(bg, min_ratio=4.5):
    """给底色选一个能看清的前景色。

    返回 (hex, contrast)。两色都不达标时返回对比度更高的那个，
    调用方可根据 contrast 决定是否告警。
    """
    cd = contrast(bg, FG_DARK)
    cl = contrast(bg, FG_LIGHT)
    if cd is None and cl is None:
        return FG_DARK, None
    if cd is None:
        return FG_LIGHT, cl
    if cl is None:
        return FG_DARK, cd
    # 深底配白字、浅底配黑字：按亮度判断比按对比度更符合直觉
    l = rel_lum(bg)
    if l is not None and l < 0.45:
        # 深底优先白字
        if cl >= min_ratio:
            return FG_LIGHT, cl
        return (FG_DARK if cd > cl else FG_LIGHT), max(cd, cl)
    if cd >= min_ratio:
        return FG_DARK, cd
    return (FG_LIGHT if cl > cd else FG_DARK), max(cd, cl)


def fix_pair(fg, bg, min_ratio=4.5):
    """已知前景+背景，若对比不足则给出建议。

    返回 (建议前景, 实际对比度, 是否达标)。
    """
    c = contrast(fg, bg)
    if c is None:
        return fg, None, True
    if c >= min_ratio:
        return fg, c, True
    sug, _ = best_fg(bg, min_ratio)
    return sug, c, False