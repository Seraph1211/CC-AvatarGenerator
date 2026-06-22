# Claude Code 实用效率技巧

*Last updated: 2026-06-19*

> 把 Claude Code 用到"高级工程师级"的高阶实战技巧。
> 不覆盖基础用法（`/init`、`claude` 启动等），只讲能显著提升效率的工作流。
> 信息源：[Best practices](https://code.claude.com/docs/en/best-practices.md) · [Extend Claude Code](https://code.claude.com/docs/en/features-overview.md) · [CLI reference](https://code.claude.com/docs/en/cli-reference.md) · [Interactive mode](https://code.claude.com/docs/en/interactive-mode.md)

---

## 核心心法：Context 是最重要的资源

几乎所有技巧本质上都是"控制 context 占用的策略"。

**ROI 最高的三件事**：

1. **修短 CLAUDE.md 到 200 行以内** — 一次投入，长久受益
2. **任务间习惯 `/clear`** — 防止性能雪崩
3. **读大量文件的任务用 subagent** — 主对话 context 不被污染

---

## 1. CLAUDE.md 最佳实践

### 核心规则

每行都要通过"删掉它，Claude 会出错吗？"的测试。如果不会，删掉。

### 应该写

- Claude 猜不到的 Bash 命令（如特有的 `make` target）
- 与默认行为不同的代码风格（如"用 ES modules，不用 CommonJS"）
- 仓库礼仪（分支命名、PR 模板、commit 前 typecheck）
- 该项目特有的架构决策
- 环境变量、必需的 dev quirk
- 反复踩过的"gotcha"

### 不该写

- Claude 看代码就能猜出来的内容
- 标准语言约定（Claude 已经知道）
- 经常变动的信息（用 `@docs/` import，不要硬编码）
- 长篇教程、文件级描述

### 组织技巧

- 用 `@path/to/file` 语法 import 子文档，避免 CLAUDE.md 臃肿
- 多层级 CLAUDE.md（用户级 `~/.claude/CLAUDE.md` + 项目级 + 子目录级），子目录级按需加载
- 项目根用 `CLAUDE.md`（提交到 git）+ `CLAUDE.local.md`（个人笔记，gitignore）
- 用 `.claude/rules/` 替代过长的 CLAUDE.md，配合 `paths` frontmatter 做按路径加载

### 反例

把 API 文档、教程、完整架构说明全堆进 CLAUDE.md。Claude 会"读到但忽略"——加 emphasis 词（`IMPORTANT`、`YOU MUST`）也只能提高注意力，不是银弹。

---

## 2. 上下文管理：用 `/clear` 而不是忍受膨胀

### 关键洞察

Claude 表现下降的最大原因是 context 充满历史失败尝试。`/clear` 一次干净的会话 + 更好的初始 prompt，几乎总是胜过 20 轮纠错的会话。

### 关键技巧

- **无关任务之间用 `/clear`** — "kitchen sink session"是头号杀手
- **同一问题纠错超过 2 次 → `/clear` 重写 prompt** — 把"刚才试过 X、Y、Z 都不行"总结进新 prompt
- **自动 compaction 触发时，关键指令可能丢失** — 把它们写进 CLAUDE.md，不依赖对话历史
- **`/compact <focus>`** 比自动 compaction 更可控：`/compact Focus on the API changes`
- **`Esc` + `Esc` → "Summarize from here / up to here"** — 局部压缩，比全量更精准
- **`/btw` 问临时问题** — 答案在 overlay 里，不会进 context；"那个配置文件叫什么来着？"用 `/btw` 问
- **`/context`** 看占用大头是什么

### 反例

让一个 session 从"修登录 bug"撑到"加 OAuth"再到"重构数据库"，context 满了 Claude 把最早的需求都忘了。

---

## 3. Prompt 写法：参照"问高级工程师"的方式

### 黄金法则

把 Claude 当成不知道项目上下文、但能力很强的高级工程师。给目标、给约束、给示例。

### 四要素对比

| 策略 | ❌ 低效 | ✅ 高效 |
|---|---|---|
| 限定范围 | "给 foo.py 加测试" | "给 foo.py 加测试，覆盖用户登出的边界条件，不要用 mocks" |
| 指向来源 | "为什么 X API 那么怪？" | "翻 X 的 git 历史，梳理 API 演进" |
| 引用现有模式 | "加日历组件" | "看首页现有组件的模式（X.php 是好例子），按这个模式实现可分页选年月的日历，只用代码库已有的库" |
| 描述症状 | "修登录 bug" | "登录后 session 超时会失败。查 src/auth/，特别是 token 刷新。先写一个能复现的失败测试，再修" |

### 富文本输入技巧

- **`@文件名`** — 自动读取文件，比描述位置快
- **`Ctrl+V` 粘贴图片** — UI bug、报错截图、设计稿直接贴
- **拖放图片** — 直接当输入
- **`!`** 前缀走 shell mode — 快速执行命令同时保留在 context
- **Pipe 数据**：`cat error.log | claude -p "分析"` — CI/批处理场景

### 反例

"帮我看看代码"。把"代码"换成具体文件、症状、期望。

---

## 4. Plan Mode：4 阶段工作流

### 何时用

**能一句话讲清楚改动的，就别 plan**。

### 应该 plan 的场景

- 多文件改动
- 不确定实现路径
- 不熟悉被改动的代码

### 4 阶段工作流

1. **Explore** — 进 plan mode，读代码回答问题，不修改
2. **Plan** — 让 Claude 写详细实现计划
3. **Implement** — 退出 plan mode 实施，对照 plan 验证
4. **Commit** — 让 Claude 写好 commit message 开 PR

### Plan 编辑

plan mode 下按 `Ctrl+G` 在 `$EDITOR` 里直接编辑计划，再让 Claude 继续。

### 反例

所有改动都进 plan mode 反而拖慢 — 重命名、加 log、修 typo 直接让 Claude 干。

---

## 5. 子代理（Subagent）模式：Context 隔离 = 长期 session 的命脉

### 核心价值

subagent 在独立 context window 跑，只把摘要返回主对话。

### 何时拆 subagent

- **研究型任务** — "用 subagent 调研我们的 auth 系统怎么处理 token 刷新"
- **代码 review** — "用 subagent 检查这个 diff 的边界条件"
- **验证** — 实施完后让独立 subagent 验证（避免"自己批改自己作业"）
- **多文件查找** — 找 X 是怎么实现的，让 subagent 读 50 个文件后只回报关键发现

### 内置 Explore agent

Claude Code 自带一个 "Explore" agent 专门做调研任务，**不带 CLAUDE.md 和 git status**，context 更轻。规划任务用 "Plan" agent。

### 进阶：隔离 worktree 并行

```bash
# 终端 1：开发新功能
claude --worktree feature-auth

# 终端 2：并行修 bug
claude --worktree bugfix-123
```

两个 worktree 各自独立分支，互不冲突。配 `--tmux` 可在 iTerm2 panes 里看。

### 反例

让主对话里"调研 X 的实现"读 80 个文件，主对话 context 直接爆。换 subagent 读，回报 1 段总结。

---

## 6. Skills vs Commands vs Hooks vs Rules：四件套各司其职

| 触发器 | 解决方案 |
|---|---|
| Claude 两次违反同一约定 | 加 CLAUDE.md |
| 反复手打同一段开头 prompt | 存为 user-invocable skill |
| 反复粘贴同一 playbook/多步流程 | 做成 skill |
| 反复从浏览器 tab 复制 Claude 看不到的数据 | 接 MCP server |
| Claude 读一堆文件找 symbol 定义 | 装 code intelligence plugin |
| 副作用任务输出爆炸主对话 | 用 subagent |
| 必须每次自动发生的副作用 | 写 hook |

### 关键区分

- **CLAUDE.md** = "永远做 X" 的规则，每次 session 自动加载
- **Skill** = on-demand 知识/工作流，可 `/<name>` 手动触发或描述触发
- **Hook** = 生命周期事件触发的确定性脚本（`PreToolUse`、`PostToolUse`、`SessionStart`、`Stop`），CLAUDE.md 是请求，hook 是强制
- **MCP** = 接外部服务（Slack、Figma、数据库）
- **Rules（`.claude/rules/`）** = 路径作用域的规则（`paths` frontmatter），只在打开匹配文件时加载

### Context cost 排序（从高到低）

CLAUDE.md（每次都加载完整内容）→ MCP（tool 名加载，schema 延迟）→ Skills（描述每次加载，完整内容按需）→ Subagents（完全隔离）→ Hooks（零成本，除非返回输出）

### 反例

- 用 CLAUDE.md 写只在某类任务用到的 API 文档（应该 skill，按需加载）
- 用 CLAUDE.md 说"永远不要编辑 .env"（应该 hook 强制）
- 临时策略放在 CLAUDE.md 而不是 skill

---

## 7. 工具调用优化：让 Claude 走最短路径

### 给 Claude 的捷径

- **`@file`**：Claude 在回复前自动读文件，省一轮
- **`@dir`**：列目录结构，比"找 X 在哪"快
- **`@server:resource`**：MCP 资源直接引用（`@github:repos/owner/repo/issues`）
- **`Ctrl+O`**：开 transcript viewer，看完整 tool call 链（默认折叠"MCP 3 次调用"这种摘要）
- **`/context`**：查 context 占用的元凶（往往是某个大文件或 MCP tool schema）

### 反例

- 用 `cat`/`head`/`tail` 让 Claude 自己读文件 → 直接用 Read 工具，会自动控制 token
- 让 Claude 描述文件路径再读 → 用 `@`

---

## 8. CLI flag & 快捷键

### 最有用的 flag

| 场景 | Flag |
|---|---|
| 接管 web session 到本地 | `claude --teleport` |
| 启动到后台跑长任务，立刻回终端 | `claude --bg "investigate flaky test"` |
| 恢复最近 session | `claude --continue` / `-c` |
| 选特定 session 恢复 | `claude --resume <name\|id>` / `-r` |
| fork session 不动原 session | `--fork-session` |
| 指定模型 | `claude --model claude-sonnet-4-6` |
| 直接进 plan mode | `claude --permission-mode plan` |
| 非交互（CI/脚本） | `claude -p "..." --output-format json` |
| 加 working dir | `claude --add-dir ../apps ../lib` |
| 加载额外 MCP | `claude --mcp-config ./mcp.json` |
| 加载 plugin | `claude --plugin-dir ./my-plugin` |
| 启动无任何自定义（排查配置） | `claude --bare -p "..."` |
| 启动 + 立即后台跑 shell 命令 | `claude --bg --exec 'pytest -x'` |
| 限制工具集（不可信输入场景） | `claude --tools "Bash,Edit,Read"` |
| 限制可执行命令（批处理） | `claude --allowedTools "Bash(git commit *)"` |
| Resume 从 PR 创建的 session | `claude --from-pr 123` |
| 流式 JSON（CI 集成） | `claude -p "..." --output-format stream-json --verbose` |
| 跳过权限提示 | `claude --permission-mode bypassPermissions` |

### 关键快捷键

| 快捷键 | 作用 |
|---|---|
| `Esc` | 中断 Claude 改方向（保留已完成的工作） |
| `Esc` + `Esc` | 空输入时开 rewind 菜单；非空输入时清空并保存到 history |
| `Shift+Tab` | 循环 permission modes（default → acceptEdits → plan → auto） |
| `Ctrl+C` | 中断或清空输入（二次退出） |
| `Ctrl+G` / `Ctrl+X Ctrl+E` | 在外部编辑器里编辑 prompt（长 prompt 必备） |
| `Ctrl+O` | 切 transcript viewer（看完整 tool call） |
| `Ctrl+L` | 强制重绘屏幕 |
| `Ctrl+B` | 后台运行当前 bash 命令（tmux 用户按两次） |
| `Ctrl+R` | 反向搜索历史命令 |
| `Ctrl+T` | 切 task list 显示 |
| `Option+P` / `Alt+P` | 切模型 |
| `Option+T` / `Alt+T` | 切 extended thinking |
| `\` + `Enter` | 多行输入（任何终端都支持） |
| `Tab` | 接受提示的下一条 prompt suggestion |
| `Space` | Voice dictation（按住录音） |

### 反例

用 `cat > file` 让 Claude 写文件（应用 Write 工具，自动 backup/checkpoint）。

---

## 9. MCP 集成：先查 `/mcp` 再决定

### 接 MCP 的信号

发现自己在从另一个工具（如 issue tracker、监控 dashboard）往 chat 复制数据。接上后 Claude 直接读写该系统。

### 作用域优先级

`local > project > user`

### 高效配置

- 把高频白名单加到 `settings.json` 的 `permissions.allow`（如 `WebFetch(domain:www.packyapi.com)`）
- **`/mcp`** 查看各 server 占用的 token 成本 — MCP schema 默认 defer（tool search 模式），但用得多还是会涨
- 用 `claude --mcp-config ./mcp.json --strict-mcp-config` 在 CI 里精确控制加载哪些 server
- 不活跃的 server 用 `/mcp` 断开连接，节省 context

### 反例

所有 MCP server 全年开着；某些 server 一次加载几百个 tool 的 schema。

---

## 10. 多会话管理：并行 + 不串味

### 会话命名

`claude -n "oauth-migration"` 或 `/rename`。每个工作流一个名字，便于 `--resume` 找。

### resume vs fork

- `--continue`/`--resume` 恢复同一 session ID，继续累积
- `--fork-session` 复制历史到新 session ID，原 session 不动（"试两条路线，对比"）

### 并行模式选择

| 需求 | 方案 |
|---|---|
| 编辑不冲突，并行实验 | `--worktree <name>` |
| 多 session 统一监控 | Desktop app / `claude agents` |
| 不在本地跑 | `claude --remote` web session |
| 多 session 互相通信 | Agent teams（实验性） |

### Writer/Reviewer 模式（官方推荐）

- 会话 A：实现
- 会话 B（新 context，无偏差）：review
- 会话 A：消化 review feedback

两个 session 的 context 完全独立 — B 不会因为看过 A 的实现过程而偏袒。

### 反例

一个 session 做完所有事，最后让它 review 自己写的代码（自我偏倚无法消除）。

---

## 11. 特定任务的高效模式

### 调试

```
build 报错：[完整堆栈]
猜位置是 src/auth/session.ts 的 token 刷新。
写一个能复现的失败测试，然后修。
跑构建确认成功。修根因，不要抑制报错。
```

关键是给"能跑的 check"（test/build/screenshot）。

### Code review

- 用 `/code-review` skill — 内置 fresh subagent 视角
- 给具体 review 标准："对照 PLAN.md 检查每条 requirement 是否实现；列出的边界 case 有测试；没改范围外的东西。报告 gap，不要 style preferences"

### Refactor

- 小步走："先改 utils.js 的第 1-20 行，跑测试；再改 21-40 行"
- 每次后跑测试，避免一次大改后定位问题难

### 测试

- "找 NotificationsService.swift 里没被覆盖的函数" → 自动找
- 强调"match 现有测试风格"，避免 Claude 自己造框架

### 研究

- **deep research**：用 `/deep-research` skill（fan-out 搜索 + 引用核对 + 综述）
- **`/btw`** 问临时问题，不进 context
- **`@server:resource`** 拉 MCP 数据

### 批量迁移（fan-out）

```bash
# 1. 让 Claude 列文件清单
claude -p "list all 2000 Python files needing migration" > files.txt

# 2. 写脚本循环
for f in $(cat files.txt); do
  claude -p "Migrate $f from React to Vue. Return OK or FAIL." \
    --allowedTools "Edit,Bash(git commit *)"
done

# 3. 先跑前 3 个，根据失败调整 prompt，再批量
```

### 研究加验证（对抗性）

让一个 Claude 写代码，另一个 Claude 在新 context 里挑刺。"一个 subagent 写实现，另一个 subagent 验证"是去除偏倚的标准模式。

---

## 12. 反模式清单

| 反模式 | 表现 | 修复 |
|---|---|---|
| **Kitchen sink session** | 一个 session 内多个无关任务，context 全是噪音 | 任务间 `/clear` |
| **反复纠错同一问题** | 2 次纠错后 context 被失败尝试污染 | `/clear` + 重写 prompt |
| **过度膨胀的 CLAUDE.md** | Claude 忽略一半规则 | 严苛剪枝；要么删，要么转 hook |
| **Trust-then-verify gap** | 实现看着对，边界 case 全漏 | 必给 test/script/screenshot 验证 |
| **Infinite exploration** | "调研 X" 不限定范围，Claude 读 100 个文件 | scope 收紧；或 subagent |

---

## 如果只选 3 个技巧立刻上手

1. **修短 CLAUDE.md 到 200 行内**（每行通过删除测试）
2. **任务间习惯 `/clear`**（无关任务别串在一起）
3. **复杂调研用 Explore subagent**（避免主对话 context 污染）

---

## 参考文档

- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices.md)
- [Extend Claude Code (skills/hooks/subagents/MCP 对比)](https://code.claude.com/docs/en/features-overview.md)
- [CLI reference (全部 flag)](https://code.claude.com/docs/en/cli-reference.md)
- [Interactive mode (全部快捷键)](https://code.claude.com/docs/en/interactive-mode.md)
- [Common workflows (按任务的 prompt 模板)](https://code.claude.com/docs/en/common-workflows.md)
- [How Claude Code works (agentic loop + context window)](https://code.claude.com/docs/en/how-claude-code-works.md)
