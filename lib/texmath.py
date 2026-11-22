#!/usr/bin/env python3
# -*- coding: utf-8 -*-
BM = chr(92)
DIF_ = "diff"

import re as _re2
_RE_RUN = _re2.compile(r"[A-Za-z]{2,}")

_RE_SUP = _re2.compile(r"\^\{([^{}]*)\}")
_RE_SUB = _re2.compile(r"_\{([^{}]*)\}")

_RE_KEEP = _re2.compile(r"(diff|thin|med|quad|qquad)")

def _split_runs_global(t):
    if not t:
        return t
    out = []
    depth = 0
    i = 0
    n = len(t)
    while i < n:
        ch = t[i]
        if ch == "(":
            depth += 1
            out.append(ch)
            i += 1
            continue
        if ch == ")":
            depth = max(0, depth - 1)
            out.append(ch)
            i += 1
            continue
        if depth > 0:
            out.append(ch)
            i += 1
            continue
        if ch.isascii() and ch.isalpha():
            j = i
            while j < n and t[j].isascii() and t[j].isalpha():
                j += 1
            word = t[i:j]
            if word in ("dif", "thin", "med"):
                out.append(word)
            else:
                out.append(" ".join(word))
            i = j
            continue
        out.append(ch)
        i += 1
    return "".join(out)
_SYMS = ("pi", "alpha", "beta", "gamma", "delta", "theta", "lambda", "mu",
         "sigma", "phi", "psi", "omega", "infinity", "approx", "equiv",
         "sum", "product", "integral", "lim")

def _sep_symbols(t):
    if not t:
        return t
    for sym in _SYMS:
        i = 0
        buf = []
        while True:
            k = t.find(sym, i)
            if k < 0:
                buf.append(t[i:])
                break
            buf.append(t[i:k])
            after = k + len(sym)
            before_ok = (k == 0) or (not t[k - 1].isalpha())
            buf.append(sym)
            if after < len(t) and t[after].isascii() and t[after].isalpha() and before_ok:
                buf.append(" ")
            i = after
        t = "".join(buf)
    return t

_FN = ("sin", "cos", "tan", "cot", "sec", "csc", "log", "ln", "exp", "lim",
       "sum", "product", "integral", "max", "min", "sup", "inf", "det")

def _pre_fn(t):
    """insert space before known function names when glued to a letter"""
    if not t:
        return t
    GUARD = (("delim", chr(2) + "X1X"), ("block", chr(2) + "X2X"), ("cases", chr(2) + "X3X"), ("binom", chr(2) + "X4X"), ("upright", chr(2) + "X5X"), ("bold", chr(2) + "X6X"))
    for gw, rep in GUARD:
        t = t.replace(gw, rep)
    if not t:
        return t
    for f in _FN:
        i = 0
        buf = []
        while True:
            k = t.find(f, i)
            if k < 0:
                buf.append(t[i:])
                break
            buf.append(t[i:k])
            after = k + len(f)
            glued = k > 0 and t[k - 1].isascii() and t[k - 1].isalpha()
            if glued:
                buf.append(" ")
            buf.append(f)
            i = after
        t = "".join(buf)
    return t

def _tight_scripts(t):
    t = t.replace(" _", "_").replace(" ^", "^")
    return t

def _fix_scripts(t):
    for _ in range(4):
        n = t
        t = _RE_SUP.sub(lambda m: "^(" + m.group(1) + ")", t)
        t = _RE_SUB.sub(lambda m: "_(" + m.group(1) + ")", t)
        if t == n:
            break
    return t

def _split_letters(t):
    """AB -> A B so Typst treats them as separate italic variables"""
    if not t:
        return t
    return _RE_RUN.sub(lambda m: " ".join(m.group(0)), t)

def _t(s):
    return s.replace(BM + "left", "").replace(BM + "right", "")

def _brace_end(s, i):
    """s[i] is '{', return (inner, index_after_close)"""
    d = 0
    j = i
    while j < len(s):
        if s[j] == "{":
            d += 1
        elif s[j] == "}":
            d -= 1
            if d == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)

def _read_brace(s, i):
    """skip spaces at i then read {...}; return (inner, next_idx)"""
    while i < len(s) and s[i] == " ":
        i += 1
    if i < len(s) and s[i] == "{":
        return _brace_end(s, i)
    if i < len(s):
        return s[i], i + 1
    return "", i

def _read_opt(s, i):
    """read optional [...]; return (inner or None, next_idx)"""
    while i < len(s) and s[i] == " ":
        i += 1
    if i < len(s) and s[i] == "[":
        d = 0
        j = i
        while j < len(s):
            if s[j] == "[":
                d += 1
            elif s[j] == "]":
                d -= 1
                if d == 0:
                    return s[i + 1:j], j + 1
            j += 1
        return s[i + 1:], len(s)
    return None, i

WRAP = {
    "frac": (2, None, "frac(%s, %s)"),
    "dfrac": (2, None, "frac(%s, %s)"),
    "tfrac": (2, None, "frac(%s, %s)"),
    "binom": (2, None, "binom(%s, %s)"),
    "sqrt": (1, 2, "sqrt(%s)"),
    "text": (1, None, "\"%s\""),
    "mathrm": (1, None, "upright(%s)"),
    "operatorname": (1, None, "op(%s)"),
    "mathbf": (1, None, "bold(%s)"),
    "mathit": (1, None, "italic(%s)"),
    "mathbb": (1, None, "bb(%s)"),
    "mathcal": (1, None, "cal(%s)"),
    "hat": (1, None, "hat(%s)"),
    "widehat": (1, None, "hat(%s)"),
    "bar": (1, None, "overline(%s)"),
    "overline": (1, None, "overline(%s)"),
    "vec": (1, None, "arrow(%s)"),
    "dot": (1, None, "dot(%s)"),
    "ddot": (1, None, "dot.double(%s)"),
    "underline": (1, None, "underline(%s)"),
}

GREEK = ["alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi", "pi", "rho", "sigma", "tau", "upsilon", "phi", "varphi", "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi", "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega"]

OPS = {
    "sum": "sum", "prod": "product", "int": "integral", "iint": "integral.double",
    "oint": "integral.cont", "lim": "lim", "sin": "sin", "cos": "cos", "tan": "tan",
    "log": "log", "ln": "ln", "exp": "exp", "max": "max", "min": "min",
    "inf": "infinity", "partial": "diff", "nabla": "nabla", "infty": "infinity",
    "to": "arrow.r", "rightarrow": "arrow.r", "Rightarrow": "arrow.r.double",
    "Leftrightarrow": "arrow.l.r.double", "le": "lt.eq", "leq": "lt.eq",
    "ge": "gt.eq", "geq": "gt.eq", "ne": "eq.not", "neq": "eq.not",
    "approx": "approx", "equiv": "equiv", "times": "times", "cdot": "dot.op",
    "pm": "plus.minus", "div": "div", "cup": "union", "cap": "sect",
    "in": "in", "notin": "in.not", "subset": "subset", "subseteq": "subset.eq",
    "supset": "supset", "forall": "forall", "exists": "exists", "emptyset": "emptyset",
    "angle": "angle", "perp": "perp", "parallel": "parallel", "sim": "tilde.op",
    "circ": "circle.stroked", "degree": "degree", "because": "because",
    "therefore": "therefore", "ldots": "dots.h", "cdots": "dots.h.c", "dots": "dots.h",
    "quad": "#h(1em)", "qquad": "#h(2em)",
}

DROP = ["displaystyle", "textstyle", "limits", "nolimits", "big", "Big", "bigg", "Bigg",
        "bigl", "bigr", "Bigl", "Bigr", "biggl", "biggr", "biggl", "biggr",
        "left", "right", "!", ",", ";", ":", ">", " "]

def _name_at(s, i):
    """s[i] is backslash? assume caller passed after backslash"""
    j = i
    while j < len(s) and s[j].isalpha():
        j += 1
    return s[i:j], j

def convert(s):
    if s is None:
        return ""
    s = _t(s)
    s = s.replace(BM + "mathrm{d} ", "dif ")
    s = s.replace(BM + "mathrm{d}", "dif ")
    out = []
    i = 0
    while i < len(s):
        ch = s[i]
        if ch != BM:
            if ch.isascii() and ch.isalpha():
                j = i
                while j < len(s) and s[j].isascii() and s[j].isalpha():
                    j += 1
                word = s[i:j]
                if word in ("dif", "thin", "med", "and", "or", "not", "in"):
                    out.append(word)
                elif len(word) > 1:
                    out.append(" ".join(word))
                else:
                    out.append(word)
                i = j
                continue
            out.append(ch)
            i += 1
            continue
        name, j = _name_at(s, i + 1)
        if not name:
            if j < len(s):
                nxt = s[j]
                rep = {",": "thin", ";": "med", ":": "med", "!": "", " ": " ", "{": "", "}": "", "%": ""}
                out.append(" " + rep.get(nxt, nxt) + " " if rep.get(nxt, nxt) else "")
                i = j + 1
            else:
                i = j
            continue
        if name in DROP:
            i = j
            continue
        if name in WRAP:
            cnt, optmax, tpl = WRAP[name]
            args = []
            k = j
            if optmax is not None:
                o, k2 = _read_opt(s, k)
                if o is not None:
                    args.append(o)
                    k = k2
            need = cnt
            got = 0
            while got < need:
                a, k2 = _read_brace(s, k)
                args.append(a)
                got += 1
                k = k2
            if name == "text":
                out.append("\"" + args[0] + "\"")
            elif name == "sqrt" and len(args) > 1:
                out.append("root(%s, %s)" % (convert(args[0]), convert(args[1])))
            elif name == "binom":
                out.append("binom(%s, %s)" % (convert(args[0]), convert(args[1])))
            else:
                if name in ("overline", "hat", "widehat", "bar", "vec", "dot", "ddot", "underline"):
                    out.append(tpl % _split_letters(convert(args[0])))
                else:
                    out.append(tpl % tuple(convert(a) for a in args))
            i = k
            continue
        if name == "begin":
            env, k = _read_brace(s, j)
            endm = "end{" + env + "}"
            epos = s.find(BM + endm, k)
            body = s[k:epos] if epos >= 0 else s[k:]
            out.append(" " + _matrix(env, body) + " ")
            i = epos + len(BM + endm) if epos >= 0 else len(s)
            continue
        if name in GREEK:
            out.append(name + " ")
            i = j
            continue
        if name in OPS:
            out.append(OPS[name] + " ")
            i = j
            continue
        out.append(name)
        i = j
    res = _fix_scripts("".join(out))
    res = _pre_fn(res)
    res = res.replace(chr(2) + "X1X", "delim").replace(chr(2) + "X2X", "block").replace(chr(2) + "X3X", "cases").replace(chr(2) + "X4X", "binom").replace(chr(2) + "X5X", "upright").replace(chr(2) + "X6X", "bold")
    res = _sep_symbols(res)
    return _tight_scripts(res)

def _matrix(env, body):
    rows = body.split(BM + BM)
    cells = []
    for r in rows:
        parts = r.split("&")
        cells.append(", ".join(convert(p).strip() for p in parts))
    delim = 'none'
    if 'pmatrix' in env:
        delim = '"("'
    elif 'bmatrix' in env:
        delim = '"["'
    elif 'vmatrix' in env:
        delim = '"|"'
    elif 'Bmatrix' in env:
        delim = '"{"'
    if 'matrix' in env or 'smallmatrix' in env:
        if delim == 'none':
            return "mat(%s)" % ("; ".join(cells))
        return "mat(delim: %s, %s)" % (delim, "; ".join(cells))
    if 'cases' in env:
        return "cases(%s)" % (", ".join(cells))
    if 'align' in env or 'gather' in env or 'eqnarray' in env:
        return " ".join(cells)
    return " ".join(cells)
