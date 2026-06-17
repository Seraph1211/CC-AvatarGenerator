"""MiniMax 自定义协议 provider——非 OpenAI 兼容，走原生 httpx。

协议特征：
  - POST {base_url}/v1/image_generation
  - subject_reference: [{type:character, image_file:data:image/png;base64,...}]
  - response_format: base64
  - 可选 style: {style_type, style_weight}
  - 响应：{base_resp:{status_code, status_msg}, data:{image_base64:[...]}}
"""
import base64
import time
from typing import ClassVar

import httpx

from .base import (
    ImageGenError, ImageProvider, ImageRequest, ImageResult, _now_ms,
)


class MiniMaxProvider(ImageProvider):
    """MiniMax image-01 / image-01-live 协议实现。"""

    name: ClassVar[str] = "minimax"

    def img2img(self, request: ImageRequest) -> ImageResult:
        if not request.image:
            raise ImageGenError(
                "img2img requires request.image",
                provider=self.name, model_id=self.cfg.model_id,
            )
        image_b64 = base64.b64encode(request.image).decode()
        payload = {
            "model": self.cfg.model_id,
            "prompt": request.prompt,
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "n": 1,
            "aigc_watermark": False,
            "subject_reference": [
                {
                    "type": "character",
                    "image_file": f"data:image/png;base64,{image_b64}",
                }
            ],
        }
        style = getattr(self.cfg, "style", None)
        if style:
            payload["style"] = style

        # 请求级 params 可以覆盖 prompt/extra 字段
        defaults = getattr(self.cfg, "img2img_defaults", {}) or {}
        payload.update({**defaults, **request.params})

        endpoint = f"{self.cfg.base_url.rstrip('/')}/v1/image_generation"
        client = httpx.Client(timeout=120)
        start = time.time()
        try:
            response = client.post(
                endpoint,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
        except Exception as e:
            raise ImageGenError(
                f"MiniMax request failed: {e}",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            ) from e

        if response.status_code != 200:
            raise ImageGenError(
                f"MiniMax HTTP {response.status_code}: {response.text[:500]}",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            )

        data = response.json()
        base_resp = data.get("base_resp", {})
        if base_resp.get("status_code", -1) != 0:
            raise ImageGenError(
                f"MiniMax error {base_resp.get('status_code')}: "
                f"{base_resp.get('status_msg', 'unknown')}",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            )

        images = (data.get("data") or {}).get("image_base64", [])
        if not images:
            raise ImageGenError(
                "MiniMax response missing image_base64",
                provider=self.name, model_id=self.cfg.model_id, platform=self.cfg.platform,
            )
        return ImageResult(
            image_bytes=base64.b64decode(images[0]),
            provider=self.name,
            model_id=self.cfg.model_id,
            platform=self.cfg.platform,
            latency_ms=_now_ms(start),
            raw=data,
        )

    def txt2img(self, request: ImageRequest) -> ImageResult:
        # MiniMax 协议中 subject_reference 是核心图生图能力；文生图走不同参数。
        # MVP 暂不实现——现有生产只用了图生图，文生图不在 MVP 范围。
        raise ImageGenError(
            f"{self.name} provider does not implement txt2img in MVP",
            provider=self.name, model_id=self.cfg.model_id,
        )
