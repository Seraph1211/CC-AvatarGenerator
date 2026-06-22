# 长期项目的 Session 管理

*Last updated: 2026-06-19*

> 跨周 / 跨月 / 跨半年的项目，Claude Code 的 session 该怎么开、什么时候清、状态怎么沉淀。
> 核心立场：**Session 是临时工，git + docs 是永久记忆**。
> 配套：[claude-code-tips.md](claude-code-tips.md) · [claude-code-features.md](claude-code-features.md) · [../cc-connect/](../cc-connect/README.md)

---

## 1. 核心心法：把"记忆"外化到项目文件里

**Session 是临时 context，不是持久记忆**。长期项目的关键不是"靠一个 session 记住一切"，而是**让项目文件自己记得**。

### 该把状态记在哪里

| 位置 | 写什么 |
|---|---|
| `CLAUDE.md` | 项目约定、必踩的坑、dev quirk |
| `docs/architecture.md` | 架构决策 |
| `docs/design-decisions.md` | 关键取舍 |
| `docs/prompt-tuning-guide.md` | 调优心得 |
| `docs/progress/<phase>-summary.md` | **每个阶段结束时的总结**（建议新建） |
| `.claude/rules/<scope>.md` | 路径作用域的规则 |
| git commit message | 关键变更的"为什么" |
| 代码注释 | 非显然的设计意图 |

**Session context 越短越好，关键状态都在磁盘上**。

---

## 2. 三种 Session 策略对比

| 策略 | 适合 | 不适合 | 长期项目评分 |
|---|---|---|---|
| **A. 一个 session 走到底，定期 `/clear`** | 短期项目（1-2 天） | 跨周/跨月项目 | ❌ |
| **B. 每次都开新 session** | 完全无关的零散任务 | 持续演进的项目 | ❌ |
| **C. 阶段化 session + 外化记忆** | **持续演进的项目** ✅ | - | ✅ **推荐** |

### 为什么 A 不好

- `/clear` 后这段 session 学到的东西全没了（除非写进磁盘）
- context 越撑越大，前 1/3 轮 Claude 几乎不记得了
- 失败尝试的"幽灵"还在（compact 也会保留）
- token 成本线性累积

### 为什么 B 不好

- 每个 session 都从零开始理解项目
- Claude 不知道你昨天为什么拒绝了一个方案
- 跨 session 的"决策一致性"靠人脑记忆 + git log——容易脱节

### 为什么 C 好

- 每个 session 是**干净、聚焦、便宜**的
- 关键状态在 `git` / `docs/` / `CLAUDE.md` 里，跨 session 持久
- session 之间用文档握手，Claude 进 session 就能快速"进入状态"
- 单个 session 失败不会污染后续工作

---

## 3. 阶段切分原则

**一个 session = 一个有清晰交付的阶段**。完成或阶段性完成后，写一份 progress doc，**开新 session**。

### 切分粒度参考

- 太小（如"修一个 typo 一个 session"）：太碎，开销大于收益
- 太大（如"半年所有事一个 session"）：context 爆炸
- **合适**：一个功能模块 / 一个阶段目标 / 一个可交付里程碑

### 例子（本项目视角）

```
┌─ Phase 1: MVP 上线 ──────────────────────────────┐
│  Session 1.1: 脚手架 + 基础模型接入                │
│  Session 1.2: 预处理 + 质量门                      │
│  Session 1.3: 前端 UI + 联调                       │
│  → 结束：写 docs/progress/phase-1-mvp.md           │
└───────────────────────────────────────────────────┘
┌─ Phase 2: 模型拓展 ──────────────────────────────┐
│  Session 2.1: PackyAPI 多模型接入                  │
│  Session 2.2: GPT-Image-2 / Gemini 适配            │
│  Session 2.3: 模型选择 UI + fallback 链            │
│  → 结束：写 docs/progress/phase-2-models.md        │
└───────────────────────────────────────────────────┘
┌─ Phase 3: Prompt 调优与稳定性 ───────────────────┐
│  Session 3.1: 引用图片风格对齐                      │
│  Session 3.2: 输出稳定性 4 层防御                   │
│  Session 3.3: 质量门迭代                            │
│  → 结束：写 docs/progress/phase-3-stability.md     │
└───────────────────────────────────────────────────┘
```

---

## 4. 实际工作流

### 4.1 启动一个阶段 session

```bash
# 启动新 session，命名
claude -n "phase-3-stability"

# 或者如果上次的 session 还没结清
claude --continue             # 恢复最近 session
claude --resume "phase-2-models"   # 按名字恢复
```

**第一步：让 Claude 先读项目状态**（1-2 轮就够，不必靠累积 context）

```
你现在接手这个项目的"稳定性"阶段。
先读：
1. docs/architecture.md
2. docs/design-decisions.md
3. docs/progress/phase-1-mvp.md
4. docs/progress/phase-2-models.md

读完后，告诉我你理解到的当前状态、已知风险、和未完成项。
```

这样**用一个干净的 session，只花 1-2 轮**，Claude 就"复习"完毕。

### 4.2 session 中途切任务时

| 场景 | 做法 |
|---|---|
| 相关任务 | 继续在当前 session（可以 `/clear` 清空噪音） |
| 完全不同主题 | 开新 session，别串 |
| 想保留当前又试新方向 | `--fork-session` 复制历史到新 session |
| 临时小问题 | `/btw` 问（答案不进 context） |

### 4.3 session 结束时：写 progress doc

**这是最关键的一步**。详见 [第 5 节](#5-progress-doc-模板)。

### 4.4 session 之间的"握手"流程

```
新 session 启动
    ↓
1. 命名: claude -n "phase-X-<topic>"
    ↓
2. 让 Claude 读上一阶段的 progress doc + 关键 docs/
    ↓
3. Claude 简述当前状态(确认它理解对了)
    ↓
4. 列出本阶段目标
    ↓
5. 开始干活
    ↓
6. 阶段结束:写 progress doc + git commit
    ↓
7. 开下一个 session(回到 1)
```

---

## 5. Progress Doc 模板

每个阶段 session 结束时，commit 这份 markdown 进 git：

```markdown
# Phase N: <阶段名> - 进度总结

*完成日期: YYYY-MM-DD*

## 目标
本阶段要达成什么（一两句话）

## 已完成
- ✅ 事项 1
- ✅ 事项 2
- ✅ 事项 3

## 踩过的坑
- **坑 1**: 现象 → 根因 → 修复
- **坑 2**: 现象 → 根因 → 修复

## 关键决策与理由
- 决策 A，因为 X，所以选 A 而非 B
- 决策 C ...

## 下个 session 接手时
1. 先看 [未完成](#未完成) 段
2. 重读 `docs/architecture.md#<相关段>`
3. 注意 `<关键文件>:<行号>` 的开关 / 约束

## 未完成
- [ ] 事项 X
- [ ] 事项 Y

## 关联
- 涉及 commit: <commit hash>
- 涉及 PR: <PR link>
- 相关 docs: docs/<other>.md
```

---

## 6. 关键命令速查

| 命令 | 用途 |
|---|---|
| `claude -n "name"` | 启动并命名 session |
| `/rename` | 给当前 session 改名 |
| `claude --continue` / `-c` | 恢复最近 session |
| `claude --resume <name\|id>` / `-r` | 按名字/ID 恢复 |
| `--fork-session` | 复制当前 session 到新 ID（不动原 session） |
| `/clear` | 清空 context（不丢磁盘上的状态） |
| `/compact <focus>` | 手动压缩，指定保留重点 |
| `/btw` | 临时问题，答案不进 context |
| `/agents` | 列出可用 subagent |

---

## 7. 必须避免的反模式

| 反模式 | 后果 |
|---|---|
| 一个 session 跑 3 周，只在满了之后 `/clear` | 关键决策在 clear 后丢失，Claude 重复犯同样错 |
| 每个小任务都开新 session | 跨任务的知识不连贯，每次都要重新解释项目 |
| progress doc 写完不 commit / 不更新 | 等于没写，下个 session 看不到 |
| 把所有"我要做"的事塞进一个长 session | "kitchen sink session"，所有任务都做不好 |
| 依赖 session context 记"为什么这样设计" | 一旦 clear 就忘了，设计漂移 |
| session 结束不写 progress doc | 下个 session 从零开始，重复劳动 |
| progress doc 写得很长很全，但没人读 | 失去"握手"价值，模板要简洁可扫读 |

---

## 8. 给本项目的具体建议

按 git log 看，项目分成了清晰阶段：

- `7987f00` feat: 初始化 MVP - 线条头像生成器
- `26f4c43` feat: 完成PackyAPI 多模型图生图调试
- `74ca3ea` refactor: 引入 provider 抽象层
- `8f3a5f1` feat: 模型选择后台开关 + UI 改进 + 日志增强

**这 4 个 commit 天然就是 4 个 session 阶段的产物**。建议立即执行：

1. **建 `docs/progress/` 目录**
2. **回看 git log，给每个 commit 补 `phase-N-*.md`**，从 commit message 展开"为什么这样做、踩过什么坑、还有什么没做"
3. **调整 CLAUDE.md** — 把"项目当前阶段 + 核心约束 + 已知坑"压到 200 行内
4. **以后的开发**：先想清楚"这是第几个 phase、目标是什么"，再开 session
5. **session 结束的标志** = 写了一篇 progress doc + commit 干净

这样**半年后回头看**，你（和 Claude）都能从 git log + progress docs + 现有 `docs/` 完整还原项目脉络，**不必依赖任何一个 session 的 context**。

---

## 9. 一句话总结

**Session 是临时工，git + docs 是你的永久记忆**。

长期项目 = **阶段化 session** + **外化到文件** + **阶段间用文档握手**。

Session 越短越干净越好，关键状态必须"离开 context 落到磁盘"。

---

## 参考

- [claude-code-tips.md](claude-code-tips.md) — 上下文管理 / `/clear` / `/btw` / `--resume` 等基础
- [claude-code-features.md](claude-code-features.md) — `Agent` 工具 / subagent 体系
- [../cc-connect/](../cc-connect/README.md) — 微信桥接：`send` / `cron` / `timer` / `relay` + 多项目路由方案
- [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices.md) — 官方最佳实践
- [How Claude Code works (agentic loop + context window)](https://code.claude.com/docs/en/how-claude-code-works.md) — context 机制
