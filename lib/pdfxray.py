# -*- coding: utf-8 -*-
"""pdf_xray 原型：把 PDF 一页解析成 AI 能直读的结构（不依赖识图）。

三条数据源，缺一不可：
  1. get_bboxlog()  —— 唯一能看见 fill-shade（渐变/pattern 填充）的接口。
                       get_drawings()/get_cdrawings() 都漏掉它，
                       实测 slide 章节页的满屏渐变在 drawings 里是 0 条。
  2. get_drawings() —— 实色块的精确颜色（bboxlog 只给 bbox，不给填色）。
  3. get_text('dict') —— 文字、字号、字体、精确 bbox。

输出两段：
  [布局] 字符画：形状用边框字符，文字用真字叠上去（坐标就是真实坐标）
  [元素] 逐条列出：类型 rect=(x0,y0,x1,y1) mm 尺寸 颜色 字号 文字
"""

import pymupdf
import unicodedata


def _mm2pt(v):
    return v * 72.0 / 25.4


def _hex(rgb):
    if not rgb or len(rgb) < 3:
        return None
    return '#%02X%02X%02X' % tuple(max(0, min(255, int(round(c * 255)))) for c in rgb[:3])


def _page_size_mm(p):
    return p.rect.width * 25.4 / 72.0, p.rect.height * 25.4 / 72.0


def collect(p):
    """收集一页的全部元素，返回 (shapes, texts, page_w, page_h)。

    形状来源必须是 get_drawings() 而不是只用 get_bboxlog()：
    bboxlog 只给 bbox 不给描边颜色，导致「独立描边框」（type='s'）拿不到
    stroke 值，cross_border 判据直接失效（实测 cert 边框就因此漏掉）。
    另外 get_drawings() 看不见 pattern/shading 填充，所以 shade 仍靠 bboxlog 补。
    """
    r = p.rect
    shapes = []

    # --- 主来源：get_drawings()，它带 fill / color / type，几何也准 ---
    seen = set()
    for d in p.get_drawings():
        rr = d.get('rect')
        if rr is None or rr.is_empty:
            continue
        t = d.get('type')
        kind = 'fill' if t in ('f', 'fs') else ('stroke' if t == 's' else 'stroke')
        key = (round(rr.x0, 1), round(rr.y0, 1), round(rr.x1, 1), round(rr.y1, 1), kind)
        if key in seen:
            continue
        seen.add(key)
        shapes.append({
            'kind': kind,
            'rect': rr,
            'fill': _hex(d.get('fill')) if t in ('f', 'fs') else None,
            'stroke': _hex(d.get('color')) if t in ('s', 'fs') else None,
        })

    # --- 补漏：get_bboxlog() 能看见 shading/pattern，drawings 看不见 ---
    for kind, bb in p.get_bboxlog():
        if kind in ('fill-shade', 'stroke-shade'):
            shapes.append({'kind': 'shade',
                           'rect': pymupdf.Rect(0, 0, r.width, r.height),
                           'fill': None, 'stroke': None,
                           'note': '渐变/图案填充（整页铺底）'})

    # --- 文字 ---
    texts = []
    for b in p.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for ln in b['lines']:
            for sp in ln['spans']:
                t = sp['text']
                if not t.strip():
                    continue
                texts.append({
                    'text': t,
                    'rect': pymupdf.Rect(*sp['bbox']),
                    'size': sp['size'],
                    'font': sp['font'],
                    'color': _hex(_rgb_from_int(sp.get('color', 0))),
                })
    return shapes, texts, r.width, r.height


def _rgb_from_int(v):
    if not isinstance(v, int):
        return None
    return (((v >> 16) & 255) / 255.0, ((v >> 8) & 255) / 255.0, (v & 255) / 255.0)


def _cw(ch):
    """终端列宽：全角/宽字符占 2 列，其余 1 列（emoji 也算 2）。
    不区分的话中文会挤掉后面一半，字符画整体错位。"""
    if unicodedata.east_asian_width(ch) in ('W', 'F'):
        return 2
    return 1


def _overlaps(a, b):
    """两个元素是否真的重叠（有面积交集，不是仅仅贴边）。"""
    x = min(a.x1, b.x1) - max(a.x0, b.x0)
    y = min(a.y1, b.y1) - max(a.y0, b.y0)
    return x > 0.5 and y > 0.5


def art(p, cols=72):
    """字符画：形状画框，文字叠真字。全角字符按 2 列占位。"""
    shapes, texts, pw, ph = collect(p)
    rows = max(8, int(round(cols * (ph / pw) * 0.5)))
    g = [[' '] * cols for _ in range(rows)]
    sw, sh = pw / cols, ph / rows

    def put(x, y, ch):
        if 0 <= y < rows and 0 <= x < cols:
            g[y][x] = ch

    def put_text(x, y, s, limit=None):
        for ch in s:
            w = _cw(ch)
            if x + w > (limit if limit is not None else cols):
                break
            if 0 <= y < rows and 0 <= x < cols:
                g[y][x] = ch
                if w == 2 and x + 1 < cols:
                    g[y][x + 1] = ''      # 占位，不覆盖
            x += w

    def box(rr, edge, fillch=None):
        x0 = max(0, int(rr.x0 / sw)); x1 = min(cols - 1, int(rr.x1 / sw))
        y0 = max(0, int(rr.y0 / sh)); y1 = min(rows - 1, int(rr.y1 / sh))
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if y in (y0, y1) or x in (x0, x1):
                    if g[y][x] == ' ':
                        g[y][x] = edge
                elif fillch and g[y][x] == ' ':
                    g[y][x] = fillch

    # 大块先画，小块后画，避免小卡片被整页底色盖掉轮廓
    for s in sorted(shapes, key=lambda s: -(s['rect'].width * s['rect'].height)):
        if s['kind'] == 'shade':
            box(s['rect'], '*', '.')
        elif s['kind'] == 'fill':
            box(s['rect'], '=', '.')
        else:
            box(s['rect'], '+')

    for t in texts:
        cx = int(t['rect'].x0 / sw)
        cy = int(t['rect'].y0 / sh)
        # 不越过自己 span 的右边界，否则会盖掉右侧元素
        lim = int(t['rect'].x1 / sw) + 1
        put_text(cx, cy, t['text'], limit=min(cols, lim))

    return '\n'.join(''.join(r0) for r0 in g)


def effects(p):
    """识别页面上的视觉特效，返回 [{kind, rect, detail}]。

    每种特效在 PDF 里有确定特征，全部实测确认（_fx2.pdf）：

      阴影 shadow   两个错位填充块，一块是深色偏移层（typst 的 shadowed 是
                    下方垫一层 tint 块）。实测 D5D6D5 与 FFFFFF 只差 y 2.5pt，
                    且深块右下各多 1.5pt。
      磨砂 frost    填充 opacity < 1 + 白色描边。实测 fill=EDF3F9 fo=0.878
                    stroke=FFFFFF so=1.0。
      泛光 glow     描边 opacity 很低（0.1~0.4）→ 半透明外圈。实测
                    stroke=2F5BE9 so=0.18。
      渐变 gradient fill-shade 出现（bboxlog 独有），常伴随一条高光条
                    fill_opacity≈0.55。
      噪点 noise    内嵌 raster image（PNG）。实测 1200x440 png。
      曲线/波浪     stroke-path，且 dashes 为空、无填色。
    """
    out = []
    shapes, texts, pw, ph = collect(p)

    fills = [s for s in shapes if s['kind'] == 'fill']
    strokes = [s for s in shapes if s['kind'] == 'stroke']

    # --- 噪点 / 任何栅格图 ---
    for im in p.get_images(full=True):
        xref = im[0]
        try:
            info = p.parent.extract_image(xref)
        except Exception:
            continue
        w, h = info.get('width', 0), info.get('height', 0)
        # 找该图的放置矩形
        rect = None
        for kind, bb in p.get_bboxlog():
            if kind == 'fill-image':
                rect = pymupdf.Rect(*bb)
                break
        out.append({'kind': 'image', 'rect': rect or pymupdf.Rect(0, 0, pw, ph),
                    'detail': '内嵌位图 %dx%d %s（噪点纹理/栅格化磨砂多为此类）'
                              % (w, h, info.get('ext', '?'))})

    # --- 阴影：两个近似同尺寸块，一个偏移且颜色更深 ---
    # 实测 typst 的 shadowed 是「外扩一圈的底色块」+「卡片块」，
    # 两者宽高只差 spread/depth。判据不能要求颜色不同（浅色阴影几乎同色），
    # 只看几何：宽高大 0.5~6pt 且右下都外扩。
    for a in fills:
        for b in fills:
            if a is b:
                continue
            ra, rb = a['rect'], b['rect']
            dw = ra.width - rb.width
            dh = ra.height - rb.height
            if not (0.4 < dw <= 16 and 0.4 < dh <= 16):
                continue
            # 外扩块应该左下同起点、右下更大
            if abs(ra.x0 - rb.x0) > 1.5 or abs(ra.y0 - rb.y0) > 1.5:
                continue
            out.append({'kind': 'shadow', 'rect': ra,
                        'detail': '投影层外扩 %.1f×%.1fpt  阴影色=%s 卡色=%s'
                                  % (dw, dh, a['fill'], b['fill'])})
            break   # 只退出内层：外层继续找下一张卡，否则多卡只报第一条

    # --- 磨砂 / 泛光：靠 opacity 判 ---
    for d in p.get_drawings():
        rr = d.get('rect')
        if rr is None or rr.is_empty:
            continue
        fo = d.get('fill_opacity')
        so = d.get('stroke_opacity')
        if fo is not None and 0.05 < fo < 0.95 and d.get('fill'):
            out.append({'kind': 'translucent_fill', 'rect': rr,
                        'detail': '半透明填充 opacity=%.2f 色=%s（磨砂/叠层）'
                                  % (fo, _hex(d.get('fill')))})
        if so is not None and 0.05 < so < 0.95 and d.get('color'):
            out.append({'kind': 'glow', 'rect': rr,
                        'detail': '低透明度描边 opacity=%.2f 色=%s（泛光外圈）'
                                  % (so, _hex(d.get('color')))})

    # --- 渐变：bboxlog 的 fill-shade ---
    n_shade = sum(1 for k, _ in p.get_bboxlog() if k == 'fill-shade')
    if n_shade:
        out.append({'kind': 'gradient', 'rect': pymupdf.Rect(0, 0, pw, ph),
                    'detail': 'shading 填充 %d 处（线性/径向渐变）' % n_shade})

    # --- 曲线/波浪：细长描边路径（不是卡片边框）---
    # 卡片边框虽然也是 stroke，但它是「填充块的描边」，宽高比正常；
    # 真正的 curve/wave 是高度很小(<=30pt)、宽度很大(>=120pt)的开放路径。
    # 实测 curve 的 svg 高度约 70 用户单位缩放到 ~30pt，波浪线更扁。
    for s in strokes:
        r = s['rect']
        if r.width >= 120 and r.height <= 30 and s.get('stroke'):
            dash = None
            for d in p.get_drawings():
                if d.get('type') in ('s', 'fs') and d.get('rect') and \
                        abs(d['rect'].x0 - r.x0) < 0.6 and abs(d['rect'].y0 - r.y0) < 0.6:
                    dash = d.get('dashes')
                    break
            out.append({'kind': 'curve', 'rect': r,
                        'detail': '细长描边路径 %s  %.0f×%.0fpt  dash=%s（曲线/波浪/装饰线）'
                                  % (s['stroke'], r.width, r.height, dash)})

    return out


def anomalies(p, tol=1.0):
    """判据式检查：不需要看图就能报出的确定性问题。

    只报「有明确判据」的问题，不猜美观：
      - cross_border  文字跨越形状边框（压穿/压线的数学定义）
      - overlap       两个文字块真正重叠（不是贴边）
      - out_of_page   元素超出页面可打印区域
      - empty_page    整页没有任何文字
      - tofu          字体缺字形

    cross_border 是本文件最有价值的一条。实测证据：
      _vis.pdf 里 `工程师` 的 bbox=(170,368,202,379)，而 cert 证书框底边 y=370，
      文字横跨 368→379 正好压在边框线上，渲染出来就是边框从字中间穿过。
      人眼看图能发现"压穿"，但说不出压在哪、压了多少；这里给的是坐标和 pt 数。
    """
    shapes, texts, pw, ph = collect(p)
    out = []

    # 收集填充区（用来判断文字是否被完整包住）
    fill_rects = [s['rect'] for s in shapes if s['kind'] == 'fill']
    border_rects = [(s['rect'], s.get('stroke')) for s in shapes
                    if s['kind'] in ('stroke', 'fill') and s.get('stroke')]

    def contained_in_any(r):
        for fr in fill_rects:
            if (r.x0 >= fr.x0 - tol and r.x1 <= fr.x1 + tol
                    and r.y0 >= fr.y0 - tol and r.y1 <= fr.y1 + tol):
                return True
        return False

    # 1) 跨越边框 = 与描边框相交 + 不被任何填充区完整包住
    for t in texts:
        tr = t['rect']
        if contained_in_any(tr):
            continue
        for br, _sc in border_rects:
            ix = min(tr.x1, br.x1) - max(tr.x0, br.x0)
            iy = min(tr.y1, br.y1) - max(tr.y0, br.y0)
            if ix > tol and iy > tol:
                inside = (tr.x0 >= br.x0 - tol and tr.x1 <= br.x1 + tol
                          and tr.y0 >= br.y0 - tol and tr.y1 <= br.y1 + tol)
                if not inside:
                    out.append(('cross_border', tr,
                                '文字跨越边框 %.1fpt：%r  bbox=(%.1f,%.1f,%.1f,%.1f) 框=(%.1f,%.1f,%.1f,%.1f)'
                                % (iy, t['text'][:20], tr.x0, tr.y0, tr.x1, tr.y1,
                                   br.x0, br.y0, br.x1, br.y1)))
                break

    # 2) 豆腐块
    for t in texts:
        if '\ufffd' in t['text']:
            out.append(('tofu', t['rect'], '文字含替换符，字体缺字形：%r' % t['text'][:30]))

    # 2.5) 图像压字：fx gradient / noise / 二维码等会以 image 形式插入，
    #      它们不在 get_drawings() 里（在 get_image_info()），原来完全没查，
    #      导致「渐变图高 177pt 压住下一个标题」这种严重重叠报 0 条。
    try:
        _raw_imgs = [pymupdf.Rect(i['bbox']) for i in p.get_image_info()]
    except Exception:
        _raw_imgs = []
    # PyMuPDF 对同一张图会重复返回多条（实测一张图报 4 次），先按几何去重，
    # 否则图像两两比对会变成 N×N 的重复噪音，把真正的 image_over_text 淹掉。
    imgs = []
    for _r in _raw_imgs:
        if not any(abs(_r.x0 - x.x0) < 0.5 and abs(_r.y0 - x.y0) < 0.5
                   and abs(_r.width - x.width) < 0.5 and abs(_r.height - x.height) < 0.5
                   for x in imgs):
            imgs.append(_r)
    for ir in imgs:
        for t in texts:
            tr = t['rect']
            ox = min(tr.x1, ir.x1) - max(tr.x0, ir.x0)
            oy = min(tr.y1, ir.y1) - max(tr.y0, ir.y0)
            if not (ox > 2.0 and oy > 2.0):
                continue
            inside = (tr.x0 >= ir.x0 - 1 and tr.x1 <= ir.x1 + 1
                      and tr.y0 >= ir.y0 - 1 and tr.y1 <= ir.y1 + 1)
            if inside:
                # 完全在图内，可能是「fx-card 正文」（设计如此）也可能是「被压住的后续标题」。
                # 判据：这张图是否被人为撑到远超常规高度。fx gradient 默认 h=220 用户单位
                # ≈ 176pt，若超过 1.3 倍说明图片溢出自己的容器，压住了后面的内容。
                if ir.height > 230:
                    out.append(('image_over_text', tr,
                                '文字被超高图像覆盖（图高 %.0fpt，疑似溢出容器）：%r'
                                % (ir.height, t['text'][:20])))
                continue
            out.append(('image_over_text', tr,
                        '图像压住文字 %.1fpt 高：%r  bbox y=%.1f~%.1f 图 y=%.1f~%.1f'
                        % (oy, t['text'][:20], tr.y0, tr.y1, ir.y0, ir.y1)))

    # 2.6) 图像互相重叠（同一区域叠了多张，多半是尺寸算错没撑开）
    for i in range(len(imgs)):
        for j in range(i + 1, len(imgs)):
            a, b = imgs[i], imgs[j]
            ox = min(a.x1, b.x1) - max(a.x0, b.x0)
            oy = min(a.y1, b.y1) - max(a.y0, b.y0)
            if ox > 4.0 and oy > 4.0:
                # 同位置同尺寸的重复条目（PyMuPDF 有时一张图报多次）要跳过
                if abs(a.x0 - b.x0) < 0.5 and abs(a.y0 - b.y0) < 0.5 \
                        and abs(a.width - b.width) < 0.5 and abs(a.height - b.height) < 0.5:
                    continue
                out.append(('image_overlap', a,
                            '两张图重叠 %.1f×%.1fpt  图1 y=%.1f~%.1f 图2 y=%.1f~%.1f'
                            % (ox, oy, a.y0, a.y1, b.y0, b.y1)))

    # 3) 文字两两重叠
    #    只报「明显压字」，不报排版正常的相邻/叠字：
    #    - 引号、括号这类单字符 span 与正文行框相交是中文排版常态（实测 _sl3 第3页误报）
    #    - 阈值取 3pt 以上，1~2pt 的多半是行框 padding
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i]['rect'], texts[j]['rect']
            ta, tb = texts[i]['text'].strip(), texts[j]['text'].strip()
            if len(ta) <= 2 or len(tb) <= 2:
                continue          # 引号/顿号这类标点独立 span，不算压字
            ox = min(a.x1, b.x1) - max(a.x0, b.x0)
            oy = min(a.y1, b.y1) - max(a.y0, b.y0)
            if ox > 3.0 and oy > 3.0:
                out.append(('overlap', a,
                            '两段文字重叠 %.1f×%.1fpt：%r × %r'
                            % (ox, oy, texts[i]['text'][:18], texts[j]['text'][:18])))

    # 4) 超出页面
    for t in texts:
        r = t['rect']
        if r.x1 > pw + tol or r.y1 > ph + tol or r.x0 < -tol or r.y0 < -tol:
            out.append(('out_of_page', r, '文字超出页面：%r' % t['text'][:24]))

    # 5) 空页
    if not texts:
        out.append(('empty_page', pymupdf.Rect(0, 0, pw, ph), '整页没有任何文字'))

    return out


def dump(p, idx):
    shapes, texts, pw, ph = collect(p)
    wmm, hmm = _page_size_mm(p)
    L = []
    L.append('页%d  %.1f×%.1f mm  形状%d 文字%d' % (idx, wmm, hmm, len(shapes), len(texts)))
    for s in shapes:
        rr = s['rect']
        L.append('  [%-6s] x=%.1f y=%.1f w=%.1f h=%.1f  fill=%s %s' % (
            s['kind'], rr.x0, rr.y0, rr.width, rr.height,
            s['fill'] or '-', s.get('note', '')))
    for t in texts:
        rr = t['rect']
        L.append('  [text  ] x=%.1f y=%.1f w=%.1f h=%.1f  size=%.1f  %r' % (
            rr.x0, rr.y0, rr.width, rr.height, t['size'], t['text'][:40]))
    return '\n'.join(L)


def run(path, pages='1', cols=72, detail='full'):
    """给 core.cmd_xray 调用的入口，直接返回可 JSON 化的 dict。

    detail 三档：
      full  字符画 + 可疑 + 特效 + 元素清单（最完整）
      art   只要字符画
      brief 只要可疑 + 特效（不看图也能判断有没有出问题）
    """
    D = pymupdf.open(path)
    nums = []
    for part in str(pages).replace('，', ',').split(','):
        part = part.strip()
        if not part:
            continue
        if part.lower() == 'all':
            nums = list(range(1, D.page_count + 1))
            break
        if '-' in part:
            a, b = part.split('-', 1)
            try:
                nums.extend(range(int(a), int(b) + 1))
            except Exception:
                pass
        else:
            try:
                nums.append(int(part))
            except Exception:
                pass
    if not nums:
        nums = [1]

    out_pages = []
    total_anom = 0
    for n in nums:
        if not (1 <= n <= D.page_count):
            continue
        p = D[n - 1]
        wmm, hmm = _page_size_mm(p)
        rec = {'page': n, 'size_mm': [round(wmm, 1), round(hmm, 1)]}

        an = anomalies(p)
        total_anom += len(an)
        if an:
            rec['anomalies'] = [{'kind': k, 'x': round(r.x0, 1), 'y': round(r.y0, 1),
                                 'msg': m} for k, r, m in an]

        fx = effects(p)
        if fx:
            rec['effects'] = [{'kind': e['kind'],
                               'x': round(e['rect'].x0, 1), 'y': round(e['rect'].y0, 1),
                               'w': round(e['rect'].width, 1), 'h': round(e['rect'].height, 1),
                               'detail': e['detail']} for e in fx]

        if detail in ('full', 'art'):
            rec['art'] = art(p, cols=int(cols))
        if detail == 'full':
            shapes, texts, pw, ph = collect(p)
            rec['elements'] = (
                [{'type': s['kind'], 'x': round(s['rect'].x0, 1), 'y': round(s['rect'].y0, 1),
                  'w': round(s['rect'].width, 1), 'h': round(s['rect'].height, 1),
                  'fill': s.get('fill'), 'stroke': s.get('stroke')}
                 for s in shapes]
                + [{'type': 'text', 'x': round(t['rect'].x0, 1), 'y': round(t['rect'].y0, 1),
                    'w': round(t['rect'].width, 1), 'h': round(t['rect'].height, 1),
                    'size': round(t['size'], 1), 'color': t['color'], 'text': t['text'][:60]}
                   for t in texts]
            )
        out_pages.append(rec)

    doc_pages = D.page_count
    D.close()
    return {'pages_total': doc_pages, 'pages_read': len(out_pages),
            'anomalies_total': total_anom, 'detail': detail, 'data': out_pages}


if __name__ == '__main__':
    import sys
    path = sys.argv[1]
    pages = sys.argv[2] if len(sys.argv) > 2 else '1'
    cols = sys.argv[3] if len(sys.argv) > 3 else 72
    detail = sys.argv[4] if len(sys.argv) > 4 else 'full'
    R = run(path, pages, cols, detail)
    for rec in R['data']:
        print('=' * 24, 'page', rec['page'], '=' * 24)
        if rec.get('art'):
            print(rec['art'])
            print()
        if rec.get('anomalies'):
            print('[可疑]')
            for a in rec['anomalies']:
                print('  %-12s (%.1f,%.1f) %s' % (a['kind'], a['x'], a['y'], a['msg']))
            print()
        if rec.get('effects'):
            print('[特效]')
            for e in rec['effects']:
                print('  %-16s (%6.1f,%6.1f, %6.1f×%6.1f)  %s'
                      % (e['kind'], e['x'], e['y'], e['w'], e['h'], e['detail']))
            print()
        if rec.get('elements'):
            print('[元素]')
            for el in rec['elements']:
                if el['type'] == 'text':
                    print('  [text  ] (%6.1f,%6.1f %5.1f×%5.1f) size=%-4.1f %r'
                          % (el['x'], el['y'], el['w'], el['h'], el['size'], el['text'][:36]))
                else:
                    print('  [%-6s] (%6.1f,%6.1f %5.1f×%5.1f) fill=%s stroke=%s'
                          % (el['type'], el['x'], el['y'], el['w'], el['h'],
                             el['fill'] or '-', el['stroke'] or '-'))
            print()
