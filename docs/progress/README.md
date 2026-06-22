# 项目阶段进度

本目录记录每个开发阶段 session 结束时的总结。每份文档对应一次主要 commit。

## 索引

| Phase | 时间 | commit | 主题 | 状态 |
|---|---|---|---|---|
| [Phase 1](phase-1-mvp-summary.md) | 2026-06-16 | `7987f00` | MVP 初始化 - 线条头像生成器 | ✅ 已完成 |
| [Phase 2](phase-2-packyapi-summary.md) | 2026-06-17 | `26f4c43` | PackyAPI 多模型图生图调试 | ✅ 已完成 |
| [Phase 3](phase-3-refactor-summary.md) | 2026-06-17 | `74ca3ea` | Provider 抽象层重构 | ✅ 已完成 |
| [Phase 4](phase-4-ui-logs-summary.md) | 2026-06-17 | `8f3a5f1` | 模型选择 UI + 日志增强 | ✅ 已完成 |
| [Phase 5](phase-5-deploy-summary.md) | 2026-06-22 | (未 commit) | 首次公网部署 (`avatar.godp.me`) | ✅ 已完成 |

## 部署相关文档

- [../deploy-guide.md](../deploy-guide.md) — 部署运维指南(覆盖运维速查 / 问题排查 / 重建指南)

## 写作约定

每份 progress doc 包含：

- **目标** — 这个 phase 要达成什么
- **已完成** — 交付清单
- **关键决策与理由** — 非显然的选择
- **踩过的坑** — 现象 / 根因 / 修复
- **未完成 / 留给下一阶段** — 显式记录"故意没做"的项
- **下个 session 接手时** — 新 session 启动该读什么
- **关联** — 涉及 commit / PR / 相关 docs
- **统计** — 代码行数 / 文件数 / 时间
- **反思** — 写给未来自己的心得

## 关联文档

- [../claude-code/session-management.md](../claude-code/session-management.md) — Session 管理方法论（为什么要写这些 doc）
- [../architecture.md](../architecture.md) — 当前架构主说明书
- [../mvp-plan.md](../mvp-plan.md) — MVP 目标 / 范围
- [../../CLAUDE.md](../../CLAUDE.md) — 项目根 CLAUDE.md
