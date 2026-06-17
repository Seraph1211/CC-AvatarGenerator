"""Image generation provider abstraction.

provider 字段表示"协议"（OpenAI Images / Chat Completions / MiniMax native / ...），
同协议下不同平台（PackyAPI / OpenAI 官方 / Requesty）的差异由 model_config.base_url
和 api_key 体现——新增一个 OpenAI 兼容中转只需在 config.py 加一行 ModelConfig。
"""
from .base import ImageProvider, ImageRequest, ImageResult, ImageGenError
from .openai_compat import OpenAICompatProvider
from .chat_completions import ChatCompletionsProvider
from .minimax import MiniMaxProvider
from .openrouter import OpenRouterProvider

# 协议注册表：新增 provider 类只需往里加一行
PROVIDERS: dict[str, type[ImageProvider]] = {
    "openai_compat": OpenAICompatProvider,
    "chat_completions": ChatCompletionsProvider,
    "minimax": MiniMaxProvider,
    "openrouter": OpenRouterProvider,
}


def make_provider(model_config):
    """根据 model_config.provider 字段实例化对应的 provider。

    Args:
        model_config: config.ModelConfig 实例（dataclass）

    Returns:
        ImageProvider 子类实例

    Raises:
        KeyError: provider 协议名未注册
        ValueError: 缺少对应的 API key
    """
    provider_name = model_config.provider
    if provider_name not in PROVIDERS:
        raise KeyError(
            f"Unknown provider protocol: {provider_name!r}. "
            f"Registered: {list(PROVIDERS)}"
        )
    return PROVIDERS[provider_name](model_config)


__all__ = [
    "ImageProvider",
    "ImageRequest",
    "ImageResult",
    "ImageGenError",
    "PROVIDERS",
    "make_provider",
]
