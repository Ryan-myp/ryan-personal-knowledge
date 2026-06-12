# Web Agent 科普与实战

> 基于 Datawhale hello-agents Extra11 社区贡献整理

---

## 第一部分：入门引导（5 分钟速览）

### 什么是 Web Agent？

Web Agent 是以**网页浏览器**为主要行动表面的自主智能体。它通过 DOM、可访问性树和屏幕截图的组合来感知页面，用 LLM 推理下一步动作，然后在真实浏览器里执行——点击、输入、滚动、跳转。

### 核心架构：感知 → 推理 → 行动

| 层级 | 职责 | 关键技术 |
|------|------|---------|
| **感知** | 理解页面内容 | DOM 解析、截图 + VLM、混合感知 |
| **推理** | 决定下一步 | LLM 规划、记忆、反思 |
| **行动** | 执行操作 | Playwright/CDP、点击、输入、导航 |

### 三种感知策略对比

| 策略 | 优点 | 缺点 | 适用场景 |
|------|------|------|---------|
| **基于 DOM** | 快速、精准、成本低 | 无法处理 Canvas/Shadow DOM | 结构化网页 |
| **基于视觉** | 通用性强、能处理任何 UI | 慢、贵、易幻觉 | 复杂 SPA |
| **混合（推荐）** | 视觉理解布局 + DOM 精确定位 | 实现复杂 | 生产环境 |

### Web Agent vs RPA vs GUI Agent

| 维度 | RPA | Web Agent | GUI Agent |
|------|-----|-----------|-----------|
| **感知** | DOM 选择器 | DOM + 视觉 | 截图 + VLM |
| **抗 UI 变化** | ❌ | ⚠️ | ✅ |
| **反爬意识** | ❌ | ✅ 必需 | ❌ |
| **认证处理** | 手动 | 一等公民 | 有限 |
| **跨平台** | 有限 | Web 专用 | 任意平台 |

---

## 第二部分：源码级深度

### 2.1 Web Agent 核心实现 — Go 实现

```go
package webagent

import (
	"context"
	"fmt"
	"time"
	
	"github.com/playwright-community/playwright-go"
)

// WebAgent Web 智能体核心
type WebAgent struct {
	pw       *playwright.Playwright
	browser  *playwright.Browser
	page     *playwright.Page
	perception *Perception
	reasoner   *Reasoner
	maxSteps int
}

// Perception 感知层：DOM + 视觉混合
type Perception struct {
	DOMInfo    DOMInfo
	Screenshot []byte
	VLMResult  VLMAnalysis
}

// DOMInfo 从 DOM 提取的结构化信息
type DOMInfo struct {
	URL        string
	Title      string
	Elements   []UIElement
	Forms      []FormData
}

// UIElement DOM 中的可交互元素
type UIElement struct {
	Tag        string   // button, input, a, div
	Role       string   // button, textbox, link
	Text       string   // 可见文本
	AriaLabel  string   // 无障碍标签
	ID         string   // 元素 ID
	Classes    []string // CSS 类
	Attributes map[string]string
	BBox       [4]int   // x, y, width, height
}

// Reasoner 推理层
type Reasoner struct {
	LLMClient LLMClient
	History   []Step
}

// Step ReAct 循环中的一步
type Step struct {
	StepNum     int
	Thought     string
	Action      Action
	Observation string
}

// Action 要执行的动作
type Action struct {
	Type       string // click, type, scroll, navigate, extract
	Selector   string // CSS 选择器
	Text       string // 输入文本
	Parameters map[string]interface{}
}

// NewWebAgent 创建 Web Agent
func NewWebAgent() (*WebAgent, error) {
	pw, err := playwright.Run()
	if err != nil {
		return nil, fmt.Errorf("start playwright: %w", err)
	}
	
	browser, err := pw.Chromium.Launch(&playwright.BrowserTypeLaunchOptions{
		Headless: playwright.Bool(true),
		Args: playwright.StringArray{
			"--disable-blink-features=AutomationControlled",
			"--no-sandbox",
		},
	})
	if err != nil {
		return nil, err
	}
	
	page, err := browser.NewPage()
	if err != nil {
		return nil, err
	}
	
	return &WebAgent{
		pw:       pw,
		browser:  browser,
		page:     page,
		perception: &Perception{},
		reasoner: &Reasoner{
			History: make([]Step, 0),
		},
		maxSteps: 20,
	}, nil
}

// Run 执行 Web Agent 主循环
func (a *WebAgent) Run(ctx context.Context, goal string) error {
	for step := 1; step <= a.maxSteps; step++ {
		// 1. 感知
		if err := a.perceive(); err != nil {
			return err
		}
		
		// 2. 推理
		step, err := a.reasoner.Reason(goal, a.perception)
		if err != nil {
			return err
		}
		
		// 3. 执行
		if err := a.execute(step.Action); err != nil {
			return err
		}
		
		a.reasoner.History = append(a.reasoner.History, step)
		
		// 4. 检查是否完成
		if a.isGoalCompleted(goal, step.Observation) {
			fmt.Printf("Goal completed in %d steps!\n", step)
			return nil
		}
	}
	
	return fmt.Errorf("max steps (%d) exceeded", a.maxSteps)
}

// perceive 执行感知（DOM + 视觉混合）
func (a *WebAgent) perceive() error {
	// 1. 提取 DOM 信息
	domInfo, err := a.extractDOM()
	if err != nil {
		return err
	}
	a.perception.DOMInfo = domInfo
	
	// 2. 截图（用于视觉辅助）
	screenshot, err := a.page.Screenshot(&playwright.PageScreenshotOptions{
		FullPage: playwright.Bool(true),
	})
	if err != nil {
		return err
	}
	a.perception.Screenshot = screenshot
	
	return nil
}

// extractDOM 从页面提取结构化 DOM 信息
func (a *WebAgent) extractDOM() (DOMInfo, error) {
	domInfo := DOMInfo{}
	
	// 获取 URL 和标题
	url, _ := a.page.URL()
	title, _ := a.page.Title()
	domInfo.URL = url
	domInfo.Title = title
	
	// 提取可交互元素
	elements, err := a.page.Evaluate(`() => {
		const elements = [];
		const interactiveTags = ['button', 'input', 'a', 'select', 'textarea'];
		document.querySelectorAll('*').forEach(el => {
			if (interactiveTags.includes(el.tagName.toLowerCase())) {
				elements.push({
					tag: el.tagName.toLowerCase(),
					role: el.getAttribute('role') || '',
					text: el.textContent?.trim()?.substring(0, 100) || '',
					ariaLabel: el.getAttribute('aria-label') || '',
					id: el.id || '',
					classes: el.className?.split(' ') || [],
					attributes: Object.fromEntries(Array.from(el.attributes).map(a => [a.name, a.value])),
					rect: el.getBoundingClientRect()
				});
			}
		});
		return elements;
	}`)
	
	if err != nil {
		return domInfo, err
	}
	
	// 解析 elements
	elementsJSON, _ := json.Marshal(elements)
	json.Unmarshal(elementsJSON, &domInfo.Elements)
	
	return domInfo, nil
}

// execute 执行动作
func (a *WebAgent) execute(action Action) error {
	switch action.Type {
	case "click":
		return a.page.Click(action.Selector, playwright.PageClickOptions{
			Timeout: playwright.Float(5.0),
		})
	case "type":
		return a.page.Fill(action.Selector, action.Text)
	case "navigate":
		return a.page.Goto(action.Parameters["url"].(string))
	case "scroll":
		return a.page.Evaluate(fmt.Sprintf(
			"window.scrollTo(0, %d)", action.Parameters["y"].(float64)),
		)
	case "extract":
		return a.extractInformation(action)
	default:
		return fmt.Errorf("unknown action type: %s", action.Type)
	}
}
```

### 2.2 反爬绕过 — Go 实现

```go
package webagent

// AntiBot 反爬绕过策略
type AntiBot struct {
	page *playwright.Page
}

// NewAntiBot 创建反爬配置
func NewAntiBot(page *playwright.Page) *AntiBot {
	return &AntiBot{page: page}
}

// StealthMode 隐身模式：绕过常见反爬检测
func (a *AntiBot) StealthMode() error {
	// 1. 移除 webdriver 标志
	err := a.page.Evaluate(`() => {
		Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
		window.chrome = {runtime: {}};
		navigator.plugins.length = 1;
		navigator.languages = ['en-US', 'en'];
	}`)
	if err != nil {
		return err
	}
	
	// 2. 设置合理的 viewport
	err = a.page.SetViewportSize(1920, 1080)
	if err != nil {
		return err
	}
	
	// 3. 添加用户代理
	err = a.page.SetExtraHTTPHeaders(map[string]string{
		"Accept-Language": "en-US,en;q=0.9",
		"User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
	})
	
	return err
}

// HandleCAPTCHA 处理验证码（简化版）
func (a *AntiBot) HandleCAPTCHA() error {
	// 检测是否有验证码
	hasCaptcha, _ := a.page.Evaluate(`() => {
		return !!document.querySelector('.captcha, #captcha, .geetest');
	}`)
	
	if hasCaptcha.(bool) {
		// 策略 1: 等待人工输入
		fmt.Println("CAPTCHA detected, waiting for manual input...")
		time.Sleep(30 * time.Second)
		
		// 策略 2: 尝试自动求解（需要第三方服务）
		// captchaText := solveCAPTCHAWithService()
		// a.page.Fill('#captcha_input', captchaText)
	}
	
	return nil
}

// RateLimiting 速率限制：模拟人类操作节奏
func (a *AntiBot) RateLimiting() error {
	// 随机延迟（模拟人类阅读时间）
	delay := time.Duration(rand.Intn(2000) + 1000) // 1-3 秒
	time.Sleep(delay)
	
	// 随机滚动（模拟人类浏览）
	scrollAmount := rand.Intn(500) + 200
	_, err := a.page.Evaluate(fmt.Sprintf(
		"window.scrollBy(0, %d)", scrollAmount,
	))
	
	return err
}
```

### 2.3 混合感知策略 — Go 实现

```go
package webagent

// MixedPerception 混合感知：视觉 + DOM
type MixedPerception struct {
	domElements []UIElement
	vlmElements []VisionElement
}

// AnalyzePage 混合分析页面
func (mp *MixedPerception) AnalyzePage(domInfo DOMInfo, screenshot []byte) ([]ActionCandidate, error) {
	var candidates []ActionCandidate
	
	// 1. 从 DOM 提取结构化信息
	for _, el := range domInfo.Elements {
		candidates = append(candidates, ActionCandidate{
			Type:       el.Tag,
			Selector:   fmt.Sprintf("%s%s%s", 
				el.ID, el.AriaLabel, el.Text),
			Text:       el.Text,
			Confidence: 0.9, // DOM 识别通常很准确
			Source:     "dom",
		})
	}
	
	// 2. 用 VLM 分析截图（补充 DOM 无法识别的部分）
	vlmResult, err := callVLMAPI(screenshot, "分析页面，识别所有可交互元素")
	if err != nil {
		return candidates, err
	}
	
	// 3. 合并结果
	for _, vlmEl := range vlmResult.Elements {
		// 检查是否已在 DOM 中找到
		found := false
		for _, domEl := range candidates {
			if domEl.Text == vlmEl.Text && domEl.Source == "dom" {
				found = true
				break
			}
		}
		
		if !found {
			// VLM 发现的额外元素
			candidates = append(candidates, ActionCandidate{
				Type:       vlmEl.Type,
				Selector:   fmt.Sprintf("x,y:%d,%d", vlmEl.X, vlmEl.Y),
				Text:       vlmEl.Text,
				Confidence: 0.7, // VLM 置信度较低
				Source:     "vision",
			})
		}
	}
	
	return candidates, nil
}

// ActionCandidate 动作候选
type ActionCandidate struct {
	Type       string
	Selector   string
	Text       string
	Confidence float64
	Source     string // "dom" or "vision"
}

// SelectBestAction 选择最佳动作
func (mp *MixedPerception) SelectBestAction(goal string, candidates []ActionCandidate) *ActionCandidate {
	// 优先选择 DOM 识别的结果（更准确）
	var best *ActionCandidate
	bestScore := 0.0
	
	for i, c := range candidates {
		score := c.Confidence
		if c.Source == "dom" {
			score *= 1.5 // DOM 结果加分
		}
		
		// 文本匹配度（与目标相关）
		if strings.Contains(strings.ToLower(c.Text), strings.ToLower(goal)) {
			score *= 2.0
		}
		
		if score > bestScore {
			bestScore = score
			best = &candidates[i]
		}
	}
	
	return best
}
```

---

## 第三部分：实战注意事项

### 可靠性保障

1. **元素定位**: 优先用 CSS 选择器，备选用坐标
2. **超时控制**: 每个操作设置合理超时
3. **重试机制**: 网络波动时自动重试
4. **状态检查**: 操作前检查页面状态

### 反爬策略

1. **隐身模式**: 移除 webdriver 标志
2. **用户代理**: 使用常见浏览器 UA
3. **速率限制**: 模拟人类操作节奏
4. **Cookie 管理**: 保持登录状态

### 性能优化

1. **DOM 缓存**: 避免重复解析
2. **懒加载**: 只加载可见区域
3. **并发**: 多个 Web Agent 并行执行

---

## 第四部分：自测题

### 问题 1
为什么生产级 Web Agent 普遍采用混合感知策略？

<details>
<summary>查看答案</summary>

1. **DOM 优势**: 快速、精准、成本低，能直接获取元素类型和文本
2. **DOM 劣势**: 无法处理 Canvas 渲染、Shadow DOM、动态加载内容
3. **视觉优势**: 能处理任何 UI，包括 Canvas 和复杂动画
4. **视觉劣势**: 慢、贵、易产生幻觉
5. **混合策略**: 视觉理解布局 + DOM 精确定位，取长补短
6. **业界实践**: Anthropic Computer Use、OpenAI Operator、Browser-Use 都采用混合方案

</details>

### 问题 2
Web Agent 为什么要处理反爬？这和普通爬虫有什么区别？

<details>
<summary>查看答案</summary>

1. **反爬普遍**: Cloudflare、DataDome、PerimeterX 等广泛使用
2. **指纹识别**: 浏览器指纹、行为生物特征分析
3. **行为检测**: 检测自动化操作模式（速度、轨迹）
4. **与普通爬虫区别**: 
   - 爬虫：批量抓取，追求速度
   - Web Agent：模拟人类交互，追求稳定
5. **绕过策略**: 隐身模式、速率限制、Cookie 管理、CAPTCHA 处理
6. **道德考量**: 尊重 robots.txt，不恶意攻击目标网站

</details>

### 问题 3
Web Agent 的 ReAct 循环中，为什么需要记忆和反思机制？

<details>
<summary>查看答案</summary>

1. **记忆作用**: 
   - 记住已访问的页面，避免重复
   - 记住成功的路径，加速类似任务
   - 记住失败的经验，避免重蹈覆辙
2. **反思作用**: 
   - 分析当前步骤是否偏离目标
   - 判断是否需要改变策略
   - 从错误中学习，改进后续行为
3. **状态管理**: 网页状态会变化，需要跟踪当前状态
4. **长链路任务**: 复杂任务需要多步协作，记忆是关键
5. **Go 实现**: 用 map 存储访问历史，用 LLM 反思当前策略

</details>

---

*本文档基于 Datawhale hello-agents Extra11 社区贡献整理，内容经过精简和 Go 化改造。*
*Web Agent 的核心：让 AI 学会"上网"，自主导航和执行任务。*
