# telegramify-markdown Agent Guide

## Quick Rules

- 基于 pyromark（Rust pulldown-cmark 绑定）的事件流状态机，修改转换逻辑前理解 EventWalker 架构
- 输出为 plain text + `list[MessageEntity]`，所有 offset/length 以 UTF-16 code units 计算
- 核心仅依赖 pyromark，mermaid 渲染（Pillow + aiohttp）是可选依赖
- 测试用 unittest，运行 `pdm run test`
- 中文注释优先

## What telegramify-markdown Does

将原始 Markdown（包括 LLM 输出、GitHub README 等）转换为 Telegram plain text + MessageEntity 数组。不再输出 MarkdownV2 字符串，彻底绕过转义问题。支持 LaTeX→Unicode 转换、Mermaid 图表渲染、expandable blockquote 等。

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.10+ |
| 核心依赖 | pyromark >=0.7.0（Rust pulldown-cmark 绑定） |
| 包管理 | PDM |
| 构建后端 | pdm-backend |
| 测试 | unittest |
| 可选依赖 | Pillow, aiohttp（Mermaid 渲染） |
| 测试依赖 | pyTelegramBotAPI, python-dotenv（Telegram 集成测试） |

## 开发环境

本项目使用 **PDM** 管理依赖和虚拟环境。所有开发操作（安装、测试、构建）必须通过 `pdm` 命令执行，不要直接使用 `pip install -e .` 或 `python -m unittest`。

PDM 会自动管理 `.venv` 虚拟环境和 `src/` 布局下的包路径。

## Common Commands

```bash
pdm install                  # 安装依赖（创建 .venv 并安装项目）
pdm install -G mermaid       # 安装含 mermaid 支持
pdm install -G tests         # 安装测试依赖
pdm run test                 # 运行测试（必须用此命令，确保包路径正确）
pdm build                    # 构建包
```

## Architecture

```
输入 Markdown
    │
    ├─ 预处理: ||spoiler|| → <tg-spoiler>
    ├─ 预处理: LaTeX 转换 (latex_escape/)
    │
    ▼
pyromark.events(text, options)  → 事件流
    │
    ▼
EventWalker 状态机 (converter.py)
    ├─ 维护 text_buffer + utf16_offset
    ├─ entity_stack: Start → push, End → pop 并生成 MessageEntity
    ├─ 识别 segments: text / code_block / mermaid
    │
    ▼
convert() → (str, list[MessageEntity])         # 同步 API
telegramify() → list[Text | File | Photo]      # 异步，含拆分/文件提取/mermaid
```

## Project Map

```
src/telegramify_markdown/
  __init__.py          # 公共 API: convert(), telegramify()
  converter.py         # 核心: pyromark 事件 → (text, entities)，EventWalker 状态机
  entity.py            # MessageEntity dataclass, utf16_len(), split_entities()
  pipeline.py          # 异步管道: 拆分、代码块提取、mermaid 渲染
  config.py            # 用户配置: Symbol, RenderConfig (singleton)
  content.py           # 输出类型: Text, File, Photo, ContentType, ContentTrace
  code_file.py         # 代码块→文件名映射 (语言→扩展名)
  word_count.py        # UTF-16 字数统计
  mermaid.py           # Mermaid 图表渲染（可选，需 aiohttp + Pillow）
  latex_escape/        # LaTeX 公式 → Unicode 转换
  logger.py            # 日志

tests/
  test_entity.py       # MessageEntity, utf16_len, split_entities 测试
  test_converter.py    # convert() 转换器测试
  test_pipeline.py     # telegramify pipeline 测试
  test_server.py       # Telegram Bot API 集成测试（需 TELEGRAM_BOT_TOKEN）
  test_word_count.py   # 字数统计测试
  exp1.md, exp2.md     # 测试用 Markdown 样本

playground/            # 实验/调试用发送脚本
feature-test/          # 特性测试脚本
```

## Coding Standards

- 遵循 PEP 8
- 公共 API 需要 docstring
- 所有 entity offset/length 必须以 UTF-16 code units 计算（emoji 占 2 个单位）
- converter.py 中的事件处理方法命名遵循 `_on_start_xxx` / `_on_end_xxx` 模式

## Testing

```bash
pdm run test
# 或
python -m unittest discover -s ./tests -p test_*.py
```

测试样本在 `tests/exp1.md` 和 `tests/exp2.md`，修改转换逻辑后务必验证输出。

集成测试需要设置 `TELEGRAM_BOT_TOKEN` 环境变量，未设置时自动跳过。
