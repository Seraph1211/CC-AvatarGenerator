"""OpenAI Chat Completions 多模态协议 provider。

走 /v1/chat/completions,把图片以 image_url content part 形式内联进消息。
覆盖:OpenAI 官方多模态模型、Requesty 多模态模型等。
OpenRouter 单独走 openrouter.py(它有特殊的 headers / modalities / ToS 处理)。
"""
import base64
import time
from openai import OpenAI

from .base import ImageProvider, ImageRequest, ImageResult, ModelNotFoundError


def _extract_image_from_chat_message(message) -> str | None:
    """从 OpenAI 兼容的 chat 响应 message 中抽取 base64 图片字符串。

    兼容两种结构:
      1. message.images (OpenRouter 风格)
      2. message.content 为 content-part 列表,type="image_url" (OpenAI 多模态)
    """
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
            return _data_url_to_b64(url) if url.startswith("data:") else _download_url_as_b64(url)

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
                return _data_url_to_b64(url) if url.startswith("data:") else _download_url_as_b64(url)

    return None


def _data_url_to_b64(url: str) -> str:
    return url.split(",", 1)[1]


def _download_url_as_b64(url: str) -> str:
    import httpx
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    return base64.b64encode(resp.content).decode()


class ChatCompletionsProvider(ImageProvider):
    """OpenAI Chat Completions 协议多模态实现。"""
    name = "chat_completions"

    def _client(self) -> OpenAI:
        return OpenAI(
            api_key=self.api_key,
            base_url=self.cfg.base_url,
            timeout=300,
        )

    def _build_messages(self, request: ImageRequest) -> list[dict]:
        """构造 messages:用户消息包含文本 prompt + image_url 内联图。"""
        if not request.image:
            raise ValueError("img2img requires request.image to be set")
        image_data_url = f"data:image/png;base64,{base64.b64encode(request.image).decode()}"
        return [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": request.prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ]

    def img2img(self, request: ImageRequest) -> ImageResult:
        return self._chat_generate(request)

    def txt2img(self, request: ImageRequest) -> ImageResult:
        # 纯文生图也走 chat 协议(部分多模态模型不支持纯文)
        request = ImageRequest(prompt=request.prompt, image=None, params=request.params)
        return self._chat_generate(request)

    def _chat_generate(self, request: ImageRequest) -> ImageResult:
        messages = self._build_messages(request) if request.image else [
            {"role": "user", "content": request.prompt}
        ]
        kwargs = {**self.cfg.img2img_defaults, **request.params}
        start = time.time()
        try:
            completion = self._client().chat.completions.create(
                model=self.cfg.model_id,
                messages=messages,
                **kwargs,
            )
        except Exception as e:
            self._translate_error(e)

        message = completion.choices[0].message
        img_b64 = _extract_image_from_chat_message(message)
        if not img_b64:
            raise RuntimeError(
                f"Chat completion response did not include an image: "
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

    @staticmethod
    def _translate_error(e: Exception) -> None:
        msg = str(e)
        if "model not found" in msg.lower():
            raise ModelNotFoundError(
                f"模型未识别,请检查 token 分组是否开通该模型。原始错误: {msg}"
            ) from e
        raise
