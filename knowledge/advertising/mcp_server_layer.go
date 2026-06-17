package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"
)

// ============================================================
// MCP Server 封装层 - Meta/Google/TikTok/DV360 API 统一抽象
// ============================================================

// MarketingProvider 营销平台类型
type MarketingProvider string

const (
	ProviderMeta      MarketingProvider = "meta"
	ProviderGoogle    MarketingProvider = "google_ads"
	ProviderTikTok    MarketingProvider = "tiktok"
	ProviderDV360     MarketingProvider = "dv360"
)

// MarketingProviderConfig 平台配置
type MarketingProviderConfig struct {
	Provider         MarketingProvider `json:"provider"`
	Slug             string            `json:"slug"`
	DisplayName      string            `json:"display_name"`
	ServerName       string            `json:"server_name"`
	Description      string            `json:"description"`
	ProviderAPIVer   string            `json:"provider_api_version"`
	BaseURL          string            `json:"provider_base_url"`
	SupportedAPIVers []string          `json:"supported_api_versions"`
	ToolSchemaVer    string            `json:"tool_schema_version"`
	ServerVer        string            `json:"server_version"`
	RequiredCtx      []string          `json:"required_context"`
	OptionalCtx      []string          `json:"optional_context"`
	DocsURL          string            `json:"docs_url"`
}

// DefaultProviderConfigs 默认平台配置
func DefaultProviderConfigs() []MarketingProviderConfig {
	return []MarketingProviderConfig{
		{
			Provider:    ProviderGoogle,
			Slug:        "google-ads",
			DisplayName: "Google Ads",
			ServerName:  "Google Ads Marketing API MCP Server",
			Description: "Google Ads Marketing API 本地 MCP Server，聚合广告活动、广告组、广告和素材的查询、创建、更新能力",
			ProviderAPIVer: "v24",
			BaseURL:      "https://googleads.googleapis.com",
			SupportedAPIVers: []string{"v22", "v23", "v24"},
			ToolSchemaVer:    "marketing-tool-schema.v1",
			ServerVer:        "marketing-mcp-server.v1",
			RequiredCtx:      []string{"customer_id"},
			OptionalCtx:      []string{"login_customer_id"},
			DocsURL:          "https://developers.google.com/google-ads/api/docs",
		},
		{
			Provider:    ProviderMeta,
			Slug:        "meta",
			DisplayName: "Meta Marketing API",
			ServerName:  "Meta Marketing API MCP Server",
			Description: "Meta Marketing API 本地 MCP Server，聚合 Campaign、Ad Set、Creative、Ad 的查询、创建、更新能力",
			ProviderAPIVer: "v20",
			BaseURL:      "https://graph.facebook.com",
			SupportedAPIVers: []string{"v19", "v20", "v21"},
			ToolSchemaVer:    "marketing-tool-schema.v1",
			ServerVer:        "marketing-mcp-server.v1",
			RequiredCtx:      []string{"access_token", "business_id"},
			OptionalCtx:      []string{"pixel_id"},
			DocsURL:          "https://developers.facebook.com/docs/marketing-apis/",
		},
		{
			Provider:    ProviderTikTok,
			Slug:        "tiktok",
			DisplayName: "TikTok Ads",
			ServerName:  "TikTok Marketing API MCP Server",
			Description: "TikTok Marketing API 本地 MCP Server，聚合广告系列、广告组、广告的查询、创建、更新能力",
			ProviderAPIVer: "v14",
			BaseURL:      "https://api.tiktokv.com",
			SupportedAPIVers: []string{"v13", "v14"},
			ToolSchemaVer:    "marketing-tool-schema.v1",
			ServerVer:        "marketing-mcp-server.v1",
			RequiredCtx:      []string{"access_token", "account_id"},
			OptionalCtx:      []string{"pixel_id"},
			DocsURL:          "https://developers.tiktok.com/doc/marketing-api-overview/",
		},
		{
			Provider:    ProviderDV360,
			Slug:        "dv360",
			DisplayName: "DV360",
			ServerName:  "DV360 API MCP Server",
			Description: "Display & Video 360 API 本地 MCP Server，聚合广告系列、广告组、创意的查询、创建、更新能力",
			ProviderAPIVer: "v1",
			BaseURL:      "https://dv360.googleapis.com",
			SupportedAPIVers: []string{"v1"},
			ToolSchemaVer:    "marketing-tool-schema.v1",
			ServerVer:        "marketing-mcp-server.v1",
			RequiredCtx:      []string{"partner_id", "client_id"},
			OptionalCtx:      []string{"network_id"},
			DocsURL:          "https://developers.google.com/display-video",
		},
	}
}

// MarketingEntitySpec 营销实体规范（跨平台统一）
type MarketingEntitySpec struct {
	Key        string   `json:"key"`         // 统一键名
	Singular   string   `json:"singular"`    // 单数形式
	Plural     string   `json:"plural"`      // 复数形式
	DisplayName string  `json:"display_name"` // 显示名称
	IDParam    string   `json:"id_param"`    // ID 参数名
	PathName   string   `json:"path_name"`   // API 路径名
	GAQLRes    string   `json:"gaql_resource"` // Google GAQL 资源名
	GAMutateCol string  `json:"ga_mutate_col"` // Google Mutate 集合
	MetaColl   string   `json:"meta_collection"` // Meta API 集合
	TikTokPath string   `json:"tiktok_path"`   // TikTok API 路径
	DV360Coll  string   `json:"dv360_collection"` // DV360 API 集合
}

// StandardEntitySpecs 标准实体规范
var StandardEntitySpecs = []MarketingEntitySpec{
	{
		Key: "campaign", Singular: "Campaign", Plural: "Campaigns",
		DisplayName: "广告系列", IDParam: "campaign_id", PathName: "campaigns",
		GAQLRes: "Campaign", GAMutateCol: "campaigns", MetaColl: "campaigns",
		TikTokPath: "/v1.0/{account_id}/campaigns", DV360Coll: "campaigns",
	},
	{
		Key: "ad_group", Singular: "Ad Group", Plural: "Ad Groups",
		DisplayName: "广告组", IDParam: "ad_group_id", PathName: "adgroups",
		GAQLRes: "AdGroup", GAMutateCol: "adGroups", MetaColl: "ad_sets",
		TikTokPath: "/v1.0/{account_id}/ad_groups", DV360Coll: "adGroups",
	},
	{
		Key: "ad", Singular: "Ad", Plural: "Ads",
		DisplayName: "广告", IDParam: "ad_id", PathName: "ads",
		GAQLRes: "Ad", GAMutateCol: "ads", MetaColl: "ads",
		TikTokPath: "/v1.0/{account_id}/ads", DV360Coll: "ads",
	},
	{
		Key: "creative", Singular: "Creative", Plural: "Creatives",
		DisplayName: "创意", IDParam: "creative_id", PathName: "creatives",
		GAQLRes: "", GAMutateCol: "", MetaColl: "creatives",
		TikTokPath: "/v1.0/{account_id}/creatives", DV360Coll: "creatives",
	},
	{
		Key: "keyword", Singular: "Keyword", Plural: "Keywords",
		DisplayName: "关键词", IDParam: "keyword_id", PathName: "keywords",
		GAQLRes: "Keyword", GAMutateCol: "keywords", MetaColl: "",
		TikTokPath: "", DV360Coll: "targeting",
	},
	{
		Key: "ad_set", Singular: "Ad Set", Plural: "Ad Sets",
		DisplayName: "广告集", IDParam: "ad_set_id", PathName: "adsets",
		GAQLRes: "", GAMutateCol: "", MetaColl: "ad_sets",
		TikTokPath: "/v1.0/{account_id}/ad_groups", DV360Coll: "adGroups",
	},
}

// MarketingFieldSpec 营销字段规范
type MarketingFieldSpec struct {
	Name        string                 `json:"name"`
	Type        string                 `json:"type"`
	Description string                 `json:"description"`
	Required    bool                   `json:"required"`
	Enum        []string               `json:"enum,omitempty"`
	Default     interface{}            `json:"default,omitempty"`
	Schema      map[string]interface{} `json:"schema,omitempty"`
}

// MarketingOperationSpec 营销操作规范
type MarketingOperationSpec struct {
	Action       string                 `json:"action"`
	Description  string                 `json:"description"`
	Category     string                 `json:"category"` // read/write/query
	Method       string                 `json:"method"`   // GET/POST/PUT/DELETE
	Path         string                 `json:"path"`
	QueryFields  []MarketingFieldSpec   `json:"query_fields,omitempty"`
	BodyFields   []MarketingFieldSpec   `json:"body_fields,omitempty"`
	DefaultBody  map[string]interface{} `json:"default_body,omitempty"`
	IncludeAdvID bool                   `json:"include_advertiser_id,omitempty"`
	SkipReqCtx   bool                   `json:"skip_required_context,omitempty"`
}

// ToolDescriptor MCP 工具描述
type ToolDescriptor struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Parameters  []ToolParameter        `json:"parameters"`
	ServerName  string                 `json:"server_name"`
	Version     string                 `json:"version"`
	Category    string                 `json:"category"`
	Channel     string                 `json:"channel"`
	Extra       map[string]interface{} `json:"extra,omitempty"`
}

// ToolParameter 工具参数
type ToolParameter struct {
	Name        string                 `json:"name"`
	Path        string                 `json:"path,omitempty"`
	Type        string                 `json:"type"`
	Description string                 `json:"description"`
	Required    bool                   `json:"required"`
	Default     interface{}            `json:"default,omitempty"`
	Enum        []string               `json:"enum,omitempty"`
	Schema      map[string]interface{} `json:"schema,omitempty"`
}

// MarketingAPIServer 营销 API MCP Server
type MarketingAPIServer struct {
	config     MarketingProviderConfig
	tools      []ToolDescriptor
	httpClient *http.Client
	mu         sync.RWMutex
}

// NewMarketingAPIServer 创建营销 API Server
func NewMarketingAPIServer(cfg MarketingProviderConfig) *MarketingAPIServer {
	return &MarketingAPIServer{
		config:     cfg,
		httpClient: &http.Client{Timeout: 30 * time.Second},
	}
}

// DiscoverTools 发现并注册工具
func (s *MarketingAPIServer) DiscoverTools() []ToolDescriptor {
	s.mu.Lock()
	defer s.mu.Unlock()

	tools := make([]ToolDescriptor, 0)

	for _, entity := range StandardEntitySpecs {
		// 查询类工具
		tools = append(tools, s.makeReadTool(entity))
		// 创建类工具
		tools = append(tools, s.makeCreateTool(entity))
		// 更新类工具
		tools = append(tools, s.makeUpdateTool(entity))
	}

	// 特殊工具
	tools = append(tools, s.makePerformanceTool())
	tools = append(tools, s.makeAnomalyDetectionTool())

	s.tools = tools
	return tools
}

// makeReadTool 生成查询工具
func (s *MarketingAPIServer) makeReadTool(entity MarketingEntitySpec) ToolDescriptor {
	fields := []ToolParameter{
		{Name: "id", Type: "string", Description: entity.DisplayName + " ID", Required: true},
		{Name: "fields", Type: "string", Description: "要返回的字段（逗号分隔）", Required: false},
		{Name: "limit", Type: "integer", Description: "返回数量限制", Required: false, Default: 100},
	}

	// 根据平台添加特定字段
	switch s.config.Provider {
	case ProviderGoogle:
		fields = append(fields, ToolParameter{
			Name: "filter", Type: "string", Description: "GAQL 过滤器（如：campaign.status = 'ENABLED'）",
			Required: false,
		})
	case ProviderMeta:
		fields = append(fields, ToolParameter{
			Name: "filter_status", Type: "enum", Description: "状态过滤器", Required: false,
			Enum: []string{"ALL", "ACTIVE", "PAUSED", "DELETED"},
		})
	case ProviderTikTok:
		fields = append(fields, ToolParameter{
			Name: "filter_by", Type: "string", Description: "TikTok 过滤器", Required: false,
		})
	}

	return ToolDescriptor{
		Name:        fmt.Sprintf("get_%s", entity.Key),
		Description: fmt.Sprintf("查询 %s 详情 - %s", entity.DisplayName, s.config.DisplayName),
		Parameters:  fields,
		ServerName:  s.config.ServerName,
		Version:     s.config.ToolSchemaVer,
		Category:    "read",
		Channel:     string(s.config.Provider),
	}
}

// makeCreateTool 生成创建工具
func (s *MarketingAPIServer) makeCreateTool(entity MarketingEntitySpec) ToolDescriptor {
	baseFields := []ToolParameter{
		{Name: "name", Type: "string", Description: entity.DisplayName + " 名称", Required: true},
		{Name: "status", Type: "string", Description: "状态（ACTIVE/PAUSED）", Required: false, Default: "ACTIVE"},
	}

	// 根据实体类型添加特定字段
	switch entity.Key {
	case "campaign":
		baseFields = append(baseFields,
			ToolParameter{Name: "objective", Type: "string", Description: "广告目标（BRAND_AWARENESS/TRAFFIC/CONVERSIONS）", Required: true},
			ToolParameter{Name: "daily_budget", Type: "number", Description: "日预算（单位：平台货币最小单位）", Required: false},
			ToolParameter{Name: "campaign_group_id", Type: "string", Description: "广告系列组 ID", Required: false},
		)
	case "ad_group":
		baseFields = append(baseFields,
			ToolParameter{Name: "campaign_id", Type: "string", Description: "所属广告系列 ID", Required: true},
			ToolParameter{Name: "bid_strategy", Type: "string", Description: "出价策略（IMPRESSIONS/CLICKS/CONVERSIONS）", Required: true},
			ToolParameter{Name: "cpc_bid", Type: "number", Description: "CPC 出价", Required: false},
			ToolParameter{Name: "cpa_bid", Type: "number", Description: "CPA 出价", Required: false},
		)
	}

	return ToolDescriptor{
		Name:        fmt.Sprintf("create_%s", entity.Key),
		Description: fmt.Sprintf("创建 %s - %s", entity.DisplayName, s.config.DisplayName),
		Parameters:  baseFields,
		ServerName:  s.config.ServerName,
		Version:     s.config.ToolSchemaVer,
		Category:    "write",
		Channel:     string(s.config.Provider),
	}
}

// makeUpdateTool 生成更新工具
func (s *MarketingAPIServer) makeUpdateTool(entity MarketingEntitySpec) ToolDescriptor {
	fields := []ToolParameter{
		{Name: "id", Type: "string", Description: entity.DisplayName + " ID", Required: true},
		{Name: "fields", Type: "object", Description: "要更新的字段（JSON 对象）", Required: true},
	}

	return ToolDescriptor{
		Name:        fmt.Sprintf("update_%s", entity.Key),
		Description: fmt.Sprintf("更新 %s - %s", entity.DisplayName, s.config.DisplayName),
		Parameters:  fields,
		ServerName:  s.config.ServerName,
		Version:     s.config.ToolSchemaVer,
		Category:    "write",
		Channel:     string(s.config.Provider),
	}
}

// makePerformanceTool 生成表现查询工具
func (s *MarketingAPIServer) makePerformanceTool() ToolDescriptor {
	return ToolDescriptor{
		Name:        "get_performance",
		Description: fmt.Sprintf("获取 %s 广告表现数据", s.config.DisplayName),
		Parameters: []ToolParameter{
			{Name: "ids", Type: "array", Description: "广告组 ID 列表", Required: true},
			{Name: "date_range", Type: "string", Description: "日期范围（YYYY-MM-DD,YYYY-MM-DD）", Required: true},
			{Name: "dimensions", Type: "array", Description: "维度（DAY/HOUR/COUNTRY_DEVICE）", Required: false},
			{Name: "metrics", Type: "array", Description: "指标（IMPRESSSIONS/CLICKS/CONVERSIONS/SPEND）", Required: false},
		},
		ServerName: s.config.ServerName,
		Version:    s.config.ToolSchemaVer,
		Category:   "read",
		Channel:    string(s.config.Provider),
	}
}

// makeAnomalyDetectionTool 生成异常检测工具
func (s *MarketingAPIServer) makeAnomalyDetectionTool() ToolDescriptor {
	return ToolDescriptor{
		Name:        "detect_anomalies",
		Description: fmt.Sprintf("检测 %s 广告异常", s.config.DisplayName),
		Parameters: []ToolParameter{
			{Name: "entity_type", Type: "string", Description: "实体类型（CAMPAIGN/AD_GROUP/AD）", Required: true},
			{Name: "entity_ids", Type: "array", Description: "实体 ID 列表", Required: true},
			{Name: "lookback_days", Type: "integer", Description: "回溯天数", Required: false, Default: 7},
			{Name: "threshold", Type: "number", Description: "异常阈值（标准差倍数）", Required: false, Default: 2.0},
		},
		ServerName: s.config.ServerName,
		Version:    s.config.ToolSchemaVer,
		Category:   "read",
		Channel:    string(s.config.Provider),
	}
}

// ListTools 列出所有工具
func (s *MarketingAPIServer) ListTools() []ToolDescriptor {
	if len(s.tools) == 0 {
		s.DiscoverTools()
	}
	return s.tools
}

// GetToolSchema 获取工具 Schema
func (s *MarketingAPIServer) GetToolSchema(toolName string) (*ToolDescriptor, error) {
	for _, tool := range s.ListTools() {
		if tool.Name == toolName {
			return &tool, nil
		}
	}
	return nil, fmt.Errorf("tool %s not found", toolName)
}

// CallTool 调用工具（统一入口）
func (s *MarketingAPIServer) CallTool(ctx context.Context, toolName string, params map[string]interface{}) (interface{}, error) {
	// 根据工具名分发
	parts := strings.Split(toolName, "_")
	if len(parts) < 2 {
		return nil, fmt.Errorf("invalid tool name: %s", toolName)
	}

	action := parts[0]  // get/create/update
	entity := parts[1]  // campaign/ad_group/ad/creative/keyword/ad_set

	switch action {
	case "get":
		return s.handleRead(ctx, entity, params)
	case "create":
		return s.handleCreate(ctx, entity, params)
	case "update":
		return s.handleUpdate(ctx, entity, params)
	case "detect_anomalies":
		return s.handleAnomalyDetection(ctx, params)
	case "get_performance":
		return s.handlePerformance(ctx, params)
	default:
		return nil, fmt.Errorf("unknown action: %s", action)
	}
}

// handleRead 处理查询
func (s *MarketingAPIServer) handleRead(ctx context.Context, entity string, params map[string]interface{}) (interface{}, error) {
	id, _ := params["id"].(string)
	if id == "" {
		return nil, fmt.Errorf("id is required")
	}

	// 构建 API 请求
	_ = s.buildReadURL(entity, id)
	
	// 实际生产环境这里会调用真实 API
	// resp, err := s.httpClient.Get(url)
	// ...

	return map[string]interface{}{
		"entity":    entity,
		"id":        id,
		"provider":  string(s.config.Provider),
		"mock_data": true,
		"data": map[string]interface{}{
			"name": fmt.Sprintf("%s_%s", entity, id),
			"status": "ACTIVE",
			"impressions": 10000,
			"clicks": 500,
			"conversions": 25,
			"spend": 250.0,
		},
	}, nil
}

// handleCreate 处理创建
func (s *MarketingAPIServer) handleCreate(ctx context.Context, entity string, params map[string]interface{}) (interface{}, error) {
	name, _ := params["name"].(string)
	if name == "" {
		return nil, fmt.Errorf("name is required")
	}

	// 生成 ID
	id := fmt.Sprintf("%s_%s_%d", entity, name, time.Now().Unix())

	return map[string]interface{}{
		"status":   "success",
		"entity":   entity,
		"id":       id,
		"name":     name,
		"provider": string(s.config.Provider),
	}, nil
}

// handleUpdate 处理更新
func (s *MarketingAPIServer) handleUpdate(ctx context.Context, entity string, params map[string]interface{}) (interface{}, error) {
	id, _ := params["id"].(string)
	fields, _ := params["fields"].(map[string]interface{})
	if id == "" || fields == nil {
		return nil, fmt.Errorf("id and fields are required")
	}

	return map[string]interface{}{
		"status":   "success",
		"entity":   entity,
		"id":       id,
		"updated":  fields,
		"provider": string(s.config.Provider),
	}, nil
}

// handleAnomalyDetection 处理异常检测
func (s *MarketingAPIServer) handleAnomalyDetection(ctx context.Context, params map[string]interface{}) (interface{}, error) {
	entityType, _ := params["entity_type"].(string)
	entityIDs, _ := params["entity_ids"].([]interface{})
	lookbackDays, _ := params["lookback_days"].(int)
	if lookbackDays == 0 {
		lookbackDays = 7
	}

	anomalies := make([]map[string]interface{}, 0)
	for _, id := range entityIDs {
		// 模拟异常检测结果
		anomalies = append(anomalies, map[string]interface{}{
			"entity_id": id,
			"entity_type": entityType,
			"anomaly_type": "spike",
			"severity": "warning",
			"description": fmt.Sprintf("%s 指标异常波动", entityType),
			"lookback_days": lookbackDays,
		})
	}

	return map[string]interface{}{
		"anomalies": anomalies,
		"total":     len(anomalies),
		"provider":  string(s.config.Provider),
	}, nil
}

// handlePerformance 处理表现查询
func (s *MarketingAPIServer) handlePerformance(ctx context.Context, params map[string]interface{}) (interface{}, error) {
	ids, _ := params["ids"].([]interface{})
	dateRange, _ := params["date_range"].(string)

	return map[string]interface{}{
		"date_range": dateRange,
		"entity_ids": ids,
		"metrics": map[string]interface{}{
			"impressions": 100000,
			"clicks": 5000,
			"conversions": 250,
			"spend": 2500.0,
			"ctr": 0.05,
			"cpc": 0.50,
			"cpa": 10.0,
			"roas": 5.0,
		},
		"provider": string(s.config.Provider),
	}, nil
}

// buildReadURL 构建查询 URL
func (s *MarketingAPIServer) buildReadURL(entity, id string) string {
	switch s.config.Provider {
	case ProviderGoogle:
		return fmt.Sprintf("%s/v%d/customers/%s/%s/%s", 
			s.config.BaseURL, s.parseVersion(s.config.ProviderAPIVer), id, entity, id)
	case ProviderMeta:
		return fmt.Sprintf("%s/v%s/%s", 
			s.config.BaseURL, s.config.ProviderAPIVer, id)
	case ProviderTikTok:
		return fmt.Sprintf("%s/v1.0/%s/%s", 
			s.config.BaseURL, id, entity)
	case ProviderDV360:
		return fmt.Sprintf("%s/v1/%s/%s", 
			s.config.BaseURL, entity, id)
	default:
		return ""
	}
}

// parseVersion 解析版本号
func (s *MarketingAPIServer) parseVersion(ver string) int {
	var v int
	fmt.Sscanf(ver, "v%d", &v)
	return v
}

// GetConfig 获取配置
func (s *MarketingAPIServer) GetConfig() MarketingProviderConfig {
	return s.config
}

// ExportToolsAsJSON 导出工具列表为 JSON
func (s *MarketingAPIServer) ExportToolsAsJSON() ([]byte, error) {
	tools := s.ListTools()
	return json.MarshalIndent(tools, "", "  ")
}
