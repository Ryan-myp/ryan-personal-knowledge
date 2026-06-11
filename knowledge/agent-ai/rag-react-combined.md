# RAG + ReAct 组合使用指南

> 标签: `#RAG` `#ReAct` `#智能体` `#组合模式`
> 创建日期: 2026-06-08
> 作者: Ryan

---

## 1. 组合模式概述

RAG（检索增强生成）和 ReAct（推理与行动交替）结合使用，创造出功能强大的智能体架构。

### 核心优势
- **知识获取** - RAG 提供准确、最新的知识库
- **灵活执行** - ReAct 支持调用各种工具和 API
- **自主决策** - Agent 能自主决定何时检索、何时执行
- **可解释性** - 完整的推理和决策链路

### 架构示意图
```
                    ┌─────────────────────┐
                    │    用户请求         │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │   ReAct 控制器      │
                    │  (推理与行动交替)    │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
┌─────────▼─────────┐ ┌───────▼───────┐ ┌─────────▼─────────┐
│   RAG 检索模块     │ │  工具调用模块  │ │   外部 API 模块    │
│  (知识库查询)      │ │  (本地工具)   │ │  (外部服务)       │
└───────────────────┘ └───────────────┘ └───────────────────┘
          │                    │                    │
          └────────────────────┼────────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │   答案生成模块      │
                    │  (综合所有信息)      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │    最终答案         │
                    └─────────────────────┘
```

---

## 2. 实现架构

### 2.1 核心组件

```python
class RagReactAgent:
    """RAG + ReAct 组合智能体"""
    
    def __init__(self):
        # RAG 系统
        self.rag_system = RAGSystem()
        
        # 可用工具集
        self.tools = {
            "search_knowledge": self.rag_system.search,  # 检索知识库
            "call_api": self.make_api_call,              # 调用外部 API
            "calculate": self.calculate,                 # 数学计算
            "send_message": self.send_message            # 发送消息
        }
        
        # 语言模型
        self.llm = LLMClient()
    
    def process(self, question):
        """处理用户请求"""
        history = []
        max_iterations = 10
        
        for i in range(max_iterations):
            # 1. 思考：LLM 决定下一步行动
            thought_action = self.llm.generate_thought_action(
                question, history, self.tools
            )
            
            # 2. 执行行动
            if thought_action.action:
                result = self.execute_tool(
                    thought_action.action,
                    thought_action.parameters
                )
                
                # 记录到历史
                history.append({
                    "thought": thought_action.thought,
                    "action": thought_action.action,
                    "observation": result
                })
                
                # 检查是否完成
                if self.is_complete(thought_action.thought):
                    break
            else:
                break
        
        # 3. 生成最终答案
        return self.generate_final_answer(question, history)
    
    def execute_tool(self, action_name, parameters):
        """执行工具调用"""
        if action_name in self.tools:
            return self.tools[action_name](**parameters)
        else:
            return f"错误：未找到工具 {action_name}"
```

### 2.2 工具集成

```python
class RAGSystem:
    """RAG 检索系统"""
    
    def __init__(self):
        self.vector_db = VectorDatabase()
        self.embedding_model = EmbeddingModel()
    
    def search(self, query):
        """检索相关知识"""
        # 1. 向量化查询
        query_vector = self.embedding_model.encode(query)
        
        # 2. 向量相似度搜索
        results = self.vector_db.similarity_search(query_vector, top_k=5)
        
        # 3. 格式化结果
        return self.format_results(results)

class APIConnector:
    """外部 API 连接器"""
    
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.example.com"
    
    def call(self, endpoint, params):
        """调用外部 API"""
        # 实现 API 调用逻辑
        pass
```

---

## 3. 实际应用场景

### 场景 1: 智能客服系统

```
用户: "我上周下的订单什么时候能到？"

ReAct 循环:
  Thought: 需要查询用户订单状态
  Action: search_knowledge(query="用户123订单状态")
  Observation: {"order_id": "ORD456", "status": "shipped", "tracking": "XYZ789"}
  
  Thought: 需要获取物流信息
  Action: call_api(endpoint="/tracking", params={"tracking_id": "XYZ789"})
  Observation: {"carrier": "顺丰", "eta": "2026-06-10", "location": "北京分拣中心"}
  
  Thought: 需要生成回复
  Action: send_message("您的订单ORD456已通过顺丰发货，物流单号XYZ789，预计6月10日送达，当前在北京分拣中心。")
```

### 场景 2: 数据分析助手

```
用户: "分析一下上季度销售数据，看看哪些产品表现最好"

ReAct 循环:
  Thought: 需要查询销售数据
  Action: call_api(endpoint="/sales", params={"quarter": "Q1-2026"})
  Observation: {"data": [...], "total_revenue": 1500000}
  
  Thought: 需要分析产品表现
  Action: search_knowledge(query="产品绩效分析方法")
  Observation: ["基于销售额排名", "基于增长率", "基于利润率"]
  
  Thought: 需要计算各项指标
  Action: calculate(expression="calculate_metrics(data)")
  Observation: {"top_products": ["产品A", "产品B", "产品C"]}
  
  Thought: 需要生成报告
  Action: send_message("上季度表现最好的产品是：1. 产品A (收入50万) 2. 产品B (收入40万) 3. 产品C (收入30万)")
```

### 场景 3: 研究助理

```
用户: "帮我找一下关于 Transformer 架构的最新研究进展"

ReAct 循环:
  Thought: 需要检索最新研究
  Action: search_knowledge(query="Transformer 架构 最新研究 2026")
  Observation: ["论文1: 改进的注意力机制", "论文2: 更高效的训练方法"]
  
  Thought: 需要获取论文详情
  Action: call_api(endpoint="/paper", params={"id": "paper1"})
  Observation: {"title": "高效Transformer", "abstract": "...", "methods": ["方法1", "方法2"]}
  
  Thought: 需要综合信息
  Action: send_message("最新研究进展包括：1. 改进的注意力机制 - 效率提升30% 2. 新的训练方法 - 收敛速度提升50%")
```

---

## 4. 优化策略

### 4.1 性能优化

1. **缓存机制**
   ```python
   class CachedRAGSystem:
       def __init__(self):
           self.cache = {}
       
       def search(self, query):
           if query in self.cache:
               return self.cache[query]
           
           result = self.rag_system.search(query)
           self.cache[query] = result
           return result
   ```

2. **并行处理**
   ```python
   import asyncio
   
   async def parallel_execution(actions):
       """并行执行独立行动"""
       tasks = [execute_action(action) for action in actions]
       return await asyncio.gather(*tasks)
   ```

3. **增量更新**
   - 知识库增量更新而非全量重建
   - 向量数据库增量索引

### 4.2 质量优化

1. **查询优化**
   - 自动扩展查询词
   - 查询重写和规范化

2. **结果重排序**
   - 使用重排序模型精排
   - 结合多种信号（相似度、时效性、权威性）

3. **答案验证**
   - 交叉验证多个来源
   - 置信度评估

---

## 5. 最佳实践

### 5.1 工具设计原则
- **清晰的描述** - 每个工具都有详细的描述
- **标准化的接口** - 统一的参数和返回格式
- **错误处理** - 完善的异常处理和重试机制

### 5.2 提示词设计
- **结构化输出** - 要求 Thought-Action-Observation 格式
- **明确约束** - 限制行动范围和工具选择
- **进度跟踪** - 监控任务完成度

### 5.3 监控和调试
- **完整日志** - 记录所有 Thought-Action-Observation 步骤
- **性能指标** - 监控响应时间和成功率
- **用户反馈** - 收集用户评价用于优化

---

## 6. 相关资源

- 参考书籍：《Agent设计模式：图解可复用智能体架构》
- 论文：ReAct: Synergizing Reasoning and Acting in Language Models
- 开源项目：LangChain, LlamaIndex, AutoGPT

---

### React + Agent 的 Go 实现

```go
package react

import (
	"context"
	"fmt"
	"strings"
	"sync"
)

type Thought struct {
	Reasoning string
	Action    string
	Input     string
}

type Agent struct {
	tools map[string]Tool
	mu    sync.Mutex
	memo  []string
}

type Tool interface {
	Name() string
	Execute(ctx context.Context, input string) (string, error)
}

func (a *Agent) Step(ctx context.Context, thought *Thought) (string, error) {
	tool, ok := a.tools[thought.Action]
	if !ok {
		return "", fmt.Errorf("unknown tool: %s", thought.Action)
	}
	return tool.Execute(ctx, thought.Input)
}

func (a *Agent) RunReact(ctx context.Context, query string, maxSteps int) (string, error) {
	a.mu.Lock()
	a.memo = append(a.memo, query)
	a.mu.Unlock()

	for i := 0; i < maxSteps; i++ {
		thought := &Thought{
			Reasoning: fmt.Sprintf("Step %d: Analyzing query", i+1),
			Action:    "search",
			Input:     query,
		}
		obs, err := a.Step(ctx, thought)
		if err != nil {
			return "", err
		}
		if strings.Contains(obs, "FINAL") {
			return obs, nil
		}
	}
	return "Max steps reached", nil
}

func main() {
	a := &Agent{tools: map[string]Tool{
		"search": &mockTool{},
	}}
	result, _ := a.RunReact(context.Background(), "What is RAG?", 3)
	fmt.Printf("Result: %s\n", result)
}

type mockTool struct{}

func (t *mockTool) Name() string { return "search" }
func (t *mockTool) Execute(ctx context.Context, input string) (string, error) {
	return "FINAL: RAG = Retrieval Augmented Generation", nil
}

*本文基于微信读书《Agent设计模式》及相关技术文档整理*

---

## 自测题

### 问题 1
RAG + React 结合后，LLM 在哪个阶段执行检索？为什么不是每次 Thought 都检索？

<details>
<summary>查看答案</summary>

**最佳实践是在 Thought 阶段判断是否需要检索，而非每次 Action 都检索**。

原因：
1. **成本**：每次 Thought 都检索会增加 LLM API 调用和向量数据库查询
2. **缓存**：相同查询的结果可以缓存复用
3. **效率**：Agent 可以先用自己的知识回答，遇到知识盲区才触发检索
4. **延迟**：检索需要时间，减少检索次数能降低端到端响应延迟

</details>

### 问题 2
Go 的 `context.Context` 在 Agent 系统中为什么比直接用 `chan` 更合适？

<details>
<summary>查看答案</summary>

1. **传播性**：Context 可以层层传递，chan 需要手动转发
2. **取消机制**：`ctx.Done()` 天然支持超时和取消
3. **Value 携带**：可以携带请求级数据（trace ID、用户信息）
4. **结构化**：`go context` 是 Go 的官方最佳实践

chan 更适合并发数据流，Context 更适合请求级生命周期管理。Agent 的 RunReact 需要的是请求级管理，所以 Context 更合适。

</details>
