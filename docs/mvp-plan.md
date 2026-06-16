# CC-AvatarGenerator MVP 方案

*Last updated: 2026-06-15*

## 一、验证目标

唯一要回答的问题：**「用户愿不愿意上传照片，付钱换一张线条头像？」**

成功指标（满足任意一个即可）：
- 10 个朋友里有 3 个表示"会用"
- 有人主动问"能不能帮我做一个"
- 有人愿意付 ¥9.9 拿高清版

---

## 二、功能边界

| 做 | 不做 |
|---|---|
| 上传照片 → 线条头像（预览图） | 登录/注册 |
| 下载预览图 | 支付（模拟即可） |
| Loading 状态 + 错误提示 | 高清下载（MVP 后期再加） |
| 多模型切换（对比用，URL 参数控制） | 历史记录 |
| | 内容审核 |
| | CDN/对象存储 |
| | 人脸检测（非清晰照片靠提示语引导用户） |

**多模型切换说明**：目的是模型横向对比效果，不是产品功能。用 URL 参数 `?model=xxx` 或页面底部隐藏入口控制，不进主流程 UI。

---

## 三、技术选型

| 层面 | 选择 | 理由 |
|---|---|---|
| 后端框架 | FastAPI (Python 3.11+) | 轻量、异步、适合产品基础 |
| 前端 | 纯 HTML + Tailwind CSS CDN + 原生 JS | 零构建工具，天然响应式，后续 H5 可复用 |
| MVP 测试模型 | `image-01`（MiniMax 图生图） | 国内可充值，subject_reference 图生图，先跑通全流程 |
| 对比模型 | `gpt-image-1`（Requesty images.edit） | 原生 img2img，输出稳定，备用对比 |
| Prompt 切换 | `MODELS[].prompt_file` | 每个模型绑定独立 prompt 文件，切换模型即切换 prompt |
| 图像处理 | Pillow | 只用于 resize，inline 在 generator.py |

---


**Prompt 文件**：
- `prompts/line_art.txt` — 完整版（gpt-image-1 等）
- `prompts/line_art_minimax.txt` — MiniMax 精简版（≤1500 字符）

## 四、项目结构

```
CC-AvatarGenerator/
├── app.py                   # FastAPI 入口，路由定义
├── config.py                # 模型注册表 + 环境变量读取
├── static/
│   └── index.html           # 前端单文件
├── services/
│   └── generator.py         # photo_to_line_art(image_bytes, model) → image_bytes
├── prompts/
│   ├── line_art.txt         # Prompt 模板（纯文本，可直接编辑）
│   └── references/          # prompt 调试用的 input/output 对，临时文件，可清理
├── references/              # style spec 参考图（7 张），已锁定，不随便修改
├── docs/
│   ├── mvp-plan.md
│   ├── design-decisions.md
│   ├── tech-comparison.md
│   └── prompt-tuning-guide.md  # prompt 调优指南 + 踩坑记录
├── requirements.txt
├── .env.example
└── .gitignore
```

> **两个 references 目录说明**：
> - `references/`（根目录）：style spec，7 张风格锚定参考图，`generator.py` 里引用此路径
> - `prompts/references/`：prompt 调试过程的测试 input/output，与代码无关，可随时清理

**删除的原始设计**：
- `services/preprocessor.py` → resize 逻辑 inline 进 generator.py（3 行）
- `services/quality_checker.py` → 用 try/retry(1次) 替代，MVP 不需要 CV 分析
- `prompts/line_art.toml` → 改为 `.txt`，无需额外解析库

---

## 五、核心流程

```
用户上传照片
  ↓
resize 到 1024×1024 + 转换为 RGBA PNG（Pillow，inline）
  ↓  ⚠️ gpt-image-1 images.edit() 只接受 RGBA PNG，JPEG 必须在此处转换
读取 line_art.txt，构建请求
  ↓
调用模型 API（gpt-image-1 images.edit 或 fal.ai）
  ↓
失败? → 重试一次 → 仍失败 → 返回友好错误提示
  ↓
返回 base64 图片
  ↓
前端：展示预览 + 下载按钮（loading 态管理见下）
```

> **注意**：`references/` 参考图在 MVP 阶段不传入 API 请求（gpt-image-1 的 images.edit 以 prompt 文字驱动风格），仅作为人工评估对齐标准。Post-MVP 可探索将参考图作为 style reference 传入。

---

## 六、前端 UX 关键状态

```
初始态      →  [上传区域]  拖拽或点击选择照片
上传后       →  [锁定按钮] + loading 动画 + "通常需要 10-20 秒"提示
生成成功    →  预览图 + [下载] 按钮，平滑过渡
生成失败    →  错误提示（"生成失败，请重试"）+ 重新上传入口
```

实现方式：fetch + JS 状态机，不需要 SSE 或 WebSocket。

---

## 七、API 路由设计

```
POST /generate
  Request:  multipart/form-data
    - file: image (jpg/png, ≤10MB)
    - model: string (optional, default="gpt-image-1")
  Response: JSON
    - image_base64: string
    - model_used: string
    - duration_ms: int

GET /models
  Response: JSON
    - models: [{id, name, provider}]   # 返回可用模型列表，供前端下拉
```

---

## 八、成功后的下一步

1. 增加风格选择（2-3 种）
2. 上线高清付费下载
3. H5 适配
4. 根据对比测试结果，决定是否切换主力模型或自建管线
