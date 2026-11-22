# -*- coding: utf-8 -*-
"""Mermaid 扩展图类型 -> SVG（自包含，零外部依赖）
支持：sequenceDiagram / gantt / classDiagram / subgraph（flowchart 内嵌）

设计原则：
- 每个 renderer 只处理一种语法，输入是源码字符串，输出 (svg_text, width, height)
- 不做通用图形抽象，各图类型几何差异太大，硬抽会互相污染
- 中文宽度按 1.0em 估，ASCII 按 0.55em 估（和 mermaid.py 的 text_w 保持一致）
"""
import re
import html

FONT = '"Noto Sans CJK SC","Source Han Sans SC",sans-serif'
EDGE_C = '#8A93A0'
TEXT_C = '#2F3742'
MUTED_C = '#6B7684'
ACCENT = '#2547A8'
ACCENT2 = '#1F7A5C'
WARN_C = '#B45309'

# 中性色板，按出现顺序循环
PALETTE = ['#2547A8', '#1F7A5C', '#B45309', '#7C3AED', '#0F766E', '#BE123C']


def esc(s):
    return html.escape(str(s), quote=True)


def text_w(t, size=13.0):
    """估算文本宽度：中文 1.0em，ASCII 0.55em。"""
    w = 0.0
    for ch in str(t):
        w += (1.0 if ord(ch) > 0x2E80 else 0.55) * size
    return w


def detect_kind(src):
    """识别图类型。返回 flowchart / sequence / gantt / class / unknown。"""
    for raw in src.replace('\r', '').split('\n'):
        ln = raw.strip()
        if not ln or ln.startswith('%%'):
            continue
        low = ln.lower()
        if re.match(r'^(graph|flowchart)\b', low):
            return 'flowchart'
        if re.match(r'^sequencediagram\b', low):
            return 'sequence'
        if re.match(r'^gantt\b', low):
            return 'gantt'
        if re.match(r'^(classdiagram|classDiagram)\b', ln, re.I):
            return 'class'
        return 'unknown'
    return 'unknown'


# ============================================================
# 1. sequenceDiagram
# ============================================================

def _parse_sequence(src):
    """返回 (participants[list of (id,label)], messages[list of dict])"""
    parts = []          # [(id, label)]
    seen = {}
    msgs = []
    notes = []
    for raw in src.replace('\r', '').split('\n'):
        ln = raw.strip()
        if not ln or ln.startswith('%%'):
            continue
        low = ln.lower()
        if low.startswith('sequencediagram'):
            continue
        m = re.match(r'^(?:participant|actor)\s+(\S+)(?:\s+as\s+(.+))?$', ln, re.I)
        if m:
            pid = m.group(1)
            label = (m.group(2) or pid).strip()
            if pid not in seen:
                seen[pid] = True
                parts.append((pid, label))
            continue
        m = re.match(r'^note\s+(left of|right of|over)\s+([^:]+):\s*(.*)$', ln, re.I)
        if m:
            notes.append((m.group(1).lower(), m.group(2).strip(), m.group(3).strip()))
            continue
        # 消息：A->>B: text / A-->B: text / A->B: text / A--xB: text
        m = re.match(r'^(.+?)\s*(-{1,2}>>?|-{1,2}x|-->>|->>)\s*(.+?)\s*:\s*(.*)$', ln)
        if m:
            a, arrow, b, txt = m.group(1).strip(), m.group(2), m.group(3).strip(), m.group(4).strip()
            dashed = arrow.startswith('--')
            cross = arrow.endswith('x')
            for pid in (a, b):
                if pid not in seen and pid not in ('', 'Note'):
                    seen[pid] = True
                    parts.append((pid, pid))
            msgs.append(dict(a=a, b=b, text=txt, dashed=dashed, cross=cross))
            continue
    return parts, msgs, notes


def render_sequence(src):
    parts, msgs, notes = _parse_sequence(src)
    if not parts:
        return None

    n = len(parts)
    col_w = 130.0
    left_pad = 30.0
    top = 24.0
    head_h = 34.0
    msg_gap = 42.0
    bottom_pad = 30.0

    # 每条消息可能加宽列间距
    max_txt = 0.0
    for m in msgs:
        max_txt = max(max_txt, text_w(m['text'], 12.0))
    col_w = max(col_w, min(200.0, max_txt * 0.9 + 40.0))

    W = left_pad * 2 + col_w * n
    H = top + head_h + msg_gap * max(1, len(msgs)) + bottom_pad + (22.0 * len(notes))
    cx = {}
    for i, (pid, label) in enumerate(parts):
        cx[pid] = left_pad + col_w * i + col_w / 2

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" viewBox="0 0 %.0f %.0f">' % (W, H, W, H))
    out.append('<style>text{font-family:%s;}</style>' % FONT)
    out.append('<rect x="0" y="0" width="%.0f" height="%.0f" fill="#FFFFFF"/>' % (W, H))
    out.append('<defs><marker id="sq-arrow" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto">'
               '<path d="M0,0 L8,3 L0,6 z" fill="%s"/></marker></defs>' % EDGE_C)

    # participant 头 + 生命线
    for i, (pid, label) in enumerate(parts):
        x = cx[pid]
        bw = min(col_w - 16, text_w(label, 13.0) + 26)
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="4" fill="#EEF2F9" stroke="%s" stroke-width="1.2"/>' % (
            x - bw / 2, top, bw, head_h, ACCENT))
        out.append('<text x="%.1f" y="%.1f" font-size="13" fill="%s" text-anchor="middle" dominant-baseline="central">%s</text>' % (
            x, top + head_h / 2, TEXT_C, esc(label)))
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#C8D0DC" stroke-width="1.2" stroke-dasharray="4,4"/>' % (
            x, top + head_h, x, H - bottom_pad))

    # 消息
    y = top + head_h + msg_gap * 0.75
    for k, m in enumerate(msgs):
        a, b = m['a'], m['b']
        x1 = cx.get(a, left_pad)
        x2 = cx.get(b, left_pad)
        color = PALETTE[k % len(PALETTE)] if a != b else EDGE_C
        dash = ' stroke-dasharray="5,4"' if m['dashed'] else ''
        marker = '' if m['cross'] else ' marker-end="url(#sq-arrow)"'
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.4"%s%s/>' % (
            x1, y, x2, y, color, dash, marker))
        if m['cross']:
            out.append('<path d="M%.1f,%.1f l7,7 M%.1f,%.1f l-7,7" stroke="%s" stroke-width="1.6"/>' % (
                x2 - 4, y - 4, x2 - 4, y - 4, color))
        tx = (x1 + x2) / 2
        out.append('<text x="%.1f" y="%.1f" font-size="12" fill="%s" text-anchor="middle" dominant-baseline="central">%s</text>' % (
            tx, y - 9, TEXT_C, esc(m['text'])))
        y += msg_gap

    # notes 放在底部
    ny = H - bottom_pad + 4
    for pos, who, txt in notes:
        ids = [p.strip() for p in who.split(',') if p.strip()]
        xs = [cx[i] for i in ids if i in cx]
        if not xs:
            continue
        nx = sum(xs) / len(xs)
        nw = max(120.0, text_w(txt, 12.0) + 24)
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="22" rx="3" fill="#FFF8E1" stroke="%s" stroke-width="1"/>' % (
            nx - nw / 2, ny, nw, WARN_C))
        out.append('<text x="%.1f" y="%.1f" font-size="12" fill="%s" text-anchor="middle" dominant-baseline="central">%s</text>' % (
            nx, ny + 11, TEXT_C, esc(txt)))
        ny += 22

    out.append('</svg>')
    return '\n'.join(out), W, H


# ============================================================
# 2. gantt
# ============================================================

def _parse_gantt(src):
    """返回 (sections[(name,[tasks])], tasks: [{name, start, dur, section}], axis_fmt)"""
    tasks = []
    sections = []
    cur_section = ''
    axis_fmt = '%m-%d'
    for raw in src.replace('\r', '').split('\n'):
        ln = raw.strip()
        if not ln or ln.startswith('%%'):
            continue
        low = ln.lower()
        if low.startswith('gantt'):
            continue
        if low.startswith('title'):
            continue
        m = re.match(r'^dateformat\s+(\S+)', low)
        if m:
            axis_fmt = m.group(1)
            continue
        if low.startswith(('axisformat', 'excludes', 'todaymarker', 'weekday')):
            continue
        m = re.match(r'^section\s+(.+)$', ln, re.I)
        if m:
            cur_section = m.group(1).strip()
            sections.append((cur_section, []))
            continue
        # task: 名称 :tag, id, start, dur
        m = re.match(r'^(.+?)\s*:\s*(.+)$', ln)
        if m:
            name = m.group(1).strip()
            meta = [x.strip() for x in m.group(2).split(',')]
            tags = []
            vals = []
            for it in meta:
                if it in ('done', 'active', 'crit', 'milestone'):
                    tags.append(it)
                elif it:
                    vals.append(it)
            if not vals:
                continue
            # vals 可能是 [id, start, dur] / [start, dur] / [dur]
            start, dur = '0', '1'
            if len(vals) >= 3:
                start, dur = vals[1], vals[2]
            elif len(vals) == 2:
                start, dur = vals[0], vals[1]
            elif len(vals) == 1:
                dur = vals[0]
            tasks.append(dict(name=name, start=start, dur=dur, tags=tags,
                              section=cur_section, id=vals[0] if len(vals) >= 3 else ''))
            if cur_section and sections:
                sections[-1][1].append(tasks[-1])
            continue
    return sections, tasks, axis_fmt


def _gantt_num(s):
    """把 start/dur 解析成数值。日期按 YYYY-MM-DD 转天数，d/w 后缀处理。"""
    s = str(s).strip()
    m = re.match(r'^(\d{4})-(\d{1,2})-(\d{1,2})$', s)
    if m:
        import datetime
        try:
            d = datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return d.toordinal()
        except Exception:
            return 0
    m = re.match(r'^(\d+(?:\.\d+)?)\s*([dwmy]?)$', s, re.I)
    if m:
        v = float(m.group(1))
        u = (m.group(2) or 'd').lower()
        return v * {'d': 1, 'w': 7, 'm': 30, 'y': 365}.get(u, 1)
    return 0


def render_gantt(src):
    sections, tasks, axis_fmt = _parse_gantt(src)
    if not tasks:
        return None

    # 计算绝对时间轴：start 可能是绝对日期或相对 after xxx
    base = None
    order = []
    for t in tasks:
        st = _gantt_num(t['start'])
        if base is None and st > 100000:
            base = st
        order.append(t)

    # start 是日期 -> 绝对；否则按累加
    cursor = 0.0
    for t in tasks:
        st = _gantt_num(t['start'])
        du = _gantt_num(t['dur']) or 1
        if st > 100000:
            t['_s'] = st
            cursor = st + du
        else:
            if base is not None and st > 0 and st < 1000:
                t['_s'] = base + st
            else:
                t['_s'] = cursor
            cursor = t['_s'] + du
        t['_d'] = du

    t0 = min(t['_s'] for t in tasks)
    t1 = max(t['_s'] + t['_d'] for t in tasks)
    span = max(1.0, t1 - t0)

    label_w = max(text_w(t['name'], 12.5) for t in tasks) + 30
    label_w = max(120.0, min(260.0, label_w))
    row_h = 30.0
    top = 22.0
    head_h = 26.0
    W = max(560.0, label_w + 60 + 380.0)

    # 分组：有 section 的按 section 分行 + 段头
    groups = []
    if sections and any(s[1] for s in sections):
        for sname, sts in sections:
            groups.append((sname, sts))
    else:
        groups.append(('', tasks))

    nrows = sum(len(g[1]) for g in groups) + sum(1 for g in groups if g[0])
    H = top + head_h + row_h * nrows + 24.0

    chart_x0 = label_w + 12
    chart_w = W - chart_x0 - 24

    def x_of(v):
        return chart_x0 + (v - t0) / span * chart_w

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" viewBox="0 0 %.0f %.0f">' % (W, H, W, H))
    out.append('<style>text{font-family:%s;}</style>' % FONT)
    out.append('<rect x="0" y="0" width="%.0f" height="%.0f" fill="#FFFFFF"/>' % (W, H))

    # 时间刻度：等分 span，按 axis_fmt 显示
    ticks = 6
    ty = top
    out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#D8DEE8" stroke-width="1"/>' % (
        chart_x0, ty + head_h - 6, chart_x0 + chart_w, ty + head_h - 6))
    for k in range(ticks + 1):
        v = t0 + span * k / ticks
        x = x_of(v)
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#EDF1F6" stroke-width="1"/>' % (
            x, ty + head_h - 6, x, H - 20))
        lab = ''
        if v >= 100000:
            import datetime
            try:
                lab = datetime.date.fromordinal(int(v)).strftime('%m-%d')
            except Exception:
                lab = ''
        else:
            lab = str(int(round(v)))
        if lab:
            out.append('<text x="%.1f" y="%.1f" font-size="10.5" fill="%s" text-anchor="middle">%s</text>' % (
                x, ty + 10, MUTED_C, esc(lab)))

    y = ty + head_h
    k = 0
    for sname, sts in groups:
        if sname:
            out.append('<text x="12" y="%.1f" font-size="11.5" fill="%s" font-weight="bold">%s</text>' % (
                y + row_h * 0.6, MUTED_C, esc(sname)))
            y += row_h
        for t in sts:
            x = x_of(t['_s'])
            w = max(6.0, x_of(t['_s'] + t['_d']) - x)
            color = PALETTE[k % len(PALETTE)]
            if 'crit' in t['tags']:
                color = '#BE123C'
            elif 'done' in t['tags']:
                color = '#7A8494'
            elif 'active' in t['tags']:
                color = ACCENT
            out.append('<text x="12" y="%.1f" font-size="12" fill="%s" dominant-baseline="central">%s</text>' % (
                y + row_h / 2, TEXT_C, esc(t['name'])))
            bh = 15.0
            out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3.5" fill="%s" opacity="0.92"/>' % (
                x, y + (row_h - bh) / 2, w, bh, color))
            if 'milestone' in t['tags']:
                mx = x + w / 2
                my = y + row_h / 2
                # 菱形：从顶点顺时针画四个边，闭合成 z
                out.append('<path d="M%.1f,%.1f L%.1f,%.1f L%.1f,%.1f L%.1f,%.1f Z" fill="%s"/>' % (
                    mx, my - 8, mx + 8, my, mx, my + 8, mx - 8, my, color))
            y += row_h
            k += 1

    out.append('</svg>')
    return '\n'.join(out), W, H


# ============================================================
# 3. classDiagram
# ============================================================

def _parse_class(src):
    """返回 (classes: {name: {attrs:[], methods:[]}}, relations: [{a,b,kind,label}])"""
    classes = {}
    rels = []
    cur = None
    for raw in src.replace('\r', '').split('\n'):
        ln = raw.rstrip()
        s = ln.strip()
        if not s or s.startswith('%%'):
            continue
        if re.match(r'^classDiagram\b', s, re.I):
            continue
        if s == '}':
            cur = None
            continue
        m = re.match(r'^class\s+(\w+)\s*\{\s*$', s)
        if m:
            cur = m.group(1)
            classes.setdefault(cur, dict(attrs=[], methods=[]))
            continue
        m = re.match(r'^class\s+(\w+)$', s)
        if m:
            classes.setdefault(m.group(1), dict(attrs=[], methods=[]))
            cur = None
            continue
        if cur:
            if '(' in s and ')' in s:
                classes[cur]['methods'].append(s.rstrip(';'))
            else:
                classes[cur]['attrs'].append(s.rstrip(';'))
            continue
        # 关系：A <|-- B / A --> B : label / A *-- B / A o-- B / A ..> B
        m = re.match(r'^(\w+)\s*([<|>*o.\-]{2,})\s*(\w+)(?:\s*:\s*(.+))?$', s)
        if m:
            a, arrow, b, lbl = m.group(1), m.group(2), m.group(3), (m.group(4) or '').strip()
            classes.setdefault(a, dict(attrs=[], methods=[]))
            classes.setdefault(b, dict(attrs=[], methods=[]))
            if '<|' in arrow:
                kind = 'inherit'
            elif '*--' in arrow:
                kind = 'compose'
            elif 'o--' in arrow:
                kind = 'aggregate'
            elif '..>' in arrow or '..|>' in arrow:
                kind = 'depend'
            else:
                kind = 'assoc'
            rels.append(dict(a=a, b=b, kind=kind, label=lbl))
    return classes, rels


def render_class(src):
    classes, rels = _parse_class(src)
    if not classes:
        return None

    # 卡片尺寸
    PAD = 12.0
    LINE_H = 18.0
    HEAD_H = 30.0
    col_gap = 60.0
    row_gap = 70.0

    boxes = {}
    for name, body in classes.items():
        w = max(text_w(name, 13.5) + 28,
                max([text_w(x, 11.5) + 24 for x in body['attrs']] or [0]),
                max([text_w(x, 11.5) + 24 for x in body['methods']] or [0]))
        w = max(140.0, min(300.0, w))
        h = HEAD_H + LINE_H * (len(body['attrs']) + len(body['methods']) + 1)
        if not body['attrs'] and not body['methods']:
            h = HEAD_H + 12
        boxes[name] = dict(w=w, h=h, x=0.0, y=0.0)

    # 网格布局：按 sqrt 列数排
    import math
    n = len(boxes)
    cols = max(1, int(math.ceil(math.sqrt(n))))
    rows = int(math.ceil(n / cols))
    col_w = max(b['w'] for b in boxes.values()) + col_gap
    row_h = max(b['h'] for b in boxes.values()) + row_gap

    for i, name in enumerate(boxes):
        r, c = divmod(i, cols)
        b = boxes[name]
        b['x'] = 24 + c * col_w + (max(x['w'] for x in boxes.values()) - b['w']) / 2
        b['y'] = 24 + r * row_h

    W = 48 + col_w * cols
    H = 48 + row_h * rows

    out = []
    out.append('<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" viewBox="0 0 %.0f %.0f">' % (W, H, W, H))
    out.append('<style>text{font-family:%s;}</style>' % FONT)
    out.append('<rect x="0" y="0" width="%.0f" height="%.0f" fill="#FFFFFF"/>' % (W, H))
    out.append('<defs><marker id="cd-hollow" markerWidth="13" markerHeight="13" refX="11" refY="4.5" orient="auto">'
               '<path d="M0,0 L11,4.5 L0,9 z" fill="#FFFFFF" stroke="%s" stroke-width="1.2"/></marker>' % EDGE_C)
    out.append('<marker id="cd-arrow" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto">'
               '<path d="M0,0 L8,3 L0,6 z" fill="%s"/></marker></defs>' % EDGE_C)

    def anchor(name, tx, ty):
        """取盒子朝目标方向的边中点"""
        b = boxes[name]
        cx = b['x'] + b['w'] / 2
        cy = b['y'] + b['h'] / 2
        dx, dy = tx - cx, ty - cy
        if abs(dx) * b['h'] > abs(dy) * b['w']:
            return (b['x'] + b['w'] if dx > 0 else b['x'], cy)
        return (cx, b['y'] + b['h'] if dy > 0 else b['y'])

    # 关系线先画
    for r in rels:
        if r['a'] not in boxes or r['b'] not in boxes:
            continue
        ba, bb = boxes[r['a']], boxes[r['b']]
        pa = anchor(r['a'], bb['x'] + bb['w'] / 2, bb['y'] + bb['h'] / 2)
        pb = anchor(r['b'], ba['x'] + ba['w'] / 2, ba['y'] + ba['h'] / 2)
        dash = ' stroke-dasharray="5,4"' if r['kind'] == 'depend' else ''
        mk = ' marker-end="url(#cd-arrow)"'
        if r['kind'] in ('inherit',):
            mk = ' marker-end="url(#cd-hollow)"'
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.5"%s%s/>' % (
            pa[0], pa[1], pb[0], pb[1], EDGE_C, dash, mk))
        if r['label']:
            mx, my = (pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2
            out.append('<text x="%.1f" y="%.1f" font-size="11" fill="%s" text-anchor="middle">%s</text>' % (
                mx, my - 5, MUTED_C, esc(r['label'])))

    # 盒子
    for name, body in classes.items():
        b = boxes[name]
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="#FFFFFF" stroke="%s" stroke-width="1.4"/>' % (
            b['x'], b['y'], b['w'], b['h'], ACCENT))
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="#EEF2F9"/>' % (
            b['x'], b['y'], b['w'], HEAD_H))
        out.append('<text x="%.1f" y="%.1f" font-size="13.5" font-weight="bold" fill="%s" text-anchor="middle" dominant-baseline="central">%s</text>' % (
            b['x'] + b['w'] / 2, b['y'] + HEAD_H / 2, TEXT_C, esc(name)))
        ty = b['y'] + HEAD_H + 6
        for a in body['attrs']:
            out.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="%s" dominant-baseline="central">%s</text>' % (
                b['x'] + PAD, ty, TEXT_C, esc(a)))
            ty += LINE_H
        if body['attrs'] and body['methods']:
            out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="#DCE3EE" stroke-width="1"/>' % (
                b['x'], ty - 6, b['x'] + b['w'], ty - 6))
        for mth in body['methods']:
            out.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="%s" dominant-baseline="central">%s</text>' % (
                b['x'] + PAD, ty, ACCENT2, esc(mth)))
            ty += LINE_H

    out.append('</svg>')
    return '\n'.join(out), W, H


# ============================================================
# 4. subgraph 支持（flowchart 内嵌）
# ============================================================

def extract_subgraphs(src):
    """从 flowchart 源码里抠出 subgraph 结构。
    返回 (clean_src, subs: [(id, title, [node_ids])], node_in_sub: {node: sub_id})
    做法：把 subgraph/end 行去掉，让 flowchart 主解析认得节点和边；
    子图归属单独记，渲染时画底板 + 标题。
    """
    subs = []
    node_in_sub = {}
    keep = []
    cur = None
    stack = []
    for raw in src.replace('\r', '').split('\n'):
        ln = raw.strip()
        # subgraph 语法：subgraph id[标题] / subgraph 标题 / subgraph id
        m = re.match(r'^subgraph\s+([^\s\[\]]+)\s*(?:\[\s*(.+?)\s*\])?\s*$', ln, re.I)
        if not m:
            # subgraph 标题里有空格但不带 id：subgraph 接入层
            m2 = re.match(r'^subgraph\s+(.+)$', ln, re.I)
            if m2:
                title = m2.group(1).strip()
                sid = 'sg%d' % (len(subs) + 1)
                cur = (sid, title, [])
                subs.append(cur)
                stack.append(cur)
                continue
        if m:
            sid = m.group(1).strip()
            title = (m.group(2) or sid).strip()
            cur = (sid, title, [])
            subs.append(cur)
            stack.append(cur)
            continue
        if re.match(r'^end\s*$', ln, re.I):
            if stack:
                stack.pop()
            cur = stack[-1] if stack else None
            continue
        keep.append(raw)
        # 记录这行出现的节点 id（粗提取：标识符后接形状符号或纯标识符）
        if cur is not None and ln and not ln.startswith('%%'):
            for nid in re.findall(r'(?:^|[\s\-\.=>|])([A-Za-z_][\w]*)', ln):
                if nid.lower() in ('graph', 'flowchart', 'td', 'tb', 'bt', 'lr', 'rl',
                                   'subgraph', 'end', 'style', 'classdef', 'class', 'click'):
                    continue
                node_in_sub.setdefault(nid, cur[0])
                if nid not in cur[2]:
                    cur[2].append(nid)
    return '\n'.join(keep), subs, node_in_sub
