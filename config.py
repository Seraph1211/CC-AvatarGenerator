"""Model registry + provider protocol config.

设计要点：
  - ModelConfig 是 dataclass，按字段明确表达每个模型的（协议、平台、参数）三要素
  - provider 字段表示"协议"（如 openai_compat、minimax、openrouter），
    同协议下不同平台（PackyAPI / OpenAI 官方）的差异由 base_url + api_key_env 体现
  - 新增 OpenAI 兼容中转平台 = MODELS 加一行；新增协议 = providers/ 加一个文件
"""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


# ============================================================
# Provider 协议注册表
# ============================================================
# 由 services/providers/__init__.py 填充，这里做延迟绑定避免循环 import。
# 写法说明：在 config.py 中保留 PROVIDERS 名字空间，前端可通过 /models 看到协议名。
PROVIDERS_REGISTRY: dict[str, str] = {
    "openai_compat": "OpenAI Images API 协议（覆盖 PackyAPI / OpenAI 官方 / Requesty 等）",
    "chat_completions": "OpenAI Chat Completions 多模态协议",
    "minimax": "MiniMax 自定义协议（subject_reference）",
    "openrouter": "OpenRouter 图像多模态（含 ToS 兜底）",
}


# ============================================================
# Model registry
# ============================================================

@dataclass
class ModelConfig:
    """单个模型条目的完整配置。

    字段按"调用一次 API 需要的所有信息"组织：
      - 协议相关：provider
      - 路由相关：base_url, api_key_env, model_id, platform
      - 提示词：prompt_file
      - 协议级默认参数：txt2img_defaults, img2img_defaults
      - 预处理：preprocess_max_dim（影响上传到上游的图片大小）
      - 特殊：default_headers（OpenRouter 必需）、style（MiniMax 特定）
    """

    display_name: str
    provider: str
    model_id: str
    base_url: str
    api_key_env: str
    platform: str
    prompt_file: str = "prompts/line_art.txt"
    txt2img_defaults: dict = field(default_factory=dict)
    img2img_defaults: dict = field(default_factory=dict)
    preprocess_max_dim: int = 1024
    default_headers: dict | None = None
    style: dict | None = None  # MiniMax 特定字段
    visible: bool = True       # False = 仅供内部/兜底链使用，不展示给前端用户


MODELS: dict[str, ModelConfig] = {
    # ----- MiniMax -----
    "image-01": ModelConfig(
        display_name="MiniMax Image 01",
        provider="minimax",
        model_id="image-01",
        base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com"),
        api_key_env="MINIMAX_API_KEY",
        platform="MiniMax",
        prompt_file="prompts/line_art_minimax.txt",
    ),
    "image-01-live": ModelConfig(
        display_name="MiniMax Image 01 Live",
        provider="minimax",
        model_id="image-01-live",
        base_url=os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com"),
        api_key_env="MINIMAX_API_KEY",
        platform="MiniMax",
        prompt_file="prompts/line_art_minimax.txt",
        style={"style_type": "元气", "style_weight": 0.8},
    ),
    # ----- PackyAPI GPT Image 2 -----
    "GPT-Image-2": ModelConfig(
        display_name="GPT Image 2 (PackyAPI)",
        provider="openai_compat",
        model_id="gpt-image-2",
        base_url=os.getenv("PACKYAPI_BASE_URL", "https://www.packyapi.com/v1"),
        api_key_env="PACKYAPI_TOKEN_SORA",
        platform="PackyAPI",
        img2img_defaults={
            "size": "1024x1024",
            "quality": "low",
            "input_fidelity": "high",
            "extra_body": {"output_format": "png"},
        },
        txt2img_defaults={
            "size": "1024x1024",
            "quality": "low",
            "extra_body": {"output_format": "png"},
        },
    ),
    # ----- OpenAI 官方 GPT Image 2 -----
    "GPT-Image-2-Official": ModelConfig(
        display_name="GPT Image 2 (OpenAI 官方)",
        provider="openai_compat",
        model_id="gpt-image-2",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        platform="OpenAI",
        img2img_defaults={
            "size": "1024x1024",
            "quality": "low",
            "input_fidelity": "high",
        },
        txt2img_defaults={
            "size": "1024x1024",
            "quality": "low",
        },
    ),
    # ----- PackyAPI Gemini 3.1 Flash Image Preview -----
    "Gemini-3.1-Flash-Image-Preview": ModelConfig(
        display_name="Gemini 3.1 Flash Image (PackyAPI)",
        provider="openai_compat",  # PackyAPI 把 Gemini 归一化为 OpenAI 协议
        model_id="gemini-3.1-flash-image-preview",
        base_url=os.getenv("PACKYAPI_BASE_URL", "https://www.packyapi.com/v1"),
        api_key_env="PACKYAPI_TOKEN",
        platform="PackyAPI",
        img2img_defaults={"response_format": "url"},
        txt2img_defaults={"response_format": "url"},
    ),
    # ----- OpenRouter 多模态（兜底链，不展示给用户）-----
    "openrouter-image": ModelConfig(
        display_name="OpenRouter Multimodal (兜底链)",
        provider="openrouter",
        model_id="google/gemini-2.5-flash-image-preview",  # 占位，按需调整
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key_env="OPENROUTER_API_KEY",
        platform="OpenRouter",
        default_headers={
            "HTTP-Referer": "https://github.com/Seraph1211/CC-AvatarGenerator",
            "X-Title": "CC-AvatarGenerator",
        },
        visible=False,
    ),
}


# ============================================================
# Active model selection
# ============================================================

ACTIVE_MODEL = os.getenv("ACTIVE_MODEL", "GPT-Image-2")
# 保留旧名 DEFAULT_MODEL 作为别名，避免引用方修改
DEFAULT_MODEL = ACTIVE_MODEL

# 功能开关：模型选择 UI
# True  → 前端显示下拉菜单，用户可选模型
# False → 前端隐藏模型选择区；统一用 ACTIVE_MODEL；
#         业务流程不出现任何模型信息（loading 文案、结果展示都隐藏）
SHOW_MODEL_SELECT = os.getenv("SHOW_MODEL_SELECT", "true").lower() in ("true", "1", "yes")


# ============================================================
# Helpers
# ============================================================

def get_model(key: str) -> ModelConfig:
    """按注册表 key 查询模型配置。"""
    if key not in MODELS:
        raise KeyError(f"Unknown model: {key!r}. Available: {list(MODELS)}")
    return MODELS[key]


def resolve_model_config(key: str) -> ModelConfig:
    """兼容旧接口：支持 registry key 或 API model_id 查询，未命中时回退到 active model。"""
    if key in MODELS:
        return MODELS[key]
    for cfg in MODELS.values():
        if cfg.model_id == key:
            return cfg
    return get_model(ACTIVE_MODEL)


def list_models() -> list[dict]:
    """供 /models 端点使用的标准化输出——只返回 visible=True 的模型。"""
    return [
        {
            "id": k,
            "name": v.display_name,
            "provider": v.provider,
            "platform": v.platform,
            "model_id": v.model_id,
        }
        for k, v in MODELS.items()
        if v.visible
    ]


def get_visible_default() -> str:
    """返回第一个 visible=True 的模型 key——前端兜底默认。"""
    for k, v in MODELS.items():
        if v.visible:
            return k
    return ACTIVE_MODEL
