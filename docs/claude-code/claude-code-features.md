# Claude Code 新版功能速查

*Last updated: 2026-06-19*

> Claude Code（CLI / IDE / Web / Desktop）的功能总览。截止 2026-06-19。
> 不是项目代码文档，而是给团队成员查 Claude Code 自身能力的参考表。
> 信息源：[Claude Code Overview](https://code.claude.com/docs/en/overview.md) · [Changelog](https://code.claude.com/docs/en/changelog.md) · [Claude Fable 5](https://www.anthropic.com/news/claude-fable-5-mythos-5)

---

## 1. 多端运行环境

Claude Code 不再局限于终端，已覆盖所有主流界面：

| 环境 | 说明 |
|---|---|
| **Terminal CLI** | macOS / Linux / WSL / Windows，支持后台自动升级 |
| **VS Code / Cursor 扩展** | 内联 diff、@-mention、plan review、会话历史 |
| **JetBrains 插件** | IntelliJ / PyCharm / WebStorm 等，2026.1+ 修复了闪烁问题 |
| **Desktop App** | 独立桌面，可视化 diff、并行多会话、计划任务 |
| **Web 版** | [claude.ai/code](https://claude.ai/code)，浏览器直接跑，无需本地环境 |
| **iOS App** | 手机端继续工作 |
| **Claude Code in Chrome** 扩展 | 调试实时 Web 应用 |
| **Remote Control / Teleport** | 跨设备接力会话（`claude --teleport`） |
| **Slack / Dispatch / Channels** | 从聊天工具路由任务 |

---

## 2. 子代理（Subagents）能力跃升

### 关键版本变更

| 版本 | 变更 |
|---|---|
| 2.1.172 | **嵌套子代理** — 子代理可再派生子代理（最多 5 层） |
| 2.1.181 | 强制子代理深度限制，权限语法 `Agent(model:opus)` 拦截特定模型 |
| 2.1.139 | 后端子代理 (ctrl+b) 不会从零重启；`CLAUDE_PROJECT_DIR` 传给 stdio MCP |
| 2.1.178 | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` 时每个会话隐式拥有一个团队 |

### 核心机制

- **新增 `Agent` 工具的 `name` 参数** — 直接派发队友 agent，无需先 `TeamCreate`
- **独立 context window** — 主对话不被搜索结果/日志淹没
- **自定义 system prompt、工具访问、权限**
- **可路由到更便宜的模型**（如 Haiku）以控成本
- **用户级子代理** 可在多个项目复用

---

## 3. Skills（技能）系统

**重大变化**：`.claude/commands/foo.md` 与 `.claude/skills/foo/SKILL.md` 等价，统一为 Skills 体系，遵循 [Agent Skills](https://agentskills.io) 开放标准，跨工具兼容。

### 核心机制

- 写一个 `SKILL.md`，**按需加载**（不像 CLAUDE.md 总是占 context）
- 支持**目录结构**：可附带 supporting files
- 支持 **frontmatter** 控制调用方式
- Claude 可自动按相关性加载，也可手动 `/skill-name` 触发

### 主要更新

- 2.1.157：`.claude/skills` 自动加载，无需 marketplace；`claude plugin init <name>` 脚手架
- 2.1.152：skills 和 slash commands 可以在 frontmatter 中设置 `disallowed-tools`
- 2.1.178：嵌套的 `.claude/skills` 目录也会加载
- 2.1.152：`/reload-skills` 命令 — 不重启即可重新扫描技能目录
- 2.1.169：`CLAUDE_CODE_DISABLE_BUNDLED_SKILLS` 可禁用内置技能
- 2.1.163：`$` 转义语法支持字面量 `$`

### 捆绑的内置技能（部分）

`/debug`、`/code-review`、`/simplify`、`/batch`、`/fewer-permission-prompts`、`/loop`、`/claude-api`、`/run`、`/init`、`/statusline`、`/review`、`/security-review`、`/insights`、`/verify`、`/design-sync`、`/update-config`、`/keybindings-help`、`/deep-research`

---

## 4. Hooks（钩子）系统增强

### 新增事件与字段

- **`MessageDisplay` 钩子**（2.1.152）— 转换或隐藏助手消息文本
- **`terminalSequence` 字段**（2.1.141）— 桌面通知、窗口标题、响铃
- **`args: string[]` 字段**（2.1.139）— 直接 spawn 命令，不经 shell
- **`hookSpecificOutput.sessionTitle`**（2.1.152）— SessionStart 时设置
- **`hookSpecificOutput.additionalContext`**（2.1.163）— Stop/SubagentStop 时注入额外 context

### 新选项

- `continueOnBlock` for `PostToolUse`（2.1.139）— 即使拦截也继续
- SessionStart 钩子的 `reloadSkills: true`（2.1.152）
- 自托管 runner 的 `post-session` 生命周期钩子（2.1.169）

---

## 5. MCP（Model Context Protocol）集成

| 维度 | 更新 |
|---|---|
| OAuth | 2.1.181 改善 OAuth 浏览器页面与 Claude Code 视觉一致；无头/SDK 模式下不再暴露 auth-stub 工具 |
| 安全 | 2.1.181 `claude mcp list/get` 不再打印 secrets；credential headers/URL secrets 自动脱敏 |
| 配置 | 2.1.154 stdio server 收到 `CLAUDE_CODE_SESSION_ID` 和 `CLAUDECODE=1`；plugin 配置支持 `${CLAUDE_PROJECT_DIR}` 引用 |
| 修复 | 2.1.183 headless 模式下要求认证的 MCP server 不再暴露 stub 工具；2.1.144 修复 SVG 等不支持的 MIME 类型中断会话 |

---

## 6. 计划模式（Plan Mode）升级

- 2.1.172：`opusplan` 模型在 plan mode 下默认 1M context 窗口
- `opusplan[1m]` workaround 可在 plan mode 切到 Opus
- 2.1.147：`/simplify` 重命名为 `/code-review`，支持 `--comment` 在 GitHub PR 内联评论

---

## 7. 新模型支持

### Claude Fable 5（2.1.170）
"Mythos-class" 模型，能力超过此前任何公开发布的模型。

### Claude Opus 4.8（2.1.154）
- 默认 effort = high
- `/effort xhigh` 处理最难任务
- **Fast mode**：2x 速率、2.5x 速度，价格仅为原来的几分之一

### Auto Mode（2.1.158）
- 支持 Opus 4.7/4.8，可在 Bedrock / Vertex / Foundry 启用
- 子代理派发前由分类器评估（2.1.178）
- 不再需要 opt-in 同意（2.1.152）
- 改善数据外泄检测（2.1.154）

---

## 8. 安全与防破坏

### 破坏性命令拦截（2.1.183）
默认拦截以下命令，除非 Claude 在本会话中显式发起：

- `git reset --hard`、`git checkout -- .`、`git clean -fd`、`git stash drop`
- `git commit --amend`（除非该 commit 是本会话 agent 创建的）
- `terraform destroy` / `pulumi destroy` / `cdk destroy`

### Sandboxing

- 2.1.181 `sandbox.allowAppleEvents` 沙箱配置
- 2.1.169 `CLAUDE_CODE_SAFE_MODE` 启动时禁用所有自定义

---

## 9. 计划任务 & 后台会话

### Routines（Anthropic 托管）
- 即使电脑关闭也运行
- 可由 API 调用或 GitHub 事件触发
- 在 Web / Desktop / CLI `/schedule` 创建

### Desktop Scheduled Tasks
- 本地机器执行，可直接访问本地文件与工具

### 后台会话
- `claude --bg --exec '<command>'` 后台跑 shell 命令
- `claude agents` 统一管理
- `Ctrl+T` 钉住后台会话
- 自动后台更新 Claude Code 版本（2.1.163）
- 保留 `--mcp-config`、`--settings`、`--add-dir`、`--plugin-dir`、`--strict-mcp-config`

---

## 10. 新增命令

| 命令 | 功能 |
|---|---|
| `/cd` | 移动会话到新工作目录（2.1.169） |
| `/goal` | 设置完成条件，Claude 持续工作直到达成（2.1.139） |
| `/scroll-speed` | 调鼠标滚轮速度（2.1.139） |
| `/reload-skills` | 不重启重新扫描 skills |
| `/code-review` | 重命名自 `/simplify`，支持 `--comment` |
| `/usage-credits` | 重命名自 `/extra-usage`（2.1.144） |
| `/plugin list` | 列出已安装插件（2.1.163） |
| `/config key=value` | 直接改设置，如 `/config thinking=false`（2.1.181） |
| `/workflows` | 查看动态 workflow 运行情况（2.1.154） |

---

## 11. 新设置项

| 设置 | 说明 |
|---|---|
| `attribution.sessionUrl` | 从 commit/PR 中省略 claude.ai session 链接 |
| `enforceAvailableModels` | 托管设置，模型白名单 |
| `fallbackModel` | 最多 3 个 fallback 模型 |
| `requiredMinimumVersion` / `requiredMaximumVersion` | 版本钉死 |
| `wheelScrollAccelerationEnabled` | 鼠标滚轮加速 |
| `footerLinksRegexes` | 正则匹配的页脚徽章 |
| `worktree.bgIsolation: "none"` | 后台会话直接编辑工作副本 |
| `sandbox.allowAppleEvents` | 沙箱 Apple Events 许可 |

---

## 12. 可观测性（OTel）

- `OTEL_RESOURCE_ATTRIBUTES` 值作为 metric datapoints 的 label（2.1.161）
- `agent_id` 和 `parent_agent_id` 加到 `claude_code.tool` OTEL span（2.1.145）
- `tool_decision` 事件在 `OTEL_LOG_TOOL_DETAILS=1` 时包含 `tool_parameters`（2.1.157）
- `app.entrypoint` OTEL metric attribute（2.1.152）

---

## 13. CI/CD 与团队协作

- **GitHub Actions / GitLab CI/CD**：自动化 PR review、issue triage
- **GitHub Code Review**：每个 PR 自动 review
- **Slack 集成**：在 Slack @Claude 直接转 PR
- **Dispatch**：手机消息任务自动建 Desktop 会话

---

## 14. 性能与稳定性改进

- **Prompt caching** 修复：自定义 `ANTHROPIC_BASE_URL` 和 Foundry 上不再失效（2.1.181）
- **Write/Edit** 修复：网络驱动器上不再产生 0 字节文件（2.1.181）
- **Compaction** 修复：尊重 `--fallback-model`（2.1.178）
- 后台会话不再吞前台会话的版本更新

---

## 信息来源

- [Claude Code Overview](https://code.claude.com/docs/en/overview.md)
- [Claude Code Changelog](https://code.claude.com/docs/en/changelog.md)
- [Subagents 文档](https://code.claude.com/docs/en/sub-agents.md)
- [Skills 文档](https://code.claude.com/docs/en/skills.md)
- [Claude Fable 5 发布说明](https://www.anthropic.com/news/claude-fable-5-mythos-5)
- [Agent Skills 开放标准](https://agentskills.io)
