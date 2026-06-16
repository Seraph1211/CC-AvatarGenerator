# 设计决策记录

*Last updated: 2026-06-15*

---

## 决策 1：风格对齐方法 — 参考图锚定法

**问题**：两个人对"极简线条风"的理解不可能完全一致。仅靠文字描述无法保证对齐。

**决策**：用参考图作为风格 Spec，替代文字共识。

**流程**：
1. 在动代码之前，先用 API 跑 prompt 实验（可以用 Playground），找到"对了"的感觉
2. 选出 3-5 张满意的样本，存入 `prompts/references/`
3. 参考图即 style spec：后续所有 prompt 调整、模型对比，都以"是否接近参考图"作为唯一评判标准
4. 换模型时，不需要重新沟通风格描述——对着参考图调 prompt 就够了

**为什么先选参考图再写代码**：  
`gpt-image-1` 的 `images.edit()` 接口可以直接传参考图（style reference），prompt 描述"学习参考图风格"会比纯文字更稳定。参考图选不好，后面所有代码都是在跑偏的方向上努力。

---

## 决策 2：输出稳定性 — 两层防御（MVP）

**问题**：API 生成有随机性，同一 prompt 不同输入可能产出质量悬殊的结果。

**决策**：MVP 阶段只做前两层，第三层留 Post-MVP。

### 第 1 层：输入标准化（必做）
- 图片 resize 到 1024×1024，同时转换为 **RGBA PNG**（Pillow inline，约 5 行）
  - ⚠️ `gpt-image-1` 的 `images.edit()` 接口只接受带 alpha 通道的 PNG，JPEG 直接传会报错，必须在此处转换
- 不做人脸检测：用提示语引导用户（"请上传正面清晰照片，效果最佳"），非正面照让用户自己判断重传

### 第 2 层：Prompt 锁定（必做）
- 固定 prompt 文本（存 `prompts/line_art.txt`）
- 固定 seed（API 支持时）
- Temperature 最低值

### 第 3 层：质量门禁（Post-MVP）
- 记录每次生成的 model + duration + 用户是否下载（下载 = 满意的隐式信号）
- 发现质量下降 → 调 prompt 或切模型
- **不在 MVP 做边缘密度/色彩分布 CV 分析**：实现成本高、调参需大量样本、效果不确定，用"重试一次"覆盖大部分场景

---

## 决策 3：多模型切换 — 模型注册表（对比测试用）

**问题**：需要对比不同模型的出图效果，同时避免对普通用户暴露不必要的复杂性。

**决策**：后端维护模型注册表；前端通过 URL 参数控制，不进主流程 UI。

**MVP 接入的模型**：

```python
# config.py
MODELS = {
    "gpt-image-1": {
        "provider": "openai",
        "model": "gpt-image-1",
        "api_key_env": "OPENAI_API_KEY",
        "supports_img2img": True,
    },
    "fal-flux": {
        "provider": "fal",
        "model": "fal-ai/flux/schnell",
        "api_key_env": "FAL_API_KEY",
        "supports_img2img": True,   # ⚠️ 编码前需确认：flux/schnell 是 text-to-image 模型，
                                    # 需验证 fal.ai 是否提供对应的 img2img 端点。
                                    # 若不支持，MVP 阶段只用 gpt-image-1，fal 对比测试后置。
    },
}

ACTIVE_MODEL = os.getenv("ACTIVE_MODEL", "gpt-image-1")
```

**切换方式**：
- `POST /generate` 的 `model` 参数覆盖默认值
- URL 参数 `?model=fal-flux` 触发前端切换（放在页面底部"开发者选项"或隐藏入口）
- 环境变量 `ACTIVE_MODEL` 设全局默认

**generator.py 内部**：`photo_to_line_art(image_bytes, model_id)` 统一接口，内部按 provider 分发，对路由层透明。

**不做**：通用适配器 / 策略模式抽象。MVP 阶段两个 provider 的分发用 if/else 足够，等第三个模型进来再重构。

---

## 决策 4：产品形态 — Web First，H5 Ready

**问题**：最终产品需要同时支持 Web 和 H5，但 MVP 只做 Web。

**决策**：纯 HTML + Tailwind CSS CDN + 原生 JS，不引入前端框架。

**理由**：
- 纯 HTML 天生响应式，加 viewport + 媒体查询即可适配 H5
- Tailwind CDN 开发快，样式灵活
- 零构建工具，单文件可运行
- 后续 H5：API 调用逻辑完全复用，只需加 viewport 配置

---

## 决策 5：主力模型选择 — gpt-image-1 而非 Gemini Flash

**问题**：原方案使用 Gemini 2.5 Flash，但该模型是多模态理解模型，不支持图像生成。

**决策**：使用 `gpt-image-1`（OpenAI）作为主力模型。

**理由**：
- `images.edit()` 接口原生支持 img2img（传入原图 + prompt → 返回转换图）
- 可以传参考图作为风格引导
- API 调用极简，不需要 Vertex AI 等复杂基础设施
- 出图稳定性在同类 API 中较好

**成本参考**：约 $0.04/张（1024px），MVP 阶段可控。

**排除的选项**：
- `gemini-2.5-flash`：不支持图像生成，只能理解图像
- `Imagen 3 (Vertex AI)`：需要 GCP 项目，上手成本高
- `Midjourney API`：非官方，稳定性存疑

---

## 决策 6：大模型 API 方案 vs 自建管线

详见 [tech-comparison.md](tech-comparison.md)。

**结论**：MVP 阶段用大模型 API 快速验证，量起来后再评估切换时机。

**切换触发条件（参考）**：日均生成量 > 500 张，且自建管线（GPU 摊销 + 运维）的边际成本低于 API 成本时，启动迁移评估。
