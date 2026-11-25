# -*- coding: utf-8 -*-
"""collage 组件写法说明（给 AI 看的工具描述）。
独立成文件的原因：这段是给「写 Markdown 的 AI」看的，必须保留真实换行，
直接拼进 gen_package.py 的字符串元组里很容易被折叠成一行。
"""

COLLAGE_DOC = "\n".join([
    "【拼贴版面 collage】整页自由叠放，坐标单位 mm。",
    "★★★★★ 每个图层必须单独占一行，绝不能写在 ::: collage 同一行 —— 写在同一行会被当成标题处理，图层静默丢失（工具会自动救回来但会告警）。正确写法：",
    "::: collage w=297 h=167 bg=F5F2EC      <- 这一行只放参数",
    "bgimg|/path/a.jpg      （照片铺满整页当底，自动 fit:cover）",
    "mask|1A2438|46      （整页蒙版，第二段是透明度 0~100）",
    "img|/path/b.jpg|0,0|86,58|shape=arc k=0.30 pos=left-top pad=20 bw=1.2 bc=C8A15A",
    "text|标题|0,0|160|pos=left-top pad=22 size=30 weight=bold font=BodoniModa_400i color=FFFFFF track=8",
    "block|正文|0,0|120,40|pos=right-bottom pad=20 fill=FFFFFF alpha=18 color=1A1A1A size=9 pad=5 r=2",
    "vtext|竖排|0,0|40,120|pos=right-top pad=20 size=11 gap=3",
    "oval|/path/c.jpg|0,0|70,70|pos=center-middle pad=0      （椭圆开窗）",
    "dot|8FA3BD|0,0|2.5|pos=left-bottom pad=30",
    "ring|8B8070|0,0|3|pos=right-middle pad=30 w=0.8",
    "line|C9D6E5|0,0|120,0|pos=left-top pad=40 w=0.5      （第二点是终点偏移）",
    "curve|M10,70 C60,20 140,95 270,30|0,0|60,20|pos=center-bottom pad=10 color=BE123C w=1.5",
    "orn|8B8070|0,0|40,12|pos=center-top pad=10 w=1      （装饰卷草，自动生成 S 形）",
    ":::",
    "【定位两种写法】① 直接给 x,y：img|路径|20,30|86,58",
    "② 给锚点让工具算（推荐，不用手算坐标）：pos=left-top / center-middle / right-bottom，取 left|center|right 与 top|middle|bottom 的组合，再配 pad=边距，x,y 段写 0,0 占位即可。",
    "【shape= 异形裁剪】可选 arc(左上大圆角) / arc4(四角圆角) / slant(斜切) / notch(缺角) / ellipse(椭圆) / arch(拱顶) / wave(波浪底)，k=弧度比例默认 0.26（0.02~0.49），描边 bw/bc 在异形上同样生效。照片会自动预裁到精确比例，不会变形。",
    "★ 拼贴要配 theme=slide（16:9）+ margin=0mm + page_numbers=false，画布 w/h 用 297x167；不要在 collage 前面写 ## 标题（会占掉页面顶部），标题用 text 图层画进去。",
])

if __name__ == '__main__':
    print(COLLAGE_DOC)
    print('---')
    print('lines:', COLLAGE_DOC.count('\n') + 1)
_COMPACT = '【★ 写之前先记住 6 条（其余细节见 pdfxray.py 顶部注释）】\n1. alpha 是透明度不是不透明度：alpha=0 完全不透明，alpha=100 全透明。要 30% 不透明写 70。\n2. dot / ring 的 size 是半径不是直径：要直径 26 就写 13。\n3. 文字压照片上必须写 bg=真实底色，否则自动对比色会按画布猜，猜错就是黑字压雪山看不见。\n4. 中文字体没有 italic，用 skew=12 做伪斜体（style:italic 会静默失效）。\n5. block 高度由内容自动撑开，不是写死值。接在块后面的元素，用 pdf_xray 量真实 bbox 再定坐标。\n6. 想要「深色字压浅色条」（参考图最常见），用 block 做半透明浅条 + 深色字，不要白字硬压图再调蒙版。'
COLLAGE_DOC = COLLAGE_DOC + "\n\n" + _COMPACT
