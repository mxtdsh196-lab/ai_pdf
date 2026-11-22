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

// ---------- 页面 ----------
#set page(
  paper: cfg.paper,
  margin: if cfg.slide { (x: 15mm, y: 0mm) } else { cfg.margin },
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

// ---------- 标题 ----------
#show heading.where(level: 1): it => {
  if cfg.slide {
    // 幻灯片模式：每个 H1 = 新一页，页眉色条横贯整页
    pagebreak(weak: true)
    // margin 已由 set page 设为 (x:15mm, y:0)，这里用负偏移让色条贴到纸边
    place(top + left, dx: -15mm, dy: 0pt,
      block(width: 297mm, height: 20mm, fill: accent)[
        #place(left + bottom, dx: 15mm, dy: -6.5mm)[
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
#let card(title, body) = block(
  width: 100%, radius: 4pt, fill: white,
  stroke: 0.6pt + lc, inset: (x: 12pt, y: 10pt),
)[
  #if title != "" [
    #text(font: hf, size: bs * 0.95, weight: "bold", fill: accent)[#title]
    #v(4pt)
  ]
  #set text(size: bs * 0.9)
  #body
]

#let cardgrid(items, cols: 2) = {
  if items.len() == 0 { return }
  grid(
    columns: (1fr,) * cols, gutter: 8pt,
    ..items.map(it => card(it.at(0), it.at(1))),
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
          #block(
            width: 100%, height: 11pt, radius: 2pt, fill: soft,
            place(
              top + left,
              block(
                width: (it.at(1) / maxv) * 100%,
                height: 11pt,
                radius: 2pt,
                fill: accent,
              ),
            ),
          )
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
  pagebreak(weak: true)
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
