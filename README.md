# ai_pdf

**给 AI 用的中文 PDF 排版包。只写 Markdown，排版正确性由转换器保证。** 引擎 Typst，3 页文档 0.6–1 秒。

> 核心设计原则：**不让模型写 Typst**。Typst 的括号与模式对 LLM 太脆弱，输入锁死在 Markdown，转换器承担全部语法正确性。

---

## 亮点

- **23 个工具**：生成、体检、拆分、合并、加密、水印、字体检查、批量生成
- **7 个版式 + 6 套配色**，含 16:9 **PPT 幻灯片**（8 种预设版式）
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


## 代码结构（v2.2）
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
└── typst-libs/      60 文件  meander（环绕）+ basho（竖排）
                    8117 行
```
打包体积 **553 KB**。

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
└── typst-libs/      60 文件  meander（环绕）+ basho（竖排）
                     5972 行
```

`gen_package.py`（打包器）在构建分支里，用于把源码打成 Operit 沙盒包。

---

## 许可证

代码 MIT。内置 Typst 库 `meander` 与 `basho` 遵循各自原仓库许可。
字体不随仓库分发，请自行下载对应免费商用字体。
