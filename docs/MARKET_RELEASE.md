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

**23 个工具，覆盖从出稿到交付的全流程**

- `make_pdf`——Markdown 转 PDF，一手包办主题/配色/封面/组件/公式/Mermaid
- `render_pdf_preview`——渲染成 PNG 自检（**不是可选项**，只看 success 无法判断好不好看）
- `pdf_lint`——程序化版式体检：文字溢出、空白页、贴边、低 dpi 图、字体未嵌入
- 拆分 / 合并 / 抽页 / 按书签拆章 / 旋转 / 压缩
- AES-256 加密 / 去密码 / 水印 / 页眉页脚
- 字体覆盖检查 / 字体推荐 / 拼写建议
- CSV+模板批量生成 / docx·odt·html·xlsx 导入

**7 个版式 × 6 套配色**

report（报告讲义）、handout（黑体紧凑）、resume（简历）、editorial（杂志楷体）、minimal（极简）、certificate（证书风）、**slide（PPT 幻灯片）**

**15 类内容组件**，写在 Markdown 里就行：

KPI 数据卡 / 胶囊徽章 / 六色提示框 / 卡片网格（1-6列）/ 对比双栏 / 进度条 / 环形进度 / 评分方块 / 横条图 / 时间线 / 编号步骤 / 定义表 / **文字环绕图片** / **竖排** / 自动目录

**16:9 幻灯片**

每个 `#` 一级标题自动一页，自动加色条页眉、自动隐藏页码。8 种预设版式：封面、章节页、大数字、多栏卡片、对比、流程、引言、挂图。

**4 种 Mermaid 图，全部自研零依赖**

不用 Chromium、不用 mmdc、不用联网：

flowchart（含 subgraph 底板）/ sequenceDiagram / gantt（含 milestone）/ classDiagram

**数学公式**

直接写 LaTeX，自动转 Typst。frac / sqrt / sum / int / lim / matrix / cases / 希腊字母 / vec / hat 等 100+ 命令。

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

---

代码开源：https://github.com/mxtdsh196-lab/ai_pdf
Bug 和需求欢迎提 issue。
```

---

## 资源文件

```
dist/ai_pdf.js
大小：388512 字节
sha256：0cd4aeb97f919d87daf27906a6321d08fa3c4c40bbc1f5571defa5a62745c721
```

## 提交步骤（网页端）

1. 打开 Operit 市场发布页
2. 类型选 **Script / 沙盒包**
3. 填 title、description（上面那段）、categoryId `business_productivity`
4. 上传 `dist/ai_pdf.js`
5. 关联仓库填 `https://github.com/mxtdsh196-lab/ai_pdf`
6. 提交审核

> ⚠️ 上传前先在本地跑一次 `pdf_selfcheck`，确认三件依赖都在，否则新用户第一次会直接失败。