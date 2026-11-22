# ai_pdf

**给 AI 用的中文 PDF 排版包。只写 Markdown，排版正确性由转换器保证。** 引擎 Typst，3 页文档 0.6–1 秒。

> 核心设计原则：**不让模型写 Typst**。Typst 的括号与模式对 LLM 太脆弱，输入锁死在 Markdown，转换器承担全部语法正确性。

---

## 亮点

- **23 个工具**：生成、体检、拆分、合并、加密、水印、字体检查、批量生成
- **7 个版式 + 6 套配色**，含 16:9 **PPT 幻灯片**（8 种预设版式）
- **15 类内容组件**：KPI 卡、进度条、环形进度、时间线、对比栏、定义表……
- **文字环绕真实图片**（meander）、**中英日竖排**（basho）
- **4 种 Mermaid 图全自研**：flowchart / sequenceDiagram / gantt / classDiagram，零外部依赖
- **`pdf_lint` 程序化版式体检**：不靠人眼找溢出、空白页、低 dpi 图
- **20+ 类输入校验**：写错了工具自己开口，不靠调用方下次小心

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
