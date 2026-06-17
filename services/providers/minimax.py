"""MiniMax image_generation 协议 provider。

MiniMax 的 image_generation 不是 OpenAI 兼容,使用自定义的
subject_reference / style 字段,所以独立实现,走裸 httpx。
"""
import base64
import httpx

from .base import ImageProvider, ImageRequest, ImageResult, ImageGenError


class MiniMaxProvider(ImageProvider):
    """MiniMax image_generation 端点实现。"""
    name = "minimax"

    def img2img(self, request: ImageRequest) -> ImageResult:
        if not request.image:
            raise ValueError("img2img requires request.image to be set")
        return self._generate(request)

    def txt2img(self, request: ImageRequest) -> ImageResult:
        return self._generate(request)

    def _generate(self, request: ImageRequest) -> ImageResult:
        image_b64 = base64.b64encode(request.image).decode() if request.image else None

        payload = {
            "model": self.cfg.model_id,
            "prompt": request.prompt,
            "aspect_ratio": "1:1",
            "response_format": "base64",
            "n": 1,
            "aigc_watermark": False,
        }
        if image_b64:
            payload["subject_reference"] = [
                {
                    "type": "character",
                    "image_file": f"data:image/png;base64,{image_b64}",
                }
            ]
        # MiniMax style 字段(可选)由 model_config.style 注入
        if self.cfg.style:
            payload["style"] = self.cfg.style

        # 允许 request.params 覆盖 payload 字段
        payload.update(request.params)

        endpoint = self.cfg.endpoint or f"{self.cfg.base_url}/v1/image_generation"

        client = httpx.Client(timeout=120)
        resp = client.post(
            endpoint,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if resp.status_code != 200:
            raise ImageGenError(
                f"MiniMax API error: {resp.status_code} {resp.text[:500]}"
            )

        data = resp.json()
        base_resp = data.get("base_resp", {})
        if base_resp.get("status_code", -1) != 0:
            raise ImageGenError(
                f"MiniMax API error {base_resp.get('status_code')}: "
                f"{base_resp.get('status_msg', 'unknown error')}"
            )

        images = data.get("data", {}).get("image_base64", [])
        if not images:
            raise ImageGenError("MiniMax API response did not include an image")

        return ImageResult(
            image_bytes=base64.b64decode(images[0]),
            provider=self.name,
            model_id=self.cfg.model_id,
            platform=self.cfg.platform,
            latency_ms=int(resp.elapsed.total_seconds() * 1000),
            raw=data,
        )
