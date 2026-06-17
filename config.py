"""Model registry and configuration."""
import os
from dotenv import load_dotenv

load_dotenv()

REQUESTY_BASE_URL = os.getenv("REQUESTY_BASE_URL", "https://router.requesty.ai/v1")
MINIMAX_BASE_URL = os.getenv("MINIMAX_BASE_URL", "https://api.minimaxi.com")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
PACKYAPI_BASE_URL = os.getenv("PACKYAPI_BASE_URL", "https://www.packyapi.com/v1")

DEFAULT_PROMPT_FILE = "prompts/line_art.txt"

# Model registry (keys are used in ACTIVE_MODEL and API ?model= param)
MODELS = {
    "image-01": {
        "name": "MiniMax Image 01",
        "provider": "minimax",
        "endpoint": f"{MINIMAX_BASE_URL}/v1/image_generation",
        "model": "image-01",
        "prompt_file": "prompts/line_art_minimax.txt",
    },
    "image-01-live": {
        "name": "MiniMax Image 01 Live",
        "provider": "minimax",
        "endpoint": f"{MINIMAX_BASE_URL}/v1/image_generation",
        "model": "image-01-live",
        "prompt_file": "prompts/line_art_minimax.txt",
        "style": {
            "style_type": "元气",
            "style_weight": 0.8,
        },
    },
    "GPT-Image-2": {
        "name": "GPT Image 2 (via PackyAPI)",
        "provider": "packyapi",
        "endpoint": f"{PACKYAPI_BASE_URL}/images/edits",
        "model": "gpt-image-2",
        "prompt_file": "prompts/line_art.txt",
    },
}

DEFAULT_MODEL = os.getenv("ACTIVE_MODEL", "image-01")


def get_api_key(provider: str) -> str:
    """Return API key for a provider."""
    if provider in ("requesty", "openai"):
        env_name = "REQUESTY_API_KEY"
    elif provider == "openrouter":
        env_name = "OPENROUTER_API_KEY"
    elif provider == "packyapi":
        env_name = "PACKYAPI_TOKEN_SORA"
    else:
        env_name = f"{provider.upper()}_API_KEY"
    key = os.getenv(env_name)
    if not key:
        raise ValueError(f"Missing {env_name} in environment")
    return key


def resolve_model_config(model_id: str) -> dict:
    """Resolve registry key or API model name to a model config dict."""
    if model_id in MODELS:
        return MODELS[model_id]
    for cfg in MODELS.values():
        if cfg["model"] == model_id:
            return cfg
    fallback_key = DEFAULT_MODEL if DEFAULT_MODEL in MODELS else "image-01"
    return MODELS[fallback_key]


def get_active_model() -> dict:
    return resolve_model_config(DEFAULT_MODEL)
