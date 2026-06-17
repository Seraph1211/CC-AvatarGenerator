"""PackyAPI 平台测试脚本——薄壳，调用 production 的 provider 栈。

用法：
  python test/packyapi/test_packyapi.py                  # 文+图，默认模型
  python test/packyapi/test_packyapi.py --test txt2img   # 仅文
  python test/packyapi/test_packyapi.py --test img2img   # 仅图
  python test/packyapi/test_packyapi.py --model Gemini-3.1-Flash-Image-Preview

输出：test/packyapi/img/{model_key}/output_{suffix}_{index:03d}.png

注意：
  - 本脚本只负责：参数解析、预处理、调用 provider、保存结果、打印日志
  - 真正的 API 调用走 services.providers.make_provider()，和生产完全同源
  - IMG_MAX_DIM=512 仅为测试场景覆盖上传大小，规避 60s 长连接问题
"""
import argparse
import os
import sys
import time

# 让脚本可以直接 python test/packyapi/test_packyapi.py 运行
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, PROJECT_ROOT)

from config import ACTIVE_MODEL, get_model                      # noqa: E402
from services.generator import load_prompt                       # noqa: E402
from services.preprocessor import preprocess_image                # noqa: E402
from services.providers import make_provider                     # noqa: E402
from services.providers.base import ImageRequest, ImageGenError   # noqa: E402

# 测试场景专用：源图缩到 512 减少上传体积，规避 PackyAPI 60s 长连接被掐
TEST_IMG_MAX_DIM = 512

# 文生图通用 prompt（不依赖任何图）
TXT2IMG_PROMPT = (
    "Generate a hand-drawn minimalist line art sketch of a young person. "
    "Pure black brush-pen ink on white paper, casual avatar style. "
    "Under 50 strokes total, simple face with 4-6 marks. "
    "No shading, no color, no gray. 1:1 square."
)

OUTPUT_ROOT = os.path.join(SCRIPT_DIR, "img")
REF_IMG = os.path.join(PROJECT_ROOT, "references", "pic3.jpg")


# ============================================================
# 日志
# ============================================================

def _log(step: int, tag: str, msg: str) -> None:
    """统一日志格式：[MM-dd hh:mm:ss] [步骤] 标签 | 内容"""
    ts = time.strftime("%m-%d %H:%M:%S")
    print(f"  {ts} [{step}] {tag:8s} | {msg}")


# ============================================================
# 产物保存
# ============================================================

def _next_index(model_key: str, suffix: str) -> int:
    out_dir = os.path.join(OUTPUT_ROOT, model_key)
    if not os.path.isdir(out_dir):
        return 1
    prefix = f"output_{suffix}_"
    max_idx = 0
    for name in os.listdir(out_dir):
        if not (name.startswith(prefix) and name.endswith(".png")):
            continue
        try:
            idx = int(name[len(prefix):-4])
            if idx > max_idx:
                max_idx = idx
        except ValueError:
            continue
    return max_idx + 1


def _save_bytes(image_bytes: bytes, model_key: str, suffix: str) -> str:
    out_dir = os.path.join(OUTPUT_ROOT, model_key)
    os.makedirs(out_dir, exist_ok=True)
    idx = _next_index(model_key, suffix)
    filename = f"output_{suffix}_{idx:03d}.png"
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filepath


# ============================================================
# 测试用例
# ============================================================

def test_txt2img(model_key: str) -> bool:
    """文生图测试：纯文本 prompt 调 provider.txt2img。"""
    print("\n" + "=" * 60)
    print(f"【文生图】{model_key} → provider.txt2img")
    print("=" * 60)
    cfg = get_model(model_key)
    _log(1, "准备", f"provider={cfg.provider} | platform={cfg.platform} | model_id={cfg.model_id}")
    provider = make_provider(cfg)
    request = ImageRequest(prompt=TXT2IMG_PROMPT)
    try:
        result = provider.txt2img(request)
    except ImageGenError as e:
        _log(2, "结果", f"❌ {e}")
        return False
    filepath = _save_bytes(result.image_bytes, model_key, "txt2img")
    _log(2, "结果", f"✅ 文生图成功 | {len(result.image_bytes)} bytes | {filepath} | latency={result.latency_ms}ms")
    return True


def test_img2img(model_key: str) -> bool:
    """图生图测试：参考图 + prompt 调 provider.img2img。"""
    print("\n" + "=" * 60)
    print(f"【图生图】{model_key} → provider.img2img")
    print("=" * 60)
    cfg = get_model(model_key)
    _log(1, "准备", f"provider={cfg.provider} | platform={cfg.platform} | model_id={cfg.model_id}")
    if not os.path.exists(REF_IMG):
        _log(1, "准备", f"❌ 参考图不存在: {REF_IMG}")
        return False
    raw = open(REF_IMG, "rb").read()
    preprocessed = preprocess_image(raw, max_dim=TEST_IMG_MAX_DIM)
    _log(1, "准备", f"源图预处理 | {len(raw)} -> {len(preprocessed)} bytes (max_dim={TEST_IMG_MAX_DIM})")
    prompt = load_prompt(cfg.prompt_file)
    _log(1, "准备", f"prompt 加载 | {cfg.prompt_file} | {len(prompt)} chars")
    provider = make_provider(cfg)
    request = ImageRequest(prompt=prompt, image=preprocessed)
    try:
        result = provider.img2img(request)
    except ImageGenError as e:
        _log(2, "结果", f"❌ {e}")
        return False
    filepath = _save_bytes(result.image_bytes, model_key, "img2img")
    _log(2, "结果", f"✅ 图生图成功 | {len(result.image_bytes)} bytes | {filepath} | latency={result.latency_ms}ms")
    return True


# ============================================================
# 主入口
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(description="PackyAPI 平台测试（薄壳，调 production 栈）")
    parser.add_argument(
        "--model",
        default=ACTIVE_MODEL,
        help=f"注册表 key（默认 ACTIVE_MODEL={ACTIVE_MODEL}）",
    )
    parser.add_argument(
        "--test",
        choices=["all", "txt2img", "img2img"],
        default="all",
        help="all（文+图，默认）/ txt2img / img2img",
    )
    args = parser.parse_args()

    print(f"PackyAPI 测试 | model={args.model} | test={args.test}")
    print("—" * 60)

    run_txt = args.test in ("all", "txt2img")
    run_img = args.test in ("all", "img2img")
    results = {}
    if run_txt:
        results["txt2img"] = test_txt2img(args.model)
    if run_img:
        results["img2img"] = test_img2img(args.model)

    print("\n" + "=" * 60)
    print("【汇总】")
    print("=" * 60)
    for name, ok in results.items():
        print(f"  {'✅ PASS' if ok else '❌ FAIL'}  {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
