# ai_pdf

**给 AI 用的中文 PDF 排版包。只写 Markdown，排版正确性由转换器保证。** 引擎 Typst，3 页文档 0.6–1 秒。

> 核心设计原则：**默认不让模型写 Typst**。Typst 的括号与模式对 LLM 太脆弱，输入锁死在 Markdown，转换器承担全部语法正确性。

---

## 亮点

- **24 个工具**：生成、体检、拆分、合并、加密、水印、字体检查、批量生成
- **7 个版式 + 6 套配色**，含 16:9 **PPT 幻灯片**（8 种预设版式）
- **学科图形**：函数图、立体几何、化学结构式（SMILES一行出苯环）、流程图，12个 Typst包已内置，离线可用
- **26 类内容组件**：KPI 卡、进度条、环形进度、时间线、对比栏、定义表、发票、证书、简历、菜单、海报……
- **统一样式系统**：`style` / `radius` / `tone` 三个词控制阴影、玻璃、渐变、描边
- **特效层**：泛光、磨砂、噪点、流体渐变、自定义曲线（**SVG 只做装饰，文字仍可搜索**）
- **真实可扫二维码**：零依赖自研编码器，从 PDF 抠图解码验证通过
- **文字环绕真实图片**（meander）、**中英日竖排**（basho）
- **4 种 Mermaid 图全自研**：flowchart / sequenceDiagram / gantt / classDiagram，零外部依赖
- **`pdf_lint` 程序化版式体检**：不靠人眼找溢出、空白页、低 dpi 图
- **20+ 类输入校验**：写错了工具自己开口，不靠调用方下次小心

---

---

## 统一样式系统（v2.2 新增）

AI 只需记住 **3 个词**，不用碰具体像素：

| 参数 | 取值 |
|---|---|
| `style` | `flat` / `shadow` / `glass` / `gradient` / `outline` |
| `radius` | `0` / `4` / `8` / `pill` |
| `tone` | `primary` / `success` / `warn` / `danger` / `neutral` / `soft` |

```markdown
::: cards2 style=shadow radius=8 tone=success
### 阴影卡片

文字仍可选中、可搜索。
:::
```

行内颜色：

```markdown
[红色警示]{color=danger}    ← 语义色
[品牌蓝]{color=#BE123C}     ← 任意十六进制
[渐变字]{gradient=true}      ← 主题渐变
```

---

## 特效层（v2.2 新增）

**核心设计：SVG 只做背景/装饰，正文永远由 Typst 排。**
所以磨砂、泛光卡片里的文字**仍然可选中、可搜索、可复制**——实测 5/5 文本可从 PDF 文本层提取。

| 组件 | 效果 | 能放正文 |
|---|---|---|
| `::: fx glow` | 泛光卡片 | ✅ |
| `::: fx frost` | 磨砂玻璃卡片 | ✅ |
| `::: fx gradient c1=2547A8 c2=7C3AED` | 流体渐变 | ✅ |
| `::: fx noise` | 噪点纹理 | — |
| `::: fx wave` | 波浪分割线 | — |
| `::: curve M10,70 C60,20 140,95 270,30` | 自定义贝塞尔曲线 | — |

> **体积提醒**：噪点用栅格 PNG 而非 SVG `feTurbulence`。后者会把噪点渲染成海量 path，实测一份 3 页文档从 37KB 涨到 3.4MB；改用 PNG 后 257KB。

---

## 商业组件（v2.2 新增）

| 组件 | 写法 | 说明 |
|---|---|---|
| `::: invoice` | `品名\|数量\|单价` | **小计与合计自动计算** |
| `::: cert` | `name\|张三  title\|证书名  body\|正文` | 双层边框、签署栏、编号 |
| `::: resume` | `时间\|标题\|描述` | 简历时间线 |
| `::: skills` | `标签1\|标签2\|标签3` | 技能标签组 |
| `::: menu` | `菜品\|价格\|备注` | 菜单 |
| `::: poster` | `hero\|主标题  when\|时间` | 海报主视觉 |
| `::: price` | `套餐\|价格\|功能1,功能2\|推荐` | 价格表 |
| `::: faq` | `问题\|答案` | 静态问答 |
| `::: team` | `姓名\|职位\|简介` | 团队介绍 |
| `::: capsule` | `标题文字` | 圆角胶囊标题 |
| `::: qrcode` | `内容\|说明` | **真实可扫二维码** |

### 二维码：零依赖自研编码器

`lib/qrgen.py`（412 行）从零实现 QR 编码：字节模式、纠错 L/M/Q/H、版本 1–10、8 种掩码自动择优。

**验证方式不是"看着像二维码"**：
- 自写解码器反解 **7/7 通过**（v1–v6、中英文、1–100 字节）
- 真实 PNG 反解 **12/12 通过**（四纠错等级）
- **从生成的 PDF 里抠图再解码成功** → 解出原 URL

---

## 读图能力：pdf_xray（v2.2）

AI 写完 Markdown 后，**不用识图**就能知道自己放出来的东西长什么样。

`pdf_xray` 直接反解 PDF 的绘制指令，每页给四块：

| 输出 | 内容 |
|---|---|
| **布局字符画** | 形状画边框、文字显示原字，坐标就是真实坐标 |
| **可疑项** | 文字跨越边框 / 文字重叠 / 出界 / 豆腐块，**带精确 pt 数** |
| **特效清单** | 阴影外扩量、磨砂透明度、泛光描边透明度、渐变处数、噪点图尺寸、曲线路径 |
| **元素清单** | 每个块的 x / y / 宽 / 高 / 颜色 / 字号 |

三档详略：`detail=full`（默认）/ `art`（只看图）/ `brief`（只看可疑+特效，最省 token）。

**它能报出识图说不出具体数值的东西。** 实测：

```
缺陷文档 → cross_border  文字跨越边框 1.5pt：'工程师'
                           bbox=(170.1,368.3,201.6,378.8) 框=(56.7,125.3,538.6,369.8)
修复后   → 0 条
```

人眼看图能发现「压穿了」，但说不出压在哪、压了多少；这里直接给坐标和 pt 数。

### 三条数据源，缺一不可

| 接口 | 能拿到 | 拿不到 |
|---|---|---|
| `get_bboxlog()` | **`fill-shade`（渐变/图案填充）**、绘制顺序 | 颜色 |
| `get_drawings()` | 精确 fill / stroke / opacity | **看不见 pattern 填充** |
| `get_text('dict')` | 文字、字号、字体、bbox | 图形 |

> 只靠 `get_drawings()` 会漏掉整页渐变——实测 slide 章节页的满屏渐变在 drawings 里是 **0 条**，只有 bboxlog 能看见。

### 判据踩过的坑

- `dh < 8` 挡掉了 `dh == 8.0`：`sh-depth=8pt` 正好落在开区间外 → 该用 `<=`
- `stroke_opacity < 0.45` 挡掉了 `strength=20`（opacity 0.80）：泛光**调强**反而识别不到
- 中文全角占 2 个终端列，不区分的话字符画整体错位
- 引号、顿号这类单字符 span 与正文行框相交是中文排版常态，重叠判定要排除

---

## 特效强度全部可调（v2.2）

v2.2 的特效强度是写死的，AI 没有任何手段改。v2.2 全部开放，越界钳到边界并给 warning：

| 特效 | 参数 | 范围 |
|---|---|---|
| **阴影** | `sh-depth` / `sh-spread` / `sh-tint` | 0.5~12pt / 0~8pt / `light`·`mid`·`dark`·6 位十六进制 |
| **磨砂** | `opacity` / `light` / `bar` / `border` | 0~100 / 0~100 / 长度 / 长度 |
| **磨砂颗粒** | `grain` / `grain-a` | 1.5~10（颗粒边长 pt，默认 **4**）/ 0~100（白颗粒浓度，默认 42） |
| **磨砂衬底** | `bg` / `bg-c1` / `bg-c2` / `bg-angle` | `gradient`·`1`·图片路径 / 6 位十六进制 / 6 位十六进制 / 0~360 |
| **泛光** | `strength` / `width` | 0~100（越大越淡）/ 长度 |
| **噪点** | `alpha` | 0~1（写 `30` = 30%） |
| **渐变** | `angle` / `strength` | 0~360 / 0~1 |
| **波浪** | `amp` / `color` | 1~40 |

```markdown
::: cards2 style=shadow sh-depth=8pt sh-spread=4pt sh-tint=dark
::: fx glow strength=20 width=6pt
::: fx frost opacity=60 light=0 bar=8pt
::: fx gradient c1=2547A8 c2=7C3AED angle=270 strength=0.6
::: fx noise alpha=0.5
```
参数是否生效，用 xray 直接验：调重后阴影外层从 `外扩 0.5×1.0pt` 变成 `4.0×8.0pt`，阴影色从 `#E8E8E8` 变 `#B4B4B4`。

### 磨砂玻璃怎么做到"真磨砂"

`block(blur:)` 在 Typst 0.15 不支持（实测 `unexpected argument: blur`）。SVG `feGaussianBlur` 能做真模糊，但**文字会被栅格化**，不可选不可搜，与这个包的核心设计直接冲突，所以否决。

最终方案是 **双层矢量颗粒**（深点 + 白点错位半格）+ 顶部高光 + 底部反光线，叠在 `block(inset: 0pt, clip: true)` 里：

- PDF 里 `images = 0`，颗粒走 `/Pattern`（`/p0 scn`），只有几 KB
- 矢量点阵，任意缩放不糊
- 文字仍由 Typst 排，可选中、可搜索、可复制

```markdown
::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 opacity=40 grain=4
磨砂玻璃压在渐变上，下层色彩透上来
:::
```

**必须是双层颗粒的原因（三个实测踩坑）：**

1. **单层白颗粒在白底上等于没有。** 白点叠 `#DCE7F5` 45% 底色的对比度只有 **3.1 灰阶 = 1.2%**，肉眼完全不可见；而且 `grain-a` 越大点越白、越看不见——参数方向是反的。所以必须有深色粒子把底色压暗，才有砂面质感。
2. **`transparentize(100%)` 是全透明，不是「完全不透明」。** 之前用 `calc.min(100%, ga * 2.4)` 给深颗粒上色，直接把它变成看不见，标准差从 6.66 掉到 1.46。深颗粒透明度固定 30%。
3. **`place` 没有 `dx` 参数。** 写 `place(center + horizon, dx: ...)` 会让整个 `tiling` 塌成一个 tile。错位要用 `move(dx: ...)` 包住内容。

**`grain` 默认 4pt 而不是 1.8pt。** 1.8pt 的颗粒在 100~150dpi 下只有 2~3px，糊成一片；实测就是这个原因让人觉得「磨砂没有效果」。要更粗可到 7~10，颗粒大到肉眼可数。

**验收看像素标准差，不要只看图。** 白纸上的磨砂用 600dpi 采样卡片纯色区，标准差应 ≥ 15；如果接近 0，说明颗粒层根本没画出来。

---
**修掉的两个假参数：**

1. `gradient_blob(angle=)` 签名里有、函数体**完全没用** —— 6 个角度输出 md5 全同 `5dde039ef4`。现在两个径向光斑按角度绕中心对向分布。
2. `radius=pill` 输出成 `rad: pill`（缺引号），Typst 当变量名解析直接编译失败。

---


## 自由拼贴 collage（v2.3 大幅扩展）

整页绝对定位排版。每个图层一行，坐标单位 mm。

```markdown
::: collage w=267 h=137.06 bg=paper palette_from=1F3A5F

bgimg|src:wpphoto:mountain     照片铺满当底（可写 URL 源，见下）
mask|001436|45                 整页蒙版，第二段是透明度 0~100
img|/path/a.jpg|0,0|70,50|shape=arc k=0.28 pos=left-top pad=14 bw=1.2 bc=FFFFFF
text|标题|0,0|160|pos=left-top pad=22 size=30 weight=bold font=BodoniModa_400i color=accent track=8
block|正文|0,0|120,40|pos=right-bottom pad=20 fill=deep color=paper size=9 pad=5
vtext|竖排|0,0|24,90|pos=right-top pad=14 size=13 cols=1 gap=4
oval|/path/c.jpg|0,0|70,70|pos=center-middle pad=0
dot|8FA3BD|0,0|2.5|pos=left-bottom pad=30
ring|8B8070|0,0|3|pos=right-middle pad=30 w=0.8
line|C9D6E5|0,0|120,0|pos=left-top pad=40 w=0.5
curve|M10,70 C60,20 140,95 270,30|0,0|60,20|pos=center-bottom pad=10 color=BE123C w=1.5
orn|8B8070|0,0|40,12|pos=center-top pad=10 w=1
:::
```

### 定位：pos 锚点，不用手算坐标

`pos=` 取 `left`/`center`/`right` × `top`/`middle`/`bottom` 的组合，配 `pad=` 边距，x,y 段写 `0,0` 占位即可。工具会按**真实版心**（页面减去 margin）算位置。

也可以直接给 `x,y`。

### 异形裁剪：shape=

`rect`(默认) / `arc`(左上大圆角) / `arc4`(四角圆角) / `slant`(斜切) / `notch`(缺角) / `ellipse` / `arch`(拱顶) / `wave`(波浪底)。

`k=` 弧度比例，默认 0.26（0.02~0.49）。描边 `bw`/`bc` 在异形上同样生效。

照片会自动预裁到**精确目标比例**，不会变形——这一步必须做，因为 Typst 算 SVG 包围盒用的是 `<image>` 在 `slice` 展开后的尺寸，不是 viewport。实测 600×404 的 SVG 声明 `width:86mm` 会画出 97.2mm（放大 1.13 倍），预裁 + `preserveAspectRatio='none'` 才能得到 86.0mm。

### 画布会自动收进版心

写 `w=297`（页面宽）但主题 `margin=15mm` 时，版心只有 267mm，画布会向右溢出。现在会**自动等比缩到版心**并告警，图形和字号一起缩。

想让画布真的铺满整页，显式写 `margin=0mm`。

---

## 角色色阶 palette_from（v2.3）

给**一个**基色，工具用 **OKLab** 生成同色相的深→浅阶梯。AI 不用懂色彩学，只写角色名。

```markdown
::: collage w=267 h=137.06 bg=paper palette_from=1F3A5F
block|标题|0,0|120,30|fill=deep color=paper
:::
```

| 角色 | 用途 | 明度 |
|---|---|---|
| `deep` | 压照片 / 深色块底 | L=0.20 |
| `mid` | 次级色块 | L=0.46 |
| `veil` | 半透明蒙版色（配 alpha 用） | L=0.40 |
| `soft` | 中间调 | L=0.58 |
| `pale` | 页面 / 卡片浅底 | L=0.84 |
| `paper` | 近白纸色 | L=0.98 |
| `ink` | 正文墨色 | — |
| `accent` | 基色本身 | — |

`fill=` / `color=` / `bg=` 都支持角色名。也可以继续写十六进制精调。

**为什么不预设一堆配色**：参考图千变万化，预设永远追不完。给机制（给一个色相，自动出阶梯）比给答案（cinema/editorial/nature 等固定色板）更能适配新场景。

**为什么不用 cubehelix（如 `corkscrew` 包）**：cubehelix 生成的是**彩虹色阶**（黑→蓝→绿→金→粉→白），色相在变。它服务于数据可视化，目的是让不同数值视觉可分。排版色阶要的是「同一色相只变明度」——实测 cubehelix 输出跨越蓝绿金粉，不能当色阶用。

---

## 自动对比色（v2.3）

**不写 `color` 时，按底色亮度自动选黑字或白字。**

```markdown
block|文字|0,0|100,30|fill=1F3A5F            → 自动白字（11.5:1）
block|文字|0,0|100,30|fill=DDE5EC            → 自动黑字（14.5:1）
```

写了但对比度不够时会**告警并自动纠正**：

```
collage block 文字对比度只有 1.6:1（#141414 压在 #1F3A5F 上），
几乎看不清；已改成 #FFFFFF。
```

判据用 WCAG 2.1 标准：正文 ≥4.5:1，大字 ≥3:1。

**画布是背景照片（`bgimg`）时不做检查**，直接默认白字——照片亮度不可预知。

---

## 从网络取图（v2.3）

图片位置可以写 `src:` 开头的取图指令，工具会下载到本地缓存再交给 Typst。

```markdown
bgimg|src:wpphoto:mountain
img|src:wikimedia:coffee
img|src:picsum:night
```

| 前缀 | 来源 | 授权 | 实测 |
|---|---|---|---|
| `src:wpphoto:` | wordpress.org/photos | **CC0** | ✅ 原图约 4000px，铺 267mm ≈ 380dpi |
| `src:wikimedia:` | Wikimedia Commons | CC0（可筛） | ✅ 官方 API，偏「文献级」照片 |
| `src:picsum:` | picsum.photos | Unsplash | ✅ 免 key，但 seed 是哈希不是关键词 |

规则：
- **多词只用第一个词**。实测 `snow mountain` 在 wpphoto 返回 0 结果，而 `snow` 有 1327 张。
- **下划线当空格**：`src:wpphoto:snow_mountain` → 搜 `snow`。空格会被 `|` 分隔符截断。
- **别用 `@` 开头**：pandoc 会把 `@xxx` 解析成 Citation 节点，内容整段消失。这也是为什么用 `src:` 而不是 `@`。
- 取不到图会告警并跳过该图层，不会静默消失。

### 实测被 Cloudflare 挡死、不要浪费时间再试的站

| 站 | 证据 |
|---|---|
| pxhere | `cf-mitigated: challenge`，Turnstile 无法自动通过 |
| stocksnap | `__cf_chl_rt_tk` |
| creazilla / publicdomainpictures | 403 |
| cc0.cn / gahag | 连不上 |
| loremflickr | 500 |
| t.alcy.cc | 404 |
| openverse | 000 |

尝试过的手段全部无效：完整浏览器头（`Sec-CH-UA` / `Sec-Fetch-*`）、`--compressed`、真实无头浏览器（控制台报 `No available adapters`，Turnstile 找不到可用验证方式）。

**这些站都是 CC0 免费图库，本来就有合法途径。** 需要里面的图，人工挑好另存到本地目录，比任何绕过方案都稳。

---

## 竖排（v2.3 改真竖排）

`vtext` / `vertical` 改用 basho 的 `tate`，是**连续竖排**，不是逐字换行。

```markdown
vtext|色阶与竖排|0,0|24,90|pos=right-top pad=14 size=13 cols=1 gap=4
```

- `cols=` 分几列（1~8，默认 1），多列从右往左
- `gap=` 字间距
- 中文标点用竖排形式（，。等）

旧实现是 `每字 + linebreak()`，三个问题：英文被拆成单个字母（`Short` → `S/h/o/r/t`）、中文标点错位、超出高度的部分直接掉出画布。

⚠️ 踩过的坑：`#tate(...)` 的内容**不能套 `#text(...)`**，套了就退化成横排。正确写法是外层 `#set text(...)` 设样式，`tate` 里放纯文本。

---

## 版心传递（v2.3）

`md2typst` 现在知道真实版心尺寸（页面减 margin），由 `core.py` 在转换前通过 `set_ctx()` 传入。

不传的话 collage 会把用户写的 `w` 直接当画布大小，等于默认 `margin=0`，超出版心就向右溢出。这个 bug 表现为 `pdf_lint` 报 `graphic_overflow` 右 15mm。

⚠️ `a['margin']` 为空时必须回退到**主题默认值**（`THEMES[theme]['margin']`），否则版心算成整页，限幅等于没做。注意主题表叫 `THEMES`，`THEME` 是 theme2.typ 的文件路径（str）。

---

##  学科图形（v2.4）

数学的函数图、立体几何，化学的结构式和方程式，以及流程图、框图、网络拓扑，都不靠新工具，用一个 `::: draw`直接嵌 Typst代码。

为什么不做成参数化工具：这些东西本质是「按数学定义画线」，不是「调旋钮」。写 `x => x*x/2`就是抛物线，包成 `parabola(a=0.5)`反而画不了「椭圆+焦点+准线+切线」这种组合。

### 写法

三条硬约束：

1. `::: draw`独占一行，**后面不能带参数**（pandoc不认 `::: name k=v`）
2.代码块前后**必须空行**，否则不被识别成 fenced div
3.内层必须是代码块，代码原样插入，不转义不解析

### 内置12个包

|包 |干什么 |
|---|---|
| cetz0.5.3 /0.5.2 |绘图底座，API取法 TikZ |
| cetz-plot0.1.4 |函数图（带坐标轴、刻度、图例） |
| cetz-venn0.2.0 |韦恩图 |
| cetz-fields0.2.0 |向量场、库仑场 |
| fletcher0.6.0 |流程图、框图、网络拓扑 |
| molchemist0.1.6 |化学结构式，写 SMILES就出图 |
| alchemist0.2.0 |骨架式低层控制 |
| chemformula0.1.3 |化学方程式 |
| ezchem / physica / oxifmt / tidy |辅助 |

全部塞在 `ai_pdf.js`里（gzip+b64，267文件含4个 WASM），首次调用自动解包到 `typst-packages/`，**不联网也能用**。

### 三个例子

**苯环**（SMILES，不用算坐标）：`#render-smiles("c1ccccc1", skeletal: true)`。不加 `skeletal: true`会画出全部氢，中学要骨架式。

**函数图**：`#import "@preview/cetz-plot:0.1.4": plot`然后 `plot.add((x => x*x-1), domain: (-3,3), style: (stroke: red+1pt))`。

**流程图**（国标符号）：起止框 `corner-radius:8pt`，处理框 `corner-radius:2pt`，判断框 `shape: "diamond"`，输入输出 `shape: "parallelogram"`，箭头 `edge((0,0),(0,1), "->", label: [是])`。

### 容易踩的坑

- `plot.add`的数据是**位置参数**，写 `data:`报错
-线型写 `style: (stroke: red+1pt)`，直接 `stroke:`报错
-本机没有 `calc.rad`，弧度用 `x*calc.pi/180`
- `ortho` / `perspective`是**包裹式**：`ortho(x:..., y:..., z:..., {绘图代码})`
- `fletcher`矩形框用 `corner-radius`，写 `radius`会缩成字中间一个小圈
- `fletcher`的 `shape:`传**字符串**，不是函数
- `fletcher`必须给 `fill: white`，否则连线穿过节点文字

---

## 代码结构（v2.3）
```
lib/
├── core.py         1540 行  Typst 后端：cfg / 封面 / 编译 / 24 个 PDF 命令
├── md2typst.py     2032 行  Markdown → Typst 转换器
├── theme2.typ      1056 行  主题引擎 + 样式系统 + 特效 + 商业组件
├── gen_package.py   869 行  打包器（base64 内嵌 → ai_pdf.js）
├── pdfxray.py       477 行  PDF 反向解析：布局字符画 / 可疑项 / 特效清单
├── texmath.py       340 行  LaTeX → Typst 数学
├── mermaid.py       631 行  flowchart 渲染器
├── mermaid2.py      590 行  sequence / gantt / classDiagram
├── fxgen.py         170 行  SVG 特效生成（装饰层）
├── qrgen.py         412 行  QR 码编码器（零依赖）
├── colorkit.py     WCAG 2.1 对比度 + 自动前景色
├── oklch.py        OKLab/OKLCH 色彩空间 + 单色相明度阶梯
├── imgsrc.py       取图：wordpress/wikimedia/picsum 下载缓存
├── collage_doc.py  collage 语法说明（进工具描述）
└── typst-libs/      60 文件  meander（环绕）+ basho（竖排）
                    8117 行
```
打包体积 **658 KB**。

### 构建可复现

两次构建（间隔任意时间、任意目录）**逐字节相同**：

```bash
cd lib && AI_PDF_OUT=/tmp/a.js python3 gen_package.py
sleep 2 && AI_PDF_OUT=/tmp/b.js python3 gen_package.py
md5sum /tmp/a.js /tmp/b.js   # 完全一致
```

保证手段：gzip `mtime=0` + `json sort_keys=True` + `sorted(os.walk())`。

> 这两处曾经都漏过：一处 gzip 忘了 `mtime=0`，另一处 `os.walk` 顺序不定 → 同内容构建出不同字节（实测两侧差 1520 字节），市场发布报 `asset does not match the local artifact`。
---

## 快速开始

### 在 Operit 里用

```javascript
await use_package({ package_name: 'ai_pdf' })

await ai_pdf.make_pdf({
  output_path: '/sdcard/Download/report.pdf',
  content: '# 标题\n\n正文内容。',
  theme: 'report',
  palette: 'blue'
})

// 必做：渲染成图看一眼
await ai_pdf.render_pdf_preview({ pdf_path: '/sdcard/Download/report.pdf' })
```

### 独立跑（不依赖 Operit）

```bash
export AI_PDF_FONT_DIRS=/path/to/fonts      # 可选
export AI_PDF_PKG_DIR=/path/to/typst-packages  # 可选

cd lib
python3 core.py build '{"md_file":"a.md","out":"a.pdf","theme":"report"}'
```

依赖：`typst`（0.15+）、`pandoc`、`PyMuPDF`、`ghostscript`。

---

## 文档

| 文件 | 内容 |
|---|---|
| [`docs/代码结构.md`](docs/代码结构.md) | 文件职责、关键函数、调用细节（780 行） |
| [`docs/踩坑记录.md`](docs/踩坑记录.md) | **开发期所有 bug 的根因与修法，最有价值**（750 行） |
| [`docs/字体清单.md`](docs/字体清单.md) | 53 款免费商用字体详情 |
| [`examples/`](examples/) | 可跑示例 |

---

## 目录

```
lib/
├── core.py         1499 行  Typst 后端：cfg / 封面 / 编译 / 23 个 PDF 命令
├── md2typst.py     1436 行  Markdown → Typst 转换器（pandoc JSON AST）
├── theme2.typ       741 行  主题引擎：页面/标题/组件/幻灯片/环绕/竖排
├── texmath.py       340 行  LaTeX → Typst 数学转换
├── mermaid.py       631 行  flowchart 渲染器
├── mermaid2.py      590 行  sequence / gantt / classDiagram 渲染器
├── colorkit.py     WCAG 2.1 对比度 + 自动前景色
├── oklch.py        OKLab/OKLCH 色彩空间 + 单色相明度阶梯
├── imgsrc.py       取图：wordpress/wikimedia/picsum 下载缓存
├── collage_doc.py  collage 语法说明（进工具描述）
└── typst-libs/      60 文件  meander（环绕）+ basho（竖排）
                     5972 行
```

`gen_package.py`（打包器）在构建分支里，用于把源码打成 Operit 沙盒包。

---

## 许可证

代码 MIT。内置 Typst 库 `meander` 与 `basho` 遵循各自原仓库许可。
字体不随仓库分发，请自行下载对应免费商用字体。
