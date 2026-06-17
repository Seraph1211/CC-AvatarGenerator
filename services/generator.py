"""Avatar generation service — high-level orchestrator.

调用链：load_prompt → preprocess → make_provider → img2img → quality_check。
每个环节都是协议无关的，单一职责，便于扩展和测试。
"""
import json
import time
import traceback
import uuid

from config import ACTIVE_MODEL, get_model
from services.preprocessor import preprocess_image
from services.providers import make_provider
from services.providers.base import ImageGenError, ImageRequest, ImageResult
from services.providers.openrouter import OpenRouterToSError
from services.quality_checker import passes as quality_passes
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


def generate_avatar(
    image_bytes: bytes,
    model_key: str | None = None,
    request_id: str | None = None,
) -> ImageResult:
    """统一入口：preprocess → provider.img2img → quality gate。

    Args:
        image_bytes: 上传的图片原始字节
        model_key: 注册表 key（默认 ACTIVE_MODEL）
        request_id: 关联 ID（默认自动生成 8 字符），用于日志串联一次请求的所有步骤

    Returns:
        ImageResult，包含 image_bytes / model_key / latency_ms / platform 等元信息

    Raises:
        ImageGenError: provider 调用失败或质量门未通过
        OpenRouterToSError: 已捕获并兜底，不应冒泡
    """
    rid = request_id or uuid.uuid4().hex[:8]
    key = model_key or ACTIVE_MODEL
    cfg = get_model(key)
    t_start = time.time()

    logger.info(
        f"[{rid}] request.start | model_key={key} | provider={cfg.provider} | "
        f"platform={cfg.platform} | file_size_in={len(image_bytes)} | "
        f"preprocess_dim={cfg.preprocess_max_dim} | prompt_file={cfg.prompt_file}"
    )

    # 1. 加载 prompt
    t1 = time.time()
    prompt = load_prompt(cfg.prompt_file)
    logger.info(f"[{rid}] prompt.loaded | file={cfg.prompt_file} | len={len(prompt)} | dur={_ms(t1)}ms")

    # 2. 预处理
    t2 = time.time()
    preprocessed = preprocess_image(image_bytes, max_dim=cfg.preprocess_max_dim)
    logger.info(
        f"[{rid}] preprocess.done | in={len(image_bytes)}B → out={len(preprocessed)}B | "
        f"target_dim={cfg.preprocess_max_dim} | dur={_ms(t2)}ms"
    )

    # 3. 构造 provider + 发送请求
    provider = make_provider(cfg)
    request = ImageRequest(prompt=prompt, image=preprocessed)

    t3 = time.time()
    try:
        result = provider.img2img(request)
    except OpenRouterToSError as e:
        # OpenRouter 服务端 ToS 拦截——按业务规则兜底到 image-01-live
        _dbg(
            rid, "H5", "generator.py:generate_avatar:fallback",
            "openrouter blocked by ToS, fallback to image-01-live",
            {"requested_model": key},
        )
        logger.warning(f"[{rid}] fallback.trigger | reason=openrouter_tos | {key} → image-01-live")
        fallback = get_model("image-01-live")
        fallback_provider = make_provider(fallback)
        t_fb = time.time()
        result = fallback_provider.img2img(request)
        logger.info(
            f"[{rid}] fallback.request.done | model=image-01-live | "
            f"latency={result.latency_ms}ms | dur_total={_ms(t_fb)}ms"
        )
        result.model_key = f"{key} -> image-01-live"
        result.model_id = fallback.model_id
    except ImageGenError as e:
        logger.error(
            f"[{rid}] provider.error | type=ImageGenError | provider={e.provider} | "
            f"model_id={e.model_id} | platform={e.platform} | msg={e} | dur={_ms(t3)}ms"
        )
        raise
    except Exception as e:
        logger.error(
            f"[{rid}] request.error | type={type(e).__name__} | msg={e} | dur={_ms(t3)}ms\n"
            f"{traceback.format_exc()}"
        )
        raise ImageGenError(
            f"Unexpected error: {e}",
            provider=cfg.provider, model_id=cfg.model_id, platform=cfg.platform,
        ) from e

    logger.info(
        f"[{rid}] provider.done | provider={result.provider} | model_id={result.model_id} | "
        f"latency={result.latency_ms}ms | bytes={len(result.image_bytes)} | dur={_ms(t3)}ms"
    )

    # 设置 model_key 供上层使用
    if not result.model_key:
        result.model_key = key

    # 4. 质量门
    t4 = time.time()
    qc_ok = quality_passes(result.image_bytes)
    logger.info(f"[{rid}] quality_check.done | passed={qc_ok} | dur={_ms(t4)}ms")
    if not qc_ok:
        raise ImageGenError(
            "Generated image failed quality check",
            provider=result.provider, model_id=result.model_id, platform=result.platform,
        )

    logger.info(
        f"[{rid}] request.success | model_key={result.model_key} | "
        f"provider_latency={result.latency_ms}ms | total_dur={_ms(t_start)}ms | "
        f"bytes={len(result.image_bytes)}"
    )
    return result


def _ms(start: float) -> int:
    """毫秒差，结构化日志用。"""
    return int((time.time() - start) * 1000)
