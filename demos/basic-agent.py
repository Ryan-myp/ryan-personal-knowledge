#!/usr/bin/env python3
"""
基础 Agent 实现示例

实现一个基于 LLM 的简单 Agent，支持：
- 意图识别
- 工具调用
- 任务执行
"""

import json
import re
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
import time
import os


@dataclass
class AgentConfig:
    """Agent 配置"""
    model: str = "default"
    system_prompt: str = ""
    max_iterations: int = 10
    temperature: float = 0.7


@dataclass
class Tool:
    """工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    func: Callable


@dataclass
class Message:
    """消息"""
    role: str
    content: str


@dataclass
class AgentState:
    """Agent 状态"""
    messages: List[Message] = field(default_factory=list)
    iteration: int = 0
    completed: bool = False


class BaseAgent:
    """
    基础 Agent 类
    
    支持：
    - 意图识别
    - 工具调用
    - 任务执行
    - 状态管理
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or AgentConfig()
        self.tools: Dict[str, Tool] = {}
        self.state = AgentState()
        
        # 设置系统提示
        if not self.config.system_prompt:
            self.config.system_prompt = self._default_system_prompt()
    
    def _default_system_prompt(self) -> str:
        """默认系统提示"""
        return """你是一个有帮助的 AI 助手。你能够理解用户意图，调用合适的工具，并提供准确的答案。"""
    
    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool
        print(f"✅ 已注册工具: {tool.name} - {tool.description}")
    
    def identify_intent(self, user_input: str) -> Dict[str, Any]:
        """
        意图识别
        
        Args:
            user_input: 用户输入
            
        Returns:
            意图识别结果
        """
        print(f"\n🔍 意图识别: {user_input}")
        
        # 简单的意图识别规则
        intent_patterns = {
            "search": ["搜索", "查找", "查询", "find", "search", "query"],
            "calculate": ["计算", "算一下", "calculate", "math", "sum"],
            "translate": ["翻译", "translate", "翻译一下"],
            "explain": ["解释", "说明", "explain", "what is", "什么是"],
            "create": ["创建", "生成", "create", "generate", "写"],
            "default": []
        }
        
        for intent, keywords in intent_patterns.items():
            if any(keyword in user_input.lower() for keyword in keywords):
                print(f"   识别意图: {intent}")
                return {"intent": intent, "confidence": 0.8}
        
        print(f"   识别意图: default")
        return {"intent": "default", "confidence": 0.5}
    
    def call_tool(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """
        调用工具
        
        Args:
            tool_name: 工具名称
            parameters: 工具参数
            
        Returns:
            工具执行结果
        """
        if tool_name not in self.tools:
            return f"❌ 未找到工具: {tool_name}"
        
        tool = self.tools[tool_name]
        try:
            result = tool.func(**parameters)
            print(f"   ✅ 工具执行成功: {tool_name}")
            return result
        except Exception as e:
            print(f"   ❌ 工具执行失败: {tool_name} - {str(e)}")
            return f"❌ 工具执行失败: {str(e)}"
    
    def execute_task(self, user_input: str) -> str:
        """
        执行任务
        
        Args:
            user_input: 用户输入
            
        Returns:
            任务执行结果
        """
        print(f"\n🤖 执行任务: {user_input}")
        
        # 记录用户消息
        self.state.messages.append(Message(role="user", content=user_input))
        
        # 识别意图
        intent_result = self.identify_intent(user_input)
        
        # 根据意图选择工具
        intent = intent_result["intent"]
        
        if intent == "search":
            result = self.call_tool("search", {"query": user_input})
        elif intent == "calculate":
            result = self.call_tool("calculator", {"expression": user_input})
        elif intent == "translate":
            result = self.call_tool("translator", {"text": user_input})
        elif intent == "explain":
            result = self.call_tool("explainer", {"topic": user_input})
        elif intent == "create":
            result = self.call_tool("creator", {"topic": user_input})
        else:
            result = "💭 我理解你的意思了。让我帮你处理这个请求..."
        
        # 记录助手回复
        self.state.messages.append(Message(role="assistant", content=result))
        
        return result
    
    def get_state(self) -> Dict[str, Any]:
        """获取 Agent 状态"""
        return {
            "iteration": self.state.iteration,
            "messages_count": len(self.state.messages),
            "completed": self.state.completed,
            "tools": list(self.tools.keys())
        }


# 示例工具实现
def search_tool(query: str) -> str:
    """搜索工具"""
    return f"🔍 搜索结果: 关于'{query}'的搜索结果..."


def calculator_tool(expression: str) -> str:
    """计算器工具"""
    try:
        # 简单的计算器实现
        result = eval(expression)
        return f"🧮 计算结果: {expression} = {result}"
    except Exception as e:
        return f"❌ 计算失败: {str(e)}"


def translator_tool(text: str) -> str:
    """翻译工具"""
    return f"🌐 翻译结果: {text} (已翻译成中文)"


def explainer_tool(topic: str) -> str:
    """解释工具"""
    return f"💡 关于'{topic}'的解释..."


def creator_tool(topic: str) -> str:
    """创建工具"""
    return f"📝 已创建关于'{topic}'的内容..."


def demo():
    """演示"""
    print("🤖 Agent 基础实现示例")
    print("=" * 50)
    
    # 创建 Agent
    agent = BaseAgent()
    
    # 注册工具
    agent.register_tool(Tool(
        name="search",
        description="搜索工具",
        parameters={"query": "str"},
        func=search_tool
    ))
    
    agent.register_tool(Tool(
        name="calculator",
        description="计算器工具",
        parameters={"expression": "str"},
        func=calculator_tool
    ))
    
    agent.register_tool(Tool(
        name="translator",
        description="翻译工具",
        parameters={"text": "str"},
        func=translator_tool
    ))
    
    agent.register_tool(Tool(
        name="explainer",
        description="解释工具",
        parameters={"topic": "str"},
        func=explainer_tool
    ))
    
    agent.register_tool(Tool(
        name="creator",
        description="创建工具",
        parameters={"topic": "str"},
        func=creator_tool
    ))
    
    # 测试执行
    test_inputs = [
        "帮我搜索 Python 编程",
        "计算 123 * 456",
        "翻译 Hello World",
        "解释什么是机器学习",
        "创建一个关于 AI 的故事"
    ]
    
    for user_input in test_inputs:
        result = agent.execute_task(user_input)
        print(f"   结果: {result}")
        print("-" * 30)
    
    # 显示状态
    state = agent.get_state()
    print(f"\n📊 Agent 状态: {json.dumps(state, ensure_ascii=False, indent=2)}")


if __name__ == "__main__":
    demo()
