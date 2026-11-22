# -*- coding: utf-8 -*-
"""Mermaid flowchart -> SVG（自包含，零外部依赖）
支持：graph/flowchart TD|TB|BT|LR|RL、节点形状、边类型、语义色分支、跨层绕行
"""
import re as _re
import html as _html
from collections import defaultdict as _dd, deque as _dq
# 兼容别名
re = _re
html = _html
defaultdict = _dd
deque = _dq


# ============================================================
# from mparse.py
# ============================================================
# 节点形状：按长度降序匹配，避免 [[ 被 [ 抢先
SHAPES = [
    (r'\[\((.+?)\)\]', 'cyl'),      # [(数据库)]
    (r'\[\[(.+?)\]\]', 'sub'),      # [[子程序]]
    (r'\(\((.+?)\)\)', 'circle'),   # ((圆))
    (r'\(\[(.+?)\]\)', 'stad'),     # ([体育场])
    (r'\[(.+?)\]', 'rect'),         # [矩形]
    (r'\((.+?)\)', 'round'),        # (圆角)
    (r'\{(.+?)\}', 'dia'),          # {菱形}
    (r'>(.+?)\]', 'asym'),          # >不对称]
]

# 边：按长度降序
EDGES = [
    (r'--\s*([^->|]+?)\s*-->', 'arrow', True),   # -- 文字 -->
    (r'--\s*([^->|]+?)\s*---', 'line', True),    # -- 文字 ---
    (r'-\.\s*([^.>|]+?)\s*\.->', 'dotted', True),
    (r'==\s*([^=>|]+?)\s*==>', 'thick', True),
    (r'-->\|([^|]+?)\|', 'arrow', True),          # -->|文字|
    (r'---\|([^|]+?)\|', 'line', True),
    (r'-\.->\|([^|]+?)\|', 'dotted', True),
    (r'==>\|([^|]+?)\|', 'thick', True),
    (r'-->', 'arrow', False),
    (r'---', 'line', False),
    (r'-\.->', 'dotted', False),
    (r'==>', 'thick', False),
]

class Node:
    __slots__ = ('nid', 'label', 'shape', 'rank', 'x', 'y', 'w', 'h', 'order')
    def __init__(self, nid, label, shape):
        self.nid = nid
        self.label = label
        self.shape = shape
        self.rank = 0
        self.x = self.y = 0.0
        self.w = self.h = 0.0
        self.order = 0

class Edge:
    __slots__ = ('src', 'dst', 'kind', 'label')
    def __init__(self, src, dst, kind, label=''):
        self.src = src
        self.dst = dst
        self.kind = kind
        self.label = label

class Graph:
    def __init__(self):
        self.nodes = {}
        self.edges = []
        self.direction = 'TD'

    def node(self, nid, label=None, shape='rect'):
        n = self.nodes.get(nid)
        if n is None:
            n = Node(nid, label if label else nid, shape)
            self.nodes[nid] = n
        else:
            if label:
                n.label = label
            if shape != 'rect':
                n.shape = shape
        return n

def _strip_quotes(s):
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in '"\'':
        return s[1:-1]
    return s

def _match_shape(token):
    token = token.strip()
    if not token:
        return None
    m = _re.match(r'^([A-Za-z_][\w-]*)\s*(.*)$', token, re.S)
    if not m:
        return None
    nid = m.group(1)
    rest = m.group(2).strip()
    if not rest:
        return (nid, None, 'rect')
    for pat, shape in SHAPES:
        mm = _re.match('^' + pat + '$', rest, re.S)
        if mm:
            return (nid, _strip_quotes(mm.group(1)), shape)
    return (nid, None, 'rect')

def _find_edges(s):
    hits = []
    i = 0
    n = len(s)
    while i < n:
        best = None
        for pat, kind, has_label in EDGES:
            m = _re.compile(pat).match(s, i)
            if m:
                # 取最长匹配（优先带 label 的长形式）
                if best is None or m.end() > best[1]:
                    best = (i, m.end(), kind, (m.group(1) if has_label else ''))
        if best:
            hits.append(best)
            i = best[1]
        else:
            i += 1
    return hits

def _split_chain(s):
    s = s.strip().rstrip(';')
    if not s:
        return []
    hits = _find_edges(s)
    if not hits:
        return []
    out = []
    prev = None          # 上一个节点 token
    cur_start = 0
    for (st, en, kind, label) in hits:
        left_tok = s[cur_start:st].strip()
        if prev is None:
            lt = _match_shape(left_tok)
            if lt is None:
                # 左侧不是合法节点，跳过这个边
                cur_start = en
                continue
        else:
            lt = prev
        prev = lt
        # 右边 token 到下一个边开始（或结尾）
        nxt = [h for h in hits if h[0] >= en]
        nxt_end = nxt[0][0] if nxt else len(s)
        right_tok = s[en:nxt_end].strip()
        rt = _match_shape(right_tok) if right_tok else None
        if rt is None:
            # 右侧没有节点（如 A-->），跳过
            cur_start = nxt_end
            prev = None
            continue
        out.append((lt, kind, label, rt))
        prev = rt
        cur_start = nxt_end
    return out

def parse(src):
    g = Graph()
    lines = src.replace('\r', '').split('\n')
    for raw in lines:
        ln = raw.strip()
        if not ln or ln.startswith('%%'):
            continue
        # 头部
        h = _re.match(r'^(graph|flowchart)\s+(TD|TB|BT|LR|RL)\b', ln, re.I)
        if h:
            g.direction = h.group(2).upper()
            rest = ln[h.end():].strip().rstrip(';')
            if rest:
                _consume(g, rest)
            continue
        if _re.match(r'^(subgraph|end|style|classDef|class|click|linkStyle)\b', ln, re.I):
            continue
        _consume(g, ln)
    return g

def _consume(g, ln):
    # 拆多个语句（分号分隔），但要避开引号内分号
    parts = []
    buf = []
    q = None
    for ch in ln:
        if q:
            buf.append(ch)
            if ch == q:
                q = None
            continue
        if ch in '"\'':
            q = ch
            buf.append(ch)
            continue
        if ch == ';':
            parts.append(''.join(buf))
            buf = []
            continue
        buf.append(ch)
    parts.append(''.join(buf))
    for p in parts:
        p = p.strip()
        if not p:
            continue
        chain = _split_chain(p)
        if chain:
            for lt, kind, label, rt in chain:
                g.node(*lt)
                g.node(*rt)
                g.edges.append(Edge(lt[0], rt[0], kind, label))
        else:
            m = _match_shape(p)
            if m:
                g.node(*m)

# ============================================================
# from mlayout.py
# ============================================================
NODE_H = 50.0
MIN_W = 76.0
PAD_X = 26.0
RANK_GAP = 62.0      # 层间距
SIB_GAP = 26.0       # 同层节点间距
MARGIN = 30.0

_STYLE = {
    'start':  ('#E8EEFF', '#2F5BEA', '#14213D'),
    'end':    ('#E8EEFF', '#2F5BEA', '#14213D'),
    'rect':   ('#EEF3FF', '#2F5BEA', '#14213D'),
    'round':  ('#EEF3FF', '#2F5BEA', '#14213D'),
    'dia':    ('#FFF4E6', '#B5552B', '#2A1A13'),
    'action': ('#EAF7F1', '#1F7A5A', '#14251E'),
    'cyl':    ('#F3ECFB', '#6B3FA0', '#1F1729'),
    'sub':    ('#EEF3FF', '#2F5BEA', '#14213D'),
    'circle': ('#EEF3FF', '#2F5BEA', '#14213D'),
    'stad':   ('#EEF3FF', '#2F5BEA', '#14213D'),
    'asym':   ('#EEF3FF', '#2F5BEA', '#14213D'),
}

def text_w(t, size=15.0):
    w = 0.0
    for c in t:
        w += (size + 0.5) if ord(c) > 127 else (size * 0.55)
    return w

def node_size(n):
    tw = text_w(n.label)
    if n.shape == 'dia':
        return (max(tw + 44, MIN_W + 30), NODE_H + 6)
    if n.shape == 'circle':
        d = max(tw + 40, 74)
        return (d, d)
    if n.shape in ('start', 'end'):
        return (max(tw + 46, 88), NODE_H - 4)
    return (max(tw + PAD_X * 2, MIN_W), NODE_H)

def _compute_ranks(g):
    """分层：先用 DFS 去掉回环边，再做最长路径分层"""
    ids = list(g.nodes)
    # 1) DFS 标记回边
    WHITE, GREY, BLACK = 0, 1, 2
    color = {i: WHITE for i in ids}
    adj = _dd(list)
    for e in g.edges:
        if e.src in g.nodes and e.dst in g.nodes and e.src != e.dst:
            adj[e.src].append(e.dst)
    back = set()
    def dfs(u):
        color[u] = GREY
        for v in adj[u]:
            if color[v] == GREY:
                back.add((u, v))
            elif color[v] == WHITE:
                dfs(v)
        color[u] = BLACK
    for i in ids:
        if color[i] == WHITE:
            dfs(i)
    # 2) 用去掉回边后的图做入度
    indeg = {i: 0 for i in ids}
    out = _dd(list)
    for e in g.edges:
        if e.src not in g.nodes or e.dst not in g.nodes or e.src == e.dst:
            continue
        if (e.src, e.dst) in back:
            continue
        indeg[e.dst] += 1
        out[e.src].append(e.dst)
    rank = {i: 0 for i in ids}
    q = _dq([i for i in ids if indeg[i] == 0])
    seen = set()
    while q:
        u = q.popleft()
        seen.add(u)
        for v in out[u]:
            if rank[v] < rank[u] + 1:
                rank[v] = rank[u] + 1
            indeg[v] -= 1
            if indeg[v] == 0:
                q.append(v)
    # 3) 未被访问（仍在环里）的节点：按回边起点推一层
    for i in ids:
        if i not in seen:
            preds = [e.src for e in g.edges if e.dst == i and e.src in seen]
            rank[i] = (max(rank[p] for p in preds) + 1) if preds else 0
    for i, n in g.nodes.items():
        n.rank = rank.get(i, 0)
    # 不做形状推断：Mermaid 语义里 [x] 就是矩形，
    # 起始/结束要靠 ([x]) 显式声明

def _layout(g):
    _compute_ranks(g)
    ranks = _dd(list)
    for nid, n in g.nodes.items():
        ranks[n.rank].append(n)
    rk = sorted(ranks)
    lr = g.direction in ('LR', 'RL')
    # 尺寸
    for n in g.nodes.values():
        n.w, n.h = node_size(n)
    # 层内尺寸
    layer_thick = {}   # 层“厚度”（TD 时是高度，LR 时是宽度）
    layer_span = {}    # 层“跨度”
    for r in rk:
        lst = ranks[r]
        if lr:
            layer_thick[r] = max(n.w for n in lst)
            layer_span[r] = sum(n.h for n in lst) + SIB_GAP * (len(lst) - 1)
        else:
            layer_thick[r] = max(n.h for n in lst)
            layer_span[r] = sum(n.w for n in lst) + SIB_GAP * (len(lst) - 1)
    max_span = max(layer_span.values()) if layer_span else 0
    total_thick = sum(layer_thick[r] for r in rk) + RANK_GAP * max(0, len(rk) - 1)
    # 检测是否存在回环/上向边，需要右侧留白
    if lr:
        W = total_thick + MARGIN * 2
        H = max_span + MARGIN * 2
    else:
        W = max_span + MARGIN * 2 + 46
        H = total_thick + MARGIN * 2
    # 放置
    thick_pos = 0.0
    for r in rk:
        lst = ranks[r]
        span = layer_span[r]
        if lr:
            cx = MARGIN + thick_pos + layer_thick[r] / 2
            cur = MARGIN + (max_span - span) / 2
            for n in lst:
                n.x = cx - n.w / 2
                n.y = cur
                cur += n.h + SIB_GAP
        else:
            cy = MARGIN + thick_pos + layer_thick[r] / 2
            cur = MARGIN + (max_span - span) / 2
            for n in lst:
                n.x = cur
                n.y = cy - n.h / 2
                cur += n.w + SIB_GAP
        thick_pos += layer_thick[r] + RANK_GAP
    return W, H

def _center(n):
    return (n.x + n.w / 2, n.y + n.h / 2)

# ============================================================
# from mroute.py
# ============================================================
STEM = 22.0      # 分支处短竖段长度

class Route:
    __slots__ = ('head', 'tail', 'color', 'kind', 'label', 'lpos', 'lanchor')
    def __init__(self):
        self.head = []      # 无箭头段（可着色）
        self.tail = []      # 带箭头段
        self.color = '#9AA3AF'
        self.kind = 'arrow'
        self.label = ''
        self.lpos = (0.0, 0.0)
        self.lanchor = 'middle'

def label_color(lbl):
    if not lbl:
        return None
    if any(k in lbl for k in ('是', 'Yes', 'yes', '成立', '成功', 'ok', 'OK', '通过')):
        return '#3F9E6A'
    if any(k in lbl for k in ('否', 'No', 'no', '不成立', '失败', 'error', 'Error', '拒绝')):
        return '#C4663C'
    return '#5B7BB5'

def _routes(g):
    nodes = g.nodes
    lr = g.direction in ('LR', 'RL')
    out_edges = _dd(list)
    in_edges = _dd(list)
    for e in g.edges:
        if e.src == e.dst:
            continue
        out_edges[e.src].append(e)
        in_edges[e.dst].append(e)

    # 目标顶部入点分配（按来源 x 排序，避免交叉）
    entry = {}
    for dst, lst in in_edges.items():
        lst = [e for e in lst if e.src in nodes and nodes[e.src].rank < nodes[dst].rank]
        if not lst:
            continue
        lst.sort(key=lambda e: nodes[e.src].x + nodes[e.src].w / 2)
        n = len(lst)
        for i, e in enumerate(lst):
            entry[id(e)] = i - (n - 1) / 2.0

    routes = {}
    for src, lst in out_edges.items():
        a = nodes.get(src)
        if not a:
            continue
        if lr:
            sx, sy = a.x + a.w, a.y + a.h / 2
        else:
            sx, sy = a.x + a.w / 2, a.y + a.h
        downs = [e for e in lst if nodes.get(e.dst) and nodes[e.dst].rank > a.rank]
        same = [e for e in lst if nodes.get(e.dst) and nodes[e.dst].rank <= a.rank]

        spread = 0.0
        if len(downs) > 1:
            span = max(nodes[e.dst].x + nodes[e.dst].w / 2 for e in downs) - min(nodes[e.dst].x + nodes[e.dst].w / 2 for e in downs)
            spread = min(STEM + 22, max(STEM, span * 0.12))
        else:
            spread = STEM

        for e in downs:
            b = nodes[e.dst]
            r = Route()
            r.kind = e.kind
            r.label = e.label
            if lr:
                tx, ty = b.x, b.y + b.h / 2 + entry.get(id(e), 0) * 14
            else:
                tx, ty = b.x + b.w / 2, b.y
            lc = label_color(e.label)
            if lr:
                if abs(ty - sy) < 0.5:
                    r.tail = [(sx, sy), (tx, ty)]
                else:
                    mx = sx + spread
                    r.head = [(sx, sy), (mx, sy)]
                    r.tail = [(mx, sy), (mx, ty), (tx, ty)]
                    r.lpos = ((sx + mx) / 2, sy - 10)
            else:
                if abs(tx - sx) < 0.5:
                    r.tail = [(sx, sy), (tx, ty)]
                else:
                    # 漏斗汇合：先垂直下行 → 水平收向中轴 → 垂直进目标
                    my = ty - 18
                    if my <= sy:
                        my = sy + 16
                    r.head = [(sx, sy), (sx, my), (tx, my)]
                    r.tail = [(tx, my), (tx, ty)]
                    r.lpos = (tx + (7 if tx > sx else -7), my - 9)
                    r.lanchor = 'start' if tx > sx else 'end'
            if lc and r.head:
                r.color = lc
            routes[id(e)] = r

        for e in same:
            b = nodes.get(e.dst)
            if not b:
                continue
            r = Route()
            r.kind = e.kind
            r.label = e.label
            # 回环/上向边：从右侧外绕，不穿中轴
            if lr:
                py = min(a.y, b.y) - 28
                r.tail = [(a.x + a.w / 2, a.y), (a.x + a.w / 2, py),
                          (b.x + b.w / 2, py), (b.x + b.w / 2, b.y)]
            else:
                px = max(a.x + a.w, b.x + b.w) + 34
                r.tail = [(a.x + a.w / 2, a.y + a.h), (a.x + a.w / 2, a.y + a.h + 22),
                          (px, a.y + a.h + 22), (px, b.y + b.h / 2), (b.x + b.w, b.y + b.h / 2)]
            routes[id(e)] = r
    return routes

# ============================================================
# render
# ============================================================
STYLE = _STYLE
FONT = '"Noto Sans CJK SC","Source Han Sans SC",sans-serif'
EDGE_C = '#8A93A0'
EDGE_LBL = '#6B7280'

# 语义色：按出边标签推断
def edge_label_color(lbl):
    if not lbl:
        return EDGE_C
    if any(k in lbl for k in ('是', 'Yes', 'yes', 'Y', '成功', 'ok', 'OK')):
        return '#3F9E6A'
    if any(k in lbl for k in ('否', 'No', 'no', 'N', '失败', 'error', 'Error')):
        return '#C4663C'
    return '#5B7BB5'

def _esc(s):
    return _html.escape(s, quote=False)

def anchor_points(a, b, reverse=False):
    """根据渲染方向，取 a 出发、b 接收的锚点"""
    acx, acy = _center(a)
    bcx, bcy = _center(b)
    dx, dy = bcx - acx, bcy - acy
    if abs(dy) >= abs(dx):
        # 纵向为主
        if dy >= 0:
            return (acx, a.y + a.h), (bcx, b.y)
        return (acx, a.y), (bcx, b.y + b.h)
    else:
        if dx >= 0:
            return (a.x + a.w, acy), (b.x, bcy)
        return (a.x, acy), (b.x + b.w, bcy)

def path_ortho(p1, p2, direction='TD'):
    """正交路径，返回 points 列表"""
    x1, y1 = p1
    x2, y2 = p2
    if direction in ('LR', 'RL'):
        mx = (x1 + x2) / 2
        return [(x1, y1), (mx, y1), (mx, y2), (x2, y2)]
    my = (y1 + y2) / 2
    return [(x1, y1), (x1, my), (x2, my), (x2, y2)]

def shape_svg(n):
    fill, ln, tc = STYLE.get(n.shape, STYLE['rect'])
    x, y, w, h = n.x, n.y, n.w, n.h
    cx, cy = x + w / 2, y + h / 2
    out = []
    if n.shape == 'dia':
        out.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" stroke="%s" stroke-width="1.5"/>' % (
            cx, y, x + w, cy, cx, y + h, x, cy, fill, ln))
    elif n.shape == 'circle':
        r = min(w, h) / 2
        out.append('<circle cx="%.1f" cy="%.1f" r="%.1f" fill="%s" stroke="%s" stroke-width="1.5"/>' % (cx, cy, r, fill, ln))
    elif n.shape in ('start', 'end'):
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="%.1f" fill="%s" stroke="%s" stroke-width="1.5"/>' % (
            x, y, w, h, h / 2, fill, ln))
    elif n.shape == 'round':
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="12" fill="%s" stroke="%s" stroke-width="1.5"/>' % (x, y, w, h, fill, ln))
    elif n.shape == 'cyl':
        ry = 7.0
        out.append('<path d="M%.1f,%.1f a%.1f,%.1f 0 0,0 %.1f,0 a%.1f,%.1f 0 0,0 %.1f,0 v%.1f a%.1f,%.1f 0 0,1 %.1f,0 z" fill="%s" stroke="%s" stroke-width="1.5"/>' % (
            x, y + ry, w / 2, ry, w, w / 2, ry, -w, h - ry * 2, w / 2, ry, -w, fill, ln))
    elif n.shape == 'sub':
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="3" fill="%s" stroke="%s" stroke-width="1.5"/>' % (x, y, w, h, fill, ln))
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.2"/>' % (x + 8, y, x + 8, y + h, ln))
        out.append('<line x1="%.1f" y1="%.1f" x2="%.1f" y2="%.1f" stroke="%s" stroke-width="1.2"/>' % (x + w - 8, y, x + w - 8, y + h, ln))
    elif n.shape == 'asym':
        out.append('<polygon points="%.1f,%.1f %.1f,%.1f %.1f,%.1f %.1f,%.1f" fill="%s" stroke="%s" stroke-width="1.5"/>' % (
            x + 12, y, x + w, y, x + w, y + h, x + 12, y + h, fill, ln))
    else:
        out.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="7" fill="%s" stroke="%s" stroke-width="1.5"/>' % (x, y, w, h, fill, ln))
    # 文字（保持外框坐标系）
    out.append('<text x="%.1f" y="%.1f" font-size="15" fill="%s" text-anchor="middle" dominant-baseline="central">%s</text>' % (
        cx, cy, tc, _esc(n.label)))
    return '\n'.join(out)

def to_svg(g, out_path, title=None, subgraphs=None):
    """subgraphs: [(id, title, [node_ids])] —— 可选，画成带底板的框。"""
    W, H = _layout(g)
    if title:
        pass
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="%.0f" height="%.0f" viewBox="0 0 %.0f %.0f">' % (W, H, W, H),
             '<style>text{font-family:%s;}</style>' % FONT,
             '<rect x="0" y="0" width="%.0f" height="%.0f" fill="#FFFFFF"/>' % (W, H)]
    DEFS = ('<defs>'
            '<marker id="a-arrow" markerWidth="10" markerHeight="10" refX="8.5" refY="3.2" orient="auto"><path d="M0,0 L8.5,3.2 L0,6.4 z" fill="%s"/></marker>' % EDGE_C +
            '<marker id="a-thick" markerWidth="11" markerHeight="11" refX="9" refY="3.6" orient="auto"><path d="M0,0 L9,3.6 L0,7.2 z" fill="%s"/></marker>' % EDGE_C +
            '</defs>')
    parts.append(DEFS)
    # subgraph 底板：先画，压在边和节点下面
    if subgraphs:
        for _sid, _title, _nids in subgraphs:
            members = [g.nodes[x] for x in _nids if x in g.nodes]
            if not members:
                continue
            x0 = min(n.x for n in members) - 14
            y0 = min(n.y for n in members) - 30
            x1 = max(n.x + n.w for n in members) + 14
            y1 = max(n.y + n.h for n in members) + 12
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" rx="6" '
                         'fill="#F5F8FC" stroke="#C8D4E6" stroke-width="1.2" stroke-dasharray="6,3"/>' % (
                             x0, y0, x1 - x0, y1 - y0))
            parts.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="%s" font-weight="bold">%s</text>' % (
                x0 + 8, y0 + 15, '#5B6672', _esc(_title)))
    # 边先画（在节点下面）
    routes = _routes(g)
    for e in g.edges:
        r = routes.get(id(e))
        if not r:
            continue
        dash = ''
        width = 1.5
        marker = 'a-arrow'
        if e.kind == 'dotted':
            dash = ' stroke-dasharray="5,4"'
        elif e.kind == 'thick':
            width = 2.6
            marker = 'a-thick'
        elif e.kind == 'line':
            marker = ''
        # 无箭头段（可着色）
        if r.head and len(r.head) > 1:
            pl = ' '.join('%.1f,%.1f' % p for p in r.head)
            parts.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linejoin="round" stroke-linecap="round"%s/>' % (
                pl, r.color, width, dash))
        # 带箭头段
        if r.tail and len(r.tail) > 1:
            pl = ' '.join('%.1f,%.1f' % p for p in r.tail)
            mk = (' marker-end="url(#%s)"' % marker) if marker else ''
            parts.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="%.1f" stroke-linejoin="round" stroke-linecap="round"%s%s/>' % (
                pl, '#9AA3AF' if r.head else r.color, width, dash, mk))
        # 标签
        if e.label:
            lx, ly = r.lpos
            parts.append('<text x="%.1f" y="%.1f" font-size="11.5" fill="%s" text-anchor="%s" dominant-baseline="central">%s</text>' % (
                lx, ly, r.color, r.lanchor, _esc(e.label)))
    # 再画节点
    for nid in sorted(g.nodes, key=lambda k: (g.nodes[k].rank, g.nodes[k].x)):
        parts.append(shape_svg(g.nodes[nid]))
    parts.append('</svg>')
    open(out_path, 'w', encoding='utf-8').write('\n'.join(parts))
    return W, H
