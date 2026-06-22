# CC Connect 使用手册

*Last updated: 2026-06-20*

> 本项目通过 **cc-connect** 桥接到个人微信对话。Claude 在终端输出的文本/媒体默认会自动投递到微信会话;但**定时任务、bot 间协作、静默回复、媒体附件投递**等场景需要显式调用 `cc-connect` 命令。
> 配套:[../claude-code/session-management.md](../claude-code/session-management.md) · [../claude-code/claude-code-features.md](../claude-code/claude-code-features.md)

---

## 1. 核心工作流

```
┌─────────────────┐
│  微信 (WeChat)  │  ← 用户在手机微信上发出消息
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  cc-connect 桥接 │  ← 守护进程,常驻后台,把消息转给 Claude Code
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Claude Code   │  ← 在终端 / IDE 里工作
└────────┬────────┘
         │
         ▼  (你的普通文本回复自动送达微信)
┌─────────────────┐
│   微信 (WeChat)  │
└─────────────────┘
```

**关键事实**:

- **普通文本回复** — 你在 Claude Code 输出的普通文本会自动投递给当前会话的微信用户,**不用**调用任何命令。
- **媒体、调度、bot 协作** — 这些**必须**显式调用 `cc-connect send | cron | timer | relay`。
- 环境变量 `CC_PROJECT` 和 `CC_SESSION_KEY` 在 cc-connect 启动的 session 里已经注入,大多数子命令不需要再传 `--project` / `--session-key`。

---

## 2. 发送回复

### 2.1 普通文本 — 默认自动投递

直接回复就好,不需要任何命令:

```
用户:看一下 git log
Claude:📜 最近的提交是...  ← 这一行文本会自动出现在微信里
```

唯一例外:如果你在回复里写了 `NO_REPLY`(单独一行、case-insensitive),cc-connect 会把这一行剥掉再投递;如果**整条回复只有 `NO_REPLY`** 或剥掉后为空,**什么都不投递**(完全静默)。

```python
# 适合:定时任务触发了,但发现没什么值得报告的
# 适合:群聊里这条消息明显是发给别人的,自己闭嘴
```

### 2.2 发送媒体附件 — `cc-connect send`

当生成了一张图、一个 PDF、一段语音,**必须**用 `cc-connect send` 才能渲染成微信可识别的消息类型,否则只会被当作普通文本+文件链接。

| 媒体类型 | flag | 渲染效果 |
|---|---|---|
| 图片 | `--image /path.png` | 微信图片气泡 |
| 文件 (任意) | `--file /path.pdf` | 文件下载 |
| 音频 | `--audio /path.mp3` | 原生语音气泡(Feishu/Telegram),其他平台降级为文件 |
| 视频 | `--video /path.mp4` | 原生视频播放器 |
| 文字转语音 | `--tts "text"` | 合成并发送语音气泡 |

**典型用法**:

```bash
# 单图
cc-connect send --image /tmp/chart.png

# 图片 + 文字说明
cc-connect send --image /tmp/avatar.png --message "这是生成的头像"

# 多图 / 多文件(可重复)
cc-connect send --image /tmp/a.png --image /tmp/b.png --file /tmp/report.pdf

# 用户要求"念给我听"时
cc-connect send --tts "今天天气晴,适合出门"

# 长文本 / 含特殊字符 — 用 --stdin
cc-connect send --stdin <<'EOF'
多行报告
含 $variable 与 "quoted" 内容
EOF
```

**易踩的坑**:

- `--audio` / `--video` 是平台敏感的:Feishu 会渲染成原生语音/视频气泡,其他平台(比如 QQ)cc-connect 自动降级为文件附件。**用户明确要听/看**时才能用 `--audio` / `--video`;否则降级为 `--file` 更安全。
- `--tts` 成功后,**只回复 `NO_REPLY`**,不要把同一句话再用普通文本复述一遍(用户已经听到语音了)。
- `--image` / `--file` 可以和 `--message` 同用,但**不要重复同一句话**到普通文本里。

---

## 3. 定时任务 — cron vs timer

这是最容易选错的:`cc-connect cron` 和 `cc-connect timer` 是**两套完全不同的命令**,选错会产生非常糟糕的体验。

| 命令 | 用途 | 何时删除 | 用什么查 |
|---|---|---|---|
| `cc-connect cron` | **周期性**任务(每天/每周/每小时) | 永久存活,直到你主动 `del` | `cc-connect cron list` |
| `cc-connect timer` | **一次性延迟**(3 分钟后/明天 9 点) | 触发后自动归档 | `cc-connect timer list` |

### 3.1 cron:周期性任务

```bash
# 每天早上 6 点收集 GitHub trending
cc-connect cron add --cron "0 6 * * *" --prompt "收集今日 GitHub trending 仓库并汇总" --desc "每日 GitHub Trending"

# 每周一上午 9 点生成周报
cc-connect cron add --cron "0 9 * * 1" --prompt "生成上周项目状态周报" --desc "周报"

# 每 2 分钟跑一次 ipconfig(新 session 每次)
cc-connect cron add --cron "*/2 * * *" --exec "ipconfig" --session-mode new-per-run --desc "ipconfig 检查"
```

**重要:避免整点 `:00` 和 `:30`**:所有用户说"早上 9 点"都被解释成 `0 9 * * *`,所有用户说"每小时一次"都被解释成 `0 * * * *`,会导致**全网同一秒打到 API**。在用户没指定精确时间时,挑一个非整点分钟:

```bash
# ❌ 不好:全网统一
cc-connect cron add --cron "0 9 * * *" ...

# ✅ 好:避开尖峰
cc-connect cron add --cron "57 8 * * *" ...   # 8:57
cc-connect cron add --cron "7 * * * *" ...     # 每小时 :07
```

只在用户明确说"9 点整""半点"时才用 `0` / `30`。

### 3.2 timer:一次性延迟

```bash
# 2 小时后检查 PR
cc-connect timer add --delay 2h --prompt "检查 PR #123 状态" --desc "PR 检查"

# 30 分钟后看磁盘
cc-connect timer add --delay 30m --exec "df -h" --desc "磁盘检查"

# 明天早上 9 点提醒(本地时区)
cc-connect timer add --at "2026-06-21T09:00" --prompt "早会提醒" --desc "早会"
```

**判断题**:用户说"每 / 经常 / 每周" → cron;说"X 分钟后 / 明天 X 点 / 提醒我一次" → timer。

### 3.3 查看与管理

```bash
# 列出
cc-connect cron list
cc-connect timer list

# 详情(改之前先看)
cc-connect cron info <job-id>
cc-connect timer info <timer-id>

# 立刻触发一次(测试用)
cc-connect cron exec <job-id>

# 改一个字段(不要 del + add)
cc-connect cron edit <job-id> cron_expr "0 10 * * *"
cc-connect cron edit <job-id> enabled false    # 暂停,不删
cc-connect cron edit <job-id> prompt "新 prompt"

# 删除
cc-connect cron del <job-id>
cc-connect timer del <timer-id>
```

**改一条 cron 的时候,优先 `edit` 而不是 `del` + `add`**:job-id 会变,用户追踪起来更乱。

---

## 4. Bot 间协作 — `cc-connect relay`

跨 bot 让两个 Claude 会话对话(例如让 Gemini 帮你查一个文档,然后把结果带到当前会话):

```bash
# 当前 bot 主动发消息给 gemini bot
cc-connect relay send --to gemini "请帮我查 Python 3.13 的新特性"

# 完整场景:问 gemini 一个问题,把答复拿到手
# (relay send 是同步等待的,会拿到对方 bot 的回复)
```

**坑**:

- `--to` 后面必须是 `/bind` 命令输出的**精确项目名**,不能改、不能猜。例如 `gemini`,不是 `gemini-bot`。
- `CC_PROJECT` / `CC_SESSION_KEY` 环境变量已经注入,不用再传 `--from` / `--session-key`。
- 群聊里 relay 的对话是公开的(所有人都看得到),别用它传敏感信息。

---

## 5. 静默回复 — `NO_REPLY`

规则很微妙,**写错位置会让用户多收到一条空消息**:

| 你写的 | 用户收到 |
|---|---|
| 整条回复只有 `NO_REPLY` | 什么都不收到(完全静默) |
| `NO_REPLY` 在末尾(前文有内容) | 收到前文(末尾的 NO_REPLY 被剥掉) |
| `NO_REPLY` 不在独立一行 | 不会被识别,会被当成普通文本发出 |

**适用场景**:

- 定时任务触发,巡检了一遍发现没异常,不该打扰用户
- 群聊里这条消息明显是给别人的,你已经分析过没你啥事
- `cc-connect send --tts` 之后 — 用户已经听到语音,你闭嘴就行

---

## 6. 微信端的格式约定

文本回复最终会被投递到**手机微信**,小屏阅读。规则:

- **避免 markdown 表格** — 微信渲染会把表格压扁、移动端基本不可读。用短段落、列表、有序列表替代。
- **代码块用 ` ` 而不是 \`\`\`** — 微信支持 inline code 但不渲染 fenced code block,大段代码用截图或文件附件。
- **emoji 开头** — 全局约定(见 `~/.claude/CLAUDE.md`):每条回复第一个字符必须是 emoji,且要选**和当前消息语义匹配**的(✅ 完成、❌ 失败、🔍 查询、📊 数据、🛠 操作、💬 对话)。
- **超长回复要分段** — 一次发一大坨用户根本读不完。如果要发的内容 > 几屏,用 `cc-connect send --file report.md` 发附件,正文给一个一句话摘要。
- **别提"plan"** — 在 AskUserQuestion / ExitPlanMode 之外不要问"这个方案 OK 吗?",那是 plan mode 专属句式。

---

## 7. 常用模式速查

| 用户说的话 | 该用的命令 |
|---|---|
| "把生成的图发给我" / "看图" | `cc-connect send --image <path>` |
| "念给我听" / "用语音回我" | `cc-connect send --tts "..."`,然后只回 `NO_REPLY` |
| "下载这个 PDF" | `cc-connect send --file <path>` |
| "每天早上 6 点..." | `cc-connect cron add --cron "57 5 * * *" ...` |
| "X 分钟后提醒我..." | `cc-connect timer add --delay Xm ...` |
| "让 gemini 帮我查 X" | `cc-connect relay send --to gemini "查 X"` |
| "看看定时任务" | `cc-connect cron list` / `cc-connect timer list` |
| "停掉那个任务" | `cc-connect cron info <id>` → `cron del` 或 `edit enabled false` |
| "这条消息不该回复我" | 整条回复只写 `NO_REPLY` |

---

## 8. 故障排查

| 症状 | 排查 |
|---|---|
| 文本回复没出现在微信 | 看 `~/.cc-connect/logs/cc-connect.log`;确认 `cc-connect daemon status` 是 running |
| `cc-connect send --image` 发出去是文件链接不是图片 | 确认路径是绝对路径且文件存在;某些平台(老版微信)对大图(>10MB)自动降级 |
| cron 触发后没收到任何消息 | cron 任务 prompt 里写"如果没异常就回 `NO_REPLY`";否则 agent 会试图回复但不知道发给谁 |
| relay 报错 `unknown project` | `--to` 的项目名和 `/bind` 输出不一致,精确复制 |
| timer 没到点就归档了 | 检查 `--at` 时间是否已过;时区解释为本地时区 |
| `NO_REPLY` 没被识别 | 必须独立成行;不能夹在段落中间 |
| cron 任务跑挂了 | `cc-connect cron info <id>` 看 timeout-mins,默认 30 分钟,大任务可能需要调大 |

---

## 9. 相关资源

- 项目主页:<https://github.com/chenhg5/cc-connect>
- 安装文档:<https://github.com/chenhg5/cc-connect/blob/main/INSTALL.md>
- 本项目其他文档:
  - [../architecture.md](../architecture.md) — 架构设计
  - [../claude-code/session-management.md](../claude-code/session-management.md) — Session 管理心法
  - [../claude-code/claude-code-features.md](../claude-code/claude-code-features.md) — Claude Code 功能盘点