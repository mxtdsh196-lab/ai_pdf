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

## 统一样式系统（v2.1 新增）

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

## 特效层（v2.1 新增）

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

## 商业组件（v2.1 新增）

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

## 代码结构（v2.1）

```
lib/
├── core.py         1499 行  Typst 后端：cfg / 封面 / 编译 / 23 个 PDF 命令
├── md2typst.py     1799 行  Markdown → Typst 转换器
├── theme2.typ      1036 行  主题引擎 + 样式系统 + 特效 + 商业组件
├── gen_package.py   745 行  打包器（base64 内嵌 → ai_pdf.js）
├── texmath.py       340 行  LaTeX → Typst 数学
├── mermaid.py       631 行  flowchart 渲染器
├── mermaid2.py      590 行  sequence / gantt / classDiagram
├── fxgen.py         154 行  SVG 特效生成（装饰层）
├── qrgen.py         412 行  QR 码编码器（零依赖）
└── typst-libs/      60 文件  meander（环绕）+ basho（竖排）
                     7206 行
```

打包体积 **445 KB**。

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
