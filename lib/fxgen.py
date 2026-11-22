# -*- coding: utf-8 -*-
"""SVG 特效生成器（装饰层专用）

设计原则：**只生成背景/装饰，绝不往 SVG 里放正文**。
SVG 里的文字是矢量图形，不可选、不可搜、不可复制。
所以这里的函数只画形状，正文永远由 Typst 排。
"""
import io


def _hex(c, default='#2547A8'):
    if not c:
        return default
    c = str(c).strip().lstrip('#')
    if len(c) == 6 and all(ch in '0123456789abcdefABCDEF' for ch in c):
        return '#' + c
    return default


def glow_card(w=200, h=80, color='#2547A8', blur=7, radius=12, opacity=0.9):
    """泛光卡片：高斯模糊的色块，用作背景装饰"""
    c = _hex(color)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
        '<defs><filter id="g" x="-50%%" y="-50%%" width="200%%" height="200%%">'
        '<feGaussianBlur stdDeviation="%d"/></filter></defs>'
        '<rect x="%d" y="%d" width="%d" height="%d" rx="%d" fill="%s" opacity="%.2f" filter="url(#g)"/>'
        '</svg>'
    ) % (w, h, blur, blur + 4, blur + 4, w - 2 * blur - 8, h - 2 * blur - 8, radius, c, opacity)
    return svg


def frost_panel(w=300, h=160, radius=14, tint='#FFFFFF', opacity=0.55, noise=0.06):
    """磨砂玻璃面板：半透明白 + 细高光边 + 噪点"""
    t = _hex(tint, '#FFFFFF')
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
        '<defs>'
        '<filter id="n"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="3"/>'
        '<feColorMatrix type="saturate" values="0"/>'
        '<feComponentTransfer><feFuncA type="linear" slope="%.2f"/></feComponentTransfer></filter>'
        '<linearGradient id="hl" x1="0" y1="0" x2="0" y2="1">'
        '<stop offset="0" stop-color="#FFFFFF" stop-opacity="0.9"/>'
        '<stop offset="0.06" stop-color="#FFFFFF" stop-opacity="0"/></linearGradient>'
        '</defs>'
        '<rect x="1" y="1" width="%d" height="%d" rx="%d" fill="%s" opacity="%.2f"/>'
        '<rect x="1" y="1" width="%d" height="%d" rx="%d" fill="url(#hl)" opacity="0.5"/>'
        '<rect x="1" y="1" width="%d" height="%d" rx="%d" fill="#000000" filter="url(#n)" opacity="0.5"/>'
        '<rect x="1" y="1" width="%d" height="%d" rx="%d" fill="none" stroke="#FFFFFF" stroke-opacity="0.6" stroke-width="1.2"/>'
        '</svg>'
    ) % (w, h, noise, w - 2, h - 2, radius, t, opacity,
         w - 2, h - 2, radius,
         w - 2, h - 2, radius,
         w - 2, h - 2, radius)
    return svg


def noise_png(w=600, h=220, alpha=0.12):
    """噪点纹理（栅格 PNG）。

    为什么不用 SVG feTurbulence：矢量噪点会被嵌成海量 path，
    实测一份 3 页文档从 37KB 涨到 3.4MB。栅格化后只有几十 KB。
    """
    try:
        import random
        from PIL import Image
    except Exception:
        return None
    img = Image.new('L', (w, h), 255)
    px = img.load()
    a = int(alpha * 255)
    rnd = random.Random(20261122)  # 固定种子，保证可复现
    for y in range(h):
        for x in range(w):
            if rnd.random() < 0.35:
                px[x, y] = 255 - rnd.randint(0, a)
    buf = io.BytesIO()
    img.save(buf, 'PNG', optimize=True)
    return buf.getvalue()


def noise_texture(w=240, h=140, alpha=0.35, freq=0.85):
    """兼容旧调用：返回 SVG（已不推荐，体积大）"""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
        '<defs><filter id="nz"><feTurbulence type="fractalNoise" baseFrequency="%.2f" numOctaves="2"/>'
        '<feColorMatrix type="saturate" values="0"/>'
        '<feComponentTransfer><feFuncA type="linear" slope="%.2f"/></feComponentTransfer></filter></defs>'
        '<rect width="%d" height="%d" fill="#000000" filter="url(#nz)"/>'
        '</svg>'
    ) % (w, h, freq, alpha, w, h)
    return svg


def gradient_blob(w=300, h=200, c1='#2547A8', c2='#7C3AED', angle=135, strength=0.85):
    """流体渐变底（极光感）。

    angle 真正生效：两个径向光斑的位置按角度绕中心对向分布。
    之前 angle 写在签名里但函数体完全没用，6 个角度输出 md5 全同（实测）。
    strength 控制光斑起始不透明度（0~1）。
    """
    import math
    a = _hex(c1)
    b = _hex(c2)
    ang = float(angle) % 360.0
    rad = math.radians(ang)
    # 光斑 1 沿 angle 方向，光斑 2 在对向；半径取 0.28 保证不出画布
    r1 = 0.28
    x1 = 0.5 + r1 * math.cos(rad)
    y1 = 0.5 + r1 * math.sin(rad)
    x2 = 0.5 - r1 * math.cos(rad)
    y2 = 0.5 - r1 * math.sin(rad)
    s1 = max(0.0, min(1.0, float(strength)))
    s2 = max(0.0, min(1.0, s1 * 0.88))
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
        '<defs>'
        '<radialGradient id="b1" cx="%.4f" cy="%.4f" r="0.72">'
        '<stop offset="0" stop-color="%s" stop-opacity="%.2f"/>'
        '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
        '<radialGradient id="b2" cx="%.4f" cy="%.4f" r="0.66">'
        '<stop offset="0" stop-color="%s" stop-opacity="%.2f"/>'
        '<stop offset="1" stop-color="%s" stop-opacity="0"/></radialGradient>'
        '</defs>'
        '<rect width="%d" height="%d" fill="#FFFFFF"/>'
        '<rect width="%d" height="%d" fill="url(#b1)"/>'
        '<rect width="%d" height="%d" fill="url(#b2)"/>'
        '</svg>'
    ) % (w, h, x1, y1, a, s1, a, x2, y2, b, s2, b, w, h, w, h, w, h)
    return svg


def curve_ornament(w=280, h=90, path='M10,70 C60,20 140,95 270,30',
                   color='#1F7A5C', width=2.5, dot=True):
    """自定义曲线装饰。path 用 SVG path 语法。"""
    c = _hex(color, '#1F7A5C')
    dot_svg = ''
    if dot:
        # 取路径中点附近放一个小圆点
        dot_svg = '<circle cx="%d" cy="%d" r="4" fill="%s"/>' % (w // 2, h // 2, c)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
        '<path d="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linecap="round"/>'
        '%s'
        '</svg>'
    ) % (w, h, path, c, width, dot_svg)
    return svg


def wave_divider(w=400, h=24, color='#EEF2F9', amp=8):
    """波浪分割线"""
    c = _hex(color, '#EEF2F9')
    mid = h / 2
    d = 'M0,%.1f Q%.1f,%.1f %.1f,%.1f T%.1f,%.1f T%d,%.1f L%d,%d L0,%d Z' % (
        mid, w * 0.125, mid - amp, w * 0.25, mid, w * 0.5, mid, w, mid, w, h, h)
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d">'
        '<path d="%s" fill="%s"/></svg>'
    ) % (w, h, d, c)
    return svg


KINDS = {
    'glow': glow_card,
    'frost': frost_panel,
    'noise': noise_texture,
    'gradient': gradient_blob,
    'wave': wave_divider,
}

CURVE = curve_ornament