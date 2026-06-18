# 测试策略深度：覆盖规范/回归测试/CI 门禁

> 从单元测试到端到端测试，逐层解析 Agent 系统的测试体系

---

## 第一部分：测试金字塔

```
Agent 测试金字塔：
┌─────────────────────────────────────────────────────────────────────┐
│                                                                        │
│                          ┌─────┐                                      │
│                         / E2E \                                     │
│                        / 测试   \                                    │
│                       /──────────\                                   │
│                      /  集成测试  \                                  │
│                     /──────────────\                                 │
│                    /   单元测试     \                                │
│                   /──────────────────\                               │
│                  /                    \                              │
│                 /                      \                             │
│                /                        \                            │
│               /                          \                           │
│              /                            \                          │
│             /                              \                         │
│            /                                \                        │
│           /                                  \                       │
│          /                                    \                      │
│         /                                      \                     │
│        /                                        \                    │
│       /                                          \                   │
│      /                                            \                  │
│     /                                              \                 │
│    /                                                \                │
│   /                                                  \               │
│  /                                                    \              │
│ /                                                      \             │
│/________________________________________________________\____________ │
│  数量: 多                                              数量: 少       │
│  速度: 快                                              速度: 慢       │
│  维护成本: 低                                          维护成本: 高     │
│  覆盖率: 高                                            覆盖率: 低       │
└─────────────────────────────────────────────────────────────────────┘

比例建议：
• 单元测试: 70%
• 集成测试: 20%
• E2E 测试: 10%
```

---

## 第二部分：单元测试规范

### 测试覆盖要求

```
必须写单元测试的模块：
1. core/ 下的所有公共函数
   - DynamicAgent
   - SkillBundle
   - Runtime
   - StepExecutorRegistry
   - MCPToolCaller
   - CircuitBreaker
   - Idempotency
   - Memory Manager

2. planning/ 下的所有公共函数
   - IntentPlanner
   - HeuristicPlan
   - DeterministicPlan

3. 所有 pattern 函数
   - RunConfirmedToolActionWithVerify
   - RunUniqueLookup
   - BuildReviewActionResult

4. 所有 custom executor
   - SlotFillerExecutor
   - ListQueryExecutor
   - PlanResolverExecutor
   - ...

不强制单元测试的：
1. 纯配置（YAML/Markdown）
2. 简单的 getter/setter
3. 已覆盖的集成测试
```

### 测试模板

```go
package core

import (
    "context"
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestDynamicAgent_New(t *testing.T) {
    t.Run("valid bundle", func(t *testing.T) {
        bundle := &SkillBundle[UACampaignSlots]{
            Workflow: Profile[UACampaignSlots]{
                Manifest: AgentManifest{Name: "test"},
            },
        }
        
        agent, err := NewDynamicAgent(UACampaignSlots, DynamicAgentConfig[UACampaignSlots]{
            Bundle: bundle,
        })
        
        require.NoError(t, err)
        assert.NotNil(t, agent)
        assert.Equal(t, "test", agent.Manifest().Name)
    })
    
    t.Run("nil bundle", func(t *testing.T) {
        _, err := NewDynamicAgent(UACampaignSlots, DynamicAgentConfig[UACampaignSlots]{
            Bundle: nil,
        })
        
        assert.Error(t, err)
        assert.Contains(t, err.Error(), "bundle is required")
    })
    
    t.Run("empty manifest name", func(t *testing.T) {
        bundle := &SkillBundle[UACampaignSlots]{
            Workflow: Profile[UACampaignSlots]{
                Manifest: AgentManifest{Name: ""},
            },
        }
        
        agent, err := NewDynamicAgent(UACampaignSlots, DynamicAgentConfig[UACampaignSlots]{
            Bundle: bundle,
        })
        
        require.NoError(t, err)
        // 从 bundle 的 manifest 获取名字
        assert.Equal(t, bundle.Workflow.Manifest.Name, agent.Manifest().Name)
    })
}

func TestRuntime_Run(t *testing.T) {
    t.Run("normal execution", func(t *testing.T) {
        // 准备测试数据
        profile := Profile[testSlots]{
            Steps: []WorkflowStep[testSlots]{
                &mockStep{
                    key: "step_1",
                    runFn: func(ctx context.Context, input WorkflowContext[testSlots]) (*WorkflowResult[testSlots], error) {
                        return &WorkflowResult[testSlots]{
                            State: "done",
                            Slots: testSlots{Value: "test"},
                        }, nil
                    },
                },
            },
        }
        
        runtime := NewRuntime(profile)
        ctx := context.Background()
        input := WorkflowContext[testSlots]{
            SessionID: "test-session",
            Slots:     testSlots{},
        }
        
        result, traces, err := runtime.Run(ctx, input)
        
        require.NoError(t, err)
        assert.Equal(t, "done", result.State)
        assert.Len(t, traces, 1)
        assert.Equal(t, "step_1", traces[0].StepName)
    })
    
    t.Run("step returns error", func(t *testing.T) {
        profile := Profile[testSlots]{
            Steps: []WorkflowStep[testSlots]{
                &mockStep{
                    key: "step_1",
                    runFn: func(ctx context.Context, input WorkflowContext[testSlots]) (*WorkflowResult[testSlots], error) {
                        return nil, fmt.Errorf("step failed")
                    },
                },
            },
        }
        
        runtime := NewRuntime(profile)
        ctx := context.Background()
        input := WorkflowContext[testSlots]{
            SessionID: "test-session",
        }
        
        _, _, err := runtime.Run(ctx, input)
        
        assert.Error(t, err)
        assert.Contains(t, err.Error(), "step failed")
    })
    
    t.Run("step skips", func(t *testing.T) {
        profile := Profile[testSlots]{
            Steps: []WorkflowStep[testSlots]{
                &mockStep{
                    key: "step_1",
                    runFn: func(ctx context.Context, input WorkflowContext[testSlots]) (*WorkflowResult[testSlots], error) {
                        return &WorkflowResult[testSlots]{
                            State:  "skipped",
                            Status: "step_skipped",
                        }, nil
                    },
                },
            },
        }
        
        runtime := NewRuntime(profile)
        ctx := context.Background()
        input := WorkflowContext[testSlots]{
            SessionID: "test-session",
        }
        
        result, traces, err := runtime.Run(ctx, input)
        
        require.NoError(t, err)
        assert.Equal(t, "skipped", result.State)
        assert.Len(t, traces, 1)
        assert.True(t, traces[0].Skipped)
    })
}
```

---

## 第三部分：集成测试规范

### 集成测试覆盖要求

```
必须写集成测试的场景：
1. 完整的 workflow 执行
   - 从用户输入到最终输出
   - 验证所有 step 按预期执行
   - 验证 slot 正确填充

2. MCP 工具调用
   - 验证参数正确传递
   - 验证返回值正确处理
   - 验证错误处理

3. Session 管理
   - 验证 session 持久化
   - 验证 session 恢复
   - 验证并发 session

4. 意图规划
   - 验证 LLM 规划
   - 验证规则 fallback
   - 验证确定性兜底

5. 熔断器
   - 验证状态转换
   - 验证降级行为
```

### 集成测试模板

```go
package ua_campaign

import (
    "context"
    "testing"
    "github.com/stretchr/testify/assert"
    "github.com/stretchr/testify/require"
)

func TestService_CreateOrContinue(t *testing.T) {
    t.Run("full campaign creation flow", func(t *testing.T) {
        // 1. 创建 Service
        store := NewInMemorySessionStore()
        tools := &mockMCPToolCaller{}
        model := &mockModelClient{}
        
        service, err := NewService(store, tools, WithModelClient(model))
        require.NoError(t, err)
        
        // 2. 第一轮：意图识别
        req1 := &CreateRequest{
            SessionID: "test-session-1",
            Message:   "帮我创建一个 TikTok 广告",
            Actor: Actor{
                UserID: "user-001",
            },
        }
        
        resp1, err := service.CreateOrContinue(context.Background(), req1)
        require.NoError(t, err)
        assert.Equal(t, StateIntentCaptured, resp1.State)
        assert.Equal(t, StatusWaitingUser, resp1.Status)
        assert.NotEmpty(t, resp1.Question)
        
        // 3. 第二轮：补充信息
        req2 := &CreateRequest{
            SessionID: "test-session-1",
            Message:   "TikTok",
            Slots: UACampaignSlots{
                Platform: "tiktok",
            },
        }
        
        resp2, err := service.CreateOrContinue(context.Background(), req2)
        require.NoError(t, err)
        assert.Equal(t, StateNeedAccount, resp2.State)
        assert.NotEmpty(t, resp2.Question)
        
        // 4. 验证 session 持久化
        session := store.Get("test-session-1")
        require.NotNil(t, session)
        assert.Equal(t, "user-001", session.Actor.UserID)
    })
    
    t.Run("dry run mode", func(t *testing.T) {
        store := NewInMemorySessionStore()
        tools := &mockMCPToolCaller{}
        model := &mockModelClient{}
        
        service, err := NewService(store, tools, WithModelClient(model))
        require.NoError(t, err)
        
        req := &CreateRequest{
            SessionID: "test-session-2",
            Message:   "帮我创建一个 TikTok 广告",
            DryRun:    true,
        }
        
        resp, err := service.CreateOrContinue(context.Background(), req)
        require.NoError(t, err)
        assert.Equal(t, "dry_run", resp.Metadata["mode"])
    })
}

// mockMCPToolCaller 模拟 MCP 工具调用
type mockMCPToolCaller struct {
    callCount int
    lastReq   MCPToolRequest
}

func (m *mockMCPToolCaller) CallTool(ctx context.Context, req MCPToolRequest) (*MCPToolResult, error) {
    m.callCount++
    m.lastReq = req
    
    // 模拟返回
    return &MCPToolResult{
        Data: map[string]interface{}{
            "campaign_id": "mock-campaign-123",
            "status":      "draft",
        },
    }, nil
}

// mockModelClient 模拟 LLM 模型
type mockModelClient struct{}

func (m *mockModelClient) ChatCompletion(ctx context.Context, req ChatCompletionRequest) (*ChatCompletionResponse, error) {
    return &ChatCompletionResponse{
        Choices: []Choice{
            {
                Message: &Message{
                    Content: `{"intent":"create_ad","slots":{"platform":"tiktok"}}`,
                },
            },
        },
    }, nil
}
```

---

## 第四部分：回归测试

### 回归测试策略

```
回归测试覆盖的场景：
1. 每次修改 core/ 代码后
   - 运行所有 core 单元测试
   - 运行所有 UA Campaign 集成测试

2. 每次修改 workflow.yaml 后
   - 运行 workflow lint 检查
   - 运行对应的集成测试

3. 每次修改 slot_schema.yaml 后
   - 运行 slot schema 校验
   - 运行相关的单元测试

4. 每次修改 MCP 路由配置后
   - 运行路由匹配测试
   - 运行 MCP 调用集成测试
```

### Golden File Testing

```go
package core

import (
    "testing"
    "github.com/stretchr/testify/assert"
)

// GoldenFileTest 金文件测试
func TestCompileSkillBundle_Golden(t *testing.T) {
    tests := []struct {
        name       string
        bundlePath string
        goldenPath string
    }{
        {
            name:       "calculator",
            bundlePath: "../examples/calculator/skill/references/skill_bundle.yaml",
            goldenPath: "../examples/calculator/skill/references/.golden/skill_bundle.json",
        },
        {
            name:       "ua_campaign",
            bundlePath: "../../skills/ua-campaign-creation/references/skill_bundle.yaml",
            goldenPath: "../../skills/ua-campaign-creation/references/.golden/skill_bundle.json",
        },
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            // 1. 编译 SkillBundle
            bundle, err := CompileSkillBundle[any](tt.bundlePath, NewStepExecutorRegistry[any]())
            assert.NoError(t, err)
            
            // 2. 序列化为 JSON
            jsonBytes, err := json.MarshalIndent(bundle, "", "  ")
            assert.NoError(t, err)
            
            // 3. 对比金文件
            goldenBytes, err := os.ReadFile(tt.goldenPath)
            if err != nil {
                // 金文件不存在，创建它
                os.WriteFile(tt.goldenPath, jsonBytes, 0644)
                t.Skip("golden file created")
            }
            
            assert.JSONEq(t, string(goldenBytes), string(jsonBytes))
        })
    }
}
```

---

## 第五部分：CI 门禁

### CI Pipeline

```yaml
# .github/workflows/agent-tests.yml
name: Agent Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Go
        uses: actions/setup-go@v4
        with:
          go-version: '1.21'
      
      - name: Run unit tests
        run: |
          cd app/agent
          go test -v -race -coverprofile=coverage.out ./core/... ./planning/... ./ua_campaign/...
          go tool cover -func=coverage.out
      
      - name: Check coverage
        run: |
          go tool cover -func=coverage.out | grep total | awk '{print $3}' | grep -q "^90"
          # 要求覆盖率 >= 90%
      
      - name: Run integration tests
        run: |
          cd app/agent
          go test -v -tags=integration ./...
      
      - name: Lint
        run: |
          cd app/agent
          golangci-lint run ./...
      
      - name: Check support_flow.go size
        run: |
          lines=$(wc -l < app/agent/ua_campaign/support_flow.go)
          if [ $lines -gt 1000 ]; then
            echo "ERROR: support_flow.go is too large ($lines lines, max 1000)"
            exit 1
          fi
      
      - name: Check golden files
        run: |
          cd app/agent
          go test -run TestCompileSkillBundle_Golden ./core/...
```

### CI 门禁规则

```
必须通过的 CI 检查：
1. 单元测试覆盖率 >= 90%
2. 集成测试全部通过
3. Lint 无错误
4. support_flow.go < 1000 行
5. Golden files 匹配
6. 无 race condition
7. 无安全漏洞（trivy scan）
```

---

## 第六部分：自测题

### Q1: 测试金字塔的比例？

**A**: 单元测试 70%、集成测试 20%、E2E 测试 10%。

### Q2: 回归测试什么时候触发？

**A**: 修改 core 代码、workflow.yaml、slot_schema.yaml、MCP 路由配置后。

### Q3: CI 门禁的关键检查？

**A**: 覆盖率 >= 90%、集成测试通过、Lint 无错误、support_flow.go < 1000 行、Golden files 匹配、无 race condition。

---

## 第七部分：生产实践

### 1. 测试覆盖率

```
覆盖率目标：
1. core/ >= 90%
2. planning/ >= 85%
3. ua_campaign/ >= 80%
4. 整体 >= 85%
```

### 2. 测试规范

```
测试规范：
1. 每个 public 函数必须有测试
2. 测试用例覆盖正常/异常/边界情况
3. 使用 testify/assert 和 testify/require
4. 测试名称描述场景
5. 测试数据使用 table-driven tests
```

### 3. 持续集成

```
CI 要点：
1. 每次 PR 运行完整测试
2. 覆盖率不达标阻断合并
3. 定期运行安全扫描
4. 自动部署测试环境
```
