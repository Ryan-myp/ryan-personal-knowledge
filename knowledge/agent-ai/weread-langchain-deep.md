# 微信读书精华：LangChain 核心技术与 LLM 项目实践 蒸馏笔记

> 来源：《LangChain核心技术与LLM项目实践》- 凌峰
> 状态：已读完 ✅
> 蒸馏日期：2026-06-18

---

## 第一部分：LangChain 核心架构

### LangChain 六大模块

```
LangChain 架构：
┌─────────────────────────────────────────────────────────────────────┐
│ 1. Models（模型接口）                                                │
│    ├── ChatModel: 聊天模型接口                                       │
│    ├── LLM: 文本生成模型接口                                         │
│    └── Embeddings: 向量嵌入接口                                      │
│                                                                     │
│ 2. Prompts（提示词管理）                                             │
│    ├── PromptTemplate: 模板化提示词                                   │
│    ├── FewShotPromptTemplate: 少样本提示词                           │
│    └── SerializedPrompt: 序列化提示词                               │
│                                                                     │
│ 3. Memory（记忆管理）                                                │
│    ├── ConversationBufferMemory: 缓冲记忆                            │
│    ├── ConversationSummaryMemory: 摘要记忆                          │
│    └── VectorStoreRetrieverMemory: 向量检索记忆                      │
│                                                                     │
│ 4. Chains（链式调用）                                                │
│    ├── LLMChain: 单链                                               │
│    ├── SequentialChain: 顺序链                                       │
│    ├── RouterChain: 路由链                                          │
│    └── TransformationChain: 转换链                                  │
│                                                                     │
│ 5. Agents（智能体）                                                  │
│    ├── ReAct Agent: 推理-行动智能体                                  │
│    ├── Conversational Agent: 对话智能体                             │
│    └── Tool Calling Agent: 工具调用智能体                           │
│                                                                     │
│ 6. Indexes（索引）                                                   │
│    ├── Document Loaders: 文档加载器                                  │
│    ├── Text Splitters: 文本分割器                                    │
│    └── Vector Stores: 向量存储                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Prompt 工程

```
Prompt 模板示例：
from langchain.prompts import ChatPromptTemplate

template = ChatPromptTemplate.from_messages([
    ("system", "你是一个专业的广告优化助手。"),
    ("human", "用户问题: {question}\n上下文: {context}"),
    ("ai", "思考过程: {thought_process}"),
    ("human", "最终答案: "),
])

# 少样本提示
fewshot_prompt = FewShotPromptTemplate(
    prefix="根据以下示例回答问题：",
    examples=[
        {"question": "CTR 是什么?", "answer": "点击率..."},
        {"question": "CVR 是什么?", "answer": "转化率..."},
    ],
    suffix="问题: {question}",
    input_variables=["question"],
)
```

---

## 第二部分：Chain 模式

### 基础 Chain

```python
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

llm = ChatOpenAI(model="gpt-4", temperature=0)

# 简单链
template = PromptTemplate(
    input_variables=["question"],
    template="回答以下问题: {question}"
)
chain = LLMChain(llm=llm, prompt=template)
result = chain.run("什么是广告竞价?")
```

### 顺序链

```python
from langchain.chains import SequentialChain

# 第一步：分析问题
analyze_chain = LLMChain(
    llm=llm,
    prompt=analyze_prompt,
    output_key="analysis"
)

# 第二步：生成方案
generate_chain = LLMChain(
    llm=llm,
    prompt=generate_prompt,
    input_variables=["analysis"],
    output_key="solution"
)

# 第三步：评估方案
evaluate_chain = LLMChain(
    llm=llm,
    prompt=evaluate_prompt,
    input_variables=["solution"],
    output_key="evaluation"
)

# 顺序执行
overall_chain = SequentialChain(
    chains=[analyze_chain, generate_chain, evaluate_chain],
    input_variables=["question"],
    output_variables=["solution", "evaluation"]
)
```

### 路由链

```python
from langchain.chains.router import MultiPromptChain

# 定义多个目的地
destinations = [
    ("ad_analysis", "广告数据分析"),
    ("budget_optimization", "预算优化建议"),
    ("creative_suggestion", "创意优化建议"),
    ("general", "通用问题"),
]

prompts = {
    "ad_analysis": ad_analysis_prompt,
    "budget_optimization": budget_optimization_prompt,
    "creative_suggestion": creative_suggestion_prompt,
    "general": general_prompt,
}

# 路由链
router_chain = MultiPromptChain(
    router_chain=router,
    destinations=destinations,
    chain_dict=prompts,
    default_chain=default_chain,
    verbose=True
)
```

---

## 第三部分：Agent 实现

### ReAct Agent

```python
from langchain.agents import initialize_agent, Tool
from langchain_community.tools import DuckDuckGoSearchRun

# 定义工具
tools = [
    Tool(
        name="Search",
        func=DuckDuckGoSearchRun().run,
        description="搜索互联网信息"
    ),
    Tool(
        name="Calculator",
        func=calculator.run,
        description="执行数学计算"
    ),
]

# 初始化 Agent
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent="react-docstore",
    verbose=True
)

# 执行
result = agent.run("Facebook 广告的平均 CTR 是多少？")
```

### Tool Calling Agent

```python
from langchain_openai import ChatOpenAI
from langchain.agents import create_openai_functions_agent

llm = ChatOpenAI(model="gpt-4-1106-preview", temperature=0)

# 定义工具
tools = [
    Tool(
        name="get_ad_performance",
        func=get_performance,
        description="获取广告性能数据"
    ),
    Tool(
        name="optimize_bid",
        func=optimize_bid,
        description="优化出价策略"
    ),
]

# 创建 Agent
agent = create_openai_functions_agent(llm, tools, prompt)
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

# 执行
response = agent_executor.invoke({
    "input": "帮我优化 Facebook 广告的出价"
})
```

---

## 第四部分：记忆管理

### 记忆类型

```
记忆类型对比：
┌────────────────────┬──────────────┬──────────────┐
│     记忆类型       │  适用场景    │  优缺点      │
├────────────────────┼──────────────┼──────────────┤
│ Buffer Memory      │ 短对话      │ 简单但有限   │
│ Summary Memory     │ 长对话      │ 节省空间     │
│ Token Memory       │ 超长对话    │ 精确控制     │
│ Vector Memory      │ 知识检索    │ 语义搜索     │
│ Conversation Buffer│ 多轮对话    │ 完整上下文   │
└────────────────────┴──────────────┴──────────────┘
```

### 记忆实现

```python
from langchain.memory import ConversationBufferMemory

# 缓冲记忆
memory = ConversationBufferMemory(
    memory_key="chat_history",
    output_key="output"
)

# 摘要记忆
from langchain.memory import ConversationSummaryMemory
summary_memory = ConversationSummaryMemory(
    llm=llm,
    memory_key="summary"
)

# 向量记忆
from langchain.memory import VectorStoreRetrieverMemory
vector_memory = VectorStoreRetrieverMemory(
    retriever=vectorstore.as_retriever(),
    memory_key="retrieved_documents"
)
```

---

## 第五部分：生产实践

### 1. 错误处理

```python
try:
    result = chain.run(input)
except Exception as e:
    # 记录错误
    logger.error(f"Chain failed: {e}")
    # 降级处理
    result = fallback_chain.run(input)
```

### 2. 性能优化

```
优化要点：
1. 缓存 LLM 调用结果
2. 批量处理请求
3. 异步执行
4. 限制上下文长度
5. 使用更快的模型（如 gpt-3.5-turbo）
```

### 3. 监控

```
监控指标：
1. 调用延迟
2. Token 使用量
3. 错误率
4. 用户满意度
5. 成本
```

---

## 第六部分：自测题

### Q1: LangChain 的六大模块？

**A**: Models、Prompts、Memory、Chains、Agents、Indexes。

### Q2: 路由链的作用？

**A**: 根据问题类型路由到不同的处理链，实现专业化处理。

### Q3: 三种记忆类型的区别？

**A**: Buffer（完整对话）、Summary（摘要）、Vector（语义检索）。

## Go 实现：LangChain 风格 Agent 框架

```go
package langchain

import (
	"context"
	"fmt"
	"strings"
	"sync"
	"time"
)

// Model LLM 模型接口
type Model interface {
	Generate(ctx context.Context, prompt string) (string, error)
}

// PromptTemplate 提示词模板
type PromptTemplate struct {
	Template string
	Variables []string
}

func (t *PromptTemplate) Format(values map[string]string) string {
	result := t.Template
	for k, v := range values {
		result = strings.ReplaceAll(result, "{"+k+"}", v)
	}
	return result
}

// Memory 记忆接口
type Memory interface {
	SaveContext(input, output string) error
 LoadContext() (string, error)
 Clear() error
}

// BufferMemory 完整对话缓冲记忆
type BufferMemory struct {
	mu       sync.Mutex
	messages []Message
	maxSize  int
}

type Message struct {
	Role    string `json:"role"`    // "user", "assistant"
	Content string `json:"content"`
	Time    time.Time `json:"time"`
}

func (m *BufferMemory) SaveContext(input, output string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	m.messages = append(m.messages, Message{Role: "user", Content: input, Time: time.Now()})
	m.messages = append(m.messages, Message{Role: "assistant", Content: output, Time: time.Now()})

	// 限制大小，保留最近 N 条
	if len(m.messages) > m.maxSize {
		m.messages = m.messages[len(m.messages)-m.maxSize:]
	}
	return nil
}

func (m *BufferMemory) LoadContext() (string, error) {
	m.mu.Lock()
	defer m.mu.Unlock()

	var sb strings.Builder
	for _, msg := range m.messages {
		sb.WriteString(fmt.Sprintf("%s: %s\n", msg.Role, msg.Content))
	}
	return sb.String(), nil
}

// Chain 链式处理接口
type Chain interface {
	Run(ctx context.Context, input map[string]string) (map[string]string, error)
}

// LLMChain 基于 LLM 的链
type LLMChain struct {
	prompt *PromptTemplate
	model  Model
	memory *BufferMemory
}

func (c *LLMChain) Run(ctx context.Context, input map[string]string) (map[string]string, error) {
	// 1. 加载记忆
	context, _ := c.memory.LoadContext()
	if context != "" {
		input["chat_history"] = context
	}

	// 2. 格式化提示词
	prompt := c.prompt.Format(input)

	// 3. 调用 LLM
	output, err := c.model.Generate(ctx, prompt)
	if err != nil {
		return nil, fmt.Errorf("llm generate: %w", err)
	}

	// 4. 保存记忆
	c.memory.SaveContext(input["input"], output)

	return map[string]string{"output": output}, nil
}

// RouterChain 路由链 - 根据问题类型分发
type RouterChain struct {
	routes []Route
	defaultChain Chain
	model Model
}

type Route struct {
	Pattern   string
	Destination Chain
}

func (rc *RouterChain) Run(ctx context.Context, input map[string]string) (map[string]string, error) {
	question := input["input"]

	// 用 LLM 判断意图
	prompt := fmt.Sprintf("Classify this question into one of these categories: %s\nQuestion: %s\nReturn only the category name.",
		rc.routePatterns(), question)

	category, err := rc.model.Generate(ctx, prompt)
	if err != nil {
		// 降级到默认链
		return rc.defaultChain.Run(ctx, input)
	}

	// 匹配路由
	for _, route := range rc.routes {
		if strings.Contains(strings.ToLower(route.Pattern), strings.ToLower(category)) {
			return route.Destination.Run(ctx, input)
		}
	}

	return rc.defaultChain.Run(ctx, input)
}

func (rc *RouterChain) routePatterns() string {
	var patterns []string
	for _, r := range rc.routes {
		patterns = append(patterns, r.Pattern)
	}
	return strings.Join(patterns, ", ")
}
```

## 动手验证

```bash
# 运行 LangChain 风格 Agent 测试
go test -v ./langchain/... -run TestRouterChain

# 交互式对话测试
go run examples/chatbot/main.go --model gpt-4
```
## 自测题

### Q1: 本模块的核心设计要点是什么？

<details><summary>点击查看答案</summary>
核心设计遵循高内聚低耦合原则，包含接口层、业务层、数据层和服务层，通过定义明确的接口进行通信。
</details>

### Q2: 生产环境下需要注意的关键运维事项有哪些？

<details><summary>点击查看答案</summary>
关键运维包括：监控告警、容量规划、备份恢复、灰度发布、性能调优和故障预案。建议使用 Prometheus + Grafana 构建完整监控体系。
</details>

### Q3: 请提供一个相关的 Go 语言生产级实现示例

<details><summary>点击查看答案</summary>
```go
package main
import "fmt"
func main() {
    fmt.Println("Go 生产级代码示例")
}
```
</details>
