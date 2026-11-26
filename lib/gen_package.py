#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#生成 ai_pdf v2（Typst引擎）沙盒包
import base64, hashlib, io, json, os
import collage_doc
import subject_doc

# ============================================================
# ai_pdf 唯一打包入口（真源 = .typst_test/lib）
# 别在别处跑打包脚本：dev_package 下曾有一份 v1.0.0 weasyprint 的
# make_package.py，误跑会让整包退回 12 个工具。已归档到 _archive_v1。
# ============================================================
# LIB 自定位：脚本就在 lib/ 里，用它自己的目录，不写死绝对路径。
# 写死的话别人 clone 下来构建会去读本机路径（上次就是这么漏的）。
LIB = os.path.dirname(os.path.abspath(__file__))
OUT = os.environ.get('AI_PDF_OUT') or '/sdcard/Download/Operit/dev_package/ai_pdf/ai_pdf.js'
os.makedirs(os.path.dirname(OUT), exist_ok=True)

core = open(os.path.join(LIB, 'core.py'), 'rb').read()
md2t = open(os.path.join(LIB, 'md2typst.py'), 'rb').read()
theme = open(os.path.join(LIB, 'theme2.typ'), 'rb').read()
texm = open(os.path.join(LIB, 'texmath.py'), 'rb').read()
mdm = open(os.path.join(LIB, 'mermaid.py'), 'rb').read()
mdm2 = open(os.path.join(LIB, 'mermaid2.py'), 'rb').read()
fxg = open(os.path.join(LIB, 'fxgen.py'), 'rb').read()
qrg = open(os.path.join(LIB, 'qrgen.py'), 'rb').read()
xry = open(os.path.join(LIB, 'pdfxray.py'), 'rb').read()
# v2.3 新增：颜色/色阶/取图三个模块（collage 的自动对比色与 src: 取图依赖它们）
ckit = open(os.path.join(LIB, 'colorkit.py'), 'rb').read()
okl = open(os.path.join(LIB, 'oklch.py'), 'rb').read()
isrc = open(os.path.join(LIB, 'imgsrc.py'), 'rb').read()
# 打包器必须把自己也辞进包：否则 runtime 里的 gen_package.py 永远是旧版，
# 审查者/AI 去读那份会被误导（实测 runtime 副本停在只算 5 个文件的旧逻辑）。
# 注意：不能把自身算进 ver，那是自引用（需要算自己的 hash 才能算自己的 hash），
# 单独用 .gnpver 控制自嵌文件的重写。
_SELF = os.path.abspath(__file__)
gnp_raw = open(_SELF, 'rb').read()
# 内嵌副本的 LIB 必须写成真实部署路径：AI 在手机上读 runtime/gen_package.py
# 时要能看到实际路径，而不是构建机的临时目录。
gnp = gnp_raw.replace(
    b"LIB = os.path.dirname(os.path.abspath(__file__))",
    b"LIB = '/sdcard/Download/.typst_test/lib'")
if gnp == gnp_raw:
    print('NOTE: LIB 行未替换（可能已是绝对路径）')
gnpver = hashlib.sha256(gnp).hexdigest()[:16]
ver = hashlib.sha256(core + md2t + theme + texm + mdm + mdm2 + fxg + qrg + xry).hexdigest()[:16]
print('version', ver, 'gnpver', gnpver, 'sizes', len(core), len(md2t), len(theme))

# 组件数量不能写死：之前写「11类组件」实际早已 31 类，描述一直在撒谎。
# 从 md2typst 的分发分支实时推导，加新组件时描述自动跟上。
import re as _re
_md2src = md2t.decode('utf-8') if isinstance(md2t, bytes) else md2t
_elif = _re.findall(r"elif\s+name\s*==\s*['\"]([^'\"]+)['\"]", _md2src)
_groups = _re.findall(r"name\s+in\s*\(([^)]*)\)", _md2src)
_comp_main = list(_elif)
_comp_alias = len(_elif)
for _g in _groups:
    _al = _re.findall(r"['\"]([a-z0-9_-]+)['\"]", _g)
    _comp_alias += len(_al)
    if _al:
        _comp_main.append(_al[0])
COMP_COUNT = len(_comp_main)
COMP_ALIAS = _comp_alias
print('components', COMP_COUNT, 'names/aliases', COMP_ALIAS)

PARAMS = [
 ('output_path', '输出 PDF的完整路径，如 /sdcard/Download/report.pdf', True),
 ('content', 'Markdown正文（默认）。支持标题/表格/列表/引用/代码块/任务清单，以及下方 %d 类组件 div（%d 个名字/别名，完整清单见 COMPONENTS）。' % (COMP_COUNT, COMP_ALIAS), False),
 ('input_path', '也可传已有 .md文件路径，代替 content', False),
 ('input_format', 'markdown（默认）或 html（按原始 HTML处理）', False),
 ('theme', '版式：report(报告讲义/宋体/默认)、handout(黑体紧凑)、resume(简历)、editorial(杂志/楷体)、minimal(极简)、certificate(证书)、slide(PPT幻灯片/16:9横版/每个#一级标题=一页)', False),
 ('palette', '配色：blue(默认)、ink(墨黑)、forest(森绿)、clay(陶土)、plum(梅紫)、gold(金曜)', False),
 ('page_size', '纸张：a4(默认)、a5、a3、b5、letter', False),
 ('margin', '页边距，如22mm /22mm20mm(上下左右) /20mm18mm22mm18mm。不填用主题默认', False),
 ('base_size', '正文字号，如11pt /10.5pt /9pt。不填用主题默认', False),
 ('leading', '行距，如0.72em /1.0em。不填用主题默认', False),
 ('font_body', '正文字体，如 Noto Serif CJK SC / Noto Sans CJK SC / LXGW WenKai，不填用主题默认', False),
 ('font_head', '标题字体，同上', False),
 ('header_text', '页眉文字（默认用 title）', False),
 ('page_numbers', '是否显示页码：true(默认)/false', False),
 ('watermark', '水印文字，如内部资料。留空不显示', False),
 ('title', '文档标题，用于页眉与封面', False),
 ('subtitle', '封面副标题', False),
 ('kicker', '封面顶部胶囊标签，如高中数学 ·复习讲义', False),
 ('cover_meta', '封面底部信息行，可含简单 HTML', False),
 ('cover_cards', '封面装饰卡片，格式标题::说明|标题::说明，最多3个，用来填满封面下半部', False),
 ('cover', '是否生成封面页：true/false(默认)', False),
 ('font_dir', '额外字体目录，多个用 : 分隔。默认已包含内置字体库，一般不用填', False),
 ('extra_typst', '追加原生 Typst代码（高级逃生口，默认不用）', False),
]

COMPONENTS = (
 '组件写法（写在 content里，fenced div，每行用 |分隔字段）：'
 '::: kpi值|说明 （KPI数据卡一行，可多条）'
 '::: badges标签|primary （徽章，变体 primary/success/warn/danger/neutral/soft）'
 '::: callout warn标题正文 （六色提示框，变体 note/info/success/warn/danger/quote）'
 '::: cards2 ###卡片标题正文 （卡片网格，数字为列数）'
 '::: compare ###左侧标题内容 ###右侧标题内容 （对比双栏）'
 '::: progress名称|百分比 （进度条）'
 '::: ring名称|百分比 （环形进度，一行最多3个）'
 '::: wrap首行写 位置|宽|高 （文字环绕，位置取 left-top/right-top/left-bottom/right-bottom，宽高带单位如42mm）'
 '::: vertical2／vertical3数字是列数 （竖排，从右往左，可加 size=10pt gap=3pt）'
 '::: rating名称|分值 （评分方块，满分5）'
 '::: chart标签|数值 （横条图）'
 '::: timeline时间|说明 （时间线）'
 '::: steps每行一个步骤 （编号步骤）'
 '::: defs术语|定义 （定义表）'
 '【统一样式参数】以下三个参数可加在 cards/compare/price/team/capsule 等组件后：'
 '  style=flat|shadow|glass|gradient|outline （阴影/玻璃/渐变/描边）'
 '  radius=0|4|8|pill （圆角）'
 '  tone=primary|success|warn|danger|neutral|soft （配色）'
 '  例：::: cards2 style=shadow radius=8 tone=success'
 '【胶囊标题】::: capsule 标题文字 （可加 tone=danger solid=false）'
 '【商业组件】'
 '::: qrcode 内容|说明 （真实可扫二维码，说明可省）'
 '::: price 套餐|价格|功能1,功能2,功能3|推荐标签 （推荐标签可省，最后一行可标"推荐"）'
 '::: faq 问题|答案 （每行一组问答）'
 '::: team 姓名|职位|简介 （每行一人，最多3列）'
 '::: invoice 品名|数量|单价 （每行一项，小计与合计自动算）'
 '::: cert name|张三 title|证书名 body|正文 org|署名单位 date|日期 serial|编号 （每行 键|值）'
 '::: resume 时间|标题|描述 （简历时间线，描述可省）'
 '::: skills 标签1|标签2|标签3 （技能标签组）'
 '::: menu 菜品|价格|备注 （菜单，备注可省）'
 '::: poster hero|主标题 sub|副标题 when|时间 where|地点 note|补充 （海报主视觉，每行 键|值）'
 '【特效】SVG 只做装饰，文字仍由 Typst 排（可选中可搜索）。程度全部可调：'
 '::: fx glow tone=primary strength=82 width=2pt （泛光：strength=描边透明度 0~100，越大越淡；width=描边粗细）'
 '::: fx frost opacity=12 light=45 bar=2.5pt border=0.9pt （磨砂：opacity=底色不透明 0~100 越大越实；light=高光条透明度；bar=高光条宽；border=边框粗）'
 '::: fx noise alpha=0.12 （噪点：alpha=颗粒浓度 0~1，写 30 也行=30%）'
 '::: fx gradient c1=2547A8 c2=7C3AED angle=135 strength=0.85 （流体渐变：angle=光斑角度 0~360；strength=浓度 0~1）'
 '::: fx wave amp=8 color=EEF2F9 （波浪分割线：amp=波幅 1~40）'
 '::: curve M10,70 C60,20 140,95 270,30 （自定义曲线，写 SVG path，可加 color=BE123C width=3）'
 '阴影程度：::: cards2 style=shadow sh-depth=2.5pt sh-spread=1.5pt sh-tint=dark （sh-depth=向下偏移 0.5~12pt；sh-spread=右下外扩 0~8pt；sh-tint=light|mid|dark 或 6 位十六进制）'
 '【行内颜色】[文字]{color=danger} 语义色；[文字]{color=#BE123C} 指定十六进制；[文字]{gradient=true} 渐变字。'
 '::: pagebreak （强制分页，空内容）'
 '::: toc （自动目录，空内容）'
 '''
''' + collage_doc.COLLAGE_DOC + '''
''' + subject_doc.SUBJECT_DOC + '''
'''
 '**每个 ::: 必须配对闭合**：开头 ::: progress 换行写数据，结尾单独一行 :::。漏了闭合后面全乱。'
 '行内：[重点]{.badge .primary}徽章；==高亮==荧光标记。'
 '按字体：[文字]{.font-Cinzel} 改单段字体（名字里的空格写下划线）；::: font-Cinzel 到 ::: 之间整块换字体。'
  '数学公式：直接写 LaTeX，工具会自动转 Typst。行内 $E=mc^2$，行间 $$\\frac{a}{b}$$；' '支持 frac/sqrt/sqrt[n]/sum/int/lim/matrix/greek/text{}/hat/vec，不用自己写 Typst 数学语法。'
  '【theme=slide 幻灯片专属】每个 # 一级标题 = 一页，自动加蓝底白字页眉条并分页，不用写 ::: pagebreak。'
  '可用版式（数据行同样用 | 分隔）：'
  '::: slide-cover 标题|副标题|胶囊标签|底部信息 （封面页，放第一个）'
  '::: slide-section 编号|标题|备注 （章节分隔页，满屏渐变）'
  '::: slide-quote 引言正文|署名 （居中大引言）'
  '::: slide-cols 标题|正文 （每行一组，默认3栏，可写 cols=2/4/5/6）'
  '::: slide-stats 数值|说明|颜色 （大数字卡，默认2栏，颜色如 #1F7A5C，可省略）'
  '::: slide-compare 左标题|左正文|右标题|右正文 （单行4列；也支持两行各2列）'
  '::: slide-flow 标题|说明 （每行一步，带编号圆点和连接线；numbered=false 改圆点）'
  '::: slide-split 左栏内容 --- 右栏内容 （两栏，中间单独一行 --- 分隔；可加 side=left）'
)

tools = []
tools.append({
 'name': 'make_pdf',
 'description': {
 'zh': ('【做PDF就用这个】Markdown一步生成中文精排 PDF。引擎 Typst，速度约0.6-1秒。'
 '可选封面、6主题、6配色，字号/行距/边距/字体全部可调。'
 + COMPONENTS +
 '生成后务必再调 render_pdf_preview看一眼确认不丑（这一步不能省）。'),
 'en': 'Primary PDF builder (Typst engine, ~1s). Markdown to typeset Chinese PDF with cover,6 themes,6 palettes; sizes/margins/fonts tunable;11 component divs. Always call render_pdf_preview afterwards.'},
 'parameters': [{'name': n, 'description': {'zh': d, 'en': d}, 'type': 'string', 'required': r}
 for n, d, r in PARAMS]})

tools.append({
 'name': 'render_pdf_preview',
 'description': {'zh': '把 PDF指定页渲染成 PNG用于自检。make_pdf之后必做：拿到路径后用 read_file(direct_image=true)真正看图，确认无错位/溢出/空白页再交付。',
 'en': 'Render PDF pages to PNG for visual self-check after make_pdf.'},
 'parameters': [
 {'name': 'pdf_path', 'description': {'zh': 'PDF路径', 'en': 'PDF path'}, 'type': 'string', 'required': True},
 {'name': 'output_dir', 'description': {'zh': 'PNG输出目录，默认 /sdcard/Download/.ai_pdf_preview', 'en': 'Output dir'}, 'type': 'string', 'required': False},
 {'name': 'pages', 'description': {'zh': '页码：1 /1-3 /1,4 / all，默认第1页', 'en': 'Pages'}, 'type': 'string', 'required': False},
 {'name': 'dpi', 'description': {'zh': '分辨率，默认110', 'en': 'DPI'}, 'type': 'string', 'required': False}]})

tools.append({
 'name': 'list_pdf_themes',
 'description': {'zh': '列出可用主题、配色与组件写法说明。不确定选哪个主题时先调它。',
 'en': 'List themes, palettes and component syntax.'},
 'parameters': []})

tools.append({
 'name': 'pdf_info',
 'description': {'zh': '读 PDF信息：页数、实际尺寸(mm)、横竖、文件大小、元数据。',
 'en': 'PDF info.'},
 'parameters': [{'name': 'pdf_path', 'description': {'zh': 'PDF路径', 'en': 'PDF path'}, 'type': 'string', 'required': True}]})

tools.append({
 'name': 'merge_pdfs',
 'description': {'zh': '按顺序合并多个 PDF。', 'en': 'Merge PDFs in order.'},
 'parameters': [
 {'name': 'output_path', 'description': {'zh': '输出路径', 'en': 'Output'}, 'type': 'string', 'required': True},
 {'name': 'input_paths', 'description': {'zh': '输入 PDF路径数组', 'en': 'Input paths'}, 'type': 'array', 'required': True}]})

tools.append({
 'name': 'split_pdf',
 'description': {'zh': '按页范围拆分 PDF；ranges留空则逐页拆。', 'en': 'Split by ranges.'},
 'parameters': [
 {'name': 'pdf_path', 'description': {'zh': '源 PDF', 'en': 'Source'}, 'type': 'string', 'required': True},
 {'name': 'output_dir', 'description': {'zh': '输出目录', 'en': 'Out dir'}, 'type': 'string', 'required': True},
 {'name': 'ranges', 'description': {'zh': '如1-3,4-6', 'en': 'Ranges'}, 'type': 'string', 'required': False}]})

tools.append({
 'name': 'extract_pdf_pages',
 'description': {'zh': '抽取指定页另存为新 PDF。', 'en': 'Extract pages.'},
 'parameters': [
 {'name': 'pdf_path', 'description': {'zh': '源 PDF', 'en': 'Source'}, 'type': 'string', 'required': True},
 {'name': 'output_path', 'description': {'zh': '输出路径', 'en': 'Output'}, 'type': 'string', 'required': True},
 {'name': 'pages', 'description': {'zh': '如1-3,7', 'en': 'Pages'}, 'type': 'string', 'required': True}]})

tools.append({
 'name': 'rotate_pdf_pages',
 'description': {'zh': '旋转指定页，修正扫描件方向。', 'en': 'Rotate pages.'},
 'parameters': [
 {'name': 'pdf_path', 'description': {'zh': '源 PDF', 'en': 'Source'}, 'type': 'string', 'required': True},
 {'name': 'output_path', 'description': {'zh': '输出路径', 'en': 'Output'}, 'type': 'string', 'required': True},
 {'name': 'pages', 'description': {'zh': '默认 all', 'en': 'Pages'}, 'type': 'string', 'required': False},
 {'name': 'degrees', 'description': {'zh': '90/180/270，默认90', 'en': 'Degrees'}, 'type': 'string', 'required': False}]})

tools.append({
 'name': 'compress_pdf',
 'description': {'zh': '压缩 PDF体积，返回压缩前后字节数与压缩率。', 'en': 'Compress PDF.'},
 'parameters': [
 {'name': 'pdf_path', 'description': {'zh': '源 PDF', 'en': 'Source'}, 'type': 'string', 'required': True},
 {'name': 'output_path', 'description': {'zh': '输出路径', 'en': 'Output'}, 'type': 'string', 'required': True},
 {'name': 'quality', 'description': {'zh': 'screen/ebook(默认)/printer', 'en': 'Quality'}, 'type': 'string', 'required': False}]})

tools.append({
 'name': 'images_to_pdf',
 'description': {'zh': '多张图片合成一个 PDF，每张一页，自动缩放居中。', 'en': 'Images to PDF.'},
 'parameters': [
 {'name': 'output_path', 'description': {'zh': '输出路径', 'en': 'Output'}, 'type': 'string', 'required': True},
 {'name': 'image_paths', 'description': {'zh': '图片路径数组', 'en': 'Images'}, 'type': 'array', 'required': True},
 {'name': 'page_size', 'description': {'zh': 'a4(默认)或 fit', 'en': 'Page size'}, 'type': 'string', 'required': False}]})

tools.append({
 'name': 'extract_pdf_text',
 'description': {'zh': '按页提取 PDF文字。', 'en': 'Extract text.'},
 'parameters': [
 {'name': 'pdf_path', 'description': {'zh': 'PDF路径', 'en': 'Path'}, 'type': 'string', 'required': True},
 {'name': 'pages', 'description': {'zh': '页范围，留空全部', 'en': 'Pages'}, 'type': 'string', 'required': False}]})

tools.append({
 'name': 'pdf_selfcheck',
 'description': {'zh': '检查引擎是否就绪：typst二进制、pandoc、PyMuPDF、主题文件。首次使用或报错时先跑它。',
 'en': 'Check engine readiness.'},
 'parameters': []})

tools.append({
 'name': 'pdf_lint',
 'description': {'zh': '程序化版式体检：查空白页、文字溢出页边界、贴边、图片分辨率过低、页面尺寸不一致、字体未嵌入。比人眼看图更靠谱，交付前跑一次。注意：只查几何与字体，不查内容完整性——组件被压穿、元素重叠、文字被裁、豆腐块都可能 0 errors，仍需看图确认。【查不出对比度】白字压浅色云海只有 1.9:1，本工具报 0 errors 但人眼看不清。要验可读性：渲染 PNG 后取字内像素 RGB 众数算 WCAG 对比度（≥4.5）。根治是「浅色半透明条+深色字」，不要白字硬压图。详见 pdfxray.py 顶部注释。',
  'en': 'Programmatic layout lint: blank pages, text overflow, near-edge, low-DPI images, page size mismatch, non-embedded fonts. Geometry/font checks only, NOT content integrity — overlaps, clipping, tofu boxes can still pass with 0 errors; inspect the rendered page.'},
 'parameters': [
  {'name': 'pdf_path', 'description': {'zh': 'PDF 路径', 'en': 'PDF 路径'}, 'type': 'string', 'required': True},
  {'name': 'tol_mm', 'description': {'zh': '溢出容差毫米，默认2', 'en': '溢出容差毫米，默认2'}, 'type': 'string', 'required': False},
  {'name': 'min_dpi', 'description': {'zh': '图片最低 dpi，默认150', 'en': '图片最低 dpi，默认150'}, 'type': 'string', 'required': False},
 ]})
tools.append({
 'name': 'pdf_xray',
 'description': {'zh': '把 PDF 解析成你能直接读的结构，不用看图。每页给出三块：① 布局字符画（形状画边框、文字显示原字，坐标就是真实坐标）② 可疑项（文字跨越边框/文字重叠/出界/豆腐块，带精确 pt 数）③ 特效清单（阴影偏移量、磨砂透明度、泛光描边透明度、渐变处数、噪点图尺寸、曲线路径）+ 逐元素坐标/尺寸/颜色/字号。用来回答「我写的东西放出来长什么样」：卡片有没有压边框、两列间距多少、颜色有没有生效、阴影多重。注意它读的是几何与绘制指令，看不到「好不好看」，审美仍需人判断。【量坐标前必读】① dot/ring 的 size 是半径不是直径；② img 带 shape= 时图像 bbox 是裁切前尺寸（声明 70mm 实测 121mm），不能拿来判重叠；③ alpha 是透明度百分比（0=不透明）；④ block 高度由内容自动撑开，要接元素先拿本工具量真实 bbox；⑤ 中文字体无 italic，用 skew=。完整 13 条见 pdfxray.py 顶部注释。',
  'en': 'Parse a PDF into structure you can read directly, no image recognition. Per page: (1) layout ASCII art (shapes as borders, real text at real coordinates) (2) anomalies with exact pt values (text crossing a border / overlapping text / out of page / tofu) (3) effects inventory (shadow offset, frost opacity, glow stroke opacity, gradient count, noise bitmap size, curve paths) plus per-element bbox/color/size. Answers "what does my markup actually render as": did text cross a card border, how wide is the gutter, did my color apply, how heavy is the shadow. It reads geometry and draw ops only — aesthetics still need a human.'},
 'parameters': [
  {'name': 'pdf_path', 'description': {'zh': 'PDF 路径', 'en': 'PDF path'}, 'type': 'string', 'required': True},
  {'name': 'pages', 'description': {'zh': '页码：1 / 1-3 / 1,4 / all，默认第1页', 'en': 'Pages: 1 / 1-3 / 1,4 / all. Default first page.'}, 'type': 'string', 'required': False},
  {'name': 'cols', 'description': {'zh': '字符画宽度（列），默认72。越大越精细但行越长', 'en': 'ASCII art width in columns, default 72.'}, 'type': 'string', 'required': False},
  {'name': 'detail', 'description': {'zh': 'full(默认，图+可疑+特效+元素) / art(只要字符画) / brief(可疑+特效，不要字符画)', 'en': 'full(default) / art / brief'}, 'type': 'string', 'required': False},
 ]})
tools.append({
 'name': 'check_font_coverage',
 'description': {'zh': '检查指定字体是否覆盖文本里每一个字（防生僻字变豆腐块）。text 和 input_path 二选一。',
  'en': 'Check whether a font covers every character in the text (prevents tofu boxes).'},
 'parameters': [
  {'name': 'text', 'description': {'zh': '要检查的文本', 'en': '要检查的文本'}, 'type': 'string', 'required': False},
  {'name': 'input_path', 'description': {'zh': '或传 md/pdf 路径', 'en': '或传 md/pdf 路径'}, 'type': 'string', 'required': False},
  {'name': 'font', 'description': {'zh': '字体 family 名，如 Source Han Serif SC', 'en': '字体 family 名，如 Source Han Serif SC'}, 'type': 'string', 'required': True},
 ]})
tools.append({
 'name': 'match_font',
 'description': {'zh': '给一段文字，按字形覆盖度推荐字体库里最合适的几款字体。',
  'en': 'Given text, rank fonts in the library by glyph coverage.'},
 'parameters': [
  {'name': 'text', 'description': {'zh': '文本', 'en': '文本'}, 'type': 'string', 'required': False},
  {'name': 'input_path', 'description': {'zh': '或传 md/pdf 路径', 'en': '或传 md/pdf 路径'}, 'type': 'string', 'required': False},
 ]})
tools.append({
 'name': 'check_font_exists',
 'description': {'zh': '检查字体名在字体库里存不存在，写错时给拼写建议。注意 Noto Serif/Sans CJK SC 是系统字体，不在项目库内。',
  'en': 'Check if a font family exists in the built-in library, with spelling suggestions.'},
 'parameters': [
  {'name': 'font', 'description': {'zh': '字体 family 名', 'en': '字体 family 名'}, 'type': 'string', 'required': True},
 ]})
tools.append({
 'name': 'split_by_outline',
 'description': {'zh': '按 PDF 自带书签（标题大纲）拆成多个 PDF，每个一级标题一册。源文档必须有分页，否则会提示无法拆。',
  'en': 'Split PDF by its own outline/bookmarks (one file per heading).'},
 'parameters': [
  {'name': 'pdf_path', 'description': {'zh': 'PDF 路径', 'en': 'PDF 路径'}, 'type': 'string', 'required': True},
  {'name': 'output_dir', 'description': {'zh': '输出目录', 'en': '输出目录'}, 'type': 'string', 'required': False},
  {'name': 'level', 'description': {'zh': '拆到第几层书签，默认1', 'en': '拆到第几层书签，默认1'}, 'type': 'string', 'required': False},
 ]})
tools.append({
 'name': 'stamp_pdf',
 'description': {'zh': '给 PDF 每页叠加页眉/页脚/页码/水印。中文会自动选 TTF 并做字体子集化（用 OTF 会让文件涨到 20MB）。已有页码时默认不重复加。',
  'en': 'Overlay header/footer/page numbers/watermark on every page. Auto-picks a TTF and subsets fonts.'},
 'parameters': [
  {'name': 'pdf_path', 'description': {'zh': 'PDF 路径', 'en': 'PDF 路径'}, 'type': 'string', 'required': True},
  {'name': 'output_path', 'description': {'zh': '输出路径', 'en': '输出路径'}, 'type': 'string', 'required': False},
  {'name': 'header', 'description': {'zh': '页眉文字', 'en': '页眉文字'}, 'type': 'string', 'required': False},
  {'name': 'footer', 'description': {'zh': '页脚文字', 'en': '页脚文字'}, 'type': 'string', 'required': False},
  {'name': 'watermark', 'description': {'zh': '水印文字', 'en': '水印文字'}, 'type': 'string', 'required': False},
  {'name': 'size', 'description': {'zh': '字号，默认8', 'en': '字号，默认8'}, 'type': 'string', 'required': False},
  {'name': 'offset', 'description': {'zh': '边距毫米，默认10', 'en': '边距毫米，默认10'}, 'type': 'string', 'required': False},
  {'name': 'color', 'description': {'zh': '颜色 #888888', 'en': '颜色 #888888'}, 'type': 'string', 'required': False},
  {'name': 'page_numbers', 'description': {'zh': '是否加页码，默认 true', 'en': '是否加页码，默认 true'}, 'type': 'boolean', 'required': False},
 ]})
tools.append({
 'name': 'encrypt_pdf',
 'description': {'zh': 'PDF 加密（AES-256/128、RC4）。加密后自动自检确认真的受保护。密码忘了无法恢复。',
  'en': 'Encrypt PDF (AES-256/128, RC4) with self-verification.'},
 'parameters': [
  {'name': 'pdf_path', 'description': {'zh': 'PDF 路径', 'en': 'PDF 路径'}, 'type': 'string', 'required': True},
  {'name': 'password', 'description': {'zh': '打开密码', 'en': '打开密码'}, 'type': 'string', 'required': True},
  {'name': 'output_path', 'description': {'zh': '输出路径', 'en': '输出路径'}, 'type': 'string', 'required': False},
  {'name': 'owner_password', 'description': {'zh': '权限密码，默认同打开密码', 'en': '权限密码，默认同打开密码'}, 'type': 'string', 'required': False},
  {'name': 'algorithm', 'description': {'zh': 'aes-256(默认)/aes-128/rc4-128/rc4-40', 'en': 'aes-256(默认)/aes-128/rc4-128/rc4-40'}, 'type': 'string', 'required': False},
  {'name': 'allow_copy', 'description': {'zh': '允许复制，默认 true', 'en': '允许复制，默认 true'}, 'type': 'boolean', 'required': False},
  {'name': 'allow_modify', 'description': {'zh': '允许修改，默认 false', 'en': '允许修改，默认 false'}, 'type': 'boolean', 'required': False},
 ]})
tools.append({
 'name': 'decrypt_pdf',
 'description': {'zh': 'PDF 去密码。密码不对会明确报错。',
  'en': 'Remove PDF password.'},
 'parameters': [
  {'name': 'pdf_path', 'description': {'zh': 'PDF 路径', 'en': 'PDF 路径'}, 'type': 'string', 'required': True},
  {'name': 'password', 'description': {'zh': '密码', 'en': '密码'}, 'type': 'string', 'required': False},
  {'name': 'output_path', 'description': {'zh': '输出路径', 'en': '输出路径'}, 'type': 'string', 'required': False},
 ]})
tools.append({
 'name': 'optimize_pdf',
 'description': {'zh': 'PDF 体积优化：字体子集化 + 对象清理 + 可选 Ghostscript 压图。返回压缩前后字节数与压缩率。',
  'en': 'Reduce PDF size: font subsetting, object cleanup, optional Ghostscript image compression.'},
 'parameters': [
  {'name': 'pdf_path', 'description': {'zh': 'PDF 路径', 'en': 'PDF 路径'}, 'type': 'string', 'required': True},
  {'name': 'output_path', 'description': {'zh': '输出路径', 'en': '输出路径'}, 'type': 'string', 'required': False},
  {'name': 'subset_fonts', 'description': {'zh': '字体子集化，默认 true', 'en': '字体子集化，默认 true'}, 'type': 'boolean', 'required': False},
  {'name': 'gs_compress', 'description': {'zh': '是否再用 Ghostscript 压，默认 false', 'en': '是否再用 Ghostscript 压，默认 false'}, 'type': 'boolean', 'required': False},
  {'name': 'quality', 'description': {'zh': 'screen/ebook(默认)/printer', 'en': 'screen/ebook(默认)/printer'}, 'type': 'string', 'required': False},
 ]})
tools.append({
 'name': 'import_document',
 'description': {'zh': '把 docx / odt / html / xlsx 转成 Markdown，之后交给 make_pdf 出 PDF。',
  'en': 'Convert docx/odt/html/xlsx to Markdown for make_pdf.'},
 'parameters': [
  {'name': 'input_path', 'description': {'zh': '源文件路径', 'en': '源文件路径'}, 'type': 'string', 'required': True},
  {'name': 'output_path', 'description': {'zh': '输出 .md 路径', 'en': '输出 .md 路径'}, 'type': 'string', 'required': False},
 ]})
tools.append({
 'name': 'batch_pdf',
 'description': {'zh': '批量生成：CSV 或 JSON 的行数据 + 含 {{列名}} 占位的 Markdown 模板，一次产出多份 PDF。文件名默认取「姓名/name/标题」列。',
  'en': 'Batch generate PDFs from CSV/JSON rows + a Markdown template with {{column}} placeholders.'},
 'parameters': [
  {'name': 'data_path', 'description': {'zh': 'CSV 或 JSON 路径', 'en': 'CSV 或 JSON 路径'}, 'type': 'string', 'required': True},
  {'name': 'template_path', 'description': {'zh': '含 {{列名}} 占位的 .md 路径', 'en': '含 {{列名}} 占位的 .md 路径'}, 'type': 'string', 'required': True},
  {'name': 'output_dir', 'description': {'zh': '输出目录', 'en': '输出目录'}, 'type': 'string', 'required': False},
  {'name': 'name_from', 'description': {'zh': '用哪一列做文件名', 'en': '用哪一列做文件名'}, 'type': 'string', 'required': False},
  {'name': 'limit', 'description': {'zh': '只生成前 N 份', 'en': '只生成前 N 份'}, 'type': 'string', 'required': False},
  {'name': 'theme', 'description': {'zh': '版式，同 make_pdf', 'en': '版式，同 make_pdf'}, 'type': 'string', 'required': False},
  {'name': 'palette', 'description': {'zh': '配色，同 make_pdf', 'en': '配色，同 make_pdf'}, 'type': 'string', 'required': False},
 ]})

meta = {
 'name': 'ai_pdf',
 'version': '2.5.0',
 'display_name': {'zh': 'AI生成 PDF', 'en': 'AI PDF Maker'},
 'description': {
 'zh': ('写 Markdown出可打印的中文排版 PDF，Typst引擎。'
 '主题、配色、字号、边距、字体全可调，也支持整页自由拼贴；'
 '函数图、化学结构式、流程图用 ::: draw写 Typst，所需包已内置。'
 '自带 lint、xray、预览三种自检。'),
 'en': 'Markdown in, print-ready Chinese PDF out, powered by Typst. '
 'Theme, palette, size, margin and font all tunable; full-page free collage supported. '
 'Math plots, chemical structures and flowcharts via ::: draw, with needed packages bundled. '
 'Includes lint, xray and preview self-checks.'},
 'enabledByDefault': True,
 'category': 'File',
 'author': ['Operit'],
 'tools': tools,
}

JS = r'''/* METADATA
__META__
*/

const RUNTIME = '/sdcard/Download/.ai_pdf_runtime';
const CORE = RUNTIME + '/core.py';
const MD2T = RUNTIME + '/md2typst.py';
const THEME = RUNTIME + '/theme2.typ';
const TEXM = RUNTIME + '/texmath.py';
const MDM = RUNTIME + '/mermaid.py';
const MDM2 = RUNTIME + '/mermaid2.py';
const FXG = RUNTIME + '/fxgen.py';
const QRG = RUNTIME + '/qrgen.py';
const GNP = RUNTIME + '/gen_package.py';
const XRY = RUNTIME + '/pdfxray.py';
const CKIT = RUNTIME + '/colorkit.py';
const OKL = RUNTIME + '/oklch.py';
const ISRC = RUNTIME + '/imgsrc.py';
const ERRORLOG = RUNTIME + '/last_error.log';
const VERFILE = RUNTIME + '/.ver';
const VER = '__VER__';
const CORE_B64 = '__CORE__';
const MD2T_B64 = '__MD2T__';
const THEME_B64 = '__THEME__';
const TEXM_B64 = '__TEXM__';
const MDM_B64 = '__MDM__';
const MDM2_B64 = '__MDM2__';
const FXG_B64 = '__FXG__';
const QRG_B64 = '__QRG__';
const GNP_B64 = '__GNP__';
const XRY_B64 = '__XRY__';
const CKIT_B64 = '__CKIT__';
const OKL_B64 = '__OKL__';
const ISRC_B64 = '__ISRC__';
const GNPVERFILE = RUNTIME + '/.gnpver';
const GNPVER = '__GNPVER__';
const LIBS_B64 = '__LIBS__';
const LOCAL_TYPST = [
 '/sdcard/Download/.typst_test/typst-aarch64-unknown-linux-musl/typst',
 '/sdcard/Download/typst',
 '/sdcard/Download/.ai_pdf_runtime/typst',
];
const DL_URL = 'https://github.com/typst/typst/releases/download/v0.15.1/typst-aarch64-unknown-linux-musl.tar.xz';

function q(s) {
 return "'" + String(s == null ? '' : s).replace(/'/g, "'\"'\"'") + "'";
}

async function sh(cmd, timeoutMs) {
 const r = await Tools.System.terminal.hiddenExec(cmd, {
 executorKey: 'ai_pdf',
 timeoutMs: timeoutMs ||180000
 });
 return { code: (r && r.exitCode), out: String((r && r.output) || '') };
}

function pickJson(raw) {
 const lines = String(raw || '').split('\n');
 for (let i = lines.length -1; i >=0; i--) {
 const s = lines[i].trim();
 if (s.charAt(0) === '{') {
 try { return JSON.parse(s); } catch (e) { }
 }
 }
 return null;
}

async function ensureTypst() {
 let r = await sh('test -x /root/bin/typst && echo HAVE_TYPST',30000);
 if (r.out.indexOf('HAVE_TYPST') >=0) return true;
 const paths = LOCAL_TYPST.map(q).join(' ');
 r = await sh('for f in ' + paths + '; do if [ -f "$f" ]; then mkdir -p /root/bin && cp "$f" /root/bin/typst && chmod +x /root/bin/typst && echo COPIED && break; fi; done',60000);
 if (r.out.indexOf('COPIED') >=0) return true;
 r = await sh('cd /tmp && curl -sL -m300 -o t.tar.xz ' + q(DL_URL) + ' && tar -xf t.tar.xz && mkdir -p /root/bin && cp typst-aarch64-unknown-linux-musl/typst /root/bin/typst && chmod +x /root/bin/typst && echo DL_OK',360000);
 if (r.out.indexOf('DL_OK') >=0) return true;
 throw new Error('typst binary unavailable; put it at /root/bin/typst (download: ' + DL_URL + ')');
}

const PKG_DIR = RUNTIME + '/typst-packages';

// 内嵌的 typst 库（gzip+b64 单条）解包到 RUNTIME/typst-packages/
// 解包后 core.py 用 --package-path 指向它，@local/meander、@local/basho 即可用
// 内嵌 typst包解包。
//之前是 Python 逐文件写（267 次 open/write），在 /sdcard（FUSE）上实测约18s。
//改成写一个 tar.gz 再 tar xzf 一次解，减少 syscall 次数。
async function unpackLibs() {
 await Tools.Files.mkdir(PKG_DIR, true);
 const tgz = RUNTIME + "/_libs.tar.gz";
 await Tools.Files.writeBinary(tgz, LIBS_B64);
 const r = await sh("tar xzf " + q(tgz) + " -C " + q(PKG_DIR) + " && echo UNPACKED",180000);
 if (r.out.indexOf("UNPACKED") <0) throw new Error("typst库解包失败：" + String(r.out || "").slice(0,300));
 try { await sh("rm -f " + q(tgz),20000); } catch (e) {}
}
let ready = false;

async function ensure() {
 if (ready) return;
 await Tools.Files.mkdir(RUNTIME, true);
 let need = true;
 try {
 const v = await Tools.Files.read(VERFILE);
 need = String((v && v.content) || '').trim() !== VER;
 } catch (e) { need = true; }
 if (need) {
 await Tools.Files.writeBinary(CORE, CORE_B64);
 await Tools.Files.writeBinary(MD2T, MD2T_B64);
 await Tools.Files.writeBinary(THEME, THEME_B64);
 await Tools.Files.writeBinary(TEXM, TEXM_B64);
 await Tools.Files.writeBinary(MDM, MDM_B64);
 await Tools.Files.writeBinary(MDM2, MDM2_B64);
 await Tools.Files.writeBinary(FXG, FXG_B64);
 await Tools.Files.writeBinary(QRG, QRG_B64);
 await Tools.Files.writeBinary(CKIT, CKIT_B64);
 await Tools.Files.writeBinary(OKL, OKL_B64);
 await Tools.Files.writeBinary(ISRC, ISRC_B64);
 await unpackLibs();
 await Tools.Files.write(VERFILE, VER);
 }
 // GNP/XRY 单独用 GNPVER 管版本，不能嵌在上面的 if (need) 里。
 // 之前那样写：只改 pdfxray.py 时 .ver 不变（因为 .ver 是 8 个核心文件的 hash），
 // need=false，于是 XRY 永远不更新，改了半天没生效。
 let needGnp = true;
 try {
 const gv = await Tools.Files.read(GNPVERFILE);
 needGnp = String((gv && gv.content) || '').trim() !== GNPVER;
 } catch (e) { needGnp = true; }
 if (needGnp) {
 await Tools.Files.writeBinary(GNP, GNP_B64);
 await Tools.Files.writeBinary(XRY, XRY_B64);
 await Tools.Files.write(GNPVERFILE, GNPVER);
 }
 await ensureTypst();
 ready = true;
}

async function call(sub, args, timeoutMs) {
 const payload = JSON.stringify(args || {});
 const cmd = 'cd ' + q(RUNTIME) + ' && python3 core.py ' + sub + ' ' + q(payload);
 const r = await sh(cmd, timeoutMs ||300000);
 const j = pickJson(r.out);
 if (j) return j;
 return {
 success: false,
 error: 'backend no JSON for "' + sub + '" (exit=' + r.code + ')',
 raw_output: r.out.slice(-1200)
 };
}

function asArray(v) {
 if (Array.isArray(v)) return v.map(function (x) { return String(x).trim(); }).filter(Boolean);
 return String(v || '').split(',').map(function (x) { return x.trim(); }).filter(Boolean);
}

async function make_pdf(p) {
 if (!p.output_path) throw new Error('output_path is required');
 if (!p.content && !p.input_path) throw new Error('need content (markdown) or input_path');
 const a = { out: p.output_path };
 // input_format 之前是死参数：html 会被当 Markdown 硬塞，样式全丢
 const fmt = String(p.input_format || 'markdown').toLowerCase();
 const isHtml = fmt === 'html';
 if (p.content) { if (isHtml) a.html = p.content; else a.md = p.content; }
 if (p.input_path) { if (isHtml) a.html_file = p.input_path; else a.md_file = p.input_path; }
 // 原来这里是手写白名单，font_dir 就在 PARAMS 里声明了却漏在白名单外面，
 // 导致这个参数永远传不到后端。改成黑名单式：除非已做特殊映射，其余一律透传。
 const SPECIAL = ['output_path', 'content', 'input_path', 'input_format'];
 Object.keys(p).forEach(function (k) {
 if (SPECIAL.indexOf(k) >= 0) return;
 if (p[k] != null && p[k] !== '') a[k] = p[k];
 });
 const cov = String(p.cover == null ? '' : p.cover).toLowerCase();
 a.cover = (cov === 'true' || cov === '1' || cov === 'yes');
 if (p.page_numbers != null && p.page_numbers !== '') a.page_numbers = p.page_numbers;
 const j = await call('build', a,300000);
 if (j && j.success) {
 j.next_step = 'MUST call render_pdf_preview(pdf_path="' + p.output_path +
 '") then view the PNG with read_file(direct_image=true) before reporting done.';
 }
 return j;
}

async function render_pdf_preview(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 const j = await call('preview', {
 pdf: p.pdf_path,
 outdir: p.output_dir || '/sdcard/Download/.ai_pdf_preview',
 pages: p.pages || '1',
 dpi: String(p.dpi || '110')
 },180000);
 if (j && j.success && j.rendered && j.rendered.length) {
 j.hint = 'Open these PNG paths with read_file(direct_image=true) to actually inspect layout.';
 }
 return j;
}

async function list_pdf_themes() {
 return {
 success: true,
 engine: 'typst',
 themes: [
 { name: 'report', use: '报告/白皮书/讲义。宋体正文+黑体标题，最通用（默认）' },
 { name: 'handout', use: '课堂讲义/速查表。黑体、紧凑、页边距小' },
 { name: 'resume', use: '简历/CV。四边等距、留白干净' },
 { name: 'editorial', use: '杂志稿/内刊/长文。楷体标题+大页边距' },
 { name: 'minimal', use: '公文/技术文档。去渐变，只用细线' },
 { name: 'certificate', use: '证书/奖状。大字号、宽边距，建议配 gold + cover=false' },
 { name: 'slide', use: 'PPT 幻灯片，16:9。每个 # 一级标题自动一页；含 8 种版式 slide-cover/section/quote/cols/stats/compare/flow/split' }
 ],
 palettes: [
 { name: 'blue', use: '通用专业蓝（默认）' },
 { name: 'ink', use: '墨黑，正式低调' },
 { name: 'forest', use: '森绿，教育健康' },
 { name: 'clay', use: '陶土橙，温暖文创' },
 { name: 'plum', use: '梅紫，艺术设计' },
 { name: 'gold', use: '金曜，证书庆典' }
 ],
 components: {
 kpi: '::: kpi ┊值|说明 （可多条）',
 badges: '::: badges ┊标签|primary （primary/success/warn/danger/neutral/soft）',
 callout: '::: callout warn标题 ┊正文 （note/info/success/warn/danger/quote）',
 cards: '::: cards2 ┊ ###标题 ┊正文 （数字为列数）',
 compare: '::: compare ┊ ###左标题 ┊内容 ┊ ###右标题 ┊内容',
 progress: '::: progress ┊名称|百分比',
 ring: '::: ring ┊名称|百分比 （环形进度，一行最多 3 个并排）',
 wrap: '::: wrap ┊left-top|45mm|38mm ┊正文（文字环绕方块）',
 vertical: '::: vertical3 ┊正文（竖排，数字=列数，从右往左）',
 rating: '::: rating ┊名称|分值',
 chart: '::: chart ┊标签|数值',
 timeline: '::: timeline ┊时间|说明',
 steps: '::: steps ┊每行一步',
 defs: '::: defs ┊术语|定义',
 pagebreak: '::: pagebreak',
 toc: '::: toc'
 },
 inline: '徽章 [重点]{.badge .primary}；高亮 ==文字=='
 };
}

async function pdf_info(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 return await call('info', { pdf: p.pdf_path },90000);
}

async function merge_pdfs(p) {
 const ins = asArray(p.input_paths);
 if (!ins.length) throw new Error('input_paths is empty');
 return await call('merge', { out: p.output_path, inputs: ins },180000);
}

async function split_pdf(p) {
 if (!p.pdf_path || !p.output_dir) throw new Error('pdf_path and output_dir required');
 return await call('split', { pdf: p.pdf_path, outdir: p.output_dir, ranges: p.ranges || '' },180000);
}

async function extract_pdf_pages(p) {
 if (!p.pdf_path || !p.output_path || !p.pages) throw new Error('pdf_path/output_path/pages required');
 return await call('extract', { pdf: p.pdf_path, out: p.output_path, pages: p.pages },180000);
}

async function rotate_pdf_pages(p) {
 if (!p.pdf_path || !p.output_path) throw new Error('pdf_path/output_path required');
 return await call('rotate', {
 pdf: p.pdf_path, out: p.output_path,
 pages: p.pages || 'all', degrees: String(p.degrees || '90')
 },180000);
}

async function compress_pdf(p) {
 // 失败一律 return {success:false,error:...}，不 throw。
 // 实测 throw 在宿主工具边界会被吞成空错误：包内日志 message 完整 37 字，
 // 但用户只看到空白。return 走 wrap 正常分支就能透传。
 if (!p.pdf_path || !p.output_path) {
 return { success: false, error: 'pdf_path/output_path required' };
 }
 // 输入必须真是 PDF：Ghostscript 遇到非 PDF 仍会造出空白页且退出码 0
 // （实测 1 字节 txt -> 2218 字节假 PDF，ratio -221700%）。
 const before = await call('info', { pdf: p.pdf_path }, 90000);
 if (!before || before.success === false || !before.file_size) {
 return { success: false, error: 'PDF not found or not a valid PDF: ' + p.pdf_path +
 (before && before.error ? ' (' + before.error + ')' : '') };
 }
 if (p.pdf_path === p.output_path) {
 return { success: false, error: 'output_path must differ from pdf_path' };
 }
 if (before.encrypted === true) {
 return { success: false, error: 'input PDF is encrypted; decrypt it first (decrypt_pdf)' };
 }
 const quality = p.quality || 'ebook';
 const preset = { screen: '/screen', ebook: '/ebook', printer: '/printer' }[quality] || '/ebook';
 const cmd = 'gs -q -dNOPAUSE -dBATCH -sDEVICE=pdfwrite -dCompatibilityLevel=1.7 -dPDFSETTINGS=' +
 preset + ' -dDetectDuplicateImages=true -dCompressFonts=true -sOutputFile=' +
 q(p.output_path) + ' ' + q(p.pdf_path) + ' 2>&1; cd ' + q(RUNTIME) +
 ' && python3 core.py info ' + q(JSON.stringify({ pdf: p.output_path }));
 const r = await sh(cmd, 300000);
 const j = pickJson(r.out);
 if (!j) return { success: false, error: 'compress failed', raw_output: r.out.slice(-800) };
 if (before && before.file_size) {
 j.original_bytes = before.file_size;
 j.saved_bytes = before.file_size - j.file_size;
 j.ratio = before.file_size > 0
 ? Math.round((1 - j.file_size / before.file_size) * 1000) / 10 + '%'
 : null;
 }
 j.quality = quality;
 return j;
}

async function images_to_pdf(p) {
 const imgs = asArray(p.image_paths);
 if (!imgs.length) throw new Error('image_paths is empty');
 return await call('img2pdf', { out: p.output_path, inputs: imgs, page_size: p.page_size || 'A4' },240000);
}

async function extract_pdf_text(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 const a = { pdf: p.pdf_path };
 if (p.pages) a.pages = p.pages;
 return await call('text', a,180000);
}

async function pdf_selfcheck() {
 const j = await call('selfcheck', {},120000);
 return j;
}

async function pdf_xray(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 return await call('xray', {
 pdf: p.pdf_path,
 pages: p.pages || '1',
 cols: p.cols || 72,
 detail: p.detail || 'full'
 }, 300000);
}

async function pdf_lint(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 return await call('lint', { pdf: p.pdf_path, tol_mm: p.tol_mm, min_dpi: p.min_dpi }, 300000);
}
async function check_font_coverage(p) {
 const a = {};
 if (p.text) a.text = p.text;
 if (p.input_path) a.input = p.input_path;
 if (p.font) a.font = p.font;
 return await call('fontcov', a, 300000);
}
async function match_font(p) {
 const a = {};
 if (p.text) a.text = p.text;
 if (p.input_path) a.input = p.input_path;
 return await call('matchfont', a, 300000);
}
async function check_font_exists(p) {
 if (!p.font) throw new Error('font is required');
 return await call('fontcheck', { font: p.font }, 300000);
}
async function split_by_outline(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 return await call('splitoutline', { pdf: p.pdf_path, output_dir: p.output_dir, level: p.level || 1 }, 300000);
}
async function stamp_pdf(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 const a = { pdf: p.pdf_path };
 if (p.output_path) a.out = p.output_path;
 ['header','footer','watermark','size','offset','color','watermark_size'].forEach(function(k){
  if (p[k] !== undefined && p[k] !== null) a[k] = p[k];
 });
 if (p.page_numbers !== undefined) a.page_numbers = p.page_numbers;
 return await call('stamp', a, 300000);
}
async function encrypt_pdf(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 if (!p.password) throw new Error('password is required');
 return await call('encrypt', { pdf: p.pdf_path, out: p.output_path, password: p.password,
  owner_password: p.owner_password, algorithm: p.algorithm || 'aes-256',
  allow_copy: p.allow_copy, allow_modify: p.allow_modify }, 300000);
}
async function decrypt_pdf(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 return await call('decrypt', { pdf: p.pdf_path, out: p.output_path, password: p.password }, 300000);
}
async function optimize_pdf(p) {
 if (!p.pdf_path) throw new Error('pdf_path is required');
 return await call('optimize', { pdf: p.pdf_path, out: p.output_path,
  subset_fonts: p.subset_fonts, gs_compress: p.gs_compress, quality: p.quality }, 600000);
}
async function import_document(p) {
 const src = p.input_path || p.source_path;
 if (!src) throw new Error('input_path is required');
 return await call('importdoc', { input: src, out: p.output_path }, 300000);
}
async function batch_pdf(p) {
 if (!p.data_path) throw new Error('data_path is required (CSV 或 JSON)');
 if (!p.template_path) throw new Error('template_path is required (含 {{列名}} 的 .md)');
 const a = { data: p.data_path, template: p.template_path, output_dir: p.output_dir };
 ['theme','palette','page_size','margin','base_size','leading','font_body','font_head',
  'cover','watermark','name_from','limit'].forEach(function(k){
  if (p[k] !== undefined && p[k] !== null) a[k] = p[k];
 });
 return await call('batch', a, 1800000);
}
//纯静态工具用：不跑 ensure()。
// ensure()在版本变化后要解包267个文件（实测约18s），而 list_pdf_themes
//只是返回硬编码清单，没理由等它。
function wrapStatic(fn) {
 return async function (params) {
   const data = await fn(params || {});
  complete({ success: !!(data && data.success !== false), data: data });
 };
}

function wrap(fn) {
 return async function (params) {
 try {
 await ensure();
 const data = await fn(params || {});
 complete({ success: !!(data && data.success !== false), data: data });
 } catch (e) {
 // 诊断：部分分支（如 compress_pdf 在 await 之后 throw）宿主会报空错误。
 // 把现场写到 /last_error.log，下次复现直接看文件而不是猜。
 let msg = '';
 try { msg = String((e && e.message) || e || ''); } catch (e2) { msg = ''; }
 try {
 const sep = String.fromCharCode(10);
 await Tools.Files.write(ERRORLOG, [
 'time=' + new Date().toISOString(),
 'fn=' + (fn && fn.name || '?'),
 'typeof=' + typeof e,
 'message_len=' + msg.length,
 'keys=' + (e && typeof e === 'object' ? Object.keys(e).join(',') : '-'),
 'message=' + msg.slice(0, 4000)
 ].join(sep));
 } catch (e3) { }
 if (!msg) msg = 'backend error (empty message); see ' + ERRORLOG;
 complete({ success: false, error: msg });
 }
 };
}
exports.make_pdf = wrap(make_pdf);
exports.render_pdf_preview = wrap(render_pdf_preview);
exports.list_pdf_themes = wrapStatic(list_pdf_themes);
exports.pdf_info = wrap(pdf_info);
exports.merge_pdfs = wrap(merge_pdfs);
exports.split_pdf = wrap(split_pdf);
exports.extract_pdf_pages = wrap(extract_pdf_pages);
exports.rotate_pdf_pages = wrap(rotate_pdf_pages);
exports.compress_pdf = wrap(compress_pdf);
exports.images_to_pdf = wrap(images_to_pdf);
exports.pdf_xray = wrap(pdf_xray);
exports.pdf_lint = wrap(pdf_lint);
exports.check_font_coverage = wrap(check_font_coverage);
exports.match_font = wrap(match_font);
exports.check_font_exists = wrap(check_font_exists);
exports.split_by_outline = wrap(split_by_outline);
exports.stamp_pdf = wrap(stamp_pdf);
exports.encrypt_pdf = wrap(encrypt_pdf);
exports.decrypt_pdf = wrap(decrypt_pdf);
exports.optimize_pdf = wrap(optimize_pdf);
exports.import_document = wrap(import_document);
exports.batch_pdf = wrap(batch_pdf);
exports.extract_pdf_text = wrap(extract_pdf_text);
exports.pdf_selfcheck = wrap(pdf_selfcheck);
'''

# ---- 内嵌 typst 库（meander / basho），gzip+b64 单条数据 ----
# 内嵌 typst 包。key 带 local/ 或 preview/ 前缀，解包到 PKG_DIR 下。
LIB_DIRS = ['local/meander/0.4.6', 'local/basho/0.1.0']
# preview 包（学科图形用）：cetz 量图、molchemist 化学结构式带 WASM、
# cetz-plot 函数图、fletcher 流程图、alchemist 骨架式、chemformula 化学式。
_PREVIEW = [
    'preview/cetz/0.5.3', 'preview/cetz/0.5.2',        # 0.5.2 是 cetz-plot 的依赖
    'preview/cetz-plot/0.1.4', 'preview/cetz-venn/0.2.0',
    'preview/cetz-fields/0.2.0', 'preview/fletcher/0.6.0',
    'preview/molchemist/0.1.6', 'preview/alchemist/0.2.0',
    'preview/chemformula/0.1.3', 'preview/ezchem/0.1.1',
    'preview/physica/0.9.8', 'preview/oxifmt/1.0.0',
    'preview/oxifmt/0.2.1', 'preview/tidy/0.3.0',
]
# 解包根目录：/sdcard/Download/.ai_pdf_runtime/typst-packages
# 文本包在 LIB/typst-libs 下，preview 包直接读运行时的 typst-packages
LIB_ROOT = os.path.join(LIB, 'typst-libs')
PREVIEW_ROOT = '/sdcard/Download/.ai_pdf_runtime/typst-packages'
# 只收这三类，其余（README/LICENSE/gallery 图片）跳过省体积
_KEEP_EXT = ('.typ', '.toml', '.wasm')

def _collect(root, prefix, out):
    for _dp, _dn, _fs in sorted(os.walk(root)):
        for _f in sorted(_fs):
            if not _f.endswith(_KEEP_EXT):
                continue
            _fp = os.path.join(_dp, _f)
            _key = prefix + '/' + os.path.relpath(_fp, root).replace(os.sep, '/')
            if _f.endswith('.wasm'):
                # 二进制：base64 存储，解包时按字节写
                out[_key] = {'b64': base64.b64encode(open(_fp, 'rb').read()).decode('ascii')}
            else:
                out[_key] = open(_fp, encoding='utf-8').read()

_libs = {}
for _p in LIB_DIRS:
    _r = os.path.join(LIB_ROOT, _p.split('/', 1)[1])
    if not os.path.isdir(_r):
        print('WARN lib dir missing:', _r)
        continue
    _collect(_r, _p, _libs)
for _p in _PREVIEW:
    _r = os.path.join(PREVIEW_ROOT, _p)
    if not os.path.isdir(_r):
        print('WARN preview pkg missing:', _r)
        continue
    _collect(_r, _p, _libs)
import gzip as _gz
# sort_keys + mtime=0：不信顺序和上时间戳就会让同内容构建出不同字节（实测两侧差 1520 字节）
#打成 tar再 gzip：运行端一次 tar xzf解完，不用267次 open/write。
#保留可复现：成员排序 + mtime=0 + uid/gid=0 + gzip mtime=0。
#打成 tar再 gzip：运行端一次 tar xzf解完，不再用267次 open/write。
#保留可复现：成员排序 + mtime=0 + uid/gid=0 + uname/gname空 + gzip mtime=0。
#这个环境会把多行缩进压成1空格，所以这里全部写成单行表达式，不用 for/with块。
import tarfile as _tf
_tbuf = io.BytesIO()
_tar = _tf.open(fileobj=_tbuf, mode='w', format=_tf.GNU_FORMAT)
_items = [(r, base64.b64decode(v['b64']) if isinstance(v, dict) else v.encode('utf-8')) for r, v in sorted(_libs.items())]
_mk = lambda r, d: (lambda t: (setattr(t, 'size', len(d)), setattr(t, 'mtime',0), setattr(t, 'uid',0), setattr(t, 'gid',0), setattr(t, 'uname', ''), setattr(t, 'gname', ''), setattr(t, 'mode',0o644), t)[-1])(_tf.TarInfo(r))
[_tar.addfile(_mk(r, d), io.BytesIO(d)) for r, d in _items]
_tar.close()
LIBS_B64 = base64.b64encode(_gz.compress(_tbuf.getvalue(),9, mtime=0)).decode('ascii')
if not _libs:
    raise SystemExit('ERROR: typst 库为空，检查 ' + LIB_ROOT)
print('libs embedded:', len(_libs), 'files,', len(LIBS_B64), 'b64 chars')

js = (JS.replace('__META__', json.dumps(meta, ensure_ascii=False, indent=2))
 .replace('__VER__', ver)
 .replace('__CORE__', base64.b64encode(core).decode('ascii'))
 .replace('__MD2T__', base64.b64encode(md2t).decode('ascii'))
 .replace('__THEME__', base64.b64encode(theme).decode('ascii'))
 .replace('__TEXM__', base64.b64encode(texm).decode('ascii'))
 .replace('__MDM__', base64.b64encode(mdm).decode('ascii'))
 .replace('__MDM2__', base64.b64encode(mdm2).decode('ascii'))
 .replace('__FXG__', base64.b64encode(fxg).decode('ascii'))
 .replace('__QRG__', base64.b64encode(qrg).decode('ascii'))
 .replace('__GNP__', base64.b64encode(gnp).decode('ascii'))
 .replace('__GNPVER__', gnpver)
 .replace('__XRY__', base64.b64encode(xry).decode('ascii'))
 .replace('__CKIT__', base64.b64encode(ckit).decode('ascii'))
 .replace('__OKL__', base64.b64encode(okl).decode('ascii'))
 .replace('__ISRC__', base64.b64encode(isrc).decode('ascii'))
 .replace('__LIBS__', LIBS_B64))

open(OUT, 'w', encoding='utf-8').write(js)
print('written', OUT, len(js.encode('utf-8')), 'bytes')
print('meta tools', len(meta['tools']))

# ---- 真源指纹：方便和 runtime 比对，下次「改了不生效」一眼看出 ----
import hashlib as _hl
for _n in ('core.py', 'md2typst.py', 'theme2.typ', 'gen_package.py',
           'mermaid.py', 'mermaid2.py', 'texmath.py', 'fxgen.py', 'qrgen.py', 'pdfxray.py',
           'colorkit.py', 'oklch.py', 'imgsrc.py'):
    _p = os.path.join(LIB, _n)
    if os.path.exists(_p):
        print('src', _n, _hl.md5(open(_p, 'rb').read()).hexdigest()[:8])

# ---- 危险残留自检 ----
_dp = os.path.dirname(OUT)
for _bad in ('make_package.py', 'ai_pdf.src.js'):
    if os.path.exists(os.path.join(_dp, _bad)):
        print('WARN dev_package 还有旧版残留:', _bad)