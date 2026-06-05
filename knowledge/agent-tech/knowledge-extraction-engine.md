# 代码知识提取引擎

**日期**: 2025-06-05
**标签**: #agent-架构 #知识提取 #AST #CFG #DFG

## 核心问题

> 如何把代码、文档、Schema 变成可查询的知识？

现有方案大多停留在"全文搜索"层面，但真正的知识是结构化的：
- **谁调用谁** (调用关系)
- **数据从哪来到哪去** (数据流)
- **代码怎么组织** (控制流)
- **接口怎么定义** (API契约)

## 知识分层模型

```text
代码/文档
    │
    ▼
┌─ Layer 0: 原始文本 ────────────────────────────┐
│ .py .java .yaml .md .json .sql               │
└────────────────────────────────────────────────┘
    │ 解析
    ▼
┌─ Layer 1: 结构化抽象 ─────────────────────────┐
│                                                  │
│  AST (Abstract Syntax Tree) — 语法结构           │
│    ├── 函数定义 (function, class, method)        │
│    ├── 变量声明与赋值                             │
│    ├── 控制流 (if/for/while/try/except)         │
│    └── 表达式与操作符                             │
│                                                  │
│  CFG (Control Flow Graph) — 执行路径            │
│    ├── 基本块 (basic blocks)                     │
│    ├── 分支条件                                 │
│    ├── 循环结构                                 │
│    └── 异常处理路径                              │
│                                                  │
│  DFG (Data Flow Graph) — 数据传播               │
│    ├── 变量来源 (definition)                    │
│    ├── 变量消费 (use)                           │
│    ├── 数据转换 (transformation)                │
│    └── 边界情况 (null, default, error)          │
│                                                  │
│  SIG (Signature Graph) — 接口契约               │
│    ├── 函数签名 (参数、返回类型、装饰器)          │
│    ├── 类继承关系                               │
│    └── 模块导出                                 │
│                                                  │
│  TSG (Type/Schema Graph) — 类型与 Schema         │
│    ├── 数据库表结构                             │
│    ├── API 请求/响应 schema                      │
│    └── Proto/gRPC 定义                          │
│                                                  │
│  Flow (Business Flow) — 业务流                  │
│    ├── 入口点 (entry points: API route, handler) │
│    ├── 调用拓扑 (caller → callee)                │
│    ├── 数据落点 (tables, queues, cache)          │
│    └── 外部依赖 (Provider, Third-party API)      │
│                                                  │
└──────────────────────────────────────────────────┘
    │ 索引
    ▼
┌─ Layer 2: 知识索引 ────────────────────────────┐
│                                                  │
│  • BM25 索引 — 文本关键词匹配                   │
│  • 向量索引 — 语义相似度                         │
│  • 图谱索引 — 关系查询                            │
│  • 元数据索引 — 文件路径、行号、语言、修改时间      │
│                                                  │
└──────────────────────────────────────────────────┘
    │ 查询
    ▼
┌─ Layer 3: 知识查询服务 ─────────────────────────┐
│                                                  │
│  • 代码知识查询 — "这个功能在哪里实现？"          │
│  • 数据流查询 — "这个字段的值从哪来？"            │
│  • 调用链查询 — "谁调用了这个方法？"              │
│  • 影响分析 — "改了这个函数会影响哪些地方？"      │
│  • 业务流查询 — "订单创建的全链路是什么？"         │
│                                                  │
└──────────────────────────────────────────────────┘
```

## 关键实现思路

### 1. AST 解析 — Python 优先

```python
# 使用 Python 标准库 ast，零依赖
import ast

class CodeVisitor(ast.NodeVisitor):
    """遍历 AST 提取结构化信息"""
    
    def visit_FunctionDef(self, node):
        """提取函数定义"""
        return {
            "type": "function",
            "name": node.name,
            "args": [self._get_arg(a) for a in node.args.args],
            "returns": self._get_type(node.returns),
            "decorators": [self._get_name(d) for d in node.decorator_list],
            "lines": (node.lineno, node.end_lineno),
            "children": [self.visit(child) for child in ast.walk(node)],
        }
    
    def visit_ClassDef(self, node):
        """提取类定义"""
        return {
            "type": "class",
            "name": node.name,
            "bases": [self._get_name(b) for b in node.bases],
            "methods": [self.visit(m) for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))],
        }
```

### 2. CFG 构建 — 基本块 + 分支

```python
class CFGBuilder:
    """从 AST/字节码构建控制流图"""
    
    def build(self, node):
        """返回 CFG: {basic_block_id: {successors: [...], predicates: [...]}}"""
        # 关键：识别分支点 (if/elif/else/for/while/try)
        # 每个分支点就是一个决策节点
        # 叶节点是 return/raise/continue/break
        pass
```

### 3. DFG 构建 — 变量追踪

```python
class DataFlowAnalyzer:
    """追踪变量从定义到消费的路径"""
    
    def analyze(self, node):
        """
        返回 DFG:
        {
          "var_name": {
            "definitions": [{"file": "a.py", "line": 10}],
            "uses": [{"file": "b.py", "line": 25}],
            "transforms": [{"op": "+", "file": "c.py", "line": 30}],
            "null_path": True/False,
            "source_system": "database|api|config|constant"
          }
        }
        """
        pass
```

### 4. Flow 构建 — 业务流从入口点开始

```python
class FlowBuilder:
    """从入口点构建业务流"""
    
    def discover_entry_points(self, repo):
        """自动发现入口点"""
        # Python FastAPI: @app.route 装饰器
        # Python Flask: @app.route 装饰器
        # Java Spring: @RestController, @GetMapping
        # Go Gin: router.POST(...)
        pass
    
    def build_call_graph(self, entry_point):
        """从入口点开始 BFS 构建调用拓扑"""
        # 调用邻居: 直接调用、反射调用、动态派发
        # 跳过: 第三方库、标准库(可配置)
        pass
    
    def find_data_sinks(self, call_graph):
        """从调用拓扑中找到数据落点"""
        # SQL 查询 → 数据库表
        # API 调用 → 外部服务
        # Cache 读写 → Redis/Memcached
        # 文件读写 → 对象存储/文件系统
        pass
```

## 存储方案

### 轻量方案（本地文件）

```
knowledge_graph/
├── nodes.jsonl          # 节点: {id, type, name, file, line, metadata}
├── edges.jsonl          # 边: {from, to, type, weight}
└── index/
    ├── bm25.json        # BM25 倒排索引
    └── meta.json        # 元数据索引
```

### 图谱方案（SQLite + FTS5）

```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,          -- function, class, table, api, route...
    name TEXT NOT NULL,
    file TEXT,
    line_start INTEGER,
    line_end INTEGER,
    metadata JSON,
    content TEXT,                -- 可全文搜索的内容
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX idx_nodes_type ON nodes(type);
CREATE INDEX idx_nodes_file ON nodes(file);
CREATE FTS5 nodes_content_fts ON nodes(content);

CREATE TABLE edges (
    from_id TEXT,
    to_id TEXT,
    type TEXT NOT NULL,          -- calls, depends_on, reads, writes...
    weight REAL DEFAULT 1.0
);

CREATE INDEX idx_edges FROM ON edges(from_id);
CREATE INDEX idx_edges TO ON edges(to_id);
```

## 查询模式

### 1. 代码知识查询

```python
# "订单创建接口在哪里实现？"
query = "order create"
results = search(
    text=query,
    scope=["code", "schema"],
    language="python",
    min_confidence=0.7
)
# 返回: file, line, context excerpt
```

### 2. 调用链查询

```python
# "谁调用了 OrderService.create？"
results = query_graph(
    query="who calls OrderService.create",
    relation="calls",
    direction="reverse",
    depth=3
)
# 返回: [Controller → Handler → Service → create()]
```

### 3. 数据流查询

```python
# "User表 status 字段的值从哪来？"
results = query_dataflow(
    entity="User.status",
    direction="upstream",
    include_transforms=True
)
# 返回: [API 参数 → DTO → Entity → DB]
```

### 4. 影响分析

```python
# "改了 OrderService.create 会影响哪些地方？"
results = query_impact(
    symbol="OrderService.create",
    direction="downstream",
    include_tests=True
)
# 返回: [调用者 → 测试用例 → 依赖服务]
```

## 与现有 ad-knowledge-query 的关系

| 维度 | ad-knowledge-query | 知识提取引擎 |
|------|-------------------|-------------|
| 输入 | 代码文件 | 代码文件 |
| 解析 | grep/ripgrep | AST/CFG/DFG |
| 索引 | SQLite + FTS5 | SQLite FTS5 + 图谱 |
| 查询 | 关键词/语义 | 结构化查询 + 关系遍历 |
| 粒度 | 文件/行级 | 函数/变量/类型级 |
| 知识密度 | 低 | 高 |

**互补关系**：
- 知识提取引擎是**上游**：把代码变成结构化知识
- ad-knowledge-query 是**下游**：消费结构化知识

## 实施路径

### Phase 1: AST 解析 (Python)
- 实现 Python AST 提取器
- 支持函数、类、方法提取
- 输出 JSONL 格式

### Phase 2: 图谱构建
- SQLite + FTS5 存储
- 节点+边模型
- 基础关系查询

### Phase 3: 多语言支持
- Java (JavaParser)
- TypeScript (ts-morph)
- Go (golang.org/x/tools/go/ast)

### Phase 4: 业务流发现
- 入口点自动发现
- 调用拓扑构建
- 数据落点识别

### Phase 5: 知识查询服务
- 集成到 biz-delivery
- 统一的查询 API
- 与 agentmemory 结合

## 技术选型

| 组件 | 方案 | 理由 |
|------|------|------|
| Python AST | 标准库 ast | 零依赖 |
| Java AST | JavaParser | 成熟稳定 |
| TS AST | ts-morph | 基于 TypeScript Compiler API |
| 存储 | SQLite | 轻量、FTS5、零依赖 |
| 索引 | BM25 + 向量 | 混合搜索 |
| 图谱查询 | SQL JOIN + 递归CTE | SQLite 支持 |
