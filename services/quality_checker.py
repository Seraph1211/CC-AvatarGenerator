"""输出质量门:对 provider 返回的图片做基本可用性检查。

MVP 阶段:placeholder 实现,只做最基础的全白/全黑检测。
后续迭代会加入:边缘密度、颜色分布、人脸检测等更严格的检查,
并把结果记录到监控里(post-MVP 阶段)。
"""
from .providers.base import ImageResult


def passes(result: ImageResult) -> bool:
    """质量门主入口。返回 True 表示通过,False 表示该结果应被丢弃/重试。

    当前规则:
      1. 图片尺寸非零
      2. 不是几乎纯白/纯黑(全空或全黑失败)

    真正的指标(边缘密度、颜色分布、人脸检测)在 post-MVP 阶段接入。
    """
    img_bytes = result.image_bytes
    if not img_bytes or len(img_bytes) < 100:
        return False

    try:
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    except Exception:
        # 无法解码的图片直接判失败
        return False

    # 极端情况检测:全白/全黑通常意味着生成失败
    extrema = img.getextrema()
    # extrema 是 ((rmin, rmax), (gmin, gmax), (bmin, bmax))
    if all(rmax - rmin < 5 for rmin, rmax in extrema):
        # RGB 三个通道几乎没变化 → 单色图
        return False

    return True
