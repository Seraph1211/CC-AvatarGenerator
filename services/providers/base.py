"""图像生成 provider 抽象基类 + 统一请求/响应类型。"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar, TYPE_CHECKING

if TYPE_CHECKING:
    pass  # 避免循环依赖,运行时不需要


@dataclass
class ModelConfig:
    """一个具体模型部署的完整配置。

    设计原则:provider 字段表示"协议"(走哪个 provider 类),platform +
    base_url + api_key_env 共同表示"平台"(请求发到哪个端点、用哪个 token)。
    同一协议下不同平台 = 不同 ModelConfig entry。

    Attributes:
        display_name: 展示用名称(前端 dropdown 显示)
        provider: 协议类名,对应 services/providers/PROVIDERS 注册表的 key
                  ("openai_compat" / "chat_completions" / "minimax" / "openrouter")
        model_id: 实际传给 API 的 model 字段(如 "gpt-image-2")
        base_url: provider API 根 URL(不包含 /images/edits 等路径)
        api_key_env: 存放 API key 的环境变量名
        platform: 平台归属("PackyAPI" / "OpenAI" / "Google" / "MiniMax" / "OpenRouter"),
                  用于前端按平台分组、监控打标
        prompt_file: 该模型使用的 prompt 模板文件路径
        preprocess_max_dim: 输入图片归一化边长(传给 preprocessor)
        txt2img_defaults: 文生图请求默认参数(覆盖到 provider 调用层)
        img2img_defaults: 图生图请求默认参数
        style: provider 特定扩展字段(MiniMax 的 style 字典等),由 provider 自己读取
        endpoint: provider 特定扩展字段(完整 endpoint URL,主要用于 MiniMax)
    """
    display_name: str
    provider: str
    model_id: str
    base_url: str
    api_key_env: str
    platform: str
    prompt_file: str = "prompts/line_art.txt"
    preprocess_max_dim: int = 1024
    txt2img_defaults: dict = field(default_factory=dict)
    img2img_defaults: dict = field(default_factory=dict)
    style: dict | None = None
    endpoint: str | None = None


@dataclass
class ImageRequest:
    """一次图像生成请求的统一表示。

    Attributes:
        prompt: 文本 prompt
        image: 源图字节（图生图必填，文生图为 None）
        params: 模型/调用级参数（size / quality / output_format / response_format / ...），
                由 provider 透传给底层 API。ModelConfig 的 *_defaults 是默认,
                ImageRequest.params 是调用级 override。
    """
    prompt: str
    image: bytes | None = None
    params: dict = field(default_factory=dict)


@dataclass
class ImageResult:
    """provider 统一返回结果。

    Attributes:
        image_bytes: 解码后的图片二进制（PNG 字节流，统一格式）
        mime_type: 图片 MIME（默认 image/png）
        provider: 协议名（"openai_compat" / "minimax" / ...），对应 PROVIDERS 注册表 key
        model_id: 实际传给 API 的 model 字段
        platform: 平台归属（"PackyAPI" / "OpenAI" / ...），用于监控/前端展示
        latency_ms: 本次调用耗时
        raw: 原始响应（dict 或 SDK 对象的 dump），用于调试/监控/回溯
    """
    image_bytes: bytes
    mime_type: str = "image/png"
    provider: str = ""
    model_id: str = ""
    platform: str = ""
    latency_ms: int = 0
    raw: dict | None = None

    def to_base64(self) -> str:
        """转为 base64 字符串(不含 data: 前缀),供前端 <img src> 使用。"""
        import base64
        return base64.b64encode(self.image_bytes).decode()


class ImageGenError(RuntimeError):
    """provider 调用失败的统一异常基类。"""


class AuthError(ImageGenError):
    """API key 缺失或无效。"""


class ModelNotFoundError(ImageGenError):
    """模型未识别（通常意味着 token 分组没开通该模型）。"""


class ImageProvider(ABC):
    """图像生成 provider 抽象基类。

    一个 provider = 一种 wire 协议（OpenAI Images / OpenAI Chat / MiniMax 原生 / ...）。
    同一协议下不同平台（PackyAPI / OpenAI 官方）的差异由 model_config.base_url
    和 api_key_env 体现,provider 类本身不感知具体平台。
    """
    name: ClassVar[str] = ""

    def __init__(self, model_config):
        self.cfg = model_config
        self.api_key = self._resolve_api_key()

    def _resolve_api_key(self) -> str:
        env_name = self.cfg.api_key_env
        import os
        key = os.getenv(env_name)
        if not key:
            raise AuthError(
                f"Missing {env_name} in environment. "
                f"Set it in .env or export it before starting the server."
            )
        return key

    @abstractmethod
    def txt2img(self, request: ImageRequest) -> ImageResult:
        """文生图:prompt -> 一张图。"""

    @abstractmethod
    def img2img(self, request: ImageRequest) -> ImageResult:
        """图生图:prompt + source_image -> 一张图。request.image 必须提供。"""
