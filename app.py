"""FastAPI entry point."""
import time
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from config import MODELS, ACTIVE_MODEL, DEFAULT_MODEL
from services.generator import generate_avatar

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
def list_models():
    """List available models. 前端按 platform 分组渲染 dropdown。"""
    return JSONResponse({
        "default": DEFAULT_MODEL,
        "models": [
            {
                "id": k,
                "name": v.display_name,
                "platform": v.platform,
                "provider": v.provider,
            }
            for k, v in MODELS.items()
        ],
    })


@app.post("/generate")
async def generate(
    file: UploadFile = File(...),
    model: str = Form(ACTIVE_MODEL),
):
    """Generate avatar from uploaded photo."""
    image_bytes = await file.read()

    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 10MB)")

    if file.content_type not in ["image/jpeg", "image/png"]:
        raise HTTPException(status_code=400, detail="Only JPEG/PNG supported")

    start = time.time()
    try:
        result = generate_avatar(image_bytes, model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    duration_ms = int((time.time() - start) * 1000)

    return JSONResponse({
        "image_base64": result["image_base64"],
        "model_used": result["model_used"],
        "duration_ms": duration_ms,
    })


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
