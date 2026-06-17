"""PackyAPI 测试脚本——调用 production 的 provider 栈做烟雾测试。

设计:本脚本只负责 argparse、prompt 加载、产物落盘这些"测试外围"工作;
API 调用、错误处理、响应解析全部走 services.providers 包,和生产代码
共用同一份实现。

用法:
  python test/packyapi/test_packyapi.py                  # 跑 ACTIVE_MODEL 的文+图
  python test/packyapi/test_packyapi.py --test txt2img   # 只跑文生图
  python test/packyapi/test_packyapi.py --test img2img   # 只跑图生图
  python test/packyapi/test_packyapi.py --model gpt-image-2

输出:test/packyapi/img/{model}/output_{suffix}_{idx:03d}.png
"""
import argparse
import os
import sys
import time
from dataclasses import replace

# 把项目根加进 sys.path,让 from config / from services... 能找到
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import ACTIVE_MODEL, get_model
from services.preprocessor import preprocess_image
from services.providers import ImageRequest, make_provider

# ============================================================
# 路径与输出约定
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
IMG_PATH = os.path.join(PROJECT_ROOT, "references", "pic3.jpg")
OUTPUT_DIR_NAME = "img"


def _get_output_dir(model_key: str) -> str:
    return os.path.join(SCRIPT_DIR, OUTPUT_DIR_NAME, model_key)


# ============================================================
# 测试侧覆盖:缩小输入 + 调低 quality,模拟 60s 边界场景
# ============================================================
# 生产 cfg.preprocess_max_dim = 1024,这里覆盖到 512 缩短上传耗时
# 生产 cfg.img2img_defaults["quality"] = "high",这里覆盖到 "low"
TEST_PREPROCESS_MAX_DIM = 512
TEST_IMG2IMG_QUALITY = "low"
TEST_TXT2IMG_QUALITY = "low"


def _build_test_config(model_key: str):
    """基于生产 cfg 构造一个测试 cfg,覆盖预处理边长和质量参数。

    复用同一份 prompt、base_url、token 等,只换掉两个会显著影响耗时的字段。
    """
    prod_cfg = get_model(model_key)
    # img2img_defaults 覆盖 quality 到 low
    new_img2img = {**prod_cfg.img2img_defaults, "quality": TEST_IMG2IMG_QUALITY}
    new_txt2img = {**prod_cfg.txt2img_defaults, "quality": TEST_TXT2IMG_QUALITY}
    return replace(
        prod_cfg,
        preprocess_max_dim=TEST_PREPROCESS_MAX_DIM,
        txt2img_defaults=new_txt2img,
        img2img_defaults=new_img2img,
    )


# ============================================================
# 工具函数
# ============================================================

def _log(step: int, tag: str, msg: str):
    """统一日志格式:[时间] [步骤序号] 标签 | 内容"""
    ts = time.strftime("%m-%d %H:%M:%S")
    print(f"  {ts} [{step}] {tag:8s} | {msg}")


def _get_next_index(model_key: str, suffix: str) -> int:
    output_dir = _get_output_dir(model_key)
    if not os.path.isdir(output_dir):
        return 1
    prefix = f"output_{suffix}_"
    max_idx = 0
    for name in os.listdir(output_dir):
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
    """把 image_bytes 写入 test/packyapi/img/{model}/output_{suffix}_{idx:03d}.png。"""
    output_dir = _get_output_dir(model_key)
    os.makedirs(output_dir, exist_ok=True)
    idx = _get_next_index(model_key, suffix)
    filepath = os.path.join(output_dir, f"output_{suffix}_{idx:03d}.png")
    with open(filepath, "wb") as f:
        f.write(image_bytes)
    return filepath


# 文生图测试用 prompt(纯文本,不引用源图)
TXT2IMG_PROMPT = (
    "Generate a hand-drawn minimalist line art sketch of a young person. "
    "Pure black brush-pen ink on white paper, casual avatar style. "
    "Under 50 strokes total, simple face with 4-6 marks. "
    "No shading, no color, no gray. 1:1 square."
)


def _load_prompt() -> str:
    """从 production prompt 文件加载图生图 prompt(用 cfg.prompt_file 路径)。"""
    prod_cfg = get_model(ACTIVE_MODEL)
    prompt_path = os.path.join(PROJECT_ROOT, prod_cfg.prompt_file)
    if not os.path.exists(prompt_path):
        raise FileNotFoundError(
            f"Prompt file not found: {prompt_path}. "
            f"Check cfg.prompt_file in config.py."
        )
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read().strip()


# ============================================================
# 实际测试
# ============================================================

def test_txt2img(model_key: str) -> bool:
    cfg = _build_test_config(model_key)
    provider = make_provider(cfg)
    req = ImageRequest(prompt=TXT2IMG_PROMPT)

    print("\n" + "=" * 60)
    print(f"【文生图】{model_key} ({cfg.platform})")
    print("=" * 60)
    _log(1, "准备", f"provider={cfg.provider} | model_id={cfg.model_id} | base={cfg.base_url}")

    try:
        result = provider.txt2img(req)
    except Exception as e:
        _log(2, "调用", f"❌ {type(e).__name__}: {e}")
        return False

    filepath = _save_bytes(result.image_bytes, model_key, "txt2img")
    _log(3, "结果", f"✅ 落盘 | size={len(result.image_bytes)} bytes | {filepath}")
    return True


def test_img2img(model_key: str) -> bool:
    cfg = _build_test_config(model_key)
    provider = make_provider(cfg)

    print("\n" + "=" * 60)
    print(f"【图生图】{model_key} ({cfg.platform})")
    print("=" * 60)

    # 1. 加载图生图 prompt
    try:
        prompt = _load_prompt()
        _log(1, "准备", f"prompt loaded | {len(prompt)} chars")
    except Exception as e:
        _log(1, "准备", f"❌ {e}")
        return False

    # 2. 预处理源图
    if not os.path.exists(IMG_PATH):
        _log(1, "准备", f"❌ 图片不存在: {IMG_PATH}")
        return False
    with open(IMG_PATH, "rb") as f:
        image_bytes = preprocess_image(f.read(), max_dim=TEST_PREPROCESS_MAX_DIM)
    _log(1, "准备", f"图片已预处理 | {len(image_bytes)} bytes | max_dim={TEST_PREPROCESS_MAX_DIM}")

    # 3. 调用 provider
    req = ImageRequest(prompt=prompt, image=image_bytes)
    _log(2, "调用", f"POST {cfg.base_url}/images/edits | provider={cfg.provider}")
    try:
        result = provider.img2img(req)
    except Exception as e:
        _log(2, "调用", f"❌ {type(e).__name__}: {e}")
        return False

    # 4. 落盘
    filepath = _save_bytes(result.image_bytes, model_key, "img2img")
    _log(3, "结果", f"✅ 落盘 | size={len(result.image_bytes)} bytes | {filepath}")
    return True


# ============================================================
# 入口
# ============================================================

def main() -> int:
    parser = argparse.ArgumentParser(
        description="PackyAPI 平台测试(走 production provider 栈)"
    )
    parser.add_argument("--model", default=ACTIVE_MODEL, help=f"模型 key(默认 {ACTIVE_MODEL})")
    parser.add_argument(
        "--test",
        choices=["all", "txt2img", "img2img"],
        default="all",
        help="跑哪些测试:all(默认)/txt2img/img2img",
    )
    args = parser.parse_args()

    print("PackyAPI 测试 (production provider 栈)\n")
    print(f"  模型 : {args.model}")
    print(f"  来源 : config.MODELS['{args.model}']")
    run_txt = args.test in ("all", "txt2img")
    run_img = args.test in ("all", "img2img")
    print(f"  本次 : {'文生图 + ' if run_txt else ''}{'图生图' if run_img else ''}".rstrip(" +"))

    results = {}
    if run_txt:
        results["txt2img"] = test_txt2img(args.model)
    if run_img:
        results["img2img"] = test_img2img(args.model)

    print("\n" + "=" * 60)
    print("【结果汇总】")
    print("=" * 60)
    for name, passed in results.items():
        print(f"  {'✅ PASS' if passed else '❌ FAIL'}  {name}")
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
