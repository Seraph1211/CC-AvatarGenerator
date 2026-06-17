"""PackyAPI 图像模型统一测试脚本

支持测试以下模型（通过 CONFIG 区的 ACTIVE_MODEL 切换）：
  - gpt-image-2                        （OpenAI 协议，PACKYAPI_TOKEN_SORA 分组）
  - gemini-3.1-flash-image-preview     （Gemini 协议，PACKYAPI_TOKEN 分组）

用法：
  1. 在 .env 中配置对应分组的 Token（见 MODEL_CONFIG）
  2. 修改 CONFIG 区的 ACTIVE_MODEL 选择要测试的模型
  3. 跑测试：
       python test/packyapi/test_packyapi.py                  # 文生图 + 图生图（默认）
       python test/packyapi/test_packyapi.py --test txt2img   # 只跑文生图
       python test/packyapi/test_packyapi.py --test img2img   # 只跑图生图

输出：test/packyapi/img/{model}/output_{suffix}_{index:03d}.png
"""
import os
import sys
import argparse
import base64
import time
import httpx
from dotenv import load_dotenv

load_dotenv()


# ============================================================
# CONFIG：切换测试目标只改 ACTIVE_MODEL 这一行
# ============================================================
# 模型配置：每个模型可独立设置 token 环境和额外请求参数
# 设计要点：
#   - gpt-image-2 走完整 OpenAI Images API 规范，可以传 size/quality/output_format
#     以及关键的 input_fidelity="high"（保留原图人物特征，对头像产品是必备）
#   - gemini-3.1-flash-image-preview 走 PackyAPI image channel，
#     多传非标参数会触发上游 "submit request timeout"，故只保留最小集
MODEL_CONFIG = {
    "gpt-image-2": {
        "token_env": "PACKYAPI_TOKEN_SORA",   # OpenAI 协议（Sora 分组）
        "txt2img_extra": {
            "size": "1024x1024",
            "quality": "low",
            "output_format": "png",
            "response_format": "url",  # 文档推荐 url
        },
        "img2img_extra": {
            "size": "1024x1024",
            "quality": "low",
            "output_format": "png",
            "response_format": "url",
            "input_fidelity": "high",  # 关键：保留原图人物特征（avatar 必备）
        },
    },
    "gemini-3.1-flash-image-preview": {
        "token_env": "PACKYAPI_TOKEN",         # Gemini 分组
        "txt2img_extra": {
            "response_format": "url",
        },
        "img2img_extra": {
            "response_format": "url",
        },
    },
}

# 当前激活的模型（改这里切换）
ACTIVE_MODEL = "gpt-image-2"
# ACTIVE_MODEL = "gemini-3.1-flash-image-preview"

# 全局基础配置
BASE_URL = "https://www.packyapi.com/v1"

# 脚本所在目录与项目根
# SCRIPT_DIR 在 test/packyapi/ 下，要上溯两级才能到项目根
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))

# 图生图测试用图片（锚定到项目根，无论从哪个 CWD 运行都能找到）
IMG_PATH = os.path.join(PROJECT_ROOT, "references", "pic3.jpg")

# 图生图 prompt 文件路径（运行时动态加载）
LINE_ART_PROMPT_PATH = os.path.join(PROJECT_ROOT, "prompts", "line_art.txt")

# 源图最大边长（图生图上传前缩放目标）
# 设为 512：规避 PackyAPI 60s 长连接被掐（详见 _load_img_bytes 注释）
IMG_MAX_DIM = 512

# 输出图片根目录：test/packyapi/img/
# 每个模型一个子目录：test/packyapi/img/{model}/
# 命名规则: output_{model}_{suffix}_{index:03d}.png
OUTPUT_DIR_NAME = "img"


def _get_output_dir(model: str) -> str:
    """根据 model 返回对应的输出子目录路径：test/packyapi/img/{model}/。"""
    return os.path.join(SCRIPT_DIR, OUTPUT_DIR_NAME, model)


# ============================================================
# 工具函数
# ============================================================

def _load_active_config():
    """从 ACTIVE_MODEL 加载对应配置。"""
    if ACTIVE_MODEL not in MODEL_CONFIG:
        print(f"❌ 未配置的模型: {ACTIVE_MODEL}")
        print(f"   支持: {list(MODEL_CONFIG.keys())}")
        sys.exit(1)
    cfg = MODEL_CONFIG[ACTIVE_MODEL]
    token_env = cfg["token_env"]
    token = os.getenv(token_env)
    return ACTIVE_MODEL, token, token_env, cfg


def _log(step: int, tag: str, msg: str):
    """统一日志格式：[时间] [步骤序号] 标签 | 内容

    例:  06-17 14:23:45 [3] 发送   | 收到响应 | status=200
    """
    ts = time.strftime("%m-%d %H:%M:%S")
    print(f"  {ts} [{step}] {tag:8s} | {msg}")


def _check_config():
    """打印当前生效的配置，验证 Token 是否存在。"""
    print("—" * 60)
    print("【配置检查】")
    model, token, token_env, _ = _load_active_config()
    if not token:
        print(f"  ❌ 未设置 {token_env}，请在 .env 中配置")
        sys.exit(1)
    print(f"  ✅ 激活模型      : {model}")
    print(f"  ✅ Token 环境变量: {token_env}")
    print(f"  ✅ Base URL      : {BASE_URL}")
    print(f"  ✅ 参考图片      : {IMG_PATH}")
    print(f"  ✅ Prompt 文件   : {LINE_ART_PROMPT_PATH}")
    print(f"  ✅ 源图最大边长  : {IMG_MAX_DIM}px（规避 60s 长连接被掐）")
    print(f"  ✅ 输出目录      : {_get_output_dir(model)}")


def _get_next_index(model: str, suffix: str) -> int:
    """扫描 _get_output_dir(model) 中已有的 output_{suffix}_XXX.png，
    返回下一个可用的编号（max + 1）。目录不存在或无匹配文件时返回 1。
    """
    output_dir = _get_output_dir(model)
    if not os.path.isdir(output_dir):
        return 1
    prefix = f"output_{suffix}_"
    max_idx = 0
    for name in os.listdir(output_dir):
        if not (name.startswith(prefix) and name.endswith(".png")):
            continue
        stem = name[len(prefix):-4]   # 去掉前缀和 .png 后缀
        try:
            idx = int(stem)
            if idx > max_idx:
                max_idx = idx
        except ValueError:
            continue
    return max_idx + 1


def _save_b64(b64: str, model: str, suffix: str) -> str:
    """将 base64 字符串解码并保存为 PNG 文件。

    文件命名：output_{suffix}_{index:03d}.png（模型名在父目录中）
    保存位置：test/packyapi/img/{model}/

    Args:
        b64: 纯 base64 字符串（不含 data: 前缀）
        model: 模型名（用于子目录名）
        suffix: txt2img / img2img（用于文件名）

    Returns:
        保存文件的绝对路径
    """
    output_dir = _get_output_dir(model)
    os.makedirs(output_dir, exist_ok=True)
    idx = _get_next_index(model, suffix)
    filename = f"output_{suffix}_{idx:03d}.png"
    filepath = os.path.join(output_dir, filename)

    _log(0, "保存", f"开始写入文件 -> {filepath}")
    try:
        img_bytes = base64.b64decode(b64)
        with open(filepath, "wb") as f:
            f.write(img_bytes)
        _log(0, "保存", f"写入完成 | size={len(img_bytes)} bytes | path={filepath}")
        return filepath
    except Exception as e:
        _log(0, "保存", f"写入失败: {e}")
        raise


def _download_image(url: str, model: str, suffix: str) -> str:
    """从远程 URL 下载图片并保存为本地 PNG 文件。

    适用于部分模型/通道不直接返回 b64_json 的情况（例如返回腾讯云 COS 链接）。

    文件命名：output_{suffix}_{index:03d}.png（模型名在父目录中）
    保存位置：test/packyapi/img/{model}/

    Args:
        url: 远程图片 URL
        model: 模型名（用于子目录名）
        suffix: txt2img / img2img（用于文件名）

    Returns:
        保存文件的绝对路径
    """
    output_dir = _get_output_dir(model)
    os.makedirs(output_dir, exist_ok=True)
    idx = _get_next_index(model, suffix)
    filename = f"output_{suffix}_{idx:03d}.png"
    filepath = os.path.join(output_dir, filename)

    _log(0, "下载", f"开始从 URL 下载 -> {url[:80]}...")
    try:
        with httpx.Client(timeout=60) as client:
            resp = client.get(url)
        resp.raise_for_status()
        img_bytes = resp.content
        with open(filepath, "wb") as f:
            f.write(img_bytes)
        _log(0, "下载", f"下载完成 | size={len(img_bytes)} bytes | path={filepath}")
        return filepath
    except Exception as e:
        _log(0, "下载", f"❌ 下载失败: {e}")
        raise


def _load_img_bytes(path: str) -> bytes:
    """读取并预处理图片为 PNG bytes（图生图用）。

    策略：
      - 缩放到 IMG_MAX_DIM 以内（thumbnail 保持比例）
      - 转 RGB 去 alpha
      - 重新编码为 PNG 减小体积
      - PIL 不可用时回退到原始字节

    关于 IMG_MAX_DIM=512 的取舍：
      PackyAPI 官方文档明确警告"图生图/高清/高分辨率下生成耗时长，
      60 秒左右长连接会被中断（Server disconnected without sending
      a response）"。输出尺寸 1024x1024 是必须的，但输入源图可以
      比它小——模型会自己升采样。把源图压到 512x512 可以让上传 +
      上游处理都在 60s 窗口内完成，规避被掐连接的问题。
      根治需要用户侧把 packyapi.com 加入代理白名单。
    """
    try:
        from PIL import Image
        import io

        img = Image.open(path)
        orig_dim = img.size
        _log(1, "准备", f"原图信息 | format={img.format} | mode={img.mode} | size={orig_dim}")

        max_dim = IMG_MAX_DIM
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
            _log(1, "准备", f"图片已缩放 | {orig_dim} -> {img.size}")
        else:
            _log(1, "准备", f"图片无需缩放 | size={img.size}")

        if img.mode != "RGB":
            img = img.convert("RGB")
            _log(1, "准备", "图片已转 RGB 模式")
        else:
            _log(1, "准备", "图片已是 RGB 模式")

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        out_bytes = buf.getvalue()
        _log(1, "准备", f"预处理完成 | 输出 {len(out_bytes)} bytes")
        return out_bytes
    except ImportError:
        _log(1, "准备", "⚠️ PIL 不可用，回退到原始字节")
        with open(path, "rb") as f:
            return f.read()


def _load_img2img_prompt() -> str:
    """从 prompts/line_art.txt 加载图生图 prompt。"""
    if not os.path.exists(LINE_ART_PROMPT_PATH):
        print(f"❌ 图生图 prompt 文件不存在: {LINE_ART_PROMPT_PATH}")
        sys.exit(1)
    with open(LINE_ART_PROMPT_PATH, "r", encoding="utf-8") as f:
        return f.read().strip()


# 文生图通用 prompt（不引用图片上下文）
TXT2IMG_PROMPT = (
    "Generate a hand-drawn minimalist line art sketch of a young person. "
    "Pure black brush-pen ink on white paper, casual avatar style. "
    "Under 50 strokes total, simple face with 4-6 marks. "
    "No shading, no color, no gray. 1:1 square."
)


# ============================================================
# 文生图测试
# ============================================================

def test_txt2img(model: str, token: str, cfg: dict) -> bool:
    """文生图测试：仅用文本 prompt 调用 /v1/images/generations。

    基础字段（model, prompt, n）+ 模型特定 extras（见 MODEL_CONFIG）。

    流程：
      1. 构建请求体
      2. POST 到 /v1/images/generations
      3. 解析响应中的 b64_json 或 url
      4. 保存为本地 PNG

    Returns:
        True 表示测试通过，False 表示失败。
    """
    print("\n" + "=" * 60)
    print(f"【文生图测试】{model} -> /images/generations")
    print("=" * 60)

    payload = {
        "model": model,
        "prompt": TXT2IMG_PROMPT,
        "n": 1,
    }
    # 合并模型特定参数（gpt-image-2 会拿到 size/quality/output_format）
    payload.update(cfg.get("txt2img_extra", {}))
    _log(1, "准备", f"构建请求体完成 | prompt_len={len(TXT2IMG_PROMPT)} chars")
    _log(1, "准备", f"endpoint = POST {BASE_URL}/images/generations")
    _log(1, "准备", f"请求字段: {list(payload.keys())}")

    _log(2, "发送", "正在 POST /images/generations...")
    client = httpx.Client(timeout=180)
    try:
        resp = client.post(
            f"{BASE_URL}/images/generations",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    except httpx.TimeoutException:
        _log(2, "发送", "❌ 请求超时 (>180s)")
        return False
    except httpx.ConnectError as e:
        _log(2, "发送", f"❌ 连接失败: {e}")
        return False
    except Exception as e:
        _log(2, "发送", f"❌ 请求异常: {type(e).__name__}: {e}")
        return False

    elapsed_ms = int(resp.elapsed.total_seconds() * 1000)
    _log(2, "发送", f"收到响应 | status={resp.status_code} | elapsed={elapsed_ms}ms")

    if resp.status_code != 200:
        _log(3, "解析", f"❌ HTTP {resp.status_code}")
        _log(3, "解析", f"响应体: {resp.text[:500]}")
        if "model not found" in resp.text.lower():
            _log(3, "解析", "💡 提示: 模型名未识别，请检查令牌分组是否开通")
        return False
    _log(3, "解析", "HTTP 200 OK，开始解析 JSON...")

    try:
        data = resp.json()
    except Exception as e:
        _log(3, "解析", f"❌ JSON 解析失败: {e}")
        _log(3, "解析", f"原始响应: {resp.text[:500]}")
        return False

    items = data.get("data", [])
    _log(3, "解析", f"返回图片数: {len(items)}")

    if not items:
        _log(3, "解析", "❌ 响应 data 数组为空")
        _log(3, "解析", f"完整响应: {resp.text[:500]}")
        return False

    item = items[0]
    b64 = item.get("b64_json")
    url = item.get("url")

    if b64:
        _log(4, "提取", f"获取到 b64_json | len={len(b64)} chars")
        filepath = _save_b64(b64, model, "txt2img")
        _log(5, "结果", f"✅ 文生图成功 | 图片: {filepath}")
        return True

    if url:
        _log(4, "提取", f"获取到 url: {url[:100]}...")
        filepath = _download_image(url, model, "txt2img")
        _log(5, "结果", f"✅ 文生图成功 | 图片: {filepath}")
        return True

    _log(4, "提取", "❌ 响应中既无 b64_json 也无 url")
    _log(4, "提取", f"item keys: {list(item.keys())}")
    _log(4, "提取", f"完整响应: {resp.text[:500]}")
    return False


# ============================================================
# 图生图测试
# ============================================================

def test_img2img(model: str, token: str, cfg: dict) -> bool:
    """图生图测试：上传本地图片 + prompt 调用 /v1/images/edits。

    prompt 从 prompts/line_art.txt 动态加载（与项目实际生成保持一致）。

    修复记录（之前踩过的坑）：
      - PackyAPI image channel 不支持 chat completions，只支持 /v1/images/edits
      - 非标准参数（quality/output_format/size）可能让 channel 转换逻辑卡住，
        触发上游 "submit request timeout"（gemini 模型会受影响）
      - 1MB+ 的原图预处理到 1024x1024 RGB PNG，减小上游处理耗时
      - gpt-image-2 必须传 input_fidelity="high" 才保留原图人物特征

    流程：
      1. 加载 line_art.txt 作为 prompt
      2. 预处理参考图片到 1024x1024 RGB PNG
      3. 构建 multipart/form-data（基础字段 + 模型特定 extras）
      4. POST 到 /v1/images/edits
      5. 解析响应中的 b64_json 或 url
      6. 保存为本地 PNG

    Returns:
        True 表示测试通过，False 表示失败。
    """
    print("\n" + "=" * 60)
    print(f"【图生图测试】{model} -> /images/edits")
    print("=" * 60)

    # ---------- 步骤 1：加载 prompt ----------
    _log(1, "准备", f"加载图生图 prompt <- {LINE_ART_PROMPT_PATH}")
    try:
        prompt = _load_img2img_prompt()
        _log(1, "准备", f"prompt 已加载 | len={len(prompt)} chars")
    except Exception as e:
        _log(1, "准备", f"❌ 加载 prompt 失败: {e}")
        return False

    # ---------- 步骤 2：检查并预处理图片 ----------
    if not os.path.exists(IMG_PATH):
        _log(1, "准备", f"❌ 图片不存在: {IMG_PATH}")
        return False

    abs_img_path = os.path.abspath(IMG_PATH)
    _log(1, "准备", f"图片存在 | path={abs_img_path}")

    try:
        image_bytes = _load_img_bytes(abs_img_path)
    except Exception as e:
        _log(1, "准备", f"❌ 读取/预处理图片失败: {e}")
        return False

    # ---------- 步骤 3：构建 multipart 请求 ----------
    _log(2, "准备", "构建 multipart/form-data 请求体...")
    files = {"image": ("photo.png", image_bytes, "image/png")}
    form_data = {
        "model": model,
        "prompt": prompt,
        "n": "1",
    }
    # 合并模型特定参数
    #   gpt-image-2: size/quality/output_format/input_fidelity/response_format
    #   gemini:      response_format（其他参数不能传，会触发 timeout）
    form_data.update(cfg.get("img2img_extra", {}))
    _log(2, "准备", f"图片已打包 | field_name=image | mime=image/png | {len(image_bytes)} bytes")
    _log(2, "准备", f"表单字段: {list(form_data.keys())}")

    # ---------- 步骤 4：发送请求 ----------
    _log(3, "发送", "正在 POST /images/edits（上传图片+prompt）...")
    client = httpx.Client(timeout=180)
    try:
        resp = client.post(
            f"{BASE_URL}/images/edits",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=form_data,
        )
    except httpx.TimeoutException:
        _log(3, "发送", "❌ 请求超时 (>180s)")
        return False
    except httpx.ConnectError as e:
        _log(3, "发送", f"❌ 连接失败: {e}")
        return False
    except Exception as e:
        _log(3, "发送", f"❌ 请求异常: {type(e).__name__}: {e}")
        return False

    elapsed_ms = int(resp.elapsed.total_seconds() * 1000)
    _log(3, "发送", f"收到响应 | status={resp.status_code} | elapsed={elapsed_ms}ms")

    # ---------- 步骤 5：检查 HTTP 状态 ----------
    if resp.status_code != 200:
        _log(4, "解析", f"❌ HTTP {resp.status_code}")
        _log(4, "解析", f"响应体: {resp.text[:500]}")
        if "model not found" in resp.text.lower():
            _log(4, "解析", "💡 提示: 模型名未识别，请检查令牌分组是否开通")
        return False
    _log(4, "解析", "HTTP 200 OK | 开始解析 JSON...")

    # ---------- 步骤 6：解析 JSON ----------
    try:
        data = resp.json()
    except Exception as e:
        _log(4, "解析", f"❌ JSON 解析失败: {e}")
        _log(4, "解析", f"原始响应: {resp.text[:500]}")
        return False

    items = data.get("data", [])
    _log(4, "解析", f"返回图片数: {len(items)}")

    if not items:
        _log(4, "解析", "❌ 响应 data 数组为空")
        _log(4, "解析", f"完整响应: {resp.text[:500]}")
        return False

    item = items[0]

    # ---------- 步骤 7：提取图片 ----------
    b64 = item.get("b64_json")
    url = item.get("url")

    if b64:
        _log(5, "提取", f"获取到 b64_json | len={len(b64)} chars")
        filepath = _save_b64(b64, model, "img2img")
        _log(6, "结果", f"✅ 图生图成功 | 图片: {filepath}")
        return True

    if url:
        _log(5, "提取", f"获取到 url: {url[:100]}...")
        filepath = _download_image(url, model, "img2img")
        _log(6, "结果", f"✅ 图生图成功 | 图片: {filepath}")
        return True

    _log(5, "提取", "❌ 响应中既无 b64_json 也无 url")
    _log(5, "提取", f"item keys: {list(item.keys())}")
    _log(5, "提取", f"完整响应: {resp.text[:500]}")
    return False


# ============================================================
# 主入口
# ============================================================

def main():
    """测试入口——通过 --test 选择要跑的测试，默认两个都跑。"""
    parser = argparse.ArgumentParser(
        description="PackyAPI 图像模型测试（切模型请改 CONFIG.ACTIVE_MODEL）"
    )
    parser.add_argument(
        "--test",
        choices=["all", "txt2img", "img2img"],
        default="all",
        help="要跑的测试：all（文+图，默认）/ txt2img（仅文）/ img2img（仅图）",
    )
    args = parser.parse_args()

    print("PackyAPI 图像模型统一测试\n")
    _check_config()
    model, token, _, cfg = _load_active_config()

    run_txt = args.test in ("all", "txt2img")
    run_img = args.test in ("all", "img2img")

    print(f"\n  本次运行：{'文生图 + ' if run_txt else ''}{'图生图' if run_img else ''}".rstrip(" +"))

    results = {}
    if run_txt:
        results["txt2img"] = test_txt2img(model, token, cfg)
    if run_img:
        results["img2img"] = test_img2img(model, token, cfg)

    # ---------- 汇总 ----------
    print("\n" + "=" * 60)
    print("【测试结果汇总】")
    print("=" * 60)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")
    if all(results.values()):
        print(f"\n  🎉 全部通过。激活模型: {model}")
        return 0
    print(f"\n  ⚠️  有失败项。激活模型: {model}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
