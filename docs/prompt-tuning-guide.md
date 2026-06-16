# Prompt 调优指南

*Last updated: 2026-06-15*

本文记录 `prompts/line_art.txt` 的优化思路、已踩过的坑、以及遇到具体问题时的调整方向。

---

## 当前 Prompt 的核心设计思路（v3）

**反直觉的关键认知：不要让模型"转换"照片，要让模型"画一个人"。**

- 旧思路（错）："把照片转换成线条风格" → 模型会把照片所有边缘描一遍，出素描
- 新思路（对）："看一眼照片，然后用最少的笔画出这个人" → 模型以插画师视角工作

Prompt 结构三层：
1. **任务定性**（最前面，权重最高）：明确"不是描照片，是画人物"
2. **身份提取**：只捕捉性别、发型、服装类型、姿势这四件事
3. **笔触约束**（量化）：整图 <50 笔，每个区域有上限，给模型一个可感知的目标

---

## 已知陷阱与修复记录

### 陷阱 1：输出是随机人物，不是照片里的人
**现象**：生成了一个完全不同的人（不同性别、不同配件）

**根因**：prompt 开头是风格描述，身份约束权重太低；prompt 里列举的配件（包、眼镜）被模型当成生成指令

**修复**：
- 第一句话必须是身份锚定："The ONLY subject must be the exact person shown in the photo"
- 配件描述改为："ONLY accessories visible in the photo; do NOT invent any"

---

### 陷阱 2：素描感太强，像描线稿不像简笔画
**现象**：每根发丝、每条皱褶、每个面部轮廓都有线，像彩铅稿去色版

**根因**：prompt 里"faithfully preserve / exactly as they appear"让模型把照片所有信息都描出来

**修复**：
- 把任务定性从"transform"改为"draw as a character illustration — do NOT trace"
- 加量化笔触上限：整图 <50 笔，头发 3-5 笔，脸 4-6 个 mark
- 加成功标准："looks like drawn in under 3 minutes by a confident illustrator"

---

## 问题诊断决策树

遇到问题先对号入座，每次只改一个方向：

| 现象 | 根因 | 调整方向 |
|---|---|---|
| 输出是随机人物/配件对不上 | 身份锚定弱 | 把"ONLY subject must be the exact person"移到第一行；检查是否在 prompt 里列举了配件名词 |
| 素描感强/发丝太多 | 模型在"描"照片 | 加"do NOT trace photo edges"；降低头发笔触上限到 3-4 笔；加"drawn in under 3 minutes" |
| 有颜色/灰调/阴影 | 线条约束不够强 | 加"absolutely no color, no gray, no shading whatsoever"；把"No shading"顶到风格要求第一条 |
| 线条太细/太像钢笔 | 线条质感描述缺失 | 加"medium-thick brush-pen quality lines, not hairlines" |
| 面部太复杂/像素描肖像 | 脸部约束不够 | 强化"exactly 4-6 marks total for the face; no jaw outline" |
| 衣服细节太多 | 服装约束不够 | 加"outer silhouette only; maximum 2 interior lines per garment; ignore all seams and textures" |
| 背景有残留/有阴影 | 背景约束缺失 | 加"pure white background; no shadows; no ground plane" |
| 整体太复杂/像漫画分镜 | 总体约束缺失 | 加"total strokes across entire figure under 50; if it looks like a comic panel, simplify further" |
| 人物被截断/比例怪 | 构图未约束 | 加"full figure or waist-up, subject centered, leaving generous white space around" |
| 深色衣服没填实心黑 | 黑色填充规则不明确 | 加"clothing that is visibly dark/black in the photo should be rendered as solid black fill" |

---

## 调参节奏（重要）

**每次只改一个变量**，否则不知道哪处起效。

推荐流程：
1. 用固定的 5 张基准测试照（不同性别/发型/服装）
2. 改一处 prompt
3. 5 张全跑，不是只测一张
4. 对比前后版本，只保留带来整体改善的改动

---

## gpt-image-1 特性备忘

- **不支持 seed 参数**：输出稳定性完全靠 prompt 约束密度，prompt 越具体输出越收敛
- **images.edit() 可传多张图**：可以同时传用户照片 + 参考图，让模型"学习参考图风格"（Post-MVP 可探索）
- **内容过滤**：清晰的人像照片不容易触发；模糊/遮挡/非正面照可能被拒绝
- **输出尺寸**：fixed 1024×1024，前端展示时缩到 512px 即可
