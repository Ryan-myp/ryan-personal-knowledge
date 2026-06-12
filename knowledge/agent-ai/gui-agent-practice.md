# GUI Agent 科普与实战

> 基于 Datawhale hello-agents Extra06 社区贡献整理

---

## 第一部分：入门引导（5 分钟速览）

### 什么是 GUI Agent？

GUI Agent 是能让 AI **看懂屏幕、操作界面**的智能体。它不是通过 API 调用，而是像人一样通过视觉感知和操作。

### GUI Agent 的核心技术架构

| 组件 | 说明 |
|------|------|
| **感知** | 截图 + VLM 理解 UI 布局和元素 |
| **推理** | LLM 决定下一步操作（点击哪里、输入什么） |
| **执行** | 鼠标点击、键盘输入、滚动、拖拽 |

### 主流 GUI Agent 框架对比

| 框架 | 感知方式 | 目标平台 | 特点 |
|------|---------|---------|------|
| **Mobile-Agent** | 截图 + VLM | 手机 | 专注移动端 |
| **SeeClick** | 截图 + 坐标标注 | 桌面 | 精确坐标定位 |
| **OmniParser** | OCR + UI 解析 | 跨平台 | 结构化 UI 理解 |
| **OpenHands** | 混合 (DOM+视觉) | 网页 | Web + 桌面 |
| **Claude Computer Use** | 视觉 + 坐标 | 桌面 | Anthropic 闭源 |

### GUI Agent vs Web Agent vs RPA

| 维度 | RPA | Web Agent | GUI Agent |
|------|-----|-----------|-----------|
| **主要表面** | Web/桌面 | 网页浏览器 | 任意 UI |
| **感知方式** | DOM 选择器 | DOM + 视觉 | 截图 + VLM |
| **抗 UI 变化** | ❌ 立即失效 | ⚠️ 有限 | ✅ 视觉弹性 |
| **跨平台** | 有限 | Web 专用 | 任意平台 |

---

## 第二部分：源码级深度

### 2.1 GUI Agent 核心感知 — Go 实现

```go
package guagent

import (
	"context"
	"encoding/json"
	"fmt"
	"image"
	"image/png"
	"os"
	"os/exec"
	"strings"
)

// Screenshot 截屏
func Screenshot() (*image.RGBA, error) {
	cmd := exec.Command("screencapture", "-x") // macOS
	output, err := cmd.Output()
	if err != nil {
		return nil, fmt.Errorf("screenshot failed: %w", err)
	}
	
	img, err := png.Decode(strings.NewReader(string(output)))
	if err != nil {
		return nil, fmt.Errorf("decode screenshot failed: %w", err)
	}
	
	return img.(*image.RGBA), nil
}

// VisionElement 视觉识别的 UI 元素
type VisionElement struct {
	ID        string  `json:"id"`
	BBox      [4]int  `json:"bbox"` // x, y, width, height
	Label     string  `json:"label"` // "button", "input", "text"
	Text      string  `json:"text"` // 元素文本内容
	Confidence float64 `json:"confidence"`
}

// VLMPerception VLM 感知层
type VLMPerception struct {
	Model      VLMModel // 视觉语言模型
	ScreenShot *image.RGBA
	Elements   []VisionElement
}

type VLMModel interface {
	AnalyzeScreen(screen *image.RGBA) ([]VisionElement, error)
}

// GPT4VPerception 使用 GPT-4V 进行屏幕分析
func (v *VLMPerception) AnalyzeWithGPT4V(ctx context.Context) error {
	// 将截图编码为 base64
	imgData, _ := encodeToBase64(v.ScreenShot)
	
	// 构建 prompt
	prompt := `
分析这张屏幕截图，识别所有可交互元素。

对于每个元素，输出:
- ID: 唯一标识符 (如 "btn_1", "input_1")
- BBox: 边界框 [x, y, width, height]
- Label: 元素类型 (button/input/text/image/link)
- Text: 元素的可见文本
- Confidence: 识别信心 [0.0-1.0]

只输出 JSON 格式，不要其他文字。
`
	
	// 调用 VLM API
	response, err := callVLMAPI(ctx, imgData, prompt)
	if err != nil {
		return err
	}
	
	// 解析响应
	var elements []VisionElement
	if err := json.Unmarshal([]byte(response), &elements); err != nil {
		return err
	}
	
	v.Elements = elements
	return nil
}

// ScreenAction 屏幕操作
type ScreenAction struct {
	Type       string  `json:"type"`       // click/type/scroll/drag
	ElementID  string  `json:"element_id"` // 目标元素 ID
	Position   [2]int  `json:"position"`   // x, y 坐标
	Text       string  `json:"text"`       // 输入文本
	Parameters map[string]interface{} `json:"parameters"`
}

// ScreenExecutor 屏幕执行层
type ScreenExecutor struct{}

// ExecuteAction 执行屏幕操作
func (e *ScreenExecutor) ExecuteAction(ctx context.Context, action ScreenAction) error {
	switch action.Type {
	case "click":
		return e.handleClick(action)
	case "type":
		return e.handleType(action)
	case "scroll":
		return e.handleScroll(action)
	case "drag":
		return e.handleDrag(action)
	default:
		return fmt.Errorf("unknown action type: %s", action.Type)
	}
}

func (e *ScreenExecutor) handleClick(action ScreenAction) error {
	x, y := action.Position[0], action.Position[1]
	// 移动到指定坐标
	if err := mouseMove(x, y); err != nil {
		return fmt.Errorf("mouse move failed: %w", err)
	}
	// 点击
	return click()
}

func (e *ScreenExecutor) handleType(action ScreenAction) error {
	// 先点击目标元素聚焦
	if err := e.clickElement(action.ElementID); err != nil {
		return err
	}
	// 输入文本
	return typeText(action.Text)
}
```

### 2.2 ReAct 循环 — Go 实现

```go
package guagent

// GUIAgent 实现 ReAct (Reason + Act) 循环
type GUIAgent struct {
	Perception  *VLMPerception
	Reasoner    *Reasoner
	Executor    *ScreenExecutor
	MaxSteps    int
}

type Step struct {
	StepNum     int
	Thought     string      // 推理思考
	Action      ScreenAction // 执行动作
	Observation string      // 观察结果
}

func (a *GUIAgent) Run(ctx context.Context, goal string) error {
	var steps []Step
	currentScreen, _ := Screenshot()
	
	for step := 1; step <= a.MaxSteps; step++ {
		// Step 1: 感知屏幕
		a.Perception.ScreenShot = currentScreen
		if err := a.Perception.AnalyzeWithGPT4V(ctx); err != nil {
			return err
		}
		
		// Step 2: 推理
		thought, action := a.Reasoner.Reason(goal, currentScreen, a.Perception.Elements)
		
		// 检查是否完成
		if a.Reasoner.IsGoalCompleted(goal, currentScreen) {
			fmt.Printf("Goal completed in %d steps!\n", step)
			return nil
		}
		
		// Step 3: 执行
		if err := a.Executor.ExecuteAction(ctx, action); err != nil {
			return err
		}
		
		// Step 4: 等待变化
		time.Sleep(500 * time.Millisecond)
		
		// Step 5: 获取新屏幕
		newScreen, _ := Screenshot()
		
		steps = append(steps, Step{
			StepNum:     step,
			Thought:     thought,
			Action:      action,
			Observation: fmt.Sprintf("Clicked element %s, moved to (%d,%d)", 
				action.ElementID, action.Position[0], action.Position[1]),
		})
		
		currentScreen = newScreen
	}
	
	return fmt.Errorf("max steps (%d) exceeded", a.MaxSteps)
}
```

### 2.3 常见 GUI Agent 场景 — Go 实现

```go
package guagent

// 场景 1: 自动化表单填写
func (a *GUIAgent) FillForm(ctx context.Context, formFields map[string]string) error {
	// 1. 识别表单元素
	a.Perception.ScreenShot, _ = Screenshot()
	a.Perception.AnalyzeWithGPT4V(ctx)
	
	// 2. 匹配字段
	for fieldName, value := range formFields {
		element := a.findElementByLabel(fieldName)
		if element == nil {
			return fmt.Errorf("field %s not found", fieldName)
		}
		
		// 3. 输入值
		action := ScreenAction{
			Type:      "type",
			ElementID: element.ID,
			Position:  [2]int{element.BBox[0], element.BBox[1]},
			Text:      value,
		}
		
		if err := a.Executor.ExecuteAction(ctx, action); err != nil {
			return err
		}
	}
	
	return nil
}

// 场景 2: 截图搜索
func (a *GUIAgent) SearchOnScreen(ctx context.Context, keyword string) error {
	// 1. 找到搜索框
	a.Perception.ScreenShot, _ = Screenshot()
	a.Perception.AnalyzeWithGPT4V(ctx)
	
	searchInput := a.findElementByType("input_search")
	if searchInput == nil {
		return fmt.Errorf("search input not found")
	}
	
	// 2. 输入关键词
	action := ScreenAction{
		Type:       "type",
		ElementID:  searchInput.ID,
		Position:   [2]int{searchInput.BBox[0], searchInput.BBox[1]},
		Text:       keyword,
	}
	
	if err := a.Executor.ExecuteAction(ctx, action); err != nil {
		return err
	}
	
	// 3. 点击搜索按钮
	searchBtn := a.findElementByLabel("搜索")
	if searchBtn != nil {
		btnAction := ScreenAction{
			Type:     "click",
			ElementID: searchBtn.ID,
			Position: [2]int{searchBtn.BBox[0], searchBtn.BBox[1]},
		}
		return a.Executor.ExecuteAction(ctx, btnAction)
	}
	
	return nil
}

// 场景 3: 异常检测
func (a *GUIAgent) DetectAnomaly(ctx context.Context) error {
	// 截图并用 VLM 分析
	a.Perception.ScreenShot, _ = Screenshot()
	a.Perception.AnalyzeWithGPT4V(ctx)
	
	// 检查是否有错误信息、弹窗等
	for _, el := range a.Perception.Elements {
		if strings.Contains(strings.ToLower(el.Text), "error") ||
		   strings.Contains(strings.ToLower(el.Text), "警告") {
			return fmt.Errorf("anomaly detected: %s", el.Text)
		}
	}
	
	return nil
}
```

---

## 第三部分：实战注意事项

### 性能优化

1. **截屏频率**: 不要太频繁（建议 2-5 秒一次），避免资源浪费
2. **增量感知**: 只分析变化区域，不需要每次都分析整个屏幕
3. **缓存结果**: 相似 UI 状态可以缓存识别结果
4. **降级策略**: VLM 调用失败时，使用规则-based 回退

### 可靠性保障

1. **元素存在性检查**: 操作前检查元素是否存在
2. **超时机制**: 每个操作设置超时，避免无限等待
3. **重试逻辑**: 操作失败时自动重试 2-3 次
4. **人工介入**: 复杂场景支持人工确认或接管

### 常见失败场景

1. **元素识别失败**: 元素太小、颜色太浅、被遮挡
2. **页面加载**: 操作太快，页面还没加载完
3. **弹窗拦截**: 广告弹窗、确认弹窗干扰正常流程
4. **滚动问题**: 元素在可视区域外

---

## 第四部分：自测题

### 问题 1
GUI Agent 的感知层为什么需要 VLM 而不是传统 CV 模型？

<details>
<summary>查看答案</summary>

1. **语义理解**: VLM 能理解 UI 元素的语义含义（"这是登录按钮"）
2. **泛化能力**: VLM 见过各种 UI，不需要针对每个应用重新训练
3. **文字识别**: VLM 内置 OCR 能力，能直接读取 UI 文字
4. **灵活性**: 不需要预定义元素类型，VLM 能理解任意 UI
5. **多模态**: 同时理解视觉布局 + 文字内容 + 交互意图
6. **局限**: VLM 成本高、速度慢，需要权衡延迟和准确率

</details>

### 问题 2
GUI Agent 的 ReAct 循环中，为什么需要"等待变化"这一步？

<details>
<summary>查看答案</summary>

1. **页面加载**: 操作后页面需要时间渲染变化
2. **避免竞态**: 太快操作下一个元素，可能操作到旧状态
3. **稳定性**: 等待 500ms-2s 让页面稳定，避免误操作
4. **超时控制**: 等待时间过长说明加载失败，需要处理
5. **优化**: 可以用轮询检测变化，而不是固定等待

</details>

### 问题 3
GUI Agent 相比 RPA 的主要优势是什么？

<details>
<summary>查看答案</summary>

1. **抗 UI 变化**: RPA 依赖精确坐标/XPath，UI 一变就失效；GUI Agent 用视觉理解，能弹性适应
2. **无需代码**: RPA 需要开发/维护脚本；GUI Agent 通过自然语言指令工作
3. **泛化能力**: GUI Agent 能理解未见过的 UI；RPA 只能处理预定义场景
4. **复杂交互**: GUI Agent 能处理拖拽、弹窗、验证等复杂场景
5. **缺点**: GUI Agent 速度慢、成本高、不可靠；RPA 速度快、稳定、成本低
6. **适用场景**: RPA 适合简单、稳定的流程；GUI Agent 适合复杂、多变的场景

</details>

---

*本文档基于 Datawhale hello-agents Extra06 社区贡献整理，内容经过精简和 Go 化改造。*
*GUI Agent 的核心：让 AI 像人一样"看"屏幕并操作。*
