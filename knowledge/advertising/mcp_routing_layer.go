package main

import (
	"context"
	"encoding/json"
	"fmt"
	"strings"
	"sync"
	"time"
)

// ============================================================
// MCP Tool 路由层 - 统一路由 + 安全策略 + 凭证管理
// ============================================================

// ToolRisk 工具风险等级
type ToolRisk string

const (
	ToolRiskRead        ToolRisk = "read"
	ToolRiskWrite       ToolRisk = "write"
	ToolRiskDestructive ToolRisk = "destructive"
)

// ToolCallRoute 工具调用路由
type ToolCallRoute string

const (
	RouteManaged  ToolCallRoute = "managed_mcp"
	RouteFallback ToolCallRoute = "fallback"
)

// ToolCallStatus 工具调用状态
type ToolCallStatus string

const (
	StatusSuccess ToolCallStatus = "success"
	StatusError   ToolCallStatus = "error"
	StatusBlocked ToolCallStatus = "blocked"
)

// ToolCallRecord 工具调用记录
type ToolCallRecord struct {
	ToolName   string        `json:"tool_name"`
	Risk       ToolRisk      `json:"risk"`
	Route      ToolCallRoute `json:"route"`
	ServerName string        `json:"server_name"`
	Status     ToolCallStatus `json:"status"`
	Confirmed  bool          `json:"confirmed"`
	Error      string        `json:"error,omitempty"`
	DurationMS int64         `json:"duration_ms"`
	CreatedAt  time.Time     `json:"created_at"`
}

// ToolCallRecorder 工具调用记录器
type ToolCallRecorder interface {
	Record(ctx context.Context, record ToolCallRecord) error
}

// DefaultRecorder 默认记录器（内存）
type DefaultRecorder struct {
	mu    sync.Mutex
	records []ToolCallRecord
}

func (r *DefaultRecorder) Record(ctx context.Context, record ToolCallRecord) error {
	r.mu.Lock()
	defer r.mu.Unlock()
	r.records = append(r.records, record)
	return nil
}

// CredentialManager 凭证管理器
type CredentialManager struct {
	credentials map[string]map[string]map[string]string // provider -> account_id -> credentials
	mu          sync.RWMutex
}

// NewCredentialManager 创建凭证管理器
func NewCredentialManager() *CredentialManager {
	return &CredentialManager{
		credentials: make(map[string]map[string]map[string]string),
	}
}

// SetCredential 设置凭证
func (cm *CredentialManager) SetCredential(provider, accountID string, creds map[string]string) {
	cm.mu.Lock()
	defer cm.mu.Unlock()
	if _, ok := cm.credentials[provider]; !ok {
		cm.credentials[provider] = make(map[string]map[string]string)
	}
	cm.credentials[provider][accountID] = creds
}

// GetCredential 获取凭证
func (cm *CredentialManager) GetCredential(provider, accountID string) (map[string]string, error) {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	if accouns, ok := cm.credentials[provider]; ok {
		if creds, ok := accouns[accountID]; ok {
			return creds, nil
		}
	}
	return nil, fmt.Errorf("credential not found for provider=%s account=%s", provider, accountID)
}

// PolicyEngine 安全策略引擎
type PolicyEngine struct {
	// 危险操作关键词
	destructiveWords []string
	// 写操作关键词
	writeWords []string
	// 读操作关键词
	readWords []string
}

// NewPolicyEngine 创建策略引擎
func NewPolicyEngine() *PolicyEngine {
	return &PolicyEngine{
		destructiveWords: []string{
			"delete", "remove", "drop", "truncate", "purge", "destroy",
			"archive", "disable", "deactivate", "revoke", "hard_delete",
		},
		writeWords: []string{
			"create", "update", "patch", "set", "insert", "upsert", "sync",
			"import", "export", "execute", "run", "send", "publish", "apply",
			"enable", "activate", "pause", "resume", "upload", "bind", "unbind",
			"grant", "approve", "reject",
		},
		readWords: []string{
			"get", "list", "query", "search", "retrieve", "discover", "find",
			"check", "validate", "preview", "inspect", "describe", "read",
		},
	}
}

// ToolPolicyDecision 策略决策
type ToolPolicyDecision struct {
	ToolName             string
	Risk                 ToolRisk
	RequiresConfirmation bool
	Confirmed            bool
	Reason               string
}

// Evaluate 评估工具调用策略
func (pe *PolicyEngine) Evaluate(ctx context.Context, toolName string, confirmed bool) (ToolPolicyDecision, error) {
	risk := pe.classifyToolRisk(toolName)
	decision := ToolPolicyDecision{
		ToolName:   toolName,
		Risk:       risk,
		Reason:     fmt.Sprintf("%s tool %q", risk, toolName),
	}

	if risk == ToolRiskWrite || risk == ToolRiskDestructive {
		decision.RequiresConfirmation = true
		if !confirmed {
			return decision, fmt.Errorf("tool call requires confirmation: %s", decision.Reason)
		}
		decision.Confirmed = true
	}

	return decision, nil
}

// classifyToolRisk 分类工具风险
func (pe *PolicyEngine) classifyToolRisk(toolName string) ToolRisk {
	name := strings.ToLower(strings.TrimSpace(toolName))
	if name == "" {
		return ToolRiskWrite
	}

	// 拆分成单词
	parts := splitToolName(name)
	
	for _, part := range parts {
		for _, word := range pe.destructiveWords {
			if part == word {
				return ToolRiskDestructive
			}
		}
	}
	
	for _, part := range parts {
		for _, word := range pe.readWords {
			if part == word {
				return ToolRiskRead
			}
		}
	}
	
	for _, part := range parts {
		for _, word := range pe.writeWords {
			if part == word {
				return ToolRiskWrite
			}
		}
	}
	
	// 未知工具默认为写操作
	return ToolRiskWrite
}

// splitToolName 拆分工具名为单词
func splitToolName(name string) []string {
	var parts []string
	current := ""
	for _, r := range name {
		if r == '_' || r == '-' || r == '/' || r == '.' {
			if current != "" {
				parts = append(parts, current)
				current = ""
			}
		} else {
			current += string(r)
		}
	}
	if current != "" {
		parts = append(parts, current)
	}
	return parts
}

// MarketingAPIServer 营销 API Server（前向声明）
type MarketingAPIServer struct{}

// CallTool 调用工具（前向声明实现）
func (s *MarketingAPIServer) CallTool(ctx context.Context, toolName string, params map[string]interface{}) (interface{}, error) {
	return nil, fmt.Errorf("not implemented")
}

// GetToolSchema 获取工具 Schema（前向声明实现）
func (s *MarketingAPIServer) GetToolSchema(toolName string) (*ToolDescriptor, error) {
	return nil, fmt.Errorf("not implemented")
}

// ListTools 列出工具（前向声明实现）
func (s *MarketingAPIServer) ListTools() []ToolDescriptor {
	return nil
}

// GetConfig 获取配置（前向声明实现）
func (s *MarketingAPIServer) GetConfig() MarketingProviderConfig {
	return MarketingProviderConfig{}
}

// DiscoverTools 发现工具（前向声明实现）
func (s *MarketingAPIServer) DiscoverTools() []ToolDescriptor {
	return nil
}

// MarketingProviderConfig 平台配置（前向声明）
type MarketingProviderConfig struct {
	Provider    string
	DisplayName string
	ServerName  string
}

// ToolDescriptor MCP 工具描述（前向声明）
type ToolDescriptor struct {
	Name        string
	Description string
	Parameters  []ToolParameter
	ServerName  string
	Version     string
	Category    string
	Channel     string
}

// ToolParameter 工具参数（前向声明）
type ToolParameter struct {
	Name        string
	Type        string
	Description string
	Required    bool
	Default     interface{}
	Enum        []string
}

// RoutingService 路由服务
type RoutingService struct {
	servers     map[string]*MarketingAPIServer // provider -> server
	credMgr     *CredentialManager
	policy      *PolicyEngine
	recorder    ToolCallRecorder
	fallback    FallbackService
	mu          sync.RWMutex
}

// FallbackService 回退服务接口
type FallbackService interface {
	CallTool(ctx context.Context, toolName string, params map[string]interface{}) (interface{}, error)
}

// NewRoutingService 创建路由服务
func NewRoutingService(fallback FallbackService) *RoutingService {
	return &RoutingService{
		servers:   make(map[string]*MarketingAPIServer),
		credMgr:   NewCredentialManager(),
		policy:    NewPolicyEngine(),
		recorder:  &DefaultRecorder{},
		fallback:  fallback,
	}
}

// RegisterServer 注册 MCP Server
func (rs *RoutingService) RegisterServer(provider string, server *MarketingAPIServer) {
	rs.mu.Lock()
	defer rs.mu.Unlock()
	rs.servers[provider] = server
}

// SetCredential 设置凭证
func (rs *RoutingService) SetCredential(provider, accountID string, creds map[string]string) {
	rs.credMgr.SetCredential(provider, accountID, creds)
}

// CallTool 调用工具（统一入口）
func (rs *RoutingService) CallTool(ctx context.Context, toolName string, params map[string]interface{}) (interface{}, error) {
	start := time.Now()

	// 1. 策略评估
	decision, err := rs.policy.Evaluate(ctx, toolName, false)
	if err != nil {
		rs.record(ToolCallRecord{
			ToolName:   toolName,
			Risk:       decision.Risk,
			Route:      RouteFallback,
			Status:     StatusBlocked,
			Confirmed:  false,
			Error:      err.Error(),
			DurationMS: time.Since(start).Milliseconds(),
			CreatedAt:  time.Now(),
		})
		return nil, err
	}

	// 2. 查找对应的 Server
	server, err := rs.findServerForTool(toolName)
	if err != nil {
		// 尝试回退服务
		if rs.fallback != nil {
			result, err := rs.fallback.CallTool(ctx, toolName, params)
			rs.record(ToolCallRecord{
				ToolName:   toolName,
				Risk:       decision.Risk,
				Route:      RouteFallback,
				Status:     ToolCallStatus(fmt.Sprintf("%v", err != nil)),
				Confirmed:  decision.Confirmed,
				Error:      err.Error(),
				DurationMS: time.Since(start).Milliseconds(),
				CreatedAt:  time.Now(),
			})
			return result, err
		}
		return nil, fmt.Errorf("no server found for tool: %s", toolName)
	}

	// 3. 调用工具
	result, err := server.CallTool(ctx, toolName, params)
	
	status := StatusSuccess
	if err != nil {
		status = StatusError
	}
	
	rs.record(ToolCallRecord{
		ToolName:   toolName,
		Risk:       decision.Risk,
		Route:      RouteManaged,
		ServerName: server.GetConfig().ServerName,
		Status:     status,
		Confirmed:  decision.Confirmed,
		Error:      err.Error(),
		DurationMS: time.Since(start).Milliseconds(),
		CreatedAt:  time.Now(),
	})

	return result, err
}

// findServerForTool 根据工具名找到对应的 Server
func (rs *RoutingService) findServerForTool(toolName string) (*MarketingAPIServer, error) {
	rs.mu.RLock()
	defer rs.mu.RUnlock()

	// 工具名格式：{action}_{entity} 或 {action}_{entity}_xxx
	// 我们需要从工具名推断 provider
	
	// 简单策略：第一个匹配的 Server
	for _, server := range rs.servers {
		// 检查工具是否存在于该 Server
		_, err := server.GetToolSchema(toolName)
		if err == nil {
			return server, nil
		}
	}

	return nil, fmt.Errorf("no server has tool: %s", toolName)
}

// record 记录工具调用
func (rs *RoutingService) record(record ToolCallRecord) {
	if rs.recorder != nil {
		rs.recorder.Record(context.Background(), record)
	}
}

// ListTools 列出所有工具
func (rs *RoutingService) ListTools() []ToolDescriptor {
	var allTools []ToolDescriptor
	rs.mu.RLock()
	defer rs.mu.RUnlock()
	
	for _, server := range rs.servers {
		allTools = append(allTools, server.ListTools()...)
	}
	
	return allTools
}

// GetToolSchema 获取工具 Schema
func (rs *RoutingService) GetToolSchema(toolName string) (*ToolDescriptor, error) {
	rs.mu.RLock()
	defer rs.mu.RUnlock()
	
	for _, server := range rs.servers {
		tool, err := server.GetToolSchema(toolName)
		if err == nil {
			return tool, nil
		}
	}
	
	return nil, fmt.Errorf("tool %s not found", toolName)
}

// ExportToolsAsJSON 导出所有工具为 JSON
func (rs *RoutingService) ExportToolsAsJSON() ([]byte, error) {
	tools := rs.ListTools()
	return json.MarshalIndent(tools, "", "  ")
}
