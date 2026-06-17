"""输入图片归一化。

将上传的照片转为所有 provider 一致能接受的输入格式：
默认 1024×1024 RGBA PNG，pad-to-square 保比例，背景白。
不同模型可由 model_config.preprocess_max_dim 覆盖（测试用 512 减少上传体积）。
"""
import io

from PIL import Image


def preprocess_image(image_bytes: bytes, max_dim: int = 1024) -> bytes:
    """将上传的图片归一化为 max_dim×max_dim RGBA PNG bytes。

    策略：
      - 缩放到 max_dim 以内（thumbnail 保持比例）
      - 居中 paste 到 max_dim×max_dim 白底画布
      - 重新编码为 PNG

    Args:
        image_bytes: 上传的原始图片字节
        max_dim: 目标边长（默认 1024；测试场景可设 512 减少上游处理耗时）

    Returns:
        PNG 格式的 bytes
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    canvas = Image.new("RGBA", (max_dim, max_dim), (255, 255, 255, 255))
    offset = ((max_dim - img.width) // 2, (max_dim - img.height) // 2)
    canvas.paste(img, offset)
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()
