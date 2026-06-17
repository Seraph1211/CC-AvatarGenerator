# 架构设计文档

*Last updated: 2026-06-17*

> 服务端图像生成管线的架构设计。从"单一 if/elif 派发"演进到"协议 + 平台"二维解耦的可扩展结构。
> 配套代码：`services/` + `config.py` + `app.py`。

---

## 1. 设计目标

- **可扩展**：加一个新平台/协议/模型的成本可控（最好零业务代码改动）
- **可测试**：测试脚本与生产共用同一份 API 调用代码（"test what you ship"）
- **可观测**：每次调用都有结构化的 provider/model/latency 元信息
- **不退化**：原有 4 套 provider（minimax / falai / openai / openrouter）的行为保持不变

---

## 2. 架构分层

```
┌──────────────────────────────────────────────────────────────┐
│  HTTP 层    app.py  ─  POST /generate  ─  路由 + 鉴权         │
└────────────────────────┬─────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────┐
│  编排层    services/generator.py                              │
│            AvatarGenerator  ─  preprocess → provider → gate  │
└──────┬──────────────────┬─────────────────────┬─────────────┘
       │                  │                     │
┌──────▼──────┐  ┌────────▼──────────┐  ┌────────▼──────────┐
│ 预处理      │  │ 协议层            │  │ 质量门            │
│ preprocessor │  │ providers/*       │  │ quality_checker  │
│ .py          │  │ (4 套实现)         │  │ .py              │
└─────────────┘  └────────┬──────────┘  └───────────────────┘
                          │
                ┌─────────▼─────────┐
                │ 配置层            │
                │ config.py         │
                │ ModelConfig +     │
                │ PROVIDERS dict    │
                └───────────────────┘
```

每一层只依赖下一层，且向下注入配置——上层不感知具体协议，下层不感知上层业务。

---

## 3. 核心抽象

### 3.1 `ImageProvider` 抽象基类（`services/providers/base.py`）

```python
class ImageProvider(ABC):
    name: ClassVar[str]                    # 协议名，如 "openai_compat"

    def __init__(self, model_config): ...   # 注入配置 + API key

    @abstractmethod
    def img2img(self, request) -> ImageResult: ...

    @abstractmethod
    def txt2img(self, request) -> ImageResult: ...
```

- 一个 provider = 一种 wire 协议
- 跨平台的差异（base_url、api_key）由 `model_config` 注入，provider 类本身不感知

### 3.2 `ImageRequest` / `ImageResult` 统一数据类型

```python
@dataclass
class ImageRequest:
    prompt: str
    image: bytes | None = None          # 图生图必填
    params: dict = field(default_factory=dict)  # 调用方覆盖默认参数

@dataclass
class ImageResult:
    image_bytes: bytes                  # 所有 provider 出口的统一格式
    mime_type: str = "image/png"
    provider: str = ""                  # 协议名
    model_id: str = ""                  # 传给 API 的 model 字段
    model_key: str = ""                 # 注册表 key（兜底链用 "X -> Y" 格式）
    platform: str = ""                  # 平台归属
    latency_ms: int = 0
    raw: dict | None = None             # 原始响应（监控/调试）

    def to_base64(self) -> str: ...     # 前端 API 用
```

下游消费者（generator / app.py）只跟 `ImageResult` 打交道，不感知具体协议。

### 3.3 `ModelConfig` 注册表条目（`config.py`）

```python
@dataclass
class ModelConfig:
    display_name: str
    provider: str            # 协议名（PROVIDERS 注册表的 key）
    model_id: str            # 实际传给 API 的 model 字段
    base_url: str
    api_key_env: str
    platform: str
    prompt_file: str = "prompts/line_art.txt"
    txt2img_defaults: dict = field(default_factory=dict)
    img2img_defaults: dict = field(default_factory=dict)
    preprocess_max_dim: int = 1024
    default_headers: dict | None = None
    style: dict | None = None
```

字段按"调用一次 API 需要的所有信息"组织——`preprocess_max_dim` 让测试/生产按需缩图，`default_headers` 装 OpenRouter 必需的 HTTP-Referer，`style` 是 MiniMax 特有字段。新增字段直接在 dataclass 上加，provider 通过 `getattr(cfg, "field", default)` 读取。

---

## 4. 关键设计：协议 vs 平台

`provider` 字段 = 协议（"用什么方式调 API"），`base_url + api_key_env` = 平台（"请求发到哪去"）。两者解耦后：

| 想做的事 | 改 `config.py` 即可？ | 改代码？ |
|---|---|---|
| 加一个 OpenAI 兼容中转 | ✅ 1 行 `ModelConfig` | ❌ |
| 同一个模型走两个平台 | ✅ 1 行 entry（带平台后缀） | ❌ |
| 加 OpenAI 官方 gpt-image-2 | ✅ 1 行 entry | ❌ |
| 加 Gemini 原生协议 | ❌ | ✅ 新 provider 文件 + 注册 |
| 加 Midjourney / Sora | ❌ | ✅ 新 provider 文件 + 注册 |

直觉：**协议稳定、平台多变**——绝大多数新接入都是 OpenAI 兼容的中转（`openai_compat`），按平台维度扩展是高频路径。

---

## 5. 调用链路

```
HTTP /generate
  ↓
app.py 读取 multipart file + model
  ↓
generator.generate_avatar(image_bytes, model_key)
  │
  ├─ 1. cfg = get_model(model_key)
  ├─ 2. prompt = load_prompt(cfg.prompt_file)
  ├─ 3. preprocessed = preprocess_image(image_bytes, max_dim=cfg.preprocess_max_dim)
  ├─ 4. provider = make_provider(cfg)             # PROVIDERS[cfg.provider](cfg)
  ├─ 5. result = provider.img2img(ImageRequest(prompt, image=preprocessed))
  │     └─ 兜底：OpenRouterToSError → image-01-live
  ├─ 6. quality_checker.passes(result.image_bytes)  # 质量门
  └─ 7. 返回 ImageResult
  ↓
app.py 包装成 {image_base64, model_used, platform, latency_ms, duration_ms} 返回前端
```

每一环都是协议无关的——`preprocessor` 不知道也不关心下游是 PackyAPI 还是 OpenAI；`quality_checker` 不知道上游是哪个 provider。

---

## 6. provider 实现现状

| 协议类 | 文件 | 覆盖平台 | 备注 |
|---|---|---|---|
| `OpenAICompatProvider` | `openai_compat.py` | PackyAPI、OpenAI 官方、Requesty、所有 OpenAI 兼容中转 | 一次实现覆盖 80% 用例 |
| `ChatCompletionsProvider` | `chat_completions.py` | OpenAI/Requesty 的多模态模型 | base class 给 OpenRouter 继承 |
| `MiniMaxProvider` | `minimax.py` | MiniMax image-01 / image-01-live | 走原生 httpx，subject_reference 协议 |
| `OpenRouterProvider` | `openrouter.py` | OpenRouter | 继承 ChatCompletions，加 `modalities=image` + ToS 兜底 |

`falai` 的 provider 暂未迁移——`MODELS` 中也没有 falai 条目，重构期未跑该路径。后续如需接入补一个 `providers/falai.py` 即可。

---

## 7. 测试与生产同源

`test/packyapi/test_packyapi.py` 重构后从 588 行降到 179 行，且**只做四件事**：
1. argparse 解析 `--model` / `--test`
2. 调 `preprocess_image(raw, max_dim=512)` 缩图
3. 调 `make_provider(cfg).img2img(request)`（**和生产完全同源**）
4. 保存字节到 `test/packyapi/img/{model_key}/output_{suffix}_{NNN}.png`

`IMG_MAX_DIM=512` 是测试场景专用（规避 PackyAPI 60s 长连接问题），通过 `preprocess_image(max_dim=)` 参数注入，**不污染生产配置**。生产用 `cfg.preprocess_max_dim`（默认 1024）。

效果：测试脚本调通的 provider，生产一定调通；反之亦然。

---

## 8. 前端集成

### 8.1 `/models` 端点协议

```json
{
  "default": "image-01",
  "enabled": true,            // SHOW_MODEL_SELECT 开关
  "models": [
    {"id": "image-01", "name": "MiniMax Image 01", "provider": "minimax", "platform": "MiniMax", "model_id": "image-01"},
    ...
  ]
}
```

- **`enabled=false`** → 前端隐藏整个模型选择区，统一用 `ACTIVE_MODEL`；业务流程不出现任何模型信息
- **`models[]`** → 只包含 `visible=True` 的条目（兜底链如 `openrouter-image` 自动隐藏）

### 8.2 UI 行为

| 元素 | `enabled=true` | `enabled=false` |
|---|---|---|
| 模型 dropdown | 扁平列表，按 `display_name` 顺序 | 隐藏 |
| URL `?model=X` 参数 | 生效（dropdown 默认选中） | 忽略 |
| `formData` 携带 `model` | 是 | 否（后端兜底 `ACTIVE_MODEL`） |
| Loading 文案 | "正在使用「X」生成..." | "正在生成..." |
| 结果展示 | `模型：X · 耗时 Y 秒` | `耗时 Y 秒` |

### 8.3 `display_name` 兜底链解析

`_resolve_display_name(model_key)` 处理两种格式：
- 正常 key → `MODELS[key].display_name`
- 兜底链 `"X -> Y"` → `MODELS[Y].display_name`（即最终生效的模型）

这样前端展示"模型：MiniMax Image 01 Live"而不是"openrouter-image → image-01-live"。

### 8.4 提示音

Web Audio API：
- 成功：800Hz sine 单声（柔和）
- 失败：400Hz square 双声（急促）

AudioContext 在第一次点"生成"时 unlock，规避浏览器自动播放限制。

### 8.5 后端 /generate 防御

开关关闭时，**不信任前端 `model` 字段**：
```python
if not SHOW_MODEL_SELECT or not model:
    model = ACTIVE_MODEL
```
防止老版前端缓存或外部调用绕过开关。

---

## 9. 功能开关：SHOW_MODEL_SELECT

| 维度 | 行为 |
|---|---|
| 配置位置 | `config.py:161` / `.env` |
| 默认值 | `true`（保持现状） |
| 控制对象 | 前端模型选择区可见性 |
| 后端联动 | `/models.enabled` 字段 + `/generate` 强制 `ACTIVE_MODEL` |
| 日志影响 | 无（日志中 model 字段仍记录实际使用的模型） |

**典型用法：**
- 单模型部署（如只用 MiniMax image-01）→ 设 `false`，简化 UI
- 调试/对比多模型 → 设 `true`，保留选择能力

---

## 10. 扩展指南（实操）

### 加一个 OpenAI 兼容中转（如 api.example.com）

在 `config.py` 加一个 `ModelConfig`：
```python
"MyModel-Example": ModelConfig(
    display_name="My Model (Example)",
    provider="openai_compat",
    model_id="my-model-v1",
    base_url="https://api.example.com/v1",
    api_key_env="EXAMPLE_API_KEY",
    platform="Example",
    img2img_defaults={"size": "1024x1024", "quality": "low"},
),
```
完事。重启服务，dropdown 自动出现。

### 加一个新协议（如 Gemini 原生）

1. 新建 `services/providers/gemini_native.py`，继承 `ImageProvider` 实现 `img2img` / `txt2img`
2. 在 `services/providers/__init__.py` 的 `PROVIDERS` 字典加一行注册
3. 在 `config.py` 加 `ModelConfig(provider="gemini_native", ...)` 条目

### 加一个 Prompt 变体

`ModelConfig.prompt_file` 字段已经支持每个模型独立的 prompt 路径。直接加新文件 + 在 entry 中改 `prompt_file` 即可。

---

## 11. 待办

- [ ] `services/quality_checker.py` 当前是占位实现（只验证 PIL 能解码）—— post-MVP 接入 blank detection / edge density / color distribution 三档检查
- [ ] `_dbg` 硬编码到绝对路径 `/Users/seraph/.../.cursor/debug-c32fda.log`——应改为相对路径或 env var
- [ ] `falai` provider 未迁移（不在 MODELS 中，本次跳过）
- [ ] 监控埋点：每次成功/失败调用应上报 `provider / model / platform / latency_ms / 错误类型` 到集中日志
- [ ] Provider 调用增加 retry 策略：当前单次失败立即抛错，应在网络错误/限流场景下重试 1-2 次
