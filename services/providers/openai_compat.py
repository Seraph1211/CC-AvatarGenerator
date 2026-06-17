"""OpenAI Images API 协议 provider。

覆盖:PackyAPI、OpenAI 官方、Requesty、绝大多数 OpenAI-compat 中转平台。
本类只关心 wire 协议(/v1/images/generations + /v1/images/edits),
具体平台(URL、token)由 model_config 注入。
"""
import base64
import time
from openai import OpenAI
import httpx

from .base import ImageProvider, ImageRequest, ImageResult, ModelNotFoundError


class OpenAICompatProvider(ImageProvider):
    """OpenAI Images API 协议实现。"""
    name = "openai_compat"

    def _client(self) -> OpenAI:
        return OpenAI(
            api_key=self.api_key,
            base_url=self.cfg.base_url,
            timeout=300,
        )

    def img2img(self, request: ImageRequest) -> ImageResult:
        if not request.image:
            raise ValueError("img2img requires request.image to be set")
        defaults = self.cfg.img2img_defaults
        kwargs = {**defaults, **request.params}

        start = time.time()
        try:
            response = self._client().images.edit(
                model=self.cfg.model_id,
                image=("photo.png", request.image, "image/png"),
                prompt=request.prompt,
                **kwargs,
            )
        except Exception as e:
            self._translate_error(e)

        return self._extract_result(response, start)

    def txt2img(self, request: ImageRequest) -> ImageResult:
        defaults = self.cfg.txt2img_defaults
        kwargs = {**defaults, **request.params}

        start = time.time()
        try:
            response = self._client().images.generate(
                model=self.cfg.model_id,
                prompt=request.prompt,
                **kwargs,
            )
        except Exception as e:
            self._translate_error(e)

        return self._extract_result(response, start)

    def _extract_result(self, response, start: float) -> ImageResult:
        item = response.data[0]
        if item.url:
            img_b64 = self._download_as_b64(item.url)
        elif item.b64_json:
            img_b64 = item.b64_json
        else:
            raise RuntimeError(
                f"{self.cfg.display_name} response missing both url and b64_json"
            )
        return ImageResult(
            image_bytes=base64.b64decode(img_b64),
            provider=self.name,
            model_id=self.cfg.model_id,
            platform=self.cfg.platform,
            latency_ms=int((time.time() - start) * 1000),
            raw=response.model_dump() if hasattr(response, "model_dump") else None,
        )

    @staticmethod
    def _download_as_b64(url: str) -> str:
        """下载远程图片 URL 并返回 base64 字符串(不含 data: 前缀)。"""
        resp = httpx.get(url, timeout=60)
        resp.raise_for_status()
        return base64.b64encode(resp.content).decode()

    @staticmethod
    def _translate_error(e: Exception) -> None:
        """把 SDK 异常统一翻译为业务异常,带上可识别的错误类型。"""
        msg = str(e)
        if "model not found" in msg.lower():
            raise ModelNotFoundError(
                f"模型未识别,请检查 token 分组是否开通该模型。原始错误: {msg}"
            ) from e
        raise
