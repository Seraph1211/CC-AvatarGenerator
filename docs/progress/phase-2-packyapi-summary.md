# Phase 2: PackyAPI 多模型调试 - 进度总结

*完成日期: 2026-06-17*
*对应 commit: `26f4c43` feat: 完成PackyAPI 多模型图生图调试 + 调整 test 目录结构*

---

## 目标

在 MVP 单模型跑通的基础上，接入 PackyAPI 平台的多模型（GPT-Image-2 / Gemini 等），做横向效果对比，验证 MVP 阶段主力模型的选择。

---

## 已完成

- ✅ 接入 PackyAPI 平台作为新 provider
- ✅ GPT-Image-2 接入（图生图 + 文生图两种模式）
- ✅ Gemini 系列模型测试（多模态路径）
- ✅ MiniMax prompt 精修（v2，适配更多边界场景）
- ✅ 新增 3 张参考资料图（`references/pic1-3.jpg`）
- ✅ 测试目录结构化（`test/packyapi/test_packyapi.py`，588 行）
- ✅ 引入 `utils/logger.py`（按天截断 logger）
- ✅ 调整 `.env.example` 补 PACKYAPI_TOKEN 等新环境变量
- ✅ 4 类测试样例：img2img / txt2img × 多个模型

---

## 关键决策与理由

| # | 决策 | 理由 |
|---|---|---|
| 1 | **PackyAPI 作为统一的"多模型中转"** | 比一个一个接 OpenAI 官方 / Gemini 官方快；统一鉴权 + 统一调用协议 |
| 2 | **测试与生产同源** | `test_packyapi.py` 直接调用 production 代码，不造平行实现 |
| 3 | **`utils/logger.py` 按天截断** | 调试期日志量会大，按天截断便于排查且不会撑爆磁盘 |
| 4 | **新 prompt 调优要"先小范围实验"** | 模型变了 prompt 必须重调；不直接覆盖 `line_art.txt` 而是先在小数据集验证 |

---

## 踩过的坑

- **坑 1：PackyAPI 不同模型的入参差异**
  - 现象：同样调"图生图"，GPT-Image-2 / Gemini / MiniMax 入参结构不一样
  - 根因：各模型 API 协议不统一
  - 修复：在 generator.py 里按 model 分支处理（临时方案，下个 phase 抽象）

- **坑 2：测试输出图片体积爆炸**
  - 现象：`test/output/` 目录很快堆到几 GB
  - 根因：每次测试都保存全分辨率原图
  - 修复：未根本解决，下个 phase 处理；当前用 `.gitignore` 隔离输出目录

- **坑 3：代理软件 60s 截断 gpt-image-2 长请求**
  - 现象：gpt-image-2 图生图 1-2.5min 的请求被掐断
  - 根因：本地代理软件默认 60s 超时
  - 修复：需加 `packyapi.com` 到白名单（详见 [PackyAPI 代理 60s 超时](../../) 笔记）
  - 状态：已记入项目记忆（待补到 docs）

---

## 未完成 / 留给 Phase 3+

- [ ] provider 抽象层（5 个模型 if/elif 链已经太长）
- [ ] 协议层 vs 平台层二维解耦
- [ ] 兜底链（OpenRouter 兜底 OpenAI 403）
- [ ] 测试输出图片清理机制
- [ ] gpt-image-2 prompt 独立文件
- [ ] 前端动态 `<optgroup>` 按平台分组

---

## 下个 session 接手时

1. 读 `services/generator.py` 的 `_generate_*` 系列函数，体会"if/elif 链已经不可维护"是为什么触发 provider 抽象
2. 看 `test/packyapi/test_packyapi.py` 的 588 行，里面有大量重复的 provider dispatch（待收敛）
3. 注意 `config.py:MODELS` 注册表已扩展到 5 个 model
4. PackyAPI 代理白名单是运行前提，否则必踩 60s 截断

---

## 关联

- 涉及 commit: `26f4c43`
- 涉及 PR: （本阶段无 PR）
- 相关 docs:
  - [mvp-plan.md](../mvp-plan.md) — MVP 范围
  - [phase-1-mvp-summary.md](phase-1-mvp-summary.md) — 上一阶段
  - 后续: [phase-3-refactor-summary.md](phase-3-refactor-summary.md)
- 涉及文件:
  - `config.py` (+32 行)
  - `services/generator.py` (+352/-147 行)
  - `test/packyapi/test_packyapi.py` (+588 行，新增)
  - `utils/logger.py` (+43 行，新增)
  - `prompts/line_art_minimax.txt` (重写，+31 行)
  - `references/pic1-3.jpg` (3 张新增)
  - `.env.example` (+10 行)

---

## 统计

- 代码: 1075 行新增 / 147 行删除
- 文件: 22 个变更 / 2 个新增
- 测试输出: 9 张图（被 gitignore）
- 时间: 1 天

---

## 反思（本阶段写给未来的自己）

**测试目录和测试输出体积管理是软基建**,本阶段意识到但没解决。下个 phase 之前要建一个 cleanup 机制（自动清理 7 天前的测试输出）。
