#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""markdown -> typst（pandoc JSON AST + 组件 fenced div）"""
import subprocess, shutil, json, re, os, sys

PANDOC = shutil.which("pandoc") or "/usr/bin/pandoc"

PANDOC_FROM = ("markdown+pipe_tables+task_lists+fenced_divs+raw_html"
               "+footnotes+definition_lists+strikeout+superscript"
               "+subscript+mark+auto_identifiers")

_ESC = {"#": "\\#", "$": "\\$", "*": "\\*", "_": "\\_", "`": "\\`",
        "<": "\\<", ">": "\\>", "@": "\\@", "\\\\": "\\\\", "~": "\\~"}

DQ = chr(34)
SQ = chr(39)


class TypstError(Exception):
    pass


TASK_MARKS = ("\u2610", "\u2612", "\u2611")
WARNINGS = []
TYPST_MATH_FUNCS = set((
    # texmath 实际输出名（不是 LaTeX 原名）：\vec -> arrow，\bar -> overline
    "arrow", "hat", "tilde", "dot", "dia", "macron", "overline", "underline",
    "breve", "acute", "grave", "check", "cancel", "accent",

    "frac",
    "sqrt",
    "root",
    "sum",
    "prod",
    "int",
    "lim",
    "vec",
    "mat",
    "abs",
    "norm",
    "floor",
    "ceil",
    "round",
    "binom",
    "cases",
    "ln",
    "log",
    "exp",
    "sin",
    "cos",
    "tan",
    "sec",
    "csc",
    "cot",
    "sinh",
    "cosh",
    "tanh",
    "arcsin",
    "arccos",
    "arctan",
    "min",
    "max",
    "sup",
    "inf",
    "det",
    "dim",
    "gcd",
    "mod",
    "op",
    "cal",
    "bb",
    "frak",
    "mono",
    "bold",
    "italic",
    "upright",
    "text",
    "overline",
    "underline",
    "hat",
    "tilde",
    "dot",
    "dia",
    "acute",
    "grave",
    "breve",
    "check",
    "macron",
    "bar",
    "cancel",
    "annotate",
    "display",
    "inline",
    "script",
    "sscript",
    "limits",
    "scripts",
    "dif",
    "thin",
    "med",
    "and",
    "or",
    "not",
    "in",
    "equiv",
    "approx",
    "times",
    "angle",
    "prime",
    "partial",
    "infinity",
    "nothing",
    "emptyset",
    "oo",
))
KNOWN_CODE_LANGS = ("python", "py", "javascript", "js", "typescript", "ts",
                    "bash", "sh", "shell", "console", "json", "yaml", "yml",
                    "html", "css", "sql", "typst", "rust", "go", "java",
                    "c", "cpp", "c++", "diff", "markdown", "md", "toml",
                    "xml", "ini", "text", "txt")


def esc(t):
    return "".join(_ESC.get(c, c) for c in t)


def q(s):
    return DQ + s.replace("\\", "\\\\").replace(DQ, "\\" + DQ) + DQ


def num(s):
    m = re.search(r"-?\d+(?:\.\d+)?", str(s).replace(",", "").replace("\uff0c", ""))
    if not m:
        if str(s).strip():
            WARNINGS.append("数值字段写成了 %s，不是数字，已按 0 处理" % str(s).strip()[:30])
        return "0"
    return m.group(0)


# ============ fenced div 预处理器 ============
import re as _re

_RE_OPEN = _re.compile(r"^:::\s*([A-Za-z][\w-]*)(.*)$")
_RE_KV = _re.compile(r"([A-Za-z_][\w-]*)=\"([^\"]*)\"|([A-Za-z_][\w-]*)='([^']*)'|([A-Za-z_][\w-]*)=([^\s]+)")


def _quote_v(v):
    # 值若含中文/空格则用引号包住
    if _re.search(r"[^\x00-\x7f]", v) or " " in v:
        return DQ + v + DQ
    return v


def preprocess(md):
    # ============================================================
    # HTML 组件块保护。
    # PANDOC_FROM 带 fenced_divs，<div class="kpis"> 会被解析成 Div 块而不是
    # RawBlock，于是 _raw_html() 里的 kpis/badges/page-break 处理全成死代码，
    # 内容静默丢失。办法：交给 pandoc 前把这类块换成 ```{=html}，pandoc 会
    # 原样保留成 RawBlock，走回 _raw_html()。
    # ============================================================
    BT = chr(96) * 3
    _HKEYS = ("kpis", "badges", "page-break")
    def _html_guard(md_text):
        """把含已知 class 的 <div> 块整体包成 ```{=html} 围栏块。

        难点：<div class="kpis"> 里嵌着 <div class="kpi">，正则非贪婪会在第一个
        </div> 就收尾把块切碎。所以按顺序手动数 <div> / </div> 配对。
        """
        out = []
        i = 0
        pat = _re.compile(r"<div\b[^>]*class\s*=\s*['\"]([^'\"]*)['\"]", _re.I)
        while True:
            m = pat.search(md_text, i)
            if not m:
                out.append(md_text[i:])
                break
            cls = m.group(1).lower()
            if not any(k in cls for k in _HKEYS):
                out.append(md_text[i:m.end()])
                i = m.end()
                continue
            depth = 0
            end = -1
            for tm in _re.finditer(r"<div\b|</div\s*>", md_text[m.start():], _re.I):
                if tm.group(0).lower().startswith("</"):
                    depth -= 1
                    if depth == 0:
                        end = m.start() + tm.end()
                        break
                else:
                    depth += 1
            if end < 0:
                out.append(md_text[i:])
                break
            blk = md_text[m.start():end]
            out.append(md_text[i:m.start()])
            out.append(chr(10) + BT + "{=html}" + chr(10) + blk.rstrip() + chr(10) + BT + chr(10))
            i = end
        return "".join(out)

    md = _html_guard(md)

    # task list语法 -> Unicode方框（不依赖 pandoc扩展）
    md = md.replace("- [x]", "- " + chr(0x2612) + " ")
    md = md.replace("- [X]", "- " + chr(0x2612) + " ")
    md = md.replace("- [ ]", "- " + chr(0x2610) + " ")
    """把 ::: callout warn title=xx 这类简体写法转成 ::: {.callout .warn title=xx}"""
    # 先把 ```{=typst} ... ``` 原始块整体挖出来做占位，免得下面的标题正则
    # 把 "#import" 当成 Markdown 标题改成 "# import"，Typst 直接语法失败。
    _traw = []
    def _stash(mm):
        _traw.append(mm.group(2))
        return chr(0xE000) + str(len(_traw) - 1) + chr(0xE001)
    md = _re.sub(r"(?ms)^```\{=(typst|typ)\}[ \t]*\n(.*?)^```[ \t]*$",
                 _stash, md)
    md = _re.sub(r"(?m)^(#{1,6})([^\s#])", lambda mm: mm.group(1) + " " + mm.group(2), md)
    # 还原原始块（此时标题正则已经跑完）
    def _unstash(mm):
        i = int(mm.group(1))
        return "```{=typst}" + chr(10) + _traw[i] + "```"
    md = _re.sub(chr(0xE000) + r"(\d+)" + chr(0xE001), _unstash, md)
    lines = md.split("\n")
    out = []
    for ln in lines:
        m = _RE_OPEN.match(ln)
        if not m:
            out.append(ln)
            continue
        head = ln.rstrip()
        # 已经是标准写法 {: ...} 或 {.xxx}，跳过
        rest0 = head[3:].lstrip()
        if rest0.startswith("{") or rest0.startswith("}"):
            out.append(ln)
            continue
        name = m.group(1)
        args = (m.group(2) or "").strip()
        classes = [name]
        pairs = []
        if args:
            # 先抽 key=value
            leftover = args
            for km in _RE_KV.finditer(args):
                _k = km.group(1) or km.group(3) or km.group(5)
                _v = km.group(2) if km.group(2) is not None else (km.group(4) if km.group(4) is not None else km.group(6))
                pairs.append((_k, _v))
            leftover = _RE_KV.sub(" ", leftover).strip()
            # 剩下的裸词当作 class / 或 data-title
            words = leftover.split()
            if words:
                # 第一个裸词若是已知变体，作为 class
                KNOWN = {"note", "info", "success", "warn", "danger", "quote",
                         "primary", "soft", "neutral"}
                if words[0] in KNOWN:
                    classes.append(words[0])
                    words = words[1:]
                else:
                    for kk in ("danger", "success", "quote", "primary", "neutral", "info", "note", "warn", "soft"):
                        if words[0].startswith(kk) and len(words[0]) > len(kk):
                            classes.append(kk)
                            words = [words[0][len(kk):]] + words[1:]
                            break
                # 余下的裸词合并为标题
                if words:
                    pairs.append(("data-title", " ".join(words)))
        parts = [".%s" % c for c in classes]
        for k, v in pairs:
            parts.append("%s=%s" % (k, _quote_v(v)))
        out.append("::: {%s}" % " ".join(parts))
    res = "\n".join(out)
    # fenced div 内部：heading 前必须有空行，否则 pandoc 把它当续行文本
    _l2 = res.split("\n")
    _fin = []
    _inside = False
    for _ln in _l2:
        _st = _ln.strip()
        _is_fence = _st.startswith(":::")
        if (not _is_fence) and _inside and _re.match(r"^#{1,6}[ ]", _st):
            if _fin and _fin[-1].strip():
                _fin.append("")
        _fin.append(_ln)
        if _is_fence:
            _inside = not _inside
    if _inside:
        WARNINGS.append("fenced div 未闭合：文末还开着 :::。后面所有内容都会被当成同一块，格式会错。请在末尾补一行 :::")
    return "\n".join(_fin)


def _math(body):
    """LaTeX -> Typst 数学。转换不了的命令会退成纯文本，绝不让 LaTeX 原样进 Typst。"""
    raw = body
    try:
        import texmath
        r = texmath.convert(body)
    except Exception as e:
        WARNINGS.append("公式转换抛异常（已改为纯文本）：%s —— %s"
                        % (raw.strip()[:40], str(e)[:60]))
        return _math_fallback(raw)

    if not r:
        WARNINGS.append("公式转换结果为空（已改为纯文本）：%s" % raw.strip()[:40])
        return _math_fallback(raw)

    # texmath 遇到不认识的 LaTeX 命令是「去掉反斜杠、原样留着」：
    #   \badcommand{x}  ->  badcommand{x}
    # 这串东西进 Typst 数学环境必然 unknown variable。
    # 判据：「裸多字母标识符紧跟 ( 或 {」，且不在 Typst 数学函数白名单里。
    for m in _re.finditer(r"(?<![A-Za-z0-9_])([A-Za-z]{2,})\s*[({]", r):
        fn = m.group(1)
        if fn not in TYPST_MATH_FUNCS:
            WARNINGS.append(
                "公式里有不支持的 LaTeX 命令 %s，已整条改为纯文本（不再是数学排版）：%s"
                % (fn, raw.strip()[:40]))
            return _math_fallback(raw)
    return r


def _math_fallback(raw):
    """把无法转换的公式降级成普通文字，保证 PDF 能编出来。"""
    t = raw.strip()
    t = t.replace(chr(92), "")
    t = t.replace("{", "").replace("}", "").strip()
    if not t:
        return ""
    return '#text(size: 0.92em, style: "italic")[%s]' % esc(t[:120])

def md_to_ast(md):
    r = subprocess.run([PANDOC, "-f", PANDOC_FROM, "-t", "json"],
                       input=md, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise TypstError("pandoc: " + (r.stderr or "")[:400])
    return json.loads(r.stdout)


def classes_of(attr):
    try:
        return [c for c in attr[1] if isinstance(c, str)]
    except Exception:
        return []


def _trim(inlines):
    """裁掉内联列表首尾的空白 Str/Space。"""
    a = list(inlines)
    # 头部
    while a:
        n = a[0]
        t = n.get("t")
        if t in ("Space", "SoftBreak", "LineBreak"):
            a.pop(0)
            continue
        if t == "Str":
            s = n.get("c", "")
            st = s.lstrip()
            if not st:
                a.pop(0)
                continue
            if st != s:
                a[0] = {"t": "Str", "c": st}
        break
    # 尾部
    while a:
        n = a[-1]
        t = n.get("t")
        if t in ("Space", "SoftBreak", "LineBreak"):
            a.pop()
            continue
        if t == "Str":
            s = n.get("c", "")
            st = s.rstrip()
            if not st:
                a.pop()
                continue
            if st != s:
                a[-1] = {"t": "Str", "c": st}
        break
    return a


class R:
    def __init__(self):
        self.o = []

    def out(self):
        return "".join(self.o)

    def render(self, blocks):
        for b in blocks:
            self.blk(b)

    # ============ 块级 ============
    def blk(self, n):
        t = n.get("t")
        c = n.get("c")

        if t == "Para":
            self.o.append(self.ins(c) + "\n\n")
        elif t == "Plain":
            self.o.append(self.ins(c) + "\n")
        elif t == "Header":
            self.o.append("%s %s\n\n" % ("=" * c[0], self.ins(c[2])))
        elif t == "BulletList":
            self._list(c, "-")
        elif t == "OrderedList":
            self._list(c[1], "+")
        elif t == "BlockQuote":
            sub = R()
            sub.render(c)
            self.o.append("#blockquote[\n%s\n]\n\n" % sub.out().strip())
        elif t == "CodeBlock":
            cls = classes_of(c[0])
            lang = cls[0] if cls else ""
            if lang and lang.lower() not in KNOWN_CODE_LANGS and lang.lower() not in ("mermaid", "mmd"):
                WARNINGS.append("代码块语言 `%s` 无高亮规则，按纯文本渲染（不影响内容）" % lang)
            if lang.lower() in ("mermaid", "mmd"):
                self.o.append(self._mermaid(c[1]) + "\n\n")
            else:
                self.o.append(self._code(c[1], lang))
        elif t == "Table":
            self._table(c)
        elif t == "HorizontalRule":
            self.o.append("#hr()\n\n")
        elif t == "Div":
            self._div(c[0], c[1])
        elif t == "LineBlock":
            for line in c:
                self.o.append(self.ins(line) + "\\\\\n")
            self.o.append("\n")
        elif t == "Figure":
            attr, cap, inner = c[0], c[1], c[2]
            sub = R()
            sub.render(inner)
            captxt = ""
            try:
                if cap and cap[0]:
                    captxt = self.ins(cap[0])
            except Exception:
                pass
            body = sub.out().strip()
            if captxt:
                self.o.append("#figure(\n%s,\ncaption: [%s]\n)\n\n" % (body, captxt))
            else:
                self.o.append(body + "\n\n")
        elif t == "RawBlock":
            _fmt = c[0]
            if _fmt == "html":
                self.o.append(self._raw_html(c[1]))
            elif _fmt in ("typst", "typ"):
                self.o.append(c[1].rstrip() + chr(10) + chr(10))
            else:
                WARNINGS.append(
                    "原始块（```{=%s}）不被支持，内容已丢弃。只有 typst / html 能直通" % _fmt)

    def _code(self, code, lang):
        f = "```"
        while f in code:
            f += "`"
        return "%s%s\n%s\n%s\n\n" % (f, lang, code.rstrip("\n"), f)

    def _mermaid(self, code):
        """Mermaid 代码 -> SVG -> Typst #image；失败则回退成代码块"""
        try:
            import sys as _sys, os as _os2
            _d = _os2.path.dirname(_os2.path.abspath(__file__))
            if _d not in _sys.path:
                _sys.path.insert(0, _d)
            import mermaid as _mm
            import mermaid2 as _mm2
            import tempfile, os as _os

            kind = _mm2.detect_kind(code)
            fd, path = tempfile.mkstemp(suffix='.svg', prefix='mmd_')
            _os.close(fd)

            if kind == 'sequence':
                r = _mm2.render_sequence(code)
            elif kind == 'gantt':
                r = _mm2.render_gantt(code)
            elif kind == 'class':
                r = _mm2.render_class(code)
            else:
                r = None

            if r is not None:
                svg, w, h = r
                open(path, 'w', encoding='utf-8').write(svg)
            else:
                # flowchart（含 subgraph）走原渲染器
                _clean, _subs, _node_in_sub = _mm2.extract_subgraphs(code)
                g = _mm.parse(_clean)
                if not g.nodes:
                    _os.unlink(path)
                    WARNINGS.append(
                        "Mermaid 图里没有识别到节点；支持 flowchart/sequenceDiagram/gantt/classDiagram")
                    return self._code(code, "mermaid")
                w, h = _mm.to_svg(g, path, subgraphs=_subs or None)

            # 按版心宽度等比缩放（版心约 468pt）
            maxw = 468.0
            disp = min(maxw, w)
            return "#block(above: 8pt, below: 10pt, width: 100%%)[\n  #align(center)[#image(%s, width: %.1fpt)]\n]" % (q(path), disp)
        except Exception as e:
            WARNINGS.append("Mermaid 渲染失败（已回退成代码块）：%s" % str(e)[:80])
            return self._code(code, "mermaid")

    def _list(self, items, marker):
        """渲染列表。子列表递归收集到同一 rows，靠 depth 缩进表达层级。

        修了两处真 bug：
        1) 旧代码把子列表先渲染再按 "#block(" 前缀过滤，而 _list 输出每行都以
           "#block(" 开头 → 子列表 100% 被丢弃，内容静默消失。
        2) 嵌套告警判据 x.get("t") 里 x 是 list 不是 dict → AttributeError
           被 except 吞掉，告警永远不触发。
        """
        rows = self._collect_list(items, marker, 0)
        if not rows:
            return
        self.o.append(chr(10) + "#block(above: 7pt, below: 7pt)[" + chr(10))
        seq = {}
        for depth, txt, no_mark, mk in rows:
            seq[depth] = seq.get(depth, 0) + 1
            ind = 1.3 * depth
            if no_mark:
                self.o.append(
                    "  " + "#block(inset: (left: %.1fem, y: 2.8pt))[%s]" % (ind, txt) + chr(10))
            else:
                _mk = mk if mk else marker
                self.o.append(
                    "  " + "#block(inset: (left: %.1fem, y: 2.8pt))[%s %s]" % (ind, _mk, txt) + chr(10))
        self.o.append("]" + chr(10))

    def _collect_list(self, items, marker, depth, max_depth=4):
        """递归收集列表行：[(depth, 文本, 是否无标记, 自定义标记)]。"""
        out_rows = []
        seq = 0
        for it in items:
            seq += 1
            first = True
            for si in it:
                if not isinstance(si, dict):
                    continue
                t = si.get("t")
                c = si.get("c")
                if t in ("Plain", "Para"):
                    txt = self.ins(c)
                    if first:
                        no_mark = (txt[:1] in TASK_MARKS)
                        mk = "%d." % seq if marker == "+" else marker
                        out_rows.append((depth, txt, no_mark, mk))
                        first = False
                    else:
                        out_rows.append((depth, txt, True, ""))
                elif t in ("BulletList", "OrderedList"):
                    if depth >= max_depth:
                        WARNINGS.append(
                            "列表嵌套超过 %d 层，更深的层级缩进不区分（内容仍在）" % max_depth)
                        continue
                    sub_items = c if t == "BulletList" else c[1]
                    sub_marker = "-" if t == "BulletList" else "+"
                    out_rows.extend(
                        self._collect_list(sub_items, sub_marker, depth + 1, max_depth))
        return out_rows

    def _table(self, c):
        try:
            colspecs, head, bodies = c[2], c[3], c[4]
        except Exception:
            return
        ncol = len(colspecs) or 1

        def rows_of(container, is_body=False):
            res = []
            try:
                rows = container[3] if is_body else container[1]
                for r in rows:
                    rc = []
                    for cell in r[1]:
                        sub = R()
                        sub.render(cell[4])
                        rc.append(sub.out().strip())
                    res.append(rc)
            except Exception:
                pass
            return res

        header = rows_of(head)
        body = []
        for b in bodies:
            body += rows_of(b, is_body=True)

        # 行完整性校验：pandoc 会把缺的单元格补成空，所以长度总是等于 ncol。
        # 真正的信号是「中间出现空单元格」——几乎一定是源 Markdown 少写了 |
        for ri, r in enumerate(header + body):
            if ri == 0:
                continue
            blank = [i for i, cc in enumerate(r) if not cc.strip()]
            if blank and len(blank) < ncol:
                WARNINGS.append(
                    "表格第 %d 行有 %d 个空单元格（位置 %s），源 Markdown 很可能少写了 | ，这一行会错位"
                    % (ri + 1, len(blank), ",".join(str(i + 1) for i in blank)))
        aligns = self._aligns(colspecs, ncol)
        lines = ["#table(", "  columns: (%s)," % ", ".join(["1fr"] * ncol)]
        if aligns:
            lines.append("  align: (%s)," % ", ".join(aligns))
        cells = []
        for r in header + body:
            for cc in r:
                cells.append("[%s]" % cc)
        if cells:
            lines.append("  " + ", ".join(cells) + ",")
        lines.append(")")
        self.o.append("\n".join(lines) + "\n\n")

    def _aligns(self, colspecs, ncol):
        M = {"AlignLeft": "left", "AlignRight": "right",
             "AlignCenter": "center", "AlignDefault": "left"}
        per = []
        for cs in colspecs:
            v = "left"
            try:
                if isinstance(cs, list) and cs and isinstance(cs[0], dict):
                    v = M.get(cs[0].get("t"), "left")
                elif isinstance(cs, dict):
                    v = M.get(cs.get("t"), "left")
            except Exception:
                pass
            per.append(v)
        while len(per) < ncol:
            per.append("left")
        per = per[:ncol]
        return None if all(x == "left" for x in per) else per

    # ============ 组件 ============
    def _slide(self, name, cls, kvs, inner):
        """幻灯片版式。数据行用 | 分隔字段。"""
        rows = []
        for k, payload, _lv in self._lines(inner or []):
            if k != "line":
                continue
            txt = self._text(payload).strip()
            if txt:
                rows.append(txt)
        if name.startswith("slide-"):
            kind = name[6:]
        else:
            kind = kvs.get("layout") or ""
        kind = kind.strip().lower()

        def _rgb_or_accent(c):
            c = str(c).strip().lstrip("#")
            if len(c) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in c):
                return 'rgb("#' + c + '")'
            WARNINGS.append("slide-stats 颜色 %s 不是 6 位十六进制，已用主题色" % c)
            return "accent"

        def cell(row, i, default=""):
            parts = [p.strip() for p in row.split("|")]
            return parts[i] if i < len(parts) and parts[i] else default

        # ---- 封面 ----
        if kind == "cover":
            title = cell(rows[0], 0) if rows else ""
            sub = cell(rows[0], 1) if rows else ""
            kick = cell(rows[0], 2) if rows else ""
            meta = cell(rows[0], 3) if rows else ""
            opts = []
            if sub:
                opts.append("subtitle: [%s]" % esc(sub))
            if kick:
                opts.append("kicker: [%s]" % esc(kick))
            if meta:
                opts.append("meta: [%s]" % esc(meta))
            tail = (", " + ", ".join(opts)) if opts else ""
            return "#slide-cover([%s]%s)" % (esc(title), tail)

        # ---- 章节页 ----
        if kind == "section":
            num = cell(rows[0], 0) if rows else "01"
            ttl = cell(rows[0], 1) if rows else ""
            note = cell(rows[0], 2) if rows else ""
            if note:
                return "#slide-section([%s], [%s], note: [%s])" % (esc(num), esc(ttl), esc(note))
            return "#slide-section([%s], [%s])" % (esc(num), esc(ttl))

        # ---- 引言页 ----
        if kind == "quote":
            qb = cell(rows[0], 0) if rows else ""
            who = cell(rows[0], 1) if rows else ""
            if who:
                return "#slide-quote([%s], who: [%s])" % (esc(qb), esc(who))
            return "#slide-quote([%s])" % esc(qb)

        # ---- 多栏卡片 ----
        if kind in ("cols", "col", "cards"):
            raw = kvs.get("cols") or kvs.get("data-cols") or ""
            n = int(raw) if str(raw).isdigit() else 3
            if n < 1 or n > 6:
                WARNINGS.append("slide-cols 列数 %s 越界（1-6），已用 3" % n)
                n = 3
            items = []
            for r in rows:
                items.append("(%s, [%s])" % (q(cell(r, 0)), esc(cell(r, 1))))
            if not items:
                WARNINGS.append("slide-cols 没有数据行，会是空页")
            return "#slide-cols((%s), cols: %d)" % (", ".join(items), n)

        # ---- 大数字 ----
        if kind in ("stats", "stat", "numbers"):
            raw = kvs.get("cols") or kvs.get("data-cols") or ""
            n = int(raw) if str(raw).isdigit() else 2
            items = []
            for r in rows:
                vv = cell(r, 0)
                ll = cell(r, 1)
                cc = cell(r, 2)
                if cc:
                    col = _rgb_or_accent(cc)
                else:
                    col = "accent"
                items.append("([%s], [%s], %s)" % (esc(vv), esc(ll), col))
            if not items:
                WARNINGS.append("slide-stats 没有数据行，会是空页")
            return "#slide-stats((%s), cols: %d)" % (", ".join(items), n)

        # ---- 对比 ----
        if kind in ("compare", "vs"):
            # 两种写法都支持：
            #   单行 4 列： 左标题|左正文|右标题|右正文
            #   两行 2 列： 左标题|左正文  /  右标题|右正文
            if not rows:
                WARNINGS.append("slide-compare 没有数据行，会是空页")
                rows = ["|||"]
            if len(rows) == 1 and len([p for p in rows[0].split("|")]) >= 4:
                lh = cell(rows[0], 0)
                lb = cell(rows[0], 1)
                rh = cell(rows[0], 2)
                rb = cell(rows[0], 3)
            else:
                if len(rows) < 2:
                    WARNINGS.append("slide-compare 需要 2 行（左|右）或 1 行 4 列，当前 %d 行" % len(rows))
                    rows = rows + [""] * (2 - len(rows))
                lh = cell(rows[0], 0)
                lb = cell(rows[0], 1)
                rh = cell(rows[1], 0)
                rb = cell(rows[1], 1)
            return "#slide-compare([%s], [%s], [%s], [%s])" % (esc(lh), esc(lb), esc(rh), esc(rb))

        # ---- 流程 / 时间线 ----
        if kind in ("flow", "timeline", "steps"):
            items = []
            for r in rows:
                items.append("([%s], [%s])" % (esc(cell(r, 0)), esc(cell(r, 1))))
            if not items:
                WARNINGS.append("slide-flow 没有数据行，会是空页")
            raw = kvs.get("numbered") or kvs.get("data-numbered")
            if raw is not None and str(raw).lower() in ("false", "0", "no"):
                nb = "false"
            else:
                nb = "true"
            return "#slide-flow((%s), numbered: %s)" % (", ".join(items), nb)

        # ---- 左图右文 ----
        if kind in ("split", "image"):
            side = kvs.get("side") or kvs.get("data-side") or "right"
            # 用 --- 分隔两栏；没有 --- 时按前两块分组
            groups = []
            cur = []
            for b in (inner or []):
                if b.get("t") == "HorizontalRule":
                    groups.append(cur)
                    cur = []
                else:
                    cur.append(b)
            groups.append(cur)
            if len(groups) < 2:
                WARNINGS.append("slide-split 需要两栏内容，用一行 --- 分隔；当前只有 1 栏")
                groups = [cur, []]
            parts = []
            for g in groups[:2]:
                r = R()
                r.render(g)
                parts.append(r.out().strip())
            return "#slide-split(([%s], [%s]), side: %s)" % (
                parts[0], parts[1], q(side))

        WARNINGS.append("未知幻灯片版式 ::: %s。可用：cover / section / quote / cols / stats / compare / flow / split" % name)
        sub = R()
        sub.render(inner)
        return sub.out().strip()

    def _div(self, attr, inner):
        cls = classes_of(attr)
        kvs = {}
        try:
            for k, v in attr[2]:
                kvs[k] = v
        except Exception:
            pass
        name = cls[0] if cls else ""

        # 空组件：有 ::: xxx 但没有内容，几乎肯定是忘写数据行
        _EMPTY_OK = ("pagebreak", "toc", "no-break", "nobreak")
        if name and name not in _EMPTY_OK and not any(
                k == "line" for k, _p, _l in self._lines(inner or [])):
            WARNINGS.append("组件 ::: %s 里没有任何数据行，渲染出来会是空块" % name)

        # block font: ::: font-Cinzel ... :::
        if name.startswith("font-") or name.startswith("f-"):
            _fam = name.split("-", 1)[1].replace("_", " ")
            _subd = R()
            _subd.render(inner)
            self.o.append(chr(10) + "#[" + chr(10) + "#set text(font: %s)" % q(_fam) + chr(10) + _subd.out().strip() + chr(10) + "]" + chr(10) + chr(10))
        elif name == "kpi":

            self.o.append(self._pairs(inner, "kpirow") + "\n\n")
        elif name == "badges":
            self.o.append(self._badges(inner) + "\n\n")
        elif name == "callout":
            kind = cls[1] if len(cls) > 1 else "note"
            title = kvs.get("title") or kvs.get("data-title") or ""
            sub = R()
            sub.render(inner)
            ttl = "title: [%s], " % esc(title) if title else ""
            self.o.append("#callout(kind: %s, %s)[\n%s\n]\n\n"
                          % (q(kind), ttl, sub.out().strip()))
        elif name.startswith("cards"):
            self.o.append(self._cards(inner, cls, kvs, name[5:]) + "\n\n")
        elif name == "compare":
            self.o.append(self._compare(inner))
        elif name in ("progress", "rating"):
            self.o.append(self._numbered(inner, name) + "\n\n")
        elif name in ("wrapimg", "wrapimage", "wrapimg2"):
            self.o.append(self._wrapimg(inner, cls, kvs) + "\n\n")
        elif name in ("wrap", "circlewrap"):
            self.o.append(self._wrap(inner, cls, kvs) + "\n\n")
        elif name in ("vertical", "tate") or (
                name.startswith("vertical") and name[8:].isdigit()):
            _n = name[8:] if name.startswith("vertical") and name[8:].isdigit() else ""
            self.o.append(self._vertical(inner, cls, kvs, n=_n) + "\n\n")
        elif name == "ring":
            self.o.append(self._rings(inner) + "\n\n")
        elif name == "chart":
            self.o.append(self._chart(inner) + "\n\n")
        elif name == "timeline":
            self.o.append(self._timeline(inner) + "\n\n")
        elif name == "steps":
            self.o.append(self._steps(inner) + "\n\n")
        elif name == "defs":
            self.o.append(self._defs(inner) + "\n\n")
        elif name == "pagebreak":
            self.o.append("#pagebreak()\n\n")
        elif name == "toc":
            self.o.append("#sectiontoc()\n\n")
        elif name.startswith("slide-") or name == "slide":
            self.o.append(self._slide(name, cls, kvs, inner) + chr(10) * 2)
        elif name == "font":
            fam = kvs.get("name") or kvs.get("data-name") or kvs.get("font") or ""
            if not fam and len(cls) > 1:
                fam = cls[1]
            sz = kvs.get("size") or kvs.get("data-size") or ""
            wt = kvs.get("weight") or kvs.get("data-weight") or ""
            sub = R()
            sub.render(inner)
            opts = []
            if fam:
                opts.append("font: %s" % q(fam))
            if sz:
                opts.append("size: %s" % sz)
            if wt:
                opts.append("weight: %s" % (wt if str(wt).isdigit() else q(wt)))
            if opts:
                self.o.append("#text(%s)[\n%s\n]\n\n" % (", ".join(opts), sub.out().strip()))
            else:
                self.o.append(sub.out().strip() + "\n\n")
        elif name == "fontspec":
            self.o.append(self._fontspec(inner, cls, kvs) + "\n\n")
        elif name in ("no-break", "nobreak"):
            sub = R()
            sub.render(inner)
            self.o.append("#block(breakable: false)[\n%s\n]\n\n" % sub.out().strip())
        else:
            # 未知组件名：记警告 + 明确标注，不再静默丢格式
            WARNINGS.append("未知组件 ::: %s —— 已按普通段落渲染，格式丢失。可用组件见 list_pdf_themes" % name)
            sub = R()
            sub.render(inner)
            self.o.append("#block(above: 6pt, below: 6pt)[\n%s\n]\n\n" % sub.out().strip())

    # ---- 行提取：统一三元组 (kind, inlines, level) ----
    def _lines(self, blocks):
        res = []
        for b in blocks:
            t = b.get("t")
            c = b.get("c")
            if t in ("Para", "Plain"):
                cur = []
                for n in c:
                    if n.get("t") in ("SoftBreak", "LineBreak"):
                        if cur:
                            res.append(("line", cur, 0))
                        cur = []
                    else:
                        cur.append(n)
                if cur:
                    res.append(("line", cur, 0))
            elif t in ("BulletList", "OrderedList"):
                items = c if t == "BulletList" else c[1]
                for it in items:
                    res.extend(self._lines(it))
            elif t == "Header":
                res.append(("head", c[2], c[0]))
            elif t == "HorizontalRule":
                res.append(("hr", [], 0))
        return res

    def _split_pipe(self, inlines):
        parts = []
        cur = []
        for n in inlines:
            if n.get("t") == "Str" and "|" in n.get("c", ""):
                pieces = n["c"].split("|")
                for i, p in enumerate(pieces):
                    if p:
                        cur.append({"t": "Str", "c": p})
                    if i < len(pieces) - 1:
                        parts.append(cur)
                        cur = []
            else:
                cur.append(n)
        parts.append(cur)
        return [_trim(x) for x in parts]

    def _text(self, inlines):
        out = []
        for n in inlines:
            t = n.get("t")
            c = n.get("c")
            if t == "Str":
                out.append(c)
            elif t in ("Space", "SoftBreak", "LineBreak"):
                out.append(" ")
            elif t == "Code":
                out.append(c[1])
            elif t in ("Emph", "Strong", "Strikeout", "Superscript",
                       "Subscript", "SmallCaps", "Underline"):
                out.append(self._text(c))
            elif t == "Span":
                out.append(self._text(c[1]))
        return "".join(out).strip()

    def _pairs(self, blocks, wrapper):
        items = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            left = self.ins(parts[0]) if parts else ""
            right = self.ins(parts[1]) if len(parts) > 1 else ""
            items.append("([%s], [%s])" % (left, right))
        if not items:
            return ""
        return "#%s((\n  %s,\n))" % (wrapper, ",\n  ".join(items))

    def _badges(self, blocks):
        items = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            label = self.ins(parts[0]) if parts else ""
            k = self._text(parts[1]) if len(parts) > 1 else "soft"
            if not k:
                k = "soft"
            items.append("([%s], %s)" % (label, q(k)))
        if not items:
            return ""
        return "#badgerow((\n  %s,\n))" % ",\n  ".join(items)

    def _numbered(self, blocks, fn):
        items = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            label = self.ins(parts[0]) if parts else ""
            raw = self._text(parts[1]) if len(parts) > 1 else "0"
            items.append("#%s([%s], %s)" % (fn, label, num(raw)))
        return "\n".join(items)

    def _rings(self, blocks, per_row=3):
        items = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            label = self.ins(parts[0]) if parts else ""
            raw = self._text(parts[1]) if len(parts) > 1 else "0"
            items.append("ring(%s, label: [%s])" % (num(raw), label))
        if not items:
            return ""
        n = 3 if len(items) >= 3 else len(items)
        cols = ", ".join(["1fr"] * n)
        body = (",%s  " % chr(10)).join(items)
        return ("#grid(columns: (%s), gutter: 12pt, align: center,%s  %s,%s)%s"
                % (cols, chr(10), body, chr(10), chr(10)))
    def _chart(self, blocks):
        items = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            label = self.ins(parts[0]) if parts else ""
            raw = self._text(parts[1]) if len(parts) > 1 else "0"
            items.append("([%s], %s)" % (label, num(raw)))
        if not items:
            return ""
        return "#barchart((\n  %s,\n))" % ",\n  ".join(items)

    def _timeline(self, blocks):
        items = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            left = self.ins(parts[0]) if parts else ""
            right = self.ins(parts[1]) if len(parts) > 1 else ""
            items.append("([%s], [%s])" % (left, right))
        if not items:
            return ""
        return "#timeline((\n  %s,\n))" % ",\n  ".join(items)

    def _steps(self, blocks):
        items = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            items.append("[%s]" % self.ins(payload))
        if not items:
            return ""
        return "#steps((\n  %s,\n))" % ",\n  ".join(items)

    def _fontspec(self, blocks, cls, kvs):
        rows = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            if not parts:
                continue
            fam = self._text(parts[0]) if parts else ""
            note = self._text(parts[1]) if len(parts) > 1 else ""
            if not fam:
                continue
            rows.append((fam, note))
        if not rows:
            return ""
        cells = []
        for fam, note in rows:
            cells.append(
                "table.cell[#block(above: 4pt, below: 4pt)["
                "#text(font: %s, size: 18pt)[%s]#linebreak()"
                "#text(font: %s, size: 7pt, fill: luma(120))[%s]"
                "#text(font: %s, size: 6.5pt, fill: luma(165))[  %s]]]"
                % (q(fam), esc("AaBbCc 0123 中文"), q("Noto Sans CJK SC"), esc(fam),
                   q("Noto Sans CJK SC"), esc(note)))
        out = ["#table(columns: (1fr, 1fr), stroke: none, fill: none, inset: 0pt, gutter: 8pt,"]
        out.append(("," + chr(10)).join(cells) + ",")
        out.append(")")
        return chr(10).join(out)

    def _defs(self, blocks):
        items = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            term = self.ins(parts[0]) if parts else ""
            if len(parts) <= 1:
                WARNINGS.append(
                    "defs 这一行没有竖线，定义栏是空的：%s（要写成 术语|定义）"
                    % (term.replace(chr(10), " ")[:30] or "(空行)"))
                desc = ""
            else:
                desc = self.ins(parts[1])
            items.append("([%s], [%s])" % (term, desc))
        if not items:
            return ""
        return "#deflist((\n  %s,\n))" % ",\n  ".join(items)

    def _grouped(self, blocks):
        """按 Header 切组：[(title, [body...])]"""
        groups = []
        cur_title = None
        cur_body = []
        started = False
        for kind, payload, lv in self._lines(blocks):
            if kind == "head":
                if started:
                    groups.append((cur_title, cur_body))
                cur_title = self.ins(payload)
                cur_body = []
                started = True
            elif kind == "line":
                if not started:
                    cur_title = ""
                    started = True
                cur_body.append(self.ins(payload))
        if started:
            groups.append((cur_title, cur_body))
        return groups

    def _cards(self, blocks, cls, kvs=None, cols=None):
        kvs = kvs or {}
        if not cols or not str(cols).isdigit():
            cols = str(kvs.get("cols") or "2")
        cols = str(cols)
        if not cols.isdigit() or not (1 <= int(cols) <= 6):
            WARNINGS.append("卡片列数写了 %s，只支持 1-6，已按 2 列处理" % cols)
            cols = "2"
        items = []
        for title, body in self._grouped(blocks):
            b = " ".join(x for x in body if x)
            items.append("([%s], [%s])" % (title or "", b))
        if not items:
            return ""
        return "#cardgrid((\n  %s,\n), cols: %s)" % (",\n  ".join(items), cols)

    def _wrap(self, blocks, cls, kvs=None):
        """文字环绕。首行写障碍框：位置|宽|高，其余行为正文。"""
        kvs = kvs or {}
        lines = []
        obs = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            txt = self.ins(payload)
            if not obs and not lines and "|" in self._text(payload):
                parts = self._split_pipe(payload)
                if len(parts) >= 3:
                    pos = self._text(parts[0]).strip().lower() or "left-top"
                    w = self._text(parts[1]).strip() or "42mm"
                    h = self._text(parts[2]).strip() or "34mm"
                    if pos not in ("left-top", "right-top", "left-bottom", "right-bottom"):
                        WARNINGS.append(
                            "wrap 的位置写了 %s，只支持 left-top/right-top/left-bottom/right-bottom，已按 left-top" % pos)
                        pos = "left-top"
                    for _who, _v in (("宽", w), ("高", h)):
                        if not (_v.endswith("mm") or _v.endswith("cm") or _v.endswith("pt") or _v.endswith("in")):
                            WARNINGS.append("wrap 的%s度写了 %s，缺少单位（mm/cm/pt），已按 mm 处理" % (_who, _v))
                            if _who == "宽":
                                w = _v + "mm"
                            else:
                                h = _v + "mm"
                    obs.append((pos, w, h))
                    continue
            lines.append(txt)
        if not obs:
            WARNINGS.append("wrap 里没有写障碍框，首行要写「位置|宽|高」，例如 left-top|42mm|34mm")
            return "\n".join(lines)
        body = " ".join(x for x in lines if x)
        if not body:
            WARNINGS.append("wrap 里没有正文，只有障碍框")
            return ""
        ob = ", ".join("(%s, %s, %s)" % (q(p), w, h) for p, w, h in obs)
        return "#wrap([%s], obstacles: (%s,))" % (body, ob)

    def _wrapimg(self, blocks, cls, kvs=None):
        """文字环绕图片。首行写 位置|宽|高|图片路径，其余行为正文。"""
        kvs = kvs or {}
        lines = []
        pos, w, h, src = "left-top", "42mm", "34mm", ""
        got_head = False
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            if not got_head:
                parts = self._split_pipe(payload)
                if len(parts) >= 4:
                    pos = self._text(parts[0]).strip().lower() or "left-top"
                    w = self._text(parts[1]).strip() or "42mm"
                    h = self._text(parts[2]).strip() or "34mm"
                    src = self._text(parts[3]).strip()
                    got_head = True
                    if pos not in ("left-top", "right-top", "left-bottom", "right-bottom"):
                        WARNINGS.append(
                            "wrapimg 的位置写了 %s，只支持 left-top/right-top/left-bottom/right-bottom，已按 left-top" % pos)
                        pos = "left-top"
                    for _who, _v in (("宽", w), ("高", h)):
                        if not (_v.endswith("mm") or _v.endswith("cm") or _v.endswith("pt") or _v.endswith("in")):
                            WARNINGS.append("wrapimg 的%s度写了 %s，缺少单位（mm/cm/pt），已按 mm 处理" % (_who, _v))
                            if _who == "宽":
                                w = _v + "mm"
                            else:
                                h = _v + "mm"
                    if not src:
                        WARNINGS.append("wrapimg 没写图片路径，会渲染成灰色占位块")
                    elif not os.path.exists(src):
                        WARNINGS.append(
                            "wrapimg 的图片不存在：%s（会渲染成灰色占位块，检查路径）" % src)
                        src = ""
                    continue
            lines.append(self.ins(payload))
        if not got_head:
            WARNINGS.append(
                "wrapimg 首行要写「位置|宽|高|图片路径」，例如 left-top|46mm|36mm|/sdcard/Download/a.jpg")
            return "\n".join(lines)
        body = " ".join(x for x in lines if x)
        if not body:
            WARNINGS.append("wrapimg 里没有正文，只有图片")
            return ""
        opts = "pos: %s, w: %s, h: %s" % (q(pos), w, h)
        if src:
            opts += ", src: %s" % q(src)
        return "#wrapimg([%s], %s)" % (body, opts)

    def _vertical(self, blocks, cls, kvs=None, n=""):
        """竖排。列数优先级：::: vertical3 的数字 > cols=N > cls 第二段 > 1。"""
        kvs = kvs or {}
        cols = "1"
        if n:
            cols = str(n)
        elif len(cls) > 1 and str(cls[1]).isdigit():
            cols = str(cls[1])
        elif kvs.get("cols"):
            cols = str(kvs.get("cols"))
        if not cols.isdigit() or not (1 <= int(cols) <= 8):
            WARNINGS.append("vertical 的列数写了 %s，只支持 1-8，已按 1 列处理" % cols)
            cols = "1"
        sz = kvs.get("size") or "10pt"
        gap = kvs.get("gap") or "3pt"
        body = []
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            body.append(self.ins(payload))
        if not body:
            WARNINGS.append("vertical 里没有内容")
            return ""
        return "#vertical([%s], cols: %s, size: %s, gap: %s)" % (" ".join(x for x in body if x), cols, sz, gap)

    def _compare(self, blocks):
        groups = self._grouped(blocks)
        if len(groups) < 2:
            WARNINGS.append(
                "对比栏只有 %d 组，需要 2 组（每组以 ### 标题开头），空的一侧会留白" % len(groups))
        while len(groups) < 2:
            groups.append(("", []))
        lt, lb = groups[0]
        rt, rb = groups[1]
        return ("#compare(\n  [%s], [%s],\n  [%s], [%s],\n)\n\n"
                % (lt or "", " ".join(x for x in lb if x),
                   rt or "", " ".join(x for x in rb if x)))

    def _raw_html(self, txt):
        h = txt.strip()
        low = h.lower()
        if "class=" in low and "kpis" in low:
            cards = re.findall(
                r"<div class=.kpi.>\s*<div class=.n.>(.*?)</div>\s*"
                r"<div class=.l.>(.*?)</div>\s*</div>", h, re.S)
            if cards:
                # kpi(value, label) 的 value 走 text()[#value]，传内容块会被
                # 当成整型（[88] -> 88），必须给字符串。label 保持内容块。
                items = ", ".join('(%s, [%s])' % (
                    q(_strip(a).strip()), esc(_strip(b).strip()))
                    for a, b in cards)
                return "#kpirow((%s,))\n\n" % items
        if "class=" in low and "badges" in low:
            its = re.findall(r"<span class=.badge([^\"']*).>(.*?)</span>", h, re.S)
            if its:
                items = ", ".join("([%s], %s)" % (
                    esc(_strip(t).strip()),
                    q("primary" if "solid" in cl else "soft"))
                    for cl, t in its)
                return "#badgerow((%s))\n\n" % items
        if "page-break" in low:
            return "#pagebreak()\n\n"
        if "<br" in low:
            return "\\\\\n"
        plain = _strip(h).strip()
        return (esc(plain) + "\n\n") if plain else ""

    # ============ 内联 ============
    def ins(self, nodes):
        return "".join(self.ino(n) for n in nodes)

    def ino(self, n):
        t = n.get("t")
        c = n.get("c")

        if t == "Str":
            return esc(c)
        if t == "Space":
            return " "
        if t == "SoftBreak":
            return " "
        if t == "LineBreak":
            return "\\\\\n"
        if t == "Emph":
            return "#emph[%s]" % self.ins(c)
        if t == "Strong":
            return "#strong[%s]" % self.ins(c)
        if t == "Strikeout":
            return "#strike[%s]" % self.ins(c)
        if t == "Superscript":
            return "#super[%s]" % self.ins(c)
        if t == "Subscript":
            return "#sub[%s]" % self.ins(c)
        if t == "SmallCaps":
            return "#smallcaps[%s]" % self.ins(c)
        if t == "Underline":
            return "#underline[%s]" % self.ins(c)
        if t == "Code":
            return "`%s`" % c[1]
        if t == "Math":
            kind = c[0].get("t")
            body = _math(c[1])
            if kind == "DisplayMath":
                return "\n$ %s $\n\n" % body
            return " $%s$ " % body
        if t == "Link":
            alt, target = c[1], c[2]
            url = target[0] if target else ""
            a = self.ins(alt)
            return "#link(%s)[%s]" % (q(url), a) if url else a
        if t == "Image":
            target = c[2]
            url = target[0] if target else ""
            if not url:
                return ""
            # 路径预检：Typst 遇到不存在的图片会让整份 PDF 编译失败，
            # 所以在转换期就判掉，降级成一行占位文字。
            if not (url.startswith("http://") or url.startswith("https://")):
                if not os.path.exists(url):
                    WARNINGS.append(
                        "图片不存在，已用占位文字代替（不写路径会导致整份 PDF 编译失败）：%s"
                        % url[:100])
                    return '#block(above: 6pt, below: 6pt, inset: 8pt, stroke: 0.8pt + luma(200), width: 100%%)[#text(size: 0.85em, fill: luma(120))[图片缺失：%s]]\n' % esc(url.split("/")[-1][:60])
            return "#image(%s, width: 100%%)\n" % q(url)
        if t == "Note":
            sub = R()
            sub.render(c)
            return "#footnote[%s]" % sub.out().strip()
        if t == "Quoted":
            kind = c[0].get("t")
            body = self.ins(c[1])
            L, Rr = chr(8216), chr(8217)
            LD, RD = chr(8220), chr(8221)
            return (L + body + Rr) if kind == "SingleQuote" else (LD + body + RD)
        if t == "Cite":
            return self.ins(c[1])
        if t == "Span":
            attr, inner = c[0], c[1]
            cls = classes_of(attr)
            kvs = {}
            try:
                for _k, _v in attr[2]:
                    kvs[_k] = _v
            except Exception:
                pass
            body = self.ins(inner)
            _fam = kvs.get("font") or kvs.get("data-font")
            _wt = kvs.get("weight") or kvs.get("data-weight")
            _sz = kvs.get("size") or kvs.get("data-size")
            _fill = kvs.get("color") or kvs.get("data-color")
            for _cl in cls:
                if _cl.startswith("f-") and not _fam:
                    _fam = _cl[2:].replace("-", " ")
            if _fam or _wt or _sz or _fill:
                _opts = []
                if _fam:
                    _opts.append("font: %s" % q(_fam))
                if _wt:
                    _w = str(_wt)
                    _opts.append("weight: %s" % (_w if _w.isdigit() else q(_w)))
                if _sz:
                    _opts.append("size: %s" % _sz)
                if _fill:
                    _opts.append("fill: rgb(%s)" % q(_fill))
                body = "#text(%s)[%s]" % (", ".join(_opts), body)
            # inline font: [text]{.font-Cinzel} / {.f-Source_Han_Serif_SC}
            for _c in cls:
                if _c.startswith("font-") or _c.startswith("f-"):
                    _fam = _c.split("-", 1)[1].replace("_", " ")
                    return "#text(font: %s)[%s]" % (q(_fam), body)
            if "badge" in cls:
                kind = "soft"
                for k in ("primary", "success", "warn", "danger", "neutral", "soft"):
                    if k in cls:
                        kind = k
                return "#badge([%s], kind: %s)" % (body, q(kind))
            if "mark" in cls or "highlight" in cls:
                return "#mark[%s]" % body
            return body
        if t == "RawInline":
            fmt, txt = c[0], c[1]
            if fmt == "html":
                h = txt.strip().lower()
                if h in ("<br>", "<br/>", "<br />"):
                    return "\\\\\n"
                return ""
            return "`%s`" % txt
        return ""


def _strip(html):
    s = re.sub(r"<br\s*/?>", "\n", html)
    s = re.sub(r"<[^>]+>", "", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&")
    s = s.replace("&lt;", "<").replace("&gt;", ">")
    s = s.replace(chr(38) + "quot;" + chr(59), DQ)
    return s


def convert(md):
    del WARNINGS[:]
    md = preprocess(md)
    ast = md_to_ast(md)
    r = R()
    r.render(ast["blocks"])
    return r.out().strip() + "\n"


def convert_checked(md):
    """返回 (typst源码, 警告列表)。警告非空说明输入有问题但没报错。"""
    out = convert(md)
    return out, list(WARNINGS)


if __name__ == "__main__":
    import sys
    src = sys.stdin.read()
    try:
        sys.stdout.write(convert(src))
    except TypstError as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(1)
