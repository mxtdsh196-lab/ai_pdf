# 市场发布说明（ai_pdf）

> 发布 Operit 市场时直接复制。字段对应市场条目：`title / description / author / categoryId / 资源包`

---

## title

```
AI生成 PDF（Typst 排版）
```

## categoryId

```
business_productivity
```

（备选：`dev_code`）

## author

```
mxtdsh196-lab
```

---

## description（市场长描述，直接粘贴）

```markdown
# 只写 Markdown，出 Typst 质感的 PDF

让 AI 做 PDF，最大的坑不是排版能力，是**模型写不对排版语法**。这个包把输入锁死在 Markdown，转换器承担全部语法正确性——你不需要教模型写 Typst。

一份 3 页文档 0.6–0.9 秒。

---

## 能做什么

**24 个工具，覆盖从出稿到交付的全流程**

- `make_pdf`——Markdown 转 PDF，一手包办主题/配色/封面/组件/公式/Mermaid
- **`pdf_xray`——不用识图就知道自己写的东西长什么样**（v2.2 新增，详见下节）
- `render_pdf_preview`——渲染成 PNG 自检（**不是可选项**，只看 success 无法判断好不好看）
- `pdf_lint`——程序化版式体检：文字溢出、空白页、贴边、低 dpi 图、字体未嵌入
- 拆分 / 合并 / 抽页 / 按书签拆章 / 旋转 / 压缩
- AES-256 加密 / 去密码 / 水印 / 页眉页脚
- 字体覆盖检查 / 字体推荐 / 拼写建议
- CSV+模板批量生成 / docx·odt·html·xlsx 导入

**7 个版式 × 6 套配色**

report（报告讲义）、handout（黑体紧凑）、resume（简历）、editorial（杂志楷体）、minimal（极简）、certificate（证书风）、**slide（PPT 幻灯片）**

**31 类内容组件**（50 个名字/别名），写在 Markdown 里就行：

KPI 数据卡 / 胶囊徽章 / 六色提示框 / 卡片网格（1-6列）/ 对比双栏 / 进度条 / 环形进度 / 评分方块 / 横条图 / 时间线 / 编号步骤 / 定义表 / **文字环绕图片** / **竖排** / 自动目录

**16:9 幻灯片**

每个 `#` 一级标题自动一页，自动加色条页眉、自动隐藏页码。8 种预设版式：封面、章节页、大数字、多栏卡片、对比、流程、引言、挂图。

**4 种 Mermaid 图，全部自研零依赖**

不用 Chromium、不用 mmdc、不用联网：

flowchart（含 subgraph 底板）/ sequenceDiagram / gantt（含 milestone）/ classDiagram

**数学公式**

直接写 LaTeX，自动转 Typst。frac / sqrt / sum / int / lim / matrix / cases / 希腊字母 / vec / hat 等 100+ 命令。

---

## 不用识图，也能知道自己排了什么（v2.2）

**AI 做 PDF 最大的盲区：写完看不见。** 只看 `success: true`，不知道卡片有没有压边框、颜色有没有生效、阴影多重。

`pdf_xray` 直接反解 PDF 绘制指令，每页给四块：

| 输出 | 内容 |
|---|---|
| **布局字符画** | 形状画边框、文字显示原字，坐标就是真实坐标 |
| **可疑项** | 文字跨越边框 / 重叠 / 出界 / 豆腐块，**带精确 pt 数** |
| **特效清单** | 阴影外扩量、磨砂透明度、泛光描边透明度、渐变处数、噪点图尺寸、曲线路径 |
| **元素清单** | 每个块的 x / y / 宽 / 高 / 颜色 / 字号 |

三档详略：`detail=full` / `art`（只看图）/ `brief`（只看可疑+特效，最省 token）。

**它能报出识图说不出具体数值的东西。** 实测：

```
cross_border  文字跨越边框 1.5pt：'工程师'
              bbox=(170.1,368.3,201.6,378.8) 框=(56.7,125.3,538.6,369.8)
```

人眼看图能发现「压穿了」，但说不出压在哪、压了多少；这里直接给坐标和 pt 数。

> 开发这个包时它当场抓出两个我自己没看到的 bug：
> progress/ring/rating/chart 同行写法数据全丢、三张渐变图互相压穿。

## 特效强度全部可调（v2.2）

v2.1 的特效强度写死，AI 没有任何手段改。v2.2 全部开放，越界钳到边界并给 warning：

| 特效 | 参数 | 范围 |
|---|---|---|
| **阴影** | `sh-depth` / `sh-spread` / `sh-tint` | 0.5~12pt / 0~8pt / `light`·`mid`·`dark`·十六进制 |
| **磨砂** | `opacity` / `light` / `bar` / `border` | 0~100 / 0~100 / 长度 / 长度 |
| **磨砂颗粒** | `grain` / `grain-a` | 0.2~12（颗粒边长 pt，默认 1.8）/ 0~100（浓度，默认 38） |
| **磨砂衬底** | `bg` / `bg-c1` / `bg-c2` / `bg-angle` | `gradient`·`1`·图片路径 / 十六进制 / 十六进制 / 0~360 |
| **泛光** | `strength` / `width` | 0~100（越大越淡）/ 长度 |
| **噪点** | `alpha` | 0~1（写 `30` = 30%） |
| **渐变** | `angle` / `strength` | 0~360 / 0~1 |
| **波浪** | `amp` / `color` | 1~40 |

```markdown
::: cards2 style=shadow sh-depth=8pt sh-spread=4pt sh-tint=dark
::: fx glow strength=20 width=6pt
::: fx frost bg=gradient bg-c1=2547A8 bg-c2=BE123C bg-angle=120 grain=1.6 grain-a=42
::: fx gradient c1=2547A8 c2=7C3AED angle=270 strength=0.6
::: fx noise alpha=0.5
```

### 磨砂玻璃：真磨砂还是假半透明

Typst 0.15 的 `block` 不支持 `blur`，SVG `feGaussianBlur` 能做真模糊但**文字会被栅格化**——不可选、不可搜、不可复制，和这个包"文字永远由 Typst 排"的核心设计直接冲突，所以不走那条路。

最终用 **Typst 原生 `tiling` 矢量颗粒 + 顶部高光 + 底部反光线 + 亮边** 四层叠加。PDF 里 `images = 0`（颗粒走 `/Pattern` 不占图像对象），任意缩放不糊，文字照样可选可搜。

三个关键点：

1. **磨砂必须压在内容上才看得出来。** 白纸上的磨砂就是一块浅蓝灰矩形。底色默认 `#DCE7F5`（纯白底 + 白颗粒 + 白描边在白纸上等于看不见），要效果就加 `bg=` 做衬底。
2. **`grain` 是颗粒边长，不是透明度别名。** 实测比例 0.42：`grain=1.2` → 0.5pt，`1.8` → 0.8pt，`2.6` → 1.1pt。
3. **验收必须 600dpi。** 1.2pt 颗粒在 150dpi 缩略图里只有 2.5px，糊成一片，很容易误判成"没渲染"。

---

## 为什么不容易踩坑

大多数 PDF 工具的问题是**错了不告诉你**。这个包把「让工具自己开口」当核心设计：

写错组件名、`:::` 忘闭合、表格少了竖线、图片路径不存在、颜色格式不对、字体名拼错、LaTeX 命令不支持……

统统进 `warnings` 返回，产物照出，但你会明确知道哪里错了。

早期版本我自己就踩过这些：60 行表格只渲染 39 行不报错、`font_dir` 写错永远发现不了、组件名写错整块消失。现在这些都变成了会开口的告警。

---

## 性能

| 场景 | 实测 |
|---|---|
| 3 页报告（含封面） | 0.58–0.91 s |
| 8 页幻灯片 | < 1 s |
| 预览渲染（100dpi 单页） | 约 0.5 s |

对比 WeasyPrint 方案（9 秒）约 **10 倍**。

---

## 依赖

首次使用会自动检查并下载 typst 静态二进制（48 MB）。需要 pandoc、PyMuPDF、Ghostscript。

中文字体默认用系统 Noto Serif/Sans CJK SC。包内不含字体（体积太大），但支持 `font_dir` 指向你自己的字体库。

---

## 快速开始

```
用 ai_pdf 生成一份 PDF，主题 report，配色 blue
```

或者直接：

```
theme=slide，做一个 8 页的技术汇报
```

---

## 已知限制

- Mermaid 只覆盖上述 4 种图，pie / stateDiagram 未实现
- 表格无斑马纹（设计上只留蓝色表头）
- 竖排用日文禁则，中文「。」是竖排形式
- **`pdf_xray` 只读几何与绘制指令，看不到「好不好看」**，审美仍需人判断

---

代码开源：https://github.com/mxtdsh196-lab/ai_pdf
Bug 和需求欢迎提 issue。
```

---

## 资源文件

```
dist/ai_pdf.js
大小：573694 字节
sha256：988a225c6c69afe9ad5a6a2492aa571ea93058f9d5db36e63deaadcb79e21709
Release：v2.2.0
```

## 提交步骤（网页端）

1. 打开 Operit 市场发布页
2. 类型选 **Script / 沙盒包**
3. 填 title、description（上面那段）、categoryId `business_productivity`
4. 上传 `dist/ai_pdf.js`
5. 关联仓库填 `https://github.com/mxtdsh196-lab/ai_pdf`
6. 提交审核

> ⚠️ 上传前先在本地跑一次 `pdf_selfcheck`，确认三件依赖都在，否则新用户第一次会直接失败。