# Security Core — 安全核心知识体系

> 个人知识库 · 安全板块
> 广告平台技术 TL · 2026-06-12

---

## 目录

1. [入门引导 — 5 分钟速览](#1-入门引导--5-分钟速览)
2. [OAuth2 & JWT — 认证与授权](#2-oauth2--jwt--认证与授权)
3. [RBAC — 基于角色的权限控制](#3-rbac--基于角色的权限控制)
4. [WAF — Web 应用防火墙](#4-waf--web-应用防火墙)
5. [DDoS 防护 — 流量清洗与限流](#5-ddos-防护--流量清洗与限流)
6. [自测题](#6-自测题)

---

## 1. 入门引导 — 5 分钟速览

### 1.1 安全三板斧

```
认证(Authentication)  → 你是谁？    JWT / OAuth2 / Session
授权(Authorization)   → 你能做什么？RBAC / ABAC / ACL
审计(Auditing)        → 你做了什么？日志 / Trace / SIEM
```

### 1.2 威胁模型速览

| 威胁类型 | 攻击面 | 典型防护 |
|----------|--------|----------|
| SQL 注入 | 数据库查询拼接 | 参数化查询 + WAF 规则 |
| XSS | 前端脚本注入 | CSP + 输出编码 + WAF |
| CSRF | 跨站请求伪造 | SameSite Cookie + Token |
| DDoS | 流量洪泛 | CDN + 限流 + 清洗 |
| Token 劫持 | 认证凭证泄露 | HTTPS + HttpOnly + 短 TTL |

### 1.3 广告平台安全关注点

- **API 鉴权**：广告主/代理商/运营三方角色隔离
- **计费安全**：防止点击欺诈、刷量
- **数据脱敏**：用户 PII 字段加密存储
- **合规**：GDPR / CCPA 数据主权

### 1.4 Go 安全生态速查

```
go get golang.org/x/crypto/bcrypt      # 密码哈希
go get github.com/golang-jwt/jwt/v5     # JWT 处理
go get github.com/go-chi/chi/v5         # HTTP 路由（含中间件）
go get github.com/ulule/limiter/v3      # 速率限制
go get github.com/go-playground/validator/v10  # 参数校验
```

---

## 2. OAuth2 & JWT — 认证与授权

### 2.1 OAuth2 四种授权模式

#### 2.1.1 Authorization Code（服务端应用标配）

```
Client                    Authorization Server              Resource Owner
  |                              |                                |
  |--- 1. 跳转授权页面 --------->|                                |
  |                              |<=== 1. 用户登录 + 授权 ========|
  |<== 2. 重定向 + code ---------|                                |
  |--- 2. POST code + client_secret -->|                           |
  |                              |                                |
  |<== 3. access_token ----------|                                |
  |--- 3. 带 token 访问 API ---->|                                |
  |<== 4. 资源 ------------------|                                |
```

**核心要点：**
- `code` 是一次性的，有效期极短（通常 5 分钟）
- 必须在后端交换 token，绝不能在前端暴露 `client_secret`
- 必须校验 `state` 参数防 CSRF

#### 2.1.2 Implicit（已废弃，SPA 场景改用 PKCE）

- 直接返回 `access_token` 在 URL fragment 中
- 无 `client_secret`，适合纯前端应用
- RFC 6819 已标记为 deprecated

#### 2.1.3 Resource Owner Password Credentials（信任第一方时可用）

```
Client → 用户名 + 密码 → Auth Server → access_token
```

- 高信任场景（自有 App）
- 不推荐第三方使用，因为绕过了授权页面
- 不支持 refresh token 轮换

#### 2.1.4 Client Credentials（机器对机器）

```
Service A → client_id + client_secret → Auth Server → access_token → Service B
```

- 微服务间调用、后台任务
- 无用户上下文，只有客户端身份
- 适用于广告平台的内部服务通信

### 2.2 JWT 结构深度解析

JWT = Header.Payload.Signature，以 `.` 分隔的三段 Base64URL 编码字符串。

```
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.          ← Header (alg, typ)
eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IlJ5YW4iLCJyb2xlcyI6WyJhZG1pbiJdfQ.  ← Payload (claims)
SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c       ← Signature (HMAC/RS256)
```

#### Header 结构

```json
{
  "alg": "RS256",
  "typ": "JWT",
  "kid": "key-id-2026"
}
```

- `alg`: 签名算法，HS256(对称)/RS256(RSA)/ES256(ECDSA)
- `kid`: Key ID，用于多密钥轮换时选择正确的公钥
- **坑**：攻击者可篡改 alg 为 `none` 绕过验证（需服务端严格校验）

#### Payload 标准 Claims

| Claim | 说明 | 示例 |
|-------|------|------|
| `iss` | Issuer 签发者 | `"ads-platform-auth"` |
| `sub` | Subject 主体 | `"user-12345"` |
| `aud` | Audience 受众 | `"advertiser-api"` |
| `exp` | Expiration 过期时间 | `1718200000` |
| `iat` | Issued At 签发时间 | `1718196400` |
| `jti` | JWT ID 唯一标识 | `"uuid-v4"` |

#### Go 实现：完整 JWT 签发与验证

```go
package security

import (
	"errors"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// JWTClaims 自定义 JWT claims，嵌入标准 claims
type JWTClaims struct {
	UserID   string                       `json:"uid"`
	Username string                       `json:"username"`
	Roles    []string                     `json:"roles"`
	Scopes   []string                     `json:"scopes"`
	jwt.RegisteredClaims
}

// JWTManager JWT 管理器，负责签发和验证
type JWTManager struct {
	secretKey []byte        // HS256 用对称密钥；RS256 则用私钥
	pubKey    interface{}   // RS256 用公钥验证
	method    jwt.SigningMethod
	tokenTTL  time.Duration
}

// NewJWTManagerHS256 创建 HS256 签名的 JWT Manager
func NewJWTManagerHS256(secretKey []byte, ttl time.Duration) *JWTManager {
	return &JWTManager{
		secretKey: secretKey,
		method:    jwt.SigningMethodHS256,
		tokenTTL:  ttl,
	}
}

// NewJWTManagerRS256 创建 RS256 签名的 JWT Manager
func NewJWTManagerRS256(privateKey interface{}, publicKey interface{}, ttl time.Duration) *JWTManager {
	return &JWTManager{
		pubKey: publicKey,
		method: jwt.SigningMethodRS256,
		tokenTTL: ttl,
	}
}

// GenerateToken 签发 JWT
func (jm *JWTManager) GenerateToken(userID, username string, roles, scopes []string) (string, error) {
	now := time.Now()
	claims := JWTClaims{
		UserID:   userID,
		Username: username,
		Roles:    roles,
		Scopes:   scopes,
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:    "ads-platform",
			Subject:   userID,
			Audience:  jwt.ClaimStrings{"advertiser-api"},
			ExpiresAt: jwt.NewNumericDate(now.Add(jm.tokenTTL)),
			IssuedAt:  jwt.NewNumericDate(now),
			ID:        fmt.Sprintf("%d-%s", now.UnixNano(), userID),
		},
	}

	token := jwt.NewWithClaims(jm.method, claims)

	var (
		signed string
		err    error
	)
	if jm.pubKey != nil {
		// RS256: 私钥签名
		signed, err = token.SignedString(jm.secretKey)
	} else {
		// HS256: 对称密钥签名
		signed, err = token.SignedString(jm.secretKey)
	}
	if err != nil {
		return "", fmt.Errorf("sign jwt: %w", err)
	}
	return signed, nil
}

// ValidateToken 验证 JWT，返回 claims
func (jm *JWTManager) ValidateToken(tokenStr string) (*JWTClaims, error) {
	token, err := jwt.ParseWithClaims(tokenStr, &JWTClaims{}, func(token *jwt.Token) (interface{}, error) {
		// 防御: alg 篡改攻击
		if token.Method != jm.method {
			return nil, fmt.Errorf("unexpected signing method: %v", token.Header["alg"])
		}
		if jm.pubKey != nil {
			return jm.pubKey, nil
		}
		return jm.secretKey, nil
	})
	if err != nil {
		return nil, fmt.Errorf("parse jwt: %w", err)
	}

	claims, ok := token.Claims.(*JWTClaims)
	if !ok || !token.Valid {
		return nil, errors.New("invalid jwt token")
	}

	// 额外校验 audience
	if len(claims.Audience) > 0 {
		found := false
		for _, aud := range claims.Audience {
			if aud == "advertiser-api" {
				found = true
				break
			}
		}
		if !found {
			return nil, errors.New("jwt audience mismatch")
		}
	}

	return claims, nil
}
```

### 2.3 Token Refresh 机制

#### Refresh Token 最佳实践

```
Access Token:  TTL 15min, 无状态, 可快速吊销(黑名单)
Refresh Token: TTL 7days, 有状态(存 Redis), 支持轮换(ROTATION)
```

**Refresh Token Rotation（轮换）流程：**

```
1. Client 用旧 refresh_token 换取新 access_token + 新 refresh_token
2. 旧 refresh_token 立即失效（加入黑名单或从 Redis 删除）
3. 如果旧 token 再次出现 → 说明被泄露 → 吊销全部会话
```

#### Go 实现：Refresh Token 轮换

```go
package security

import (
	"crypto/rand"
	"encoding/hex"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// RefreshTokenManager 管理 refresh token 的签发、验证和轮换
type RefreshTokenManager struct {
	jwtMgr    *JWTManager
	store     TokenStore // Redis/DB 接口
	refreshTTL time.Duration
}

// TokenStore refresh token 持久化接口
type TokenStore interface {
	Set(key string, value string, ttl time.Duration) error
	Get(key string) (string, error)
	Delete(key string) error
	Exists(key string) (bool, error)
}

// NewRefreshTokenManager 创建 refresh token 管理器
func NewRefreshTokenManager(jm *JWTManager, store TokenStore, ttl time.Duration) *RefreshTokenManager {
	return &RefreshTokenManager{
		jwtMgr:     jm,
		store:      store,
		refreshTTL: ttl,
	}
}

// IssueRefreshToken 签发新的 refresh token
func (rm *RefreshTokenManager) IssueRefreshToken(userID string) (accessToken, refreshToken string, err error) {
	// 生成不可预测的 refresh token 值
	rawRT, err := generateRandomToken(64)
	if err != nil {
		return "", "", fmt.Errorf("generate refresh token: %w", err)
	}

	// 签发 access token（短 TTL）
	accessToken, err = rm.jwtMgr.GenerateToken(userID, "", []string{}, []string{})
	if err != nil {
		return "", "", fmt.Errorf("generate access token: %w", err)
	}

	// 将 refresh token 存入存储，绑定到 user 会话
	sessionID := fmt.Sprintf("session:%s", userID)
	if err := rm.store.Set(sessionID, rawRT, rm.refreshTTL); err != nil {
		return "", "", fmt.Errorf("store refresh token: %w", err)
	}

	return accessToken, rawRT, nil
}

// RotateRefreshToken 轮换 refresh token（核心安全逻辑）
func (rm *RefreshTokenManager) RotateRefreshToken(rawRT string) (accessToken string, newRawRT string, err error) {
	// 1. 从存储中查找该 refresh token 对应的 session
	// 注意：这里用 rawRT 的值作为 key 的反向索引
	// 实际实现中建议维护一个 rt→sessionID 的映射表
	sessionID, err := rm.lookupSessionByToken(rawRT)
	if err != nil {
		return "", "", fmt.Errorf("lookup session: %w", err)
	}

	// 2. 从 session 中获取旧的 refresh token 值进行比对
	oldRT, err := rm.store.Get(sessionID)
	if err != nil {
		return "", "", fmt.Errorf("get old refresh token: %w", err)
	}
	if oldRT != rawRT {
		// Token 已被轮换或被盗用 → 吊销整个会话
		rm.store.Delete(sessionID)
		return "", "", fmt.Errorf("refresh token revoked (possible theft)")
	}

	// 3. 生成新的 refresh token
	newRawRT, err = generateRandomToken(64)
	if err != nil {
		return "", "", fmt.Errorf("generate new refresh token: %w", err)
	}

	// 4. 覆盖存储中的旧 token（原子操作）
	if err := rm.store.Set(sessionID, newRawRT, rm.refreshTTL); err != nil {
		return "", "", fmt.Errorf("store new refresh token: %w", err)
	}

	// 5. 签发新的 access token
	accessToken, err = rm.jwtMgr.GenerateToken("", "", []string{}, []string{})
	if err != nil {
		return "", "", fmt.Errorf("generate access token: %w", err)
	}

	return accessToken, newRawRT, nil
}

// RevokeAllTokens 吊销用户所有 token（登出/安全事件）
func (rm *RefreshTokenManager) RevokeAllTokens(userID string) error {
	return rm.store.Delete(fmt.Sprintf("session:%s", userID))
}

// lookupSessionByToken 反向查找（实际实现需维护 rt→session 索引）
func (rm *RefreshTokenManager) lookupSessionByToken(rawRT string) (string, error) {
	// 简化实现：实际应在 Redis 中维护 rt_value → session_key 的映射
	return "", fmt.Errorf("not implemented: need reverse index")
}

// generateRandomToken 生成密码学安全的随机 token
func generateRandomToken(length int) (string, error) {
	bytes := make([]byte, length)
	if _, err := rand.Read(bytes); err != nil {
		return "", err
	}
	return hex.EncodeToString(bytes), nil
}
```

---

## 3. RBAC — 基于角色的权限控制

### 3.1 RBAC 模型演进

```
RBAC0: 基础模型 (Role ↔ User, Role ↔ Permission)
RBAC1: 层级角色 (Role Hierarchy, 继承)
RBAC2: 约束 (Separation of Duty, Cardinality)
RBAC3: 完整模型 (RBAC1 + RBAC2)
```

广告平台典型角色体系：

```
Admin (超级管理员)
├── Advertiser (广告主) - 管理自己的广告账户
│   ├── Campaign Manager (投放经理) - 创建/编辑广告计划
│   └── Reporter (报表查看) - 只读数据
├── Agency (代理商) - 管理多个广告主
│   ├── Account Manager (账户经理)
│   └── Creative Reviewer (素材审核员)
├── Operator (平台运营) - 内部运营
│   ├── Content Moderator (内容审核)
│   └── Data Analyst (数据分析)
└── Auditor (审计员) - 只读审计日志
```

### 3.2 Go 实现：RBAC 引擎

```go
package security

import (
	"context"
	"fmt"
	"sync"
)

// Permission 权限定义
type Permission struct {
	ID          string
	Resource    string // "ad", "campaign", "report", "billing"
	Action      string // "create", "read", "update", "delete", "approve"
	Description string
}

// Role 角色定义
type Role struct {
	ID           string
	Name         string
	Permissions  []Permission
	ParentRoles  []string // 角色继承链
}

// UserRole 用户-角色关联
type UserRole struct {
	UserID string
	RoleID string
}

// RBACEngine 内存版 RBAC 引擎
type RBACEngine struct {
	mu sync.RWMutex

	// 角色 → 权限映射
	rolePerms map[string][]Permission
	// 角色继承关系
	roleHierarchy map[string][]string
	// 用户 → 角色映射
	userRoles map[string][]string
	// 角色缓存
	roleCache map[string]Role
}

// NewRBACEngine 创建 RBAC 引擎
func NewRBACEngine() *RBACEngine {
	return &RBACEngine{
		rolePerms:     make(map[string][]Permission),
		roleHierarchy: make(map[string][]string),
		userRoles:     make(map[string][]string),
		roleCache:     make(map[string]Role),
	}
}

// AddRole 注册角色及其权限
func (re *RBACEngine) AddRole(role Role) {
	re.mu.Lock()
	defer re.mu.Unlock()

	re.rolePerms[role.ID] = role.Permissions
	re.roleHierarchy[role.ID] = role.ParentRoles
	re.roleCache[role.ID] = role
}

// AssignUserRole 给用户分配角色
func (re *RBACEngine) AssignUserRole(userRole UserRole) {
	re.mu.Lock()
	defer re.mu.Unlock()

	re.userRoles[userRole.UserID] = append(re.userRoles[userRole.UserID], userRole.RoleID)
}

// HasPermission 检查用户是否有指定权限（含角色继承）
func (re *RBACEngine) HasPermission(ctx context.Context, userID, resource, action string) bool {
	re.mu.RLock()
	defer re.mu.RUnlock()

	roleIDs := re.userRoles[userID]
	if len(roleIDs) == 0 {
		return false
	}

	// 收集所有可达权限（含继承）
	checkedRoles := make(map[string]bool)
	var allPerms []Permission

	for _, roleID := range roleIDs {
		if !re.collectRolePerms(roleID, checkedRoles, &allPerms) {
			continue
		}
	}

	// 精确匹配
	for _, perm := range allPerms {
		if perm.Resource == resource && perm.Action == action {
			return true
		}
	}

	return false
}

// collectRolePerms 递归收集角色及其父角色的权限
// 防止循环继承
func (re *RBACEngine) collectRolePerms(roleID string, visited map[string]bool, perms *[]Permission) bool {
	if visited[roleID] {
		return true // 检测到循环，终止
	}
	visited[roleID] = true

	rolePerms, ok := re.rolePerms[roleID]
	if !ok {
		return true
	}
	*perms = append(*perms, rolePerms...)

	// 递归收集父角色权限
	parentRoles := re.roleHierarchy[roleID]
	for _, parentID := range parentRoles {
		re.collectRolePerms(parentID, visited, perms)
	}

	return true
}

// GetUserRoles 获取用户的所有角色（含继承）
func (re *RBACEngine) GetUserRoles(ctx context.Context, userID string) []string {
	re.mu.RLock()
	defer re.mu.RUnlock()

	roleIDs := re.userRoles[userID]
	result := make([]string, 0, len(roleIDs))
	visited := make(map[string]bool)

	for _, roleID := range roleIDs {
		re.collectRoleNames(roleID, visited, &result)
	}

	return result
}

func (re *RBACEngine) collectRoleNames(roleID string, visited map[string]bool, names *[]string) {
	if visited[roleID] {
		return
	}
	visited[roleID] = true

	if role, ok := re.roleCache[roleID]; ok {
		*names = append(*names, role.Name)
	}

	for _, parentID := range re.roleHierarchy[roleID] {
		re.collectRoleNames(parentID, visited, names)
	}
}

// CheckAndMiddleware RBAC 中间件（适配 chi 风格）
type RBACMiddleware struct {
	engine *RBACEngine
}

// RequirePermission 创建权限检查中间件
func (rm *RBACMiddleware) RequirePermission(resource, action string) func(next http.Handler) http.Handler {
	return func(next http.Handler) http.Handler {
		return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			// 从 context 中获取用户 ID（由 JWT 中间件填充）
			userID := r.Context().Value(ctxUserID).(string)

			if !rm.engine.HasPermission(r.Context(), userID, resource, action) {
				http.Error(w, "403 Forbidden", http.StatusForbidden)
				return
			}

			next.ServeHTTP(w, r)
		})
	}
}

// 辅助 context key
type ctxKey string

const ctxUserID ctxKey = "userID"
```

### 3.3 性能优化：预计算权限集

对于高频请求场景，RBAC 实时递归效率低，应预计算：

```go
// PermissionSet 预计算的权限集合，O(1) 查询
type PermissionSet struct {
	mu     sync.RWMutex
	permMap map[string]map[string]bool // userID → resource:action → true
}

func NewPermissionSet() *PermissionSet {
	return &PermissionSet{
		permMap: make(map[string]map[string]bool),
	}
}

// Invalidate 用户角色变更时刷新缓存
func (ps *PermissionSet) Invalidate(userID string) {
	ps.mu.Lock()
	defer ps.mu.Unlock()
	delete(ps.permMap, userID)
}

// Has 预计算后的 O(1) 权限检查
func (ps *PermissionSet) Has(userID, resource, action string) bool {
	ps.mu.RLock()
	defer ps.mu.RUnlock()

	actions, ok := ps.permMap[userID]
	if !ok {
		return false
	}
	key := resource + ":" + action
	return actions[key]
}
```

---

## 4. WAF — Web 应用防火墙

### 4.1 WAF 防护层架构

```
Client → CDN/WAF → API Gateway → Backend Service
              ↑
         规则引擎 + 行为分析
```

WAF 三层防护：

| 层 | 检测方式 | 覆盖范围 |
|----|---------|---------|
| L7 规则匹配 | 正则 + AST | SQLi / XSS / Path Traversal |
| 语义分析 | 语法树 | 编码绕过 / 混淆攻击 |
| 行为分析 | 统计 + ML | 0day / 未知攻击 |

### 4.2 SQL 注入防护

#### 原理

SQL 注入本质是**数据与代码边界被破坏**。参数化查询（Prepared Statement）是最根本的解法。

#### Go 实现：SQL 注入检测器

```go
package security

import (
	"regexp"
	"strings"
)

// SQLInjectionDetector SQL 注入检测器
type SQLInjectionDetector struct {
	patterns []*regexp.Regexp
}

// NewSQLInjectionDetector 创建检测器
func NewSQLInjectionDetector() *SQLInjectionDetector {
	d := &SQLInjectionDetector{}

	// 经典 SQL 注入模式
	patterns := []string{
		`(--|#|/\*)`,                          // 注释符
		`(\b(union\s+all\s+)?select\b)`,       // UNION SELECT
		`(\b(select|insert|update|delete)\s+\w+\s+from\b)`, // DML
		`(\bdrop\s+table\b|\balter\s+table\b)`, // DDL
		`(\bor\b\s+\d+\s*=\s*\d+)`,            // OR 1=1
		`(\band\b\s+\d+\s*=\s*\d+)`,           // AND 1=1
		`(\bexec\b|\bexecute\b)`,              // 执行
		`(\bxp_cmdshell\b|\bsp_execsql\b)`,    // 扩展存储过程
		`(\binformation_schema\b|\bsysobjects\b)`, // 元数据探测
		`(\bwaitfor\s+delay\b|\bbenchmark\b)`, // 时间盲注
		`(\bload_file\b|\bsqlite_master\b)`,   // 文件读取
		`('\s*(or|and)\s+')`,                  // 引号闭合
	}

	for _, p := range patterns {
		d.patterns = append(d.patterns, regexp.MustCompile("(?i)"+p))
	}

	return d
}

// Detect 检测输入是否包含 SQL 注入特征
func (d *SQLInjectionDetector) Detect(input string) bool {
	if input == "" {
		return false
	}

	// 先解码常见编码
	decoded := decodeSQLInput(input)

	for _, pattern := range d.patterns {
		if pattern.MatchString(decoded) {
			return true
		}
	}

	return false
}

// decodeSQLInput 解码常见编码绕过手法
func decodeSQLInput(input string) string {
	// URL 解码
	decoded := input
	// Hex 解码 (\xHH)
	// Unicode 解码 (\uHHHH)
	// 双字节编码 (%25XX)
	return decoded
}

// SafeQuery 安全查询封装（参数化查询）
func SafeQuery(query string, args ...interface{}) (string, []interface{}) {
	// 生产环境应使用 database/sql 的占位符机制
	// 此处仅做演示
	return query, args
}
```

### 4.3 XSS 防护

#### 三种 XSS 类型

```
Stored XSS:    恶意脚本存入数据库 → 所有访问者中招（最危险）
Reflected XSS: 恶意链接反射回来 → 钓鱼攻击
DOM-based XSS: 纯前端 JS 操作 DOM 导致的注入
```

#### Go 实现：XSS 检测与净化

```go
package security

import (
	"regexp"
	"strings"
)

// XSSDetector XSS 检测器
type XSSDetector struct {
	scriptPatterns   []*regexp.Regexp
	eventHandlerRe   *regexp.Regexp
	dataURIRe          *regexp.Regexp
}

// NewXSSDetector 创建 XSS 检测器
func NewXSSDetector() *XSSDetector {
	d := &XSSDetector{}

	d.scriptPatterns = []*regexp.Regexp{
		regexp.MustCompile(`(?i)<script[^>]*>.*?</script>`),
		regexp.MustCompile(`(?i)javascript\s*:`),
		regexp.MustCompile(`(?i)vbscript\s*:`),
		regexp.MustCompile(`(?i)expression\s*\(`),
		regexp.MustCompile(`(?i)eval\s*\(`),
		regexp.MustCompile(`(?i)document\.cookie`),
		regexp.MustCompile(`(?i)document\.location`),
		regexp.MustCompile(`(?i)window\.open`),
		regexp.MustCompile(`(?i)<iframe[^>]*>`),
		regexp.MustCompile(`(?i)<object[^>]*>`),
		regexp.MustCompile(`(?i)<embed[^>]*>`),
		regexp.MustCompile(`(?i)<form[^>]*>`),
		regexp.MustCompile(`(?i)<img[^>]*on\w+\s*=`),
		regexp.MustCompile(`(?i)<svg[^>]*on\w+\s*=`),
		regexp.MustCompile(`(?i)<body[^>]*onload\s*=`),
	}

	d.eventHandlerRe = regexp.MustCompile(`(?i)on(?:click|load|error|mouseover|focus|blur|submit|change)\s*=`)
	d.dataURIRe = regexp.MustCompile(`(?i)data\s*:\s*text/html`)

	return d
}

// DetectXSS 检测 XSS 攻击
func (d *XSSDetector) DetectXSS(input string) bool {
	if input == "" {
		return false
	}

	// 解码 HTML 实体
	decoded := decodeHTMLInput(input)

	for _, pattern := range d.scriptPatterns {
		if pattern.MatchString(decoded) {
			return true
		}
	}

	if d.eventHandlerRe.MatchString(decoded) {
		return true
	}

	if d.dataURIRe.MatchString(decoded) {
		return true
	}

	return false
}

// SanitizeHTML 净化 HTML（白名单方式）
func SanitizeHTML(input string) string {
	// 生产环境应使用 bluemonday 库
	// 此处展示核心逻辑
	input = strings.ReplaceAll(input, "<", "&lt;")
	input = strings.ReplaceAll(input, ">", "&gt;")
	input = strings.ReplaceAll(input, "&", "&amp;")
	input = strings.ReplaceAll(input, "\"", "&quot;")
	return input
}

// decodeHTMLInput 解码 HTML 实体
func decodeHTMLInput(input string) string {
	replacements := map[string]string{
		"&lt;":  "<",
		"&gt;":  ">",
		"&amp;": "&",
		"&quot;": `"`,
		"&#x":   "", // 十六进制实体
		"&#":    "", // 十进制实体
	}
	for old, new := range replacements {
		input = strings.ReplaceAll(input, old, new)
	}
	return input
}
```

### 4.4 CSRF 防护

#### 双重 Cookie 机制

```
1. Server 设置 CSRF token 到 HttpOnly Cookie
2. Server 将同一 token 写入隐藏表单字段或 Response Header
3. 浏览器提交请求时同时携带 Cookie 和表单 token
4. Server 比对两者是否一致
```

#### Go 实现：CSRF 中间件

```go
package security

import (
	"crypto/rand"
	"encoding/base64"
	"net/http"
	"strings"
)

// CSRFProtection CSRF 防护中间件
type CSRFProtection struct {
	tokenLength int
	headerName  string
	cookieName  string
	exemptPaths []string // 豁免路径（如 GET/HEAD/OPTIONS）
}

// NewCSRFProtection 创建 CSRF 防护
func NewCSRFProtection() *CSRFProtection {
	return &CSRFProtection{
		tokenLength: 32,
		headerName:  "X-CSRF-Token",
		cookieName:  "_csrf",
		exemptPaths: []string{"GET", "HEAD", "OPTIONS"},
	}
}

// GenerateToken 生成 CSRF token
func (cp *CSRFProtection) GenerateToken() string {
	bytes := make([]byte, cp.tokenLength)
	rand.Read(bytes)
	return base64.StdEncoding.EncodeToString(bytes)
}

// Middleware CSRF 防护中间件
func (cp *CSRFProtection) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 豁免安全方法
		for _, method := range cp.exemptPaths {
			if r.Method == method {
				next.ServeHTTP(w, r)
				return
			}
		}

		// 从 Cookie 读取 token
		cookie, err := r.Cookie(cp.cookieName)
		if err != nil {
			http.Error(w, "CSRF token missing", http.StatusForbidden)
			return
		}

		// 从 Header 或 Form 读取 token
		formToken := r.FormValue("_csrf")
		headerToken := r.Header.Get(cp.headerName)
		queryToken := r.URL.Query().Get("_csrf")

		token := formToken
		if token == "" {
			token = headerToken
		}
		if token == "" {
			token = queryToken
		}

		// 恒定时间比较（防时序攻击）
		if !constantTimeCompare(cookie.Value, token) {
			http.Error(w, "CSRF token mismatch", http.StatusForbidden)
			return
		}

		next.ServeHTTP(w, r)
	})
}

// constantTimeCompare 恒定时间字符串比较
func constantTimeCompare(a, b string) bool {
	if len(a) != len(b) {
		return false
	}
	var diff uint64
	for i := 0; i < len(a); i++ {
		diff |= uint64(a[i] ^ b[i])
	}
	return diff == 0
}
```

### 4.5 综合 WAF 中间件

```go
package security

import (
	"net/http"
	"strings"
)

// WAFMiddleware 综合 WAF 中间件
type WAFMiddleware struct {
	sqlDetector   *SQLInjectionDetector
	xssDetector   *XSSDetector
	csrfProtect   *CSRFProtection
	maxBodySize   int64
	allowedOrigin string // CORS
}

// NewWAFMiddleware 创建 WAF 中间件
func NewWAFMiddleware() *WAFMiddleware {
	return &WAFMiddleware{
		sqlDetector:   NewSQLInjectionDetector(),
		xssDetector:   NewXSSDetector(),
		csrfProtect:   NewCSRFProtection(),
		maxBodySize:   1 << 20, // 1MB
		allowedOrigin: "https://ads-platform.example.com",
	}
}

// Handler 综合 WAF 处理函数
func (w *WAFMiddleware) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 1. 请求头安全检查
		w.checkHeaders(w, r)

		// 2. Body 大小限制
		r.Body = http.MaxBytesReader(w, r.Body, w.maxBodySize)

		// 3. URL Path 检查
		if w.sqlDetector.Detect(r.URL.Path) || w.xssDetector.DetectXSS(r.URL.Path) {
			w.logAttack(r, "path_injection")
			http.Error(w, "Bad Request", http.StatusBadRequest)
			return
		}

		// 4. Query Parameter 检查
		q := r.URL.Query()
		for _, vals := range q {
			for _, val := range vals {
				if w.sqlDetector.Detect(val) {
					w.logAttack(r, "sql_injection_query")
					http.Error(w, "Bad Request", http.StatusBadRequest)
					return
				}
				if w.xssDetector.DetectXSS(val) {
					w.logAttack(r, "xss_query")
					http.Error(w, "Bad Request", http.StatusBadRequest)
					return
				}
			}
		}

		// 5. Form Body 检查（POST/PUT/PATCH）
		if r.Method == "POST" || r.Method == "PUT" || r.Method == "PATCH" {
			if err := r.ParseForm(); err == nil {
				for _, vals := range r.Form {
					for _, val := range vals {
						if w.sqlDetector.Detect(val) {
							w.logAttack(r, "sql_injection_body")
							http.Error(w, "Bad Request", http.StatusBadRequest)
							return
						}
						if w.xssDetector.DetectXSS(val) {
							w.logAttack(r, "xss_body")
							http.Error(w, "Bad Request", http.StatusBadRequest)
							return
						}
					}
				}
			}
		}

		// 6. JSON Body 检查（Content-Type: application/json）
		if strings.HasPrefix(r.Header.Get("Content-Type"), "application/json") {
			// JSON body 需要在读取 body 前做检查
			// 生产环境应使用 json.Decoder 逐字段校验
		}

		// 通过所有检查
		next.ServeHTTP(w, r)
	})
}

func (w *WAFMiddleware) checkHeaders(w http.ResponseWriter, r *http.Request) {
	// 禁止敏感 header
	bannedHeaders := []string{"X-Forwarded-For", "X-Real-IP"}
	for _, h := range bannedHeaders {
		if r.Header.Get(h) != "" {
			// 记录但不阻止（上游代理可能设置）
		}
	}
}

func (w *WAFMiddleware) logAttack(r *http.Request, attackType string) {
	// 生产环境接入 ELK/Splunk
	// log.Printf("[WAF] attack=%s ip=%s path=%s ua=%s", attackType, r.RemoteAddr, r.URL.Path, r.UserAgent())
}
```

---

## 5. DDoS 防护 — 流量清洗与限流

### 5.1 DDoS 攻击分类

```
Volume-based (带宽消耗)
  ├─ UDP Flood
  ├─ ICMP Flood
  └─ DNS Amplification

Protocol (协议栈消耗)
  ├─ SYN Flood
  ├─ ACK Flood
  └─ Slowloris (连接保持)

Application Layer (应用层)
  ├─ HTTP Flood
  ├─ Slow POST
  └─ Search/API Abuse
```

### 5.2 限流算法

| 算法 | 特点 | 适用场景 |
|------|------|---------|
| Fixed Window | 简单但有临界突刺 | 全局 QPS 限制 |
| Sliding Window | 平滑过渡，内存占用高 | 精细限流 |
| Token Bucket | 允许突发，匀速补充 | API 限流（最常用） |
| Leaky Bucket | 匀速流出，拒绝突发 | 消息队列 |
| GCRA (GNU Clock) | 理论最优，精确控制 | 高性能网关 |

### 5.3 Go 实现：多层限流器

```go
package security

import (
	"sync"
	"time"
)

// RateLimiter 限流器接口
type RateLimiter interface {
	Allow(key string) bool
	Reset(key string)
}

// --- Token Bucket 实现 ---

// TokenBucket 令牌桶限流器
type TokenBucket struct {
	mu         sync.Mutex
	tokens     float64
	maxTokens  float64
	refillRate float64 // tokens per second
	lastRefill time.Time
}

// NewTokenBucket 创建令牌桶
func NewTokenBucket(maxTokens float64, refillRate float64) *TokenBucket {
	return &TokenBucket{
		tokens:     maxTokens,
		maxTokens:  maxTokens,
		refillRate: refillRate,
		lastRefill: time.Now(),
	}
}

// Allow 尝试获取一个 token
func (tb *TokenBucket) Allow() bool {
	tb.mu.Lock()
	defer tb.mu.Unlock()

	now := time.Now()
	elapsed := now.Sub(tb.lastRefill).Seconds()
	tb.tokens += elapsed * tb.refillRate
	if tb.tokens > tb.maxTokens {
		tb.tokens = tb.maxTokens
	}
	tb.lastRefill = now

	if tb.tokens >= 1.0 {
		tb.tokens -= 1.0
		return true
	}
	return false
}

// --- Per-Key Rate Limiter (分布式友好) ---

// PerKeyLimiter 每个 key 独立的限流器
type PerKeyLimiter struct {
	mu        sync.Mutex
	limiters  map[string]*TokenBucket
	maxTokens float64
	refillRate float64
	cleanupInterval time.Duration
	stopChan  chan struct{}
}

// NewPerKeyLimiter 创建 per-key 限流器
func NewPerKeyLimiter(maxTokens, refillRate float64, cleanupInterval time.Duration) *PerKeyLimiter {
	pl := &PerKeyLimiter{
		limiters:      make(map[string]*TokenBucket),
		maxTokens:     maxTokens,
		refillRate:    refillRate,
		cleanupInterval: cleanupInterval,
		stopChan:      make(chan struct{}),
	}
	go pl.cleanupLoop()
	return pl
}

// Allow 对指定 key 执行限流
func (pl *PerKeyLimiter) Allow(key string) bool {
	pl.mu.Lock()
	bucket, exists := pl.limiters[key]
	if !exists {
		bucket = NewTokenBucket(pl.maxTokens, pl.refillRate)
		pl.limiters[key] = bucket
	}
	pl.mu.Unlock()

	return bucket.Allow()
}

// Reset 重置指定 key 的限流状态
func (pl *PerKeyLimiter) Reset(key string) {
	pl.mu.Lock()
	delete(pl.limiters, key)
	pl.mu.Unlock()
}

// Stop 停止清理协程
func (pl *PerKeyLimiter) Stop() {
	close(pl.stopChan)
}

// cleanupLoop 定期清理长时间未使用的 key
func (pl *PerKeyLimiter) cleanupLoop() {
	ticker := time.NewTicker(pl.cleanupInterval)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			pl.mu.Lock()
			// 简化：每轮清理一半的 key（生产环境应维护 LastAccess 时间）
			count := 0
			for k := range pl.limiters {
				if count > len(pl.limiters)/2 {
					break
				}
				delete(pl.limiters, k)
				count++
			}
			pl.mu.Unlock()
		case <-pl.stopChan:
			return
		}
	}
}

// --- Sliding Window Counter 滑动窗口计数器 ---

// SlidingWindowCounter 滑动窗口限流器（精确计数）
type SlidingWindowCounter struct {
	mu        sync.Mutex
	windowSize time.Duration
	maxCalls  int64
	requests  []time.Time // 请求时间戳列表
}

// NewSlidingWindowCounter 创建滑动窗口限流器
func NewSlidingWindowCounter(windowSize time.Duration, maxCalls int64) *SlidingWindowCounter {
	return &SlidingWindowCounter{
		windowSize: windowSize,
		maxCalls:   maxCalls,
		requests:   make([]time.Time, 0),
	}
}

// Allow 检查是否在限流范围内
func (sw *SlidingWindowCounter) Allow() bool {
	sw.mu.Lock()
	defer sw.mu.Unlock()

	now := time.Now()
	cutoff := now.Add(-sw.windowSize)

	// 移除窗口外的请求
	idx := 0
	for idx < len(sw.requests) && sw.requests[idx].Before(cutoff) {
		idx++
	}
	if idx > 0 {
		sw.requests = sw.requests[idx:]
	}

	// 判断是否超限
	if int64(len(sw.requests)) >= sw.maxCalls {
		return false
	}

	sw.requests = append(sw.requests, now)
	return true
}

// --- 综合限流中间件 ---

// RateLimitConfig 限流配置
type RateLimitConfig struct {
	GlobalQPS    int           // 全局 QPS
	PerClientQPS int           // 单客户端 QPS
	Window       time.Duration // 滑动窗口大小
	BurstSize    int           // 突发容量
}

// DefaultRateLimitConfig 默认配置
var DefaultRateLimitConfig = RateLimitConfig{
	GlobalQPS:    10000,
	PerClientQPS: 100,
	Window:       time.Second,
	BurstSize:    200,
}

// RateLimitMiddleware 限流中间件
type RateLimitMiddleware struct {
	globalLimiter  *TokenBucket
	clientLimiter  *PerKeyLimiter
	windowLimiter  *SlidingWindowCounter
	config         RateLimitConfig
}

// NewRateLimitMiddleware 创建限流中间件
func NewRateLimitMiddleware(config RateLimitConfig) *RateLimitMiddleware {
	return &RateLimitMiddleware{
		globalLimiter:  NewTokenBucket(float64(config.BurstSize), float64(config.GlobalQPS)),
		clientLimiter:  NewPerKeyLimiter(float64(config.BurstSize), float64(config.PerClientQPS), 5*time.Minute),
		windowLimiter:  NewSlidingWindowCounter(config.Window, int64(config.PerClientQPS)),
		config:         config,
	}
}

// Handler 限流中间件入口
func (rl *RateLimitMiddleware) Handler(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 第1层: 全局限流
		if !rl.globalLimiter.Allow() {
			w.Header().Set("Retry-After", "1")
			http.Error(w, "529 Too Many Requests", http.StatusTooManyRequests)
			return
		}

		// 提取客户端标识（IP 或 API Key）
		clientKey := getClientKey(r)

		// 第2层: 客户端限流
		if !rl.clientLimiter.Allow(clientKey) {
			w.Header().Set("X-RateLimit-Limit", "100")
			w.Header().Set("X-RateLimit-Remaining", "0")
			http.Error(w, "429 Too Many Requests", http.StatusTooManyRequests)
			return
		}

		// 第3层: 滑动窗口精确限流
		if !rl.windowLimiter.Allow() {
			http.Error(w, "429 Too Many Requests", http.StatusTooManyRequests)
			return
		}

		next.ServeHTTP(w, r)
	})
}

func getClientKey(r *http.Request) string {
	// 优先使用 API Key (Header)
	if apiKey := r.Header.Get("X-API-Key"); apiKey != "" {
		return "key:" + apiKey
	}
	// 其次使用 X-Forwarded-For
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		return "ip:" + xff
	}
	return "ip:" + r.RemoteAddr
}
```

### 5.4 Slowloris 防护

Slowloris 通过保持大量半开连接耗尽服务器资源。

```go
package security

import (
	"net/http"
	"time"
)

// SlowlorisProtection 慢速连接防护
type SlowlorisProtection struct {
	readTimeout     time.Duration // 读取请求头的超时
	readHeaderTimeout time.Duration // 读取 header 的超时
	writeTimeout    time.Duration // 写入响应超时
	idleTimeout     time.Duration // 空闲连接超时
}

// NewSlowlorisProtection 创建慢速连接防护
func NewSlowlorisProtection() *SlowlorisProtection {
	return &SlowlorisProtection{
		readTimeout:       30 * time.Second,
		readHeaderTimeout: 10 * time.Second,
		writeTimeout:      60 * time.Second,
		idleTimeout:       120 * time.Second,
	}
}

// WrapServer 包装 HTTP Server，启用慢速连接防护
func (sp *SlowlorisProtection) WrapServer(handler http.Handler) *http.Server {
	return &http.Server{
		Handler:           handler,
		ReadTimeout:       sp.readTimeout,
		ReadHeaderTimeout: sp.readHeaderTimeout,
		WriteTimeout:      sp.writeTimeout,
		IdleTimeout:       sp.idleTimeout,
		MaxHeaderBytes:    1 << 16, // 64KB
		// TLS 配置（生产环境必须）
		// TLSConfig: &tls.Config{...},
	}
}
```

---

## 6. 自测题

### 题目 1：JWT 安全设计

**问题：** 以下 JWT 签发代码存在哪些安全问题？请逐一指出并给出修复方案。

```go
func insecureGenerateToken(userID string) (string, error) {
	claims := jwt.MapClaims{
		"user_id": userID,
		"admin":   true,
		"exp":     time.Now().Add(365 * 24 * time.Hour).Unix(),
	}
	token := jwt.NewWithClaims(jwt.SigningMethodHS256, claims)
	return token.SignedString([]byte("secret")) // 硬编码密钥
}
```

**答案要点：**

1. **TTL 过长**：365 天，一旦泄露无法及时收回。应改为 15 分钟 access_token + 7 天 refresh_token。
2. **密钥硬编码**：`[]byte("secret")` 强度极低且硬编码在代码中。应使用环境变量或 KMS 加载 ≥32 字节的随机密钥，生产环境用 RS256。
3. **缺少必要 claims**：没有 `iss`、`aud`、`iat`、`jti`，无法做签发者校验、受众校验和去重。
4. **`admin: true` 不安全**：将特权标志放在 JWT 中，客户端可伪造。权限应由服务端 RBAC 引擎判定，JWT 只传 userID 和角色 ID。
5. **HS256 对称签名**：多实例部署时需要共享密钥，增加泄露面。生产环境用 RS256/ES256 非对称签名。
6. **无 kid（Key ID）**：无法支持密钥轮换。

---

### 题目 2：RBAC 权限继承冲突

**问题：** 某广告平台 RBAC 系统中，用户 Alice 同时拥有两个角色：
- `CampaignManager`：权限 `{ad:create, ad:update, campaign:read}`
- `Auditor`：权限 `{campaign:read, billing:read}`

系统同时实现了 deny-overrides 和 allow-first 两种策略。请分析：

1. 如果新增角色 `BlockedAdvertiser`（权限为空，但显式 deny 所有操作），Alice 被赋予此角色后，她的 `ad:create` 权限是否还存在？
2. 在设计 RBAC 引擎时，如何处理角色继承环（A→B→C→A）？
3. 如何高效实现权限变更时的缓存刷新？

**答案要点：**

1. **Deny-overrides 策略下**，deny 优先级高于 allow。即使 `CampaignManager` 允许 `ad:create`，`BlockedAdvertiser` 的 deny 会覆盖它，Alice 不能创建广告。这是安全最佳实践——显式拒绝优于隐式允许。
2. **角色继承环检测**：在 `collectRolePerms` 中使用 `visited` 集合做 DFS 遍历。遇到已访问节点即判定为环，终止递归。生产环境应在角色创建/修改时做拓扑排序检测，而非运行时检测。
3. **缓存刷新策略**：
   - 用户角色变更 → 删除该用户的预计算权限缓存（`Invalidate(userID)`）
   - 角色权限变更 → 标记所有拥有该角色的用户缓存为 stale
   - 使用写扩散（write-through）：角色权限变更时主动刷新所有受影响用户的缓存
   - 考虑使用 Caffeine/Golang 的 `groupcache` 做多级缓存

---

### 题目 3：限流算法选型与实现

**问题：** 广告平台的 bidding API（出价接口）面临以下场景：

- 正常 QPS: 5,000
- 峰值 QPS: 20,000（持续 30 秒的促销时段）
- 单个广告主上限: 100 QPS
- 需要精确控制，不允许超发超过 5%

请选择限流算法并给出 Go 实现思路，说明为什么其他算法不适合。

**答案要点：**

**选型：Token Bucket（令牌桶）**

理由：
- **允许突发**：促销时段 20,000 QPS 的突发需要用令牌桶的 burst 能力吸收
- **匀速补充**： refill rate = 100/sec 保证单广告主不超过 100 QPS
- **精确控制**：通过调整 `maxTokens` 和 `refillRate` 可以精确控制上限和突发容量
- 超发率可控：每次 `Allow()` 只消耗 1 个 token，不会像 Fixed Window 那样在窗口切换时超发 2 倍

**为什么不选其他算法：**
- **Fixed Window**：窗口边界突刺（两个窗口各 100 QPS，边界处瞬间 200 QPS），超发率可达 100%，不满足 5% 要求
- **Sliding Window**：需要存储每个时间戳，内存占用高，分布式场景一致性难保证
- **Leaky Bucket**：不允许任何突发，促销场景会被误杀

**Go 实现关键点：**
```
每实例本地 TokenBucket:
  - maxTokens = 150 (100 QPS + 50% 缓冲)
  - refillRate = 100 tokens/sec
  - 分布式场景用 Redis + Lua 脚本实现全局限流
  - Redis Lua: 使用 ZSET 做滑动窗口，保证分布式一致性
```

---

## 附录：安全 Checklist

### 认证安全
- [ ] JWT 使用 RS256/ES256 非对称签名
- [ ] Access Token TTL ≤ 15 分钟
- [ ] Refresh Token 支持轮换 (Rotation)
- [ ] 密钥通过 KMS/Secrets Manager 管理
- [ ] OAuth2 state 参数防 CSRF

### 授权安全
- [ ] RBAC deny-overrides 策略
- [ ] 最小权限原则 (Least Privilege)
- [ ] 敏感操作二次确认
- [ ] 权限变更审计日志

### 传输安全
- [ ] 全站 HTTPS (TLS 1.2+)
- [ ] HSTS Header
- [ ] CSP (Content Security Policy)
- [ ] CORS 严格白名单

### 数据安全
- [ ] 密码 bcrypt/argon2 哈希
- [ ] PII 字段加密存储 (AES-256-GCM)
- [ ] 日志脱敏（不记录密码、Token、PII）
- [ ] 数据库字段级权限控制

### 基础设施安全
- [ ] WAF 规则定期更新
- [ ] DDoS 防护预案演练
- [ ] 限流 + 熔断 + 降级三级防护
- [ ] 安全扫描集成 CI/CD
