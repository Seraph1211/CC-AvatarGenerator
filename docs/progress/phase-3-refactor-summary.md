# Phase 3: Provider 抽象层重构 - 进度总结

*完成日期: 2026-06-17*
*对应 commit: `74ca3ea` refactor: 引入 provider 抽象层 + 多平台多协议架构*

---

## 目标

把 Phase 2 累积的 `if/elif` 链替换为"协议 + 平台"二维解耦的 provider 抽象层，让加新平台/协议/模型的成本降到最低。

详见 [architecture.md](../architecture.md)。

---

## 已完成

- ✅ 新建 `services/providers/` 子包（5 个文件 + `__init__.py`）
  - `base.py` — `ImageProvider` ABC + `ImageRequest`/`ImageResult` 统一类型
  - `openai_compat.py` — OpenAI Images API 协议（合并原 `_generate_openai_image_edit` + `_generate_packyapi`）
  - `chat_completions.py` — OpenAI Chat Completions 多模态协议
  - `minimax.py` — MiniMax `image_generation` 自定义协议
  - `openrouter.py` — OpenRouter 特殊头 + modalities + ToS 403 兜底
  - `__init__.py` — `PROVIDERS` 注册表 + `make_provider` 工厂
- ✅ 抽离 `services/preprocessor.py`（从 generator.py 拆出，支持 `max_dim` 参数）
- ✅ 抽离 `services/quality_checker.py`（MVP 阶段仅 monochrome 检测）
- ✅ `config.py` 重写：`ModelConfig` dataclass
  - 字段：`display_name` / `provider` / `model_id` / `base_url` / `api_key_env` / `platform` / `*_defaults`
  - 新增 `gemini-3.1-flash-image-preview` (PackyAPI)
  - OpenAI 官方 / OpenRouter entry 留作模板（注释启用方式）
- ✅ `services/generator.py` 简化：`generate_avatar` 从 ~140 行 if/elif 变单条调用链
- ✅ 前端动态 `<optgroup>` 按平台分组渲染（`/models` 返回 `platform + provider` 字段）
- ✅ `test_packyapi.py` 瘦身 580→200 行，复用 production provider 栈，零平行实现
- ✅ 测试 + 生产 100% 共享 API 调用代码

---

## 关键决策与理由

| # | 决策 | 理由 |
|---|---|---|
| 1 | **"协议"和"平台"二维解耦** | 同一协议下加新平台（如 OpenAI 官方）= config.py 加 entry，0 代码改动；新协议 = providers/ 加新文件 + 注册一行 |
| 2 | **`ImageProvider` ABC + `ImageRequest`/`ImageResult` 统一类型** | 所有 provider 对外接口一致；调用方不感知协议差异 |
| 3 | **OpenRouter 兜底机制** | OpenAI 官方 API 偶发 403（ToS 触发），自动 fallback 到 OpenRouter；兜底要可观测（日志区分主调 vs 兜底） |
| 4 | **测试用 `preprocess_max_dim=512` + `quality=low` 走临时 ModelConfig** | 减少测试运行时间 + 输出体积；不污染生产配置 |
| 5 | **`PROVIDERS` 注册表（dict）而非 `@register` decorator** | 配置集中可见，加 provider 时一眼能看到全貌；decorator 太"魔法" |

---

## 踩过的坑

- **坑 1：抽抽象时一度想"一步到位"覆盖所有 edge case**
  - 现象：第一版 base.py 写了 200+ 行，包含 6 个 hook
  - 根因：完美主义倾向
  - 修复：先收 3 个最常用的 hook（before_request / on_response / on_error），其他用 override 渐进补

- **坑 2：测试用例原先平行实现 provider**
  - 现象：`test_packyapi.py` 第一版自己又写了一遍 HTTP 调用
  - 根因：测试与生产代码分离太久
  - 修复：测试改用 `make_provider().img2img()`，零平行实现

- **坑 3：`_dbg` 调试日志路径在重构时丢了**
  - 现象：开发机特定路径被硬编码到 generator.py
  - 根因：未充分解耦
  - 修复：留 TODO，机器路径迁移单独处理；不阻塞抽象层上线

---

## 未完成 / 留给 Phase 4+

- [ ] 模型选择 UI 改造（前端展示当前可用的 5+ 个 model）
- [ ] `SHOW_MODEL_SELECT` 后台开关（业务流不应暴露模型信息）
- [ ] 日志增强（request_id 串联 + 平台/协议/provider/model 全链路 trace）
- [ ] `_dbg` 路径迁移
- [ ] Quality checker 升级（CV 边缘密度 / 色彩分布）
- [ ] 监控埋点（post-MVP）

---

## 下个 session 接手时

1. 先读 [architecture.md](../architecture.md) — 这是抽象层上线后的"主说明书"
2. 重点看 `services/providers/base.py` 的 `ImageProvider` ABC
3. 重点看 `config.py:ModelConfig` 字段定义
4. 重点看 `services/providers/__init__.py:PROVIDERS` 注册表
5. 记住：加新模型 = `MODELS` 加 entry；加新平台 = `MODELS` 加 entry；加新协议 = `providers/` 加新文件

---

## 架构演进图

### Phase 1-2: if/elif 链

```
generate_avatar(image, model_id)
    ↓
if model_id == "gpt-image-1":
    # OpenAI 协议（硬编码）
elif model_id == "image-01":
    # MiniMax 协议（硬编码）
elif model_id == "gpt-image-2-packyapi":
    # OpenAI 协议变体（重复实现）
elif model_id == "gemini-flash":
    # Chat Completions 协议（又一份）
...
```

### Phase 3: provider 抽象

```
generate_avatar(image, model_id)
    ↓
config = MODELS[model_id]    # ModelConfig(provider, model_id, base_url, api_key_env, ...)
provider = make_provider(config.provider)  # PROVIDERS 注册表
result = provider.img2img(ImageRequest(image, prompt, model_id, ...))
    ↓
quality_check(result.image)
    ↓
return image
```

**加新模型成本**: `MODELS` 加 1 entry（约 10 行）
**加新平台成本**: `MODELS` 加 1 entry（约 10 行）
**加新协议成本**: `providers/` 加 1 文件 + `PROVIDERS` 注册 1 行 + `MODELS` 加 entry

---

## 关联

- 涉及 commit: `74ca3ea`
- 涉及 PR: （本阶段无 PR）
- 相关 docs:
  - [architecture.md](../architecture.md) — 重构后的"主说明书"
  - [phase-2-packyapi-summary.md](phase-2-packyapi-summary.md) — 上一阶段（触发本重构的痛点）
  - 上一阶段: [phase-1-mvp-summary.md](phase-1-mvp-summary.md)
  - 后续: [phase-4-ui-logs-summary.md](phase-4-ui-logs-summary.md)
- 涉及文件:
  - `services/providers/` (5 个新文件，~580 行)
  - `services/preprocessor.py` (新)
  - `services/quality_checker.py` (新)
  - `config.py` (重写，+218 行)
  - `services/generator.py` (简化，-996 行)
  - `static/index.html` (+22 行 optgroup)
  - `app.py` (+15 行 /models 端点)
  - `test/packyapi/test_packyapi.py` (瘦身 580→200 行)

---

## 统计

- 代码: 1055 行新增 / 996 行删除（净 +59）
- 文件: 15 个变更 / 5 个新增
- 时间: 半天

---

## 反思（本阶段写给未来的自己）

**抽象的最佳时机是"加第 3 个"时**（3 个 provider if/elif 链已达 ~140 行）。早于这个点抽象是过度设计，晚于这个点是技术债。

测试和生产代码 100% 共享是关键 — 平行实现是最大的隐藏债务。
