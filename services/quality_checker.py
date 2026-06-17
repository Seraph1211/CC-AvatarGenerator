"""输出质量门——对生成结果做最低限度校验。

MVP 阶段先用占位实现：单图直接通过。
post-MVP 接入 blank detection / edge density / color distribution 三档检查。
"""
import io

from PIL import Image


def passes(image_bytes: bytes) -> bool:
    """检查生成的图片是否满足最低质量要求。

    占位实现：能成功解码为 RGB 即视为通过。
    后续可在此加：
      - 空白检测（直方图过于平坦）
      - 边缘密度（生成图几乎是纯色说明失败）
      - 颜色分布（必须包含黑/白/灰三段才能算线稿）

    Returns:
        True 通过；False 不通过
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.convert("RGB")
        return True
    except Exception:
        return False
