# 多项目路由 — 微信 ↔ 多 Claude Code 项目

*Last updated: 2026-06-20*

> 当你**同时维护多个项目**,每个都需要 Claude Code 帮你做活,又希望**不在电脑前时能从微信指挥**,cc-connect 1.3.4 是支持的。但**切换项目的姿势和你想的不一样** —— 不是发指令,而是用**不同的微信聊天(私聊/群)做路由通道**。
> 配套:[usage.md](usage.md) — cc-connect 基础使用手册

---

## 1. 动机与误区澄清

### 1.1 真实需求场景

```
你手头有 N 个项目:
  - CC-AvatarGenerator  (FastAPI)
  - HustleHub
  - 其他 ...

每个项目都需要 Claude Code 在其工作目录下读写、跑测试、调 API。

你希望:
  - 地铁上能用手机微信给 avatar 项目发消息让 agent 干活
  - 回家路上能给 HustleHub 发消息做另一件事
  - 不同项目的会话状态完全隔离(不串)
```

### 1.2 你大概率猜错的三件事

| 你以为的 | 真相 | 出处 |
|---|---|---|
| "微信发 `!hustle` 前缀切项目" | ❌ **没有这种路由规则**。cc-connect 1.3.4 不解析消息前缀 | — |
| "`/bind claudecode` / `/bind gemini` 切项目" | ❌ `/bind` 是**多 Bot Relay**(一个群聊接入多种 bot 类型,如 claudecode + gemini 共存),**不是切项目** | docs/usage.md — Multi-Bot Relay |
| "`/dir /path/to/hustle` 切到 HustleHub" | ❌ `/dir` 只改**当前项目内**的 work_dir,**不改 system_prompt**;在你现在的配置下用,agent 还是会读到 avatar 项目的提示词 | docs/usage.md — "Directory changes apply to the next session in the **current project**" |

### 1.3 真正的机制

cc-connect 通过 **chat_id 路由**:同一条微信 token,可以被多个 `[[projects.platforms]]` 块复用,每块用 `chat_id` 字段过滤到**不同的聊天会话**。来自哪个聊天的消息,就路由到哪个 project 的 agent。

> **原文**(docs/weixin.md):"私聊和群聊都想覆盖时,复制一份 `[[projects.platforms]]` 块即可。把 `chat_id` 留空就响应机器人所在的所有聊天,填具体值只响应那一个群/个人。"

---

## 2. 方案对比

| 方案 | 实施成本 | 切换体验 | 推荐度 | 适用 |
|---|---|---|---|---|
| **V1:多 `[[projects]]` + 微信群分流** ⭐ | 中(改一次 config + 建 N 个群) | 极快(换个群发消息) | ⭐⭐⭐⭐⭐ | 长期多项目 |
| V2:多 `[[projects]]` + 多个微信好友/小号 | 高(需要多账号) | 一般 | ⭐⭐ | 想严格隔离 IM 通道 |
| V3:多 cc-connect 实例 + 多通道 | 高(多 IM 通道) | 慢 | ⭐⭐ | 项目 > 5 个且必须 IM 通道级隔离 |
| V4:`mode = "multi-workspace"` | 中 | 取决于平台 | ⭐(WeChat 个人号不友好) | Slack/Feishu 等有 channel 名概念的 IM |

---

## 3. ⭐ 推荐方案 V1:多 `[[projects]]` + 微信群 chat_id 分流

### 3.1 架构图

```
┌─────────────────────────────────────────────────┐
│ cc-connect daemon (1 个进程,常驻后台)              │
│ 监听同一 ilink 微信 token                          │
└────┬──────────────┬──────────────┬───────────────┘
     │              │              │
     │ 私聊 DM      │ 群"项目A"     │ 群"项目B"   ← 微信侧聊天边界
     ▼              ▼              ▼
┌──────────┐  ┌──────────┐  ┌──────────┐
│ avatar-  │  │  proj-A  │  │  proj-B  │
│generator │  │ claude   │  │ claude   │  ← 各自 spawn 独立 Claude Code
│ (PID X)  │  │ (PID Y)  │  │ (PID Z)  │
└──────────┘  └──────────┘  └──────────┘
   work_dir:    work_dir:    work_dir:
   ~/CC-...     ~/projA      ~/projB
```

### 3.2 config.toml 示例(假设加 HustleHub 项目)

在 `~/.cc-connect/config.toml` 现有 avatar-generator 块后面追加:

```toml
# =============================================================================
# Project: HustleHub (新加)
# =============================================================================
[[projects]]
name = "hustlehub"

# 同一个 admin_from(都是你本人)
admin_from = "o9cq80-eDbOnXO6Dh4wrQlWSEdu8@im.wechat"

# 30 分钟无活动重置会话(可按需调 0 = 不重置)
reset_on_idle_mins = 30

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/Users/seraph/GitHouse/HustleHub"
mode = "bypassPermissions"  # 远程必须 yolo,本机没人答权限弹窗
append_system_prompt = """
You are being controlled remotely via cc-connect from the user's WeChat.
Working directory: /Users/seraph/GitHouse/HustleHub
[这个项目的常用命令、坑、约定写在这里]
"""

[[projects.platforms]]
type = "weixin"

[projects.platforms.options]
# ⭐ 与 avatar-generator 块用同一个 token
token = "b3f076742744@im.bot:060000c9baddb3bf9834de008d09da6163d4d2"
base_url = "https://ilinkai.weixin.qq.com"
allow_from = "*"
account_id = "b3f076742744@im.bot"

# ⭐ 关键:只响应这个 chat_id
# DM 块这里留空("" 或不写),响应所有私聊
chat_id = "HUSTLEHUB_GROUP_ID@chatroom"
```

avatar-generator 现有块里给 `[[projects.platforms]]` 加上 `chat_id = ""`(留空 = 响应所有私聊,默认行为):

```toml
[[projects.platforms]]
type = "weixin"
[projects.platforms.options]
token = "..."
...
chat_id = ""    # ← 新增这一行(原本没有这个 key 也行,但显式留空更清晰)
```

### 3.3 实施步骤

```bash
# 1. 确认 daemon 在跑
cc-connect daemon status

# 2. 在微信里建一个群(命名随意,如 "HustleHub")
#    只把你自己拉进去就行 —— ilink 个人微信的群,只要群里有人即可被识别

# 3. 让 daemon 收到新群的首条消息,捕获 chat_id
#    临时把新项目的 admin_from 设成你的微信 ID(已设),allow_from = "*"
#    然后在新群里发一条"hello"

# 4. 实时看 daemon 日志
cc-connect daemon logs -f -n 100
# 找类似: received message from chat_id=xxxxx@chatroom
# 或者关键字 chat_id、chatroom、@chatroom

# 5. 把捕获到的 chat_id 填进 config.toml 新项目的 [[projects.platforms]] 里

# 6. 重启 daemon 让新配置生效
cc-connect daemon restart

# 7. 在新群里发条消息测试 —— 应该路由到 HustleHub 项目
#    在 DM 发消息测试 —— 应该路由到 avatar-generator
```

### 3.4 验证路由生效

```bash
# 列出所有 session
cc-connect sessions list

# 应该看到 2 个(甚至更多,如果你在多个群都试过):
#   avatar-generator_b2b6bb07   私聊 DM
#   hustlehub_xxxxxxxx          群"项目B"
```

或者在微信里分别从私聊和群里发消息,看 `cc-connect daemon logs -f -n 20` 里日志怎么标 route 到哪个 project。

---

## 4. 关键澄清:三个易混命令的真实用途

### 4.1 `/bind`(Multi-Bot Relay)

```bash
/bind              # 查看当前 chat 已绑定的 bot
/bind claudecode   # 把 claudecode bot 加到这个 chat
/bind gemini       # 把 gemini bot 加到这个 chat(可叠加)
/bind -claudecode  # 移除 claudecode
```

**用途**:让一个群聊里**同时接入多种 bot**(如 claudecode 和 gemini),然后用 `cc-connect relay send --to gemini "..."` 让两个 bot 协作。**和"切换项目"无关**。

### 4.2 `/dir`

```bash
/dir                            # 查看当前 work_dir 和最近历史
/dir /path/to/another           # 改 work_dir(只影响下一个 session,project 内的)
/dir 2                          # 切到历史第 2 个目录
/dir -                          # 切回上一个目录
```

**关键限制**:
- 改动只影响**当前 project 内的下一个 session**
- **不会**改变项目的 `append_system_prompt`、`mode` 等
- 历史是 project-scoped 的

→ **不能**用它"切到另一个项目"。

### 4.3 `/switch <session_id>`

```bash
/switch abc123    # 切到指定 session(同 project 内)
```

只是切到同一个 project 内的另一个历史 session。**不能跨 project**。

---

## 5. 已知限制与坑

### 5.1 ilink token 失效后必须重建所有 binding

**场景**:微信协议偶尔会失效,需要重新扫码(`cc-connect weixin setup` 重出二维码),新 token 会覆盖 `account_id` / `token` 字段。

**后果**:`chat_id` 字段**不变**(因为群本身还在),但 token / account_id 变了。

**应对**:
- 备份 `config.toml`,尤其是所有 `[[projects.platforms]]` 块
- 重新 setup 后,把 token / account_id 字段同步到所有项目块
- `chat_id` 不动

### 5.2 群必须是 ilink 个人微信能加入的群

ilink 是**个人微信通道**,不是企业微信。群成员必须是真人微信账号。

→ 只拉自己一个人也可以(空群不算,必须至少 1 人 + 你自己 = 2 人?实际测一下)。如果你担心打扰别人,建群后只退其他成员留自己。

### 5.3 daemon 重启会丢失 in-memory session

daemon 重启后,**进程内**的活跃 Claude Code session 会死。但 `reset_on_idle_mins` 配置的下一次消息会触发 spawn 新 session。短期体感:重启后发的第一条消息会"等待 spawn",比平时慢几秒。

### 5.4 work_dir 必须存在且可读

`work_dir` 指向的目录必须:
- 存在
- 当前用户可读
- 包含 CLAUDE.md(否则 agent 不知道项目约定)

如果项目还在 git 仓库里,daemon 启动时还会做 git 操作(`skip_git = true` 可跳过)。

### 5.5 跨项目的会话状态完全隔离

不同 project 的 session 文件存在 `~/.cc-connect/sessions/<project>_<id>.json`,互不干扰。但**这意味着**:你在 avatar 项目里的对话上下文,不会自动带到 HustleHub 项目。每个项目的 Claude Code 都是独立的"临时工"。

---

## 6. 一个完整的多项目 config.toml 模板(可直接复用)

```toml
# =============================================================================
# cc-connect 多项目 + 微信群分流 模板
# =============================================================================

language = "en"

[log]
level = "info"

# -----------------------------------------------------------------------------
# Project 1: avatar-generator(默认私聊)
# -----------------------------------------------------------------------------
[[projects]]
name = "avatar-generator"
admin_from = "你的微信_ID@im.wechat"
reset_on_idle_mins = 30

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/Users/seraph/GitHouse/CC-AvatarGenerator"
mode = "bypassPermissions"
append_system_prompt = "...(avatar 项目专属提示)..."

[[projects.platforms]]
type = "weixin"

[projects.platforms.options]
token = "你的_TOKEN"
base_url = "https://ilinkai.weixin.qq.com"
allow_from = "*"
account_id = "你的_ACCOUNT_ID"
chat_id = ""    # ← DM 留空 = 响应所有私聊

# -----------------------------------------------------------------------------
# Project 2: HustleHub(群"HustleHub")
# -----------------------------------------------------------------------------
[[projects]]
name = "hustlehub"
admin_from = "你的微信_ID@im.wechat"
reset_on_idle_mins = 30

[projects.agent]
type = "claudecode"

[projects.agent.options]
work_dir = "/Users/seraph/GitHouse/HustleHub"
mode = "bypassPermissions"
append_system_prompt = "...(HustleHub 项目专属提示)..."

[[projects.platforms]]
type = "weixin"

[projects.platforms.options]
token = "你的_TOKEN"     # ← 与 Project 1 同 token
base_url = "https://ilinkai.weixin.qq.com"
allow_from = "*"
account_id = "你的_ACCOUNT_ID"
chat_id = "HUSTLEHUB_GROUP_ID@chatroom"    # ← 填捕获到的群 ID

# -----------------------------------------------------------------------------
# Project 3: 其他项目(再加就复制 Project 2 块改 work_dir 和 chat_id)
# -----------------------------------------------------------------------------
```

---

## 7. FAQ

### Q1:能不能不用微信群,用 DM 私聊前缀区分?

不能。cc-connect 1.3.4 不解析消息前缀做项目路由。

### Q2:我用其他 IM(Feishu / Telegram / Slack)能更优雅吗?

能。Feishu / Slack 的"频道"有名字,可以配合 `mode = "multi-workspace"`(`channel 名 → base_dir/<channel 名>`)实现全自动映射。WeChat 个人号群没有 channel 名概念,所以推荐 V1 手动 chat_id。

### Q3:加新项目要重启 daemon 吗?

要。每改一次 `config.toml`,跑 `cc-connect daemon restart` 让新 `[[projects]]` 块生效。改 `chat_id` 也要重启。

### Q4:项目跑挂(daemon 没响应)怎么 debug?

```bash
cc-connect daemon status
cc-connect daemon logs -f -n 100
```

看日志里有没有 `chat_id not matched` / `work_dir not found` / `token expired` 这类关键字。

### Q5:不同项目能用同一个 Claude Code 进程吗?

不能。每个 project 一个独立 Claude Code 子进程(独立 PID、独立 session 文件、独立 system_prompt)。这是隔离的代价,也是隔离的价值。

---

## 8. 相关文档

- [usage.md](usage.md) — cc-connect 基础(命令、cron/timer、relay、send、NO_REPLY 等)
- [../claude-code/session-management.md](../claude-code/session-management.md) — 长期项目的 session 管理心法
- 官方文档:<https://github.com/chenhg5/cc-connect/blob/main/docs/usage.md>
- WeChat 平台专章:<https://github.com/chenhg5/cc-connect/blob/main/docs/weixin.md>