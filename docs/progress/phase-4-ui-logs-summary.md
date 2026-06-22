# Phase 4: 模型选择 UI + 日志增强 - 进度总结

*完成日期: 2026-06-17*
*对应 commit: `8f3a5f1` feat: 模型选择后台开关 + UI 改进 + 日志增强*

---

## 目标

在 Phase 3 抽象层就绪后，把"模型选择"从"开发者选项"变成"产品可用的功能开关"——既能给开发者 / 内部测试人员调试用,又不影响普通用户的业务流程。同时补齐可观测性。

---

## 已完成

- ✅ `SHOW_MODEL_SELECT` 环境变量（`config.py`）
  - `true`（默认）：前端显示模型选择区
  - `false`：前端完全隐藏模型选择区，业务流程不出现任何模型信息
- ✅ 前端 UI 改进
  - 模型选择区视觉化（按平台分组 `<optgroup>`）
  - 上传 / 加载 / 成功 / 失败 4 态优化
  - 移动端响应式优化
- ✅ 日志增强
  - `request_id` 串联（每个请求一个 ID，端到端可追）
  - 全链路 trace：platform / protocol / provider / model / latency
  - `utils/logger.py` 升级（按天截断 + request_id 注入）
- ✅ `docs/architecture.md` 新增（292 行，重构后第一份"主说明书"）
- ✅ 全部 services/providers/* 文件重写（基于新 logger + ModelConfig 适配）
- ✅ `test_packyapi.py` 大幅瘦身（重构后 200 行模板应用）

---

## 关键决策与理由

| # | 决策 | 理由 |
|---|---|---|
| 1 | **`SHOW_MODEL_SELECT` 作为单一开关** | 业务流不应暴露"模型"这种技术概念；但开发 / 测试要能切 → 后台开关一刀切 |
| 2 | **请求级 `request_id` 串联** | 跨 service / provider / API 的请求能用同一 ID 查到完整链路 |
| 3 | **日志全在 `utils/logger.py` 集中管理** | 不让 `print` 散落；统一格式 + 统一截断策略 |
| 4 | **`architecture.md` 写在重构之后** | 先有代码再有文档；文档反映"当前实际状态"而非"理想状态" |
| 5 | **不动 model 列表本身** | 本阶段不动 `MODELS` 注册表，专注"选择 UI + 日志"；model 增删留给独立 phase |

---

## 踩过的坑

- **坑 1：UI 改完发现模型信息在 DOM 里仍可见**
  - 现象：`SHOW_MODEL_SELECT=false` 时，前端虽然隐藏了下拉框，但 hover / 右键能看到
  - 根因：仅 CSS 隐藏，DOM 节点还在
  - 修复：后端 `/models` 端点在开关关闭时直接返回 `[]`，前端拿不到 model 列表

- **坑 2：request_id 跨 async 边界丢失**
  - 现象：sub-task 里的日志没有 request_id
  - 根因：Python async contextvars 没正确传递
  - 修复：用 `contextvars.ContextVar` + log filter 注入

- **坑 3：logger 改造导致已有测试输出格式变化**
  - 现象：测试断言失败（依赖旧的 log 格式）
  - 根因：logger 改造是 breaking change
  - 修复：测试改用结构化字段查询（不依赖字符串格式）

- **坑 4：mobile 端下拉框体验差**
  - 现象：手机端 `<select>` 在某些浏览器弹出后定位错位
  - 根因：Tailwind CDN 的 form 样式覆盖
  - 修复：自定义 `<optgroup>` 样式 + viewport media query

---

## 未完成 / 留给下一阶段

- [ ] Quality checker 升级（CV 边缘密度 / 色彩分布）
- [ ] 监控埋点（post-MVP）
- [ ] `_dbg` 路径迁移（Phase 3 遗留）
- [ ] 模型效果对比 dashboard
- [ ] 用户反馈通道（"这个结果好不好"按钮）
- [ ] HD 付费下载（mvp-plan 阶段八的下一步）

---

## 下个 session 接手时

1. 先读 [architecture.md](../architecture.md) — 这是当前项目的"主说明书"，反映本阶段后的状态
2. 重点看 [docs/CLAUDE.md](../../CLAUDE.md) 的"功能开关 (`SHOW_MODEL_SELECT`)"段
3. 重点看 `config.py:SHOW_MODEL_SELECT` 的环境变量定义
4. 重点看 `utils/logger.py` 的 request_id 注入机制
5. 注意：`SHOW_MODEL_SELECT=false` 时 `/models` 返回 `[]`，前端不会显示任何模型选项

---

## 业务 vs 开发的"模型选择"双模

```
┌────────────────────────────────────────────┐
│  普通用户（业务流）                          │
│  SHOW_MODEL_SELECT=false                   │
│  → /models 返回 []                         │
│  → 前端无下拉框                             │
│  → 业务流程不出现任何模型信息                │
│  → 统一用 ACTIVE_MODEL                      │
└────────────────────────────────────────────┘

┌────────────────────────────────────────────┐
│  开发者 / 内部测试                          │
│  SHOW_MODEL_SELECT=true（默认）             │
│  → /models 返回全部 5 个 model              │
│  → 前端有下拉框，可切换                      │
│  → URL 参数 ?model=gpt-image-2 也支持       │
└────────────────────────────────────────────┘
```

详见 [architecture.md#9](../architecture.md) 的"功能开关"段。

---

## 关联

- 涉及 commit: `8f3a5f1`
- 涉及 PR: （本阶段无 PR）
- 相关 docs:
  - [architecture.md](../architecture.md) — 重构后第一份主说明书（本阶段新增）
  - [CLAUDE.md](../../CLAUDE.md) — 项目根 CLAUDE.md（本阶段补充 SHOW_MODEL_SELECT 段）
  - [phase-3-refactor-summary.md](phase-3-refactor-summary.md) — 上一阶段
  - [../claude-code/session-management.md](../claude-code/session-management.md) — 本工作流的方法论
- 涉及文件:
  - `config.py` (+289 行改动，SHOW_MODEL_SELECT 开关)
  - `static/index.html` (+126 行 UI 改进)
  - `app.py` (+74 行 /models 端点逻辑)
  - `utils/logger.py` (+75 行 request_id)
  - `services/generator.py` (+176 行日志接入)
  - `services/providers/*` (5 个文件全部重写以适配新 logger)
  - `docs/architecture.md` (新增，292 行)
  - `CLAUDE.md` (+56 行)

---

## 统计

- 代码: 1276 行新增 / 879 行删除（净 +397）
- 文件: 18 个变更
- 新增文档: `docs/architecture.md` (292 行)
- 时间: 半天

---

## 反思（本阶段写给未来的自己）

**业务流和技术流的隔离不是靠 UI 隐藏,靠后端数据流**。`SHOW_MODEL_SELECT=false` 时直接 `/models` 返回 `[]` 而不是前端 CSS 隐藏 — 这是关键区分。

**`request_id` 是后期排查的命脉**。在日志全量接入之后再补这个成本很高,趁架构刚改完就接入是最佳时机。

**CLAUDE.md 跟随代码同步更新**。功能开关 (SHOW_MODEL_SELECT) 这种"非显然决策"如果不写进 CLAUDE.md,下个 session 的 Claude 会花 30 分钟重新发现。
