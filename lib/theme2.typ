// ============================================================
// ai_pdf 主题引擎 v2 (Typst)
// cfg 由 core_typst.py 注入
// ============================================================

// 第三方库：包已内嵌，通过 --package-path 找到 @local
// 只导入命名空间，不要 * —— meander 的 elems.typ:111 定义了 pagebreak()，
// 星号导入会覆盖 Typst 内置 pagebreak，导致 ::: pagebreak 和 sectiontoc 全废。
// wrap 内部用到 placed/container/content，那里已有 import meander: *。
#import "@local/meander:0.4.6" as meander
#import "@local/basho:0.1.0": tate

#let accent = cfg.accent
#let accent2 = cfg.accent2
#let soft = cfg.soft
#let soft2 = cfg.soft2
#let ink = cfg.ink
#let lc = cfg.line
#let bf = cfg.body-font
#let hf = cfg.head-font
#let mf = cfg.mono-font
#let bs = cfg.base-size

// ---------- 大统一样式系统（style / radius / tone） ----------
// 设计目标：AI 只需记住 3 个词，不碰具体像素。
//   style: flat | shadow | glass | gradient | outline
//   radius: 0 | 4 | 8 | pill
//   tone: primary | success | warn | danger | neutral | soft

#let tone-color(t) = {
  if t == "success" { rgb("#1F7A5C") }
  else if t == "warn" { rgb("#B45309") }
  else if t == "danger" { rgb("#BE123C") }
  else if t == "neutral" { luma(110) }
  else if t == "soft" { soft }
  else { accent }
}

#let radius-of(r) = {
  if r == "pill" { 999pt }
  else if type(r) == str {
    if r == "0" { 0pt } else if r == "4" { 4pt } else if r == "8" { 8pt } else { 6pt }
  }
  else if type(r) == int { r * 1pt }
  else { 6pt }
}

#let card-style(style: "flat", tone: "primary", rad: 8, base-fill: none) = {
  let tc = tone-color(tone)
  let rf = if base-fill == none { soft2 } else { base-fill }
  let r = radius-of(rad)
  if style == "shadow" { (rf, 0.5pt + lc, r) }
  else if style == "glass" { (rf.transparentize(35%), 0.8pt + rgb("#FFFFFF").transparentize(40%), r) }
  else if style == "gradient" { (gradient.linear(rf, tc.transparentize(88%), angle: 135deg), none, r) }
  else if style == "outline" { (none, 1pt + tc, r) }
  else { (rf, 0.6pt + lc, r) }
}

// 纯 Typst 仿阴影：下方垫一层偏移浅色块，文字层不丢
// depth=偏移量 rad=圆角 tint=阴影色 spread=右下额外外扩
#let shadowed(body, rad: 8pt, depth: 2.5pt, tint: luma(214), spread: 1.5pt) = {
  // 做法：用一个 block 自身画「外扩一圈的浅色底」，再用负 inset 把内容压回内部。
  // 全程不依赖 height: 100%（那在流式布局里会撑满可用高度，灰块会盖住整页）。
  block(
    width: 100%,
    radius: rad,
    fill: tint,
    inset: (x: 0pt, y: 0pt),
    outset: (bottom: depth, right: spread, top: 0pt, left: 0pt),
  )[#body]
}

// 胶囊标题
#let capsule(body, tone: "primary", solid: true, size: 12pt) = {
  let tc = tone-color(tone)
  box(radius: 999pt,
    fill: if solid { tc } else { none },
    stroke: if solid { none } else { 1pt + tc },
    inset: (x: 5mm, y: 2.4mm),
    text(font: hf, size: size, weight: "bold",
      fill: if solid { rgb("#FFFFFF") } else { tc })[#body])
}

// 行内颜色 / 渐变
#let clr(body, color: "primary") = text(fill: tone-color(color))[#body]
#let grad-text(body) = text(fill: gradient.linear(accent, accent2, angle: 15deg))[#body]

// 二维码
#let qrcode(src, size: 30mm, caption: none) = block(width: 100%, above: 8pt, below: 8pt)[
  #align(center)[
    #image(src, width: size)
    #if caption != none [#v(2pt) #text(size: 8.5pt, fill: luma(120))[#caption]]
  ]
]

// 价格表
#let price-plans(items, cols: 3) = {
  grid(columns: (1fr,) * cols, gutter: 5mm,
    ..items.map(((nm, pr, feats, hot)) => block(
      width: 100%, radius: 6pt, inset: 6mm,
      stroke: if hot != "" { 1.6pt + accent } else { 0.6pt + lc },
      fill: if hot != "" { soft2 } else { rgb("#FFFFFF") },
    )[
      #if hot != "" [
        #box(radius: 999pt, fill: accent, inset: (x: 3mm, y: 1.2mm),
          text(size: 8pt, fill: rgb("#FFFFFF"), weight: "bold")[#hot])
        #v(2mm)
      ]
      #block(width: 100%, text(font: hf, size: 11pt, weight: "bold", fill: ink)[#nm])
      #v(2mm)
      #block(width: 100%, text(font: hf, size: 22pt, weight: "bold", fill: accent)[#pr])
      #v(3mm)
      #block(width: 100%, height: 0.5pt, fill: lc)
      #v(3mm)
      #for f in feats [
        #block(width: 100%, text(size: 9.5pt, fill: luma(80))[· #f])
        #v(1.2mm)
      ]
    ]))
}

// FAQ
#let faq(items) = block(width: 100%, above: 8pt, below: 10pt)[
  #for (i, (q, a)) in items.enumerate() [
    #block(width: 100%, inset: (left: 4mm), stroke: (left: 2.5pt + accent))[
      #block(width: 100%, text(font: hf, size: 10.5pt, weight: "bold", fill: ink)[#q])
      #v(1.6mm)
      #block(width: 100%, text(size: 9.5pt, fill: luma(85))[#a])
    ]
    #v(3.5mm)
  ]
]

// 团队介绍
#let team(items, cols: 3) = {
  grid(columns: (1fr,) * cols, gutter: 5mm,
    ..items.map(((nm, role, bio)) => block(
      width: 100%, inset: 4mm, radius: 5pt, stroke: 0.5pt + lc, fill: soft2,
    )[
      #block(width: 12mm, height: 12mm, radius: 999pt, fill: accent.transparentize(80%))
      #v(2mm)
      #block(width: 100%, text(font: hf, size: 10.5pt, weight: "bold", fill: ink)[#nm])
      #v(1mm)
      #block(width: 100%, text(size: 8.5pt, fill: accent)[#role])
      #v(1.6mm)
      #block(width: 100%, text(size: 8.5pt, fill: luma(100))[#bio])
    ]))
}


// ---------- 页面 ----------
#set page(
  paper: cfg.paper,
  margin: cfg.margin,
  numbering: none,
  header: if cfg.header-text == "" { none } else {
    align(right)[#text(font: hf, size: 8pt, fill: rgb("#B0B7C3"))[#cfg.header-text]]
  },
  footer: if cfg.page-numbers {
    context align(center)[
      #text(font: hf, size: 8.5pt, fill: rgb("#9AA3AF"))[
        #counter(page).display("1 / 1", both: true)
      ]
    ]
  } else { none },
  background: if cfg.watermark == "" { none } else {
    place(center + horizon)[
      #rotate(-30deg)[
        #text(font: hf, size: 64pt, fill: rgb("#000000").transparentize(94%))[#cfg.watermark]
      ]
    ]
  },
)

#set text(font: bf, size: bs, fill: ink, lang: "zh", region: "cn")
#set par(leading: cfg.leading, justify: true, spacing: 1.05em)
#set block(spacing:0pt)
#show math.equation.where(block: true): it => block(above: 0.85em, below: 0.85em)[#it]

// page.margin 可能是单个 length，也可能是四边 tuple；取左边距统一走这个
#let _pg-ml(m) = if type(m) == dictionary { m.left } else { m }

// ---------- 标题 ----------
#show heading.where(level: 1): it => {
  if cfg.slide {
    // 幻灯片模式：每个 H1 = 新一页，页眉色条横贯整页
    pagebreak(weak: true)
    // margin 现在跟随 cfg.margin（用户可覆盖），负偏移量用实际左边距算
    context place(top + left, dx: -_pg-ml(page.margin), dy: 0pt,
      block(width: page.width, height: 20mm, fill: accent)[
        #place(left + bottom, dx: _pg-ml(page.margin), dy: -6.5mm)[
          #text(font: hf, size: 20pt, weight: "bold", fill: white)[#it.body]
        ]
      ])
    v(26mm)
  } else {
    block(width: 100%, above: 16pt, below: 10pt, breakable: false)[
      #block(
        width: 100%, radius: 3pt,
        fill: if cfg.h1-fill { soft } else { none },
        inset: (left: 13pt, y: 8pt),
      )[
        #text(font: hf, size: cfg.h1-size, weight: "bold", fill: ink)[#it.body]
      ]
      #if cfg.h1-bar [
        #v(1pt)
        #block(width: 26mm, height: 2.2pt, fill: accent, radius: 1.1pt)
      ]
    ]
  }
}

#show heading.where(level:2): it => block(
  width:100%, above:14pt, below:7pt, breakable: false,
)[
  #block(
    width:100%, stroke: (bottom:0.6pt + lc), inset: (bottom:4pt),
  )[
    #text(font: hf, size: cfg.h2-size, weight: "bold", fill: ink)[#it.body]
  ]
  #v(0.5pt)
  #block(width:20mm, height:1.6pt, fill: accent, radius:0.8pt)
]

#show heading.where(level: 3): it => block(
  width: 100%, above: 11pt, below: 5pt, breakable: false,
)[
  #text(font: hf, size: cfg.h3-size, weight: "bold", fill: accent)[#it.body]
]

#show heading.where(level: 4): it => block(
  width: 100%, above: 9pt, below: 4pt, breakable: false,
)[
  #text(font: hf, size: cfg.h4-size, weight: "semibold", fill: ink)[#it.body]
]

// ---------- 列表 ----------
#set list(
  marker: ([#circle(fill: accent, radius: 2pt)], [--]),
  indent: 1.1em, body-indent: 0.55em, spacing: 0.85em,
)
#set enum(indent: 1.25em, body-indent: 0.55em, spacing: 0.85em, numbering: "1.")

// ---------- 引用 ----------
#show quote.where(block: true): it => block(
  width: 100%, radius: 3pt, fill: soft2,
  stroke: (left: 3pt + accent), inset: (x: 13pt, y: 9pt),
  above: 9pt, below: 9pt,
)[
  #set text(size: bs * 0.95, fill: rgb("#3A4553"))
  #it.body
]

// ---------- 代码 ----------
#show raw.where(block: false): it => box(
  radius: 2pt, fill: soft, inset: (x: 3pt, y: 0.8pt),
)[
  #text(font: mf, size: bs * 0.88, fill: accent, hyphenate: false)[#it.text]
]

#show raw.where(block: true): it => block(
  width: 100%, radius: 3pt, fill: rgb("#F7F8FA"),
  stroke: 0.5pt + rgb("#E7EBF2"), inset: 10pt,
  above: 8pt, below: 10pt,
)[
  #set text(size: bs * 0.85)
  #set par(leading: 0.62em, justify: false)
  #it
]

// ---------- 表格 ----------
#set table(
  stroke: 0.5pt + lc,
  inset: (x: 7pt, y: 5.5pt),
  fill: (c, r) => if r == 0 { accent } else if calc.odd(r) { soft2 } else { white },
)

// 注意：绝不能写 breakable: false。那会让超过一页的表格直接被裁，
// 多出的行静默消失（实测 60 行只渲染 39 行）。内容完整性优先于圆角。
#show table: it => block(
  width: 100%,
  above: 8pt, below: 11pt,
)[#it]

#show table.cell.where(y: 0): it => {
  set text(font: hf, fill: white, weight: "bold", size: bs * 0.88)
  it
}

#show table.cell: it => {
  set text(size: bs * 0.9)
  it
}

// ---------- 图片 ----------
#show figure: it => block(
  width: 100%, above: 8pt, below: 10pt, breakable: false,
)[
  #align(center)[#it.body]
  #if it.caption.body != none [
    #v(3pt)
    #text(size: bs * 0.82, fill: rgb("#8A94A3"))[#it.caption]
  ]
]

// ---------- 分割线 ----------
#let hr() = block(width: 100%, above: 11pt, below: 11pt)[
  #block(width: 100%, height: 0.8pt, fill: lc)
]

// ============================================================
// 组件
// ============================================================

// ---------- KPI 卡 ----------
#let kpi(value, label) = block(
  width: 100%, radius: 4pt, fill: soft2,
  stroke: 0.5pt + lc, inset: (x: 11pt, y: 10pt),
)[
  #text(font: hf, size: bs * 1.7, weight: "bold", fill: accent, hyphenate: false, value)
  #v(2pt)
  #text(size: bs * 0.76, fill: rgb("#6B7684"), label)
]

#let kpirow(items) = {
  if items.len() == 0 { return }
  grid(
    columns: (1fr,) * items.len(), gutter: 7pt,
    ..items.map(it => kpi(it.at(0), it.at(1))),
  )
}

// ---------- 徽章 ----------
#let badge-kinds = (
  primary: (fill: accent, text: white),
  soft: (fill: soft, text: accent),
  success: (fill: rgb("#1F9A66"), text: white),
  warn: (fill: rgb("#C97A18"), text: white),
  danger: (fill: rgb("#C43D3D"), text: white),
  neutral: (fill: rgb("#EDEFF3"), text: rgb("#4B5563")),
)

#let badge(label, kind: "soft") = box(
  radius: 999pt,
  fill: badge-kinds.at(kind).fill,
  inset: (x: 8pt, y: 3pt),
)[
  #text(font: hf, size: bs * 0.78, weight: "semibold",
        fill: badge-kinds.at(kind).text)[#label]
]

#let badgerow(items) = block(above: 6pt, below: 8pt)[
  #for it in items {
    badge(it.at(0), kind: it.at(1))
    h(4pt)
  }
]

// ---------- 提示框 ----------
#let callout-kinds = (
  note: (c: rgb("#2F5BEA"), bg: rgb("#EEF3FF")),
  info: (c: rgb("#1C7ED6"), bg: rgb("#EAF4FE")),
  success: (c: rgb("#1F9A66"), bg: rgb("#EAF7F1")),
  warn: (c: rgb("#C97A18"), bg: rgb("#FDF4E6")),
  danger: (c: rgb("#C43D3D"), bg: rgb("#FDEDED")),
  quote: (c: rgb("#A8834A"), bg: rgb("#FAF4E4")),
)

#let callout(body, kind: "note", title: none) = block(
  width: 100%, radius: 3.5pt,
  fill: callout-kinds.at(kind).bg,
  stroke: (left: 3.2pt + callout-kinds.at(kind).c),
  inset: (x: 13pt, y: 10pt),
  above: 9pt, below: 10pt,
)[
  #if title != none [
    #text(font: hf, size: bs * 0.94, weight: "bold",
          fill: callout-kinds.at(kind).c)[#title]
    #v(3pt)
  ]
  #set text(size: bs * 0.95, fill: rgb("#3A4553"))
  #body
]

// ---------- 卡片 ----------

// ---------- 特效层（SVG 装饰 + Typst 文字） ----------
// 关键设计：SVG 只做背景/装饰，正文永远由 Typst 排。
// 这样磨砂/泛光卡片的**文字仍然可选中、可搜索、可复制**。

#let fx-layer(src, w, h) = place(top + left, image(src, width: w, height: h))

// 背景图高度不能写死，也不能用 100%（place 的百分比相对页面，实测会撑到 472pt）。
// 正确做法：用 block 包住内容让它自然撑开，再用 measure 取内容高度画背景。
#let fx-card(body, src, inset-v:5mm, fit: "cover") = layout(size => block(width:100%)[
  #let inner = pad(x: inset-v, y: inset-v, body)
  #let h = measure(inner).height
  #place(top + left, image(src, width: 100%, height: h, fit: fit))
  #inner
])

// 泛光：outside 形状在内容外围画一圈半透明同色描边
// strength=描边透明度(0~100，越大越淡) width=描边粗细
#let fx-glow(body, color: "primary", inset-v: 5mm, rad: 6, tint: none,
             strength: 82, width: 2pt) = {
  // transparentize 要 ratio 不能给整数：传 strength: 95 会报 expected ratio
  let s = if type(strength) == int or type(strength) == float { strength * 1% } else { strength }
  let w = if type(width) == int or type(width) == float { width * 1pt } else { width }
  let tc = tone-color(color)
  let base = rgb("#FFFFFF")
  let rr = radius-of(rad)
  block(
    width: 100%, radius: rr, inset: inset-v,
    fill: if tint == none { soft2 } else { tint },
    stroke: w + tc.transparentize(s),
  )[#body]
}

// 磨砂玻璃：浅灰蓝半透明底（在白纸上才看得见）+ 亮边 + 左侧高光竖条
// opacity=底色的不透明度(0~100，越大越实) light=高光竖条透明度(0~100)
// bar=高光竖条宽度 border=边框粗细
// 磨砂玻璃。
// 演进过程（都是实测过、被否掉的）：
//   ① 单层半透明纯色 —— 白纸上就是一块浅蓝矩形，毫无磨砂感
//   ② 斜向高光渐变 —— 有反光但缺颗粒，像亮面塑料
//   ③ SVG feGaussianBlur —— 效果最像真毛玻璃，但文字被栅格化，不可选不可搜（否决）
//   ④ PNG 噪点叠加 —— 有效但体积大、放大糊
//   ⑤ 当前：Typst 原生 tiling 颗粒 + 高光 + 亮边
//      tiling 是真矢量 pattern（PDF 里 images=0，走 /Pattern），几 KB、任意缩放不糊，
//      文字仍由 Typst 排 —— 可选、可搜、可复制。
// 颗粒高度必须用 measure 量内容：place 里的 100% 相对页面（实测只铺满左半边），
// layout 的 sz.height 是可用高度（也错），只有 measure(inner, width:) 是对的。
#let fx-frost(body, rat: 6, inset-v: 5mm, tint: none,
              opacity: 55, light: 30, bar: 2.5pt, border: 0.9pt,
              grain: 0, grain-a: 0, bg: none) = {
  let o = if type(opacity) == int or type(opacity) == float { opacity * 1% } else { opacity }
  let l = if type(light) == int or type(light) == float { light * 1% } else { light }
  let bw = if type(bar) == int or type(bar) == float { bar * 1pt } else { bar }
  let bd = if type(border) == int or type(border) == float { border * 1pt } else { border }
  let gs = if type(grain) == int or type(grain) == float { grain * 1pt } else { grain }
  let ga = if type(grain-a) == int or type(grain-a) == float { grain-a * 1% } else { grain-a }
  // 底色不能是纯白：白底 + 白颗粒 + 白描边 = 白纸上什么也看不见（实测踩过）。
  // 用带一点冷调的浅蓝灰，磨砂质感才立得住；可用 tint= 自定。
  let base = if tint == none { rgb("#DCE7F5") } else { tint }
  let rad = radius-of(rat)
  let inner = pad(x: inset-v, y: inset-v, body)

  // ★ 颗粒必须是双层。原因（实测）：
  //   单层白颗粒叠在白底上，对比度只有 3.1 灰阶 = 1.2%，肉眼完全看不出来，
  //   而且 grain-a 越大越白越看不见 —— 参数方向是反的。
  //   改成「深颗粒 + 白颗粒错位半格」后，深粒子把底色压暗、白粒子提亮，
  //   才有砂面的明暗交错感。深颗粒色由背景色推出来，不影响 tint 自定义。
  //   深颗粒透明度固定 30%（实测甜点）：transparentize(100%) 是「完全不透明」的对立面
  //   —— Typst 里 transparentize(100%) = 全透明 = 看不见，之前卡到 100% 直接导致深颗粒消失。
  //   白颗粒错位半格叠加，形成「暗-亮」交错的砂面。
  //   darken(58%) 让深颗粒有足够对比，不依赖 grain-a 的放大。
  let dk = base.darken(58%)
  let dot(dc, a, off: 0pt) = place(center + horizon,
    move(dx: off, box(width: gs * 0.42, height: gs * 0.42, radius: 50%,
      fill: dc.transparentize(a))))

  // 有 bg 时底色必须极淡：底色是「雾」，压在背景上面。
  // 实测 opacity=22 的 #DCE7F5 仍会把背景冲成灰紫（用户指出“颜色不对”）。
  // 所以 bg 分支下用白色雾（不带蓝调）且不透明度减半，让背景色彩透出来。
  // 标准玻璃拟态底色：rgba(255,255,255,0.2)，即 80% 透明。
  // opacity 参数控制玻璃层的不透明度：opacity=20 → 白色 20% 实、80% 透。
  let fog = if bg == none { base.transparentize(o) } else { rgb("#FFFFFF").transparentize(100% - o) }
  let card = block(
    width: 100%, radius: rad, inset: 0pt,
    fill: fog,
    stroke: bd + rgb("#FFFFFF"),
    clip: true,
  )[
    // 颗粒层：place 的 height: 100% 在 block[...] 内是相对这个 block（不是页面），
    // 所以能正好铺满。前提是 block 的 inset 必须为 0，否则内部尺寸算不对。
    // 颗粒默认不画（grain: 0）。真实磨砂玻璃在宏观上是均匀的乳白层，
    // 像素点的噪点是「纱窗/网点纸」观感 —— 用户明确指出那不是磨砂。
    // PS 那种磨砂 = 白色半透明 + 背景模糊，没有颗粒。要纹理再显式传 grain=。
    #if gs > 0pt [
      #place(top + left, box(width: 100%, height: 100%,
        fill: tiling(size: (gs, gs), dot(dk, 30%))))
      #place(top + left, box(width: 100%, height: 100%,
        fill: tiling(size: (gs, gs), dot(rgb("#FFFFFF"), ga, off: gs * 0.5))))
    ]
    // 顶部镜面高光
    #place(top + left, block(width: 100%, height: bw,
      fill: rgb("#FFFFFF").transparentize(l)))
    // 底部反光细线
    #place(bottom + left, block(width: 100%, height: 0.5pt,
      fill: rgb("#FFFFFF").transparentize(70%)))
    #inner
  ]
  if bg == none {
    card
  } else {
    // 有背景时不能把 card 当 place 的内容（place 拿不到 block 的尺寸会塌掉）。
    // 改法：把背景图塞进 card 内部当底层，card 自己撑高。
    block(width: 100%, radius: rad, clip: true)[
      #layout(sz => [
        #place(top + left, image(bg, width: 100%, height: 100%, fit: "cover"))
        #card
      ])
    ]
  }
}

#let fx-curve(src, w: 100%) = block(width: 100%, above: 6pt, below: 6pt)[
  #align(center)[#image(src, width: w)]
]


// ---------- 商业组件（发票 / 证书 / 简历 / 菜单） ----------

// 发票明细表：自动算合计
#let invoice-table(items, cols: (3fr, 1fr, 1.2fr, 1.2fr), currency: "¥") = {
  let total = 0.0
  for it in items {
    total += it.at(1) * it.at(2)
  }
  block(width: 100%)[
    #grid(columns: cols, gutter: 0pt,
      ..(("品名", "数量", "单价", "小计").map(h =>
        block(width: 100%, inset: (x: 4pt, y: 5pt), fill: accent,
          text(size: 9pt, fill: rgb("#FFFFFF"), weight: "bold")[#h]))),
      ..items.map(it => {
        let sub = it.at(1) * it.at(2)
        (
          block(width: 100%, inset: (x: 4pt, y: 5pt), stroke: (bottom: 0.4pt + lc))[#text(size: 9pt)[#it.at(0)]],
          block(width: 100%, inset: (x: 4pt, y: 5pt), stroke: (bottom: 0.4pt + lc))[#align(right)[#text(size: 9pt)[#it.at(1)]]],
          block(width: 100%, inset: (x: 4pt, y: 5pt), stroke: (bottom: 0.4pt + lc))[#align(right)[#text(size: 9pt)[#currency#it.at(2)]]],
          block(width: 100%, inset: (x: 4pt, y: 5pt), stroke: (bottom: 0.4pt + lc))[#align(right)[#text(size: 9pt, weight: "bold")[#currency#sub]]],
        )
      }).flatten(),
    )
    #v(3mm)
    #align(right)[
      #block(inset: (x: 5mm, y: 3mm), radius: 3pt, fill: soft2)[
        #text(font: hf, size: 11pt, weight: "bold", fill: accent)[合计：#currency#total]
      ]
    ]
  ]
}

// 证书
#let cert-sheet(name: "", title: "荣誉证书", body: "", org: "", date: "", serial: "") = {
  block(width: 100%, radius: 3pt, inset: (x: 14mm, y: 12mm),
    above: 10pt, below: 12pt,
    stroke: 2.2pt + accent, fill: rgb("#FFFDF8"))[
    #block(width: 100%, radius: 2pt, inset: (x: 10mm, y: 9mm), stroke: 0.6pt + accent.transparentize(60%))[
      #align(center)[
        #text(font: hf, size: 24pt, weight: "bold", fill: accent)[#title]
        #v(3mm)
        #block(width: 28mm, height: 2pt, fill: accent)
      ]
      #v(8mm)
      #if name != "" [
        #align(center)[#text(font: hf, size: 15pt, weight: "bold")[#name]]
        #v(5mm)
      ]
      #block(width: 100%, inset: (x: 6mm), text(size: 10.5pt, fill: luma(70))[#body])
      #v(10mm)
      #grid(columns: (1fr, 1fr),
        align(right)[#text(size: 10pt, fill: luma(90))[#org] #v(2mm) #block(width: 34mm, height: 0.6pt, fill: luma(150))],
        align(right)[#text(size: 10pt, fill: luma(90))[#date] #v(2mm) #block(width: 34mm, height: 0.6pt, fill: luma(150))],
      )
      #if serial != "" [
        #v(4mm)
        #align(center)[#text(size: 8pt, fill: luma(160))[证书编号：#serial]]
      ]
    ]
  ]
}

// 简历时间线（左时间右内容）
#let resume-timeline(items) = block(width: 100%, above: 8pt, below: 12pt)[
  #for (i, (when, what, desc)) in items.enumerate() [
    #grid(columns: (32mm, 1fr), gutter: 4mm,
      block(width: 100%, inset: (top: 1.2mm), align(right)[
        #text(size: 9pt, fill: luma(110))[#when]
      ]),
      block(width: 100%, inset: (left: 4mm), stroke: (left: 1.6pt + accent))[
        #block(width: 100%, text(font: hf, size: 10.5pt, weight: "bold")[#what])
        #if desc != "" [
          #v(1.4mm)
          #block(width: 100%, text(size: 9pt, fill: luma(90))[#desc])
        ]
      ],
    )
    #v(4mm)
  ]
]

// 技能标签组
#let skill-tags(items) = block(width: 100%, above: 8pt, below: 10pt)[
  #for (i, s) in items.enumerate() [
    #box(radius: 999pt, fill: soft, inset: (x: 3.2mm, y: 1.4mm),
      text(size: 9pt, fill: accent, weight: "bold")[#s])
    #h(1.5mm)
  ]
]

// 菜单菜品行（名称 …… 价格）
#let menu-list(items) = block(width: 100%, above: 8pt, below: 10pt)[
  #for (i, (nm, pr, note)) in items.enumerate() [
    #grid(columns: (1fr, auto), gutter: 2mm,
      block(width: 100%)[
        #text(font: hf, size: 10.5pt, weight: "bold")[#nm]
        #if note != "" [#h(2mm) #text(size: 8.5pt, fill: luma(120))[#note]]
      ],
      block(inset: (top: 1.4mm), text(font: hf, size: 10.5pt, weight: "bold", fill: accent)[#pr]),
    )
    #v(0.8mm)
    #block(width: 100%, height: 0.4pt, fill: lc)
    #v(2.2mm)
  ]
]

// 海报主视觉块
#let poster(hero: "", sub: "", when: "", where: "", note: "") = {
  block(width: 100%, radius: 4pt, inset: (x: 12mm, y: 10mm), above: 10pt, below: 12pt,
    fill: gradient.linear(accent, accent2, angle: 135deg))[
    #align(center)[
      #block(width: 100%, text(font: hf, size: 26pt, weight: "bold", fill: rgb("#FFFFFF"))[#hero])
      #if sub != "" [#v(3mm) #block(width: 100%, text(size: 12pt, fill: rgb("#FFFFFF").transparentize(15%))[#sub])]
      #v(7mm)
      #block(width: 22mm, height: 2pt, fill: rgb("#FFFFFF").transparentize(40%))
      #v(6mm)
      #if when != "" [#block(width: 100%, text(size: 10.5pt, fill: rgb("#FFFFFF"))[#when])]
      #if where != "" [#v(2mm) #block(width: 100%, text(size: 10.5pt, fill: rgb("#FFFFFF"))[#where])]
      #if note != "" [#v(5mm) #block(width: 100%, text(size: 9pt, fill: rgb("#FFFFFF").transparentize(25%))[#note])]
    ]
  ]
}

#let card(title, body, style: "flat", rad: 4, tone: "primary",
         sh-depth: 2.5pt, sh-spread: 1.5pt, sh-tint: luma(214)) = {
  let cs = card-style(style: style, tone: tone, rad: rad, base-fill: rgb("#FFFFFF"))
  let inner = block(
    width: 100%, radius: cs.at(2), fill: cs.at(0), stroke: cs.at(1),
    inset: (x: 12pt, y: 10pt),
  )[
    #if title != "" [
      #text(font: hf, size: bs * 0.95, weight: "bold", fill: tone-color(tone))[#title]
      #v(4pt)
    ]
    #set text(size: bs * 0.9)
    #body
  ]
  if style == "shadow" {
    shadowed(rad: cs.at(2), depth: sh-depth, spread: sh-spread, tint: sh-tint)[#inner]
  } else { inner }
}
#let cardgrid(items, cols: 2, style: "flat", rad: 4, tone: "primary",
              sh-depth: 2.5pt, sh-spread: 1.5pt, sh-tint: luma(214)) = {
  if items.len() == 0 { return }
  grid(
    columns: (1fr,) * cols, gutter: 8pt,
    ..items.map(it => card(it.at(0), it.at(1),
      style: style, rad: rad, tone: tone,
      sh-depth: sh-depth, sh-spread: sh-spread, sh-tint: sh-tint)),
  )
}

// ---------- 进度条 ----------
#let progress(label, pct) = block(
  width: 100%, above: 6pt, below: 8pt,
)[
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(size: bs * 0.9)[#label]],
    [#text(size: bs * 0.85, fill: accent, weight: "bold")[#pct%]],
  )
  #v(3pt)
  #block(
    width: 100%, height: 5pt, radius: 2.5pt, fill: soft,
    place(
      top + left,
      block(
        width: calc.min(calc.max(pct / 100.0, 0.0), 1.0) * 100%,
        height: 5pt,
        radius: 2.5pt,
        fill: accent,
      ),
    ),
  )
]

// ---------- 环形进度 ----------
// 用法： ring(72)  或  ring(72, d: 56pt)
// Typst 无 curve.arc()，用 72 段折线逼近；起点必须 curve.move，否则从 (0,0) 拉歪
#let ring(pct, d: 64pt, label: none) = {
  let r = d / 2 - 2.5pt
  let steps = 72
  let v = calc.min(calc.max(pct / 100.0, 0.0), 1.0)
  let seg = int(calc.round(v * float(steps)))
  let pt(i) = {
    let a = (float(i) / steps) * 2 * calc.pi - calc.pi / 2
    let x = d / 2 + r * calc.cos(a)
    let y = d / 2 + r * calc.sin(a)
    (x, y)
  }
  box(width: d, height: d, {
    place(top + left, curve(
      stroke: 5pt + soft2,
      curve.move(pt(0)),
      ..range(1, steps + 1).map(i => curve.line(pt(i))),
    ))
    if seg > 0 {
      place(top + left, curve(
        stroke: 5pt + accent,
        curve.move(pt(0)),
        ..range(1, seg + 1).map(i => curve.line(pt(i))),
      ))
    }
    place(center + horizon, block(align(center)[
      #text(weight: "bold", size: d * 0.22, fill: ink)[#pct%]
      #if label != none {
        linebreak()
        text(size: d * 0.12, fill: ink)[#label]
      }
    ]))
  })
}

// ---------- 时间线 ----------
#let timeline(items) = {
  block(width: 100%, above: 6pt, below: 8pt)[
    #for it in items [
      #grid(
        columns: (10pt, 1fr),
        column-gutter: 8pt,
        align: (center + top, left + top),
        [
          #v(4pt)
          #circle(fill: accent, radius: 3pt)
        ],
        [
          #text(font: hf, size: bs * 0.95, weight: "bold")[#it.at(0)]
          #if it.len() > 1 and it.at(1) != "" [
            #v(2pt)
            #text(size: bs * 0.86, fill: rgb("#5B6672"))[#it.at(1)]
          ]
          #v(9pt)
        ],
      )
    ]
  ]
}

// ---------- 横条图 ----------
#let barchart(items) = {
  if items.len() == 0 { return }
  let maxv = items.map(it => it.at(1)).fold(0.0, (a, b) => if b > a { b } else { a })
  if maxv <= 0 { maxv = 1 }
  block(width: 100%, above: 8pt, below: 10pt)[
    #for it in items [
      #grid(
        columns: (62pt, 1fr, 44pt),
        column-gutter: 6pt,
        align: (left + horizon, left + horizon, right + horizon),
        [#text(size: bs * 0.85)[#it.at(0)]],
        [
          // 不能用 place() 里的百分比：它相对页面而非这个格子，
          // 实测四条 32/45/28/61 画出来一样长。改用按比例分配的 layout + 固定轨道。
          #layout(size => {
            let track = size.width
            let ratio = it.at(1) / maxv
            box(
              width: track, height: 11pt, radius: 2pt, fill: soft,
            )[
              #box(
                width: ratio * track,
                height: 11pt,
                radius: 2pt,
                fill: accent,
              )
            ]
          })
        ],
        [#text(size: bs * 0.82, weight: "bold", fill: accent)[#it.at(1)]],
      )
      #v(5pt)
    ]
  ]
}

// ---------- 评分 ----------
#let rating(label, score, max: 5) = block(
  width: 62mm, above: 5pt, below: 5pt,
)[
  #grid(
    columns: (1fr, auto),
    align: (left, right),
    [#text(size: bs * 0.9)[#label]],
    [
      #for i in range(max) {
        box(
          width: 8pt, height: 8pt, radius: 1.8pt,
          fill: if i < score { accent } else { rgb("#DDE2EA") },
        )
        h(2.5pt)
      }
    ],
  )
]

// ---------- 对比双栏 ----------
#let compare(lt, lb, rt, rb) = {
  grid(
    columns: (1fr, 1fr), gutter: 9pt,
    block(
      width: 100%, radius: 4pt, fill: rgb("#EAF7F1"),
      stroke: 0.6pt + rgb("#BFE5D4"), inset: 11pt,
    )[
      #text(font: hf, size: bs * 0.92, weight: "bold", fill: rgb("#1F9A66"))[#lt]
      #v(4pt)
      #set text(size: bs * 0.88)
      #lb
    ],
    block(
      width: 100%, radius: 4pt, fill: rgb("#FDEDED"),
      stroke: 0.6pt + rgb("#F3C9C9"), inset: 11pt,
    )[
      #text(font: hf, size: bs * 0.92, weight: "bold", fill: rgb("#C43D3D"))[#rt]
      #v(4pt)
      #set text(size: bs * 0.88)
      #rb
    ],
  )
}

// ---------- 步骤 ----------
#let steps(items) = {
  block(width: 100%, above: 6pt, below: 8pt)[
    #for (i, it) in items.enumerate() [
      #grid(
        columns: (18pt, 1fr),
        column-gutter: 6pt,
        align: (center + top, left + top),
        [
          #v(1pt)
          #block(
            width: 15pt, height: 15pt, radius: 999pt, fill: accent,
            place(
              center + horizon,
              text(font: hf, size: bs * 0.72, weight: "bold", fill: white)[#(i + 1)],
            ),
          )
        ],
        [
          #text(size: bs * 0.92)[#it]
          #v(9pt)
        ],
      )
    ]
  ]
}

// ---------- 定义表 ----------
#let deflist(items) = block(width: 100%, above: 6pt, below: 8pt)[
  #for it in items [
    #block(
      width: 100%, inset: (x: 10pt, y: 7pt), radius: 3pt,
      fill: soft2, stroke: (left: 2.5pt + accent),
      above: 3pt, below: 3pt,
    )[
      #text(font: hf, size: bs * 0.9, weight: "bold", fill: accent)[#it.at(0)]
      #h(6pt)
      #text(size: bs * 0.9)[#it.at(1)]
    ]
  ]
]

// ---------- 目录 / 分页 ----------
// pagebreak用 Typst内置，不重定义（重定义会自递归）

#let sectiontoc() = {
  block(width: 100%, above: 10pt, below: 12pt)[
    #text(font: hf, size: bs * 1.4, weight: "bold")[目录]
    #v(8pt)
    #outline(title: none, indent: 1.2em, depth: 3)
  ]
  pagebreak()
}

// ---------- 行内 ----------
#let mark(body) = box(
  fill: rgb("#FFF3C4"), inset: (x: 2pt, y: 0.5pt), radius: 1.5pt,
)[#body]

#let tag(body, kind: "soft") = badge(body, kind: kind)

// blockquote别名（转换器会输出 #blockquote[...]）
#let blockquote(body) = quote(block: true)[#body]

// ---------- 文字环绕（meander） ----------
// 用法：wrap(body, obstacles: (位置: 宽x高, ...), gap)
// 位置可取：left-top / right-top / left-bottom / right-bottom
#let _wrap-pos(name) = {
  if name == "right-top" { top + right }
  else if name == "left-bottom" { bottom + left }
  else if name == "right-bottom" { bottom + right }
  else { top + left }
}

#let wrap(body, obstacles: ()) = {
  if obstacles.len() == 0 {
    body
  } else {
    meander.reflow({
      import meander: *
      for (pos, w, h) in obstacles {
        placed(_wrap-pos(pos), box(width: w, height: h, fill: luma(235), radius: 3pt))
      }
      container()
      content(body)
    })
  }
}
#let wrap-image(body, pos: "left-top", w: 42mm, h: 34mm) = {
  wrap(body, obstacles: ((pos, w, h),))
}

// ---------- 文字环绕图片（wrapimg） ----------
// 首行写 位置|宽|高|图片路径，其余行为正文。图片不存在时退化无色占位块。
#let wrapimg(body, pos: "left-top", w: 42mm, h: 34mm, src: none, radius: 4pt) = {
  meander.reflow({
    import meander: *
    if src != none {
      placed(_wrap-pos(pos), box(
        width: w, height: h, radius: radius, clip: true,
        image(src, width: w, height: h, fit: "cover"),
      ))
    } else {
      placed(_wrap-pos(pos), box(width: w, height: h, fill: luma(235), radius: radius))
    }
    container()
    content(body)
  })
}

// ---------- 竖排（basho） ----------
// 用法：vertical(body, cols: 3, size: 10pt, gap: 3pt)
#let vertical(body, cols: 1, size: 10pt, gap: 3pt) = {
  block(width: 100%)[
    #set text(size: size)
    #tate(config: (layout: (columns: cols, gap: gap, column-gap: 2em)))[#body]
  ]
}

// ---------- 幻灯片版式（16:9） ----------
// 设计：H1 = 一页幻灯片，pagebreak(weak:true) 让标题自动开新页。
// 所有版式函数只接受「已渲染的 content」，不碰 Markdown 解析。

#let _sl-w = 297mm
#let _sl-h = 167.06mm
#let _sl-pad = 15mm
#let _sl-bar = 20mm

// 页眉色条 + 标题（返回 (bar_content, spacer)）
#let slide-head(title, color: accent, tone: "fill") = block(
  width: 100%, above: 0pt, below: 0pt, breakable: false,
)[
  #place(top + left, dx: 0pt, dy: 0pt,
    block(width: _sl-w, height: _sl-bar,
      fill: if tone == "fill" { color } else { none },
      stroke: if tone == "fill" { none } else { (bottom: 2.5pt + color) },
    )[
      #place(left + bottom, dx: _sl-pad, dy: -6.5mm)[
        #text(font: hf, size: 20pt, weight: "bold",
          fill: if tone == "fill" { white } else { color })[#title]
      ]
    ])
  #v(_sl-bar + 6mm)
]

// 内容区：定宽 + 左右留边，之后 grid 的 1fr 才能撑满
#let slide-body(body) = block(width: 100%)[#body]

// ---- 1. 封面 ----
#let slide-cover(title, subtitle: none, kicker: none, meta: none) = {
  pagebreak(weak: true)
  place(top + left, dx: -15mm, dy: 0pt,
    block(width: _sl-w, height: _sl-h,
      fill: gradient.linear(soft2, rgb("#FFFFFF"), angle: 150deg))[
    ])
  place(top + left, dx: -15mm, dy: 0pt,
    block(width: 9mm, height: _sl-h,
      fill: gradient.linear(accent, accent2, angle: 180deg)))
  place(top + left, dx: 6mm, dy: 52mm, block[
    #if kicker != none [
      #box(radius: 999pt, stroke: 1pt + accent, inset: (x: 13pt, y: 5.5pt),
        text(font: hf, size: 10pt, fill: accent)[#kicker])
      #v(14pt)
    ]
    #block(width: 190mm,
      text(font: hf, size: 40pt, weight: "bold", fill: ink)[#title])
    #v(11pt)
    #block(width: 52mm, height: 4.5pt, radius: 2.2pt,
      fill: gradient.linear(accent, accent2))
    #if subtitle != none [
      #v(13pt)
      #block(width: 200mm, text(font: bf, size: 14pt, fill: luma(90))[#subtitle])
    ]
  ])
  if meta != none [
    #place(bottom + left, dx: 24mm, dy: -18mm, block(width: 200mm)[
      #block(width: 100%, height: 0.5pt, fill: lc)
      #v(7pt)
      #text(font: bf, size: 10pt, fill: luma(120))[#meta]
    ])
  ]
}
// ---- 2. 章节分隔页 ----
#let slide-section(num, title, note: none) = {
  // 这里不能写 pagebreak：slide 主题下每个 # 一级标题已经强制分页了，
  // 再加一次会把标题留在上面一页、渐变页另起一页（pdf_lint 实测报空白页）。
  place(top + left, dx: -15mm, dy: 0pt,
    block(width: _sl-w, height: _sl-h, fill: gradient.linear(accent, accent2, angle: 135deg)))
  place(center + horizon, dx: 0pt, dy: -8mm, block[
    #text(font: hf, size: 96pt, weight: "bold", fill: white.transparentize(70%))[#num]
  ])
  place(center + horizon, dx: 0pt, dy: 16mm, block[
    #text(font: hf, size: 34pt, weight: "bold", fill: white)[#title]
  ])
  if note != none [
    #place(center + horizon, dx: 0pt, dy: 34mm, block(width: 160mm,
      align(center, text(font: bf, size: 13pt, fill: white.transparentize(25%))[#note])))
  ]
}

// ---- 3. 三栏（或 N 栏）卡片 ----
#let slide-cols(items, cols: 3, gap: 6mm) = {
  block(width: 100%, grid(columns: (1fr,) * cols, gutter: gap,
    ..items.map(((t, b)) => block(
      width: 100%, radius: 4pt, inset: 6mm,
      stroke: 0.6pt + lc, fill: soft2,
    )[
      #block(width: 100%, text(font: hf, size: 14pt, weight: "bold", fill: accent)[#t])
      #v(2.6mm)
      #block(width: 100%, text(font: bf, size: 12.5pt, fill: luma(70))[#b])
    ])))
}

// ---- 4. 大数字 ----
#let slide-stats(items, cols: 2, gap: 8mm) = {
  grid(columns: (1fr,) * cols, gutter: gap,
    ..items.map(((val, lab, col)) => block(
      width: 100%, radius: 4pt, inset: (x: 6mm, y: 5mm),
      stroke: 0.6pt + lc, fill: soft2,
    )[
      #block(width: 100%, text(font: hf, size: 54pt, weight: "bold", fill: col)[#val])
      #v(2mm)
      #block(width: 14mm, height: 2.6pt, radius: 1.3pt, fill: col)
      #v(3mm)
      #block(width: 100%, text(font: bf, size: 12.5pt, fill: luma(105))[#lab])
    ]))
}

// ---- 5. 对比栏 ----
#let slide-compare(lh, lb, rh, rb, accent_l: none, accent_r: none) = {
  let cl = if accent_l == none { accent } else { accent_l }
  let cr = if accent_r == none { accent2 } else { accent_r }
  grid(columns: (1fr, 1fr), gutter: 7mm,
    block(width: 100%, radius: 4pt, inset: 6mm, stroke: 0.7pt + cl, fill: soft2)[
      #block(width: 100%, text(font: hf, size: 14.5pt, weight: "bold", fill: cl)[#lh])
      #v(3mm)
      #block(width: 100%, text(font: bf, size: 12.5pt, fill: luma(70))[#lb])
    ],
    block(width: 100%, radius: 4pt, inset: 6mm, stroke: 0.7pt + cr, fill: soft2)[
      #block(width: 100%, text(font: hf, size: 14.5pt, weight: "bold", fill: cr)[#rh])
      #v(3mm)
      #block(width: 100%, text(font: bf, size: 12.5pt, fill: luma(70))[#rb])
    ])
}

// ---- 6. 竖排要点（时间线 / 流程） ----
#let slide-flow(items, numbered: true) = {
  let n = items.len()
  block(width: 100%)[
    #for (i, (t, b)) in items.enumerate() {
      grid(columns: (11mm, 1fr), gutter: 4mm,
        align(center + top, stack(
          dir: ttb,
          spacing: 0pt,
          block(width: 8.4mm, height: 8.4mm, radius: 999pt, fill: accent,
            align(center + horizon,
              text(font: hf, size: 11pt, weight: "bold", fill: white,
                if numbered { str(i + 1) } else { "•" }))),
          if i < n - 1 {
            block(width: 1.4pt, height: 13mm, fill: lc)
          },
        )),
        block(width: 100%, inset: (top: 0.4mm))[
          #block(width: 100%, text(font: hf, size: 14pt, weight: "bold", fill: ink)[#t])
          #v(1.8mm)
          #block(width: 100%, text(font: bf, size: 12.5pt, fill: luma(75))[#b])
          #v(4mm)
        ])
    }
  ]
}

// ---- 7. 引言页 ----
#let slide-quote(text-body, who: none) = {
  place(center + horizon, dx: 0pt, dy: -6mm, block(width: 225mm)[
    #text(font: hf, size: 66pt, fill: accent.transparentize(72%))[“]
    #block(width: 100%, inset: (left: 4mm, right: 4mm),
      text(font: hf, size: 23pt, fill: ink)[#text-body])
    #v(16pt)
    #block(width: 30mm, height: 3pt, radius: 1.5pt, fill: accent)
    #if who != none [
      #v(12pt)
      #block(width: 100%, text(font: bf, size: 12pt, fill: luma(110))[—— #who])
    ]
  ])
}

// ---- 8. 挂图页（左图右文 / 右图左文） ----
#let slide-split(body, side: "right", ratio: 0.46, gap: 9mm) = {
  // 页面已有 15mm 左右 margin，这里用内容可用宽度
  let w = _sl-w - 30mm
  let lw = w * ratio - gap / 2
  let rw = w * (1 - ratio) - gap / 2
  let first = body.at(0)
  let second = body.at(1)
  grid(
    columns: if side == "right" { (rw, lw) } else { (lw, rw) },
    gutter: gap,
    block(width: 100%)[#first],
    block(width: 100%)[#second],
  )
}
