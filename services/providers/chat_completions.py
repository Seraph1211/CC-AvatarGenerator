"""OpenAI Chat Completions 多模态协议 provider。

适用于：OpenAI 官方（gpt-image-1 部分情况）、Requesty、
任何把图片生成包成 chat completions 的中转。
endpoint：POST /v1/chat/completions
请求体：messages.content 为 [{type:text}, {type:image_url, image_url:{url:data:...}}]
响应：message.images (OpenRouter) 或 message.content 列表中的 image_url (OpenAI)。
"""
import base64
import time
from typing import ClassVar

from openai import OpenAI

from .base import (
    ImageGenError, ImageProvider, ImageRequest, ImageResult,
    _now_ms, decode_or_download,
)


class ChatCompletionsProvider(ImageProvider):
    """OpenAI Chat Completions 多模态协议——图生图。"""

    name: ClassVar[str] = "chat_completions"

    def _client(self) -> OpenAI:
        default_headers = getattr(self.cfg, "default_headers", None)
        return OpenAI(
            api_key=self.api_key,
            base_url=self.cfg.base_url,
            default_headers=default_headers,
            timeout=300,
        )

    def img2img(self, request: ImageRequest) -> ImageResult:
        if not request.image:
            raise ImageGenError(
                "img2img requires request.image",
                provider=self.name, model_id=self.cfg.model_id,
            )
        image_data_url = f"data:image/png;base64,{base64.b64encode(request.image).decode()}"
        defaults = getattr(self.cfg, "img2img_defaults", {}) or {}
        kwargs = {**defaults, **request.params}
        extra_body = kwargs.pop("extra_body", {})

        client = self._client()
        start = time.time()
        try:
            completion = client.chat.completions.create(
                model=self.cfg.model_id,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": request.prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }],
                **kwargs,
                extra_body=extra_body or None,
            )
        except Exception as e:
            raise ImageGenError(
                f"Chat completions failed: {e}",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            ) from e

        message = completion.choices[0].message
        img_b64 = self._extract_image_b64(message)
        if not img_b64:
            raise ImageGenError(
                f"Chat completion response did not include an image: {message.model_dump()}",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            )
        return ImageResult(
            image_bytes=base64.b64decode(img_b64),
            provider=self.name,
            model_id=self.cfg.model_id,
            platform=self.cfg.platform,
            latency_ms=_now_ms(start),
            raw=completion.model_dump() if hasattr(completion, "model_dump") else None,
        )

    def txt2img(self, request: ImageRequest) -> ImageResult:
        # 多数 chat 多模态模型支持纯文本，但语义不直接——MVP 暂不实现，留 raise
        raise ImageGenError(
            f"{self.name} provider does not implement txt2img in MVP",
            provider=self.name, model_id=self.cfg.model_id,
        )

    def _extract_image_b64(self, message) -> str | None:
        """从 chat 响应 message 中提取 base64 图片字符串。

        查找顺序：
          1. message.images (OpenRouter multimodal 格式)
          2. message.content 列表中的 image_url 内容块 (OpenAI multimodal 格式)
        """
        # 1. message.images
        images = getattr(message, "images", None) or []
        for img in images:
            url = None
            if isinstance(img, dict):
                inner = img.get("image_url")
                if isinstance(inner, dict):
                    url = inner.get("url")
                elif isinstance(inner, str):
                    url = inner
            else:
                inner = getattr(img, "image_url", None)
                url = getattr(inner, "url", None) if inner is not None else None
            if url:
                # data: URL 直接解 b64；远程 URL 走 decode_or_download 后再 b64
                if url.startswith("data:"):
                    return url.split(",", 1)[1]
                return base64.b64encode(decode_or_download(url)).decode()

        # 2. content 列表
        content = getattr(message, "content", None)
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                if part.get("type") != "image_url":
                    continue
                inner = part.get("image_url")
                url = inner.get("url") if isinstance(inner, dict) else None
                if url:
                    if url.startswith("data:"):
                        return url.split(",", 1)[1]
                    return base64.b64encode(decode_or_download(url)).decode()

        return None
