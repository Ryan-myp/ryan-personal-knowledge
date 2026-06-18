# 广告创意生成 AI 深度：Midjourney/DALL-E API/自动化批量生成

> 从 Stable Diffusion 到 Midjourney API，逐行解析广告创意自动化生成

---

## 第一部分：广告创意生成痛点

### 传统创意制作流程

```
传统广告创意制作：
1. 需求沟通 → 设计师理解需求（半天）
2. 创意构思 → 头脑风暴（1-2天）
3. 设计制作 → PS/Figma 出图（2-3天）
4. 审核修改 → 反馈修改（1-2天）
5. 上线测试 → A/B 测试效果（1周）

总耗时：1-2 周
成本：¥500-2000/张
产出：每天 1-2 张

AI 创意生成流程：
1. Prompt 编写 → 自然语言描述（5分钟）
2. AI 生成 → 批量生成变体（1分钟/张）
3. 人工筛选 → 挑选优质结果（10分钟）
4. 微调优化 → 局部修改（5分钟）
5. 上线测试 → A/B 测试效果（1周）

总耗时：10 分钟
成本：¥0.1-1/张
产出：每天 100-1000 张
```

---

## 第二部分：Stable Diffusion 源码深度

### SD 架构

```
Stable Diffusion 架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Autoencoder (VAE)                                                 │
│    ├── Encoder: 图像 → 潜空间 (768x64x64)                           │
│    └── Decoder: 潜空间 → 图像 (512x512x3)                           │
│                                                                     │
│ 2. U-Net (去噪网络)                                                  │
│    ├── Attention Blocks: 交叉注意力（文本条件）                       │
│    ├── ResNet Blocks: 残差连接                                      │
│    └── Down/Up Sampling: 多尺度特征                                  │
│                                                                     │
│ 3. CLIP Text Encoder                                                 │
│    ├── Tokenizer: 文本 → Token IDs                                  │
│    └── Transformer: Token IDs → 文本嵌入                            │
│                                                                     │
│ 推理流程：                                                           │
│ text → CLIP → text embeddings                                      │
│ random noise → U-Net (conditioned by text) → denoised latent        │
│ denoised latent → VAE Decode → image                                │
└─────────────────────────────────────────────────────────────────────┘
```

### pipeline_stable_diffusion.py 源码逐行解析

```python
# HuggingFace Diffusers 源码：stable_diffusion.py
class StableDiffusionPipeline(StableDiffusionMixin, PipelineMixin):
    
    def __call__(
        self,
        prompt: Union[str, List[str]] = None,
        height: int = 512,
        width: int = 512,
        num_inference_steps: int = 50,
        guidance_scale: float = 7.5,
        negative_prompt: Optional[Union[str, List[str]]] = None,
        generator: Optional[Union[torch.Generator, List[torch.Generator]]] = None,
        latents: Optional[torch.Tensor] = None,
        output_type: str = "pil",
        return_dict: bool = True,
    ):
        # 1. 文本编码
        text_input = self.tokenizer(
            prompt,
            padding="max_length",
            max_length=self.tokenizer.model_max_length,
            truncation=True,
            return_tensors="pt",
        )
        text_embeddings = self.text_encoder(text_input.input_ids)[0]
        
        # 2. 处理负面提示
        if negative_prompt is not None:
            neg_input = self.tokenizer(
                negative_prompt,
                padding="max_length",
                max_length=self.tokenizer.model_max_length,
                return_tensors="pt",
            )
            neg_embeddings = self.text_encoder(neg_input.input_ids)[0]
            text_embeddings = torch.cat([neg_embeddings, text_embeddings])
        else:
            text_embeddings = torch.cat([text_embeddings] * 2)
        
        # 3. 初始化噪声
        if latents is None:
            latents = torch.randn(
                (1, self.unet.in_channels, height // 8, width // 8),
                generator=generator,
            )
        
        # 4. 设置调度器
        self.scheduler.set_timesteps(num_inference_steps)
        
        # 5. 去噪循环
        for i, t in enumerate(self.scheduler.timesteps):
            # 5.1 扩展 batch size
            latent_model_input = torch.cat([latents] * 2)
            latent_model_input = self.scheduler.scale_model_input(
                latent_model_input, t
            )
            
            # 5.2 U-Net 去噪
            noise_pred = self.unet(
                latent_model_input, t, encoder_hidden_states=text_embeddings
            ).sample
            
            # 5.3 CFG 分离
            noise_pred_uncond, noise_pred_text = noise_pred.chunk(2)
            noise_pred = noise_pred_uncond + guidance_scale * (
                noise_pred_text - noise_pred_uncond
            )
            
            # 5.4 调度器一步
            latents = self.scheduler.step(
                noise_pred, t, latents
            ).prev_sample
        
        # 6. VAE 解码
        image = self.vae.decode(latents / 0.18215).sample
        image = (image / 2 + 0.5).clamp(0, 1)
        image = image.detach().cpu().permute(0, 2, 3, 1).numpy()
        
        return Image.fromarray((image * 255).round().astype("uint8"))
```

### attention.py 源码逐行解析

```python
# HuggingFace Diffusers 源码：attention.py - CrossAttention
class CrossAttention(nn.Module):
    """Cross-Attention 机制"""
    
    def __init__(
        self,
        query_dim: int,
        cross_attention_dim: Optional[int] = None,
        heads: int = 8,
        dim_head: int = 64,
        dropout: float = 0.0,
    ):
        super().__init__()
        inner_dim = dim_head * heads
        cross_attention_dim = cross_attention_dim or query_dim
        
        self.scale = dim_head**-0.5
        
        # Q, K, V 投影层
        self.to_q = nn.Linear(query_dim, inner_dim, bias=False)
        self.to_k = nn.Linear(cross_attention_dim, inner_dim, bias=False)
        self.to_v = nn.Linear(cross_attention_dim, inner_dim, bias=False)
        
        # 输出投影
        self.to_out = nn.Sequential(
            nn.Linear(inner_dim, query_dim),
            nn.Dropout(dropout),
        )
    
    def forward(self, hidden_states, context=None, mask=None):
        # 1. 计算 Q, K, V
        h = self.heads
        
        q = self.to_q(hidden_states)
        context = context if context is not None else hidden_states
        k = self.to_k(context)
        v = self.to_v(context)
        
        # 2. 重塑为多头
        q = self.reshape_for_scores(q)  # (batch, heads, seq_len, dim_head)
        k = self.reshape_for_scores(k)
        v = self.reshape_for_scores(v)
        
        # 3. 计算注意力
        attn_weights = torch.matmul(q, k.transpose(-1, -2)) * self.scale
        
        # 4. 应用 mask
        if mask is not None:
            attn_weights = attn_weights.masked_fill(mask == 0, -1e9)
        
        # 5. Softmax
        attn_weights = attn_weights.softmax(dim=-1)
        
        # 6. 加权求和
        attn_output = torch.matmul(attn_weights, v)
        
        # 7. 重塑回原始形状
        attn_output = self.reshape_to_output(attn_output)
        
        # 8. 输出投影
        return self.to_out(attn_output)
    
    def reshape_for_scores(self, tensor):
        batch_size, seq_len, dim = tensor.shape
        tensor = tensor.view(
            batch_size, seq_len, self.heads, self.dim_head
        )
        tensor = tensor.permute(0, 2, 1, 3)
        return tensor
```

---

## 第三部分：Midjourney API 深度

### MJ API 架构

```
MJ API 调用流程：
1. 发送 Prompt → MJ Server
2. MJ 生成图片（约 60 秒）
3. 回调通知完成
4. 下载图片

Prompt 工程技巧：
- 主体描述 + 风格 + 构图 + 光照 + 色彩
- 示例：
  "A luxury perfume bottle, golden, minimalist design,
   studio lighting, white background, product photography,
   8k, ultra detailed --ar 1:1 --v 6"
```

### mj_api.py 源码逐行解析

```python
# Midjourney API 调用
import requests
import time

class MidjourneyAPI:
    def __init__(self, api_key: str, base_url: str = "https://api.midjourney.com/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
    
    def generate(self, prompt: str, aspect_ratio: str = "1:1", 
                 version: str = "6") -> str:
        """
        生成广告创意图片
        
        Args:
            prompt: 创意描述
            aspect_ratio: 宽高比 (1:1, 16:9, 4:3, 9:16)
            version: MJ 版本
        
        Returns:
            job_id: 任务 ID
        """
        payload = {
            "prompt": prompt,
            "aspect_ratio": aspect_ratio,
            "version": version,
            "quality": "standard",
        }
        
        response = requests.post(
            f"{self.base_url}/generate",
            headers=self.headers,
            json=payload,
            timeout=30,
        )
        
        if response.status_code != 200:
            raise Exception(f"MJ API error: {response.text}")
        
        result = response.json()
        return result["job_id"]
    
    def poll_result(self, job_id: str, timeout: int = 120) -> str:
        """轮询获取生成结果"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            response = requests.get(
                f"{self.base_url}/jobs/{job_id}",
                headers=self.headers,
            )
            
            if response.status_code != 200:
                continue
            
            result = response.json()
            
            if result["status"] == "completed":
                return result["image_url"]
            elif result["status"] == "failed":
                raise Exception(f"Generation failed: {result.get('error')}")
            
            time.sleep(2)  # 每 2 秒轮询一次
        
        raise TimeoutError(f"Job {job_id} timed out")
    
    def batch_generate(self, prompts: list, aspect_ratio: str = "1:1") -> list:
        """批量生成"""
        job_ids = []
        for prompt in prompts:
            job_id = self.generate(prompt, aspect_ratio)
            job_ids.append(job_id)
        
        # 等待所有完成
        urls = []
        for job_id in job_ids:
            url = self.poll_result(job_id)
            urls.append(url)
        
        return urls
```

---

## 第四部分：DALL-E API 深度

### DALL-E 3 调用

```python
# DALL-E 3 API 调用
import openai

class DalleAPI:
    def __init__(self, api_key: str):
        self.client = openai.OpenAI(api_key=api_key)
    
    def generate(self, prompt: str, size: str = "1024x1024", 
                 quality: str = "hd", n: int = 1) -> list:
        """
        使用 DALL-E 3 生成广告创意
        
        Args:
            prompt: 创意描述
            size: 尺寸 (1024x1024, 1024x1792, 1792x1024)
            quality: 质量 (standard, hd)
            n: 生成数量
        
        Returns:
            图片 URL 列表
        """
        response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size=size,
            quality=quality,
            n=n,
            response_format="url",
        )
        
        return [img.url for img in response.data]
    
    def edit(self, image_url: str, prompt: str, 
             mask_url: str = None) -> list:
        """编辑现有图片"""
        response = self.client.images.edit(
            image=open(image_url, "rb"),
            mask=open(mask_url, "rb") if mask_url else None,
            prompt=prompt,
            n=1,
            size="1024x1024",
        )
        
        return [img.url for img in response.data]
```

---

## 第五部分：广告创意批量生成系统

### 创意生成流水线

```python
# 广告创意批量生成系统
class AdCreativeGenerator:
    def __init__(self, brand_guidelines: dict):
        self.brand = brand_guidelines
        self.mj = MidjourneyAPI(api_key="your_key")
        self.dalle = DalleAPI(api_key="your_key")
    
    def generate_variants(self, product_name: str, 
                          target_audience: str,
                          num_variants: int = 20) -> list:
        """
        为产品生成多个创意变体
        
        策略：
        1. 颜色变化：金色/银色/蓝色/红色
        2. 背景变化：纯色/渐变/场景
        3. 构图变化：正面/侧面/俯视
        4. 风格变化：简约/奢华/科技/自然
        """
        prompts = []
        
        colors = self.brand["allowed_colors"]
        backgrounds = self.brand["allowed_backgrounds"]
        styles = self.brand["allowed_styles"]
        
        for color in colors[:3]:
            for bg in backgrounds[:2]:
                for style in styles[:2]:
                    prompt = (
                        f"A professional product photo of {product_name}, "
                        f"{color} color scheme, {bg} background, "
                        f"{style} style, studio lighting, "
                        f"target audience: {target_audience}, "
                        f"high quality, 4k"
                    )
                    prompts.append(prompt)
                    
                    if len(prompts) >= num_variants:
                        break
                if len(prompts) >= num_variants:
                    break
            if len(prompts) >= num_variants:
                break
        
        # 批量生成
        urls = self.mj.batch_generate(prompts[:num_variants])
        
        return urls
    
    def optimize_for_platform(self, image_url: str, 
                               platform: str) -> dict:
        """
        针对不同平台优化图片
        
        Args:
            image_url: 原始图片 URL
            platform: 平台 (facebook, instagram, tiktok, google)
        
        Returns:
            优化后的图片信息
        """
        specs = {
            "facebook": {
                "feed": {"width": 1200, "height": 628},
                "story": {"width": 1080, "height": 1920},
                "ad": {"width": 1200, "height": 628},
            },
            "instagram": {
                "feed": {"width": 1080, "height": 1080},
                "story": {"width": 1080, "height": 1920},
            },
            "tiktok": {
                "in_feed": {"width": 1080, "height": 1920},
                "spark": {"width": 1080, "height": 1920},
            },
            "google": {
                "display": {"width": 1200, "height": 628},
                "responsive": {"width": 1200, "height": 320},
            },
        }
        
        platform_specs = specs[platform]
        optimized = {}
        
        for spec_name, spec in platform_specs.items():
            # 裁剪和调整大小
            optimized[spec_name] = {
                "width": spec["width"],
                "height": spec["height"],
                "format": "jpg",
                "quality": 85,
            }
        
        return optimized
```

---

## 第六部分：自测题

### Q1: Stable Diffusion 为什么用潜空间（Latent Space）？

**A**: 直接在像素空间去噪计算量太大（512x512x3）。VAE 将图像压缩到 64x64x4 的潜空间，计算量减少 64 倍。

### Q2: CFG（Classifier-Free Guidance）的作用？

**A**: 通过无条件预测和有条件预测的差值来增强生成质量。guidance_scale 越高，生成越符合 prompt，但可能失去多样性。

### Q3: Midjourney 和 DALL-E 的区别？

**A**:
| 维度 | Midjourney | DALL-E 3 |
|------|-----------|----------|
| 质量 | 艺术感强 | 写实感强 |
| 可控性 | 较差 | 较好 |
| 速度 | 60s | 10s |
| 价格 | ¥0.3/张 | ¥0.2/张 |
| 商用 | 需注意版权 | 明确商用许可 |

---

## 第七部分：生产实践

### 1. 创意生成流水线

```
创意生成流水线：
1. 产品图片 → 提取主色调
2. 自动生成 prompt
3. 批量生成 20-50 个变体
4. AI 评分筛选（CTR 预测）
5. 人工复核
6. A/B 测试
```

### 2. 成本控制

```
成本控制要点：
1. 优先使用 SD 本地部署（免费）
2. 批量生成降低 API 费用
3. 缓存相同 prompt 的结果
4. 设置预算上限
```

### 3. 合规审查

```
合规审查要点：
1. 品牌一致性检查
2. 版权审查（避免侵权）
3. 平台政策合规
4. 敏感内容过滤
```
