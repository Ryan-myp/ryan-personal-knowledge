# 广告模板引擎深度：模板定义/用户上传/动态渲染/版本管理

> 模板系统架构 + 模板 DSL + 动态渲染 + 版本管理 + 模板市场

---

## 第一部分：为什么需要模板引擎？

### 模板系统的价值

```
没有模板系统：
→ 每个广告都要从零制作素材
→ 成本高、效率低
→ 质量参差不齐

有模板系统：
→ 100 个模板 → 100 万广告 × 5 个素材 = 500 万个素材
→ 成本降低 90%
→ 质量统一
→ 快速迭代
```

### 模板类型

```
1. 系统模板：
   → 平台预定义的模板
   → 经过验证的高质量
   → 覆盖主流行业

2. 用户上传模板：
   → 广告主自定义模板
   → 品牌 VI 一致
   → 需要审核

3. AI 生成模板：
   → 基于数据自动优化
   → A/B 测试选出最佳
   → 持续迭代
```

---

## 第二部分：模板 DSL 设计

### 2.1 模板语言设计

```
模板 = 布局 + 变量 + 样式 + 交互

模板 DSL（Domain Specific Language）：
→ 简单、易读、易编辑
→ 支持条件渲染、循环、变量插值
→ 支持多尺寸适配
```

### 2.2 模板格式

```yaml
# 模板定义（YAML 格式）
template:
  id: "ecommerce_banner_001"
  name: "电商 Banner 模板 001"
  category: "电商"
  version: "1.0"
  
  # 画布配置
  canvas:
    width: 1200
    height: 628
    background:
      type: "gradient"
      colors: ["#FF6B6B", "#FFE66D"]
      direction: "diagonal"
  
  # 元素定义
  elements:
    # 商品图片
    - id: "product_image"
      type: "image"
      x: 50
      y: 50
      width: 500
      height: 528
      src: "{{product.image}}"  # 变量
      borderRadius: 12
      
    # 商品名称
    - id: "product_name"
      type: "text"
      x: 580
      y: 80
      width: 570
      height: 100
      text: "{{product.name}}"
      fontSize: 36
      fontWeight: "bold"
      color: "#333333"
      lineHeight: 1.4
      
    # 价格
    - id: "price"
      type: "text"
      x: 580
      y: 200
      width: 570
      height: 60
      text: "¥{{product.price}}"
      fontSize: 48
      fontWeight: "bold"
      color: "#FF6B6B"
      
    # 原价（划线）
    - id: "original_price"
      type: "text"
      x: 580
      y: 270
      width: 570
      height: 40
      text: "¥{{product.original_price}}"
      fontSize: 24
      color: "#999999"
      textDecoration: "line-through"
      
    # 促销标签
    - id: "discount_tag"
      type: "text"
      x: 580
      y: 330
      width: 200
      height: 50
      text: "{{product.discount}}"
      fontSize: 28
      fontWeight: "bold"
      color: "#FFFFFF"
      backgroundColor: "#FF6B6B"
      borderRadius: 25
      
    # 行动号召按钮
    - id: "cta_button"
      type: "button"
      x: 580
      y: 420
      width: 300
      height: 60
      text: "{{product.cta}}"
      fontSize: 24
      fontWeight: "bold"
      color: "#FFFFFF"
      backgroundColor: "#333333"
      borderRadius: 30
      clickAction: "open_url"
      clickUrl: "{{product.link}}"
      
  # 条件渲染
  conditions:
    - id: "show_discount"
      if: "{{product.discount}}"  # 有折扣才显示
      elements: ["discount_tag"]
      
    - id: "show_original_price"
      if: "{{product.original_price}}"  # 有原价才显示
      elements: ["original_price"]
  
  # 多尺寸适配
  responsive:
    - size: "320x50"
      canvas:
        width: 320
        height: 50
      elements:
        - id: "product_name"
          x: 10
          y: 5
          width: 200
          fontSize: 14
        - id: "cta_button"
          x: 220
          y: 5
          width: 90
          height: 40
          fontSize: 12
    - size: "1080x1080"
      canvas:
        width: 1080
        height: 1080
      elements:
        - id: "product_image"
          width: 540
          height: 540
        - id: "product_name"
          x: 560
          y: 100
          fontSize: 40
```

---

## 第三部分：模板渲染引擎

### 3.1 渲染架构

```
模板 DSL → 模板解析器 → AST（抽象语法树） → 渲染器 → HTML/图片/视频
                                    │
                                    └→ 变量替换 → 最终渲染
```

### 3.2 Go 实现

```go
package template

import (
    "bytes"
    "encoding/json"
    "html/template"
    "image"
    "image/color"
    "image/draw"
    "image/png"
    "os"
)

// TemplateEngine 模板引擎
type TemplateEngine struct {
    templateStore *TemplateStore
    renderer      *Renderer
}

// Template 模板
type Template struct {
    ID         string          `json:"id"`
    Name       string          `json:"name"`
    Category   string          `json:"category"`
    Version    string          `json:"version"`
    Canvas     Canvas          `json:"canvas"`
    Elements   []Element       `json:"elements"`
    Conditions []Condition     `json:"conditions"`
    Responsive []Responsive    `json:"responsive"`
}

// Canvas 画布配置
type Canvas struct {
    Width      int             `json:"width"`
    Height     int             `json:"height"`
    Background CanvasBackground `json:"background"`
}

type CanvasBackground struct {
    Type      string   `json:"type"` // solid/gradient/image
    Colors    []string `json:"colors"`
    Direction string   `json:"direction"`
}

// Element 元素
type Element struct {
    ID              string      `json:"id"`
    Type            string      `json:"type"` // image/text/button
    X               int         `json:"x"`
    Y               int         `json:"y"`
    Width           int         `json:"width"`
    Height          int         `json:"height"`
    Src             string      `json:"src"` // 图片 URL
    Text            string      `json:"text"`
    FontSize        int         `json:"font_size"`
    FontWeight      string      `json:"font_weight"`
    Color           string      `json:"color"`
    BackgroundColor string      `json:"background_color"`
    BorderRadius    int         `json:"border_radius"`
    ClickAction     string      `json:"click_action"`
    ClickURL        string      `json:"click_url"`
}

// Condition 条件
type Condition struct {
    ID       string   `json:"id"`
    If       string   `json:"if"` // 条件表达式
    Elements []string `json:"elements"`
}

// RenderRequest 渲染请求
type RenderRequest struct {
    TemplateID string                 `json:"template_id"`
    Data       map[string]interface{} `json:"data"` // 变量数据
    Size       string                 `json:"size"` // 输出尺寸
}

// RenderResult 渲染结果
type RenderResult struct {
    TemplateID string `json:"template_id"`
    ImageURL   string `json:"image_url"`
    Width      int    `json:"width"`
    Height     int    `json:"height"`
    Size       string `json:"size"`
}
```

### 3.3 变量替换

```go
// replaceVariables 替换模板中的变量
func (te *TemplateEngine) replaceVariables(text string, data map[string]interface{}) string {
    // 将 "Hello, {{name}}" 替换为 "Hello, John"
    result := text
    for key, value := range data {
        placeholder := "{{" + key + "}}"
        result = strings.ReplaceAll(result, placeholder, fmt.Sprintf("%v", value))
    }
    return result
}

// evaluateCondition 评估条件
func (te *TemplateEngine) evaluateCondition(condition Condition, data map[string]interface{}) bool {
    // 评估 "{{product.discount}}" 是否为空
    value := data["product"].(map[string]interface{})
    discount, ok := value["discount"]
    if !ok || discount == nil || discount == "" {
        return false
    }
    return true
}
```

### 3.4 图片渲染

```go
// RenderToImage 渲染为图片
func (te *TemplateEngine) RenderToImage(req *RenderRequest) (*RenderResult, error) {
    // 1. 获取模板
    tpl, err := te.templateStore.GetTemplate(req.TemplateID)
    if err != nil {
        return nil, err
    }
    
    // 2. 获取画布尺寸
    canvas := tpl.Canvas
    if req.Size != "" {
        // 使用响应式尺寸
        for _, r := range tpl.Responsive {
            if r.Size == req.Size {
                canvas = r.Canvas
                break
            }
        }
    }
    
    // 3. 创建画布
    img := image.NewRGBA(image.Rect(0, 0, canvas.Width, canvas.Height))
    
    // 4. 绘制背景
    te.drawBackground(img, canvas.Background)
    
    // 5. 渲染元素
    for _, elem := range tpl.Elements {
        // 评估条件
        if !te.isElementVisible(elem, tpl.Conditions, req.Data) {
            continue
        }
        
        // 替换变量
        text := te.replaceVariables(elem.Text, req.Data)
        src := te.replaceVariables(elem.Src, req.Data)
        
        // 绘制元素
        te.drawElement(img, elem, text, src)
    }
    
    // 6. 保存图片
    var buf bytes.Buffer
    png.Encode(&buf, img)
    
    imageURL := te.oss.Upload(buf.Bytes(), "templates/"+req.TemplateID+".png")
    
    return &RenderResult{
        TemplateID: req.TemplateID,
        ImageURL:   imageURL,
        Width:      canvas.Width,
        Height:     canvas.Height,
        Size:       req.Size,
    }, nil
}

// drawBackground 绘制背景
func (te *TemplateEngine) drawBackground(img *image.RGBA, bg CanvasBackground) {
    switch bg.Type {
    case "solid":
        c := te.parseColor(bg.Colors[0])
        draw.Draw(img, img.Bounds(), image.NewUniform(c), image.Point{}, draw.Src)
    case "gradient":
        te.drawGradient(img, bg.Colors, bg.Direction)
    case "image":
        // 加载背景图片
    }
}

// drawElement 绘制元素
func (te *TemplateEngine) drawElement(img *image.RGBA, elem Element, text, src string) {
    switch elem.Type {
    case "image":
        te.drawImageElement(img, elem, src)
    case "text":
        te.drawTextElement(img, elem, text)
    case "button":
        te.drawButtonElement(img, elem, text)
    }
}
```

---

## 第四部分：模板市场

### 4.1 模板分类

```
电商：
→ Banner 模板（6 个）
→ 信息流模板（8 个）
→ 开屏模板（4 个）

游戏：
→ 下载引导（3 个）
→ 版本更新（2 个）
→ 活动推广（5 个）

教育：
→ 课程推广（4 个）
→ 优惠促销（3 个）

金融：
→ 理财产品（3 个）
→ 信用卡（2 个）
```

### 4.2 模板上传

```go
// UploadTemplate 上传模板
func (tm *TemplateMarket) UploadTemplate(userID string, file *multipart.FileHeader) (*Template, error) {
    // 1. 解析模板文件（JSON/YAML）
    tpl, err := parseTemplateFile(file)
    if err != nil {
        return nil, err
    }
    
    // 2. 验证模板
    if err := tm.validateTemplate(tpl); err != nil {
        return nil, err
    }
    
    // 3. 设置默认值
    tpl.ID = generateUUID()
    tpl.CreatorID = userID
    tpl.Status = "pending" // 待审核
    
    // 4. 保存模板
    tm.templateStore.Save(tpl)
    
    // 5. 触发审核
    go tm.auditService.AuditTemplate(tpl.ID)
    
    return tpl, nil
}

// validateTemplate 验证模板
func (tm *TemplateMarket) validateTemplate(tpl *Template) error {
    // 1. 检查必填字段
    if tpl.Canvas.Width == 0 || tpl.Canvas.Height == 0 {
        return fmt.Errorf("canvas size is required")
    }
    
    // 2. 检查元素数量
    if len(tpl.Elements) == 0 {
        return fmt.Errorf("at least one element is required")
    }
    
    // 3. 检查元素重叠
    if tm.hasElementOverlap(tpl.Elements) {
        return fmt.Errorf("elements overlap")
    }
    
    // 4. 检查变量引用
    if err := tm.checkVariableReferences(tpl); err != nil {
        return err
    }
    
    return nil
}
```

---

## 第五部分：版本管理

### 5.1 版本管理

```
模板版本：
→ v1.0：初始版本
→ v1.1：优化样式
→ v2.0：重大变更

版本控制：
→ Git 风格：commit/branch/tag
→ 回滚：支持任意版本回滚
→ 对比：版本差异对比
```

### 5.2 代码实现

```go
// TemplateVersion 模板版本
type TemplateVersion struct {
    ID        string    `json:"id"`
    TemplateID string   `json:"template_id"`
    Version   string    `json:"version"`
    Content   []byte    `json:"content"` // 模板 DSL
    Comment   string    `json:"comment"` // 变更说明
    CreatedAt time.Time `json:"created_at"`
    CreatedBy string    `json:"created_by"`
}

// VersionManager 版本管理器
type VersionManager struct {
    db *Database
}

// CreateVersion 创建新版本
func (vm *VersionManager) CreateVersion(templateID, version, comment, createdBy string, content []byte) error {
    version := &TemplateVersion{
        TemplateID: templateID,
        Version:    version,
        Content:    content,
        Comment:    comment,
        CreatedBy:  createdBy,
    }
    
    return vm.db.SaveVersion(version)
}

// Rollback 回滚到指定版本
func (vm *VersionManager) Rollback(templateID, targetVersion string) error {
    version, err := vm.db.GetVersion(templateID, targetVersion)
    if err != nil {
        return err
    }
    
    // 恢复模板内容
    return vm.db.UpdateTemplateContent(templateID, version.Content)
}

// GetDiff 获取版本差异
func (vm *VersionManager) GetDiff(templateID, version1, version2 string) (*VersionDiff, error) {
    v1, _ := vm.db.GetVersion(templateID, version1)
    v2, _ := vm.db.GetVersion(templateID, version2)
    
    // 对比两个版本的 DSL
    diff := compareDsl(v1.Content, v2.Content)
    
    return &VersionDiff{
        TemplateID: templateID,
        Version1:   version1,
        Version2:   version2,
        Changes:    diff,
    }, nil
}
```

---

## 第六部分：自测题

### 问题 1
模板 DSL 包含哪些部分？

<details>
<summary>查看答案</summary>

1. **画布配置**：尺寸/背景
2. **元素定义**：图片/文字/按钮
3. **变量插值**：{{variable}}
4. **条件渲染**：if/else
5. **响应式适配**：多尺寸
</details>

### 问题 2
版本管理支持哪些操作？

<details>
<summary>查看答案</summary>

1. **创建版本**：每次修改生成新版本
2. **回滚**：恢复到任意版本
3. **对比**：版本差异对比
4. **标签**：v1.0/v2.0
5. **记录**：谁在什么时候改了什么
</details>

---

*本文档基于广告模板引擎生产实战整理。*