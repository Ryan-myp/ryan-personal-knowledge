# 广告创意管理深度：创意上传/审核/分类/生成

> 广告素材管理 + AI 审核 + 分类 + 生成 + 审核流程

---

## 第一部分：广告创意管理的核心挑战

### 创意管理的业务场景

```
1. 创意上传：
   → 图片/视频/文案/落地页
   → 格式验证（尺寸/大小/类型）
   → 压缩优化

2. 创意审核：
   → 内容安全（违规内容检测）
   → 广告法合规（禁用词检测）
   → 品牌安全（不适配内容）

3. 创意分类：
   → 类目识别（电商/游戏/教育）
   → 标签提取（颜色/场景/人物）
   → 相似去重

4. 创意生成：
   → A/B 测试素材自动生成
   → 个性化创意生成
   → 模板化创意生成
```

### 数据量估算

```
100 万广告 × 每个广告 5 个创意 × 每个创意 500KB
= 2.5TB 创意数据

每天新增：
→ 10 万新创意
→ 50GB 新增数据
```

---

## 第二部分：创意管理系统架构

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                    广告创意管理系统                           │
└─────────────────────────────────────────────────────────────┘

                    ┌───────────────────────────────────────┐
                    │         广告主后台                      │
                    │  - 创意上传                            │
                    │  - 创意管理                            │
                    │  - 审核状态查询                        │
                    └──────────────┬────────────────────────┘
                                   │
                    ┌──────────────▼────────────────────────┐
                    │       Creative Service (Go)           │
                    │  - 创意上传                            │
                    │  - 创意审核                            │
                    │  - 创意分类                            │
                    │  - 创意生成                            │
                    └──────┬──────────┬──────────┬──────────┘
                           │          │          │
              ┌────────────▼──┐ ┌─────▼────┐ ┌───▼────────┐
              │   OSS         │ │ AI Service│ │ MySQL      │
              │  - 图片/视频  │ │ - AI 审核 │ │ - 创意信息 │
              │  - CDN 分发   │ │ - 分类    │ │ - 审核记录 │
              └───────────────┘ └──────────┘ └────────────┘
```

### 2.2 核心表结构

```sql
-- 创意表
CREATE TABLE creative (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    ad_id           BIGINT NOT NULL,           -- 关联广告 ID
    name            VARCHAR(255) NOT NULL,     -- 创意名称
    type            TINYINT NOT NULL,          -- 类型（1=图片, 2=视频, 3=图文）
    url             VARCHAR(1024) NOT NULL,    -- 创意 URL
    thumb_url       VARCHAR(1024),             -- 缩略图 URL
    width           INT,                       -- 宽度
    height          INT,                       -- 高度
    duration        INT,                       -- 时长（视频）
    size            INT,                       -- 大小（字节）
    format          VARCHAR(32),               -- 格式（jpg/png/mp4）
    status          TINYINT DEFAULT 0,         -- 状态（0=待审核, 1=通过, 2=拒绝, 3=审核中）
    reject_reason   VARCHAR(512),              -- 拒绝原因
    ai_score        DECIMAL(5,4),             -- AI 审核分数
    ai_labels       JSON,                      -- AI 标签
    categories      JSON,                      -- 类目
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_ad_id (ad_id),
    INDEX idx_status (status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 创意审核记录表
CREATE TABLE creative_audit (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    creative_id     BIGINT NOT NULL,
    auditor_id      BIGINT,                    -- 审核员 ID（AI 审核为 NULL）
    audit_result    TINYINT NOT NULL,          -- 结果（1=通过, 2=拒绝）
    audit_reason    VARCHAR(512),              -- 原因
    audit_type      TINYINT NOT NULL,          -- 审核类型（1=AI, 2=人工）
    audit_time      DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_creative_id (creative_id),
    INDEX idx_audit_time (audit_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

---

## 第三部分：创意上传

### 3.1 上传流程

```
1. 广告主上传创意 → Creative Service
2. 格式验证 → 拒绝非法格式
3. 压缩优化 → 图片压缩/视频转码
4. 上传到 OSS → 返回 URL
5. 生成缩略图（图片/视频）
6. 创建创意记录 → status=0（待审核）
7. 触发 AI 审核 → status=2（审核中）
```

### 3.2 代码实现

```go
package creative

import (
    "context"
    "fmt"
    "image"
    "mime/multipart"
    "os"
    "time"
)

type CreativeService struct {
    db       *Database
    oss      *OSSClient
    aiService *AIService
    thumbnail *ThumbnailGenerator
}

type Creative struct {
    ID         int64
    AdID       int64
    Name       string
    Type       int    // 1=图片, 2=视频, 3=图文
    URL        string
    ThumbURL   string
    Width      int
    Height     int
    Duration   int    // 视频时长
    Size       int64
    Format     string
    Status     int    // 0=待审核, 1=通过, 2=拒绝, 3=审核中
    RejectReason string
    AIScore    float64
    AILabels   map[string]interface{}
    Categories map[string]interface{}
}

// UploadCreative 上传创意
func (svc *CreativeService) UploadCreative(ctx context.Context, adID int64, file *multipart.FileHeader, name string) (*Creative, error) {
    // 1. 验证文件格式
    allowedFormats := map[string]bool{
        "jpg": true, "jpeg": true, "png": true, "gif": true,
        "mp4": true, "mov": true, "avi": true,
    }
    ext := getFileExtension(file.Filename)
    if !allowedFormats[ext] {
        return nil, fmt.Errorf("unsupported format: %s", ext)
    }
    
    // 2. 验证文件大小（图片 10MB, 视频 100MB）
    maxSize := int64(10) << 20 // 10MB
    if ext == "mp4" || ext == "mov" {
        maxSize = int64(100) << 20 // 100MB
    }
    if file.Size > maxSize {
        return nil, fmt.Errorf("file too large: %d bytes", file.Size)
    }
    
    // 3. 打开文件
    fileReader, err := file.Open()
    if err != nil {
        return nil, err
    }
    defer fileReader.Close()
    
    // 4. 上传到 OSS
    objectKey := fmt.Sprintf("creatives/%d/%d.%s", adID, time.Now().UnixNano(), ext)
    url, err := svc.oss.Upload(ctx, fileReader, file.Size, objectKey, file.Header.Get("Content-Type"))
    if err != nil {
        return nil, err
    }
    
    // 5. 获取图片/视频信息
    width, height, duration := svc.getImageInfo(objectKey)
    
    // 6. 生成缩略图
    thumbURL := ""
    if ext == "jpg" || ext == "png" {
        thumbURL = svc.generateImageThumb(ctx, url, 200, 200)
    } else if ext == "mp4" || ext == "mov" {
        thumbURL = svc.generateVideoThumb(ctx, url, 1) // 第 1 秒截图
    }
    
    // 7. 创建创意记录
    creative := &Creative{
        AdID:       adID,
        Name:       name,
        Type:       getCreativeType(ext),
        URL:        url,
        ThumbURL:   thumbURL,
        Width:      width,
        Height:     height,
        Duration:   duration,
        Size:       file.Size,
        Format:     ext,
        Status:     0, // 待审核
    }
    
    svc.db.CreateCreative(creative)
    
    // 8. 触发 AI 审核
    go svc.aiService.AuditCreative(creative.ID, url, creative.Type)
    
    return creative, nil
}

// getImageInfo 获取图片/视频信息
func (svc *CreativeService) getImageInfo(objectKey string) (width, height, duration int) {
    // 下载文件到临时目录
    tmpFile, _ := svc.oss.Download(objectKey)
    defer os.Remove(tmpFile)
    
    // 判断类型
    if isImage(objectKey) {
        img, _ := image.DecodeFile(tmpFile)
        return img.Bounds().Dx(), img.Bounds().Dy(), 0
    } else if isVideo(objectKey) {
        duration, _ := getVideoDuration(tmpFile)
        return 0, 0, duration
    }
    return 0, 0, 0
}
```

---

## 第四部分：AI 审核

### 4.1 审核流程

```
1. 图片审核：
   → 敏感内容检测（色情/暴力/政治）
   → 广告法违规检测（违禁词）
   → 品牌安全检测（不适配内容）

2. 视频审核：
   → 逐帧采样（每秒 1 帧）
   → 每帧做图片审核
   → 音频审核（敏感词检测）

3. 审核结果：
   → AI 审核：分数 0-1，≥0.8 自动通过
   → 人工审核：分数 < 0.8 转人工
```

### 4.2 代码实现

```go
package ai

import (
    "context"
    "fmt"
)

type AIService struct {
    contentModeration *ContentModerationClient
    adLawChecker      *AdLawChecker
    brandSafety       *BrandSafetyChecker
}

type AuditResult struct {
    CreativeID int64
    Score      float64   // 0-1，越高越安全
    Labels     map[string]interface{}
    Categories map[string]interface{}
    Passed     bool
    Reason     string
}

// AuditCreative AI 审核创意
func (svc *AIService) AuditCreative(creativeID int64, url string, creativeType int) error {
    switch creativeType {
    case 1: // 图片
        return svc.auditImage(creativeID, url)
    case 2: // 视频
        return svc.auditVideo(creativeID, url)
    case 3: // 图文
        return svc.auditMixed(creativeID, url)
    }
    return fmt.Errorf("unknown creative type: %d", creativeType)
}

// auditImage 审核图片
func (svc *AIService) auditImage(creativeID int64, url string) error {
    // 1. 敏感内容检测
    moderationResult, err := svc.contentModeration.Detect(url)
    if err != nil {
        return err
    }
    
    // 2. 广告法合规检测
    adLawResult, err := svc.adLawChecker.Check(url)
    if err != nil {
        return err
    }
    
    // 3. 品牌安全检测
    brandResult, err := svc.brandSafety.Check(url)
    if err != nil {
        return err
    }
    
    // 4. 综合评分
    score := moderationResult.Score * 0.5 + adLawResult.Score * 0.3 + brandResult.Score * 0.2
    
    // 5. 生成标签
    labels := map[string]interface{}{
        "colors":       moderationResult.Colors,
        "objects":      moderationResult.Objects,
        "text":         adLawResult.Text,
        "categories":   brandResult.Categories,
    }
    
    // 6. 判断是否通过
    passed := score >= 0.8
    reason := ""
    if !passed {
        reason = fmt.Sprintf("AI 审核分数 %.2f 低于阈值 0.8，转人工审核", score)
    }
    
    // 7. 更新创意状态
    // ...
    
    return nil
}

// auditVideo 审核视频
func (svc *AIService) auditVideo(creativeID int64, url string) error {
    // 1. 视频逐帧采样
    frames, err := svc.extractFrames(url, 1) // 每秒 1 帧
    if err != nil {
        return err
    }
    
    // 2. 每帧审核
    var minScore float64 = 1.0
    for _, frame := range frames {
        score, err := svc.contentModeration.DetectFromBytes(frame)
        if err != nil {
            continue
        }
        if score < minScore {
            minScore = score
        }
    }
    
    // 3. 音频审核
    audioResult, err := svc.contentModeration.CheckAudio(url)
    if err != nil {
        return err
    }
    
    // 4. 综合评分
    score := minScore * 0.7 + audioResult.Score * 0.3
    
    // 5. 判断是否通过
    passed := score >= 0.8
    // ...
    
    return nil
}
```

---

## 第五部分：创意分类

### 5.1 分类流程

```
1. 类目识别：
   → 电商/游戏/教育/金融/游戏...
   → 使用图像分类模型

2. 标签提取：
   → 颜色标签（红/蓝/绿）
   → 场景标签（室内/室外/城市/自然）
   → 人物标签（男性/女性/儿童）

3. 相似去重：
   → 计算创意相似度
   → 拒绝重复创意
```

### 5.2 代码实现

```go
package ai

import (
    "context"
    "embed"
)

type CategoryClassifier struct {
    model  *ImageClassificationModel
}

// Classify 分类创意
func (cc *CategoryClassifier) Classify(ctx context.Context, url string) (*ClassificationResult, error) {
    // 1. 图像分类
    categories, err := cc.model.Predict(url)
    if err != nil {
        return nil, err
    }
    
    // 2. 标签提取
    labels := cc.extractLabels(url)
    
    // 3. 相似去重
    isDuplicate := cc.checkDuplicate(url)
    
    return &ClassificationResult{
        Categories:  categories,
        Labels:      labels,
        IsDuplicate: isDuplicate,
    }, nil
}

// 分类结果
type ClassificationResult struct {
    Categories  []string           // ["电商", "服装"]
    Labels      map[string][]string // {"colors": ["red", "blue"], "scenes": ["indoor"]}
    IsDuplicate bool               // 是否重复
}
```

---

## 第六部分：自测题

### 问题 1
广告创意审核的流程是什么？

<details>
<summary>查看答案</summary>

1. **上传**：格式验证 → 压缩 → OSS
2. **AI 审核**：敏感内容 → 广告法合规 → 品牌安全
3. **评分**：综合评分 ≥0.8 自动通过
4. **人工审核**：<0.8 转人工
5. **状态更新**：通过/拒绝
</details>

### 问题 2
视频审核为什么逐帧采样？

<details>
<summary>查看答案</summary>

1. **视频 = 多帧图片**
2. **逐帧审核**：每秒 1 帧
3. **取最低分**：任一模糊都拒绝
4. **音频审核**：敏感词检测
5. **综合评分**：帧审核 × 0.7 + 音频 × 0.3
</details>

---

*本文档基于广告创意管理生产实战整理。*