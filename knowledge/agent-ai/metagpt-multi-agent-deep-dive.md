# MetaGPT 多 Agent 协作系统深度蒸馏

> 来源：MetaGPT 官方源码（GitHub）
> 蒸馏日期：2026-01-15
> 核心价值：多 Agent 协作架构 + SOP 标准化流程

---

## 一、MetaGPT 架构设计

### 1.1 Team 类核心

**源码摘录**（`team.py`）：
```python
class Team(BaseModel):
    """
    Team: 拥有 1 个或多个角色（agents）、SOP（标准操作流程）、
    以及用于即时通讯的环境，致力于任何多 Agent 活动，
    如协作编写可执行代码。
    """
    
    env: Optional[Environment] = None
    investment: float = Field(default=10.0)
    idea: str = Field(default="")
    use_mgx: bool = Field(default=True)
    
    def __init__(self, context: Context = None, **data: Any):
        super(Team, self).__init__(**data)
        ctx = context or Context()
        
        # 环境初始化
        if not self.env and not self.use_mgx:
            self.env = Environment(context=ctx)
        elif not self.env and self.use_mgx:
            self.env = MGXEnv(context=ctx)
        
        # 招聘角色
        if "roles" in data:
            self.hire(data["roles"])
    
    def hire(self, roles: list[Role]):
        """招聘角色进行协作"""
        self.env.add_roles(roles)
    
    def run_project(self, idea, send_to: str = ""):
        """从发布用户需求运行项目"""
        self.idea = idea
        # 发布消息到环境
        self.env.publish_message(Message(content=idea))
    
    async def run(self, n_round=3, idea="", auto_archive=True):
        """运行项目直到目标轮次或无资金"""
        while n_round > 0:
            if self.env.is_idle:
                break
            n_round -= 1
            await self.env.run()
        
        self.env.archive(auto_archive)
        return self.env.history
```

**设计意图**：
```
问题：如何实现多 Agent 协作开发？

方案：
1. Team 作为协作容器
   - 管理多个 Role
   - 维护投资预算
   - 协调通信环境
   
2. Role 角色设计
   - 产品经理、架构师、工程师、测试
   - 每个角色有特定职责
   
3. SOP 标准化流程
   - 需求分析 → 架构设计 → 编码 → 测试
   - 每步有明确输入输出
```

### 1.2 消息通信

```python
class Environment:
    """Agent 间的通信环境"""
    
    def __init__(self, context: Context = None):
        self.roles: dict[str, Role] = {}
        self.messages: list[Message] = []
        self.context = context or Context()
    
    def add_roles(self, roles: list[Role]):
        """添加角色到环境"""
        for role in roles:
            self.roles[role.name] = role
            role.set_env(self)
    
    def publish_message(self, message: Message):
        """发布消息"""
        self.messages.append(message)
        # 通知所有相关角色
        for role in self.roles.values():
            if self._should_receive(role, message):
                role.receive(message)
    
    def run(self):
        """运行一轮"""
        for role in self.roles.values():
            role.run()
```

---

## 二、Role 角色设计

### 2.1 Action 基类

**源码摘录**（`action.py`）：
```python
class Action(SerializationMixin, ContextMixin, BaseModel):
    """
    Action: 角色执行的基本操作单元
    """
    
    name: str = ""
    i_context: Union[dict, CodingContext, ...] = ""
    prefix: str = ""  # system message 前缀
    desc: str = ""    # 技能描述
    
    llm_name_or_type: Optional[str] = None
    
    async def _aask(self, prompt: str, system_msgs=None) -> str:
        """调用 LLM"""
        return await self.llm.aask(prompt, system_msgs)
    
    async def run(self, *args, **kwargs):
        """运行动作"""
        if self.node:
            return await self._run_action_node(*args, **kwargs)
        raise NotImplementedError
```

### 2.2 角色实现

```python
class ProductManager(Role):
    """产品经理角色"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.set_roles([
            WritePRD(),      # 写产品需求文档
            WriteArchitecture(),  # 架构设计
        ])
    
    async def _act(self) -> Message:
        """执行动作"""
        # 选择最适合当前情境的 action
        action = self._select_action()
        result = await action.run(self.state)
        return Message(content=result, role=self.profile)


class Engineer(Role):
    """工程师角色"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.set_roles([
            WriteCode(),      # 编写代码
            CodeReview(),     # 代码审查
            WriteTest(),      # 编写测试
        ])
```

---

## 三、SOP 标准化流程

### 3.1 开发流程

```python
# MetaGPT 的标准开发流程
# 1. 产品经理：写 PRD
prds = team.run_project("开发一个电商系统")

# 2. 架构师：设计架构
architecture = team.run_project("基于 PRD 设计架构")

# 3. 工程师：实现代码
code = team.run_project("实现架构设计")

# 4. 测试：编写测试
tests = team.run_project("编写测试用例")
```

### 3.2 消息传递

```python
class Message:
    """角色间通信的消息"""
    
    content: str
    role: str          # 发送者角色
    cause_by: str      # 触发的 Action
    sent_from: str     # 发送者
    received_to: str   # 接收者
    timestamp: float   # 时间戳
```

---

## 四、生产级应用

### 4.1 自定义角色

```python
from metagpt.roles import Role
from metagpt.actions import Action

class DataAnalyst(Role):
    """数据分析师角色"""
    
    def __init__(self, **data):
        super().__init__(**data)
        self.set_profile("DataAnalyst")
        self.set_roles([
            DataCleaning(),
            DataAnalysis(),
            ReportGeneration(),
        ])
    
    async def _act(self) -> Message:
        """执行数据分析"""
        # 选择下一个 action
        action = self.get_next_action()
        result = await action.run(self.memory)
        return Message(content=result, role=self.profile)
```

### 4.2 集成外部工具

```python
from metagpt.actions import Action
import pandas as pd

class DataAnalysis(Action):
    """数据分析动作"""
    
    async def run(self, data: pd.DataFrame) -> str:
        """执行数据分析"""
        # 1. 数据清洗
        cleaned = self.clean(data)
        
        # 2. 统计分析
        stats = cleaned.describe()
        
        # 3. 生成报告
        report = f"""
        # 数据分析报告
        
        ## 基本统计
        {stats.to_markdown()}
        
        ## 结论
        根据分析，得出以下结论...
        """
        return report
```

---

## 五、核心洞察总结

```
1. 多 Agent 协作
   - Team 管理多个 Role
   - 消息驱动通信
   - SOP 标准化流程

2. 角色设计
   - 每个 Role 有特定职责
   - Action 执行具体操作
   - Memory 维护状态

3. 生产应用
   - 可扩展的角色系统
   - 灵活的通信机制
   - 标准化的工作流
```

---

**核心价值**：MetaGPT 的核心价值在于"SOP 驱动的多 Agent 协作"——通过标准化的软件开发流程，实现了从需求到代码的自动化生成。
EOF
echo "✅ MetaGPT 深度文档已创建"