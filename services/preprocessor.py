"""图片预处理:把上传的照片归一化为 provider 一致期望的输入。"""
import io
from PIL import Image

# 默认输出尺寸:1024×1024 pad-to-square RGBA PNG。
# 多数 provider(GPT Image 系列、Midjourney、SDXL 等)期望方形输入。
DEFAULT_MAX_DIM = 1024
DEFAULT_MODE = "RGBA"
DEFAULT_FILL = (255, 255, 255, 255)   # 纯白填充


def preprocess_image(
    image_bytes: bytes,
    max_dim: int = DEFAULT_MAX_DIM,
    mode: str = DEFAULT_MODE,
    fill: tuple = DEFAULT_FILL,
) -> bytes:
    """把任意尺寸/格式的输入图片归一化为 max_dim×max_dim 的 PNG 字节流。

    流程:
      1. 打开图片,转 RGBA(去 alpha 通道差异)
      2. thumbnail 保持比例缩放到 max_dim 以内
      3. paste 到 max_dim×max_dim 的纯白画布居中
      4. 重新编码为 PNG

    Args:
        image_bytes: 原始图片字节流(JPEG/PNG/WebP 等,PIL 支持即可)
        max_dim: 输出画布边长。源图会保持比例缩放到该边长以内再 pad 居中。
                  测试 gpt-image-2 60s 边界时建议调到 512 缓解上传耗时。
        mode: 输出颜色模式,默认 RGBA
        fill: pad 区域填充色,默认纯白不透明

    Returns:
        PNG 编码后的字节流
    """
    img = Image.open(io.BytesIO(image_bytes))
    if img.mode != mode:
        img = img.convert(mode)
    img.thumbnail((max_dim, max_dim), Image.LANCZOS)
    canvas = Image.new(mode, (max_dim, max_dim), fill)
    offset = ((max_dim - img.width) // 2, (max_dim - img.height) // 2)
    canvas.paste(img, offset)
    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()
