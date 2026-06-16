# 广告素材 AI 生成深度：文案/图片/视频自动生成

> AIGC 在广告领域的应用 + 模板化生成 + 个性化创意

---

## 第一部分：为什么需要 AI 生成素材？

### 业务场景

```
1. A/B 测试素材：
   → 同一个广告需要 10+ 个素材
   → 人工制作成本高（1 个素材 2-4 小时）
   → AI 生成：10 个素材 5 分钟

2. 个性化创意：
   → 不同用户看到不同的素材
   → 用户画像 → 生成匹配的素材
   → CTR 提升 20-30%

3. 规模化生成：
   → 100 万广告 × 5 个素材 = 500 万个素材
   → 人工无法完成
   → AI 批量生成

4. 多语言/多尺寸：
   → 同一个素材适配 10+ 种语言
   → 同一个素材适配 20+ 种尺寸
   → AI 自动转换
```

### 数据量估算

```
100 万广告 × 每个广告 5 个素材 = 500 万个素材
→ 文案：500 万条
→ 图片：500 万张
→ 视频：100 万个

每天新增：
→ 10 万新创意
→ 50 万新素材（AI 生成）
```

---

## 第二部分：素材生成架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    广告素材 AI 生成系统                       │
└─────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────────┐
                    │         广告主后台                      │
                    │  - 输入：产品信息 + 目标受众            │
                    │  - 输出：生成的素材列表                 │
                    └──────────────┬────────────────────────┘
                                   │
                    ┌──────────────▼────────────────────────┐
                    │       Creative Generation Service     │
                    │  - 文案生成                            │
                    │  - 图片生成                            │
                    │  - 视频生成                            │
                    │  - 尺寸适配                            │
                    └──────┬──────────┬──────────┬──────────┘
                           │          │          │
              ┌────────────▼──┐ ┌─────▼────┐ ┌───▼────────┐
              │  LLM API      │ │ Image Gen │ │ Video Gen  │
              │  - 文案生成    │ │ - DALL-E  │ │ - Runway   │
              │  - Claude/GPT │ │ - Midjour │ │ - Pika     │
              └───────────────┘ └──────────┘ └────────────┘
```

### 2.2 核心流程

```
1. 用户输入：
   → 产品名称：Nike Air Max
   → 目标受众：25-35 岁男性
   → 卖点：轻盈/透气/时尚
   → 语言：中文

2. AI 生成：
   → 文案：5 条（不同风格）
   → 图片：10 张（不同场景）
   → 视频：2 个（不同时长）

3. 适配：
   → 尺寸：10 种（Banner/信息流/开屏）
   → 语言：5 种（中/英/日/韩/越）

4. 审核：
   → AI 审核：自动通过/拒绝/转人工
   → 人工审核：审核转人工的素材
```

---

## 第三部分：文案生成

### 3.1 文案生成策略

```
1. 模板化生成：
   → 模板 1：产品名 + 卖点 + 促销
   → 模板 2：痛点 + 解决方案 + 行动号召
   → 模板 3：场景 + 产品 + 优惠

2. LLM 生成：
   → Prompt 工程：控制生成风格
   → Few-shot：提供示例
   → 后处理：过滤违规内容
```

### 3.2 代码实现

```go
package creative

import (
    "context"
    "strings"
)

type Copywriter struct {
    llmClient *LLMClient
    templates []Template
}

type Template struct {
    Name    string
    Pattern string // "{product} + {selling_point} + {promotion}"
    Params  []string
}

// GenerateCopy 生成文案
func (cw *Copywriter) GenerateCopy(ctx context.Context, product ProductInfo, count int) ([]string, error) {
    // 1. 模板化生成
    templateCopies := cw.generateByTemplates(product, count/2)
    
    // 2. LLM 生成
    llmCopies := cw.generateByLLM(ctx, product, count/2)
    
    // 3. 合并去重
    allCopies := append(templateCopies, llmCopies...)
    allCopies = deduplicate(allCopies)
    
    // 4. 过滤违规
    allCopies = cw.filterViolations(allCopies)
    
    return allCopies, nil
}

// generateByTemplates 模板化生成
func (cw *Copywriter) generateByTemplates(product ProductInfo, count int) []string {
    copies := make([]string, 0, count)
    
    for _, t := range cw.templates {
        params := map[string]string{
            "product":    product.Name,
            "selling_point": strings.Join(product.SellingPoints, "、"),
            "promotion":  product.Promotion,
            "cta":        product.CTA,
        }
        
        copy := cw.renderTemplate(t.Pattern, params)
        copies = append(copies, copy)
        
        if len(copies) >= count {
            break
        }
    }
    
    return copies
}

// generateByLLM LLM 生成
func (cw *Copywriter) generateByLLM(ctx context.Context, product ProductInfo, count int) []string {
    prompt := cw.buildPrompt(product)
    
    responses, err := cw.llmClient.Generate(ctx, prompt, count)
    if err != nil {
        return nil
    }
    
    return responses
}

// buildPrompt 构建 Prompt
func (cw *Copywriter) buildPrompt(product ProductInfo) string {
    return `你是一个广告文案专家。请为以下产品生成广告文案。

产品信息：
- 名称：{{.Name}}
- 卖点：{{.SellingPoints}}
- 促销：{{.Promotion}}
- 目标受众：{{.TargetAudience}}
- 语言：{{.Language}}

要求：
1. 每条文案不超过 30 字
2. 包含产品名和卖点
3. 包含行动号召
4. 不包含违禁词

请生成 {{.Count}} 条不同风格的文案。`
}
```

### 3.3 违规词过滤

```go
// ViolationFilter 违规词过滤器
type ViolationFilter struct {
    blacklist map[string]bool
}

// NewViolationFilter 创建违规词过滤器
func NewViolationFilter() *ViolationFilter {
    return &ViolationFilter{
        blacklist: map[string]bool{
            "最": true, "第一": true, "最好": true, // 广告法禁用
            "免费": true, "100%": true, // 虚假宣传
            // ...
        },
    }
}

// Filter 过滤文案
func (vf *ViolationFilter) Filter(copy string) bool {
    for word := range vf.blacklist {
        if strings.Contains(copy, word) {
            return false
        }
    }
    return true
}
```

---

## 第四部分：图片生成

### 4.1 图片生成方式

```
1. 模板化生成：
   → 固定模板 + 动态文本 + 动态图片
   → 速度快，成本低
   → 适用：电商 Banner、信息流广告

2. AIGC 生成：
   → DALL-E / Midjourney / Stable Diffusion
   → 质量高，灵活
   → 适用：品牌广告、开屏广告

3. 混合生成：
   → 模板 + AIGC 混合
   → 平衡成本和质量
   → 适用：大部分场景
```

### 4.2 代码实现

```go
type ImageGenerator struct {
    templateEngine *TemplateEngine
    aigcClient     *AIGCClient
}

// GenerateImage 生成图片
func (ig *ImageGenerator) GenerateImage(ctx context.Context, product ProductInfo, style string) ([]Image, error) {
    switch style {
    case "template":
        return ig.generateByTemplate(product)
    case "aigc":
        return ig.generateByAIGC(ctx, product)
    case "hybrid":
        return ig.generateHybrid(ctx, product)
    default:
        return ig.generateByTemplate(product)
    }
}

// generateByTemplate 模板化生成
func (ig *ImageGenerator) generateByTemplate(product ProductInfo) ([]Image, error) {
    images := make([]Image, 0)
    
    // 1. 获取模板
    templates := ig.templateEngine.GetTemplates(product.Category)
    
    // 2. 渲染模板
    for _, t := range templates {
        image := t.Render(product)
        images = append(images, image)
    }
    
    return images, nil
}

// generateByAIGC AIGC 生成
func (ig *ImageGenerator) generateByAIGC(ctx context.Context, product ProductInfo) ([]Image, error) {
    images := make([]Image, 0)
    
    // 1. 构建 Prompt
    prompt := ig.buildImagePrompt(product)
    
    // 2. 调用 AIGC API
    variants, err := ig.aigcClient.GenerateImages(ctx, prompt, 5)
    if err != nil {
        return nil, err
    }
    
    // 3. 添加产品文字
    for _, variant := range variants {
        image := ig.addTextOnImage(variant, product.Name, product.Price)
        images = append(images, image)
    }
    
    return images, nil
}

// buildImagePrompt 构建图片 Prompt
func (ig *ImageGenerator) buildImagePrompt(product ProductInfo) string {
    return `Product photography of {{.Name}}, 
style: modern, clean, professional, 
background: {{.BackgroundColor}}, 
lighting: soft, natural, 
target audience: {{.TargetAudience}}, 
include: product name "{{.Name}}" and price "{{.Price}}" in elegant typography`
}
```

---

## 第五部分：视频生成

### 5.1 视频生成方式

```
1. 模板化视频：
   → 固定模板 + 动态素材
   → 适用：产品展示、促销视频

2. AI 视频生成：
   → Runway / Pika / Sora
   → 适用：品牌视频、故事广告

3. 图文转视频：
   → 静态图片 + 动画效果
   → 适用：信息流广告、快速生成
```

### 5.2 代码实现

```go
type VideoGenerator struct {
    templateEngine *TemplateEngine
    aiVideoClient  *AIVideoClient
}

// GenerateVideo 生成视频
func (vg *VideoGenerator) GenerateVideo(ctx context.Context, product ProductInfo) ([]Video, error) {
    videos := make([]Video, 0)
    
    // 1. 模板化视频
    templateVideos, _ := vg.generateTemplateVideo(product)
    videos = append(videos, templateVideos...)
    
    // 2. AI 视频生成
    aiVideos, _ := vg.generateAIVideo(ctx, product)
    videos = append(videos, aiVideos...)
    
    return videos, nil
}

// generateTemplateVideo 模板化视频
func (vg *VideoGenerator) generateTemplateVideo(product ProductInfo) ([]Video, error) {
    // 1. 获取视频模板
    templates := vg.templateEngine.GetVideoTemplates(product.Category)
    
    // 2. 渲染视频
    videos := make([]Video, 0)
    for _, t := range templates {
        video := t.Render(product)
        videos = append(videos, video)
    }
    
    return videos, nil
}

// generateAIVideo AI 视频生成
func (vg *VideoGenerator) generateAIVideo(ctx context.Context, product ProductInfo) ([]Video, error) {
    // 1. 构建 Prompt
    prompt := vg.buildVideoPrompt(product)
    
    // 2. 调用 AI 视频生成 API
    videos, err := vg.aiVideoClient.Generate(ctx, prompt, 2)
    if err != nil {
        return nil, err
    }
    
    return videos, nil
}

// buildVideoPrompt 构建视频 Prompt
func (vg *VideoGenerator) buildVideoPrompt(product ProductInfo) string {
    return `A 15-second product video for {{.Name}}, 
showing {{.SellingPoints}}, 
modern style, professional lighting, 
ending with call-to-action text "{{.CTA}}"`
}
```

---

## 第六部分：尺寸适配

### 6.1 常见广告位尺寸

```
Banner：
→ 320×50 (移动端)
→ 300×250 (中等矩形)
→ 728×90 (Leaderboard)

信息流：
→ 1200×628 (Facebook)
→ 1080×1080 (Square)
→ 1080×1920 (Story)

开屏：
→ 1080×1920 (9:16)
→ 1440×2560 (全屏)

插屏：
→ 320×480
→ 414×736
```

### 6.2 代码实现

```go
type SizeAdapter struct{}

// Adapt 适配尺寸
func (sa *SizeAdapter) Adapt(image Image, targetSize Size) (Image, error) {
    // 1. 裁剪（保持比例）
    cropped := sa.cropToRatio(image, targetSize.Ratio)
    
    // 2. 缩放
    resized := sa.resize(cropped, targetSize.Width, targetSize.Height)
    
    // 3. 添加安全区域（文字不被裁剪）
    final := sa.addSafeArea(resized)
    
    return final, nil
}

// cropToRatio 裁剪到指定比例
func (sa *SizeAdapter) cropToRatio(image Image, ratio float64) Image {
    width := image.Width
    height := image.Height
    imageRatio := float64(width) / float64(height)
    
    var newWidth, newHeight int
    if imageRatio > ratio {
        // 图片比目标宽，裁剪宽度
        newHeight = height
        newWidth = int(float64(height) * ratio)
    } else {
        // 图片比目标高，裁剪高度
        newWidth = width
        newHeight = int(float64(width) / ratio)
    }
    
    // 从中心裁剪
    startX := (width - newWidth) / 2
    startY := (height - newHeight) / 2
    
    return image.Crop(startX, startY, newWidth, newHeight)
}
```

---

## 第七部分：自测题

### 问题 1
AI 生成素材的方式有哪些？

<details>
<summary>查看答案</summary>

1. **模板化生成**：速度快，成本低
2. **AIGC 生成**：质量高，灵活
3. **混合生成**：平衡成本和质量
4. **适用场景**：文案/图片/视频都支持
5. **批量生成**：100 万广告 × 5 素材 = 500 万素材
</details>

### 问题 2
违规词过滤怎么做？

<details>
<summary>查看答案</summary>

1. **黑名单**：广告法禁用词
2. **正则匹配**：快速过滤
3. **LLM 审核**：语义理解
4. **人工审核**：最终把关
5. **实时更新**：黑名单定期更新
</details>

---

*本文档基于广告素材 AI 生成生产实战整理。*