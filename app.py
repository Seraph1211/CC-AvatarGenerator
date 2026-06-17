"""FastAPI entry point."""
import time
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import ACTIVE_MODEL, SHOW_MODEL_SELECT, get_visible_default, list_models
from services.generator import generate_avatar
from utils.logger import logger

app = FastAPI(title="CC-AvatarGenerator")

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def index():
    """Serve static index.html."""
    from fastapi.responses import FileResponse
    return FileResponse("static/index.html")


@app.get("/models")
def get_models():
    """List available models — 由前端 dropdown 动态读取。

    当 SHOW_MODEL_SELECT=False 时：返回 enabled=false + 空 models 列表，
    前端据此隐藏模型选择区，业务流程不出现任何模型信息。
    """
    return JSONResponse({
        "default": get_visible_default(),
        "enabled": SHOW_MODEL_SELECT,
        "models": list_models() if SHOW_MODEL_SELECT else [],
    })


@app.post("/generate")
async def generate(
    request: Request,
    file: UploadFile = File(...),
    model: str = Form(""),
):
    """Generate avatar from uploaded photo."""
    rid = uuid.uuid4().hex[:8]
    image_bytes = await file.read()

    # 开关关闭 / 未传 model → 统一用 ACTIVE_MODEL
    # 防止老版前端缓存或外部调用绕过开关
    if not SHOW_MODEL_SELECT or not model:
        model = ACTIVE_MODEL

    logger.info(
        f"[{rid}] http.request | method=POST | path=/generate | "
        f"file={file.filename} | mime={file.content_type} | size={len(image_bytes)} | "
        f"model={model} | client={request.client.host if request.client else '-'}"
    )

    if len(image_bytes) > 10 * 1024 * 1024:
        logger.warning(f"[{rid}] http.reject | reason=file_too_large | size={len(image_bytes)}")
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    if file.content_type not in ["image/jpeg", "image/png"]:
        logger.warning(f"[{rid}] http.reject | reason=unsupported_mime | mime={file.content_type}")
        raise HTTPException(status_code=400, detail="Only JPEG/PNG supported")

    start = time.time()
    try:
        result = generate_avatar(image_bytes, model, request_id=rid)
    except Exception as e:
        logger.error(f"[{rid}] http.error | type={type(e).__name__} | msg={e}")
        raise HTTPException(status_code=500, detail=str(e))

    duration_ms = int((time.time() - start) * 1000)

    logger.info(
        f"[{rid}] http.response | status=200 | model_key={result.model_key} | "
        f"duration={duration_ms}ms | provider_latency={result.latency_ms}ms"
    )

    return JSONResponse({
        "image_base64": result.to_base64(),
        "model_used": result.model_key or result.model_id,
        "display_name": _resolve_display_name(result.model_key or result.model_id),
        "model_id": result.model_id,
        "provider": result.provider,
        "platform": result.platform,
        "latency_ms": result.latency_ms,
        "duration_ms": duration_ms,
    })


def _resolve_display_name(model_key: str) -> str:
    """把 model_key 翻译成 display_name 给前端展示。"""
    from config import MODELS
    if model_key in MODELS:
        return MODELS[model_key].display_name
    # 兜底链格式 "X -> Y"
    if " -> " in model_key:
        target = model_key.split(" -> ")[-1].strip()
        if target in MODELS:
            return MODELS[target].display_name
    return model_key


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
