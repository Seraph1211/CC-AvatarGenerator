"""图像生成 provider 包。

公开接口:
  - PROVIDERS: 协议名 -> provider 类的注册表
  - make_provider(cfg): 工厂函数,根据 ModelConfig.provider 实例化对应 provider
  - ImageRequest / ImageResult: 统一请求/响应类型
  - ImageProvider: 抽象基类(供新增 provider 类继承)
  - ModelConfig: 模型部署配置 dataclass
  - 异常类: ImageGenError / AuthError / ModelNotFoundError
"""
from .base import (
    ImageProvider,
    ImageRequest,
    ImageResult,
    ModelConfig,
    ImageGenError,
    AuthError,
    ModelNotFoundError,
)
from .openai_compat import OpenAICompatProvider
from .chat_completions import ChatCompletionsProvider
from .minimax import MiniMaxProvider
from .openrouter import OpenRouterProvider, OpenRouterToSError

# 协议注册表:加新协议只需往里加一行
PROVIDERS: dict[str, type[ImageProvider]] = {
    OpenAICompatProvider.name: OpenAICompatProvider,
    ChatCompletionsProvider.name: ChatCompletionsProvider,
    MiniMaxProvider.name: MiniMaxProvider,
    OpenRouterProvider.name: OpenRouterProvider,
}


def make_provider(cfg: ModelConfig) -> ImageProvider:
    """工厂:根据 cfg.provider 字段,实例化对应 provider。"""
    cls = PROVIDERS.get(cfg.provider)
    if cls is None:
        raise ValueError(
            f"Unknown provider: {cfg.provider!r}. "
            f"Available: {list(PROVIDERS)}"
        )
    return cls(cfg)


__all__ = [
    "PROVIDERS",
    "make_provider",
    "ImageProvider",
    "ImageRequest",
    "ImageResult",
    "ModelConfig",
    "ImageGenError",
    "AuthError",
    "ModelNotFoundError",
    "OpenRouterToSError",
    "OpenAICompatProvider",
    "ChatCompletionsProvider",
    "MiniMaxProvider",
    "OpenRouterProvider",
]
