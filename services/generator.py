"""Avatar generation service."""
import base64
import io
import time

from PIL import Image

from config import DEFAULT_MODEL, DEFAULT_PROMPT_FILE, get_api_key, resolve_model_config, MODELS


def load_prompt(prompt_file: str) -> str:
    """Load prompt template from file."""
    with open(prompt_file, "r", encoding="utf-8") as f:
        return f.read().strip()


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


def _model_registry_key(model_config: dict) -> str:
    for key, cfg in MODELS.items():
        if cfg is model_config or cfg == model_config:
            return key
    for key, cfg in MODELS.items():
        if cfg["model"] == model_config["model"] and cfg["endpoint"] == model_config["endpoint"]:
            return key
    return model_config["model"]


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
    endpoint = model_config["endpoint"]

    if provider == "minimax":
        result = _generate_minimax(preprocessed, prompt, model_config)
    elif provider in ("openai", "requesty") and endpoint.endswith("/images/edits"):
        result = _generate_image_edit(preprocessed, prompt, model_config)
    elif provider == "requesty" and endpoint.endswith("/chat/completions"):
        result = _generate_requesty_chat(preprocessed, prompt, model_config)
    elif provider == "falai":
        result = _generate_falai(preprocessed, prompt)
    else:
        raise ValueError(f"Unknown provider: {provider}")

    return result


def _generate_minimax(image_bytes: bytes, prompt: str, model_config: dict) -> dict:
    """Generate using MiniMax image-01 subject_reference (i2i)."""
    import httpx

    api_key = get_api_key("minimax")
    image_b64 = base64.b64encode(image_bytes).decode()

    client = httpx.Client(timeout=120)
    response = client.post(
        model_config["endpoint"],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
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
        },
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
        "duration_ms": response.elapsed.total_seconds() * 1000,
    }


def _generate_image_edit(image_bytes: bytes, prompt: str, model_config: dict) -> dict:
    """Generate using OpenAI-compatible images/edits (Requesty or OpenAI)."""
    import httpx

    api_key = get_api_key(model_config["provider"])
    image_b64 = base64.b64encode(image_bytes).decode()

    client = httpx.Client(timeout=120)
    response = client.post(
        model_config["endpoint"],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_config["model"],
            "image": image_b64,
            "prompt": prompt,
            "size": "1024x1024",
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Image edit API error: {response.status_code} {response.text}"
        )

    data = response.json()
    img_b64 = data["data"][0]["b64_json"]
    return {
        "image_base64": img_b64,
        "model_used": _model_registry_key(model_config),
        "duration_ms": response.elapsed.total_seconds() * 1000,
    }


def _generate_requesty_chat(image_bytes: bytes, prompt: str, model_config: dict) -> dict:
    """Generate using Requesty chat/completions (e.g. Gemini image models)."""
    import httpx

    api_key = get_api_key("requesty")
    image_b64 = base64.b64encode(image_bytes).decode()

    client = httpx.Client(timeout=120)
    response = client.post(
        model_config["endpoint"],
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model_config["model"],
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                            },
                        },
                    ],
                }
            ],
        },
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"Chat API error: {response.status_code} {response.text}"
        )

    data = response.json()
    message = data["choices"][0]["message"]
    content = message.get("content")

    if isinstance(content, list):
        for part in content:
            if part.get("type") == "image_url":
                url = part["image_url"]["url"]
                if url.startswith("data:"):
                    img_b64 = url.split(",", 1)[1]
                else:
                    img_resp = client.get(url)
                    img_b64 = base64.b64encode(img_resp.content).decode()
                return {
                    "image_base64": img_b64,
                    "model_used": _model_registry_key(model_config),
                    "duration_ms": response.elapsed.total_seconds() * 1000,
                }

    raise RuntimeError("Chat API response did not include an image")


def _generate_falai(image_bytes: bytes, prompt: str) -> dict:
    """Generate using fal.ai Flux Schnell."""
    import httpx

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
                img_resp = client.get(img_url)
                img_b64 = base64.b64encode(img_resp.content).decode()
                return {
                    "image_base64": img_b64,
                    "model_used": "fal-flux-schnell",
                    "duration_ms": result_resp.elapsed.total_seconds() * 1000,
                }
        time.sleep(1)

    raise RuntimeError("fal.ai generation timeout")
