# Platform Formatting Rules

## Xiaohongshu

### What Actually Renders

Xiaohongshu's native editor is **not a Markdown renderer**. It's a rich text field with limited formatting.

**Does NOT support**: `##` headers, ` ``` ` code blocks, `|table|`, `---` horizontal rules, `[text](url)` links, inline `` `code` ``, nested lists.

**Does support**: `*bold*` (platform-native), emoji, line breaks, numbered lists (simple), `#hashtag#`.

### Two Output Modes

Choose based on code density:

```text
Post contains code?
├─ 0-1 short snippets → Mode A: Native Text
│   Describe code in prose, use *bold* for identifiers
│   Deliver as: plain text ready to paste into Xiaohongshu editor
│
└─ 2+ code blocks / tables / diagrams → Mode B: Markdown → Image
    Write full Markdown → render via tool → post as image cards
    Deliver as: .md master file + recommendation for which tool to render with
```

### Mode A: Native Text Rules

- Section markers: emoji + `*bold label*` (e.g., `*s02 · Permission Gate*`)
- Code: prose description preferred. If essential, single line in `*bold monospace-ish*`
- Tables: replace with bullet lists or `key: value` pairs
- Separators: double line break, never `---`
- Paragraph: ≤ 3 lines on mobile (about 80-100 chars)
- Bold rhythm: at least one `*bold insight*` per section
- Hashtags: 4-6 at end only, in-body hashtags look spammy

### Mode B: Markdown → Image Pipeline

Write a standard Markdown master file, then feed it into one of these tools to generate styled image cards:

**Recommended tools (2025-2026)**:

| Tool | Platform | Strengths |
| --- | --- | --- |
| **xiaohongshu-text-layout** | Web (跨平台) | 自定义背景、批量导出、markdown 全支持 |
| **文颜** (yuzhi.tech/wenyan) | Web (跨平台) | 多平台一键适配、本地处理、LaTeX |
| **Carbon.sh / Ray.so** | Web (跨平台) | 单段代码截图最适合，语法高亮 |
| **RedBookCards** (pilipala5) | ⚠️ Windows only (.exe) | 12 主题、GUI、语法高亮 |

> macOS 用户优先用 **xiaohongshu-text-layout** 或 **文颜**。RedBookCards 只发布 .exe，macOS 不可用。

**Workflow**:

```text
1. Write post as standard .md file (can use tables, code blocks, headers)
2. Choose a tool based on theme needs
3. Render to images
4. Upload images to Xiaohongshu, add title + hashtags in editor
```

**Theme selection by content type**:

| Content Type | Recommended Theme |
| --- | --- |
| Code-heavy tutorial | `terminal` or `neo-brutalism` |
| Architecture deep-dive | `professional` |
| Beginner-friendly intro | `playful-geometric` |
| Design philosophy | Minimal with large typography |

### Post Anatomy (Both Modes)

```text
Image 1: Title card (hook, big typography)
Image 2-N: Content cards (one concept per card)
Image N+1: Summary/takeaway card
```

Content rhythm: Section marker every 5-8 paragraphs. Reader should never scroll more than 2 screens without a visual anchor.

---
(WeChat and Zhihu sections unchanged)

---

## WeChat Official Account

**Supports**: Rich text editor, images, colored text, some CSS.

**Rules**:
- Code blocks: use WeChat-compatible code highlighter or screenshot
- Font size: 15px body, 12px captions
- Line spacing: 1.75
- Margins: 16px sides
- Images: JPEG under 10MB, GIF under 5MB
- Cover image: 900×383px (2.35:1)

---

## Zhihu

**Supports**: Full Markdown, LaTeX, code highlighting.

**Rules**:
- Can use standard Markdown
- Opening 3 lines are the preview — make them count
- Code blocks: use language annotation for syntax highlighting
- Images: no size limit but compress for load speed
