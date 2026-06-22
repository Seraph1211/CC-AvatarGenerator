# Phase 1: MVP 上线 - 进度总结

*完成日期: 2026-06-16*
*对应 commit: `7987f00` feat: 初始化 MVP - 线条头像生成器*

---

## 目标

把"上传照片 → 线条头像"这个核心 flow 从 0 跑到 1，验证"用户愿不愿意为这个付钱"。

详见 [mvp-plan.md](../mvp-plan.md) 的"验证目标"段。

---

## 已完成

- ✅ FastAPI 后端骨架（`app.py` + `config.py` + `services/generator.py`）
- ✅ 单文件前端（`static/index.html`，纯 HTML + Tailwind CDN + 原生 JS）
- ✅ 多模型注册表（`MODELS` 字典）+ `ACTIVE_MODEL` 环境变量
- ✅ 接入 MiniMax image-01 / image-01-live
- ✅ 接入 OpenAI gpt-image-1（Requesty 中转）
- ✅ prompts 适配 MiniMax 图生图（`line_art_minimax.txt`，≤1500 字符精简版）
- ✅ 7 张 style spec 参考图（`references/image1-7.jpg`）
- ✅ 4 份项目级 docs（mvp-plan / design-decisions / tech-comparison / prompt-tuning-guide）
- ✅ 输入图片 inline resize 到 1024×1024 RGBA PNG
- ✅ 失败重试一次（try / retry×1）
- ✅ `/generate` + `/models` 路由

---

## 关键决策与理由

| # | 决策 | 理由 |
|---|---|---|
| 1 | **参考图锚定法**作为风格对齐机制 | 文字描述无法保证"极简线条风"理解一致；参考图即 style spec，prompt 调优以"是否接近参考图"为唯一标准 |
| 2 | **MVP 阶段只做 2 层稳定性防御**（输入标准化 + prompt 锁定） | 第 3 层质量门禁留 post-MVP；用"重试一次"覆盖大部分场景，避免早期 CV 投入 |
| 3 | **模型注册表 + 简单 if/elif 分发** | 两个 provider 不需要策略模式抽象；第三个模型进来再重构 |
| 4 | **Web First, H5 Ready** | 纯 HTML + Tailwind CDN + 原生 JS，零构建，响应式天然适配后续 H5 |
| 5 | **gpt-image-1 为主力模型**（非 Gemini 2.5 Flash） | Gemini 2.5 Flash 不支持图像生成；gpt-image-1 的 `images.edit()` 原生支持 img2img |
| 6 | **大模型 API 方案**（非自建管线） | MVP 阶段快速验证需求；量起来后再评估切换时机 |

详见 [design-decisions.md](../design-decisions.md)。

---

## 踩过的坑

- **坑 1：JPEG 直接传给 gpt-image-1 images.edit() 会报错**
  - 现象：API 返回 400 "Image must be PNG with alpha channel"
  - 根因：`images.edit()` 接口要求 RGBA PNG 输入
  - 修复：输入处理 inline 加一行 `convert("RGBA")`（Pillow，约 3 行）

- **坑 2：MiniMax prompt 字符限制**
  - 现象：长 prompt（>1500 字符）被截断
  - 根因：MiniMax image-01 的 prompt 字段有长度上限
  - 修复：拆出 `line_art_minimax.txt` 精简版

- **坑 3：参考图选不好导致后续调优方向跑偏**
  - 现象：早期 prompt 调优反复碰壁
  - 根因：风格基准不一致
  - 修复：先选 3-5 张参考图存为 `references/`，以"接近参考图"为唯一评判标准

---

## 未完成 / 留给 Phase 2+

- [ ] PackyAPI 多模型接入（gpt-image-2 / Gemini Flash）
- [ ] 测试脚本结构化（`test/` 目录）
- [ ] 日志工具（`utils/logger.py`）
- [ ] 模型选择 UI（当前靠 URL 参数 + 隐藏入口）
- [ ] 兜底链 / 多平台切换
- [ ] Provider 抽象层（第三模型进来后必做）
- [ ] Quality check（边缘密度/色彩分布 CV 分析）
- [ ] 监控埋点（post-MVP）

---

## 下个 session 接手时

1. 先看 [mvp-plan.md](../mvp-plan.md) "技术选型"段，确认基础假设
2. 重读 [design-decisions.md](../design-decisions.md) 决策 3（多模型切换），准备扩展 `MODELS` 注册表
3. 注意 `config.py:ACTIVE_MODEL` 默认值（应为 `image-01`）
4. 看 `services/generator.py:photo_to_line_art` 的统一接口签名，新模型从这里接入

---

## 关联

- 涉及 commit: `7987f00`
- 涉及 PR: （MVP 阶段无 PR）
- 相关 docs:
  - [mvp-plan.md](../mvp-plan.md) — MVP 目标 / 范围
  - [design-decisions.md](../design-decisions.md) — 6 个关键决策
  - [tech-comparison.md](../tech-comparison.md) — 长期战略
  - [prompt-tuning-guide.md](../prompt-tuning-guide.md) — prompt 调优心得
- 涉及文件:
  - `app.py` (75 行)
  - `config.py` (64 行)
  - `services/generator.py` (271 行)
  - `static/index.html` (301 行)
  - `prompts/line_art.txt` + `prompts/line_art_minimax.txt`
  - `references/image1-7.jpg` (7 张 style spec)

---

## 统计

- 代码: 1297 行新增
- 文件: 21 个新增
- 时间: 1 天（脚手架 + 全流程跑通）
