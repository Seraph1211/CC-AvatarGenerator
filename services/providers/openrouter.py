"""OpenRouter 专用 provider。

OpenRouter 在 OpenAI Chat Completions 基础上加了:
  1. 必传的特殊请求头(HTTP-Referer / X-Title)
  2. modalities=image 的 extra_body 开启图片生成
  3. 触犯上游 provider ToS 时返回 403,需要被上层识别并触发兜底
"""
from openai import OpenAI

from .chat_completions import ChatCompletionsProvider, _extract_image_from_chat_message
from .base import ImageRequest, ImageResult, ImageGenError


class OpenRouterToSError(ImageGenError):
    """OpenRouter 上游 provider 以 ToS 拒绝图像生成(403)。
    调用方应识别此异常并切换到兜底模型(目前是 image-01-live)。"""


class OpenRouterProvider(ChatCompletionsProvider):
    """OpenRouter 图像模型 provider,继承 ChatCompletionsProvider 复用图片抽取逻辑。"""
    name = "openrouter"

    def _client(self) -> OpenAI:
        return OpenAI(
            api_key=self.api_key,
            base_url=self.cfg.base_url,
            default_headers={
                "HTTP-Referer": "https://github.com/Seraph1211/CC-AvatarGenerator",
                "X-Title": "CC-AvatarGenerator",
            },
            timeout=300,
        )

    def _chat_generate(self, request: ImageRequest) -> ImageResult:
        """覆盖父类实现,加入 modalities=image 强制开启图生成。"""
        import base64
        import time

        messages = self._build_messages(request) if request.image else [
            {"role": "user", "content": request.prompt}
        ]

        start = time.time()
        try:
            completion = self._client().chat.completions.create(
                model=self.cfg.model_id,
                messages=messages,
                extra_body={"modalities": ["image", "text"]},
            )
        except Exception as e:
            # OpenRouter 上游 provider 经常以 403 + "Terms Of Service" 拒绝图生成
            text = str(e)
            if "Terms Of Service" in text or "403" in text:
                raise OpenRouterToSError(
                    "OpenRouter blocked this image request with provider Terms Of Service (403). "
                    "This is an account/provider policy restriction, not a request format issue. "
                    "Switch to image-01 / image-01-live as fallback."
                ) from e
            raise

        message = completion.choices[0].message
        img_b64 = _extract_image_from_chat_message(message)
        if not img_b64:
            raise ImageGenError(
                f"OpenRouter response did not include an image: "
                f"{message.model_dump() if hasattr(message, 'model_dump') else message}"
            )

        return ImageResult(
            image_bytes=base64.b64decode(img_b64),
            provider=self.name,
            model_id=self.cfg.model_id,
            platform=self.cfg.platform,
            latency_ms=int((time.time() - start) * 1000),
            raw=completion.model_dump() if hasattr(completion, "model_dump") else None,
        )
