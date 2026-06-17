"""Provider 抽象基类 + 统一请求/响应类型。"""
import base64
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar

import httpx


class ImageGenError(RuntimeError):
    """Provider 调用的统一异常基类——子类可携带 provider/model/platform 元信息。"""

    def __init__(self, message: str, *, provider: str = "", model_id: str = "", platform: str = ""):
        super().__init__(message)
        self.provider = provider
        self.model_id = model_id
        self.platform = platform


@dataclass
class ImageRequest:
    """统一的图像生成请求。"""

    prompt: str
    image: bytes | None = None              # 图生图必填，文生图为 None
    params: dict = field(default_factory=dict)  # 调用方覆盖默认参数的透传字段


@dataclass
class ImageResult:
    """统一的图像生成结果——image_bytes 是所有 provider 出口的统一格式。"""

    image_bytes: bytes
    mime_type: str = "image/png"
    provider: str = ""                      # 协议名，如 "openai_compat"
    model_id: str = ""                      # 实际传给 API 的 model 字段
    model_key: str = ""                     # 注册表 key（兜底链用 "X -> Y" 格式），由 generator 填
    platform: str = ""                      # 平台归属，如 "PackyAPI"
    latency_ms: int = 0
    raw: dict | None = None                 # 原始响应（用于调试/监控）

    def to_base64(self) -> str:
        """前端 API 用：返回纯 base64 字符串（不含 data: 前缀）。"""
        return base64.b64encode(self.image_bytes).decode("ascii")


class ImageProvider(ABC):
    """图像生成 provider 抽象基类。

    一个 provider = 一个 wire 协议（OpenAI Images / OpenAI Chat / MiniMax native / ...）。
    同一协议下不同平台（PackyAPI / OpenAI 官方）的差异由 model_config.base_url
    和 api_key_env 体现，provider 类本身不感知。
    """

    name: ClassVar[str]  # 子类必须设置

    def __init__(self, model_config):
        self.cfg = model_config
        env = model_config.api_key_env
        self.api_key = __import__("os").getenv(env)
        if not self.api_key:
            raise ImageGenError(
                f"Missing API key env var: {env}",
                provider=self.name,
                model_id=model_config.model_id,
            )

    @abstractmethod
    def img2img(self, request: ImageRequest) -> ImageResult:
        """图生图：基于参考图 + prompt 生成图像。"""

    @abstractmethod
    def txt2img(self, request: ImageRequest) -> ImageResult:
        """文生图：仅基于 prompt 生成图像。"""


# ============================================================
# 公共工具——被多个 provider 复用
# ============================================================

def decode_or_download(url: str, timeout: int = 60) -> bytes:
    """将 data: URL 或远程 URL 解析为图片字节。

    用于部分 provider 返回 url（如 COS 链接）而客户端期望统一 image_bytes 的场景。
    """
    if url.startswith("data:"):
        # data:image/png;base64,xxxxx
        b64 = url.split(",", 1)[1]
        return base64.b64decode(b64)
    resp = httpx.get(url, timeout=timeout)
    resp.raise_for_status()
    return resp.content


def _now_ms(start: float) -> int:
    import time
    return int((time.time() - start) * 1000)
