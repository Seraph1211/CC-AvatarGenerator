"""Model registry & global config.

核心结构:
  - ModelConfig: 单个模型部署的完整配置(provider 协议 + base_url + api_key_env 等)
  - PROVIDERS: 协议名 -> provider 类的注册表(来自 services/providers 包)
  - MODELS: registry_key -> ModelConfig 的全局模型清单
  - ACTIVE_MODEL: 全局默认激活的模型(可被环境变量 ACTIVE_MODEL 覆盖)
  - get_model(): 按 key 取 ModelConfig,支持 fallback

扩展指南:
  - 加新 OpenAI 兼容中转:在 MODELS 加一个 entry,provider="openai_compat" 即可
  - 加新平台(OpenAI 官方):同上,只换 base_url 和 api_key_env
  - 加新协议:在 services/providers/ 写新类,在 providers 包 __init__.py 的
    PROVIDERS 注册,再在 MODELS 加 entry 指向它
"""
import os
from dotenv import load_dotenv

from services.providers import PROVIDERS, ModelConfig

load_dotenv()


# ---- Base URL 集中管理(可被环境变量覆盖)----
PACKYAPI_BASE_URL = os.getenv("PACKYAPI_BASE_URL", "https://www.packyapi.com/v1")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
REQUESTY_BASE_URL = os.getenv("REQUESTY_BASE_URL", "https://router.requesty.ai/v1")


# ---- 全局激活模型(可被环境变量 ACTIVE_MODEL 覆盖)----
ACTIVE_MODEL = os.getenv("ACTIVE_MODEL", "image-01")


# ---- 模型注册表 ----
# 每个 entry 描述一个 (协议, 模型, 平台) 三元组,前端 dropdown 一项。
# 同底层模型在多个平台 = 多个 entry(比如 GPT-Image-2 同时在 PackyAPI 和 OpenAI 官方)。
MODELS: dict[str, ModelConfig] = {
    # === MiniMax 官方(默认) ===
    "image-01": ModelConfig(
        display_name="MiniMax Image 01",
        provider="minimax",
        model_id="image-01",
        base_url=MINIMAX_BASE_URL,
        api_key_env="MINIMAX_API_KEY",
        platform="MiniMax",
        prompt_file="prompts/line_art_minimax.txt",
        endpoint=f"{MINIMAX_BASE_URL}/v1/image_generation",
    ),
    "image-01-live": ModelConfig(
        display_name="MiniMax Image 01 Live",
        provider="minimax",
        model_id="image-01-live",
        base_url=MINIMAX_BASE_URL,
        api_key_env="MINIMAX_API_KEY",
        platform="MiniMax",
        prompt_file="prompts/line_art_minimax.txt",
        endpoint=f"{MINIMAX_BASE_URL}/v1/image_generation",
        style={"style_type": "元气", "style_weight": 0.8},
    ),

    # === PackyAPI 中转 ===
    "gpt-image-2": ModelConfig(
        display_name="GPT Image 2 (PackyAPI)",
        provider="openai_compat",
        model_id="gpt-image-2",
        base_url=PACKYAPI_BASE_URL,
        api_key_env="PACKYAPI_TOKEN_SORA",
        platform="PackyAPI",
        prompt_file="prompts/line_art.txt",
        txt2img_defaults={
            "size": "1024x1024",
            "quality": "high",
            "output_format": "png",
            "response_format": "url",
        },
        img2img_defaults={
            "size": "1024x1024",
            "quality": "high",
            "output_format": "png",
            "response_format": "url",
            "input_fidelity": "high",   # 关键:保留原图人物特征,头像产品必备
        },
    ),
    "gemini-3.1-flash-image-preview": ModelConfig(
        display_name="Gemini 3.1 Flash (PackyAPI)",
        provider="openai_compat",       # PackyAPI 把 Gemini 归一化为 OpenAI 协议
        model_id="gemini-3.1-flash-image-preview",
        base_url=PACKYAPI_BASE_URL,
        api_key_env="PACKYAPI_TOKEN",
        platform="PackyAPI",
        prompt_file="prompts/line_art.txt",
        # PackyAPI 文档:多传非标参数会触发上游 "submit request timeout",
        # 所以这里只传 response_format。
        txt2img_defaults={"response_format": "url"},
        img2img_defaults={"response_format": "url"},
    ),

    # === OpenAI 官方(预留,token 未配置时前端会报错,不会静默失败)===
    # 启用:把下面 entry 取消注释,配置 OPENAI_API_KEY 环境变量
    # "gpt-image-2-official": ModelConfig(
    #     display_name="GPT Image 2 (OpenAI 官方)",
    #     provider="openai_compat",
    #     model_id="gpt-image-2",
    #     base_url=OPENAI_BASE_URL,
    #     api_key_env="OPENAI_API_KEY",
    #     platform="OpenAI",
    #     img2img_defaults={"size": "1024x1024", "quality": "high", "input_fidelity": "high"},
    # ),

    # === OpenRouter 兜底链(可选,需 OPENROUTER_API_KEY)===
    # "openrouter-image": ModelConfig(
    #     display_name="OpenRouter Multimodal (兜底)",
    #     provider="openrouter",
    #     model_id="<具体模型>",
    #     base_url=OPENROUTER_BASE_URL,
    #     api_key_env="OPENROUTER_API_KEY",
    #     platform="OpenRouter",
    # ),
}


def get_model(key: str | None = None) -> ModelConfig:
    """按 key 取 ModelConfig。key=None 时回退到 ACTIVE_MODEL。

    Raises:
        KeyError: 未知 key 且无 fallback
    """
    key = key or ACTIVE_MODEL
    if key in MODELS:
        return MODELS[key]
    if ACTIVE_MODEL in MODELS:
        return MODELS[ACTIVE_MODEL]
    raise KeyError(
        f"Unknown model: {key!r}. Available: {list(MODELS)}"
    )


# 暴露给老代码的兼容别名
DEFAULT_MODEL = ACTIVE_MODEL


def get_api_key(provider: str) -> str:
    """兼容老代码:按 provider 名字取 API key。

    新代码应直接构造 ModelConfig 并交给 provider 内部用。
    """
    env_map = {
        "requesty": "REQUESTY_API_KEY",
        "openai": "OPENAI_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "packyapi": "PACKYAPI_TOKEN_SORA",
        "minimax": "MINIMAX_API_KEY",
        "falai": "FALAI_API_KEY",
    }
    env_name = env_map.get(provider)
    if not env_name:
        env_name = f"{provider.upper()}_API_KEY"
    key = os.getenv(env_name)
    if not key:
        raise ValueError(f"Missing {env_name} in environment")
    return key


def resolve_model_config(model_id: str) -> ModelConfig:
    """兼容老代码:接受 registry key 或底层 model_id 字符串。

    新代码应使用 get_model()。
    """
    if model_id in MODELS:
        return MODELS[model_id]
    for cfg in MODELS.values():
        if cfg.model_id == model_id:
            return cfg
    return get_model()


def get_active_model() -> ModelConfig:
    return get_model()


__all__ = [
    "PROVIDERS",
    "MODELS",
    "ACTIVE_MODEL",
    "DEFAULT_MODEL",
    "ModelConfig",
    "get_model",
    "get_api_key",
    "resolve_model_config",
    "get_active_model",
    "PACKYAPI_BASE_URL",
    "MINIMAX_BASE_URL",
    "OPENAI_BASE_URL",
    "OPENROUTER_BASE_URL",
    "REQUESTY_BASE_URL",
]
