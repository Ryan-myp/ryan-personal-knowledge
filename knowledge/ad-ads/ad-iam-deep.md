# 广告系统身份认证与权限管理深度指南（Ad IAM Deep Dive）

> **来源**：微信读书蒸馏 + 行业最佳实践 + 生产代码重构
> **创建日期**：2026-07-09
> **深度等级**：🟢深（源码级）

---

## 一、入门引导：为什么广告系统需要独立的 IAM？

### 1.1 类比：广告系统的"海关"

想象一个国际机场：
- **旅客** = 广告主/代理商/媒体方
- **护照** = OAuth Client ID + Secret
- **登机牌** = Access Token（短期有效）
- **安检口** = Authorization Server（校验权限）
- **航站楼** = 不同的业务域（DSP/SSP/Ad Exchange）

广告系统不是普通的CRUD应用——它涉及三方主体（广告主、媒体、平台），每个主体有不同的数据访问边界和API调用权限。传统RBAC不够用，需要**多租户+细粒度+跨域信任**。

### 1.2 广告系统IAM的核心挑战

| 挑战 | 说明 | 传统方案不足 |
|------|------|-------------|
| **多租户隔离** | 广告主A不能看到广告主B的Campaign数据 | RBAC没有原生tenant概念 |
| **角色层级复杂** | 广告主→代理商→子账户→操作员，四级权限链 | 简单Role-User映射无法表达层级 |
| **API粒度细** | Campaign CRUD vs Read-only vs Budget修改，同一资源不同操作不同权限 | 粗粒度role无法覆盖 |
| **跨域信任** | DSP需要信任SSP的Token，Ad Exchange需要验证双方身份 | 单域OAuth无法解决联邦身份 |
| **审计合规** | GDPR/CCPA要求记录谁在何时访问了什么数据 | 普通日志不够结构化 |

### 1.3 技术选型决策

```
方案对比：
┌─────────────────┬──────────────┬──────────────┬──────────────┐
│     维度        │   OAuth 2.0  │   OIDC       │   SAML 2.0   │
├─────────────────┼──────────────┼──────────────┼──────────────┤
│ 主要用途        │ 授权         │ 身份认证     │ 企业SSO      │
│ Token格式       │ 任意         │ JWT          │ XML          │
│ 适合场景        │ API访问控制  │ 用户登录     │ 企业内网     │
│ 广告系统适用性  │ ⭐⭐⭐⭐⭐    │ ⭐⭐⭐⭐       │ ⭐⭐          │
└─────────────────┴──────────────┴──────────────┴──────────────┘

结论：广告系统以OAuth 2.0为核心，OIDC为补充（用户登录场景），SAML仅用于企业客户集成。
```

---

## 二、核心原理：OAuth 2.0 + JWT 在广告系统中的落地

### 2.1 OAuth 2.0 四种Grant Type的选择

```go
// grant_type.go — 广告系统OAuth Grant类型定义

package iam

// GrantType 定义了客户端获取Access Token的方式
type GrantType string

const (
	// AuthorizationCodeGrant: 服务端Web应用的标准流程
	// 广告主后台管理系统使用——需要浏览器重定向+PKCE
	AuthorizationCodeGrant GrantType = "authorization_code"

	// ClientCredentialsGrant: 机器对机器通信
	// DSP↔Ad Exchange API调用——不需要用户上下文，只有应用身份
	ClientCredentialsGrant GrantType = "client_credentials"

	// RefreshTokenGrant: 刷新长期有效的Token
	// Access Token有效期短（1h），Refresh Token有效期长（30d）
	RefreshTokenGrant GrantType = "refresh_token"

	// DeviceCodeGrant: IoT/无浏览器设备
	// 广告屏投放终端、OTT设备等无键盘输入场景
	DeviceCodeGrant GrantType = "device_code"
)

// 为什么广告系统不用Password Grant？
// 1. 不安全：客户端存储明文密码
// 2. 无法撤销：改了密码所有session都失效
// 3. 违反最小权限原则：直接拿到用户凭证
// 4. 合规风险：GDPR要求明确的用户同意
```

### 2.2 Access Token 生命周期设计

```go
// token_lifecycle.go — Token生命周期管理

package iam

import (
	"time"
	"crypto/rand"
	"encoding/hex"
)

// TokenConfig 定义了Token的完整生命周期策略
type TokenConfig struct {
	// Access Token 有效期 —— 短命是安全基石
	AccessTokenTTL time.Duration // 推荐: 1小时

	// Refresh Token 有效期 —— 兼顾安全和体验
	RefreshTokenTTL time.Duration // 推荐: 30天

	// Rotation策略：每次refresh生成新的Refresh Token
	// 旧Token立即失效，防止token窃取后的长期滥用
	EnableRotation bool // 推荐: true

	// Sliding window：每次使用Refresh Token就续期
	// 活跃用户不会过期，不活跃30天后自动过期
	SlidingWindow bool // 推荐: true

	// MaxRefreshCount：一个Refresh Token最多刷新N次
	// 防止无限续期的安全隐患
	MaxRefreshCount int // 推荐: 30
}

// DefaultTokenConfig 返回广告系统的默认Token配置
func DefaultTokenConfig() *TokenConfig {
	return &TokenConfig{
		AccessTokenTTL:  time.Hour,
		RefreshTokenTTL: 30 * 24 * time.Hour,
		EnableRotation:  true,
		SlidingWindow:   true,
		MaxRefreshCount: 30,
	}
}

// GenerateTokenID 生成唯一的Token ID（用于存储和追踪）
func GenerateTokenID() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return hex.EncodeToString(b), nil
}

// AccessToken 表示短期有效的访问令牌
type AccessToken struct {
	ID        string    `json:"id"`
	ClientID  string    `json:"client_id"`
	UserID    string    `json:"user_id,omitempty"` // 用户token才有
	TenantID  string    `json:"tenant_id"`         // 多租户隔离key
	Scope     []string  `json:"scope"`             // 权限范围
	ExpiresAt time.Time `json:"expires_at"`
	CreatedAt time.Time `json:"created_at"`
	JTI       string    `json:"jti"`               // JWT ID，用于撤销
}

// RefreshToken 表示长期有效的刷新令牌
type RefreshToken struct {
	ID            string    `json:"id"`
	ParentID      string    `json:"parent_id"`       // 关联的AccessToken ID
	ClientID      string    `json:"client_id"`
	UserID        string    `json:"user_id,omitempty"`
	TenantID      string    `json:"tenant_id"`
	Nonce         string    `json:"nonce,omitempty"` // PKCE验证
	RefreshCount  int       `json:"refresh_count"`
	MaxRefresh    int       `json:"max_refresh"`
	ExpiresAt     time.Time `json:"expires_at"`
	CreatedAt     time.Time `json:"created_at"`
	Revoked       bool      `json:"revoked"`
}
```

### 2.3 JWT Token结构解析

```go
// jwt_struct.go — JWT在广告系统中的结构

package iam

// JWT Payload结构（简化版）
// {
//   "sub": "user_123",           // 用户ID
//   "iss": "https://auth.adplatform.com",  // 签发者
//   "aud": "dsp-api",            // 接收者（Audience）
//   "exp": 1720000000,           // 过期时间
//   "iat": 1719996400,           // 签发时间
//   "jti": "abc123...",          // 唯一ID
//   "tenant_id": "tenant_456",   // 租户ID
//   "scopes": ["campaign:read","campaign:write"],  // 权限范围
//   "roles": ["advertiser","manager"]           // 角色列表
// }

// Scope 定义了JWT中的权限粒度
// 广告系统的Scope设计遵循"资源:操作"模式
type Scope string

const (
	// Campaign相关
	CampaignRead    Scope = "campaign:read"
	CampaignWrite   Scope = "campaign:write"
	CampaignDelete  Scope = "campaign:delete"
	CampaignBudget  Scope = "campaign:budget"  // 特殊：只能修改预算

	// Ad Group相关
	AdGroupRead     Scope = "adgroup:read"
	AdGroupWrite    Scope = "adgroup:write"

	// Creative相关
	CreativeUpload  Scope = "creative:upload"
	CreativeApprove Scope = "creative:approve"  // 审核权限

	// Reporting相关
	ReportRead      Scope = "report:read"
	ReportExport    Scope = "report:export"

	// Account相关
	AccountManage   Scope = "account:manage"
	BillingRead     Scope = "billing:read"
	BillingWrite    Scope = "billing:write"

	// Admin相关
	AdminAll        Scope = "admin:*"
)

// Audience 定义了Token的目标服务
// 同一个Token不能在DSP和SSP之间通用
type Audience string

const (
	AudienceDSP     Audience = "dsp-api"
	AudienceSSP     Audience = "ssp-api"
	AudienceExchange Audience = "exchange-api"
	AudienceAdmin   Audience = "admin-dashboard"
)
```

### 2.4 为什么JWT要配合后端存储？

```
常见误区：JWT是无状态的，所以不需要数据库。

真相：JWT本身确实无状态（签名验证不依赖服务器），但
广告系统需要以下有状态能力：

1. Token撤销 —— 用户登出/改密码时需要让已签发JWT失效
2. Scope动态变更 —— 管理员修改了用户权限，需要立即生效
3. 审计追踪 —— 谁在什么时候用了哪个Token
4. 并发控制 —— 同一用户最多N个活跃Session
5. 租户隔离验证 —— 防止Token被篡改跨租户访问

解决方案：JWT + Redis存储（双写模式）
┌──────────┐     验证签名      ┌──────────┐
│  Client  │ ────────────────→ │  Server  │
│          │                   │          │
│ 发JWT    │ ←───────────────  │ 验签名   │
│          │   快速通过         │          │
│          │                   │          │
│          │ ── 额外检查 ────→ │ 查Redis  │
│          │                   │ 撤销列表 │
└──────────┘                   └──────────┘
```

---

## 三、生产级Go实现

### 3.1 JWT签发器

```go
// jwt_signer.go — 生产级JWT签发器

package iam

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"fmt"
	"time"

	"github.com/golang-jwt/jwt/v5"
)

// JWTSigner 负责签发和验证JWT
type JWTSigner struct {
	signingKey   *ecdsa.PrivateKey
	verifyingKey *ecdsa.PublicKey
	issuer       string
	algorithm    jwt.SigningMethod
	clockSkew    time.Duration // 允许的时间偏差
}

// NewJWTSigner 创建JWT签发器（使用ECDSA P-256，比RSA更快且密钥更短）
func NewJWTSigner() (*JWTSigner, error) {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, fmt.Errorf("generate ECDSA key: %w", err)
	}
	return &JWTSigner{
		signingKey:   key,
		verifyingKey: &key.PublicKey,
		issuer:       "https://auth.adplatform.com",
		algorithm:    jwt.SigningMethodES256,
		clockSkew:    30 * time.Second,
	}, nil
}

// Sign 签发JWT
// claims: 自定义声明（包含tenant_id, scopes, roles等）
// expiresIn: Token有效期
func (s *JWTSigner) Sign(claims CustomClaims, expiresIn time.Duration) (string, error) {
	now := time.Now()
	claims.IssuedAt = jwt.NewNumericDate(now)
	claims.ExpiresAt = jwt.NewNumericDate(now.Add(expiresIn))
	claims.Issuer = s.issuer
	claims.JWTID = generateJTI()

	token := jwt.NewWithClaims(s.algorithm, claims)
	return token.SignedString(s.signingKey)
}

// Verify 验证JWT
// 返回：是否有效 + 解析出的claims
func (s *JWTSigner) Verify(tokenStr string) (*CustomClaims, error) {
	token, err := jwt.ParseWithClaims(tokenStr, &CustomClaims{}, func(t *jwt.Token) (interface{}, error) {
		// 验证签名算法
		if t.Method != s.algorithm {
			return nil, fmt.Errorf("unexpected signing method: %v", t.Header["alg"])
		}
		return s.verifyingKey, nil
	}, jwt.WithLeeway(s.clockSkew)) // 允许clock skew

	if err != nil {
		return nil, fmt.Errorf("parse token: %w", err)
	}

	claims, ok := token.Claims.(*CustomClaims)
	if !ok || !token.Valid {
		return nil, fmt.Errorf("invalid token claims")
	}

	return claims, nil
}

// CustomClaims 广告系统JWT的自定义声明
type CustomClaims struct {
	jwt.RegisteredClaims
	TenantID  string   `json:"tenant_id"`
	UserID    string   `json:"user_id,omitempty"`
	Scopes    []string `json:"scopes"`
	Roles     []string `json:"roles"`
	PerTenant map[string]map[string][]string `json:"per_tenant_scopes,omitempty"`
	// PerTenant 用于跨租户授权场景：
	// {
	//   "agency_123": {
	//     "campaign": ["read", "write"],
	//     "adgroup": ["read"]
	//   }
	// }
}

func generateJTI() string {
	b := make([]byte, 16)
	rand.Read(b)
	return fmt.Sprintf("%x", b)
}
```

### 3.2 OAuth Authorization Server

```go
// auth_server.go — OAuth授权服务器核心实现

package iam

import (
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
)

// AuthServer 实现了完整的OAuth 2.0授权服务器
type AuthServer struct {
	signer       *JWTSigner
	redis        *redis.Client
	config       *TokenConfig
	codeStore    sync.Map // code -> AuthorizationCode
	clientStore  sync.Map // clientID -> RegisteredClient
}

// RegisteredClient 注册客户端信息
type RegisteredClient struct {
	ID             string   `json:"id"`
	Secret         string   `json:"secret"` // 哈希存储
	RedirectURIs   []string `json:"redirect_uris"`
	GrantTypes     []string `json:"grant_types"`
	Scope          []string `json:"default_scope"`
	ClientType     string   // "public" | "confidential"
	TenantID       string   `json:"tenant_id"`
	IsActive       bool     `json:"is_active"`
	CreatedAt      time.Time
}

// AuthorizationCode 授权码
type AuthorizationCode struct {
	Code       string
	ClientID   string
	UserID     string
	TenantID   string
	RedirectURI string
	Scopes     []string
	Nonce      string // for OIDC
	CodeChallenge string // for PKCE
	ExpiresAt  time.Time
	Used       bool
}

// NewAuthServer 创建授权服务器
func NewAuthServer(signer *JWTSigner, redisClient *redis.Client) *AuthServer {
	return &AuthServer{
		signer: signer,
		redis:  redisClient,
		config: DefaultTokenConfig(),
	}
}

// ExchangeAuthorizationCode 用授权码换取Token（核心流程）
func (s *AuthServer) ExchangeAuthorizationCode(
	code, clientID, clientSecret, redirectURI string,
	codeVerifier string,
) (*TokenResponse, error) {
	// Step 1: 验证授权码
	authCode, err := s.retrieveAndRevokeCode(code)
	if err != nil {
		return nil, fmt.Errorf("invalid authorization code: %w", err)
	}

	// Step 2: 验证客户端
	client, err := s.validateClient(clientID, clientSecret, authCode.ClientID)
	if err != nil {
		return nil, fmt.Errorf("client validation failed: %w", err)
	}

	// Step 3: 验证redirect URI
	if !s.matchRedirectURI(authCode.RedirectURI, redirectURI) {
		return nil, fmt.Errorf("redirect URI mismatch")
	}

	// Step 4: PKCE验证（public client必须）
	if client.ClientType == "public" {
		if err := s.verifyPKCE(authCode.CodeChallenge, codeVerifier); err != nil {
			return nil, fmt.Errorf("PKCE verification failed: %w", err)
		}
	}

	// Step 5: 生成Token
	return s.generateTokens(authCode.UserID, authCode.TenantID, authCode.Scopes, client.ID)
}

// retrieveAndRevokeCode 获取并标记授权码为已使用（一次性）
func (s *AuthServer) retrieveAndRevokeCode(code string) (*AuthorizationCode, error) {
	ctx := context.Background()

	// 从Redis获取授权码
	data, err := s.redis.Get(ctx, "oauth:code:"+code).Bytes()
	if err != nil {
		return nil, fmt.Errorf("code not found or expired")
	}

	var codeObj AuthorizationCode
	if err := json.Unmarshal(data, &codeObj); err != nil {
		return nil, fmt.Errorf("invalid code format")
	}

	if codeObj.ExpiresAt.Before(time.Now()) {
		s.redis.Del(ctx, "oauth:code:"+code)
		return nil, fmt.Errorf("authorization code expired")
	}

	if codeObj.Used {
		return nil, fmt.Errorf("authorization code already used")
	}

	// 原子性地标记为已使用
	used, err := s.redis.SetNX(ctx, "oauth:code:"+code+":used", "1", 0).Result()
	if err != nil || !used {
		return nil, fmt.Errorf("code race condition")
	}

	return &codeObj, nil
}

// verifyPKCE PKCE（Proof Key for Code Exchange）验证
// 防止授权码拦截攻击
func (s *AuthServer) verifyPKCE(challenge, verifier string) error {
	// SHA256(verifier) 应该等于 challenge
	hash := sha256.Sum256([]byte(verifier))
	computedChallenge := base64.RawURLEncoding.EncodeToString(hash[:])

	if challenge != computedChallenge {
		return fmt.Errorf("PKCE code_verifier does not match code_challenge")
	}
	return nil
}

// generateTokens 生成Access Token + Refresh Token
func (s *AuthServer) generateTokens(userID, tenantID string, scopes []string, clientID string) (*TokenResponse, error) {
	accessToken, err := s.signer.Sign(CustomClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:  s.signer.issuer,
			Subject: userID,
			Audience: jwt.ClaimStrings{clientID},
		},
		TenantID: tenantID,
		UserID:   userID,
		Scopes:   scopes,
	}, s.config.AccessTokenTTL)
	if err != nil {
		return nil, fmt.Errorf("sign access token: %w", err)
	}

	// 生成Refresh Token（存储在Redis）
	refreshTokenID, err := GenerateTokenID()
	if err != nil {
		return nil, fmt.Errorf("generate refresh token id: %w", err)
	}

	refreshToken := &RefreshToken{
		ID:           refreshTokenID,
		ClientID:     clientID,
		UserID:       userID,
		TenantID:     tenantID,
		MaxRefresh:   s.config.MaxRefreshCount,
		ExpiresAt:    time.Now().Add(s.config.RefreshTokenTTL),
		CreatedAt:    time.Now(),
	}

	ctx := context.Background()
	rtData, _ := json.Marshal(refreshToken)
	s.redis.Set(ctx, "oauth:rt:"+refreshTokenID, rtData, s.config.RefreshTokenTTL)

	// 存储AccessToken到Redis（用于撤销）
	jti := generateJTI()
	accessTokenData, _ := json.Marshal(map[string]interface{}{
		"jti":        jti,
		"user_id":    userID,
		"tenant_id":  tenantID,
		"client_id":  clientID,
		"scopes":     scopes,
		"expires_at": time.Now().Add(s.config.AccessTokenTTL).Unix(),
	})
	s.redis.Set(ctx, "oauth:at:"+jti, accessTokenData, s.config.AccessTokenTTL)

	return &TokenResponse{
		AccessToken:  accessToken,
		TokenType:    "Bearer",
		ExpiresIn:    int(s.config.AccessTokenTTL.Seconds()),
		RefreshToken: refreshTokenID,
		Scope:        strings.Join(scopes, " "),
	}, nil
}

// TokenResponse OAuth2标准响应
type TokenResponse struct {
	AccessToken  string `json:"access_token"`
	TokenType    string `json:"token_type"`
	ExpiresIn    int    `json:"expires_in"`
	RefreshToken string `json:"refresh_token,omitempty"`
	Scope        string `json:"scope,omitempty"`
	IDToken      string `json:"id_token,omitempty"` // OIDC
}
```

### 3.3 细粒度权限中间件

```go
// permission_middleware.go — 基于Scope和RBAC的权限中间件

package iam

import (
	"context"
	"net/http"
	"strings"
)

// PermissionChecker 定义权限检查接口
type PermissionChecker interface {
	// CheckScope 检查当前请求是否有指定scope
	CheckScope(ctx context.Context, requiredScopes []string) error
	// CheckRole 检查当前用户是否有指定role
	CheckRole(ctx context.Context, requiredRoles []string) error
	// CheckResourceAccess 检查对特定资源的访问权限
	CheckResourceAccess(ctx context.Context, resourceType, resourceID, action string) error
	// GetTenantID 获取当前请求的租户ID
	GetTenantID(ctx context.Context) string
}

// JWTPermissionChecker 从JWT中提取权限信息进行校验
type JWTPermissionChecker struct {
	signer *JWTSigner
	redis  *redis.Client
}

// ExtractClaimsFromRequest 从HTTP请求的Authorization Header提取JWT Claims
func (c *JWTPermissionChecker) ExtractClaimsFromRequest(r *http.Request) (*CustomClaims, error) {
	authHeader := r.Header.Get("Authorization")
	if authHeader == "" {
		return nil, fmt.Errorf("missing authorization header")
	}

	parts := strings.Split(authHeader, " ")
	if len(parts) != 2 || parts[0] != "Bearer" {
		return nil, fmt.Errorf("invalid authorization header format")
	}

	claims, err := c.signer.Verify(parts[1])
	if err != nil {
		return nil, fmt.Errorf("token verification failed: %w", err)
	}

	// 额外检查：是否在撤销列表中
	ctx := context.Background()
	jti := claims.JWTID
	revoked, _ := c.redis.Exists(ctx, "oauth:revoked:"+jti).Result()
	if revoked > 0 {
		return nil, fmt.Errorf("token has been revoked")
	}

	return claims, nil
}

// CheckScope 检查Scope权限
// 实现方式：集合包含检查
func (c *JWTPermissionChecker) CheckScope(ctx context.Context, requiredScopes []string) error {
	claims := ctx.Value("claims").(*CustomClaims)

	// 快速路径：admin:* 通配符
	for _, scope := range claims.Scopes {
		if scope == "admin:*" {
			return nil
		}
	}

	// 精确匹配：required中的每个scope都必须在claims.Scopes中
	requiredSet := make(map[string]struct{}, len(requiredScopes))
	for _, rs := range requiredScopes {
		requiredSet[rs] = struct{}{}
	}

	for _, cs := range claims.Scopes {
		delete(requiredSet, cs)
	}

	if len(requiredSet) > 0 {
		return &PermissionError{
			Missing:     requiredSet,
			Has:         toSet(claims.Scopes),
			Resource:    ctx.Value("resource_type"),
			Action:      ctx.Value("action"),
		}
	}
	return nil
}

// CheckResourceAccess 资源级权限检查
// 实现：RBAC + ABAC混合模型
func (c *JWTPermissionChecker) CheckResourceAccess(
	ctx context.Context,
	resourceType, resourceID, action string,
) error {
	claims := ctx.Value("claims").(*CustomClaims)

	// Step 1: 检查租户隔离（强制）
	userTenant := claims.TenantID
	resourceTenant := ctx.Value("resource_tenant").(string)
	if userTenant != resourceTenant {
		return &PermissionError{
			Reason: "tenant isolation violation",
			UserTenant: userTenant,
			ResourceTenant: resourceTenant,
		}
	}

	// Step 2: 检查RBAC角色权限
	userRoles := claims.Roles
	resourceRoles := getResourceRoles(resourceID) // 从DB查询资源关联的角色

	// 检查用户角色是否是资源角色的父级
	if !isRoleHierarchySatisfied(userRoles, resourceRoles) {
		return &PermissionError{
			Reason: "insufficient role hierarchy",
			UserRoles: userRoles,
			ResourceRoles: resourceRoles,
		}
	}

	// Step 3: 检查ABAC属性条件
	return evaluateABACPolicy(ctx, resourceType, resourceID, action, claims)
}

// PermissionError 权限错误详情
type PermissionError struct {
	Reason         string
	Missing        map[string]struct{}
	Has            map[string]struct{}
	UserTenant     string
	ResourceTenant string
	UserRoles      []string
	ResourceRoles  []string
}

func (e *PermissionError) Error() string {
	if e.Reason != "" {
		return fmt.Sprintf("permission denied: %s", e.Reason)
	}
	return fmt.Sprintf("permission denied: missing scopes %v (has: %v)",
		setToList(e.Missing), setToList(e.Has))
}

// Middleware HTTP中间件实现
func (c *JWTPermissionChecker) Middleware(next http.Handler, requiredScopes []string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		claims, err := c.ExtractClaimsFromRequest(r)
		if err != nil {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}

		ctx := context.WithValue(r.Context(), "claims", claims)
		r = r.WithContext(ctx)

		// 检查scope
		if len(requiredScopes) > 0 {
			if err := c.CheckScope(ctx, requiredScopes); err != nil {
				http.Error(w, err.Error(), http.StatusForbidden)
				return
			}
		}

		next.ServeHTTP(w, r)
	})
}
```

### 3.4 广告系统特有的权限模型：三级权限链

```go
// ad_permission_model.go — 广告系统三级权限链

package iam

// 广告系统的权限链比传统系统复杂得多：
//
// 层级结构：
// 集团账户（Group Account）
//   ├── 代理商账户（Agency Account）
//   │     ├── 子账户1（Sub-Account A）
//   │     │     ├── Campaign A1
//   │     │     ├── Campaign A2
//   │     │     └── ...
//   │     └── 子账户2（Sub-Account B）
//   │           ├── Campaign B1
//   │           └── ...
//   └── 直客账户（Direct Account）
//         ├── Campaign D1
//         └── ...
//
// 权限继承规则：
// 1. 代理商可以管理其名下所有子账户
// 2. 子账户操作员不能看到兄弟账户的数据
// 3. 集团管理员可以看到所有数据但不能直接操作
// 4. 预算修改权限独立于Campaign管理权限

// PermissionChain 定义了权限继承链
type PermissionChain struct {
	AccountID   string    // 当前账户ID
	AccountType AccountType // DIRECT / AGENCY / SUB_ACCOUNT
	ParentID    string    // 父账户ID
	ChildrenIDs []string  // 子账户ID列表
	Scopes      []Scope   // 直接授予的scope
	Inherited   bool      // 是否通过继承获得
}

// AccountType 账户类型枚举
type AccountType string

const (
	AccountDirect   AccountType = "DIRECT"    // 直客
	AccountAgency   AccountType = "AGENCY"    // 代理商
	AccountSub      AccountType = "SUB_ACCOUNT" // 子账户
)

// BuildPermissionChain 构建完整的权限链
func (s *AuthServer) BuildPermissionChain(accountID string) (*PermissionChain, error) {
	// 从数据库查询账户信息
	account, err := s.getAccount(accountID)
	if err != nil {
		return nil, err
	}

	chain := &PermissionChain{
		AccountID:   account.ID,
		AccountType: account.Type,
		ParentID:    account.ParentID,
		Scopes:      append([]Scope{}, account.DirectScopes...),
	}

	// 如果是子账户，继承代理商的权限（只读+有限写入）
	if account.Type == AccountSub && account.ParentID != "" {
		parentChain, err := s.BuildPermissionChain(account.ParentID)
		if err != nil {
			return nil, err
		}

		// 继承规则：子账户继承父账户的READ权限
		// 但不继承DELETE和BUDGET修改权限
		for _, scope := range parentChain.Scopes {
			if isReadableScope(scope) {
				chain.Scopes = append(chain.Scopes, scope)
			}
		}
		chain.Inherited = true
	}

	// 查询所有子账户ID（用于权限范围判定）
	chain.ChildrenIDs = s.getChildAccounts(accountID)

	return chain, nil
}

// isReadableScope 判断scope是否属于只读操作
func isReadableScope(s Scope) bool {
	scopeStr := string(s)
	return strings.HasSuffix(scopeStr, ":read") ||
		strings.HasPrefix(scopeStr, "report:") ||
		scopeStr == "campaign:read" ||
		scopeStr == "adgroup:read"
}

// CanManageAccount 判断账户是否有权限管理另一个账户
func (pc *PermissionChain) CanManageAccount(targetAccountID string) bool {
	// 直客管理员可以管理自己名下的所有子账户
	if pc.AccountType == AccountDirect {
		for _, childID := range pc.ChildrenIDs {
			if childID == targetAccountID {
				return true
			}
		}
		return false
	}

	// 代理商可以管理其名下所有子账户
	if pc.AccountType == AccountAgency {
		for _, childID := range pc.ChildrenIDs {
			if childID == targetAccountID {
				return true
			}
		}
		return false
	}

	// 子账户只能管理自己的数据
	return pc.AccountID == targetAccountID
}

// EffectiveScopes 计算该账户的有效权限集合
func (pc *PermissionChain) EffectiveScopes() []Scope {
	seen := make(map[Scope]bool)
	var result []Scope

	for _, s := range pc.Scopes {
		if !seen[s] {
			seen[s] = true
			result = append(result, s)
		}
	}
	return result
}
```

### 3.5 广告API网关中的权限校验

```go
// api_gateway.go — 广告API网关集成

package iam

import (
	"net/http"
	"strings"
)

// APIMiddleware 统一的API权限中间件
// 所有广告API请求都必须经过此中间件
type APIMiddleware struct {
	Checker *JWTPermissionChecker
}

// RoutePermission 定义了每个API路由的权限要求
type RoutePermission struct {
	Method      string   // GET, POST, PUT, DELETE
	PathPattern string   // /api/v1/campaigns/{id}
	RequiredScopes []string  // ["campaign:read"] 或 ["campaign:write"]
	RequiredRoles []string   // ["advertiser"] 或 ["admin"]
}

// 广告系统API路由权限矩阵
var APIRoutePermissions = []RoutePermission{
	// Campaign CRUD
	{http.MethodGet, "/api/v1/campaigns", []string{"campaign:read"}, []string{"advertiser", "agency"}},
	{http.MethodPost, "/api/v1/campaigns", []string{"campaign:write"}, []string{"advertiser", "agency"}},
	{http.MethodPut, "/api/v1/campaigns/{id}", []string{"campaign:write"}, []string{"advertiser", "agency"}},
	{http.MethodDelete, "/api/v1/campaigns/{id}", []string{"campaign:delete"}, []string{"advertiser"}},

	// Budget management（独立权限，防止误操作）
	{http.MethodPatch, "/api/v1/campaigns/{id}/budget", []string{"campaign:budget"}, []string{"advertiser", "agency"}},

	// Creative
	{http.MethodPost, "/api/v1/creatives", []string{"creative:upload"}, []string{"advertiser", "agency"}},
	{http.MethodPut, "/api/v1/creatives/{id}/status", []string{"creative:approve"}, []string{"approver"}},

	// Reporting
	{http.MethodGet, "/api/v1/reports", []string{"report:read"}, []string{"advertiser", "agency", "analyst"}},
	{http.MethodGet, "/api/v1/reports/export", []string{"report:export"}, []string{"advertiser", "agency"}},

	// Billing（敏感操作，需要额外MFA）
	{http.MethodGet, "/api/v1/billing/invoices", []string{"billing:read"}, []string{"admin", "finance"}},
	{http.MethodPost, "/api/v1/billing/topup", []string{"billing:write"}, []string{"admin"}},

	// Admin
	{http.MethodGet, "/api/v1/admin/audit-log", []string{"admin:*"}, []string{"super_admin"}},
}

// AuthMiddleware 权限校验中间件
func (m *APIMiddleware) AuthMiddleware(handler http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// 1. 提取并验证JWT
		claims, err := m.Checker.ExtractClaimsFromRequest(r)
		if err != nil {
			m.respondError(w, http.StatusUnauthorized, "invalid_token", err.Error())
			return
		}

		// 2. 匹配路由权限
		routePerm := m.matchRoute(r.Method, r.URL.Path)
		if routePerm == nil {
			m.respondError(w, http.StatusNotFound, "not_found", "api route not found")
			return
		}

		// 3. 检查Scope
		if err := m.Checker.CheckScope(r.Context(), routePerm.RequiredScopes); err != nil {
			m.respondError(w, http.StatusForbidden, "insufficient_scope", err.Error())
			return
		}

		// 4. 检查Role
		if err := m.Checker.CheckRole(r.Context(), routePerm.RequiredRoles); err != nil {
			m.respondError(w, http.StatusForbidden, "insufficient_role", err.Error())
			return
		}

		// 5. 资源级权限检查（租户隔离）
		resourceType, resourceID := m.extractResource(r)
		action := strings.ToLower(r.Method)
		if err := m.Checker.CheckResourceAccess(r.Context(), resourceType, resourceID, action); err != nil {
			m.respondError(w, http.StatusForbidden, "resource_access_denied", err.Error())
			return
		}

		// 6. 将权限信息注入context供下游使用
		ctx := context.WithValue(r.Context(), "user_claims", claims)
		ctx = context.WithValue(ctx, "required_scopes", routePerm.RequiredScopes)
		r = r.WithContext(ctx)

		handler.ServeHTTP(w, r)
	})
}

// matchRoute 匹配API路由权限
func (m *APIMiddleware) matchRoute(method, path string) *RoutePermission {
	for _, perm := range APIRoutePermissions {
		if perm.Method != method {
			continue
		}
		if matchPathPattern(perm.PathPattern, path) {
			return &perm
		}
	}
	return nil
}

// matchPathPattern 简单的路径模式匹配
// 支持 {param} 占位符
func matchPathPattern(pattern, path string) bool {
	patternParts := strings.Split(strings.Trim(pattern, "/"), "/")
	pathParts := strings.Split(strings.Trim(path, "/"), "/")

	if len(patternParts) != len(pathParts) {
		return false
	}

	for i, pp := range patternParts {
		if strings.HasPrefix(pp, "{") && strings.HasSuffix(pp, "}") {
			continue // 占位符匹配任意值
		}
		if pp != pathParts[i] {
			return false
		}
	}
	return true
}

func (m *APIMiddleware) respondError(w http.ResponseWriter, status int, code, message string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{
		"error":     code,
		"message":   message,
		"http_code": fmt.Sprintf("%d", status),
	})
}
```

---

## 四、实战案例：广告主自助开户流程中的IAM

### 4.1 场景描述

广告主通过自助门户注册 → 填写企业信息 → 提交审核 → 审核通过后自动创建账户 → 分配初始权限 → 首次登录设置密码。

### 4.2 完整实现

```go
// self_service_onboarding.go — 广告主自助开户IAM流程

package iam

import (
	"fmt"
	"time"
)

// OnboardingFlow 自助开户流程
type OnboardingFlow struct {
	authServer *AuthServer
	redis      *redis.Client
}

// RegistrationRequest 注册请求
type RegistrationRequest struct {
	CompanyName   string    `json:"company_name"`
	ContactName   string    `json:"contact_name"`
	Email         string    `json:"email"`
	Phone         string    `json:"phone"`
	Industry      string    `json:"industry"`
	BudgetRange   string    `json:"budget_range"` // "small" | "medium" | "large"
	ReferralCode  string    `json:"referral_code,omitempty"`
}

// OnboardResult 开户结果
type OnboardResult struct {
	AccountID       string    `json:"account_id"`
	InitialUsername string    `json:"initial_username"`
	VerificationURL string    `json:"verification_url"` // 邮箱验证链接
	Status          string    `json:"status"`           // "pending_review" | "approved" | "rejected"
}

// RegisterAdvertiser 执行自助注册流程
func (f *OnboardingFlow) RegisterAdvertiser(req RegistrationRequest) (*OnboardResult, error) {
	// Step 1: 验证邮箱唯一性
	if exists, _ := f.redis.Exists(context.Background(), "user:email:"+req.Email).Result(); exists > 0 {
		return nil, fmt.Errorf("email already registered")
	}

	// Step 2: 创建待审核账户（临时状态）
	accountID := generateAccountID()
	tempPassword := generateTempPassword() // 随机12位密码

	// Step 3: 存储待审核账户信息
	pendingAccount := PendingAccount{
		AccountID:     accountID,
		CompanyName:   req.CompanyName,
		ContactName:   req.ContactName,
		Email:         req.Email,
		Phone:         req.Phone,
		Industry:      req.Industry,
		BudgetRange:   req.BudgetRange,
		TempPassword:  hashPassword(tempPassword),
		Status:        "pending_review",
		CreatedAt:     time.Now(),
		ExpiresAt:     time.Now().Add(7 * 24 * time.Hour), // 7天后过期
	}

	accountData, _ := json.Marshal(pendingAccount)
	f.redis.Set(context.Background(), "pending:"+accountID, accountData, 7*24*time.Hour)

	// Step 4: 发送验证邮件（含verification token）
	verificationToken := generateVerificationToken(accountID)
	verifyURL := fmt.Sprintf("https://auth.adplatform.com/verify?token=%s", verificationToken)

	// Step 5: 存储verification token
	f.redis.Set(context.Background(), "verify:"+verificationToken, accountID, 24*time.Hour)

	return &OnboardResult{
		AccountID:       accountID,
		InitialUsername: req.Email,
		VerificationURL: verifyURL,
		Status:          "pending_review",
	}, nil
}

// VerifyAndActivate 验证邮箱并激活账户
func (f *OnboardingFlow) VerifyAndActivate(verificationToken, password string) (*OnboardResult, error) {
	ctx := context.Background()

	// Step 1: 验证token
	accountID, err := f.redis.Get(ctx, "verify:"+verificationToken).Result()
	if err != nil {
		return nil, fmt.Errorf("invalid verification token")
	}

	// Step 2: 获取待审核账户
	data, err := f.redis.Get(ctx, "pending:"+accountID).Bytes()
	if err != nil {
		return nil, fmt.Errorf("pending account not found")
	}

	var pending PendingAccount
	json.Unmarshal(data, &pending)

	// Step 3: 设置正式密码
	pending.TempPassword = ""
	pending.PasswordHash = hashPassword(password)
	pending.Status = "active"

	// Step 4: 更新账户状态
	pendingData, _ := json.Marshal(pending)
	f.redis.Set(ctx, "pending:"+accountID, pendingData, 0) // 永不过期

	// Step 5: 分配默认权限
	defaultScopes := f.getDefaultScopesForBudgetRange(pending.BudgetRange)
	f.assignDefaultPermissions(accountID, defaultScopes)

	// Step 6: 清理verification token
	f.redis.Del(ctx, "verify:"+verificationToken)

	return &OnboardResult{
		AccountID: accountID,
		Status:    "active",
	}, nil
}

// getDefaultScopesForBudgetRange 根据预算范围分配默认权限
func (f *OnboardingFlow) getDefaultScopesForBudgetRange(budgetRange string) []Scope {
	switch budgetRange {
	case "small":
		// 小预算：基础读写，无删除权限
		return []Scope{
			CampaignRead, CampaignWrite,
			AdGroupRead, AdGroupWrite,
			CreativeUpload,
			ReportRead,
		}
	case "medium":
		// 中预算：完整读写+预算调整
		return []Scope{
			CampaignRead, CampaignWrite, CampaignDelete,
			AdGroupRead, AdGroupWrite,
			CreativeUpload, CreativeApprove,
			CampaignBudget,
			ReportRead, ReportExport,
		}
	default: // large
		// 大预算：完全权限
		return []Scope{
			CampaignRead, CampaignWrite, CampaignDelete,
			AdGroupRead, AdGroupWrite,
			CreativeUpload, CreativeApprove,
			CampaignBudget,
			ReportRead, ReportExport,
			BillingRead, BillingWrite,
		}
	}
}
```

### 4.3 跨域Token交换（DSP↔Ad Exchange）

```go
// cross_domain_token.go — 跨域Token交换

package iam

// CrossDomainExchange 跨域Token交换
// DSP需要向Ad Exchange证明自己的身份才能发起bid request
func (s *AuthServer) CrossDomainExchange(
	dspClientID, dspSecret, exchangeAudience string,
) (*TokenResponse, error) {
	// 1. 验证DSP客户端凭据
	dspClient, err := s.getClient(dspClientID)
	if err != nil {
		return nil, fmt.Errorf("invalid DSP credentials")
	}

	// 2. 验证DSP有权访问目标Exchange
	if !s.isAuthorizedExchange(dspClientID, exchangeAudience) {
		return nil, fmt.Errorf("DSP not authorized for this exchange")
	}

	// 3. 签发面向Exchange的Token
	claims := CustomClaims{
		RegisteredClaims: jwt.RegisteredClaims{
			Issuer:  s.signer.issuer,
			Audience: jwt.ClaimStrings{exchangeAudience},
		},
		TenantID: dspClient.TenantID,
		ClientID: dspClientID,
		Scopes:   []string{"bid:submit", "report:read"},
		Roles:    []string{"dsp_client"},
	}

	token, err := s.signer.Sign(claims, 15*time.Minute) // 跨域Token有效期更短
	if err != nil {
		return nil, fmt.Errorf("sign cross-domain token: %w", err)
	}

	return &TokenResponse{
		AccessToken: token,
		TokenType:   "Bearer",
		ExpiresIn:   900, // 15分钟
		Scope:       "bid:submit report:read",
	}, nil
}
```

---

## 五、与知识库的对照

### 已有知识

| 文件 | 位置 | 相关内容 |
|------|------|----------|
| `advertising/dsp-core-flow-deep.md` | advertising | DSP核心流程中涉及Token传递 |
| `security/security-core.md` | security | 通用安全架构，包含认证基础 |
| `security/zero-trust-mtls-supply-chain.md` | security | mTLS概念，可用于服务间认证 |
| `architecture-patterns/microservice-patterns-deep.md` | architecture-patterns | 服务网格中的认证模式 |

### 本文件补充的独特内容

1. **广告系统特有的三级权限链**（集团→代理商→子账户）— 知识库中无对应文档
2. **OAuth 2.0在广告系统中的Grant Type选择策略** — 解释了为什么不用Password Grant
3. **JWT配合Redis的双写模式** — 解决了"JWT无状态但需要撤销"的经典矛盾
4. **广告API路由权限矩阵** — 生产级Go实现，涵盖Campaign/Creative/Reporting/Billing全链路
5. **自助开户流程中的IAM集成** — 从注册到激活的完整权限分配逻辑
6. **跨域Token交换** — DSP↔Ad Exchange之间的信任建立机制

### 建议后续补充

- [ ] 将`ad-iam-deep.md`中的权限模型整合到`advertising/dsp-core-flow-deep.md`中
- [ ] 结合`security/zero-trust-mtls-supply-chain.md`，补充服务间mTLS + JWT的双因子认证方案
- [ ] 扩展`ad-platform-example`中的实际项目，加入IAM模块的代码示例
