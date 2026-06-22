# CC Connect 文档目录

本目录收录所有关于 **cc-connect**(把个人微信桥接到本机 Claude Code 的中间件)的使用、配置、调试文档。

cc-connect 项目主页:<https://github.com/chenhg5/cc-connect>

## 文档列表

| 文档 | 内容 |
|---|---|
| [usage.md](usage.md) | **基础使用手册**:命令清单、`send` 媒体投递、`cron` / `timer` 调度、`relay` bot 间协作、`NO_REPLY` 静默回复、微信格式约定、故障排查 |
| [multi-project-routing.md](multi-project-routing.md) | **多项目路由方案**:多个项目时如何用微信群做 chat_id 分流,实操 config.toml 模板,FAQ |

## 阅读顺序建议

1. 第一次接触 cc-connect → 先读 [usage.md](usage.md)
2. 手头有 ≥ 2 个项目要远程协作 → 读 [multi-project-routing.md](multi-project-routing.md)
3. 排查具体问题 → 翻 [usage.md §8 故障排查](usage.md#8-故障排查)

## 文档维护约定

- 用中文为主(项目本身 CLAUDE.md 强制要求)
- 所有示例命令必须是真实可执行的(基于 cc-connect 1.3.4)
- 涉及到的配置路径以 `~/.cc-connect/` 为准
- 与项目其他文档(`../architecture.md`、`../session-management.md` 等)保持交叉引用一致