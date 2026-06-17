"""OpenAI Images API 协议 provider。

覆盖：OpenAI 官方、PackyAPI、Requesty、绝大多数 OpenAI 兼容中转。
endpoint：
  - POST /v1/images/generations  （文生图）
  - POST /v1/images/edits        （图生图，multipart）
响应支持 b64_json 和 url 两种格式——自动归一化为 image_bytes。
"""
import base64
import time
from typing import ClassVar

from openai import OpenAI

from .base import ImageGenError, ImageProvider, ImageRequest, ImageResult, _now_ms, decode_or_download


class OpenAICompatProvider(ImageProvider):
    """OpenAI Images API 协议实现。"""

    name: ClassVar[str] = "openai_compat"

    def _client(self) -> OpenAI:
        """构造 OpenAI SDK 客户端——同一 client 可复用多次调用。"""
        # 透传额外 default_headers（如 OpenRouter 需要的 HTTP-Referer）
        default_headers = None
        headers_attr = getattr(self.cfg, "default_headers", None)
        if headers_attr:
            default_headers = headers_attr

        return OpenAI(
            api_key=self.api_key,
            base_url=self.cfg.base_url,
            default_headers=default_headers,
            timeout=300,
        )

    # ------------------ 图生图 ------------------

    def img2img(self, request: ImageRequest) -> ImageResult:
        if not request.image:
            raise ImageGenError(
                "img2img requires request.image (bytes)",
                provider=self.name, model_id=self.cfg.model_id,
            )
        # 合并默认参数和请求级覆盖
        defaults = getattr(self.cfg, "img2img_defaults", {}) or {}
        kwargs = {**defaults, **request.params}
        # OpenAI SDK 不直接支持所有字段（如 output_format 走 extra_body）
        extra_body = kwargs.pop("extra_body", {})

        client = self._client()
        start = time.time()
        try:
            response = client.images.edit(
                model=self.cfg.model_id,
                image=("photo.png", request.image, "image/png"),
                prompt=request.prompt,
                **kwargs,
                extra_body=extra_body or None,
            )
        except Exception as e:
            raise ImageGenError(
                f"OpenAI images.edit failed: {e}",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            ) from e

        return self._extract_result(response, start)

    # ------------------ 文生图 ------------------

    def txt2img(self, request: ImageRequest) -> ImageResult:
        defaults = getattr(self.cfg, "txt2img_defaults", {}) or {}
        kwargs = {**defaults, **request.params}
        extra_body = kwargs.pop("extra_body", {})

        client = self._client()
        start = time.time()
        try:
            response = client.images.generate(
                model=self.cfg.model_id,
                prompt=request.prompt,
                **kwargs,
                extra_body=extra_body or None,
            )
        except Exception as e:
            raise ImageGenError(
                f"OpenAI images.generate failed: {e}",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            ) from e

        return self._extract_result(response, start)

    # ------------------ 响应解析 ------------------

    def _extract_result(self, response, start: float) -> ImageResult:
        """从 OpenAI SDK 响应中提取图片，自动处理 b64 / url 两种返回。"""
        if not response.data:
            raise ImageGenError(
                "OpenAI response has no data items",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            )

        item = response.data[0]
        if getattr(item, "b64_json", None):
            return ImageResult(
                image_bytes=base64.b64decode(item.b64_json),
                provider=self.name,
                model_id=self.cfg.model_id,
                platform=self.cfg.platform,
                latency_ms=_now_ms(start),
                raw=response.model_dump() if hasattr(response, "model_dump") else None,
            )
        if getattr(item, "url", None):
            try:
                img_bytes = decode_or_download(item.url)
            except Exception as e:
                raise ImageGenError(
                    f"Failed to download image from URL: {e}",
                    provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
                ) from e
            return ImageResult(
                image_bytes=img_bytes,
                provider=self.name,
                model_id=self.cfg.model_id,
                platform=self.cfg.platform,
                latency_ms=_now_ms(start),
                raw=response.model_dump() if hasattr(response, "model_dump") else None,
            )
        raise ImageGenError(
            "OpenAI response missing both b64_json and url",
            provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
        )
