# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Session Startup Checks (MANDATORY)

On **every session start**, before doing anything else, verify the following:

1. **statusLine is loaded globally** — The statusLine is configured in `~/.claude/settings.json` (global, not per-project) pointing to `~/.claude/statusline.sh`. Confirm the `statusLine` field exists at the top level of global settings — if it's missing, the status line will silently not render. Expected schema:
   ```json
   "statusLine": {
     "type": "command",
     "command": "/Users/seraph/.claude/statusline.sh"
   }
   ```
   If missing, notify the user and offer to add it. This is a global preference — applies to all projects, not just this one.

## Project Overview

CC-AvatarGenerator converts user-uploaded photos into minimalist line-art avatars using LLM APIs (MiniMax image-01 by default). The MVP is a single-purpose web app: upload a photo, get a 512px line-art preview. The sole validation goal is "will users pay for this?"

## Tech Stack

- **Backend**: FastAPI (Python 3.11+), async
- **Frontend**: Single-file HTML + Tailwind CSS CDN + vanilla JS — zero build tools, responsive by default for future H5 reuse
- **AI**: Multi-model registry — MiniMax image-01 (default), GPT-Image-2 (PackyAPI / OpenAI 官方), Gemini 3.1 Flash (PackyAPI), with `ACTIVE_MODEL` env var to switch
- **No auth, no database, no CDN** in MVP — pure stateless request/response

## Project Structure (current)

```
app.py                   # FastAPI entry point: /models, /generate, / (index.html)
config.py                # Model registry (MODELS dict) + ACTIVE_MODEL + SHOW_MODEL_SELECT
.env.example             # env var 文档
static/index.html        # Single-file frontend
services/
  generator.py           # 高层编排：preprocess → provider → quality_gate，request_id 串联日志
  preprocessor.py        # 预处理：resize + pad-to-square
  quality_checker.py     # 质量门（MVP 占位：PIL decode 校验）
  providers/             # 协议层：一个 provider = 一种 wire 协议
    base.py              # ImageProvider ABC + ImageRequest/ImageResult
    openai_compat.py     # PackyAPI / OpenAI 官方 / Requesty（OpenAI Images API）
    chat_completions.py  # OpenAI/Requesty 多模态（chat completions）
    openrouter.py        # OpenRouter（含 ToS 兜底）
    minimax.py           # MiniMax image-01 / image-01-live（subject_reference 协议）
prompts/                 # prompt 模板
test/                    # 测试脚本（与生产同源：make_provider().img2img()）
utils/logger.py          # 按天截断 logger（get_logger(name, show_app_name)）
docs/
  architecture.md        # 架构设计文档（核心读这一份）
  design-decisions.md    # 关键设计决策
  mvp-plan.md            # MVP 范围 + 长期战略
```

## Core Request Flow

```
Upload photo → Preprocess (resize + pad-to-square) → Load prompt from cfg.prompt_file
  → Call model API (per ACTIVE_MODEL) → Quality gate (PIL decode 校验, MVP 占位)
  → Return result image
```

## Key Design Decisions (see docs/design-decisions.md)

1. **Reference-image-anchored style alignment** — reference images in `prompts/references/` are the style spec, not prose descriptions. All prompt tuning is measured against "how close to the reference."
2. **Four-layer output stability defense** — input normalization → prompt engineering (low temp, fixed seed) → quality gating with retries → monitoring (post-MVP).
3. **Model registry + strategy pattern** — `config.py` 持有 `MODELS` 字典，protocol vs platform 二维解耦。详见 `docs/architecture.md`。
4. **Web-first, H5-ready** — no framework; responsive HTML/CSS that ports directly to mobile WebView when needed.
5. **功能开关 (SHOW_MODEL_SELECT)** — `config.py:161` 的 env var。设为 `false` 时前端隐藏模型选择区，统一用 `ACTIVE_MODEL`，业务流程不出现任何模型信息。详见 `docs/architecture.md#9`。

## Configuration (env vars)

| Var | Default | 说明 |
|---|---|---|
| `ACTIVE_MODEL` | `image-01` | 默认模型（注册表 key） |
| `SHOW_MODEL_SELECT` | `true` | 是否显示前端模型选择区 |
| `MINIMAX_API_KEY` | - | MiniMax image-01 必需 |
| `PACKYAPI_TOKEN` | - | PackyAPI 平台必需 |
| `PACKYAPI_TOKEN_SORA` | - | PackyAPI GPT-Image-2 专用 |
| `OPENAI_API_KEY` | - | OpenAI 官方 GPT-Image-2 |
| `OPENROUTER_API_KEY` | - | OpenRouter 兜底链 |

## MVP Boundary

| In scope | Out of scope |
|---|---|
| Photo upload → line-art generation | Auth / login |
| 1 style (minimalist line art) | Multi-style selection |
| 512px preview + download | HD download, multi-resolution |
| 模型选择（`SHOW_MODEL_SELECT=true`）或多模型自动 fallback | Payment (simulate only) |
| | History, content moderation, CDN |

## Long-term Strategy (see docs/tech-comparison.md)

Phase 1 (MVP): LLM API only — validate demand fast, zero infra cost.
Phase 2: API + post-processing — generate style variants, train LoRAs from the best.
Phase 3: Self-built pipeline (ComfyUI + ControlNet + LoRA) when volume crosses ~500-1000 images/day and marginal API cost exceeds GPU cost.
