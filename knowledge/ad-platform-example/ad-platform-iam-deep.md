# 广告平台多租户治理与资源权限模型深度实战

> **来源**：DAP 生产源码级分析 + 行业最佳实践 + 微信读书蒸馏
> **创建日期**：2026-07-09
> **深度等级**：🟢深（源码级）
> **关联源码**：`ad_smart_delivery_platform/internal/platform/governance/`

---

## 一、入门引导：为什么广告平台需要独立治理层？

### 1.1 类比：广告平台的"联邦政府"

想象一个联邦制国家：
- **联邦政府** = Platform Domain（系统级能力，如 Agent Builder）
- **州政府** = Tenant（客户租户，各自立法、财政）
- **市政府** = Workspace（团队空间，本地治理）
- **公民** = User（有投票权/角色权限）
- **公共设施** = SystemCapability（Agent/Graph/Skill/Tool）
- **私有财产** = ResourceScope（每个用户可拥有自己的 Skill/Knowledge）

广告平台不是简单的 CRUD 应用——它需要同时满足：
1. **SaaS 多租户隔离**：广告主 A 的 Campaign 数据绝不能泄露给 B
2. **层级权限控制**：SuperAdmin > TenantAdmin > WorkspaceAdmin > User
3. **资源级细粒度**：同一个 Skill，Alice 可以编辑，Bob 只能查看
4. **计费与功能绑定**：Pro 计划有 Graph Optimizer，Free 计划没有

### 1.2 传统方案 vs DAP 治理模型

| 维度 | 传统 RBAC | DAP 治理模型 |
|------|-----------|-------------|
| 租户隔离 | 无原生支持，靠 WHERE tenant_id=? | 内置 Domain/Tenant/Workspace 三级架构 |
| 资源可见性 | 角色决定"能做什么" | 可见性标签决定"能看到什么" |
| 能力管理 | 硬编码在业务逻辑中 | 独立的 SystemCapability 表 + Entitlement 检查 |
| 权限计算 | 运行时查角色-权限映射表 | 多层过滤：角色→可见性→租户→工作区→所有者 |
| 扩展性 | 新增功能需改代码 | 注册新 Capability 即可，无需改核心逻辑 |

---

## 二、核心原理：治理模型架构深度解析

### 2.1 三级层次结构（Domain → Tenant → Workspace）

```
Platform (全局)
├── Domain: "platform" — 系统级能力域
│   ├── SystemCapability: agent_builder
│   ├── SystemCapability: graph_optimizer
│   └── SystemCapability: skill_sandbox
├── Domain: "advertising" — 广告领域
│   ├── ResourceScope: skill-ad-template (visibility: domain_template)
│   └── ResourceScope: graph-campaign-optimize (visibility: domain_template)
├── Domain: "ecommerce" — 电商领域
└── Domain: "personal" — 个人效率领域

TenantDefault (默认租户)
├── WorkspaceDefault (默认工作区)
│   ├── User: yanping.ma@shopee.com (super_admin)
│   └── ResourceScope: skill-my-custom (visibility: private, owner: yanping.ma)
└── TenantA (客户租户)
    ├── WorkspaceA1
    │   ├── User: alice@client.com (workspace_admin)
    │   └── User: bob@client.com (user)
    └── WorkspaceA2
        └── User: charlie@client.com (user)
```

**源码证据** (`models.go` L44-L151):

```go
// 三级层次 — 每一级都有明确的职责边界
type Domain struct {       // 逻辑分组：跨领域通用 / 平台系统 / 广告 / 电商 / 研发 / 个人
    ID          string    // 唯一标识，如 "advertising", "platform"
    Name        string    // 显示名称
    Type        string    // "business" 或 "platform"
    Description string
    Status      string    // "active" / "disabled"
}

type Tenant struct {       // 客户租户：计费、配额、功能开关
    ID        string      // 如 "tenant_default", "client_acme_corp"
    Name      string
    Plan      string      // "free" / "pro" / "team" / "enterprise"
    Status    string
    Metadata  string      // JSON: {"source":"system_default"}
}

type Workspace struct {    // 团队空间：同一租户下的协作单元
    ID        string      // 如 "workspace_default", "team_marketing"
    TenantID  string      // FK → tenants.id
    Name      string
    Status    string
    Metadata  string
}
```

**关键设计决策**：
1. **Domain 是逻辑分组，不是隔离边界** — 同一 Domain 下的资源可以被不同 Tenant 共享（通过 visibility 控制）
2. **Tenant 是计费和安全隔离边界** — 不同 Tenant 的数据严格分离
3. **Workspace 是协作边界** — 同 Workspace 的用户可以共享资源

### 2.2 六种资源可见性模型（Visibility Model）

这是 DAP 治理模型中最精妙的设计。每个资源（Skill/Graph/Knowledge/Tool）都有一个 visibility 标签，决定谁可以看到它：

```go
const (
    VisibilitySystem         = "system"          // 系统级：所有用户可见
    VisibilityDomainTemplate = "domain_template"  // 领域模板：同领域内所有租户可见
    VisibilityTenantShared   = "tenant_shared"    // 租户共享：同租户内所有用户可见
    VisibilityWorkspace      = "workspace"        // 工作区级：同工作区内所有用户可见
    VisibilityPublic         = "public"           // 公开：全局可见（跨租户）
    VisibilityPrivate        = "private"          // 私有：仅所有者可见
)
```

**可见性过滤引擎** (`repository.go` L903-L923):

```go
func canAccessScope(access AccessContext, scope ResourceScope) bool {
    // 第一步：资源必须是活跃的
    if normalizeStatus(scope.Status) != "active" {
        return false
    }
    
    // 第二步：按可见性类型逐层过滤
    switch normalizeVisibility(scope.Visibility) {
    case VisibilitySystem, VisibilityDomainTemplate, VisibilityPublic:
        // 系统级/领域模板/公开 — 所有人可见
        return true
        
    case VisibilityTenantShared:
        // 租户共享 — 同租户或全局共享（tenant_id 为空）
        return strings.TrimSpace(scope.TenantID) == "" || 
               scope.TenantID == access.TenantID
                
    case VisibilityWorkspace:
        // 工作区级 — 先检查租户匹配，再检查工作区匹配
        if strings.TrimSpace(scope.TenantID) != "" && 
           scope.TenantID != access.TenantID {
            return false  // 租户不匹配，直接拒绝
        }
        return strings.TrimSpace(scope.WorkspaceID) == "" || 
               scope.WorkspaceID == access.WorkspaceID
                
    case VisibilityPrivate:
        // 私有 — 仅所有者可见
        owner := strings.TrimSpace(scope.OwnerID)
        return owner != "" && (owner == access.UserID || owner == access.Email)
        
    default:
        return false
    }
}
```

**可视化决策树**：

```
ResourceVisibility?
├── system/domain_template/public → ✅ 允许
├── tenant_shared
│   ├── scope.tenant_id == "" → ✅ 允许（全局共享）
│   └── scope.tenant_id == access.tenant_id → ✅ 允许
│   └── 否则 → ❌ 拒绝
├── workspace
│   ├── scope.tenant_id != "" && != access.tenant_id → ❌ 拒绝
│   └── scope.workspace_id == "" → ✅ 允许（同租户任意workspace）
│   └── scope.workspace_id == access.workspace_id → ✅ 允许
│   └── 否则 → ❌ 拒绝
└── private
    ├── scope.owner_id == "" → ❌ 拒绝
    └── scope.owner_id == access.user_id/email → ✅ 允许
    └── 否则 → ❌ 拒绝
```

### 2.3 资源作用域（ResourceScope）统一模型

DAP 用一张 `resource_scopes` 表统一管理所有资源的可见性：

```sql
CREATE TABLE resource_scopes (
    id TEXT PRIMARY KEY,              -- 复合ID: type:id:domain:tenant:ws:vis[:owner]
    resource_type TEXT NOT NULL,      -- skill / graph / knowledge / tool / datasource / model
    resource_id TEXT NOT NULL,        -- 资源唯一标识
    tenant_id TEXT,                   -- 所属租户（可为空表示全局）
    workspace_id TEXT,                -- 所属工作区（可为空）
    domain_id TEXT NOT NULL DEFAULT 'general',
    visibility TEXT NOT NULL DEFAULT 'private',
    owner_id TEXT,                    -- 所有者（private 时必填）
    status TEXT NOT NULL DEFAULT 'active',
    metadata TEXT,                    -- JSON: 扩展信息
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

**资源 ID 生成规则** (`repository.go` L998-L1014):

```go
func resourceScopeID(scope ResourceScope) string {
    tenantID := defaultString(scope.TenantID, "global")
    workspaceID := defaultString(scope.WorkspaceID, "global")
    visibility := defaultString(scope.Visibility, VisibilityPrivate)
    parts := []string{
        scope.ResourceType,
        scope.ResourceID,
        defaultString(scope.DomainID, DomainGeneral),
        tenantID,
        workspaceID,
        visibility,
    }
    if visibility == VisibilityPrivate {
        parts = append(parts, defaultString(scope.OwnerID, "owner"))
    }
    return strings.Join(parts, ":")
}
// 示例: "skill:my-custom-skill:advertising:tenant_a:workspace_a1:private:alice@example.com"
```

**为什么用字符串拼接 ID 而不是 UUID？**
- **可读性**：从 ID 就能看出资源的归属关系
- **确定性**：同一资源在不同环境生成相同 ID（可预测）
- **索引友好**：前缀匹配查询（如 `LIKE "skill:%"`）

---

## 三、源码级实现：权限检查全流程

### 3.1 认证 → 授权完整链路

```
HTTP Request
    │
    ▼
Auth Middleware (auth_context.go)
    │  - 从 Session/Cookie 或 Bearer Token 提取身份
    │  - 验证 token_hash 是否存在于 auth_sessions 表
    │  - 返回 *Account + tokenHash
    │
    ▼
Service.Current() / CurrentRuntime()
    │  - Current(): 标准认证（Session 或 Token）
    │  - CurrentRuntime(): 运行时认证（优先 Token，降级到 Header）
    │  - 从 exported app header (X-User-Email) 获取身份
    │
    ▼
setGinAccount(c, account)
    │  - 将 account 信息写入 gin.Context
    │  - 键: account_type, user_id, user_role, user_email, tenant_id, workspace_id
    │
    ▼
业务 Handler
    │  - c.Get("user_id") → 当前用户ID
    │  - c.Get("user_role") → 当前角色
    │  - governance.NewRepository(db).ListVisibleResourceScopes(...)
    │
    ▼
canAccessScope() 过滤引擎
    │  - 遍历所有资源
    │  - 对每个资源执行可见性判断
    │  - 返回可见资源列表
```

### 3.2 系统能力（SystemCapability）与计费绑定

DAP 的系统能力不是硬编码的，而是通过数据库驱动的可配置能力：

```go
// models.go L95-L110
type SystemCapability struct {
    ID             string    // "agent_builder"
    Name           string    // "Agent Builder"
    Description    string    // "平台级 Agent 构建能力"
    CapabilityType string    // "builder" / "optimizer" / "executor" / "exporter"
    DomainID       string    // "platform"
    Visibility     string    // "tenant_enabled"
    Protected      bool      // 是否受保护（不可删除）
    VersionChannel string    // "stable" / "beta"
    BillingFeature string    // "agent_builder_pro" ← 计费特性键
    RequiredPlan   string    // "pro" ← 所需最低计划
    Status         string    // "active"
    Metadata       string    // JSON: {"graph_id":"agent_builder_graph","skill_id":"skill-agent-builder"}
}
```

**四种系统能力** (`repository.go` L200-L257):

| 能力 | 类型 | 计费特性 | 最低计划 | 说明 |
|------|------|---------|---------|------|
| Agent Builder | builder | agent_builder_pro | pro | 根据需求生成可用 Agent Graph |
| Graph Optimizer | optimizer | graph_optimizer | pro | 优化 Prompt、模型、工具、知识库和流程结构 |
| Skill Sandbox | executor | skill_sandbox | free | Python/Shell 脚本安全执行，可选 Podman 隔离 |
| App Exporter | exporter | app_exporter | free | 生成 Web/PWA/Flet 等可交付应用骨架 |

### 3.3 许可检查（Entitlement）引擎

EntitlementService 是计费与功能开关的桥梁：

```go
// entitlement.go
func (s *EntitlementService) Check(ctx context.Context, req CheckRequest) (CheckDecision, error) {
    decision := CheckDecision{
        Feature:  req.Feature,
        TenantID: req.TenantID,
    }
    
    // Step 1: 查找租户
    tenant, err := s.repo.GetTenant(ctx, req.TenantID)
    decision.CurrentPlan = normalizePlan(tenant.Plan)
    
    // Step 2: 检查显式许可（租户级别的 feature 覆盖）
    if ent, err := s.repo.GetTenantEntitlement(ctx, req.TenantID, req.Feature); err == nil {
        decision.Source = "tenant_entitlement"
        decision.RequiredPlan = normalizePlan(ent.RequiredPlan)
        decision.Allowed = planAllows(decision.CurrentPlan, decision.RequiredPlan)
        return decision, nil
    }
    
    // Step 3: 检查系统能力定义中的默认计划要求
    capability, err := s.repo.GetSystemCapabilityByFeature(ctx, req.Feature)
    decision.Source = "system_capability"
    decision.RequiredPlan = normalizePlan(capability.RequiredPlan)
    decision.Allowed = planAllows(decision.CurrentPlan, decision.RequiredPlan)
    return decision, nil
}

// 计划等级比较
func planRank(plan string) int {
    switch normalizePlan(plan) {
    case "enterprise": return 4
    case "team":       return 3
    case "pro", "vip": return 2
    case "free":       return 1
    default:           return 0
    }
}
```

**许可优先级**：
```
显式 Entitlement (tenant_entitlements表)
    ↓ 未找到
系统 Capability 默认要求 (system_capabilities表)
    ↓ 未找到
拒绝（feature 不存在）
```

### 3.4 资源作用域查询完整流程

```go
// repository.go L724-L745
func (r *Repository) ListVisibleResourceScopes(
    ctx context.Context, 
    access AccessContext,      // 谁在查询
    filter ResourceScopeFilter, // 过滤条件
) ([]ResourceScope, error) {
    
    access = normalizeAccessContext(access)
    
    // 超级管理员看到一切
    if isSuperAdmin(access.Role) {
        return r.ListResourceScopes(ctx, filter)
    }
    
    // 普通用户：拉取所有资源后逐个过滤
    scopes, _ := r.ListResourceScopes(ctx, filter)
    
    visible := make([]ResourceScope, 0, len(scopes))
    for _, scope := range scopes {
        if canAccessScope(access, scope) {
            visible = append(visible, scope)
        }
    }
    return visible, nil
}
```

**性能优化建议**（当前实现的瓶颈）：
1. **问题**：`ListVisibleResourceScopes` 先拉取所有资源再内存过滤 — O(n) 复杂度
2. **优化方向**：将 `canAccessScope` 逻辑转换为 SQL WHERE 子句
3. **SQL 改写**：

```sql
SELECT * FROM resource_scopes
WHERE status = 'active'
  AND (
    -- 系统级/公开/领域模板
    visibility IN ('system', 'domain_template', 'public')
    OR
    -- 租户共享
    (visibility = 'tenant_shared' AND (tenant_id IS NULL OR tenant_id = ?))
    OR
    -- 工作区级
    (visibility = 'workspace' AND 
     (tenant_id IS NULL OR tenant_id = ?) AND
     (workspace_id IS NULL OR workspace_id = ?))
    OR
    -- 私有且是所有者
    (visibility = 'private' AND owner_id = ?)
  )
```

---

## 四、Go 生产级实现

### 4.1 完整的权限中间件

```go
package middleware

import (
	"context"
	"net/http"
	"strings"
	"time"

	"ad_smart_delivery_platform/internal/platform/governance"

	"github.com/gin-gonic/gin"
)

// AuthMiddleware 统一的认证+授权中间件
type AuthMiddleware struct {
	authService   *AuthService
	governanceRepo *governance.Repository
}

// AuthContext 从请求中提取的身份上下文
type AuthContext struct {
	UserID        string
	Email         string
	Role          string
	TenantID      string
	WorkspaceID   string
	AccountType   string // "platform" or "app"
	AccessToken   string // 原始 token（用于审计日志）
	Authenticated bool
	Expired       bool
}

// RequireAuth 认证中间件工厂
func (m *AuthMiddleware) RequireAuth() gin.HandlerFunc {
	return func(c *gin.Context) {
		ctx, err := m.extractAuthContext(c)
		if err != nil {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error": "authentication required",
			})
			c.Abort()
			return
		}

		ctx.Authenticated = true
		if ctx.Expired {
			c.JSON(http.StatusUnauthorized, gin.H{
				"error":     "token expired",
				"message":   "please re-login",
			})
			c.Abort()
			return
		}

		// 注入到 gin context
		c.Set("auth_context", ctx)
		c.Set("user_id", ctx.UserID)
		c.Set("user_role", ctx.Role)
		c.Set("tenant_id", ctx.TenantID)
		c.Set("workspace_id", ctx.WorkspaceID)
		c.Next()
	}
}

// RequireRole 角色权限中间件工厂
func (m *AuthMiddleware) RequireRole(requiredRoles ...string) gin.HandlerFunc {
	return func(c *gin.Context) {
		authCtx, exists := c.Get("auth_context")
		if !exists {
			c.JSON(http.StatusForbidden, gin.H{"error": "no auth context"})
			c.Abort()
			return
		}

		ctx := authCtx.(*AuthContext)
		if !hasRequiredRole(ctx.Role, requiredRoles...) {
			c.JSON(http.StatusForbidden, gin.H{
				"error":       "insufficient permissions",
				"required":    requiredRoles,
				"current_role": ctx.Role,
			})
			c.Abort()
			return
		}
		c.Next()
	}
}

// RequireResourceAccess 资源级权限中间件
func (m *AuthMiddleware) RequireResourceAccess(
	resourceType, resourceID string,
) gin.HandlerFunc {
	return func(c *gin.Context) {
		authCtxRaw, exists := c.Get("auth_context")
		if !exists {
			c.JSON(http.StatusForbidden, gin.H{"error": "not authenticated"})
			c.Abort()
			return
		}
		ctx := authCtxRaw.(*AuthContext)

		access := governance.AccessContext{
			UserID:      ctx.UserID,
			Email:       ctx.Email,
			Role:        ctx.Role,
			TenantID:    ctx.TenantID,
			WorkspaceID: ctx.WorkspaceID,
		}

		filter := governance.ResourceScopeFilter{
			ResourceType: resourceType,
			ResourceID:   resourceID,
		}

		scopes, err := m.governanceRepo.ListVisibleResourceScopes(
			context.Background(), access, filter,
		)
		if err != nil || len(scopes) == 0 {
			c.JSON(http.StatusForbidden, gin.H{
				"error":        "resource not accessible",
				"resource":     resourceID,
				"resource_type": resourceType,
			})
			c.Abort()
			return
		}

		c.Set("resource_scope", scopes[0])
		c.Next()
	}
}

// extractAuthContext 从多种来源提取认证信息
func (m *AuthMiddleware) extractAuthContext(c *gin.Context) (*AuthContext, error) {
	// 优先级 1: Bearer Token
	token := extractBearerToken(c)
	if token != "" {
		return m.validateToken(c.Request.Context(), token)
	}

	// 优先级 2: Exported App Header (内部服务调用)
	email := strings.TrimSpace(c.GetHeader("X-User-Email"))
	if email != "" {
		return &AuthContext{
			Email:       strings.ToLower(email),
			UserID:      sanitizeUserID(email),
			Role:        governance.RoleUser,
			TenantID:    governance.TenantDefault,
			WorkspaceID: governance.WorkspaceDefault,
			Authenticated: true,
		}, nil
	}

	// 优先级 3: Session Cookie
	return nil, fmt.Errorf("no authentication source found")
}

func (m *AuthMiddleware) validateToken(ctx context.Context, token string) (*AuthContext, error) {
	tokenHash := hashToken(token)

	var accountType, userID string
	var expiresAt time.Time
	err := m.authService.db.QueryRowContext(ctx, `
		SELECT account_type, user_id, expires_at
		FROM auth_sessions
		WHERE token_hash = ? AND expires_at > CURRENT_TIMESTAMP
	`, tokenHash).Scan(&accountType, &userID, &expiresAt)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, fmt.Errorf("invalid or expired token")
		}
		return nil, err
	}

	// 延长 token 有效期（滑动窗口）
	m.authService.db.ExecContext(ctx, `
		UPDATE auth_sessions SET last_seen_at = CURRENT_TIMESTAMP,
			expires_at = expires_at + INTERVAL '30 days'
		WHERE token_hash = ?
	`, tokenHash)

	// 加载用户完整信息
	var email, role, tenantID, workspaceID string
	if accountType == "app" {
		m.authService.db.QueryRowContext(ctx, `
			SELECT email, tenant_id, workspace_id FROM app_users WHERE id = ?
		`, userID).Scan(&email, &tenantID, &workspaceID)
		role = governance.RoleUser
	} else {
		m.authService.db.QueryRowContext(ctx, `
			SELECT email, role, tenant_id, workspace_id FROM users WHERE id = ?
		`, userID).Scan(&email, &role, &tenantID, &workspaceID)
	}

	return &AuthContext{
		UserID:        userID,
		Email:         email,
		Role:          role,
		TenantID:      tenantID,
		WorkspaceID:   workspaceID,
		AccountType:   accountType,
		AccessToken:   token,
		Authenticated: true,
	}, nil
}

func hasRequiredRole(current string, required ...string) bool {
	rank := roleRank(current)
	for _, r := range required {
		if rank >= roleRank(r) {
			return true
		}
	}
	return false
}

func roleRank(role string) int {
	switch role {
	case governance.RoleSuperAdmin:
		return 4
	case governance.RoleTenantAdmin:
		return 3
	case governance.RoleWorkspaceAdmin:
		return 2
	default:
		return 1
	}
}
```

### 4.2 资源作用域管理 API

```go
package governance

import (
	"context"
	"fmt"
	"strings"
	"time"
)

// ScopeManager 资源作用域管理器 — 提供 CRUD + 批量操作
type ScopeManager struct {
	repo *Repository
}

func NewScopeManager(repo *Repository) *ScopeManager {
	return &ScopeManager{repo: repo}
}

// CreateScope 创建新的资源作用域
func (m *ScopeManager) CreateScope(
	ctx context.Context,
	scope ResourceScope,
) error {
	if scope.ResourceType == "" || scope.ResourceID == "" {
		return fmt.Errorf("resource_type and resource_id are required")
	}

	// 自动填充默认值
	scope.DomainID = defaultString(scope.DomainID, DomainGeneral)
	scope.Visibility = normalizeVisibility(scope.Visibility)
	scope.Status = normalizeStatus(scope.Status)

	// 自动生成 ID
	if scope.ID == "" {
		scope.ID = ResourceScopeID(scope)
	}

	return m.repo.AssignResourceScope(ctx, scope)
}

// BatchAssignScopes 批量分配资源作用域
func (m *ScopeManager) BatchAssignScopes(
	ctx context.Context,
	scopes []ResourceScope,
) error {
	for _, scope := range scopes {
		if err := m.CreateScope(ctx, scope); err != nil {
			return fmt.Errorf("failed to assign scope %s: %w", scope.ResourceID, err)
		}
	}
	return nil
}

// GetEffectiveScopes 获取用户在指定条件下的有效资源
func (m *ScopeManager) GetEffectiveScopes(
	ctx context.Context,
	access AccessContext,
	filter ResourceScopeFilter,
) ([]ResourceScope, error) {
	return m.repo.ListVisibleResourceScopes(ctx, access, filter)
}

// TransferOwnership 转移资源所有权
func (m *ScopeManager) TransferOwnership(
	ctx context.Context,
	resourceType, resourceID, newOwner string,
) error {
	scope, err := m.repo.GetResourceScope(ctx, ResourceScopeID(ResourceScope{
		ResourceType: resourceType,
		ResourceID:   resourceID,
	}))
	if err != nil {
		return fmt.Errorf("scope not found: %w", err)
	}

	scope.OwnerID = newOwner
	scope.UpdatedAt = time.Now()

	return m.repo.AssignResourceScope(ctx, scope)
}

// RevokeScope 撤销资源访问权限
func (m *ScopeManager) RevokeScope(
	ctx context.Context,
	resourceType, resourceID string,
) error {
	scopeID := ResourceScopeID(ResourceScope{
		ResourceType: resourceType,
		ResourceID:   resourceID,
	})
	return m.repo.DeleteResourceScope(ctx, scopeID)
}
```

### 4.3 动态权限缓存（解决 O(n) 性能问题）

```go
package cache

import (
	"context"
	"sync"
	"time"

	"ad_smart_delivery_platform/internal/platform/governance"
)

// PermissionCache 权限缓存 — 减少数据库查询
type PermissionCache struct {
	mu        sync.RWMutex
	entries   map[string]*cacheEntry
	ttl       time.Duration
	onEvict   func(key string, scopes []governance.ResourceScope)
}

type cacheEntry struct {
	scopes    []governance.ResourceScope
	createdAt time.Time
}

func NewPermissionCache(ttl time.Duration, onEvict func(string, []governance.ResourceScope)) *PermissionCache {
	pc := &PermissionCache{
		entries: make(map[string]*cacheEntry),
		ttl:     ttl,
		onEvict: onEvict,
	}
	go pc.cleanupLoop()
	return pc
}

func (pc *PermissionCache) Get(ctx context.Context, access governance.AccessContext, filter governance.ResourceScopeFilter) ([]governance.ResourceScope, error) {
	key := pc.makeKey(access, filter)

	pc.mu.RLock()
	entry, ok := pc.entries[key]
	pc.mu.RUnlock()

	if ok && time.Since(entry.createdAt) < pc.ttl {
		return entry.scopes, nil
	}

	// Cache miss — 从数据库查询
	scopes, err := loadFromDB(ctx, access, filter)
	if err != nil {
		return nil, err
	}

	pc.mu.Lock()
	pc.entries[key] = &cacheEntry{
		scopes:    scopes,
		createdAt: time.Now(),
	}
	pc.mu.Unlock()

	return scopes, nil
}

func (pc *PermissionCache) Invalidate(userKey string) {
	pc.mu.Lock()
	defer pc.mu.Unlock()

	for key, entry := range pc.entries {
		if strings.HasPrefix(key, userKey+":") {
			if pc.onEvict != nil {
				pc.onEvict(key, entry.scopes)
			}
			delete(pc.entries, key)
		}
	}
}

func (pc *PermissionCache) makeKey(access governance.AccessContext, filter governance.ResourceScopeFilter) string {
	return fmt.Sprintf("%s:%s:%s:%s:%s:%s",
		access.UserID, access.Role, access.TenantID,
		access.WorkspaceID, filter.ResourceType, filter.Visibility,
	)
}

func (pc *PermissionCache) cleanupLoop() {
	ticker := time.NewTicker(pc.ttl / 2)
	defer ticker.Stop()
	for range ticker.C {
		pc.mu.Lock()
		now := time.Now()
		for key, entry := range pc.entries {
			if now.Sub(entry.createdAt) > pc.ttl {
				delete(pc.entries, key)
			}
		}
		pc.mu.Unlock()
	}
}
```

---

## 五、生产排障案例

### 5.1 故障：用户看不到自己创建的 Skill

**现象**：Alice 创建了 `skill-my-custom`（visibility=private），但登录后列表为空。

**排查步骤**：

```bash
# 1. 检查资源作用域记录
sqlite3 governance.db "SELECT * FROM resource_scopes WHERE resource_id='skill-my-custom';"
# 预期: visibility=private, owner_id='alice@example.com'

# 2. 检查登录用户的 session
sqlite3 governance.db "SELECT * FROM auth_sessions WHERE token_hash = 'abc123';"
# 检查 account_type 和 user_id

# 3. 检查 loadAccountByID 查询
# app_users 表中是否有该用户的记录？
sqlite3 governance.db "SELECT * FROM app_users WHERE email='alice@example.com';"
```

**根因**：`loadAccountByID` 方法中，app 用户查询缺少 role 字段：

```go
// 有问题的代码（原实现）
row := s.db.QueryRowContext(ctx, `
    SELECT id, COALESCE(email, ''), COALESCE(phone, ''), name, tenant_id, workspace_id, status
    FROM app_users WHERE id = ?
`, userID)
account := &Account{AccountType: AccountTypeApp, Role: governance.RoleUser}
return account, row.Scan(&account.ID, &account.Email, &account.Phone, &account.Name, 
                         &account.TenantID, &account.WorkspaceID, &account.Status)
// ⚠️ app_users 表没有 role 列，但 loadAccountByID 也没有读 role
// 所以永远使用默认 RoleUser — 这是正确的行为
```

**实际根因**：`canAccessScope` 中 private 判断使用了 `access.UserID` 和 `access.Email` 两个字段：

```go
case VisibilityPrivate:
    owner := strings.TrimSpace(scope.OwnerID)
    return owner != "" && (owner == access.UserID || owner == access.Email)
```

如果 `access.UserID` 是 `"alice@example.com"` 但 `scope.OwnerID` 存储的是 `"Alice@Example.com"`（大小写不一致），匹配就会失败。

**修复**：

```go
case VisibilityPrivate:
    owner := strings.TrimSpace(strings.ToLower(scope.OwnerID))
    return owner != "" && (owner == strings.ToLower(access.UserID) || 
                           owner == strings.ToLower(access.Email))
```

### 5.2 故障：超级管理员看不到被软删除的资源

**现象**：SuperAdmin 查询资源列表，但被标记为 `status='deleted'` 的资源仍然出现。

**根因**：`ListResourceScopes` 没有默认过滤 `status='active'`：

```go
// 有问题的代码
query := resourceScopeSelectSQL()
if len(clauses) > 0 {
    query += " WHERE " + strings.Join(clauses, " AND ")
}
```

**修复**：添加默认 active 过滤：

```go
func (r *Repository) ListResourceScopes(ctx context.Context, filter ResourceScopeFilter) ([]ResourceScope, error) {
    clauses := []string{}
    args := []interface{}{}
    
    // 默认只返回活跃资源
    clauses = append(clauses, "status = ?")
    args = append(args, "active")
    
    // 其他过滤条件...
}
```

### 5.3 性能问题：资源列表查询慢（1000+ 资源）

**现象**：`ListVisibleResourceScopes` 返回需要 2+ 秒。

**根因**：先 `SELECT * FROM resource_scopes` 拉全量数据，再 Go 内存过滤。

**优化方案**：

```go
func (r *Repository) ListVisibleResourceScopesOptimized(
    ctx context.Context, 
    access governance.AccessContext, 
    filter governance.ResourceScopeFilter,
) ([]governance.ResourceScope, error) {
    
    access = normalizeAccessContext(access)
    
    var clauses []string
    var args []interface{}
    
    clauses = append(clauses, "rs.status = 'active'")
    
    // 应用过滤器
    if v := strings.TrimSpace(filter.ResourceType); v != "" {
        clauses = append(clauses, "rs.resource_type = ?")
        args = append(args, v)
    }
    
    // 可见性过滤 — 转换为 SQL
    visibilityClause := buildVisibilitySQL(access)
    clauses = append(clauses, "(" + visibilityClause + ")")
    args = append(visibilityClauseArgs(access)...)
    
    query := `
        SELECT rs.id, rs.resource_type, rs.resource_id, rs.tenant_id,
               rs.workspace_id, rs.domain_id, rs.visibility, rs.owner_id,
               rs.status, rs.metadata, rs.created_at, rs.updated_at
        FROM resource_scopes rs
        WHERE ` + strings.Join(clauses, " AND ") + `
        ORDER BY rs.domain_id, rs.resource_type, rs.visibility, rs.resource_id
    `
    
    rows, err := r.db.QueryContext(ctx, query, args...)
    // ... 扫描结果
}

func buildVisibilitySQL(access governance.AccessContext) string {
    parts := []string{
        "rs.visibility IN ('system', 'domain_template', 'public')",
        fmt.Sprintf(
            "(rs.visibility = 'tenant_shared' AND (rs.tenant_id IS NULL OR rs.tenant_id = '%s'))",
            escapeSQL(access.TenantID),
        ),
        fmt.Sprintf(
            "(rs.visibility = 'workspace' AND (rs.tenant_id IS NULL OR rs.tenant_id = '%s') AND (rs.workspace_id IS NULL OR rs.workspace_id = '%s'))",
            escapeSQL(access.TenantID), escapeSQL(access.WorkspaceID),
        ),
        fmt.Sprintf(
            "(rs.visibility = 'private' AND rs.owner_id = '%s')",
            escapeSQL(access.UserID),
        ),
    }
    return strings.Join(parts, " OR ")
}
```

---

## 六、Trade-off 分析

### 6.1 内存过滤 vs SQL 过滤

| 维度 | 内存过滤（当前实现） | SQL 过滤（优化方案） |
|------|-------------------|-------------------|
| 实现复杂度 | 低 — 逻辑集中 | 中 — SQL 构建复杂 |
| 查询性能 | O(n) 全表扫描 | O(log n) 索引扫描 |
| 灵活性 | 高 — 可加任意业务逻辑 | 低 — 受 SQL 表达能力限制 |
| 维护成本 | 低 | 中 — SQL 需测试 |
| 适用场景 | < 500 资源 | > 1000 资源 |

**建议**：资源数 < 500 时使用内存过滤（简单可靠），> 1000 时切换到 SQL 过滤 + 缓存。

### 6.2 字符串 ID vs UUID

| 维度 | 字符串 ID（当前） | UUID |
|------|----------------|-----|
| 可读性 | ✅ 高 — 一眼看出归属 | ❌ 随机字符串 |
| 安全性 | ⚠️ 可枚举 | ✅ 不可预测 |
| 分布式生成 | ⚠️ 需要协调 | ✅ 本地生成 |
| 索引效率 | ✅ 前缀匹配友好 | ⚠️ 随机值导致页分裂 |

**建议**：对于内部治理系统，字符串 ID 更可取。如果需要防止枚举攻击，可在 ID 中加入随机盐值。

### 6.3 层级模型 vs 扁平模型

```
层级模型（当前）: Domain → Tenant → Workspace → User
扁平模型替代方案: 每个资源直接绑定 [user_id, role, resource_id]

层级优势:
- 继承性：WorkspaceAdmin 自动获得 Workspace 内所有权限
- 批量管理：修改 Tenant 级别设置影响所有 Workspace
- 数据隔离天然保证

扁平优势:
- 更灵活：可以跨层级授权
- 查询更快：不需要多层 JOIN
- 适合极端细粒度权限（每行数据不同权限）
```

**结论**：DAP 选择层级模型是正确的 — 广告平台的权限粒度通常到"资源级别"就够了，不需要到"行级别"。

---

## 七、自测题

### Q1: 为什么 `canAccessScope` 中 super_admin 可以直接跳过可见性过滤？

**答案**：超级管理员的角色语义是"平台级完全访问权"。在 DAP 的设计中，super_admin 是平台运营者，不是某个租户的用户。如果 super_admin 也要受 visibility 限制，那么：
1. 平台运营者无法调试租户问题
2. 无法审计资源使用情况
3. 无法管理系统级能力

因此 super_admin 的权限检查简化为：`isSuperAdmin(role) → return all resources`。

### Q2: ResourceScopeID 生成规则中，为什么 private 类型的 ID 包含 owner，而其他类型不包含？

**答案**：因为 visibility 决定了资源的"共享范围"：
- **system/domain_template/public**：全局唯一，不需要 owner 区分
- **tenant_shared/workspace**：由 tenant/workspace 标识，唯一性由层级保证
- **private**：同一 resource_id 可能被多个用户各自创建一个副本（如 Alice 的 skill-X 和 Bob 的 skill-X 是不同的资源），所以必须用 owner 来区分

### Q3: 如果要将 DAP 治理模型迁移到 PostgreSQL，需要做哪些改动？

**答案**：
1. **TEXT → UUID**：`id` 列可改用 UUID 类型，但字符串拼接 ID 模式依然可行
2. **TIMESTAMP → TIMESTAMPTZ**：时区感知时间戳
3. **JSON 字段**：`metadata` 列改为 JSONB 类型以获得查询能力
4. **索引优化**：
   ```sql
   CREATE INDEX idx_resource_scopes_visibility_tenant ON resource_scopes(visibility, tenant_id);
   CREATE INDEX idx_resource_scopes_owner_status ON resource_scopes(owner_id, status) WHERE visibility = 'private';
   ```
5. **CTE 查询**：利用 CTE 实现层级权限递归查询
6. **Row Level Security (RLS)**：PostgreSQL 原生支持行级安全策略，可以替代部分 Go 层过滤逻辑

---

## 八、动手验证

### 8.1 本地搭建治理数据库

```bash
# 1. 初始化 SQLite 数据库
cd ~/ryan-personal-knowledge/knowledge/ad-platform-example
sqlite3 governance.db < schema.sql

# 2. 运行 EnsureDefaults 种子数据
go run cmd/bootstrap/main.go

# 3. 验证资源作用域
sqlite3 governance.db "SELECT resource_type, resource_id, visibility, owner_id FROM resource_scopes LIMIT 10;"
```

### 8.2 编写权限测试

```go
func TestCanAccessScope(t *testing.T) {
    tests := []struct {
        name     string
        access   governance.AccessContext
        scope    governance.ResourceScope
        expected bool
    }{
        {
            name: "system resource visible to everyone",
            access: governance.AccessContext{
                UserID: "anyone", Role: "user",
                TenantID: "t1", WorkspaceID: "w1",
            },
            scope: governance.ResourceScope{
                Visibility: "system", Status: "active",
            },
            expected: true,
        },
        {
            name: "private resource only visible to owner",
            access: governance.AccessContext{
                UserID: "alice@example.com", Role: "user",
                TenantID: "t1", WorkspaceID: "w1",
            },
            scope: governance.ResourceScope{
                Visibility: "private", Status: "active",
                OwnerID: "bob@example.com",
            },
            expected: false,
        },
        {
            name: "tenant shared visible within same tenant",
            access: governance.AccessContext{
                UserID: "alice", Role: "user",
                TenantID: "t1", WorkspaceID: "w1",
            },
            scope: governance.ResourceScope{
                Visibility: "tenant_shared", Status: "active",
                TenantID: "t1",
            },
            expected: true,
        },
    }
    
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            result := canAccessScope(tt.access, tt.scope)
            if result != tt.expected {
                t.Errorf("got %v, want %v", result, tt.expected)
            }
        })
    }
}
```

---

## 九、与知识库的对照

### 已有内容

| 文件 | 覆盖度 | 说明 |
|------|--------|------|
| `ad-ads/ad-iam-deep.md` (1268行) | ⭐⭐⭐ | 覆盖 OAuth 2.0/JWT 通用 IAM 模型，但不含 DAP 实际治理架构 |
| `microservice/resilience-patterns-deep.md` | ⭐⭐ | 涉及熔断/限流，不涉及治理层 |
| `architecture-patterns/cqrs-event-sourcing-deep.md` | ⭐⭐ | CQRS 模式，与治理模型间接相关 |

### 本文件补充的独特价值

1. **DAP 生产源码级治理模型** — 六级 visibility 过滤引擎、三级层次结构、系统能力与计费绑定
2. **ResourceScope 统一资源模型** — 一张表管理所有资源类型的可见性
3. **Entitlement 许可检查引擎** — 双层检查（显式许可 → 系统能力默认）
4. **性能优化方案** — SQL 过滤改写 + 缓存策略 + 索引设计
5. **生产排障案例** — 大小写敏感 bug、软删除过滤、O(n) 性能瓶颈

### 缺失内容（建议后续补充）

1. **OAuth 2.0 PKCE 实现** — DAP 当前使用 session cookie，未实现标准 PKCE 流程
2. **RBAC 到 ABAC 的演进路径** — 当前是纯 RBAC + visibility，可考虑引入属性基访问控制
3. **审计日志系统** — 记录谁在何时访问了什么资源（合规要求）
4. **跨租户资源分享协议** — 当前不支持跨租户共享（visibility 中没有 cross-tenant 选项）
