"""Avatar generation service."""
import base64
import io
import json
import time
import traceback

import httpx
from PIL import Image
from openai import OpenAI

from config import DEFAULT_MODEL, DEFAULT_PROMPT_FILE, get_api_key, resolve_model_config, MODELS
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


# 将上传的照片归一化为 1024×1024 RGBA PNG,保证所有 provider 看到一致的输入。
def preprocess_image(image_bytes: bytes) -> bytes:
    """Resize to 1024x1024 and convert to RGBA PNG."""
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img.thumbnail((1024, 1024), Image.LANCZOS)
    canvas = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
    offset = ((1024 - img.width) // 2, (1024 - img.height) // 2)
    canvas.paste(img, offset)
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()


# 根据 model_config 反查其在 MODELS 注册表中的短 key。
def _model_registry_key(model_config: dict) -> str:
    for key, cfg in MODELS.items():
        if cfg is model_config or cfg == model_config:
            return key
    for key, cfg in MODELS.items():
        if cfg["model"] == model_config["model"] and cfg["endpoint"] == model_config["endpoint"]:
            return key
    return model_config["model"]


# ============================================================
# OpenAI SDK adapter
# ============================================================
# Covers: openai, requesty, openrouter, packyapi.
# Providers not on the OpenAI wire format (minimax, falai) stay on httpx below.

_STRIP_SUFFIXES = ("/chat/completions", "/images/edits", "/images/generations")


# 剥离 endpoint 末尾的 /chat/completions、/images/edits 等后缀,得到 SDK 所需的 base_url。
def _resolve_base_url(endpoint: str, provider: str) -> str:
    """Reduce a full endpoint to the SDK's `base_url` (no /chat/... or /images/... suffix)."""
    for suffix in _STRIP_SUFFIXES:
        if endpoint.endswith(suffix):
            return endpoint[: -len(suffix)]
    if provider == "openai":
        return "https://api.openai.com/v1"
    return endpoint


# 为 OpenAI 兼容 provider(openai / requesty / openrouter / packyapi)构建一个配置好的 SDK 客户端。
def _get_openai_client(model_config: dict) -> OpenAI:
    """Build an OpenAI SDK client for an OpenAI-compatible provider."""
    provider = model_config["provider"]
    api_key = get_api_key(provider)
    base_url = _resolve_base_url(model_config["endpoint"], provider)

    default_headers = None
    if provider == "openrouter":
        default_headers = {
            "HTTP-Referer": "https://github.com/Seraph1211/CC-AvatarGenerator",
            "X-Title": "CC-AvatarGenerator",
        }

    return OpenAI(
        api_key=api_key,
        base_url=base_url,
        default_headers=default_headers,
        timeout=300,
    )


# 从 chat 响应中提取 base64 图片,同时兼容 OpenAI 的 content 列表和 OpenRouter 的 message.images。
def _extract_image_from_chat_message(message) -> str | None:
    """Pull a base64 image string from an OpenAI-compatible chat message.

    Looks in:
      1. message.images (OpenRouter multimodal)
      2. message.content as a list of content parts (OpenAI multimodal)
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
            return _decode_or_download(url)

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
                return _decode_or_download(url)

    return None


# 将 data: URL 或远程 URL 解析为纯 base64 图片字符串(不含前缀)。
def _decode_or_download(url: str) -> str:
    """Convert a data: URL or remote URL into a base64 image string (no prefix)."""
    if url.startswith("data:"):
        return url.split(",", 1)[1]
    resp = httpx.get(url, timeout=60)
    resp.raise_for_status()
    return base64.b64encode(resp.content).decode()


# ============================================================
# Public dispatcher
# ============================================================

# 公共入口——预处理照片,路由到对应 provider 适配器,返回 base64 头像。
def generate_avatar(image_bytes: bytes, model: str = None) -> dict:
    """Generate line-art avatar from photo.

    Returns:
        dict: {image_base64, model_used, duration_ms}
    """
    model_key = model or DEFAULT_MODEL
    model_config = resolve_model_config(model_key)
    prompt_file = model_config.get("prompt_file", DEFAULT_PROMPT_FILE)
    prompt = load_prompt(prompt_file)
    preprocessed = preprocess_image(image_bytes)

    provider = model_config["provider"]

    if provider == "minimax":
        return _generate_minimax(preprocessed, prompt, model_config)
    if provider == "falai":
        return _generate_falai(preprocessed, prompt)
    if provider in ("openai", "requesty") and model_config["endpoint"].endswith("/images/edits"):
        return _generate_openai_image_edit(preprocessed, prompt, model_config)
    if provider in ("requesty", "openai") and model_config["endpoint"].endswith("/chat/completions"):
        return _generate_chat_completion(preprocessed, prompt, model_config)
    if provider == "packyapi":
        return _generate_packyapi(preprocessed, prompt, model_config)
    if provider == "openrouter":
        try:
            return _generate_openrouter(preprocessed, prompt, model_config)
        except RuntimeError as e:
            err_text = str(e)
            if "Terms Of Service (403)" in err_text or "provider Terms Of Service" in err_text:
                fallback_config = MODELS.get("image-01-live") or MODELS.get("image-01")
                if not fallback_config:
                    raise
                _dbg(
                    "openrouter-post-fix",
                    "H5",
                    "generator.py:generate_avatar:fallback",
                    "openrouter blocked, fallback to minimax",
                    {
                        "requested_model": model_config.get("model"),
                        "fallback_model": fallback_config.get("model"),
                    },
                )
                result = _generate_minimax(preprocessed, prompt, fallback_config)
                result["model_used"] = (
                    f"{_model_registry_key(model_config)} -> "
                    f"{_model_registry_key(fallback_config)}"
                )
                return result
            raise

    raise ValueError(f"Unknown provider: {provider}")


# ============================================================
# OpenAI SDK paths
# ============================================================

# Provider 适配器:OpenAI / Requesty 的 images.edit(multipart 图片上传)。
def _generate_openai_image_edit(image_bytes: bytes, prompt: str, model_config: dict) -> dict:
    """OpenAI / Requesty: client.images.edit() — multipart image edit."""
    client = _get_openai_client(model_config)

    start = time.time()
    response = client.images.edit(
        model=model_config["model"],
        image=("photo.png", image_bytes, "image/png"),
        prompt=prompt,
        size="1024x1024",
    )
    duration_ms = int((time.time() - start) * 1000)

    img_b64 = response.data[0].b64_json
    if not img_b64:
        raise RuntimeError("images.edit returned no b64_json")
    return {
        "image_base64": img_b64,
        "model_used": _model_registry_key(model_config),
        "duration_ms": duration_ms,
    }


# Provider 适配器:OpenAI / Requesty 的 chat.completions,内联 image_url 内容块。
def _generate_chat_completion(image_bytes: bytes, prompt: str, model_config: dict) -> dict:
    """OpenAI / Requesty: client.chat.completions.create() with image_url content part."""
    client = _get_openai_client(model_config)
    image_data_url = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"

    start = time.time()
    completion = client.chat.completions.create(
        model=model_config["model"],
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
    )
    duration_ms = int((time.time() - start) * 1000)

    message = completion.choices[0].message
    img_b64 = _extract_image_from_chat_message(message)
    if not img_b64:
        raise RuntimeError(
            f"Chat completion response did not include an image: {message.model_dump()}"
        )
    return {
        "image_base64": img_b64,
        "model_used": _model_registry_key(model_config),
        "duration_ms": duration_ms,
    }


# Provider 适配器:PackyAPI gpt-image-2——通过 OpenAI images.edit 调用,处理 url/b64 两种返回格式。
def _generate_packyapi(image_bytes: bytes, prompt: str, model_config: dict) -> dict:
    """PackyAPI gpt-image-2: client.images.edit() (multipart), response_format=url."""
    client = _get_openai_client(model_config)
    model = model_config["model"]
    logger.info(f"[PackyAPI] 开始生成 | model={model} | image_size={len(image_bytes)}")

    try:
        start = time.time()
        response = client.images.edit(
            model=model,
            image=("photo.png", image_bytes, "image/png"),
            prompt=prompt,
            size="1024x1024",
            quality="high",
            extra_body={"output_format": "png"},
        )
        duration_ms = int((time.time() - start) * 1000)
        logger.info(f"[PackyAPI] 完成 | duration={duration_ms / 1000:.1f}s")

        item = response.data[0]
        if item.url:
            logger.info(f"[PackyAPI] 下载图片: {item.url}")
            img_b64 = _decode_or_download(item.url)
        elif item.b64_json:
            img_b64 = item.b64_json
        else:
            raise RuntimeError("PackyAPI response missing both url and b64_json")

        return {
            "image_base64": img_b64,
            "model_used": _model_registry_key(model_config),
            "duration_ms": duration_ms,
        }
    except Exception as e:
        logger.error(f"[PackyAPI] 异常: {e}\n{traceback.format_exc()}")
        raise


# Provider 适配器:OpenRouter 图文多模态模型;遇 ToS 403 时抛错,由分发器兜底。
def _generate_openrouter(image_bytes: bytes, prompt: str, model_config: dict) -> dict:
    """OpenRouter image-capable models via client.chat.completions.create().

    OpenRouter exposes modalities via `extra_body`, and returns images in
    `message.images` (or in a content-part list). The 403 ToS fallback that
    used to live in httpx code is preserved: we re-raise the original error
    and let the dispatch caller in app.py switch to image-01-live.
    """
    client = _get_openai_client(model_config)

    _dbg(
        "openrouter-initial",
        "H1",
        "generator.py:_generate_openrouter:entry",
        "openrouter request start",
        {
            "endpoint": model_config.get("endpoint"),
            "model": model_config.get("model"),
            "prompt_len": len(prompt),
            "image_bytes_len": len(image_bytes),
        },
    )

    image_data_url = f"data:image/png;base64,{base64.b64encode(image_bytes).decode()}"

    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=model_config["model"],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_data_url}},
                    ],
                }
            ],
            extra_body={"modalities": ["image", "text"]},
        )
        duration_ms = int((time.time() - start) * 1000)
    except Exception as e:
        # Catch OpenRouter's Terms Of Service block at the SDK layer and surface
        # the same hint the previous httpx path produced.
        text = str(e)
        if "Terms Of Service" in text or "403" in text:
            _dbg(
                "openrouter-post-fix",
                "H2",
                "generator.py:_generate_openrouter:tos403",
                "openrouter provider ToS block detected",
                {"error": text[:300]},
            )
            raise RuntimeError(
                "OpenRouter blocked this image request with provider Terms Of Service (403). "
                "This is an account/provider policy restriction, not a request format issue. "
                "Please check OpenRouter provider permissions/billing, or switch to image-01 / image-01-live."
            ) from e
        raise

    _dbg(
        "openrouter-initial",
        "H2",
        "generator.py:_generate_openrouter:response",
        "openrouter raw response received",
        {"model": model_config.get("model")},
    )

    message = completion.choices[0].message
    img_b64 = _extract_image_from_chat_message(message)
    if not img_b64:
        _dbg(
            "openrouter-initial",
            "H5",
            "generator.py:_generate_openrouter:noimage",
            "no image found in openrouter response",
            {"response_excerpt": str(message.model_dump())[:400]},
        )
        raise RuntimeError(
            f"OpenRouter response did not include an image: {message.model_dump()}"
        )

    return {
        "image_base64": img_b64,
        "model_used": _model_registry_key(model_config),
        "duration_ms": duration_ms,
    }


# ============================================================
# Non-OpenAI-SDK paths (custom wire format)
# ============================================================

# Provider 适配器:MiniMax image_generation——非 OpenAI 协议,使用原生 httpx + subject_reference。
def _generate_minimax(image_bytes: bytes, prompt: str, model_config: dict) -> dict:
    """Generate using MiniMax image-01 / image-01-live subject_reference (i2i).

    MiniMax's image_generation endpoint is NOT OpenAI-compatible (custom
    subject_reference / style fields), so it stays on raw httpx.
    """
    api_key = get_api_key("minimax")
    image_b64 = base64.b64encode(image_bytes).decode()

    payload = {
        "model": model_config["model"],
        "prompt": prompt,
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

    if "style" in model_config:
        payload["style"] = model_config["style"]

    client = httpx.Client(timeout=120)
    response = client.post(
        model_config["endpoint"],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"MiniMax API error: {response.status_code} {response.text}"
        )

    data = response.json()
    base_resp = data.get("base_resp", {})
    if base_resp.get("status_code", -1) != 0:
        raise RuntimeError(
            f"MiniMax API error {base_resp.get('status_code')}: "
            f"{base_resp.get('status_msg', 'unknown error')}"
        )

    images = data.get("data", {}).get("image_base64", [])
    if not images:
        raise RuntimeError("MiniMax API response did not include an image")

    return {
        "image_base64": images[0],
        "model_used": _model_registry_key(model_config),
        "duration_ms": int(response.elapsed.total_seconds() * 1000),
    }


# Provider 适配器:fal.ai Flux Schnell——async 上传+队列轮询,使用原生 httpx。
def _generate_falai(image_bytes: bytes, prompt: str) -> dict:
    """Generate using fal.ai Flux Schnell.

    fal.ai's async-queue API is not OpenAI-compatible, so it stays on httpx.
    """
    api_key = get_api_key("falai")
    model_config = MODELS.get("fal-flux-schnell")
    if not model_config:
        raise ValueError("fal-flux-schnell is not configured in MODELS")

    client = httpx.Client(timeout=60)

    files = {"file": ("image.png", image_bytes, "image/png")}
    upload_resp = client.post(
        "https://storage.fal.services/uploads",
        files=files,
        headers={"Authorization": f"Key {api_key}"},
    )
    if upload_resp.status_code != 200:
        raise RuntimeError(f"fal.ai upload error: {upload_resp.status_code}")

    image_url = upload_resp.json()["url"]

    queue_resp = client.post(
        model_config["endpoint"],
        json={
            "prompt": prompt,
            "image_url": image_url,
        },
        headers={"Authorization": f"Key {api_key}"},
    )

    if queue_resp.status_code != 200:
        raise RuntimeError(f"fal.ai queue error: {queue_resp.status_code}")

    result_url = queue_resp.json()["response_url"]

    for _ in range(30):
        result_resp = client.get(result_url)
        if result_resp.status_code == 200:
            result_data = result_resp.json()
            if result_data.get("status") == "COMPLETED":
                img_url = result_data["images"][0]["url"]
                img_b64 = _decode_or_download(img_url)
                return {
                    "image_base64": img_b64,
                    "model_used": "fal-flux-schnell",
                    "duration_ms": int(result_resp.elapsed.total_seconds() * 1000),
                }
        time.sleep(1)

    raise RuntimeError("fal.ai generation timeout")
