# -*- coding: utf-8 -*-
"""学科图形速查（数学/物理/化学/流程图）。

只放「AI 会踩的坑」和「最小可用示例」，全部实测过。
独立成文件：这段要保留真实换行，拼进 gen_package 的元组会被折叠。
"""

SUBJECT_DOC = "\n".join([
    "【学科图形】用 ::: draw 在正文嵌 Typst 代码，数学/化学/物理/流程图都走它。",
    "格式（代码块前后必须空行，::: 独占一行，不能带参数）：",
    "::: draw",
    "",
    "```typ",
    "#import \"@preview/cetz:0.5.3\" as cetz",
    "#cetz.canvas({ import cetz.draw: *\n  line((0,0),(2,0)); circle((0,0), radius: .3) })",
    "```",
    "",
    ":::",
    "【函数图】#import \"@preview/cetz-plot:0.1.4\": plot",
    "plot.add((x => x*x-1), domain: (-3,3), style: (stroke: red+1pt))   ← 数据是位置参，线型写 style: (stroke:)",
    "弧度用 x*calc.pi/180（本机无 calc.rad）；椭圆就返回元组 (x => (3*cos, 2*sin))",
    "【collage 里 pos= 与 x,y 同时写时，x,y 会被忽略】要么给 pos= 锚点+pad=，要么纯给 x,y，别混用。",
    "【立体几何】ortho/perspective 是包裹式，不是设置状态：",
    "ortho(x: (1,-.55), y: (1,.55), z: (0,1), { line((0,0,0),(3,0,0)) })",
    "【化学结构式】#import \"@preview/molchemist:0.1.6\": *",
    "#render-smiles(\"c1ccccc1\", skeletal: true)   ← 苯；乙醇 CCO；乙酸 CC(=O)O",
    "★ 不加 skeletal 会画出全部氢（中学要骨架式）",
    "【化学方程式】#import \"@preview/chemformula:0.1.3\": ch  →  #ch(\"2H2+O2->2H2O\")",
    "【流程图/框图】#import \"@preview/fletcher:0.6.0\" as f: diagram, node, edge",
    "node((0,0), [开始], corner-radius: 8pt, fill: white, stroke: black+.7pt)",
    "坑：矩形框用 corner-radius（写 radius 会缩成字中间一个小圈）；shape 传字符串 \"diamond\"；必须给 fill: white",
 "【分子模型·球棍/空间填充/VSEPR】不用 import，主题已预置：",
 "#mol[H2O]球棍；#molspace[H2O]空间填充；#mol[H2O, width:34mm]调尺寸",
 "预置14个：H2O CO2 CH4 NH3 BF3 SO2 H2S HCl H2 Cl2 N2 PCl5 SF6 CCl4（写大写）",
 "★空间填充默认不标元素符号（球相叠会压字）；要标就调 #molecule并传 labels: true",
 "★自己搭：#ball((x,y), r,颜色, lab: [O])放在 cetz.canvas({...})里",
 "【结构式与模型分工】骨架式/平面式用 molchemist的 SMILES；立体球棍与 VSEPR用 #mol；空间填充用 #molspace",
 "【平面几何】#import \"@preview/ctz-euclide:0.3.0\": *",
 "#ctz-canvas({ import cetz.draw: * ; ctz-init() ←必须先调，不调点注册不上",
 " ctz-def-points(A: (0,0), B: (4.2,0), C: (1.3,2.9)) ←必须用命名参数，不能传位置参",
 " ctz-draw-line(\"A\", \"B\", \"C\", \"A\", stroke: black +0.9pt)",
 " ctz-draw(circumcircle: (\"A\",\"B\",\"C\"), stroke: rgb(\"#2F5BEA\") +0.7pt) ←外接圆；incircle=内切圆",
 " ctz-draw-points(\"A\",\"B\",\"C\")",
 " ctz-draw-labels(\"A\",\"B\",\"C\", A: \"below left\", B: \"below right\", C: \"above\")",
 " ctz-draw-angle(\"A\", \"B\", \"C\", radius:0.45) ←角标",
 "})",
 "其它可用：ctz-draw(path: \"A--B->C\")、segment、semicircle、arc、ellipse、parabola；ctz-def-circumcenter/centroid/incenter等三角形中心",
 "【电路元件】#import \"@preview/zap:0.6.0\"",
 "#zap.circuit({ import zap: *",
 " node(\"A\", (0,0))",
 " battery(\"b1\", \"A\", (rel: (0,2.8)), v: $E$) ←电池，v=电动势",
 " resistor(\"r1\", \"b1\", (rel: (3.4,0)), i: $I$) ←电阻，i=电流箭头",
 "})",
 "元件名可用的：resistor capacitor inductor battery switch lamp fuse diode transistor opamp logic；签名 (名称,起点, (rel:相对增量),标签)",
 "★实测：单个或两个元件能画；三个以上会挤在一起（rel语义不确定）、开关会被覆盖、闭合回路的 wire拐角也摸不清。要规整电路图就用 cetz原生 line画矩形回路、元件按绝对坐标摆，或者直接用 cetz手绘（矩形=电阻、长短平行线=电池、斜线=开关）",
])

if __name__ == '__main__':
    print(SUBJECT_DOC)
    print('---lines:', SUBJECT_DOC.count(chr(10)) + 1)
