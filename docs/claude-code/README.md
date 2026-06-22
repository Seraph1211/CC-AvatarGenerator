# Claude Code 文档目录

本目录收录所有关于 **Claude Code**(Anthropic 官方 CLI 编码 agent)的使用、心法、特性盘点文档。

Claude Code 官方文档:<https://code.claude.com/docs/en/overview.md>

## 文档列表

| 文档 | 内容 |
|---|---|
| [claude-code-features.md](claude-code-features.md) | **功能盘点**:`Agent` 工具 / Subagent 体系 / Skills / Hooks / MCP / Worktree / Plans 等所有能力 |
| [claude-code-tips.md](claude-code-tips.md) | **使用技巧**:上下文管理 / `/clear` / `/btw` / `--resume` / 快捷键 / CLI flag / 实战 prompt 模板 |
| [session-management.md](session-management.md) | **Session 管理心法**:长期项目的三种 session 策略、外化记忆、阶段化 session、跨 session 状态保留 |

## 阅读顺序建议

1. 刚装好 Claude Code,先了解能干啥 → 读 [claude-code-features.md](claude-code-features.md)
2. 开始用,但想用得更顺手 → 读 [claude-code-tips.md](claude-code-tips.md)
3. 项目跨度超过一周,想管好 context 和 session → 读 [session-management.md](session-management.md)

## 文档维护约定

- 用中文为主(项目本身 CLAUDE.md 强制要求)
- 所有 flag / 命令必须以 Claude Code 当前版本为准(信息源链接在每篇文档末尾)
- 与项目其他文档(`../architecture.md`、`../cc-connect/`、`../progress/` 等)保持交叉引用一致
- 任何"约定俗成"的最佳实践必须能在官方文档里找到出处