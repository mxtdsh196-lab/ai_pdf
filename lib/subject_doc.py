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
])

if __name__ == '__main__':
    print(SUBJECT_DOC)
    print('---lines:', SUBJECT_DOC.count(chr(10)) + 1)
