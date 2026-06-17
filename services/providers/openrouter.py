"""OpenRouter 多模态 provider——基于 Chat Completions 协议，扩展图像模态声明。

特殊点：
  - 必须传 extra_body={"modalities": ["image", "text"]}
  - 必须传 default_headers: HTTP-Referer + X-Title
  - 服务端可能返回 Terms Of Service 403 拒绝——上层按业务规则做兜底
"""
from typing import ClassVar

from .chat_completions import ChatCompletionsProvider
from .base import ImageGenError


class OpenRouterToSError(ImageGenError):
    """OpenRouter 服务端因 ToS 拒绝——上层可捕获并切到兜底模型。"""


class OpenRouterProvider(ChatCompletionsProvider):
    """OpenRouter 图像多模态模型——继承 ChatCompletions，加 modalities + ToS 处理。"""

    name: ClassVar[str] = "openrouter"

    def img2img(self, request):
        # 注入 modalities=image 到请求级 params
        request.params.setdefault("extra_body", {})
        if "modalities" not in request.params["extra_body"]:
            request.params["extra_body"]["modalities"] = ["image", "text"]
        try:
            return super().img2img(request)
        except ImageGenError as e:
            text = str(e)
            if "Terms Of Service" in text or "403" in text:
                raise OpenRouterToSError(
                    "OpenRouter blocked this image request with provider Terms Of Service (403). "
                    "This is a provider policy restriction, not a request format issue. "
                    "Switch to a fallback model or check OpenRouter provider permissions.",
                    provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
                ) from e
            raise

    def txt2img(self, request):
        raise ImageGenError(
            f"{self.name} provider does not implement txt2img in MVP",
            provider=self.name, model_id=self.cfg.model_id,
        )
