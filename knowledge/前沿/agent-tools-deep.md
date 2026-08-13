# Agent 工具系统设计 - 资深专家深度实现

## 一、工具注册发现

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    工具注册发现流程                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   开发工具 → 注册到Registry → 暴露API → Agent调用 → 返回结果              │
│      ↑___________|_____________|_____________|____________|______________│
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、工具实现

```python
from typing import Dict, Any, List
import inspect

class ToolRegistry:
    """工具注册表"""
    
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.categories: Dict[str, List[str]] = {}
    
    def register(self, tool: 'Tool'):
        """注册工具"""
        self.tools[tool.name] = tool
        
        # 分类
        if tool.category not in self.categories:
            self.categories[tool.category] = []
        self.categories[tool.category].append(tool.name)
    
    def get_tool(self, name: str) -> 'Tool':
        """获取工具"""
        return self.tools.get(name)
    
    def list_tools(self, category: str = None) -> List[Dict]:
        """列出工具"""
        if category:
            tool_names = self.categories.get(category, [])
        else:
            tool_names = list(self.tools.keys())
        
        return [self.tools[name].to_dict() for name in tool_names]
    
    def search_tools(self, query: str) -> List[Dict]:
        """搜索工具"""
        results = []
        for name, tool in self.tools.items():
            if query.lower() in name.lower() or query.lower() in tool.description.lower():
                results.append(tool.to_dict())
        return results

class Tool:
    """工具基类"""
    
    def __init__(self, name: str, description: str, category: str, 
                 parameters: Dict[str, Any], callback: callable):
        self.name = name
        self.description = description
        self.category = category
        self.parameters = parameters
        self.callback = callback
    
    def execute(self, **kwargs) -> Any:
        """执行工具"""
        return self.callback(**kwargs)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "parameters": self.parameters,
        }
```

## 三、工具选择策略

```python
class ToolSelector:
    """工具选择器"""
    
    def __init__(self, registry: ToolRegistry, llm):
        self.registry = registry
        self.llm = llm
    
    def select_tools(self, query: str, max_tools: int = 3) -> List[Dict]:
        """选择工具"""
        # 方法1: 基于语义相似度
        tools = self.registry.list_tools()
        scored_tools = []
        
        for tool in tools:
            score = self.calculate_similarity(query, tool)
            scored_tools.append((tool, score))
        
        # 排序取top-K
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        return [tool for tool, _ in scored_tools[:max_tools]]
    
    def calculate_similarity(self, query: str, tool: Dict) -> float:
        """计算相似度"""
        prompt = f"""判断以下工具和问题的相关性：

问题: {query}
工具: {tool['name']} - {tool['description']}

请给出0-1的相关性分数（只需数字）。"""
        
        response = self.llm.invoke(prompt)
        return float(response.strip())
    
    def batch_select(self, queries: List[str]) -> Dict[str, List[Dict]]:
        """批量选择工具"""
        result = {}
        for query in queries:
            result[query] = self.select_tools(query)
        return result
```

## 四、面试高频题

### Q1: 如何实现工具自动发现？

```
A:
1. 注册中心: 工具注册表
2. 语义匹配: 根据描述匹配
3. 历史偏好: 用户常用工具
```

### Q2: 如何处理工具冲突？

```
A:
1. 优先级排序
2. 互斥检测
3. 用户确认
```

## 五、自测题

1. 解释工具注册流程
2. 如何实现工具选择？
3. 如何处理工具冲突？

---

## 参考文档

- [LangChain Tools](https://python.langchain.com/docs/modules/agents/tools/)
- [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling)
