#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ai_pdf backend (Typst engine)
import sys, os, json, subprocess, tempfile, shutil, re, traceback

HERE = os.path.dirname(os.path.abspath(__file__))
THEME = os.path.join(HERE, 'theme2.typ')

PALETTES = {
    'blue': ('#2F5BEA', '#7C6BF5', '#EEF3FF', '#F6F8FF', '#1A1A1A', '#E4EAF8'),
    'ink': ('#1F2933', '#52606D', '#F0F2F5', '#F8F9FA', '#111827', '#DDE3EA'),
    'forest': ('#1F7A5A', '#3FA983', '#EAF7F1', '#F5FBF8', '#14251E', '#D5EAE0'),
    'clay': ('#B5552B', '#E08A5C', '#FDF0E8', '#FFF9F5', '#2A1A13', '#F2DDD0'),
    'plum': ('#6B3FA0', '#9B6BD6', '#F3ECFB', '#FAF7FE', '#1F1729', '#E3D5F2'),
    'gold': ('#9C7A2E', '#C9A754', '#FAF4E4', '#FDFAF0', '#241E10', '#EDE0C0'),
}

THEMES = {
    'report': dict(bf='Noto Serif CJK SC', hf='Noto Sans CJK SC', margin='22mm20mm', size='11pt', leading='0.72em', h1='19pt', h2='14pt', h3='12pt', h4='11pt', h1fill='true', h1bar='true'),
    'handout': dict(bf='Noto Sans CJK SC', hf='Noto Sans CJK SC', margin='18mm16mm', size='10.5pt', leading='0.68em', h1='18pt', h2='13.5pt', h3='11.5pt', h4='10.5pt', h1fill='true', h1bar='true'),
    'resume': dict(bf='Noto Sans CJK SC', hf='Noto Sans CJK SC', margin='16mm18mm', size='10pt', leading='0.66em', h1='17pt', h2='13pt', h3='11pt', h4='10pt', h1fill='false', h1bar='true'),
    'editorial': dict(bf='Noto Serif CJK SC', hf='LXGW WenKai', margin='24mm22mm', size='11pt', leading='0.80em', h1='20pt', h2='15pt', h3='12.5pt', h4='11pt', h1fill='false', h1bar='true'),
    'minimal': dict(bf='Noto Sans CJK SC', hf='Noto Sans CJK SC', margin='25mm24mm', size='10.5pt', leading='0.70em', h1='18pt', h2='13.5pt', h3='11.5pt', h4='10.5pt', h1fill='false', h1bar='false'),
    'certificate': dict(bf='LXGW WenKai', hf='LXGW WenKai', margin='45mm32mm', size='13pt', leading='0.95em', h1='30pt', h2='18pt', h3='14pt', h4='12pt', h1fill='false', h1bar='false'),
    'slide': dict(bf='Noto Sans CJK SC', hf='Noto Sans CJK SC', margin='15mm', size='13pt', leading='0.74em', h1='20pt', h2='14pt', h3='12pt', h4='11pt', h1fill='false', h1bar='false'),
}

PKG_DIR = os.path.join(HERE, 'typst-packages')
if not os.path.isdir(PKG_DIR):
    PKG_DIR = '/sdcard/Download/.ai_pdf_runtime/typst-packages'

FONT_DIRS = ['/sdcard/Download/Operit/projects/ai-pdf/fonts', '/sdcard/Download/ai_pdf_fonts', os.path.join(HERE, 'fonts')]

PAPER = {'a4': 'a4', 'a5': 'a5', 'letter': 'us-letter', 'a3': 'a3', 'b5': 'b5',
         '16-9': 'presentation-16-9', '169': 'presentation-16-9',
         '4-3': 'presentation-4-3', '43': 'presentation-4-3'}


def out(**kw):
    kw.setdefault('success', True)
    sys.stdout.write(json.dumps(kw, ensure_ascii=False) + chr(10))
    sys.exit(0)


def classify(msg):
    m = str(msg)
    pairs = [
        ('maximum function call depth', 'internal_recursion', '主题内部函数递归（工具bug），请把原文反馈给维护者'),
        ('unknown variable', 'undefined_symbol', '组件名或 Typst函数不存在；检查 extra_typst里的函数名，或组件名拼写'),
        ('invalid number suffix', 'bad_unit', '单位写错：边距用 mm，字号用 pt，行距用 em（如22mm /11pt /0.72em）'),
        ('unexpected argument', 'bad_argument', '参数不被接受；多半是 extra_typst给了不支持的键，删掉改用组件语法'),
        ('unclosed delimiter', 'syntax', 'Typst语法错误；优先删除 extra_typst'),
        ('expected', 'syntax', 'Typst语法错误；优先删除 extra_typst'),
        ('not found', 'missing_resource', '文件或字体找不到；图片用绝对路径，字体用 Noto Serif CJK SC'),
        ('pandoc', 'markdown', 'Markdown解析失败；检查是否有未闭合的 :::或代码块'),
        ('typst binary', 'engine', '引擎未就绪；先跑 pdf_selfcheck'),
    ]
    for k, t, h in pairs:
        if k in m:
         return (t, h)
    return ('unknown', '看 error原文定位；若与 extra_typst有关，先删掉重试')


def err(msg, **kw):
    t, h = classify(msg)
    kw.update({'success': False, 'error': str(msg),
        'error_type': t, 'hint': h})
    sys.stdout.write(json.dumps(kw, ensure_ascii=False) + chr(10))
    sys.exit(0)


def tq(s):
    return '"' + str(s).replace(chr(92), chr(92) *2).replace('"', chr(92) + '"') + '"'


def unit(v, du='mm'):
    v = str(v).strip()
    if not v:
        return '0mm'
    if re.match(r'^-?[0-9]+(\.[0-9]+)?$', v):
        return v + du
    return v


def margin_typst(spec):
    parts = re.findall(r'[0-9]+(?:\.[0-9]+)?(?:mm|cm|in|pt|em|%)', str(spec)) or [unit(spec)]
    if not parts:
        return '(x:20mm, y:22mm)'
    if len(parts) ==1:
        return parts[0]
    if len(parts) ==2:
        return '(top: %s, right: %s, bottom: %s, left: %s)' % (parts[0], parts[1], parts[0], parts[1])
    if len(parts) ==3:
        return '(top: %s, right: %s, bottom: %s, left: %s)' % (parts[0], parts[1], parts[2], parts[1])
    return '(top: %s, right: %s, bottom: %s, left: %s)' % (parts[0], parts[1], parts[2], parts[3])


def font_paths(a):
    dirs = []
    ex = a.get('font_dir')
    if ex:
        _miss = []
        for d in str(ex).split(os.pathsep):
            d = d.strip()
            if not d:
                continue
            if os.path.isdir(d):
                dirs.append(d)
            else:
                _miss.append(d)
        # 之前直接把不存在的目录丢掉，用户写错 font_dir 永远发现不了
        if _miss:
            PARAM_WARN.append('font_dir 里这些目录不存在，已忽略：%s'
                              % '、'.join(_miss[:4]))
    for d in FONT_DIRS:
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)
    return dirs

def find_typst():
    for c in ['/root/bin/typst', '/usr/local/bin/typst', '/usr/bin/typst', os.path.join(HERE, 'typst')]:
        if os.path.exists(c) and os.access(c, os.X_OK):
            return c
    return shutil.which('typst')


def get_typst():
    t = find_typst()
    if not t:
        err('typst binary not found; expected /root/bin/typst')
    return t


PAGE_WARN = []


def parse_pages(spec, total):
    if spec is None:
        return list(range(total))
    spec = str(spec).strip()
    if spec in ('', '-', 'all', '*'):
        return list(range(total))
    got = []
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        try:
            if '-' in part:
                a, b = part.split('-', 1)
                a = int(a) if a.strip() else 1
                b = int(b) if b.strip() else total
                got.extend(range(a, b + 1))
            else:
                got.append(int(part))
        except ValueError:
            err('页码写法看不懂：%r。要写成 1 / 1-3 / 1,4 / all' % part)
            return []
    seen = []
    bad = []
    for p in got:
        if 1 <= p <= total:
            if p not in seen:
                seen.append(p)
        else:
            bad.append(p)
    if bad:
        PAGE_WARN.append('页码 %s 超出范围（共 %d 页），已跳过'
                         % ('/'.join(str(x) for x in bad[:6]), total))
    return [p -1 for p in sorted(seen)]


def get_fitz():
    try:
        import pymupdf as f
        return f
    except Exception:
        pass
    try:
        import fitz as f
        return f
    except Exception as e:
        err('PyMuPDF unavailable: %s' % e)


def esc_typ(s):
    s = str(s)
    for ch, rep in (('#', chr(92) + '#'), ('$', chr(92) + '$'), ('*', chr(92) + '*'), ('_', chr(92) + '_'), ('`', chr(92) + '`'), ('<', chr(92) + '<'), ('>', chr(92) + '>'), ('@', chr(92) + '@')):
        s = s.replace(ch, rep)
    return s


CFG_TPL = ('#let cfg = (' + chr(10) + ' accent: rgb("%s"),' + chr(10) + ' accent2: rgb("%s"),' + chr(10) + ' soft: rgb("%s"),' + chr(10) + ' soft2: rgb("%s"),' + chr(10) + ' ink: rgb("%s"),' + chr(10) + ' line: rgb("%s"),' + chr(10) + ' body-font: %s,' + chr(10) + ' head-font: %s,' + chr(10) + ' mono-font: "Noto Sans Mono CJK SC",' + chr(10) + ' base-size: %s,' + chr(10) + ' leading: %s,' + chr(10) + ' paper: %s,' + chr(10) + ' margin: %s,' + chr(10) + ' page-numbers: %s,' + chr(10) + ' header-text: %s,' + chr(10) + ' watermark: %s,' + chr(10) + ' h1-size: %s,' + chr(10) + ' h2-size: %s,' + chr(10) + ' h3-size: %s,' + chr(10) + ' h4-size: %s,' + chr(10) + ' h1-fill: %s,' + chr(10) + ' h1-bar: %s,' + chr(10) + ' slide: %s,' + chr(10) + ')' + chr(10) *2)


PARAM_WARN = []


_FONT_CACHE = None


def known_fonts(a):
    """用 typst fonts 拿真实可用字体（就是实际渲染用的那个二进制）。"""
    global _FONT_CACHE
    if _FONT_CACHE is not None:
        return _FONT_CACHE
    names = set()
    try:
        typst = find_typst()
        if typst:
            # typst fonts 不支持 --package-path（传了会直接报错退出、返回空集）
            cmd = [typst, "fonts"]
            for fd in font_paths(a):
                cmd.extend(["--font-path", fd])
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if r.returncode == 0:
                for ln in r.stdout.splitlines():
                    ln = ln.strip()
                    if ln:
                        names.add(ln)
    except Exception:
        pass
    _FONT_CACHE = names
    return names


def check_font(a, key):
    val = a.get(key)
    if not val:
        return
    pool = known_fonts(a)
    if not pool:
        return
    if str(val) not in pool:
        key4 = str(val).lower()[:4]
        near = [x for x in pool if key4 in x.lower()][:4]
        tip = ("，你是不是要：%s" % " / ".join(near)) if near else ""
        PARAM_WARN.append(
            "%s 写了 %s，字体库里没有（Typst 会静默回落到默认字体，不报错）%s"
            % (key, val, tip))

def pick_theme(a):
    theme = (a.get('theme') or 'report').lower()
    if theme and theme not in THEMES:
        PARAM_WARN.append("theme 写了 %s，不存在，已用 report。可选：%s"
                          % (theme, "/".join(sorted(THEMES))))
        return 'report'
    return theme


def pick_palette(a):
    pal = (a.get('palette') or 'blue').lower()
    if pal and pal not in PALETTES:
        PARAM_WARN.append("palette 写了 %s，不存在，已用 blue。可选：%s"
                          % (pal, "/".join(sorted(PALETTES))))
        return 'blue'
    return pal


def make_cfg(a):
    theme = pick_theme(a)
    pal = pick_palette(a)
    t = dict(THEMES[theme])
    accent, accent2, soft, soft2, ink, line = PALETTES[pal]
    if a.get('font_body'):
        t['bf'] = a['font_body']
    if a.get('font_head'):
        t['hf'] = a['font_head']
    if a.get('margin'):
        t['margin'] = a['margin']
    if a.get('base_size'):
        t['size'] = unit(a['base_size'], 'pt')
    if a.get('leading'):
        t['leading'] = unit(a['leading'], 'em')
    _is_slide = (theme == 'slide')
    # 幻灯片主题默认 16:9；用户显式指定 page_size 时以用户为准
    _ps = (a.get('page_size') or ('16-9' if _is_slide else 'a4')).lower()
    paper = PAPER.get(_ps, 'presentation-16-9' if _is_slide else 'a4')
    if _ps not in PAPER:
        PARAM_WARN.append("page_size 写了 %s，不存在，已用 a4。可选：%s"
                          % (_ps, "/".join(sorted(PAPER))))
    pn = a.get('page_numbers')
    # 幻灯片默认不显示页码（页码在 16:9 页面里很碎）
    if pn is None and _is_slide:
        pn = 'false'
    pn_bool = 'false' if (pn is not None and str(pn).lower() in ('false', '0', 'no', 'off')) else 'true'
    return CFG_TPL % (accent, accent2, soft, soft2, ink, line, tq(t['bf']), tq(t['hf']), t['size'], t['leading'], tq(paper), margin_typst(t['margin']), pn_bool, tq(a.get('header_text') or ''), tq(a.get('watermark') or ''), t['h1'], t['h2'], t['h3'], t['h4'], t['h1fill'], t['h1bar'], ('true' if _is_slide else 'false'))


def make_cover(a, p):
    title = a.get('title') or ''
    sub = a.get('subtitle') or ''
    kicker = a.get('kicker') or ''
    meta = a.get('cover_meta') or ''
    hf = tq(THEMES[pick_theme(a)]['hf'])
    cards = []
    for piece in str(a.get('cover_cards') or '').split('|'):
        piece = piece.strip()
        if not piece:
            continue
        if '::' in piece:
            ct, cd = piece.split('::',1)
        else:
            ct, cd = piece, ''
        cards.append((ct.strip(), cd.strip()))
    L = []
    L.append('#page(margin:0pt, header: none, footer: none, numbering: none)[')
    L.append(' #block(width:100%%, height:100%%, fill: gradient.linear(rgb("%s"), rgb("#FFFFFF"), angle:160deg))[' % p[2])
    L.append(' #place(top + left, block(width:10mm, height:100%%, fill: gradient.linear(rgb("%s"), rgb("%s"), angle:180deg)))' % (p[0], p[1]))
    L.append(' #place(top + left, dx:24mm, dy:74mm, block[')
    if kicker:
        L.append(' #box(radius:999pt, stroke:1pt + rgb("%s"), inset: (x:13pt, y:5pt), text(font: %s, size:9pt, fill: rgb("%s"))[%s])' % (p[0], hf, p[0], esc_typ(kicker)))
        L.append(' #v(14pt)')
    if title:
        L.append(' #text(font: %s, size:32pt, weight: "bold", fill: rgb("%s"))[%s]' % (hf, p[4], esc_typ(title)))
        L.append(' #v(10pt)')
    L.append(' #block(width:46mm, height:4pt, radius:2pt, fill: gradient.linear(rgb("%s"), rgb("%s")))' % (p[0], p[1]))
    if sub:
        L.append(' #v(12pt)')
        L.append(' #block(width:126mm, text(size:12.5pt, fill: rgb("#5B6672"))[%s])' % esc_typ(sub))
    L.append(' ])')
    if cards:
        L.append(' #place(bottom + left, dx:24mm, dy: -50mm, block(width:158mm)[')
        L.append(' #block(width:100%%, height:2.4pt, radius:1.2pt, fill: gradient.linear(rgb("%s"), rgb("%s"), rgb("#FFFFFF"), angle:0deg))' % (p[0], p[1]))
        L.append(' #v(10pt)')
        cells = []
        for ct, cd in cards[:3]:
            cells.append(' block(width:100%%, radius:3pt, inset:11pt, stroke:0.5pt + rgb("%s"), fill: rgb("#FFFFFF"))[#text(font: %s, size:9pt, weight: "bold", fill: rgb("%s"))[%s]#v(4pt)#text(size:8.4pt, fill: rgb("#7A8494"))[%s]]' % (p[2], hf, p[0], esc_typ(ct), esc_typ(cd)))
        L.append(' #grid(columns: (1fr,) * %d, gutter:8pt,' % len(cards[:3]))
        L.append((',' + chr(10)).join(cells) + ',')
        L.append(' )')
        L.append(' ])')
    if meta:
        L.append(' #place(bottom + left, dx:24mm, dy: -22mm, block(width:158mm)[')
        L.append(' #block(width:100%, height:0.4pt, fill: rgb("#E6EAF0"))')
        L.append(' #v(7pt)')
        L.append(' #text(size:9.5pt, fill: rgb("#7A8494"))[%s]' % meta)
        L.append(' ])')
    L.append(' ]')
    L.append(']')
    L.append('')
    return chr(10).join(L)


def read_md(a):
    if a.get('md_file'):
        if not os.path.exists(a['md_file']):
            err('markdown file not found: %s' % a['md_file'])
        return open(a['md_file'], encoding='utf-8').read()
    if a.get('md'):
        return a['md']
    if a.get('html_file'):
        if not os.path.exists(a['html_file']):
            err('html file not found: %s' % a['html_file'])
        return open(a['html_file'], encoding='utf-8').read()
    if a.get('html'):
        return a['html']
    err('no input: provide md / md_file / html / html_file')


def cmd_build(a):
    sys.path.insert(0, HERE)
    del PARAM_WARN[:]
    check_font(a, 'font_body')
    check_font(a, 'font_head')
    import md2typst
    md = read_md(a)
    if not os.path.exists(THEME):
        err('theme2.typ missing at %s' % THEME)
    theme = open(THEME, encoding='utf-8').read()
    pal = pick_palette(a)
    paint = PALETTES[pal]
    warn = []
    try:
        # input_format=html 之前只改了 JS 层参数名，core 一律当 markdown 解析，
        # 等于没修。这里真正分流：HTML 先转 Markdown 再排版。
        if a.get('html') is not None or a.get('html_file') is not None:
            _h = a.get('html')
            if _h is None:
                _hf = a['html_file']
                if not os.path.exists(_hf):
                    err('html_file not found: %s' % _hf)
                _h = open(_hf, encoding='utf-8', errors='replace').read()
            _r = subprocess.run(['pandoc', '-f', 'html', '-t', 'gfm', '--wrap=none'],
                                input=str(_h), capture_output=True, text=True, timeout=180)
            if _r.returncode != 0:
                err('HTML 转换失败：%s' % (_r.stderr or '')[:300])
            md = _r.stdout
        body, warn = md2typst.convert_checked(md)
    except Exception as e:
        err('markdown conversion failed: %s' % e)
    parts = [make_cfg(a), theme, chr(10)]
    if a.get('cover'):
        parts.append(make_cover(a, paint))
    title = a.get('title') or ''
    # slide 模式下页面顶部的色条已经是标题了，再加页眉会跟色条重叠并超出页边
    # （pdf_lint 实测报 text_overflow 上 2.5mm）
    if title and not a.get('header_text') and pick_theme(a) != 'slide':
        parts.append('#set page(header: align(right)[#text(font: cfg.head-font, size:8pt, fill: rgb("#B0B7C3"))[%s]])' % esc_typ(title) + chr(10) *2)
    parts.append(body)
    if a.get('extra_typst'):
        parts.append(chr(10) + str(a['extra_typst']) + chr(10))
    full = ''.join(parts)
    outpath = a['out']
    if os.path.dirname(outpath):
        os.makedirs(os.path.dirname(outpath), exist_ok=True)
    fd, tmp = tempfile.mkstemp(suffix='.typ', prefix='ai_pdf_')
    os.close(fd)
    r = None
    try:
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(full)
        typst = get_typst()
        cmd = [typst, 'compile', '--root', '/']
        for fd in font_paths(a):
            cmd.extend(['--font-path', fd])
        if os.path.isdir(PKG_DIR):
            cmd.extend(['--package-path', PKG_DIR])
        cmd.extend([tmp, outpath])
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        err('typst exec error: %s' % e)
    finally:
        try:
            os.unlink(tmp)
        except Exception:
            pass
    if r.returncode !=0:
        err('typst compile failed:' + chr(10) + (r.stderr or r.stdout or '')[:1800])
    if not os.path.exists(outpath) or os.path.getsize(outpath) ==0:
        err('output not created: %s' % outpath)
    with open(outpath, 'rb') as fh:
        if fh.read(5) != b'%PDF-':
            err('output is not a PDF')
    pages = None
    try:
        fitz = get_fitz()
        dd = fitz.open(outpath)
        pages = dd.page_count
        dd.close()
    except Exception:
        pass
    allw = []
    for w in warn + PARAM_WARN:
        if w not in allw:
            allw.append(w)
    out(output=outpath, bytes=os.path.getsize(outpath), pages=pages,
        theme=pick_theme(a), palette=pal, engine='typst',
        warnings=allw if allw else None)


def cmd_preview(a):
    pdf, outdir = a['pdf'], a['outdir']
    dpi = int(a.get('dpi') or 110)
    fitz = get_fitz()
    if not os.path.exists(pdf):
        err('PDF not found: %s' % pdf)
    os.makedirs(outdir, exist_ok=True)
    doc = fitz.open(pdf)
    total = doc.page_count
    idxs = parse_pages(a.get('pages'), total)
    if not idxs:
        err('no valid pages; total=%d spec=%s' % (total, a.get('pages')))
    base = os.path.splitext(os.path.basename(pdf))[0]
    files = []
    for i in idxs:
        pix = doc[i].get_pixmap(dpi=dpi)
        path = os.path.join(outdir, '%s_p%03d.png' % (base, i +1))
        pix.save(path)
        files.append({'page': i +1, 'path': path, 'width': pix.width, 'height': pix.height})
    doc.close()
    out(total_pages=total, rendered=files)


def cmd_info(a):
    pdf = a['pdf']
    fitz = get_fitz()
    if not os.path.exists(pdf):
        err('PDF not found: %s' % pdf)
    doc = fitz.open(pdf)
    r = doc[0].rect
    w, h = r.width, r.height
    wm, hm = round(w /72 *25.4,1), round(h /72 *25.4,1)
    meta = {k: v for k, v in (doc.metadata or {}).items() if v}
    n = doc.page_count
    doc.close()
    out(pages=n, size_pt=[round(w,1), round(h,1)], size_mm={'width_mm': wm, 'height_mm': hm}, orientation='portrait' if wm < hm else 'landscape', file_size=os.path.getsize(pdf), metadata=meta)


def cmd_merge(a):
    dest, ins = a['out'], a['inputs']
    fitz = get_fitz()
    miss = [p for p in ins if not os.path.exists(p)]
    if miss:
        err('input not found: %s' % miss)
    res = fitz.open()
    for p in ins:
        d = fitz.open(p)
        res.insert_pdf(d)
        d.close()
    if os.path.dirname(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
    res.save(dest)
    n = res.page_count
    res.close()
    out(output=dest, pages=n, merged_from=len(ins))


def cmd_split(a):
    pdf, outdir = a['pdf'], a['outdir']
    fitz = get_fitz()
    if not os.path.exists(pdf):
        err('PDF not found: %s' % pdf)
    os.makedirs(outdir, exist_ok=True)
    doc = fitz.open(pdf)
    total = doc.page_count
    base = os.path.splitext(os.path.basename(pdf))[0]
    raw = (a.get('ranges') or '').strip()
    if raw:
        specs = [s.strip() for s in raw.split(',') if s.strip()]
    else:
        specs = [str(i +1) for i in range(total)]
    produced = []
    for spec in specs:
        idxs = parse_pages(spec, total)
        if not idxs:
            continue
        nd = fitz.open()
        for i in idxs:
            nd.insert_pdf(doc, from_page=i, to_page=i)
        tag = re.sub(r'[^0-9a-zA-Z]+', '_', spec)
        path = os.path.join(outdir, '%s_%s.pdf' % (base, tag))
        nd.save(path)
        c = nd.page_count
        nd.close()
        produced.append({'range': spec, 'path': path, 'pages': c})
    doc.close()
    out(total_pages=total, outputs=produced)


def cmd_extract(a):
    src, dest = a['pdf'], a['out']
    fitz = get_fitz()
    if not os.path.exists(src):
        err('PDF not found: %s' % src)
    doc = fitz.open(src)
    idxs = parse_pages(a.get('pages'), doc.page_count)
    if not idxs:
        err('no valid pages: %s' % a.get('pages'))
    nd = fitz.open()
    for i in idxs:
        nd.insert_pdf(doc, from_page=i, to_page=i)
    if os.path.dirname(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
    nd.save(dest)
    n = nd.page_count
    nd.close()
    doc.close()
    out(output=dest, pages=n, extracted=[i +1 for i in idxs])


def cmd_rotate(a):
    src, dest = a['pdf'], a['out']
    deg = int(a.get('degrees') or 90)
    fitz = get_fitz()
    if not os.path.exists(src):
        err('PDF not found: %s' % src)
    doc = fitz.open(src)
    idxs = parse_pages(a.get('pages'), doc.page_count)
    if deg % 90 != 0:
        err('degrees 必须是 90 的倍数（0/90/180/270）。'
            'PyMuPDF 只存 90 的倍数，传 %d 会被静默吞掉（报成功但没转），所以这里直接拒绝' % deg)
        return
    for i in idxs:
        doc[i].set_rotation((doc[i].rotation + deg) %360)
    doc.save(dest)
    n = doc.page_count
    doc.close()
    out(output=dest, pages=n, rotated=len(idxs), degrees=deg)


def cmd_text(a):
    pdf = a['pdf']
    doc = open_pdf(pdf, 'extract_pdf_text')
    idxs = parse_pages(a.get('pages'), doc.page_count)
    chunks = [{'page': i + 1, 'text': doc[i].get_text()} for i in idxs]
    imgs = sum(len(doc[i].get_images()) for i in idxs)
    doc.close()
    blank = [x['page'] for x in chunks if not (x['text'] or '').strip()]
    notes = []
    if blank and imgs:
        notes.append('第 %s 页没有文本层但含图片，多半是扫描件/截图；'
                     '提取文字需要 OCR（本机未装 tesseract）'
                     % '/'.join(str(p) for p in blank[:6]))
    elif blank:
        notes.append('第 %s 页没提取到任何文字' % '/'.join(str(p) for p in blank[:6]))
    out(pages=len(chunks), content=chunks,
        blank_pages=blank if blank else None, images=imgs,
        notes=notes if notes else None)



def cmd_img2pdf(a):
    from PIL import Image
    fitz = get_fitz()
    dest = a['out']
    size = (a.get('page_size') or 'A4').upper()
    paths = a['inputs']
    miss = [p for p in paths if not os.path.exists(p)]
    if miss:
        err('image not found: %s' % miss)
    doc = fitz.open()
    for pth in paths:
        im = Image.open(pth)
        w, h = im.size
        pw, ph = (w *72.0 /96.0, h *72.0 /96.0) if size == 'FIT' else (595.276,841.89)
        page = doc.new_page(width=pw, height=ph)
        if size == 'FIT':
            page.insert_image(fitz.Rect(0,0, pw, ph), filename=pth)
        else:
            s = min(pw / w, ph / h)
            dw, dh = w * s, h * s
            x0, y0 = (pw - dw) /2.0, (ph - dh) /2.0
            page.insert_image(fitz.Rect(x0, y0, x0 + dw, y0 + dh), filename=pth)
    if os.path.dirname(dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
    doc.save(dest)
    n = doc.page_count
    doc.close()
    out(output=dest, pages=n, images=len(paths))


def cmd_selfcheck(a):
    typst = find_typst()
    info = {'typst': typst or None, 'theme': os.path.exists(THEME), 'md2typst': os.path.exists(os.path.join(HERE, 'md2typst.py'))}
    ver = None
    if typst:
        try:
            r = subprocess.run([typst, '--version'], capture_output=True, text=True, timeout=30)
            ver = (r.stdout or '').strip()
        except Exception:
            pass
    info['typst_version'] = ver
    try:
        r = subprocess.run(['pandoc', '--version'], capture_output=True, text=True, timeout=30)
        info['pandoc'] = (r.stdout or '').split(chr(10))[0]
    except Exception:
        info['pandoc'] = None
    try:
        import pymupdf
        info['pymupdf'] = True
    except Exception:
        info['pymupdf'] = False
    out(ok=bool(typst) and info['theme'], detail=info)


# ============================================================
# 扩展命令（2026-11-22）
# ============================================================

def open_pdf(path, tool):
    """统一开 PDF：加密的先拦下来，提示去 decrypt_pdf，别直接抛 traceback。"""
    if not path or not os.path.exists(path):
        err('PDF not found: %s' % path)
        return None
    fz = _fitz()
    d = fz.open(path)
    if d.needs_pass:
        d.close()
        err('这个 PDF 有密码，%s 读不了。先调 decrypt_pdf 解密' % tool)
        return None
    return d


def _fitz():
    import pymupdf
    return pymupdf


def cmd_lint(a):
    """程序化版式体检。不依赖视觉模型。"""
    src = a.get('pdf') or a.get('pdf_path')
    if not src or not os.path.exists(src):
        err('PDF not found: %s' % src)
    tol_mm = float(a.get('tol_mm', 2.0))
    min_dpi = float(a.get('min_dpi', 150))
    max_pages = a.get('max_pages')

    fz = _fitz()
    doc = fz.open(src)
    total = doc.page_count
    n = min(total, int(max_pages)) if max_pages else total
    MM = 72.0 / 25.4
    tol = tol_mm * MM
    issues = []
    sizes = []

    for i in range(n):
        pg = doc[i]
        r = pg.rect
        sizes.append((round(r.width, 1), round(r.height, 1)))
        pno = i + 1
        blocks = pg.get_text('blocks')
        text = pg.get_text().strip()
        try:
            ndraw = len(pg.get_drawings())
        except Exception:
            ndraw = 0
        nimg = len(pg.get_images())

        # ① 空白页：只判「有没有字」会漏掉「只剩页眉页脚页码」的假空白
        _lines = [ln.strip() for ln in text.split(chr(10)) if ln.strip()]
        _body = [ln for ln in _lines
                 if not (ln.replace(' ', '').replace('/', '').isdigit())
                 and len(ln) > 3]
        # 只判「有没有字」会漏掉「标题被挤到新页」的近似空白页。
        # 去掉页码后整页正文不足 12 个字符、且没有图和实质图形，也算空白。
        _chars = sum(len(ln) for ln in _body)
        if _chars < 12 and nimg == 0 and ndraw <= 2:
            issues.append(dict(page=pno, kind='blank_page', level='error',
                               msg='近似空白页：整页只有 %d 个字符（多半是标题被挤到新页）' % _chars,
                               fix='检查是否多写了 ::: pagebreak，或该节内容为空'))
            continue
        if not text and nimg == 0 and ndraw == 0:
            issues.append(dict(page=pno, kind='blank_page', level='error',
                               msg='空白页：没有文字、图片或图形',
                               fix='检查是否多写了 ::: pagebreak，或该节内容为空'))
            continue

        # ② 文字溢出
        for b in blocks:
            x0, y0, x1, y1 = b[0], b[1], b[2], b[3]
            snip = (b[4] or '').strip().replace(chr(10), ' ')[:24]
            over = []
            if x1 > r.width + tol:
                over.append('右 %.1fmm' % ((x1 - r.width) / MM))
            if x0 < -tol:
                over.append('左 %.1fmm' % ((-x0) / MM))
            if y1 > r.height + tol:
                over.append('下 %.1fmm' % ((y1 - r.height) / MM))
            if y0 < -tol:
                over.append('上 %.1fmm' % ((-y0) / MM))
            if over:
                issues.append(dict(page=pno, kind='text_overflow', level='error',
                                   msg='文字超出页面边界 %s：%s' % ('、'.join(over), snip or '(无文字)'),
                                   fix='多为超长英文词/URL 或表格过宽；在源码里加空格断行，或把该处字号调小'))
                break

        # ②b 图形溢出（卡片/色块/装饰常画到页外，之前完全没查）
        try:
            for dr in pg.get_drawings():
                rr = dr.get('rect')
                if not rr:
                    continue
                dx1 = rr.x1 - r.width
                dy1 = rr.y1 - r.height
                if dx1 > tol or dy1 > tol or rr.x0 < -tol or rr.y0 < -tol:
                    issues.append(dict(
                        page=pno, kind='graphic_overflow', level='error',
                        msg='图形超出页面边界（右 %.1fmm / 下 %.1fmm）'
                            % (max(0, dx1) / MM, max(0, dy1) / MM),
                        fix='多半是卡片/色块宽度算错；检查 cards 列数或 extra_typst 的宽度'))
                    break
        except Exception:
            pass

        # ③ 文字压在页面边缘（可能被裁）
        edge = 3.0 * MM
        for b in blocks:
            if b[0] < edge or b[1] < edge or b[2] > r.width - edge or b[3] > r.height - edge:
                snip = (b[4] or '').strip().replace(chr(10), ' ')[:20]
                issues.append(dict(page=pno, kind='near_edge', level='warn',
                                   msg='文字离页边不足 3mm，打印可能被裁：%s' % (snip or '(无文字)'),
                                   fix='把 margin 调大，或减少该处内容'))
                break

        # ④ 图片分辨率
        for img in pg.get_images(full=True):
            xref = img[0]
            try:
                bbox = pg.get_image_bbox(img)
                if bbox.width <= 0 or bbox.height <= 0:
                    continue
                info = doc.extract_image(xref)
                dpi_x = info['width'] / (bbox.width / 72.0)
                if dpi_x < min_dpi:
                    issues.append(dict(page=pno, kind='low_dpi', level='warn',
                                       msg='图片分辨率约 %d dpi，低于 %d dpi，印刷会发虚'
                                           % (round(dpi_x), int(min_dpi)),
                                       fix='换更高清的图，或把该图显示尺寸缩小'))
            except Exception:
                pass

    # ⑤ 页面尺寸不一致
    if len(set(sizes)) > 1:
        issues.append(dict(page=0, kind='size_mismatch', level='error',
                           msg='页面尺寸不一致：%s' % ', '.join('%sx%s' % t for t in sorted(set(sizes))[:3]),
                           fix='多为混入了不同纸张来源的页；检查 page_size 是否统一'))

    # ⑥ 字体未嵌入
    try:
        bad_fonts = []
        for i in range(n):
            for f in doc.get_page_fonts(i):
                # (xref, ext, type, basefont, name, encoding)
                if f[1] in ('n/a', '', None):
                    bad_fonts.append(f[3])
        if bad_fonts:
            issues.append(dict(page=0, kind='font_not_embedded', level='warn',
                               msg='有 %d 个字体未嵌入：%s'
                                   % (len(set(bad_fonts)), ', '.join(sorted(set(bad_fonts))[:4])),
                               fix='换成本地字体库里有的字体，或用 optimize_pdf 做字体子集化'))
    except Exception:
        pass

    doc.close()
    errs = len([x for x in issues if x.get('level') == 'error'])
    warns = len([x for x in issues if x.get('level') == 'warn'])
    out(source=src, pages=total, scanned=n, errors=errs, warns=warns,
        clean=(errs == 0), issues=issues)


def _all_faces(a):
    """遍历字体库，返回 [(family, cmap_keys_set)]。支持 .ttc 多子字体。"""
    from fontTools.ttLib import TTFont, TTCollection
    out_list = []
    names = set()
    for d in font_paths(a):
        for dp, _dn, fs in os.walk(d):
            for f in sorted(fs):
                if not f.lower().endswith(('.ttf', '.otf', '.ttc')):
                    continue
                p = os.path.join(dp, f)
                faces = []
                try:
                    if f.lower().endswith('.ttc'):
                        faces = list(TTCollection(p, lazy=True).fonts)
                    else:
                        faces = [TTFont(p, lazy=True)]
                except Exception:
                    continue
                for tt in faces:
                    # 收集全部 nameID=1 记录（同一字体可能有简中/繁中/英文多个别名），
                    # 之前只取第一个就 break，导致「霞鶩文楷」进了库但「LXGW WenKai」没进，
                    # FontFamily 检查因此误报“库里没有”。
                    fams = []
                    try:
                        for rec in tt['name'].names:
                            if rec.nameID != 1:
                                continue
                            try:
                                v = rec.toUnicode()
                            except Exception:
                                continue
                            if v and v not in fams:
                                # 英文/ASCII 名字排前面，更好认
                                if all(ord(ch) < 128 for ch in v):
                                    fams.insert(0, v)
                                else:
                                    fams.append(v)
                    except Exception:
                        pass
                    if not fams:
                        continue
                    fam = fams[0]
                    for f2 in fams:
                        names.add(f2)
                    try:
                        cm = tt.getBestCmap() or {}
                    except Exception:
                        cm = {}
                    if cm:
                        out_list.append((fam, set(cm.keys())))
                    try:
                        tt.close()
                    except Exception:
                        pass
    return out_list, names


def _resolve_family(want, faces, names):
    """把字体名解析成字体库 family。

    只做「目标名包含在某 family 里」的单向匹配，不再反向包含——
    否则 'Noto Serif CJK SC' 会匹配到西文 'Noto Serif'，给出假阳性。
    且目标名至少要 4 个字符，避免 'Serif' 这种泛词乱撞。
    """
    w = str(want).strip().lower()
    exact = [f for f in names if f.lower() == w]
    if exact:
        return exact[0], True
    if len(w) < 4:
        return None, False
    part = [f for f in names if w in f.lower()]
    if part:
        # 取最短的（最贴近）那个
        return sorted(part, key=len)[0], True
    return None, False


def cmd_fontcov(a):
    """检查每个字在指定字体里是否都有字形。"""
    text = a.get('text') or ''
    src = a.get('md') or a.get('pdf') or a.get('input')
    if not text and src:
        if not os.path.exists(src):
            err('文件不存在：%s' % src)
        if src.lower().endswith('.pdf'):
            fz = _fitz()
            d = fz.open(src)
            text = ''.join(d[i].get_text() for i in range(d.page_count))
            d.close()
        else:
            text = open(src, encoding='utf-8').read()
    text = ''.join(ch for ch in text if ch.strip())
    if not text:
        err('no text：传 text，或传 md / pdf 路径')

    want = a.get('font')
    if not want:
        err('font is required（如 Source Han Serif SC / MiSans）')

    faces, names = _all_faces(a)
    if not faces:
        err('字体库为空或无可用字形表；先跑 pdf_selfcheck')

    fam, ok = _resolve_family(want, faces, names)
    if not ok:
        sample = sorted(names)[:8]
        err('字体库里没有「%s」。可用的前 8 个：%s。'
            '注意 Noto Serif/Sans CJK SC 是系统字体，不在项目字体库内'
            % (want, ', '.join(sample)))
        return

    have = set()
    n_face = 0
    for f2, keys in faces:
        if f2 == fam:
            have |= keys
            n_face += 1

    used = sorted(set(ord(c) for c in text))
    missing = [c for c in used if c not in have]
    sample_miss = ''.join(chr(c) for c in missing[:40])
    out(font=fam, faces=n_face, glyphs=len(have),
        chars_used=len(used), chars_missing=len(missing),
        sample=sample_miss, ok=(len(missing) == 0),
        hint=('该字体覆盖全部用字'
              if not missing else
              '缺 %d 个字形。可用 match_font 找覆盖更好的字体' % len(missing)))


def cmd_matchfont(a):
    """给一段文本，推荐字体库里覆盖最好的几款字体。"""
    text = a.get('text') or ''
    src = a.get('md') or a.get('pdf') or a.get('input')
    if not text and src and os.path.exists(src):
        if src.lower().endswith('.pdf'):
            fz = _fitz()
            d = fz.open(src)
            text = ''.join(d[i].get_text() for i in range(d.page_count))
            d.close()
        else:
            text = open(src, encoding='utf-8').read()
    used = sorted(set(ord(c) for c in text if c.strip()))
    if not used:
        err('text 为空或全是空白')

    faces, names = _all_faces(a)
    if not faces:
        err('字体库为空')

    agg = {}
    for fam, keys in faces:
        if fam in agg:
            agg[fam] |= keys
        else:
            agg[fam] = set(keys)

    ranked = []
    for fam, keys in agg.items():
        miss = sum(1 for c in used if c not in keys)
        ranked.append((miss, fam, len(keys)))
    ranked.sort(key=lambda t: (t[0], -t[2]))

    out(chars_used=len(used), total_fonts=len(agg),
        fonts=[dict(font=f, missing=m, glyphs=g) for m, f, g in ranked[:12]],
        hint='missing=0 表示完全覆盖；中西混排建议 Source Han Serif SC / MiSans / LXGW WenKai')


def _hex2rgb(h):
    h = str(h).lstrip('#')
    if len(h) != 6:
        return (0.5, 0.5, 0.5)
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def cmd_splitoutline(a):
    """按 PDF 自带书签拆成多个 PDF。"""
    src = a.get('pdf')
    if not src or not os.path.exists(src):
        err('PDF not found: %s' % src)
    dest = a.get('output_dir') or os.path.join(os.path.dirname(src), 'split_outline')
    os.makedirs(dest, exist_ok=True)
    level = int(a.get('level', 1))

    fz = _fitz()
    doc = fz.open(src)
    toc = doc.get_toc(simple=True) or []
    if not toc:
        doc.close()
        err('这个 PDF 没有书签（outline），没法按标题拆。'
            '本工具生成的文档请确认源 Markdown 用了 # / ## 标题；'
            '否则改用 split_pdf 按页范围拆')
        return

    marks = [(lv, title, pg) for lv, title, pg in toc if lv <= level]
    if len(marks) < 2:
        doc.close()
        err('第 %d 层只有 %d 个书签，不够拆；试试 level=2' % (level, len(marks)))
        return

    total = doc.page_count
    same_page = [m for m in marks if m[2] == marks[0][2]]
    if len(same_page) == len(marks) and total <= 1:
        doc.close()
        err('这份 PDF 只有 %d 页，所有书签都落在同一页，没法按章拆。'
            '按标题拆需要源文档本身有分页（内容够长，或章节间用 ::: pagebreak）'
            % total)
        return

    made = []
    skipped = []
    for i, (lv, title, pg) in enumerate(marks):
        start = max(0, pg - 1)
        end = (marks[i + 1][2] - 1) if i + 1 < len(marks) else total
        # 同页多书签时第 2 个起 end == start，旧代码直接 continue，静默丢章。
        # 这里记下来随结果返回，让调用方知道少拆了哪几章。
        if end <= start:
            skipped.append({"title": str(title), "page": pg,
                            "why": "与前一个书签同页，无法单独成册"})
            continue
        safe = re.sub(r'[\\/:*?"<>|\s]+', '_', str(title))[:40] or ('part%02d' % (i + 1))
        p = os.path.join(dest, '%02d_%s.pdf' % (i + 1, safe))
        nd = fz.open()
        nd.insert_pdf(doc, from_page=start, to_page=end - 1)
        nd.save(p)
        nd.close()
        made.append(dict(title=title, pages=end - start, path=p))

    doc.close()
    notes = []
    if skipped:
        notes.append('%d 个书签与前一章同页，拆不出独立册（内容仍在原册里）：%s'
                     % (len(skipped),
                        ' / '.join(x['title'] for x in skipped[:5])))
    out(output_dir=dest, count=len(made), parts=made,
        skipped=skipped if skipped else None,
        notes=notes if notes else None,
        hint='每个书签一册；同页书签拆不开时改用 split_pdf 按页拆')


def _cjk_font(fz, a):
    """找中文 TTF。必须是 TrueType 轮廓 —— subset_fonts 对 CFF/OTF 无效，
    用 OTF 会给 PDF 塞进 17-21MB 完整字库。"""
    pool = []
    for d in font_paths(a):
        for dp, _dn, fs in os.walk(d):
            for f in fs:
                low = f.lower()
                if not low.endswith('.ttf'):
                    continue
                p = os.path.join(dp, f)
                try:
                    pool.append((os.path.getsize(p), p))
                except Exception:
                    pass
    if not pool:
        return None
    pref = ['misans', 'notosanscjk', 'notoserifcjk', 'sourcehan', 'wenkai', 'sthinkra']
    for key in pref:
        cand = [(sz, p) for sz, p in pool if key in os.path.basename(p).lower()]
        if cand:
            cand.sort()
            return cand[0][1]
    pool.sort()
    return pool[0][1]


def cmd_stamp(a):
    """给 PDF 每页叠加页眉/页脚/页码/水印。"""
    src = a.get('pdf')
    if not src or not os.path.exists(src):
        err('PDF not found: %s' % src)
    dst = a.get('out') or (os.path.splitext(src)[0] + '_stamped.pdf')

    fz = _fitz()
    doc = fz.open(src)
    total = doc.page_count
    MM = 72.0 / 25.4
    size = float(a.get('size', 8))
    color = _hex2rgb(a.get('color') or '#888888')
    header = a.get('header') or ''
    footer = a.get('footer') or ''
    pageno = a.get('page_numbers', True)
    skip_dup = a.get('skip_if_has_pageno', True)
    mark = a.get('watermark') or ''
    offset = float(a.get('offset', 10)) * MM
    fs = float(a.get('watermark_size', 40))

    txt_all = header + footer + mark
    need_cjk = any(u'\u4e00' <= ch <= u'\u9fff' for ch in txt_all)
    ff = _cjk_font(fz, a) if need_cjk else None
    kw = {}
    if ff:
        kw = dict(fontfile=ff, fontname='cjk')
    notes = []
    if need_cjk and not ff:
        notes.append('页眉/水印含中文，但字体库里找不到可用 TTF，中文可能画不出来')

    for i, pg in enumerate(doc):
        r = pg.rect
        if header:
            pg.insert_text((offset, offset * 0.55), str(header),
                           fontsize=size, color=color, **kw)
        if footer:
            pg.insert_text((offset, r.height - offset * 0.5), str(footer),
                           fontsize=size, color=color, **kw)
        if pageno:
            existing = pg.get_text() or ''
            has = ('%d / %d' % (i + 1, total)) in existing
            if not (skip_dup and has):
                t = '%d / %d' % (i + 1, total)
                w = max(1, len(t)) * size * 0.5
                pg.insert_text(((r.width - w) / 2, r.height - offset * 0.5), t,
                               fontsize=size, color=color, **kw)
        if mark:
            # 用 insert_text + rotate，不用 textbox（框太窄会返回负值、什么都不写）
            angle = float(a.get('watermark_angle', 45))
            ang = 90 if abs(angle - 90) < abs(angle - 0) else 0
            try:
                pg.insert_text((r.width * 0.12, r.height * 0.55), str(mark),
                               fontsize=fs, color=(0.85, 0.85, 0.85),
                               rotate=ang, **kw)
            except Exception:
                try:
                    pg.insert_text((r.width * 0.12, r.height * 0.55), str(mark),
                                   fontsize=fs, color=(0.85, 0.85, 0.85), **kw)
                except Exception:
                    pass

    try:
        doc.subset_fonts(verbose=False)
    except Exception:
        pass
    doc.save(dst, garbage=4, deflate=True, deflate_fonts=True, clean=True)
    doc.close()

    chk = fz.open(dst)
    t0 = chk[0].get_text() or ''
    chk.close()
    checks = []
    if header:
        checks.append(dict(item='header', text=header, rendered=(header in t0)))
    if mark:
        checks.append(dict(item='watermark', text=mark, rendered=(mark in t0)))

    for c in checks:
        if not c['rendered'] and c['text']:
            c['rendered'] = c['text'][0] in t0
    bad = [c for c in checks if not c['rendered']]
    if bad:
        notes.append('以下内容没有出现在文本层：' +
                     ', '.join(c['item'] for c in bad) +
                     '（可能只是字体问题，请用 render_pdf_preview 看图确认）')

    out(output=dst, pages=total, bytes=os.path.getsize(dst),
        cjk_font=(os.path.basename(ff) if ff else None),
        checks=checks, notes=notes if notes else None,
        hint='已叠加；一定要 render_pdf_preview 看一眼位置对不对')


def cmd_encrypt(a):
    """PDF 加密。用 PyMuPDF 原生实现（系统 cryptography 太旧，pypdf 的 AES 用不了）。"""
    src = a.get('pdf')
    if not src or not os.path.exists(src):
        err('PDF not found: %s' % src)
    pw = a.get('password')
    if not pw:
        err('password is required')
    dst = a.get('out') or (os.path.splitext(src)[0] + '_locked.pdf')

    fz = _fitz()
    ALGS = {
        'aes-256': fz.PDF_ENCRYPT_AES_256,
        'aes-128': fz.PDF_ENCRYPT_AES_128,
        'rc4-128': fz.PDF_ENCRYPT_RC4_128,
        'rc4-40': fz.PDF_ENCRYPT_RC4_40,
    }
    alg = str(a.get('algorithm') or 'aes-256').lower()
    if alg not in ALGS:
        err('algorithm 写了 %s，只支持 aes-256 / aes-128 / rc4-128 / rc4-40' % alg)
        return

    doc = fz.open(src)
    if doc.needs_pass:
        if not doc.authenticate(str(a.get('old_password') or '')):
            doc.close()
            err('源文件已加密，old_password 不对或没给')
            return

    perm = fz.PDF_PERM_ACCESSIBILITY | fz.PDF_PERM_PRINT
    if a.get('allow_copy', True):
        perm |= fz.PDF_PERM_COPY
    if a.get('allow_modify', False):
        perm |= fz.PDF_PERM_MODIFY

    try:
        doc.save(dst, encryption=ALGS[alg],
                 user_pw=str(pw),
                 owner_pw=str(a.get('owner_password') or pw),
                 permissions=perm)
    except Exception as e:
        doc.close()
        err('加密失败（%s）：%s' % (alg, str(e)[:200]))
        return
    doc.close()

    chk = fz.open(dst)
    locked = bool(chk.needs_pass)
    chk.close()
    if not locked:
        err('加密后自检失败：文件未受密码保护，请反馈')
        return

    out(output=dst, bytes=os.path.getsize(dst), algorithm=alg, encrypted=True,
        hint='已加密并自检通过；打开需要密码，忘了无法恢复')


def cmd_decrypt(a):
    """PDF 解密/去密码。"""
    src = a.get('pdf')
    if not src or not os.path.exists(src):
        err('PDF not found: %s' % src)
    pw = a.get('password') or ''
    dst = a.get('out') or (os.path.splitext(src)[0] + '_unlocked.pdf')

    fz = _fitz()
    doc = fz.open(src)
    was = bool(doc.needs_pass)
    if was and not doc.authenticate(str(pw)):
        doc.close()
        err('密码不对，解不开')
        return
    doc.save(dst, encryption=fz.PDF_ENCRYPT_NONE, garbage=4, deflate=True)
    doc.close()

    chk = fz.open(dst)
    still = bool(chk.needs_pass)
    chk.close()
    if still:
        err('解密后自检失败：文件仍受保护，请反馈')
        return
    out(output=dst, bytes=os.path.getsize(dst), was_encrypted=was,
        hint=('已去除密码' if was else '源文件本来就没有密码，已另存一份'))


def cmd_optimize(a):
    """体积优化：字体子集化 + deflate + 可选 Ghostscript 压图。"""
    src = a.get('pdf')
    if not src or not os.path.exists(src):
        err('PDF not found: %s' % src)
    dst = a.get('out') or (os.path.splitext(src)[0] + '_opt.pdf')
    before = os.path.getsize(src)

    fz = _fitz()
    doc = fz.open(src)
    steps = []
    if a.get('subset_fonts', True):
        try:
            doc.subset_fonts(verbose=False)
            steps.append('字体子集化')
        except Exception as e:
            steps.append('字体子集化跳过(%s)' % str(e)[:40])
    q = str(a.get('quality') or 'ebook')
    doc.save(dst, garbage=4, deflate=True, deflate_images=True,
             deflate_fonts=True, clean=True)
    doc.close()

    if a.get('gs_compress'):
        tmp = dst + '.gs.pdf'
        preset = {'screen': '/screen', 'ebook': '/ebook', 'printer': '/printer'}.get(q, '/ebook')
        r = subprocess.run(['gs', '-sDEVICE=pdfwrite', '-dCompatibilityLevel=1.7',
                            '-dPDFSETTINGS=' + preset, '-dNOPAUSE', '-dQUIET', '-dBATCH',
                            '-sOutputFile=' + tmp, dst],
                           capture_output=True, text=True, timeout=300)
        if r.returncode == 0 and os.path.exists(tmp):
            if os.path.getsize(tmp) < os.path.getsize(dst):
                os.replace(tmp, dst)
                steps.append('Ghostscript(' + preset.strip('/') + ')')
            else:
                os.remove(tmp)

    after = os.path.getsize(dst)
    out(output=dst, before=before, after=after, saved=before - after,
        ratio=('%.1f%%' % ((before - after) * 100.0 / before)) if before else '0%',
        steps=steps,
        hint=('已压缩' if after < before else '压不动了，原文件可能已经很紧凑'))


def cmd_importdoc(a):
    """docx / odt / html / xlsx -> Markdown。"""
    src = a.get('input') or a.get('src')
    if not src or not os.path.exists(src):
        err('file not found: %s' % src)
    dst = a.get('out') or (os.path.splitext(src)[0] + '.md')
    low = src.lower()

    if low.endswith(('.xlsx', '.xlsm')):
        try:
            import openpyxl
        except Exception:
            err('需要 openpyxl')
        wb = openpyxl.load_workbook(src, data_only=True)
        chunks = []
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(values_only=True))
            if not rows:
                continue
            chunks.append('## ' + ws.title)
            head = rows[0]
            chunks.append('| ' + ' | '.join('' if c is None else str(c) for c in head) + ' |')
            chunks.append('|' + '---|' * len(head))
            for r in rows[1:]:
                chunks.append('| ' + ' | '.join('' if c is None else str(c) for c in r) + ' |')
            chunks.append('')
        md = chr(10).join(chunks)
    else:
        if low.endswith('.docx'):
            fmt = 'docx'
        elif low.endswith('.odt'):
            fmt = 'odt'
        else:
            fmt = 'html'
        r = subprocess.run(['pandoc', '-f', fmt, '-t', 'gfm', '--wrap=none', src],
                           capture_output=True, text=True, timeout=180)
        if r.returncode != 0:
            err('pandoc 转换失败：%s' % (r.stderr or '')[:300])
        md = r.stdout

    with open(dst, 'w', encoding='utf-8') as f:
        f.write(md)
    out(output=dst, bytes=os.path.getsize(dst), chars=len(md),
        preview=md[:200],
        hint='已转成 Markdown；再用 make_pdf(input_path=...) 出 PDF')


def cmd_batch(a):
    """批量生成：CSV/JSON + {{列名}} 模板，一次出多份 PDF。"""
    data_src = a.get('data')
    if not data_src or not os.path.exists(data_src):
        err('data not found: %s（CSV 或 JSON）' % data_src)
    tpl = a.get('template') or a.get('input')
    if not tpl or not os.path.exists(tpl):
        err('template not found: %s（含 {{列名}} 占位的 .md）' % tpl)
    dest = a.get('output_dir') or os.path.join(os.path.dirname(data_src), 'batch_out')
    os.makedirs(dest, exist_ok=True)

    if data_src.lower().endswith('.json'):
        obj = json.load(open(data_src, encoding='utf-8'))
        rows = obj if isinstance(obj, list) else [obj]
    else:
        import csv
        with open(data_src, encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
    if not rows:
        err('data 是空的')

    tpl_txt = open(tpl, encoding='utf-8').read()
    ph = set(re.findall(r'\{\{\s*([\w\-.]+)\s*\}\}', tpl_txt))
    if not ph:
        err('template 里没有 {{列名}} 占位符，批不出来')
    cols = set(rows[0].keys())
    lack = sorted(ph - cols)
    if lack:
        err('template 用到但数据里没有的列：%s。数据实际列：%s'
            % (', '.join(lack), ', '.join(sorted(cols)[:12])))
        return

    if a.get('limit'):
        rows = rows[:int(a['limit'])]

    if a.get('name_from'):
        name_key = a['name_from']
    else:
        # 优先挑像"名字"的列，否则用第一列（不是按字母序瞎选）
        prefer = ('姓名', 'name', '标题', 'title', '学生', '员工', '编号', 'id')
        name_key = None
        for k in rows[0].keys():
            if any(p.lower() == k.lower() or p in k for p in prefer):
                name_key = k
                break
        if not name_key:
            name_key = list(rows[0].keys())[0]
    made = []
    fails = []
    for i, row in enumerate(rows):
        txt = tpl_txt
        for k in ph:
            txt = re.sub(r'\{\{\s*' + re.escape(k) + r'\s*\}\}', str(row.get(k, '')), txt)
        nm = str(row.get(name_key, '') or ('doc%03d' % (i + 1)))
        nm = re.sub(r'[\\/:*?"<>|\s]+', '_', nm)[:40] or ('doc%03d' % (i + 1))
        outp = os.path.join(dest, nm + '.pdf')
        tmpmd = os.path.join(dest, '_tmp_%03d.md' % i)
        with open(tmpmd, 'w', encoding='utf-8') as f:
            f.write(txt)
        arg = {k: v for k, v in a.items()
               if k not in ('data', 'template', 'output_dir', 'limit', 'name_from')}
        arg['md_file'] = tmpmd
        arg['out'] = outp
        if not arg.get('title'):
            arg['title'] = nm
        try:
            r = subprocess.run([sys.executable, os.path.abspath(__file__), 'build',
                                json.dumps(arg, ensure_ascii=False)],
                               capture_output=True, text=True, timeout=300)
            j = json.loads((r.stdout or '{}').strip().split(chr(10))[0] or '{}')
            if j.get('success'):
                made.append(dict(row=i + 1, name=nm, path=outp, pages=j.get('pages')))
            else:
                fails.append(dict(row=i + 1, name=nm, error=str(j.get('error'))[:120]))
        except Exception as e:
            fails.append(dict(row=i + 1, name=nm, error=str(e)[:120]))
        finally:
            try:
                os.remove(tmpmd)
            except Exception:
                pass

    out(output_dir=dest, total=len(rows), made=len(made),
        failed=len(fails), files=made[:50], errors=fails[:20],
        hint=('全部成功' if not fails else '有 %d 份失败，看 errors' % len(fails)))


def cmd_fontcheck(a):
    """检查字体名是否在字体库里（含拼写建议）。"""
    want = a.get('font')
    if not want:
        err('font is required')
    faces, names = _all_faces(a)
    w0 = str(want).strip().lower()
    exact = [n for n in names if n.lower() == w0]
    if exact:
        out(font=exact[0], found=True, exact=True)
        return
    fam, ok = _resolve_family(want, faces, names)
    if ok:
        out(font=fam, found=True, exact=False,
            hint='字体库里有相近的「%s」，请确认拼写' % fam)
        return
    w = str(want).lower()[:4]
    near = [n for n in sorted(names) if w in n.lower()][:6]
    # 三元优先级原来写错了：near 非空时会把「字体库里没有」吞掉
    msg = '字体库里没有这一款。'
    if near:
        msg += '你是不是要：' + ' / '.join(near)
    out(font=want, found=False, suggestions=near, total=len(names), hint=msg)


TABLE = {'lint': cmd_lint, 'fontcov': cmd_fontcov, 'matchfont': cmd_matchfont,
        'fontcheck': cmd_fontcheck, 'splitoutline': cmd_splitoutline,
        'stamp': cmd_stamp, 'encrypt': cmd_encrypt, 'decrypt': cmd_decrypt,
        'optimize': cmd_optimize, 'importdoc': cmd_importdoc, 'batch': cmd_batch,
        'build': cmd_build, 'preview': cmd_preview, 'info': cmd_info, 'merge': cmd_merge, 'split': cmd_split, 'extract': cmd_extract, 'rotate': cmd_rotate, 'text': cmd_text, 'img2pdf': cmd_img2pdf, 'selfcheck': cmd_selfcheck}


def main():
    if len(sys.argv) <2:
        err('usage: core.py <subcommand> [json args]')
    cmd = sys.argv[1]
    fn = TABLE.get(cmd)
    if not fn:
        err('unknown subcommand: %s' % cmd)
    a = {}
    if len(sys.argv) >2:
        try:
            a = json.loads(sys.argv[2])
        except Exception as e:
            err('bad json args: %s' % e)
    try:
        fn(a)
    except SystemExit:
        raise
    except Exception:
        err(traceback.format_exc())


if __name__ == '__main__':
    main()
