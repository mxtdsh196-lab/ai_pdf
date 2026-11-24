#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""markdown -> typst（pandoc JSON AST + 组件 fenced div）"""
import subprocess, shutil, json, re, os, sys, tempfile, base64
try:
    import colorkit as _CK
except Exception:
    _CK = None
try:
    import oklch as _OK
except Exception:
    _OK = None
try:
    import imgsrc as _IS
except Exception:
    _IS = None

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
# 由 core.py 在转换前设置：版心（可排版区域）尺寸，单位 mm。
# 主要给 collage 用：画布不能超过版心，否则向右/下溢出页边。
CTX = {"content_w": None, "content_h": None, "margin_x": None, "margin_y": None}

def set_ctx(**kw):
    """core.py 把页面尺寸/边距告诉我，collage 才能算出真正的可用宽度。"""
    for k in ("content_w", "content_h", "margin_x", "margin_y"):
        if k in kw and kw[k] is not None:
            CTX[k] = float(kw[k])

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


_CHK_ON = '#box(width: 0.85em, height: 0.85em, radius: 2pt, fill: rgb("#2547A8"), align(center + horizon, text(size: 0.6em, fill: rgb("#FFFFFF"), weight: "bold")[✓]))'
_CHK_OFF = '#box(width: 0.85em, height: 0.85em, radius: 2pt, stroke: 1pt + rgb("#B0B7C3"), fill: none)[]'

# 渲染期产生的临时文件（SVG 二维码/曲线、PNG 噪点…）。
# 这些文件必须活到 typst 编译那一刻，所以不能在生成时立刻删；
# 统一登记，由 core.cmd_build 在编译结束后 flush_tmp() 清掉。
# 之前完全不清理，实测一次测试轮次就漏了 87 个文件在 /tmp。
_TMP_FILES = []


def _mkstemp(suffix, prefix):
    fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix)
    os.close(fd)
    _TMP_FILES.append(path)
    return path


def flush_tmp():
    """删除本进程登记过的临时文件。返回删掉的个数。"""
    n = 0
    while _TMP_FILES:
        p = _TMP_FILES.pop()
        try:
            if os.path.exists(p):
                os.unlink(p)
                n += 1
        except Exception:
            pass
    return n


def _len_ok(raw, lo, hi, label):
    """长度参数校验：接受 2.5pt / 3mm / 12 这类写法，数字部分做范围钳制。
    纯数字按 pt 处理（贴齐 Typst 的默认单位习惯）。"""
    s = str(raw).strip()
    import re as _r2
    m = _r2.match(r'^([0-9]+(?:\.[0-9]+)?)\s*(pt|mm|cm|em|in)?$', s)
    if not m:
        WARNINGS.append("%s 写了 %s，不是合法长度，已忽略" % (label, s))
        return None
    val = float(m.group(1))
    unit = m.group(2) or 'pt'
    if val < lo or val > hi:
        WARNINGS.append("%s=%s 超出建议范围 %s~%s%s，已钳到边界" % (label, val, lo, hi, unit))
        val = max(lo, min(hi, val))
    return ("%g%s" % (val, unit))


def esc(t):
    # 先按普通文本转义，再把占位符换成 Typst 代码
    # （顺序反了的话，_CHK_* 里的 # 会被转义成 \#，整段变成字面量）
    out = "".join(_ESC.get(c, c) for c in str(t))
    return out.replace(chr(0xE000), _CHK_ON).replace(chr(0xE001), _CHK_OFF)


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


BT3 = chr(96) * 3


def _fix_hr(md):
    """给紧贴文字的 --- 补前后空行。

    Markdown 经典坑：`文字` 换行 `---` 会被 pandoc 解析成 setext 二级标题
    （Header），不是 HorizontalRule。于是 ::: slide-split 的 --- 分隔永远失效。
    在交给 pandoc 之前统一补空行，让两种写法都产出 HorizontalRule。
    """
    lines = md.split(chr(10))
    out = []
    in_fence = False
    for i, ln in enumerate(lines):
        st = ln.strip()
        if st.startswith(BT3):
            in_fence = not in_fence
            out.append(ln)
            continue
        # 三个及以上纯 - 才算分隔线
        is_hr = (not in_fence) and len(st) >= 3 and st == ('-' * len(st))
        if is_hr:
            if out and out[-1].strip() != '':
                out.append('')
            out.append(st)
            if i + 1 < len(lines) and lines[i + 1].strip() != '':
                out.append('')
            continue
        out.append(ln)
    return chr(10).join(out)


def preprocess(md):
    md = _fix_hr(md)
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

    # task list 语法 -> 私有区占位符（PUA 字符 pandoc 不会动），
    # 交给 theme2.typ 里的 show list.item 画方框。
    # 不用 ☒/☐：字体缺这两个字形时会静默回落成豆腐块（实测踩过）。
    md = md.replace("- [x]", "- " + chr(0xE000) + " ")
    md = md.replace("- [X]", "- " + chr(0xE000) + " ")
    md = md.replace("- [ ]", "- " + chr(0xE001) + " ")
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
            path = _mkstemp(suffix='.svg', prefix='mmd_')

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
    def _qrcode(self, blocks, cls=None, kvs=None):
        """二维码。数据行：内容|说明（说明可省）

        也支持同行写法：::: qrcode 内容|说明
        """
        kvs = kvs or {}
        rows = []
        for k, payload, _lv in self._lines(blocks or []):
            if k != "line":
                continue
            txt = self._text(payload).strip()
            if txt:
                rows.append(txt)
        # 同行写法：把 div 头部的文字当作首行数据
        if not rows:
            head_txt = self._head_text(cls or [], kvs, skip=1)
            if head_txt:
                rows.append(head_txt)
        if not rows:
            WARNINGS.append("qrcode 里没有内容，无法生成二维码（写法：::: qrcode 网址|说明，或下一行写内容）")
            return ""
        head = rows[0]
        parts = [p.strip() for p in head.split("|")]
        data = parts[0]
        caption = parts[1] if len(parts) > 1 else ""
        try:
            import qrgen
            r = qrgen.render_png(data, "M", box=8, border=4)
            if r is None:
                WARNINGS.append("qrcode 内容过长，无法生成（上限约 200 字节）")
                return ""
            png, dim, ver = r
            path = _mkstemp(suffix=".png", prefix="qr_")
            open(path, "wb").write(png)
            opt = "" if not caption else ", caption: [%s]" % esc(caption)
            return "#qrcode(%s, size: 30mm%s)" % (q(path), opt)
        except Exception as e:
            WARNINGS.append("qrcode 生成失败：%s" % str(e)[:60])
            return ""

    def _price(self, blocks):
        """价格表。每行：套餐|价格|功能1,功能2|推荐标签（可省）"""
        items = []
        for k, payload, _lv in self._lines(blocks or []):
            if k != "line":
                continue
            parts = [self._text(p).strip() for p in self._split_pipe(payload)]
            if len(parts) < 2:
                WARNINGS.append("price 这一行少于 2 列，已跳过：%s" % (parts[0] if parts else ""))
                continue
            nm = parts[0]
            pr = parts[1]
            feats = [x.strip() for x in (parts[2] if len(parts) > 2 else "").split(",") if x.strip()]
            hot = parts[3] if len(parts) > 3 else ""
            fl = ", ".join("[" + esc(f) + "]" for f in feats) if feats else ""
            items.append("(%s, %s, (%s%s), %s)" % (q(nm), q(pr), fl, "," if feats else "", q(hot)))
        if not items:
            WARNINGS.append("price 没有数据行")
            return ""
        n = len(items)
        cols = n if n <= 3 else 3
        return "#price-plans((%s), cols: %d)" % (", ".join(items), cols)

    def _faq(self, blocks):
        """FAQ。每行：问题|答案"""
        items = []
        for k, payload, _lv in self._lines(blocks or []):
            if k != "line":
                continue
            parts = [self._text(p).strip() for p in self._split_pipe(payload)]
            if len(parts) < 2:
                WARNINGS.append("faq 需要「问题|答案」两列，这一行已跳过")
                continue
            items.append("([%s], [%s])" % (esc(parts[0]), esc(parts[1])))
        if not items:
            WARNINGS.append("faq 没有数据行")
            return ""
        return "#faq((%s,))" % ", ".join(items)

    def _team(self, blocks, cls, kvs=None):
        """团队介绍。每行：姓名|职位|简介"""
        items = []
        for k, payload, _lv in self._lines(blocks or []):
            if k != "line":
                continue
            parts = [self._text(p).strip() for p in self._split_pipe(payload)]
            if len(parts) < 2:
                WARNINGS.append("team 需要「姓名|职位|简介」，这一行已跳过")
                continue
            nm = parts[0]
            role = parts[1]
            bio = parts[2] if len(parts) > 2 else ""
            items.append("([%s], [%s], [%s])" % (esc(nm), esc(role), esc(bio)))
        if not items:
            WARNINGS.append("team 没有数据行")
            return ""
        n = len(items)
        cols = n if n <= 3 else 3
        return "#team((%s,), cols: %d)" % (", ".join(items), cols)

    def _fx(self, blocks, cls, kvs=None):
        """特效块。用法：::: fx frost / glow / noise / gradient / wave"""
        kvs = kvs or {}
        # pandoc 会把 ::: fx glow 里的 glow 解析成 data-title，不是第二个 class
        kind = (cls[1] if len(cls) > 1 else
                kvs.get("title") or kvs.get("data-title") or
                kvs.get("kind") or kvs.get("data-kind") or "frost")
        kind = str(kind).strip().lower()
        # 收集正文（保留为 Typst 内容，不进 SVG）
        body = []
        for k, payload, _lv in self._lines(blocks or []):
            if k == "line":
                body.append(self.ins(payload))
        body_txt = " ".join(x for x in body if x)
        pad = kvs.get("padding") or kvs.get("pad") or "5mm"
        rad = kvs.get("radius") or "6"
        tone = kvs.get("tone") or "primary"

        # ---- 特效程度：全部可调，带范围钳制 ----
        # 之前全都写死在 theme2.typ 里，AI 没有任何手段改强度。
        # 这里统一解析 + 钳制，越界给 warning 而不是静默失败。
        def _num(keys, default, lo, hi, label):
            raw = None
            for k in keys:
                v = kvs.get(k) or kvs.get("data-" + k)
                if v is not None and str(v).strip() != "":
                    raw = str(v).strip()
                    break
            if raw is None:
                return default
            try:
                val = float(raw)
            except Exception:
                WARNINGS.append("%s 写了 %s，不是数字，已用默认 %s" % (label, raw, default))
                return default
            if val < lo or val > hi:
                WARNINGS.append("%s=%s 超出范围 %s~%s，已钳到边界" % (label, val, lo, hi))
                val = max(lo, min(hi, val))
            return val

        def _len(keys, default, lo, hi, label):
            """长度参数：允许带单位（2.5pt / 3mm），数字部分按 lo/hi 钳制。"""
            raw = None
            for k in keys:
                v = kvs.get(k) or kvs.get("data-" + k)
                if v is not None and str(v).strip() != "":
                    raw = str(v).strip()
                    break
            if raw is None:
                return default
            if hi > lo:
                # 有范围要求时走统一校验；lo/hi 传 0/0 表示不限
                got = _len_ok(raw, lo, hi, label)
                return got if got else default
            import re as _r3
            if not _r3.match(r'^[0-9]+(?:\.[0-9]+)?\s*(pt|mm|cm|em|in)?$', raw):
                WARNINGS.append("%s 写了 %s，不是合法长度，已用默认 %s" % (label, raw, default))
                return default
            return raw

        if kind == "glow":
            _gs = _num(("strength", "glow", "fade"), 82, 0, 100, "fx glow strength")
            _gw = _len(("width", "w-stroke", "line"), "2pt", 0, 0, "fx glow width")
            return "#fx-glow([%s], color: %s, inset-v: %s, rad: %s, strength: %s, width: %s)" % (
                body_txt, q(tone), pad, rad, int(_gs), _gw)
        if kind in ("frost", "glass"):
            _fo = _num(("opacity", "alpha", "solid"), 55, 0, 100, "fx frost opacity")
            _fl = _num(("light", "highlight"), 30, 0, 100, "fx frost light")
            _fb = _len(("bar", "bar-width"), "2.5pt", 0, 0, "fx frost bar")
            _fbd = _len(("border", "bw"), "0.9pt", 0, 0, "fx frost border")
            # 颗粒参数：grain=点阵间距(pt)，grain-a=颗粒浓度(0~100)
            # 默认 4.0 而不是 1.8：1.8pt 的颗粒在 100~150dpi 下只有 2~3px，糊成一片，
            # 实测用户直接说「磨砂还是没有」。4.0 才能在正常查看尺寸下看出砂面。
            _fg = _num(("grain", "grain-size"), 0, 0, 10.0, "fx frost grain")
            _fga = _num(("grain-a", "grain-alpha", "grain-opacity"), 0, 0, 100, "fx frost grain-a")
            # bg：磨砂必须压在内容上才看得见。支持两种写法：
            #   bg=gradient  → 自动生成渐变背景图（配 bg-c1/bg-c2/bg-angle）
            #   bg=/path.png → 直接用这张图
            _bg = kvs.get("bg") or kvs.get("backdrop") or kvs.get("data-bg")
            _bg_out = ""
            if _bg:
                _bgs = str(_bg).strip()
                if _bgs.lower() in ("gradient", "grad", "1"):
                    try:
                        import fxgen
                        _bc1 = (kvs.get("bg-c1") or "2547A8").lstrip("#")
                        _bc2 = (kvs.get("bg-c2") or "BE123C").lstrip("#")
                        _bang = _num(("bg-angle", "bg-deg"), 120, 0, 360, "fx frost bg-angle")
                        # 关键：磨砂玻璃要模糊的是它下面的背景。背景模糊 24pt 才像真玻璃
                        # （用户拿真玻璃照片对比过：真实磨砂是「背景被揉化」，不是「叠一层颗粒」）。
                        # 背景是纯图形，模糊它不损失任何文字可搜索性。
                        _bblur = _num(("bg-blur", "bg-bl"), 24, 0, 80, "fx frost bg-blur")
                        _svgbg = fxgen.gradient_blob(600, 260, _bc1, _bc2,
                                                     angle=int(_bang), strength=1.0,
                                                     blur=float(_bblur))
                        _bgpath = _mkstemp(suffix=".svg", prefix="fxbg_")
                        open(_bgpath, "w", encoding="utf-8").write(_svgbg)
                        _bg_out = ", bg: %s" % q(_bgpath)
                    except Exception as _e:
                        WARNINGS.append("fx frost 的 bg 生成失败：%s" % str(_e)[:50])
                elif os.path.exists(_bgs):
                    _bg_out = ", bg: %s" % q(_bgs)
                else:
                    WARNINGS.append("fx frost 的 bg 写了 %s，既不是 gradient 也不是存在的文件，已忽略" % _bgs[:40])
            return ("#fx-frost([%s], rat: %s, inset-v: %s, opacity: %s, light: %s, "
                    "bar: %s, border: %s, grain: %s, grain-a: %s%s)"
                    % (body_txt, rad, pad, int(_fo), int(_fl), _fb, _fbd,
                       ("%.2f" % _fg), int(_fga), _bg_out))
        # 其余属于纯装饰图层：生成 SVG 叠在下面，文字仍用 Typst
        try:
            import fxgen
            w = int(kvs.get("w") or 600)
            h = int(kvs.get("h") or 220)
            col = kvs.get("color") or kvs.get("c1")
            c2 = kvs.get("c2")
            if kind == "noise":
                # 用栅格 PNG：SVG 的 feTurbulence 会膨胀成海量 path，实测 37KB 涨到 3.4MB
                # alpha=颗粒浓度(0~1) w/h=像素尺寸
                _na = _num(("alpha", "density", "amount"), 0.12, 0.0, 1.0, "fx noise alpha")
                # 兼容写成百分数 alpha=30 的情形
                if _na > 1.0:
                    _na = _na / 100.0
                # 噪点是横向扁条：按版心宽高比生成（约 483:40 ≈ 12:1），
                # 生成 600:220 的竖图再插会按原比例撑到 177pt 高（实测）。
                _nw = int(w * 2)
                _nh = max(24, int(_nw * 40.0 / 483.0))
                png = fxgen.noise_png(_nw, _nh, alpha=_na)
                if png:
                    path = _mkstemp(suffix=".png", prefix="fxn_")
                    open(path, "wb").write(png)
                    if body_txt:
                        return "#fx-card([%s], %s, inset-v: %s)" % (body_txt, q(path), pad)
                    return ("#block(width: 100%%, above: 4pt, below: 4pt)[#image(%s, width: 100%%)]" % q(path))
                svg = fxgen.noise_texture(w, h)
            elif kind == "gradient":
                # c1/c2=两端颜色 angle=光斑角度(0~360) strength=浓度(0~1)
                a = (col.lstrip(chr(35)) if col else None)
                b = (c2.lstrip(chr(35)) if c2 else None)
                _ang = _num(("angle", "deg"), 135, 0, 360, "fx gradient angle")
                _gst = _num(("strength", "density"), 0.85, 0.0, 1.0, "fx gradient strength")
                if _gst > 1.0:
                    _gst = _gst / 100.0
                # blur：给渐变加高斯模糊。frost 的 bg 默认模糊（磨砂玻璃要模糊背景），
                # 单独的 fx gradient 保持清晰。blur=0 可显式关掉。
                _gblur = _num(("blur", "b"), 0, 0, 60, "fx gradient blur")
                svg = fxgen.gradient_blob(int(w), int(h), a or "2547A8", b or "7C3AED",
                                          angle=int(_ang), strength=_gst,
                                          blur=float(_gblur))
            elif kind == "wave":
                # amp=波幅 color=颜色
                _amp = _num(("amp", "amplitude"), 8, 1, 40, "fx wave amp")
                _wc = kvs.get("color") or kvs.get("c1")
                _wc = ("#" + _wc.lstrip("#")) if _wc else None
                try:
                    if _wc:
                        svg = fxgen.wave_divider(int(w), 24, color=_wc, amp=int(_amp))
                    else:
                        svg = fxgen.wave_divider(int(w), 24, amp=int(_amp))
                except TypeError:
                    svg = fxgen.wave_divider(int(w), 24)
                    WARNINGS.append("fx wave 的 amp/color 未被支持（fxgen 版本旧），已用默认")
            else:
                WARNINGS.append("fx 的 kind 写了 %s，支持 frost/glow/noise/gradient/wave，已按 grid 跳过" % kind)
                return body_txt
            path = self._write_tmp(svg, ".svg")
            if not path:
                return body_txt
            if body_txt:
                return "#fx-card([%s], %s, inset-v: %s)" % (body_txt, q(path), pad)
            return ("#block(width: 100%%, above: 4pt, below: 4pt)[#image(%s, width: 100%%)]" % q(path))
        except Exception as e:
            WARNINGS.append("fx 生成失败：%s" % str(e)[:60])
            return body_txt

    def _curve(self, blocks, cls, kvs=None):
        """自定义曲线装饰。首行写 SVG path，例如 M10,70 C60,20 140,95 270,30"""
        kvs = kvs or {}
        path_d = str(kvs.get("path") or kvs.get("data-path") or "")
        for k, payload, _lv in self._lines(blocks or []):
            if k != "line":
                continue
            t = self._text(payload).strip()
            if t and not path_d:
                path_d = t
        if not path_d:
            # 同行写法：::: curve M10,70 C60,20 140,95 270,30
            path_d = self._head_text(cls or [], kvs, skip=1)
        if not path_d:
            path_d = "M10,70 C60,20 140,95 270,30"
            WARNINGS.append("curve 没写 path，已用默认曲线。写法：::: curve M10,70 C60,20 140,95 270,30")
        if not (path_d.startswith(chr(77)) or path_d.startswith(chr(109))):
            WARNINGS.append("curve 的 path 必须以 M 开头（SVG path 语法），已加前缀")
            path_d = "M" + path_d
        try:
            import fxgen
            w = int(kvs.get("w") or 280)
            h = int(kvs.get("h") or 90)
            col = kvs.get("color")
            aw = kvs.get("width") or "2.5"
            svg = fxgen.curve_ornament(w, h, path_d, (col.lstrip(chr(35)) if col else "1F7A5C"), float(aw))
            p = self._write_tmp(svg, ".svg")
            if not p:
                return ""
            return "#fx-curve(%s)" % q(p)
        except Exception as e:
            WARNINGS.append("curve 生成失败：%s" % str(e)[:60])
            return ""

    def _write_tmp(self, content, suffix):
        """把内容写成临时文件，返回路径。XML 头会自动补。"""
        try:
            if not content.lstrip().startswith("<"):
                return None
            path = _mkstemp(suffix=suffix, prefix="fx_")
            open(path, "w", encoding="utf-8").write(content)
            return path
        except Exception:
            return None

    def _head_text(self, cls, kvs, skip=1):
        """取 fenced div 头部与组件名同一行的文字。

        pandoc 会把 `::: capsule 标题` 里的标题解析成 data-title 属性，
        而不是 inner 内容。cls 里也可能剩几个词（含空格的会被拆开）。
        skip: cls 前几个是组件名/变体，跳过。
        """
        t = kvs.get("title") or kvs.get("data-title")
        if t:
            return str(t).strip()
        rest = [c for c in (cls or [])[skip:] if c]
        if rest:
            return " ".join(rest).strip()
        return ""

    def _rows_of(self, blocks):
        """把组件内容拆成 [(cells...)]，每行用 | 分隔"""
        out = []
        for k, payload, _lv in self._lines(blocks or []):
            if k != "line":
                continue
            cells = [self._text(p).strip() for p in self._split_pipe(payload)]
            if any(cells):
                out.append(cells)
        return out

    def _collage(self, blocks, cls, kvs=None):
        """拼贴版面：每行一个图层，类型|内容|x,y|尺寸|参数"""
        kvs = kvs or {}
        # ★ 常见错法：把第一行图层写在 `::: collage w= h=` 的同一行。
        # pandoc 会把那行当 data-title，图层直接消失且不报错。这里拎出来补回去。
        _KINDS = ("bgimg", "photo-bg", "mask", "veil", "img", "oval", "ellipse",
                  "arch", "text", "vtext", "vertical", "block", "panel", "box",
                  "dot", "ring", "circle-line", "line", "curve", "arc", "orn",
                  "flourish")
        _stray = str(kvs.get("data-title") or "").strip()
        if _stray and _stray.split("|")[0].strip().lower() in _KINDS:
            WARNINGS.append("collage 的第一行图层写在了 ::: 同一行（%s），已自动移回。"
                            "建议改成换行写，否则容易被当标题丢掉" % _stray.split("|")[0][:16])
            blocks = list(blocks or [])
        rows = self._rows_of(blocks)
        if _stray and _stray.split("|")[0].strip().lower() in _KINDS:
            rows = [_stray.replace("|", chr(1)).split(chr(1))] + list(rows)
        if not rows:
            WARNINGS.append("collage 没有图层")
            return ""

        _crop_mem = {}

        def _f(v, d=None):
            try:
                return float(str(v).strip())
            except Exception:
                return d

        def _mm(v, d=0.0):
            s = str(v).strip().lower()
            for u in ("mm", "cm", "pt", "in"):
                if s.endswith(u):
                    s = s[: -len(u)]
                    n = _f(s, d)
                    if u == "cm":
                        return n * 10.0
                    if u == "pt":
                        return n * 0.352778
                    if u == "in":
                        return n * 25.4
                    return n
            return _f(s, d)

        def _xy(v):
            p = str(v).replace("，", ",").split(",")
            if len(p) < 2:
                return None
            return (_mm(p[0], 0.0), _mm(p[1], 0.0))

        def _sz(v, d1, d2):
            p = str(v).replace("，", ",").split(",")
            w = _mm(p[0], d1) if str(p[0]).strip() else d1
            h = d2
            if len(p) > 1 and str(p[1]).strip():
                h = _mm(p[1], d2)
            return w, h

        def _col(c, d=None):
            s = str(c or "").strip().lstrip("#")
            if len(s) == 6 and all(x in "0123456789abcdefABCDEF" for x in s):
                return 'rgb("#%s")' % s.upper()
            if d:
                return 'rgb("#%s")' % d
            return "none"

        # ★ 角色色阶：fill=deep / color=pale 这种写法。
        # 用户只需给一个基色（palette_from=1F3A5F 或主题色），
        # 工具用 OKLab 生成同色相的深→浅阶梯，AI 不用懂色彩学。
        _RAMP = {}

        def _ramp_get(name, base_hex):
            """取角色色值。未生成过就用 base_hex 生成一套。"""
            if _OK is None or not base_hex:
                return None
            if base_hex not in _RAMP:
                try:
                    _RAMP[base_hex] = _OK.ramp_named(base_hex)
                except Exception:
                    _RAMP[base_hex] = {}
            return _RAMP[base_hex].get(str(name).lower())

        _ROLES = ("deep", "mid", "veil", "soft", "pale", "paper", "ink", "accent")

        def _colx(v, base_hex, d=None):
            """带角色名的颜色解析。先试十六进制，再试角色名，最后回退默认。"""
            s0 = str(v or "").strip().lstrip("#")
            if len(s0) == 6 and all(x in "0123456789abcdefABCDEF" for x in s0):
                return _col(s0, d), s0.upper()
            if s0.lower() in _ROLES:
                got = _ramp_get(s0, base_hex)
                if got:
                    return _col(got, d), got
            return _col(s0, d), (d or "")

        def _auto_fg(bghex, floor=4.5):
            """给底色选一个能看清的前景色。
            ★ 返回 Typst 表达式 rgb("#XXX")，和 _col() 保持一致。
            直接返回裸 #XXX 会有两个问题：① 拼进模板出现 fill: #FFFFFF
            （Typst 代码模式里 # 非法）② 与 _col 的调用点格式不一致。"""
            _hex = "141414"
            if _CK is not None:
                try:
                    _hex, _r = _CK.best_fg(bghex, floor)
                except Exception:
                    _hex = "141414"
            return 'rgb("#%s")' % str(_hex).lstrip("#").upper()

        def _contrast_warn(where, fghex, bghex, floor=4.5):
            """对比度不足时记一条告警，并返回建议前景。
            AI 选了看不清的配色要能知道，不能等用户肉眼看出来。"""
            if _CK is None:
                return fghex
            try:
                sug, ratio, ok = _CK.fix_pair(fghex, bghex, floor)
            except Exception:
                return fghex
            if ok or ratio is None:
                return fghex
            _fg = str(fghex).lstrip("#")
            _bg = str(bghex).lstrip("#")
            _sg = str(sug).lstrip("#")
            if ratio < 3.0:
                WARNINGS.append(
                    "collage %s 文字对比度只有 %.1f:1（#%s 压在 #%s 上），几乎看不清；"
                    "已改成 #%s。要么换底色，要么把 alpha 调低"
                    % (where, ratio, _fg, _bg, _sg))
                return "#" + _sg
            if ratio < floor:
                WARNINGS.append(
                    "collage %s 文字对比度偏低 %.1f:1（#%s 压在 #%s 上），建议 #%s"
                    % (where, ratio, _fg, _bg, _sg))
            return fghex

        def _kv(extra, key):
            import re as _re
            for part in extra:
                p = str(part).strip()
                if "=" not in p:
                    continue
                for mt in _re.finditer(r"([A-Za-z][\w-]*)\s*=\s*([^\s]+)", p):
                    if mt.group(1).lower() == key:
                        return mt.group(2).strip()
            return None

        # palette_from：整个 collage 的基色。写了它，fill/color 就能用角色名
        # （deep/mid/veil/soft/pale/paper/ink/accent）代替十六进制。
        _pbase = str(kvs.get("palette_from") or kvs.get("base") or "").strip().lstrip("#").upper()
        if len(_pbase) != 6:
            _pbase = ""
        _wv = kvs.get("w") or kvs.get("width")
        _hv = kvs.get("h") or kvs.get("height")
        cw = _mm(_wv, 210.0) if _wv else None
        ch = _mm(_hv, 297.0) if _hv else None
        # ★ 画布不能超过版心。slide 主题 margin=15mm，版心只有 267mm；
        # 用户写 w=297（页面宽）时，画布会向右溢出 15mm，pdf_lint 报 graphic_overflow。
        # 这里把超出版心的部分收回到版心尺寸，并按比例缩坐标（等比，不变形）。
        _lim_w = CTX.get("content_w")
        _lim_h = CTX.get("content_h")
        _sc = 1.0
        if _lim_w and cw and cw > _lim_w + 0.5:
            _sc = _lim_w / cw
        if _lim_h and ch and ch * _sc > _lim_h + 0.5:
            _sc = min(_sc, _lim_h / ch)
        _scaled = False
        _has_bgimg = False   # 画布是否被照片铺满（影响文字默认颜色）
        if _sc < 0.999:
            _raw_w, _raw_h = cw, ch   # 缩之前的大小，给告警用
            cw = cw * _sc
            ch = ch * _sc
            _scaled = True
            WARNINGS.append("collage 画布 %.1fx%.1fmm 超出了版心 %.1fx%.1fmm，"
                            "已自动等比缩到 %.1fx%.1fmm（图形和字号一起缩）。"
                            "建议直接把 w/h 写成版心尺寸"
                            % (_raw_w, _raw_h, _lim_w or 0, _lim_h or 0, cw, ch))
        bgc = (kvs.get("bg") or "").strip().lstrip("#")

        def _anchor(a, wmm, hmm, pad):
            """pos=right-top 这种锚点算成 x,y（工具算，不让 AI 手算）。"""
            s = str(a).lower().replace("_", "-").replace(" ", "-")
            hz = "left" if "left" in s else ("right" if "right" in s else "center")
            vt = "top" if "top" in s else ("bottom" if "bottom" in s else "middle")
            W = cw if cw else 297.0
            H = ch if ch else 167.0
            if hz == "left":
                x = pad
            elif hz == "right":
                x = W - wmm - pad
            else:
                x = (W - wmm) / 2.0
            if vt == "top":
                y = pad
            elif vt == "bottom":
                y = H - hmm - pad
            else:
                y = (H - hmm) / 2.0
            return (x, y)

        def _doc_shape(shp, W, H, k):
            """返回 clipPath 的 path d；rect 返回 None（不裁剪）。"""
            try:
                k = min(0.49, max(0.02, float(k)))
            except Exception:
                k = 0.26
            rx, ry = W * k, H * k
            if shp in ("", "rect", "none"):
                return None
            if shp in ("ellipse", "oval", "circle"):
                return ("M0.00,%.2f A%.2f,%.2f 0 1,0 %.2f,%.2f A%.2f,%.2f 0 1,0 0.00,%.2f Z"
                        % (H / 2.0, W / 2.0, H / 2.0, W, H / 2.0, W / 2.0, H / 2.0, H / 2.0))
            if shp in ("arc", "tl", "arc-tl"):
                return ("M%.2f,0.00 L%.2f,0.00 L%.2f,%.2f L0.00,%.2f L0.00,%.2f "
                        "Q0.00,0.00 %.2f,0.00 Z" % (rx, W, W, H, H, ry, rx))
            if shp in ("arc4", "round", "rounded"):
                return ("M%.2f,0.00 L%.2f,0.00 Q%.2f,0.00 %.2f,%.2f L%.2f,%.2f "
                        "Q%.2f,%.2f %.2f,%.2f L%.2f,%.2f Q0.00,%.2f 0.00,%.2f "
                        "L0.00,%.2f Q0.00,0.00 %.2f,0.00 Z"
                        % (rx, W - rx, W, W, ry, W, H - ry, W, H, W - rx, H,
                           rx, H, H - ry, H - ry, rx))
            if shp in ("slant", "bevel"):
                return "M0.00,0.00 L%.2f,0.00 L%.2f,%.2f L0.00,%.2f Z" % (W - rx * 1.6, W, H, H)
            if shp in ("notch", "cut"):
                return ("M0.00,0.00 L%.2f,0.00 L%.2f,%.2f L%.2f,%.2f L0.00,%.2f Z"
                        % (W - rx, W, ry, W, H, H))
            if shp in ("arch", "dome"):
                return ("M0.00,%.2f L0.00,%.2f Q0.00,0.00 %.2f,0.00 L%.2f,0.00 "
                        "Q%.2f,0.00 %.2f,%.2f L%.2f,%.2f Z"
                        % (H, ry, rx, W - rx, W, W, ry, W, H))
            if shp in ("wave", "flag"):
                return ("M0.00,0.00 L%.2f,0.00 L%.2f,%.2f "
                        "Q%.2f,%.2f %.2f,%.2f Q%.2f,%.2f 0.00,%.2f Z"
                        % (W, W, H, W * 0.66, H - ry, W * 0.5, H,
                           W * 0.34, H - ry, H))
            return None

        def _crop_cache(src, wmm, hmm):
            """把原图裁成目标宽高比并缩放，按 (路径, 宽高比) 缓存。
            ★ 必须预裁：Typst 算 SVG 包围盒时用的是 <image> 在 slice 展开后的
            尺寸（含溢出部分），不是 viewport。实测 600x404 viewport + 立式原图
            → 包围盒按 600x900 算 → width:86mm 实际画出 97.2mm（放大 13%）。
            预裁成精确比例 + preserveAspectRatio='none' 才是 86.0mm。"""
            key = (os.path.abspath(src), round(float(wmm), 2), round(float(hmm), 2))
            if key in _crop_mem:
                return _crop_mem[key]
            try:
                from PIL import Image
            except Exception:
                return None
            try:
                # 裁图只是「锦上添花」，坏图不该让整页失败：允许容错读取
                from PIL import ImageFile as _IF
                _IF.LOAD_TRUNCATED_IMAGES = True
                im = Image.open(src)
                im = im.convert("RGB") if im.mode not in ("RGB", "L") else im
                iw, ih = im.size
                # ★ 先按目标 dpi 算出目标像素尺寸，再求覆盖缩放比。
                # 不能直接拿 mm 除 px（量纲混用）——那样图会被缩成 6x4 像素变马赛克。
                DPI = 300.0
                tw = max(8, int(round(float(wmm) / 25.4 * DPI)))
                th = max(8, int(round(float(hmm) / 25.4 * DPI)))
                # 像素上限只用来防超大图拖体积，不能用 1800。
                # 1800 会把 243.8mm 宽的图压到 188dpi（实测原值上限 103dpi），
                # pdf_lint 低于 150dpi 就会报。3000 能保住 300dpi 下的 A4 版心。
                _MAXPX = 3000.0
                cap = _MAXPX / max(tw, th)
                if cap < 1.0:
                    tw, th = max(8, int(tw * cap)), max(8, int(th * cap))
                # 低 dpi 不在这里告警：bgimg 走另一条路径（直接引用原图）不会经过这里，
                # 两边各报一套会重复。统一由 pdf_lint 的 low_dpi 检（已实测能报准）。
                r = max(float(tw) / iw, float(th) / ih)
                nw, nh = max(1, int(iw * r + 0.5)), max(1, int(ih * r + 0.5))
                if (nw, nh) != (iw, ih):
                    im = im.resize((nw, nh), Image.LANCZOS)
                l = max(0, (nw - tw) // 2)
                t = max(0, (nh - th) // 2)
                im = im.crop((l, t, l + tw, t + th))
                out = _mkstemp(suffix=".jpg", prefix="clc_")
                im.save(out, quality=88, optimize=True)
                _crop_mem[key] = out
                return out
            except Exception as e:
                WARNINGS.append("collage 预裁失败（%s），改回直接引用原图" % str(e)[:40])
                return None

        def _img_src(spec, need_w_mm=0):
            """把图片地址解析成本地路径。
            @wikimedia:雪山   搜 CC0 图并下载（真搜索，能命中主题）
            @picsum:night     免 key 随机图（seed 只是哈希，不保证主题）
            其它              当作本地路径
            ★ Typst 不能读 http URL（实测报 file not found，把 URL 当相对路径），
            所以必须在这里先下载成文件。"""
            sp = str(spec or "").strip()
            # ★ 不能用 @ 开头：pandoc 会把 @xxx 当 Citation 节点，md2typst
            # 只处理 Str，图片内容会整段消失。改用 src: 前缀。
            if not (sp.lower().startswith("src:") or sp.startswith("@")):
                return sp
            if _IS is None:
                WARNINGS.append("collage 取图不可用：imgsrc 模块未加载（%s）" % sp[:40])
                return ""
            _w = int(max(800, min(3000, (need_w_mm or 200) / 25.4 * 200)))
            try:
                r = _IS.fetch(sp, width=_w)
            except Exception as e:
                WARNINGS.append("collage 取图失败（%s）：%s" % (sp[:30], str(e)[:50]))
                return ""
            if isinstance(r, dict):
                pth = r.get("path") or ""
                lic = r.get("license") or ""
                if lic and "CC0" not in lic and "Public domain" not in lic and "Unsplash" not in lic:
                    WARNINGS.append("collage 图片著作权提醒：%s 的授权是 %s，商用前确认是否需署名"
                                    % (sp[:30], lic))
                return pth
            if isinstance(r, str):
                return r
            WARNINGS.append("collage 没能取到图（%s），已跳过该图层" % sp[:40])
            return ""

        def _shaped(src, wmm, hmm, shp, k=0.26, fit="cover", stroke=None):
            """按形状裁剪照片。优先用预裁副本（实际尺寸精确），失败才直接引用原图。
            SVG 里用相对路径，不 base64：base64 418886 字节/张 → 相对引用 290 字节/张。"""
            W = 600.0
            H = max(60.0, W * float(hmm) / max(0.01, float(wmm)))
            d = _doc_shape(shp, W, H, k)
            if not d:
                return None
            path = _mkstemp(suffix=".svg", prefix="clp_")
            cropped = _crop_cache(src, wmm, hmm)
            if cropped:
                rel = os.path.relpath(cropped, os.path.dirname(path)).replace(os.sep, "/")
                par = "none"
            else:
                rel = os.path.relpath(src, os.path.dirname(path)).replace(os.sep, "/")
                par = "xMidYMid slice"
            rel = rel.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            extra = ""
            if stroke:
                try:
                    bw, bcv = stroke
                    sw = max(0.4, float(bw) * 0.352778 / max(0.01, float(wmm)) * W * 2.0)
                    extra = ("<path d='%s' fill='none' stroke='%s' stroke-width='%.2f'/>"
                             % (d, bcv, sw))
                except Exception:
                    extra = ""
            svg = ("<svg xmlns='http://www.w3.org/2000/svg' width='%d' height='%d' "
                   "viewBox='0 0 %d %d'>"
                   "<defs><clipPath id='c'><path d='%s'/></clipPath></defs>"
                   "<image x='0' y='0' width='%d' height='%d' "
                   "preserveAspectRatio='%s' clip-path='url(#c)' "
                   "href='%s'/>%s</svg>") % (int(W), int(H), int(W), int(H), d,
                                              int(W), int(H), par, rel, extra)
            open(path, "w", encoding="utf-8").write(svg)
            return path

        NL = chr(10)
        layers = []
        for r in rows:
            kind = r[0].strip().lower() if r else ""
            if not kind:
                continue
            content = r[1] if len(r) > 1 else ""
            pos_raw = r[2] if len(r) > 2 else ""
            size = r[3] if len(r) > 3 else ""
            extra = r[4:]

            if kind in ("bgimg", "photo-bg"):
                src = _img_src(content.strip(), cw or 297.0)
                _has_bgimg = True
                if not src or not os.path.exists(src):
                    WARNINGS.append("collage bgimg 不存在：%s" % src[:50])
                    continue
                # place 里的 100%% 是「相对页面」不是相对画布（实测被拉成 1263pt）。
                # 改用 layout 拿父容器真实尺寸，再按该尺寸铺满。
                # 不用 place：place 的 100% / layout 拿到的都是页面尺寸，
                # 图会被拉成页面高（1263pt）然后溢出画布。
                _bgw = _raw_w if _scaled else cw
                _bgh = _raw_h if _scaled else ch
                # 改成「画布 block 的第一项直接放 image」，它自然按容器宽度撑开，
                # 再用 height: 100% 填满，最后用零尺寸 box 抵消它对后续图层的位置影响。
                layers.append("#box(width: 0pt, height: 0pt)[#image(%s, width: %s, "
                              "height: %s, fit: \"cover\")]"
                              % (q(src),
                                 ("%.3fmm" % (_bgw if _bgw else 297.0)),
                                 ("%.3fmm" % (_bgh if _bgh else 167.0))))
                continue
            if kind in ("mask", "veil"):
                colv = _col(content, "000000")
                alpha = _f(size, 40.0) if str(size).strip() else 40.0
                layers.append("#place(top + left)[#box(width: 100%%, height: 100%%, "
                              "fill: %s.transparentize(%.1f%%))]" % (colv, alpha))
                continue

            # 尺寸先抽出来（锚点要算 x,y，必须先知道宽高）
            _presz = _sz(size, None, None) if str(size).strip() else (None, None)
            _sw, _sh = _presz
            _anc = _kv(extra, "pos") or _kv(extra, "anchor")
            pos = None
            if _anc and _sw is not None:
                _pad = _mm(_kv(extra, "pad"), 0.0)
                _ah = _sh if _sh is not None else (_sw * 0.75)
                pos = _anchor(_anc, _sw, _ah, _pad)
            if not pos:
                pos = _xy(pos_raw)
            if not pos:
                WARNINGS.append("collage 的 %s 位置不是 x,y（也没给 pos= 锚点）" % kind)
                continue
            px, py = pos
            base = "#place(top + left, dx: %.3fmm, dy: %.3fmm)" % (px, py)

            if kind == "img":
                _pre_w = _sz(size, 40.0, None)[0] if str(size).strip() else 40.0
                src = _img_src(content.strip(), _pre_w)
                if not src or not os.path.exists(src):
                    WARNINGS.append("collage 图片不存在：%s" % src[:50])
                    continue
                wmm, hmm = _sz(size, 40.0, None)
                if not hmm:
                    hmm = wmm * 0.75
                rot = _f(_kv(extra, "rot"), 0.0)
                rad = _mm(_kv(extra, "r"), 0.0)
                fitm = (_kv(extra, "fit") or "cover").strip()
                bw = _f(_kv(extra, "bw"), 0.4)
                bcv = _col(_kv(extra, "bc"), "FFFFFF")
                shp = (_kv(extra, "shape") or "").strip().lower()
                sk = _f(_kv(extra, "k"), 0.26)
                if shp and shp not in ("rect", "none", ""):
                    # 异形裁剪：SVG clipPath + 原图相对引用（体积不膨胀）
                    bc6 = (_kv(extra, "bc") or "").strip().lstrip("#").upper()
                    sp = _shaped(src, wmm, hmm, shp, sk, fitm,
                                 stroke=(bw, bc6) if (bw and bw > 0 and len(bc6) == 6) else None)
                    if not sp:
                        WARNINGS.append("collage shape=%s 不认识，已按矩形画" % shp)
                        shp = "rect"
                    else:
                        inner = "#image(%s, width: %.3fmm)" % (q(sp), wmm)
                        if rot:
                            inner = "#rotate(%.2fdeg, origin: center, reflow: true)[%s]" % (rot, inner)
                        layers.append("%s[%s]" % (base, inner))
                        continue
                st = ", stroke: %.2fpt + %s" % (bw, bcv) if bw and bw > 0 else ""
                inner = ("#block(width: %.3fmm, height: %.3fmm, radius: %.3fmm, "
                         "clip: true%s)[#image(%s, width: 100%%, height: 100%%, "
                         "fit: %s)]" % (wmm, hmm, rad, st, q(src), q(fitm)))
                if rot:
                    inner = "#rotate(%.2fdeg, origin: center, reflow: true)[%s]" % (rot, inner)
                layers.append("%s[%s]" % (base, inner))

            elif kind in ("oval", "ellipse", "arch"):
                _pre_w2 = _sz(size, 50.0, None)[0] if str(size).strip() else 50.0
                src = _img_src(content.strip(), _pre_w2)
                if not src or not os.path.exists(src):
                    WARNINGS.append("collage oval 图片不存在：%s" % src[:50])
                    continue
                wmm, hmm = _sz(size, 50.0, None)
                if not hmm:
                    hmm = wmm * 1.25
                p = _shaped(src, wmm, hmm, "ellipse", 0.26, "cover")
                if p:
                    layers.append("%s[#image(%s, width: %.3fmm)]" % (base, q(p), wmm))

            elif kind == "text":
                s4 = str(size).strip()
                if s4 and "=" in s4:
                    extra = [s4] + list(extra)
                    wmm = None
                else:
                    wmm = _mm(size, None)
                fsize = _f(_kv(extra, "size"), 9.0)
                weight = (_kv(extra, "weight") or "regular").strip()
                # 没写 color 就按画布底色自动选；写了就查对比度
                if not _has_bgimg:
                    _craw2 = _kv(extra, "color")
                # 画布是背景照片时（bgimg），文字压在照片上，亮度不可预知。
                # 这里不再做对比度检查，直接默认白字（照片排版惯用）。
                if _has_bgimg:
                    colv = 'rgb("#FFFFFF")'
                    _craw2 = None
                    _canvas = "000000"
                else:
                    _canvas = bgc if bgc else (CTX.get("canvas_bg") or "FFFFFF")
                if _craw2 is None:
                    colv = _auto_fg(_canvas)
                else:
                    colv = _col(_craw2, "1A1A1A")
                    _f2 = _contrast_warn("text", _craw2.lstrip("#"), _canvas)
                    if str(_f2).lstrip("#").upper() != _craw2.lstrip("#").upper():
                        colv = _col(_f2, "1A1A1A")
                ital = (_kv(extra, "italic") or "").lower() in ("1", "true", "yes")
                lh = _f(_kv(extra, "leading"), 1.4)
                align = (_kv(extra, "align") or "left").strip()
                track = _f(_kv(extra, "track"), 0.0)
                fnt = _kv(extra, "font")
                opts = []
                if fnt:
                    opts.append("font: %s" % q(fnt.replace("_", " ")))
                opts.append("size: %.2fpt" % fsize)
                opts.append("weight: %s" % q(weight))
                opts.append("fill: %s" % colv)
                opts.append('style: "italic"' if ital else 'style: "normal"')
                if track:
                    opts.append("tracking: %.3fem" % (track / 100.0))
                wp = "width: %.3fmm" % wmm if wmm else ""
                layers.append("%s[#block(%s)[#set par(leading: %.2fem, justify: false)%s"
                              "#text(%s)[#align(%s)[%s]]]]"
                              % (base, wp, lh, NL, ", ".join(opts), align, esc(content.replace("<br>", chr(92)))
                              ))

            elif kind in ("block", "panel", "box"):
                s4 = str(size).strip()
                if s4 and "=" in s4 and "," not in s4:
                    extra = [s4] + list(extra)
                    s4 = "60"
                wmm, hmm = _sz(s4, 60.0, None)
                _fraw = _kv(extra, "fill")
                if _pbase and _fraw and str(_fraw).lower() in _ROLES:
                    fillc, _bgh = _colx(_fraw, _pbase, "33507D")
                else:
                    fillc = _col(_fraw, "33507D")
                    _bgh = str(_fraw or "33507D").lstrip("#")
                alpha = _f(_kv(extra, "alpha"), 8.0)
                # 没写 color 就按底色亮度自动选黑/白；写了就查对比度。
                _craw = _kv(extra, "color")
                if _craw is None:
                    colv = _auto_fg(_bgh)
                elif _pbase and str(_craw).lower() in _ROLES:
                    # 角色名：直接取阶梯值，不再查对比度（阶梯本身已保证可读）
                    colv, _ = _colx(_craw, _pbase, "FFFFFF")
                else:
                    colv = _col(_craw, "FFFFFF")
                    _fixed = _contrast_warn("block", _craw.lstrip("#"), _bgh)
                    if str(_fixed).lstrip("#").upper() != _craw.lstrip("#").upper():
                        colv = _col(_fixed, "FFFFFF")
                pad = _mm(_kv(extra, "pad"), 4.0)
                rad = _mm(_kv(extra, "r"), 2.0)
                fsize = _f(_kv(extra, "size"), 8.5)
                weight = (_kv(extra, "weight") or "regular").strip()
                align = (_kv(extra, "align") or "left").strip()
                lh = _f(_kv(extra, "leading"), 1.6)
                bfnt = _kv(extra, "font")
                hp = ", height: %.3fmm" % hmm if hmm else ""
                opts = []
                if bfnt:
                    opts.append("font: %s" % q(bfnt.replace("_", " ")))
                opts.append("size: %.2fpt" % fsize)
                opts.append("weight: %s" % q(weight))
                opts.append("fill: %s" % colv)
                layers.append("%s[#block(width: %.3fmm%s, radius: %.3fmm, inset: %.3fmm, "
                              "fill: %s.transparentize(%.1f%%))[#set par(leading: %.2fem)%s"
                              "#text(%s)[#align(%s)[%s]]]]"
                              % (base, wmm, hp, rad, pad, fillc, alpha, lh, NL,
                                 ", ".join(opts), align, esc(content)))

            elif kind == "dot":
                rad = _mm(size, 2.0)
                colv = _col(content, "8FA3BD")
                alpha = _f(_kv(extra, "alpha"), 100.0)
                layers.append("%s[#circle(radius: %.3fmm, fill: %s.transparentize(%.1f%%))]"
                              % (base, rad, colv, 100.0 - alpha))

            elif kind in ("ring", "circle-line"):
                rad = _mm(size, 3.0)
                colv = _col(content, "8B8070")
                wid = _f(_kv(extra, "w"), 0.8)
                layers.append("%s[#circle(radius: %.3fmm, stroke: %.2fpt + %s, fill: none)]"
                              % (base, rad, wid, colv))

            elif kind == "line":
                xy2 = _xy(size)
                if not xy2:
                    WARNINGS.append("collage line 需要第二点")
                    continue
                x2, y2 = xy2
                colv = _col(content, "C9D6E5")
                wid = _f(_kv(extra, "w"), 0.5)
                alpha = _f(_kv(extra, "alpha"), 100.0)
                layers.append("%s[#line(start: (0mm, 0mm), end: (%.3fmm, %.3fmm), "
                              "stroke: %.2fpt + %s.transparentize(%.1f%%))]"
                              % (base, x2 - px, y2 - py, wid, colv, 100.0 - alpha))

            elif kind in ("curve", "arc", "orn", "flourish"):
                wmm, hmm = _sz(size, 30.0, 10.0)
                cn = (_kv(extra, "color") or "8B8070").lstrip("#")
                wid = _f(_kv(extra, "w"), 1.0)
                if kind in ("orn", "flourish"):
                    H = hmm * 3.0
                    m = H / 2.0
                    dn = ("M0,%.1f C%.1f,%.1f %.1f,%.1f %.1f,%.1f "
                          "S%.1f,%.1f %.1f,%.1f") % (
                        m, wmm * 0.54, m - H * 0.42, wmm * 1.08, m - H * 0.42,
                        wmm * 1.5, m, wmm * 1.92, m + H * 0.42, wmm * 2.46, m + H * 0.42)
                else:
                    dn = content.strip()
                if not dn:
                    continue
                try:
                    import fxgen
                    svg = fxgen.curve_ornament(int(wmm * 3), int(hmm * 3), dn, cn, float(wid))
                    pth = self._write_tmp(svg, ".svg")
                    if pth:
                        layers.append("%s[#image(%s, width: %.3fmm)]" % (base, q(pth), wmm))
                except Exception as e:
                    WARNINGS.append("collage %s 失败：%s" % (kind, str(e)[:40]))

            elif kind in ("vtext", "vertical"):
                # ★ 用 basho 的 tate 做真正连续竖排，不要再逐字 linebreak。
                # 旧实现把每个字符单独换行：① 英文被拆成单字母 ② 标点错位 ③ 超长部分掉出画布
                wmm, hmm = _sz(size, 20.0, 60.0)
                fsize = _f(_kv(extra, "size"), 10.0)
                gap = _f(_kv(extra, "gap"), 3.0)
                # 没写 color 就按画布底色自动选；写了就查对比度
                _craw2 = _kv(extra, "color")
                _canvas = bgc if bgc else (CTX.get("canvas_bg") or "FFFFFF")
                if _craw2 is None:
                    colv = _auto_fg(_canvas)
                else:
                    colv = _col(_craw2, "1A1A1A")
                    _f2 = _contrast_warn("text", _craw2.lstrip("#"), _canvas)
                    if _f2 != ("#" + _craw2.lstrip("#")):
                        colv = _f2
                vfnt = _kv(extra, "font")
                vcols = int(_f(_kv(extra, "cols"), 1) or 1)
                vcols = max(1, min(8, vcols))
                opts = []
                if vfnt:
                    opts.append("font: %s" % q(vfnt.replace("_", " ")))
                opts.append("size: %.2fpt" % fsize)
                opts.append("fill: %s" % colv)
                # ★ tate 的内容不能套 #text(...)，实测那样会退化成横排。
                # 正确：用 #set text(...) 设样式 + #tate(...)[纯文本]。
                layers.append("%s[#block(width: %.3fmm, height: %.3fmm, clip: true)"
                               "[#set text(%s)%s"
                               "#tate(config: (layout: (columns: %d, gap: %.2fpt, column-gap: %.2fem)))"
                               "[%s]]]"
                               % (base, wmm, hmm, ", ".join(opts), NL,
                                  vcols, gap, 2.0, esc(content.strip())))
            else:
                WARNINGS.append("collage 不认识图层「%s」" % kind)

        if not layers:
            return ""
        ws = ("%.3fmm" % cw) if cw else "100%"
        hs = ("%.3fmm" % ch) if ch else "100%"
        _body = (NL + "  ").join(layers)
        # 超出版心时：外层 block 用缩后尺寸占位，内容用 #scale 等比缩。
        # 不能只缩 cw/ch 不缩图层——那样元素会挤在左上角。
        if _scaled and _sc > 0:
            # scale 需要原始尺寸的容器，否则百分比全部错位
            _raw_w = cw / _sc
            _raw_h = ch / _sc
            _inner = ("#block(width: %.3fmm, height: %.3fmm%s)[%s%s%s]"
                      % (_raw_w, _raw_h,
                         (", fill: %s" % _col(bgc)) if bgc else "", NL,
                         _body, NL))
            return ("#block(width: %s, height: %s, clip: true)[#scale(x: %.6f%%, y: %.6f%%, "
                    "origin: top + left)[%s]]"
                    % (ws, hs, _sc * 100.0, _sc * 100.0, _inner))
        return ("#block(width: %s, height: %s%s, clip: true)[%s%s%s]"
                % (ws, hs, (", fill: %s" % _col(bgc)) if bgc else "", NL,
                   _body, NL))

    def _invoice(self, blocks, cls, kvs=None):
        """发票明细。每行：品名|数量|单价|小计（小计可省，自动算）"""
        kvs = kvs or {}
        rows = self._rows_of(blocks)
        if not rows:
            WARNINGS.append("invoice 没有数据行")
            return ""
        items = []
        for r in rows:
            if len(r) < 3:
                WARNINGS.append("invoice 需要「品名|数量|单价」，这一行跳过：%s" % r[0])
                continue
            nm = r[0]
            try:
                qty = float(r[1])
                price = float(r[2])
            except Exception:
                WARNINGS.append("invoice 的数量/单价不是数字，这一行跳过：%s" % nm)
                continue
            items.append("(%s, %g, %g)" % (q(nm), qty, price))
        if not items:
            return ""
        cur = kvs.get("currency") or "¥"
        return "#invoice-table((%s,), currency: %s)" % (", ".join(items), q(cur))

    def _cert(self, blocks):
        """证书。每行 键|值，键支持 name/title/body/org/date/serial"""
        rows = self._rows_of(blocks)
        kv = {}
        for r in rows:
            if len(r) >= 2:
                kv[r[0].lower()] = r[1]
            elif len(r) == 1:
                kv.setdefault("body", r[0])
        if not kv:
            WARNINGS.append("cert 没有数据。写法：name|张三 或 title|优秀员工")
            return ""
        opts = []
        for k in ("name", "title", "body", "org", "date", "serial"):
            if k in kv:
                opts.append("%s: [%s]" % (k, esc(kv[k])))
        if "body" not in kv:
            WARNINGS.append("cert 没写正文（body），证书会是空的")
        return "#cert-sheet(%s)" % ", ".join(opts)

    def _resume(self, blocks):
        """简历时间线。每行：时间|标题|描述（描述可省）"""
        rows = self._rows_of(blocks)
        items = []
        for r in rows:
            if len(r) < 2:
                WARNINGS.append("resume 需要「时间|标题」，这一行跳过")
                continue
            when = r[0]
            what = r[1]
            desc = r[2] if len(r) > 2 else ""
            items.append("([%s], [%s], [%s])" % (esc(when), esc(what), esc(desc)))
        if not items:
            WARNINGS.append("resume 没有数据行")
            return ""
        return "#resume-timeline((%s,))" % ", ".join(items)

    def _skills(self, blocks):
        """技能标签。每行一个标签，或用 | 分隔多个"""
        tags = []
        for r in self._rows_of(blocks):
            for t in r:
                if t:
                    tags.append(t)
        if not tags:
            WARNINGS.append("skills 没有标签")
            return ""
        return "#skill-tags((%s,))" % ", ".join(q(t) for t in tags)

    def _menu(self, blocks):
        """菜单。每行：菜品|价格|备注（备注可省）"""
        items = []
        for r in self._rows_of(blocks):
            if len(r) < 2:
                WARNINGS.append("menu 需要「菜品|价格」，这一行跳过")
                continue
            nm = r[0]
            pr = r[1]
            note = r[2] if len(r) > 2 else ""
            items.append("([%s], [%s], [%s])" % (esc(nm), esc(pr), esc(note)))
        if not items:
            WARNINGS.append("menu 没有数据行")
            return ""
        return "#menu-list((%s,))" % ", ".join(items)

    def _poster(self, blocks):
        """海报主视觉。每行 键|值，键支持 hero/sub/when/where/note"""
        kv = {}
        for r in self._rows_of(blocks):
            if len(r) >= 2:
                kv[r[0].lower()] = r[1]
            elif len(r) == 1:
                kv.setdefault("hero", r[0])
        if not kv:
            WARNINGS.append("poster 没有数据。写法：hero|活动名称")
            return ""
        opts = []
        for k in ("hero", "sub", "when", "where", "note"):
            if k in kv:
                opts.append("%s: [%s]" % (k, esc(kv[k])))
        return "#poster(%s)" % ", ".join(opts)
    def _slide(self, name, cls, kvs, inner):
        """幻灯片版式。数据行用 | 分隔字段。"""
        rows = []
        for k, payload, _lv in self._lines(inner or []):
            if k != "line":
                continue
            txt = self._text(payload).strip()
            if txt:
                rows.append(txt)
        # 头部同行文字：`::: slide-cover 标题|副标题` 这种写法里，pandoc 会把
        # 同行文字塞进 data-* 属性而不是 inner，只读 rows 会得到全空。
        # 整行作为一个 row 补进去，由下面的 cell() 按 | 拆字段（不能在这里先拆，
        # 否则 cover/stats/cols 会各自只拿到第一段，实测字段全错位）。
        _head = self._head_text(cls, kvs, skip=1)
        if _head and not rows and str(_head).strip():
            rows = [str(_head).strip()]

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
            # 头部同行文字 = 左栏第一段（pandoc 不把同行文字放进 inner）。
            # 实测 `::: slide-split 左栏 --- 右栏` 之前左栏整个消失。
            _h = self._head_text(cls, kvs, skip=1)
            _head_txt = str(_h).strip() if _h else ""
            if len(groups) < 2:
                WARNINGS.append("slide-split 需要两栏内容，用一行 --- 分隔；当前只有 1 栏")
                groups = [cur, []]
            parts = []
            for _gi, g in enumerate(groups[:2]):
                r = R()
                r.render(g)
                _seg = r.out().strip()
                if _gi == 0 and _head_txt:
                    # 直接把转义后的裸文本拼在最前面，不再套 []：
                    # 外面已经是 "#slide-split(([%s], ...))" 的方括号，套了会成 [[...]]
                    _seg = "%s%s%s" % (esc(_head_txt), chr(10) * 2 if _seg else "", _seg)
                parts.append(_seg)
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
        _EMPTY_OK = ("pagebreak", "toc", "no-break", "nobreak",
                     "fx", "effect", "noise", "wave")
        # 头部带同行文字的组件（::: capsule 标题 / ::: qrcode 网址）不算空块
        _has_head = bool(self._head_text(cls, kvs, skip=1))
        if (name and name not in _EMPTY_OK and not _has_head and not any(
                k == "line" for k, _p, _l in self._lines(inner or []))):
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
            self.o.append(self._numbered(inner, name, cls, kvs) + "\n\n")
        elif name in ("collage", "layout", "poster-canvas"):
            self.o.append(self._collage(inner, cls, kvs) + chr(10) * 2)
        elif name in ("wrapimg", "wrapimage", "wrapimg2"):
            self.o.append(self._wrapimg(inner, cls, kvs) + "\n\n")
        elif name in ("wrap", "circlewrap"):
            self.o.append(self._wrap(inner, cls, kvs) + "\n\n")
        elif name in ("vertical", "tate") or (
                name.startswith("vertical") and name[8:].isdigit()):
            _n = name[8:] if name.startswith("vertical") and name[8:].isdigit() else ""
            self.o.append(self._vertical(inner, cls, kvs, n=_n) + "\n\n")
        elif name == "ring":
            self.o.append(self._rings(inner, cls, kvs) + "\n\n")
        elif name == "chart":
            self.o.append(self._chart(inner, cls, kvs) + "\n\n")
        elif name == "timeline":
            self.o.append(self._timeline(inner, cls, kvs) + "\n\n")
        elif name == "steps":
            self.o.append(self._steps(inner) + "\n\n")
        elif name == "defs":
            self.o.append(self._defs(inner) + "\n\n")
        elif name == "pagebreak":
            self.o.append("#pagebreak()\n\n")
        elif name == "toc":
            self.o.append("#sectiontoc()\n\n")
        elif name in ("invoice", "bill"):
            self.o.append(self._invoice(inner, cls, kvs) + chr(10) * 2)
        elif name in ("cert", "certificate"):
            self.o.append(self._cert(inner) + chr(10) * 2)
        elif name in ("resume", "timeline-cv", "cv"):
            self.o.append(self._resume(inner) + chr(10) * 2)
        elif name in ("menu", "menu-list"):
            self.o.append(self._menu(inner) + chr(10) * 2)
        elif name in ("skills", "skill-tags"):
            self.o.append(self._skills(inner) + chr(10) * 2)
        elif name in ("poster", "hero"):
            self.o.append(self._poster(inner) + chr(10) * 2)
        elif name in ("fx", "effect"):
            self.o.append(self._fx(inner, cls, kvs) + chr(10) * 2)
        elif name in ("curve", "ornament"):
            self.o.append(self._curve(inner, cls, kvs) + chr(10) * 2)
        elif name in ("capsule", "pill"):
            body = " ".join(self.ins(pl) for k, pl, _ in self._lines(inner or []) if k == "line")
            if not body.strip():
                # 支持 ::: capsule 标题文字（同行写法，pandoc 会放进 data-title）
                body = esc(self._head_text(cls, kvs, skip=1))
            tone = kvs.get("tone") or kvs.get("data-tone") or "primary"
            solid = kvs.get("solid") or kvs.get("data-solid")
            sb = "false" if (solid is not None and str(solid).lower() in ("false", "0", "no")) else "true"
            sz = kvs.get("size") or "12pt"
            self.o.append("#capsule([%s], tone: %s, solid: %s, size: %s)" % (body, q(tone), sb, sz) + chr(10) * 2)
        elif name == "qrcode":
            self.o.append(self._qrcode(inner, cls, kvs) + chr(10) * 2)
        elif name in ("price", "pricing"):
            self.o.append(self._price(inner) + chr(10) * 2)
        elif name in ("faq", "qa"):
            self.o.append(self._faq(inner) + chr(10) * 2)
        elif name in ("team", "people"):
            self.o.append(self._team(inner, cls, kvs) + chr(10) * 2)
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

    def _numbered(self, blocks, fn, cls=None, kvs=None):
        items = []
        if not [1 for k2, p2, _l2 in self._lines(blocks or []) if k2 == "line" and self._text(p2).strip()]:
            _h = self._head_text(cls, kvs, skip=1)
            if _h and str(_h).strip():
                # 同行写法：pandoc 把数据放进 data-* 而非 inner，不兑底组件会消失
                # 构造一个 pandoc Plain 节点，供 _lines 正常消费
                blocks = [{"t": "Plain", "c": [{"t": "Str", "c": str(_h).strip()}]}]
        for kind, payload, _lv in self._lines(blocks):
            if kind != "line":
                continue
            parts = self._split_pipe(payload)
            label = self.ins(parts[0]) if parts else ""
            raw = self._text(parts[1]) if len(parts) > 1 else "0"
            items.append("#%s([%s], %s)" % (fn, label, num(raw)))
        return "\n".join(items)

    def _rings(self, blocks, cls=None, kvs=None, per_row=3):
        items = []
        if not [1 for k2, p2, _l2 in self._lines(blocks or []) if k2 == "line" and self._text(p2).strip()]:
            _h = self._head_text(cls, kvs, skip=1)
            if _h and str(_h).strip():
                # 同行写法：pandoc 把数据放进 data-* 而非 inner，不兑底组件会消失
                # 构造一个 pandoc Plain 节点，供 _lines 正常消费
                blocks = [{"t": "Plain", "c": [{"t": "Str", "c": str(_h).strip()}]}]
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
    def _chart(self, blocks, cls=None, kvs=None):
        items = []
        if not [1 for k2, p2, _l2 in self._lines(blocks or []) if k2 == "line" and self._text(p2).strip()]:
            _h = self._head_text(cls, kvs, skip=1)
            if _h and str(_h).strip():
                # 同行写法：pandoc 把数据放进 data-* 而非 inner，不兑底组件会消失
                # 构造一个 pandoc Plain 节点，供 _lines 正常消费
                blocks = [{"t": "Plain", "c": [{"t": "Str", "c": str(_h).strip()}]}]
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

    def _timeline(self, blocks, cls=None, kvs=None):
        items = []
        if not [1 for k2, p2, _l2 in self._lines(blocks or []) if k2 == "line" and self._text(p2).strip()]:
            _h = self._head_text(cls, kvs, skip=1)
            if _h and str(_h).strip():
                # 同行写法：pandoc 把数据放进 data-* 而非 inner，不兑底组件会消失
                # 构造一个 pandoc Plain 节点，供 _lines 正常消费
                blocks = [{"t": "Plain", "c": [{"t": "Str", "c": str(_h).strip()}]}]
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
        # 样式参数：style / radius / tone
        _st = str(kvs.get("style") or kvs.get("data-style") or "flat").lower()
        if _st not in ("flat", "shadow", "glass", "gradient", "outline", "none"):
            WARNINGS.append("cards 的 style 写了 %s，只支持 flat/shadow/glass/gradient/outline，已按 flat" % _st)
            _st = "flat"
        _rad = str(kvs.get("radius") or kvs.get("data-radius") or "4")
        _tone = str(kvs.get("tone") or kvs.get("data-tone") or "primary").lower()
        # radius-of() 里 "pill" 是合法取值（→999pt），但必须带引号传：
        # 输出成 rad: pill 时 Typst 当变量名解析，报 unknown variable: pill。
        if _rad.isdigit() or _rad in ("pill", "0", "4", "8"):
            _rad_out = _rad if _rad.isdigit() else q(_rad)
        else:
            WARNINGS.append("cards 的 radius 写了 %s，只支持 0/4/8/pill，已按 4" % _rad)
            _rad_out = "4"
        extra = ", style: %s, rad: %s, tone: %s" % (q(_st), _rad_out, q(_tone))
        # 阴影程度可调：sh-depth=偏移量 sh-spread=右下外扩 sh-tint=阴影色
        if _st == "shadow":
            _sd = kvs.get("sh-depth") or kvs.get("shadow-depth") or kvs.get("depth")
            _ss = kvs.get("sh-spread") or kvs.get("shadow-spread") or kvs.get("spread")
            _stc = kvs.get("sh-tint") or kvs.get("shadow-color") or kvs.get("shade")
            if _sd:
                _v = _len_ok(_sd, 0.5, 12, "sh-depth")
                if _v:
                    extra += ", sh-depth: %s" % _v
            if _ss:
                _v = _len_ok(_ss, 0.0, 8, "sh-spread")
                if _v:
                    extra += ", sh-spread: %s" % _v
            if _stc:
                _hexc = str(_stc).strip().lstrip("#")
                if len(_hexc) == 6 and all(c in "0123456789abcdefABCDEF" for c in _hexc):
                    extra += ", sh-tint: rgb(\"#%s\")" % _hexc.upper()
                elif str(_stc).strip() in ("light", "mid", "dark"):
                    _m = {"light": "luma(232)", "mid": "luma(214)", "dark": "luma(180)"}
                    extra += ", sh-tint: %s" % _m[str(_stc).strip()]
                else:
                    WARNINGS.append("cards 的 shadow 色写了 %s，只支持 6 位十六进制或 light/mid/dark，已用默认"
                                    % _stc)
        return "#cardgrid((\n  %s,\n), cols: %s%s)" % (",\n  ".join(items), cols, extra)

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
            _grad = kvs.get("gradient") or kvs.get("data-gradient")
            if _grad is not None and str(_grad).lower() not in ("false", "0", "no"):
                body = "#grad-text[%s]" % body
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
                    _f = str(_fill).strip()
                    _SEM = ("primary", "success", "warn", "danger", "neutral", "soft")
                    if _f.lower() in _SEM:
                        _opts.append("fill: tone-color(%s)" % q(_f.lower()))
                    else:
                        _hex = _f.lstrip("#")
                        if len(_hex) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in _hex):
                            _opts.append("fill: rgb(%s)" % q(_hex))
                        else:
                            WARNINGS.append("行内 color 写了 %s，既不是语义色也不是 6 位十六进制，已忽略" % _f)
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
