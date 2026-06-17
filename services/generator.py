"""Avatar generation service.

高阶入口:preprocess → provider → quality gate → 统一返回 dict。

Provider 实现全部在 services/providers/ 包,本文件只负责:
  1. 组装流水线
  2. 业务级兜底(OpenRouter ToS 403 → MiniMax image-01-live)
  3. 兼容老 API 响应格式({"image_base64", "model_used", "duration_ms"})
"""
import json
import time

from config import ACTIVE_MODEL, get_model
from services.preprocessor import preprocess_image
from services.providers import (
    ImageRequest,
    ImageResult,
    OpenRouterToSError,
    make_provider,
)
from services import quality_checker
from utils.logger import logger

DEBUG_LOG_PATH = "/Users/seraph/GitHouse/CC-AvatarGenerator/.cursor/debug-c32fda.log"


# 内部调试日志——将结构化事件写入 .cursor/debug-*.log,用于事后回溯 provider / 兜底流程。
def _dbg(run_id: str, hypothesis_id: str, location: str, message: str, data: dict | None = None) -> None:
    payload = {
        "sessionId": "c32fda",
        "runId": run_id,
        "hypothesisId": hypothesis_id,
        "location": location,
        "message": message,
        "data": data or {},
        "timestamp": int(time.time() * 1000),
    }
    with open(DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


# 从磁盘读取 prompt 模板文件,返回去除首尾空白后的内容。
def load_prompt(prompt_file: str) -> str:
    """Load prompt template from file."""
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()


# ============================================================
# 公共入口
# ============================================================

# 兜底链:OpenRouter ToS 403 时回退到的目标模型
OPENROUTER_FALLBACK_KEY = "image-01-live"


def generate_avatar(image_bytes: bytes, model: str = None) -> dict:
    """Generate line-art avatar from photo.

    流水线:
      1. 解析 model key → ModelConfig
      2. 加载 prompt 模板
      3. 预处理图片(尺寸由 cfg.preprocess_max_dim 控制)
      4. 实例化 provider 并调用 img2img
      5. (OpenRouter) ToS 403 时回退到 image-01-live
      6. 质量门检查(失败抛 QualityCheckFailedError)
      7. 返回统一 dict 格式

    Args:
        image_bytes: 上传图片的原始字节
        model: MODELS 注册表的 key(可空,空则用 ACTIVE_MODEL)

    Returns:
        dict: {image_base64, model_used, duration_ms}
            - image_base64: PNG base64 字符串(无 data: 前缀)
            - model_used: 实际使用的模型 key(发生兜底时为 "原key -> 兜底key")
            - duration_ms: 端到端耗时
    """
    model_key = model or ACTIVE_MODEL
    cfg = get_model(model_key)

    prompt = load_prompt(cfg.prompt_file)
    preprocessed = preprocess_image(image_bytes, max_dim=cfg.preprocess_max_dim)

    logger.info(
        f"[generate] start | model_key={model_key} | platform={cfg.platform} | "
        f"provider={cfg.provider} | max_dim={cfg.preprocess_max_dim}"
    )
    start = time.time()

    req = ImageRequest(prompt=prompt, image=preprocessed)
    provider = make_provider(cfg)

    try:
        result = provider.img2img(req)
    except OpenRouterToSError as e:
        # OpenRouter 上游 provider 以 ToS 拒绝,自动回退到 image-01-live
        logger.warning(f"[generate] OpenRouter ToS blocked, fallback to {OPENROUTER_FALLBACK_KEY}: {e}")
        _dbg(
            "openrouter-post-fix",
            "H5",
            "generator.py:generate_avatar:fallback",
            "openrouter blocked, fallback to minimax",
            {
                "requested_model_key": model_key,
                "fallback_model_key": OPENROUTER_FALLBACK_KEY,
            },
        )
        fallback_cfg = get_model(OPENROUTER_FALLBACK_KEY)
        fallback_provider = make_provider(fallback_cfg)
        result = fallback_provider.img2img(req)
        model_key = f"{model_key} -> {OPENROUTER_FALLBACK_KEY}"

    if not quality_checker.passes(result):
        raise RuntimeError(
            f"Quality check failed for {result.provider}/{result.model_id} "
            f"(platform={result.platform}, latency={result.latency_ms}ms). "
            f"Result discarded."
        )

    duration_ms = int((time.time() - start) * 1000)
    logger.info(
        f"[generate] done | model_key={model_key} | "
        f"latency={result.latency_ms}ms | total={duration_ms}ms"
    )

    return {
        "image_base64": result.to_base64(),
        "model_used": model_key,
        "duration_ms": duration_ms,
    }
