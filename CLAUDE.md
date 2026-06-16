# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

CC-AvatarGenerator converts user-uploaded photos into minimalist line-art avatars using LLM APIs (Gemini 2.5 Flash by default). The MVP is a single-purpose web app: upload a photo, get a 512px line-art preview. The sole validation goal is "will users pay for this?"

## Tech Stack

- **Backend**: FastAPI (Python 3.11+), async
- **Frontend**: Single-file HTML + Tailwind CSS CDN + vanilla JS — zero build tools, responsive by default for future H5 reuse
- **AI**: Gemini 2.5 Flash (default), with a model registry supporting GPT-4o and others via `ACTIVE_MODEL` env var
- **No auth, no database, no CDN** in MVP — pure stateless request/response

## Planned Project Structure

```
app.py                   # FastAPI entry point, routes
config.py                # Model registry (MODELS dict) + global config
static/index.html        # Single-file frontend
services/
  generator.py           # AvatarGenerator — unified interface, per-provider adapters
  preprocessor.py        # Input normalization: resize→1024², face detection, brightness/contrast
  quality_checker.py     # Post-generation checks: blank detection, edge density, color distribution
prompts/
  line_art.toml          # Prompt template
  references/            # Reference images as style spec (anchor for prompt tuning)
requirements.txt
.env.example
```

## Core Request Flow

```
Upload photo → Preprocess (resize + face detect) → Build prompt from template
  → Call model API (per ACTIVE_MODEL) → Quality gate (blank/edge/color checks, retry ≤3×)
  → Return result image
```

## Key Design Decisions (see docs/design-decisions.md)

1. **Reference-image-anchored style alignment** — reference images in `prompts/references/` are the style spec, not prose descriptions. All prompt tuning is measured against "how close to the reference."
2. **Four-layer output stability defense** — input normalization → prompt engineering (low temp, fixed seed) → quality gating with retries → monitoring (post-MVP).
3. **Model registry + strategy pattern** — `config.py` holds a `MODELS` dict keyed by short name. `generator.py` dispatches internally by provider. Switch via `ACTIVE_MODEL` env var or frontend dropdown.
4. **Web-first, H5-ready** — no framework; responsive HTML/CSS that ports directly to mobile WebView when needed.

## MVP Boundary

| In scope | Out of scope |
|---|---|
| Photo upload → line-art generation | Auth / login |
| 1 style (minimalist line art) | Multi-style selection |
| 512px preview + download | HD download, multi-resolution |
| Model switching dropdown | Payment (simulate only) |
| | History, content moderation, CDN |

## Long-term Strategy (see docs/tech-comparison.md)

Phase 1 (MVP): LLM API only — validate demand fast, zero infra cost.
Phase 2: API + post-processing — generate style variants, train LoRAs from the best.
Phase 3: Self-built pipeline (ComfyUI + ControlNet + LoRA) when volume crosses ~500-1000 images/day and marginal API cost exceeds GPU cost.
