# 应用层认证授权深度实战：Session-Based Auth + Multi-Tenant RBAC

> **来源**：ad_smart_delivery_platform 源码解析 (`internal/auth/`, `internal/platform/governance/`)
> **创建日期**：2026-07-13
> **深度等级**：🟢深（源码级 + 生产排障）

---

## 一、入门引导：为什么不用 JWT？

### 1.1 类比：酒店钥匙 vs 永久门禁卡

JWT 像是一张**永久门禁卡**——只要没过期，任何拿到卡的人都能开门，服务端无法主动撤销。

Session-based auth 像是**酒店房卡**——每次入住发卡，退房时卡立即失效，前台可以随时作废。

```
JWT 生命周期:
签发 → 用户持有 → 直到过期（服务端无法提前撤销）
  ↑                    ↑
  └── 丢失即灾难 ───────┘

Session 生命周期:
签发 → 用户持有 → 随时可撤销（服务端控制）
  ↑                    ↑
  └── 丢失可即时作废 ───┘
```

### 1.2 生产场景选择

| 维度 | JWT | Session-Based |
|------|-----|---------------|
| 服务端状态 | 无状态 | 有状态（DB/Redis） |
| 撤销能力 | ❌ 需黑名单 | ✅ 直接删 DB |
| 扩展性 | ✅ 天然水平扩展 | ⚠️ 需共享存储 |
| 安全性 | 中等（密钥泄露风险） | 高（token 存 DB） |
| 适用场景 | API 微服务、移动端 | Web 应用、多租户平台 |

**ad_smart_delivery_platform 的选择**：Session-based + Token 双重模式。
- Web 登录走 Gin session（cookie）
- API 调用走 Bearer Token（DB 存储）
- 内部服务间调用走 Header Email（X-User-Email）

---

## 二、核心架构解析

### 2.1 双账户体系

```
┌──────────────────────────────────────────────────────┐
│                    Auth Service                        │
├──────────────────────────────────────────────────────┤
│                                                      │
│  AccountType: Platform                               │
│  ┌─────────────────────────────────────┐             │
│  │  users 表                             │             │
│  │  - id (UUID)                         │             │
│  │  - email (UNIQUE)                    │             │
│  │  - phone                             │             │
│  │  - password_hash (SHA256+Salt)       │             │
│  │  - role (super_admin/user/...)       │             │
│  │  - tenant_id, workspace_id           │             │
│  │  - auth_provider ('local')           │             │
│  └─────────────────────────────────────┘             │
│                                                      │
│  AccountType: App                                    │
│  ┌─────────────────────────────────────┐             │
│  │  app_users 表                         │             │
│  │  - id (UUID)                         │             │
│  │  - email (UNIQUE)                    │             │
│  │  - phone                             │             │
│  │  - password_hash                     │             │
│  │  - role (fixed: 'user')              │             │
│  │  - tenant_id, workspace_id           │             │
│  └─────────────────────────────────────┘             │
│                                                      │
│  ┌─────────────────────────────────────┐             │
│  │  auth_sessions 表                     │             │
│  │  - id (UUID)                         │             │
│  │  - account_type                      │             │
│  │  - user_id (FK)                      │             │
│  │  - token_hash (SHA256)               │             │
│  │  - expires_at                        │             │
│  │  - last_seen_at                      │             │
│  └─────────────────────────────────────┘             │
│                                                      │
└──────────────────────────────────────────────────────┘
```

### 2.2 源码级：账户注册流程

```go
// internal/auth/service.go — Register 完整流程
func (s *Service) Register(ctx context.Context, req RegisterRequest) (*Account, string, error) {
    // Step 1: 基础校验
    accountType := normalizeAccountType(req.AccountType)
    email, phone := normalizeIdentifiers(req.Account, req.Email, req.Phone)
    
    if email == "" && phone == "" {
        return nil, "", fmt.Errorf("email or phone is required")
    }
    if len(strings.TrimSpace(req.Password)) < 6 {
        return nil, "", fmt.Errorf("password must contain at least 6 characters")
    }
    
    // Step 2: App 邮箱白名单控制
    if accountType == AccountTypeApp && !exportedAppHeaderEmailAllowed(email) {
        return nil, "", ErrAppEmailNotAllowed
    }
    
    // Step 3: 密码哈希（SHA256 + Salt + Iterations）
    passwordHash, err := hashPassword(req.Password)
    if err != nil {
        return nil, "", fmt.Errorf("hash password: %w", err)
    }
    
    // Step 4: 注册到对应的表
    if accountType == AccountTypeApp {
        return s.registerApp(ctx, email, phone, req.Name, passwordHash)
    }
    return s.registerPlatform(ctx, email, phone, req.Name, passwordHash)
}
```

**关键点**：
1. `normalizeIdentifiers` 智能判断输入是邮箱还是手机号——包含 `@` 就是邮箱，否则是手机号
2. App 账户有**邮箱白名单**限制，防止任意注册
3. 密码哈希使用自定义的 SHA256 迭代方案（不是 bcrypt/scrypt）

### 2.3 源码级：密码哈希实现

```go
// internal/auth/service.go — 密码哈希
func hashPassword(password string) (string, error) {
    // 1. 生成 16 字节随机盐
    salt := make([]byte, 16)
    if _, err := rand.Read(salt); err != nil {
        return "", err
    }
    
    // 2. 迭代 120,000 次 SHA256
    iterations := 120000
    digest := passwordDigest(password, salt, iterations)
    
    // 3. 格式化存储格式: sha256$120000$salt$digest
    return fmt.Sprintf("sha256$%d$%s$%s", iterations,
        base64.RawURLEncoding.EncodeToString(salt),
        base64.RawURLEncoding.EncodeToString(digest)), nil
}

// 核心哈希函数：password + salt -> 迭代 SHA256
func passwordDigest(password string, salt []byte, iterations int) []byte {
    buf := append([]byte(password), salt...)
    sum := sha256.Sum256(buf)
    digest := sum[:]
    for i := 1; i < iterations; i++ {
        next := sha256.Sum256(digest)
        digest = next[:]
    }
    return digest
}

// 密码验证：constant-time comparison 防时序攻击
func verifyPassword(encoded, password string) bool {
    parts := strings.Split(encoded, "$")
    if len(parts) != 4 || parts[0] != "sha256" {
        return false
    }
    var iterations int
    if _, err := fmt.Sscanf(parts[1], "%d", &iterations); err != nil || iterations <= 0 {
        return false
    }
    salt, err := base64.RawURLEncoding.DecodeString(parts[2])
    if err != nil {
        return false
    }
    expected, err := base64.RawURLEncoding.DecodeString(parts[3])
    if err != nil {
        return false
    }
    actual := passwordDigest(password, salt, iterations)
    // subtle.ConstantTimeCompare: 恒定时间比较，防时序攻击
    return subtle.ConstantTimeCompare(actual, expected) == 1
}
```

**源码级深度解析**：

| 安全措施 | 实现方式 | 防护目标 |
|----------|----------|----------|
| Salt | 16 字节 crypto/rand | 彩虹表攻击 |
| 迭代次数 | 120,000 次 SHA256 | 暴力破解成本 |
| Constant-Time Compare | `subtle.ConstantTimeCompare` | 时序攻击 |
| 存储格式 | `algo$iterations$salt$digest` | 可迁移/可升级 |

**生产排障**：120,000 次迭代在 Go 中约耗时 10-50ms（取决于 CPU）。如果登录接口 P99 超过 200ms，说明：
1. 数据库查询慢（应加 `email` 唯一索引）
2. CPU 资源不足（容器 CPU limit 太低）
3. 并发锁竞争（应改用 `sync.Map` 或无锁设计）

---

## 三、登录与 Session 管理

### 3.1 双通道认证

```go
// Current() — 支持两种认证方式：Bearer Token 或 Cookie Session
func (s *Service) Current(c *gin.Context) (*Account, string, bool) {
    // 通道 1: Bearer Token（API 调用）
    token := bearerToken(c)
    if token == "" {
        token = strings.TrimSpace(c.Query("access_token"))
    }
    if token != "" {
        if account, tokenHash, ok := s.currentFromToken(c.Request.Context(), token); ok {
            return account, tokenHash, true
        }
    }
    
    // 通道 2: Cookie Session（Web 浏览器）
    if account, ok := s.currentFromSession(c); ok {
        return account, "", true
    }
    
    return nil, "", false
}

// bearerToken — 从 Authorization header 提取
func bearerToken(c *gin.Context) string {
    header := strings.TrimSpace(c.GetHeader("Authorization"))
    if strings.HasPrefix(strings.ToLower(header), "bearer ") {
        return strings.TrimSpace(header[7:])
    }
    return ""
}
```

### 3.2 Token 创建与验证

```go
// 创建 Session Token
func (s *Service) createSession(ctx context.Context, account *Account) (string, error) {
    // 生成 32 字节随机 token（URL-safe base64）
    token, err := randomToken()
    if err != nil {
        return "", err
    }
    
    // 存入 auth_sessions 表（存 hash，不存明文）
    _, err = s.db.ExecContext(ctx, `
        INSERT INTO auth_sessions (id, account_type, user_id, token_hash, expires_at)
        VALUES (?, ?, ?, ?, ?)`,
        uuid.NewString(), account.AccountType, account.ID,
        hashToken(token), time.Now().Add(s.sessionTTL))
    
    return token, nil
}

// randomToken — 32 字节加密安全随机数
func randomToken() (string, error) {
    buf := make([]byte, 32)
    if _, err := rand.Read(buf); err != nil {
        return "", err
    }
    return base64.RawURLEncoding.EncodeToString(buf), nil
}

// hashToken — Token 存储前哈希
func hashToken(token string) string {
    sum := sha256.Sum256([]byte(token))
    return hex.EncodeToString(sum[:])
}
```

**关键设计**：
1. Token 以**明文返回给用户**（用于后续请求）
2. Token 以**SHA256 hash 存入数据库**（即使 DB 泄露也无法还原）
3. 每次请求时，将传来的 token 哈希化后查 DB

### 3.3 Token 续期（滑动过期）

```go
// currentFromToken — 验证 token 并续期
func (s *Service) currentFromToken(ctx context.Context, token string) (*Account, string, bool) {
    tokenHash := hashToken(token)
    
    var accountType, userID string
    err := s.db.QueryRowContext(ctx, `
        SELECT account_type, user_id
        FROM auth_sessions
        WHERE token_hash = ? AND expires_at > CURRENT_TIMESTAMP`, tokenHash).Scan(&accountType, &userID)
    if err != nil {
        return nil, "", false
    }
    
    account, err := s.loadAccountByID(ctx, accountType, userID)
    if err != nil || account.Status != "active" {
        return nil, "", false
    }
    
    // ⭐ 滑动续期：每次成功验证都延长 TTL
    _, _ = s.db.ExecContext(ctx, `
        UPDATE auth_sessions 
        SET last_seen_at = CURRENT_TIMESTAMP, expires_at = ? 
        WHERE token_hash = ?`,
        time.Now().Add(s.sessionTTL), tokenHash)
    
    return account, tokenHash, true
}
```

**滑动过期 vs 固定过期**：
```
滑动过期（当前实现）:
登录 ───────────────────────────────→ 过期
              ↗ 每次请求续期 ↗
              
固定过期:
登录 ──────────────────────→ 过期
              ↖ 不再续期 ↖
```

默认 TTL 为 30 天，可通过环境变量配置：
```bash
APP_AUTH_SESSION_TTL=720h          # 直接设 duration
APP_AUTH_SESSION_TTL_DAYS=7        # 或设天数
```

### 3.4 登出

```go
func (s *Service) Logout(c *gin.Context) {
    // 1. 删除 Bearer Token
    if token := bearerToken(c); token != "" {
        _, _ = s.db.ExecContext(c.Request.Context(), 
            `DELETE FROM auth_sessions WHERE token_hash = ?`, hashToken(token))
    }
    
    // 2. 删除 Session Cookie
    session := sessions.Default(c)
    if tokenHash, ok := session.Get(sessionTokenHash).(string); ok && tokenHash != "" {
        _, _ = s.db.ExecContext(c.Request.Context(),
            `DELETE FROM auth_sessions WHERE token_hash = ?`, tokenHash)
    }
    
    // 3. 清除 cookie
    session.Clear()
    _ = session.Save()
}
```

---

## 四、多租户 RBAC 架构

### 4.1 层级模型

```
Platform
├── Domain (general / platform)
│   └── Tenant (tenant_default / 客户 A / 客户 B)
│       └── Workspace (workspace_default / 项目 X / 项目 Y)
│           ├── Users
│           ├── Agents
│           ├── Graphs
│           ├── Skills
│           └── Tools
```

### 4.2 角色体系

```go
// internal/platform/governance/models.go
const (
    RoleSuperAdmin     = "super_admin"   // 平台管理员，最高权限
    RoleTenantAdmin    = "tenant_admin"   // 租户管理员
    RoleWorkspaceAdmin = "workspace_admin" // 工作空间管理员
    RoleUser           = "user"           // 普通用户
)
```

### 4.3 首次注册超级管理员

```go
// registerPlatform — 第一个注册用户自动成为 super_admin
func (s *Service) registerPlatform(ctx context.Context, email, phone, name, passwordHash string) (*Account, string, error) {
    // 检查是否已有带密码的用户
    var credentialUsers int
    if err := s.db.QueryRowContext(ctx, 
        `SELECT COUNT(1) FROM users WHERE COALESCE(password_hash, '') != ''`).Scan(&credentialUsers); err == nil {
        
        if credentialUsers == 0 {
            // 第一个用户 = 超级管理员
            bootstrapRole = governance.RoleSuperAdmin
        }
    }
    
    // ... 创建用户，role = bootstrapRole
}
```

**设计意图**：无需预置管理员账号，第一个注册的人自动获得最高权限。这在 SaaS 平台中很常见。

### 4.4 能力与特性控制

```go
// internal/platform/governance/models.go
const (
    CapabilityAgentBuilder   = "agent_builder"
    CapabilityGraphOptimizer = "graph_optimizer"
    CapabilitySkillSandbox   = "skill_sandbox"
    CapabilityAppExporter    = "app_exporter"
    
    FeatureAgentBuilderPro = "agent_builder_pro"
    FeatureGraphOptimizer  = "graph_optimizer"
    FeatureSkillSandbox    = "skill_sandbox"
    FeatureAppExporter     = "app_exporter"
)
```

 entitlement 检查流程：
```
用户请求 → 提取 tenant_id → 查 tenant.plan → 查 entitlement → 允许/拒绝
                                    ↓
                              free / pro / enterprise
```

---

## 五、内部服务间认证

### 5.1 Header-Based 认证

```go
// currentFromExportedAppHeader — 内部服务通过 HTTP Header 认证
func currentFromExportedAppHeader(c *gin.Context, s *Service) (*Account, bool) {
    email := strings.ToLower(strings.TrimSpace(c.GetHeader("X-User-Email")))
    if email == "" || !exportedAppHeaderEmailAllowed(email) {
        return nil, false
    }
    
    // 尝试从 DB 查找
    if s != nil && s.db != nil {
        if account, _, err := s.findAppAccount(c.Request.Context(), email, ""); err == nil && account.Status == "active" {
            account.AccountType = AccountTypeApp
            return account, true
        }
    }
    
    // 找不到就创建一个虚拟账户（用于跨服务传递身份）
    return &Account{
        ID:          strings.NewReplacer("@", "_", ".", "_", "+", "_").Replace(email),
        AccountType: AccountTypeApp,
        Email:       email,
        Name:        email,
        Role:        governance.RoleUser,
        TenantID:    governance.TenantDefault,
        WorkspaceID: governance.WorkspaceDefault,
        Status:      "active",
    }, true
}

// 白名单控制
func exportedAppHeaderEmailAllowed(email string) bool {
    allowed := strings.TrimSpace(os.Getenv("EXPORTED_APP_ALLOWED_EMAILS"))
    if allowed == "" {
        allowed = "yanping.ma@shopee.com" // 默认只允许自己
    }
    for _, item := range strings.Split(allowed, ",") {
        if strings.EqualFold(strings.TrimSpace(item), email) {
            return true
        }
    }
    return false
}
```

**安全分析**：
- ⚠️ **风险**：Header-based 认证依赖调用方正确设置 `X-User-Email`，如果中间代理被劫持，可伪造身份
- ✅ **缓解**：邮箱白名单 + 内部网络隔离
- 🔧 **改进建议**：改用 mTLS 或 JWT signed by internal CA

### 5.2 RequireRuntime Middleware

```go
// RequireRuntime — 内部服务调用的认证中间件
func (s *Service) RequireRuntime() gin.HandlerFunc {
    return func(c *gin.Context) {
        account, _, ok := s.CurrentRuntime(c)
        if !ok {
            c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"error": "please login"})
            return
        }
        setGinAccount(c, account)
        c.Next()
    }
}

// CurrentRuntime — 优先 Bearer Token，fallback 到 Header
func (s *Service) CurrentRuntime(c *gin.Context) (*Account, string, bool) {
    if s == nil || s.db == nil {
        // 无 DB 时只用 Header 认证
        if account, ok := currentFromExportedAppHeader(c, s); ok {
            return account, "", true
        }
        return nil, "", false
    }
    // 有 DB 时优先 Bearer Token
    if account, tokenHash, ok := s.Current(c); ok {
        return account, tokenHash, ok
    }
    // fallback 到 Header
    if account, ok := currentFromExportedAppHeader(c, s); ok {
        return account, "", true
    }
    return nil, "", false
}
```

---

## 六、生产排障

### 6.1 场景：登录 P99 延迟过高

**症状**：正常登录 50ms，高峰期 P99 超过 500ms

**排查步骤**：

```bash
# 1. 检查 password_hash 查询是否走索引
EXPLAIN ANALYZE SELECT id, email, phone, name, role, tenant_id, workspace_id, status, COALESCE(password_hash, '')
FROM users WHERE LOWER(email) = LOWER('test@example.com') LIMIT 1;

# 预期：使用 email 唯一索引，cost < 1ms
# 异常：全表扫描 → 说明 email 没有 UNIQUE 索引
```

**根因**：`users.email` 没有 UNIQUE 索引，导致每次登录全表扫描。

**修复**：
```sql
CREATE UNIQUE INDEX idx_users_email ON users(LOWER(email));
-- 或如果 email 已标准化为小写：
CREATE UNIQUE INDEX idx_users_email ON users(email);
```

### 6.2 场景：Token 续期失败

**症状**：用户频繁被登出，即使一直在操作

**排查**：
```sql
-- 检查 auth_sessions 表中是否有过期未清理的记录
SELECT COUNT(*) FROM auth_sessions WHERE expires_at < CURRENT_TIMESTAMP;

-- 检查是否有 token_hash 冲突
SELECT token_hash, COUNT(*) FROM auth_sessions GROUP BY token_hash HAVING COUNT(*) > 1;
```

**根因**：`auth_sessions` 表没有定期清理过期 token 的机制，导致表膨胀。

**修复方案**：
```go
// 添加定时清理任务
func (s *Service) CleanupExpiredSessions(ctx context.Context) error {
    _, err := s.db.ExecContext(ctx, `
        DELETE FROM auth_sessions WHERE expires_at < CURRENT_TIMESTAMP`)
    return err
}

// 建议：每天凌晨执行一次
// crontab: 0 2 * * * /path/to/cleanup-auth-sessions
```

### 6.3 场景：密码哈希升级

**症状**：需要增加迭代次数（如从 120,000 提升到 200,000）

**方案**：懒加载升级

```go
func (s *Service) Login(ctx context.Context, req LoginRequest) (*Account, string, error) {
    // ... 验证密码
    if passwordHash == "" || !verifyPassword(passwordHash, req.Password) {
        return nil, "", ErrInvalidCredentials
    }
    
    // 检查是否需要升级
    if needsUpgrade(passwordHash) {
        newHash, _ := hashPassword(req.Password)
        s.db.ExecContext(ctx, `UPDATE users SET password_hash = ? WHERE email = ?`, newHash, email)
    }
    
    // ... 创建 session
}

func needsUpgrade(encoded string) bool {
    parts := strings.Split(encoded, "$")
    if len(parts) != 4 { return false }
    var iterations int
    fmt.Sscanf(parts[1], "%d", &iterations)
    return iterations < 200000 // 目标迭代次数
}
```

---

## 七、与知识库的对照

### 7.1 已有内容

| 知识库文件 | 覆盖内容 | Gap |
|------------|----------|-----|
| `security/zero-trust-mtls-supply-chain.md` | mTLS、零信任架构 | ❌ 无应用层 auth 实现 |
| `security/security-architecture-deep.md` | 安全架构原则 | ❌ 无具体 auth 代码 |
| `security/go-cryptography-practical-deep.md` | Go 密码学基础 | ⚠️ 有哈希但无 session 管理 |
| `microservice/microservice-distributed-tracing-deep.md` | 分布式追踪 | ❌ 无认证上下文传递 |
| `agent-ai/weread-ai-agent-dev-deep.md` | Agent 开发 | ⚠️ 有 MCP 但无 auth 集成 |

### 7.2 补充内容

本文档填补了以下知识缺口：
1. **Session-based vs JWT 选型** — 生产代码中的实际选择及原因
2. **自定义密码哈希方案** — SHA256 + Salt + Iterations 的完整实现
3. **双账户体系设计** — Platform vs App 账户的分离策略
4. **Token 安全存储** — 明文返回 + DB 存 hash 的模式
5. **滑动过期机制** — 每次请求续期的 session 管理
6. **多租户 RBAC** — Domain → Tenant → Workspace 三级模型
7. **内部服务认证** — Header-based 认证的实现与风险

### 7.3 后续补充建议

| 优先级 | 主题 | 说明 |
|--------|------|------|
| P0 | OAuth2/OIDC 集成 | 生产平台需要第三方登录 |
| P0 | API Key 管理 | 程序化广告对接需要 API Key |
| P1 | RBAC 权限检查中间件 | 当前只有登录，没有细粒度权限 |
| P1 | MFA/TOTP | 安全合规要求 |
| P2 | SSO/SAML | 企业客户集成 |

---

## 八、自测题

### Q1: 为什么 auth_sessions 表存的是 token_hash 而不是 token 明文？

**答案**：
1. **安全合规**：即使数据库泄露，攻击者也无法直接用泄露的 hash 冒充用户
2. **验证方式**：用户请求带来 token → 服务端 hash(token) → 查 DB 匹配
3. **登出能力**：删 DB 记录 = 立即失效，不需要黑名单
4. **注意**：这不同于 JWT 的签名验证——JWT 不存 DB，靠签名保证不被篡改

### Q2: `subtle.ConstantTimeCompare` 为什么能防时序攻击？

**答案**：
```go
// 普通比较（不安全）:
func compare(a, b []byte) bool {
    for i := range a {
        if a[i] != b[i] {
            return false  // ❌ 第一个字节不同就立即返回，耗时不同
        }
    }
    return true
}

// ConstantTime 比较（安全）:
func compare(a, b []byte) bool {
    if len(a) != len(b) {
        return false
    }
    var equal byte = 0
    for i := 0; i < len(a); i++ {
        equal |= a[i] ^ b[i]  // 逐字节异或，全部比较完
    }
    return equal == 0  // ✅ 无论是否匹配，都遍历完整个数组
}
```

时序攻击原理：攻击者通过测量响应时间来推断 password 的正确字符。ConstantTimeCompare 确保无论匹配到第几个字节，执行时间都相同。

### Q3: 为什么 App 账户的 role 固定为 'user'，而 Platform 账户可以有 super_admin？

**答案**：
1. **安全边界**：App 账户是程序化调用的服务账户，不应有管理权限
2. **最小权限原则**：App 只能操作自己的数据，不能管理租户/工作空间
3. **Platform 账户**是人的账户，需要管理权限（创建 agent、配置 graph 等）
4. **代码证据**：
   ```go
   // findAppAccount 中硬编码 role
   account := &Account{AccountType: AccountTypeApp, Role: governance.RoleUser}
   
   // registerApp 中也固定 role
   account := &Account{..., Role: governance.RoleUser, ...}
   ```

---

## 九、动手验证

### 9.1 本地验证密码哈希性能

```go
package main

import (
    "crypto/rand"
    "crypto/sha256"
    "fmt"
    "time"
)

func hashPassword(password string, iterations int) []byte {
    salt := make([]byte, 16)
    rand.Read(salt)
    
    buf := append([]byte(password), salt...)
    sum := sha256.Sum256(buf)
    digest := sum[:]
    
    start := time.Now()
    for i := 1; i < iterations; i++ {
        next := sha256.Sum256(digest)
        digest = next[:]
    }
    elapsed := time.Since(start)
    
    fmt.Printf("Iterations: %d, Time: %v\n", iterations, elapsed)
    return digest
}

func main() {
    hashPassword("test123", 120000)
    hashPassword("test123", 200000)
    hashPassword("test123", 500000)
}
```

预期输出（M1 MacBook）：
```
Iterations: 120000, Time: 15ms
Iterations: 200000, Time: 25ms
Iterations: 500000, Time: 60ms
```

### 9.2 验证 Token 安全存储

```bash
# 1. 启动 DAP 平台
cd ~/GolandProjects/ad_smart_delivery_platform
go run ./cmd/server/...

# 2. 注册用户
curl -X POST http://localhost:8080/auth/register \
  -H "Content-Type: application/json" \
  -d '{"account":"test@example.com","password":"testpass123","name":"Test User"}'

# 3. 检查 DB 中存储的是 hash 而非明文
sqlite3 eino.db "SELECT id, email, SUBSTR(password_hash, 1, 20) FROM users LIMIT 1;"
# 预期输出类似: 550e8400-e29b... | test@example.com | sha256$120000$YwX...
```

### 9.3 测试滑动过期

```bash
# 1. 登录获取 token
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H "Content-Type: application/json" \
  -d '{"account":"test@example.com","password":"testpass123"}' | jq -r '.token')

# 2. 检查初始 expires_at
sqlite3 eino.db "SELECT expires_at FROM auth_sessions WHERE token_hash = '$(echo -n $TOKEN | sha256sum | cut -d' ' -f1)';"

# 3. 等待 1 小时后再次请求（应自动续期）
sleep 3600
curl -s http://localhost:8080/auth/status \
  -H "Authorization: Bearer $TOKEN"

# 4. 检查 expires_at 已更新
sqlite3 eino.db "SELECT expires_at, last_seen_at FROM auth_sessions WHERE token_hash = '$(echo -n $TOKEN | sha256sum | cut -d' ' -f1)';"
```

---

## 十、Trade-off 分析

### 10.1 密码哈希方案对比

| 方案 | 安全性 | 性能 | 可移植性 | 本项目选择 |
|------|--------|------|----------|-----------|
| bcrypt | ✅ | 🟡 较慢 | ✅ | ❌ |
| scrypt | ✅✅ | 🔴 慢 | ✅ | ❌ |
| Argon2id | ✅✅✅ | 🟡 | ⚠️ Go 库少 | ❌ |
| SHA256 + Salt + Iterations | 🟡 | ✅ 快 | ✅ | ✅ |

**选择 SHA256 的理由**：
1. **性能**：120,000 次迭代 ≈ 15-50ms，在可接受范围
2. **可控**：迭代次数可通过环境变量动态调整
3. **简单**：无需引入外部 C 依赖（bcrypt/scrypt 通常需要 CGO）
4. **够用**：内部平台场景，攻击面有限

**改进建议**：生产环境应升级到 Argon2id（`golang.org/x/crypto/argon2`），它是 NIST 推荐的密码哈希标准。

### 10.2 Session vs JWT 对比

| 维度 | Session（当前） | JWT |
|------|----------------|-----|
| 撤销 | ✅ O(1) DB DELETE | ❌ 需黑名单/短过期 |
| 状态 | ❌ 有状态 | ✅ 无状态 |
| 水平扩展 | ⚠️ 需共享 DB/Redis | ✅ 天然扩展 |
| 安全性 | ✅ Token 存 DB | ⚠️ 密钥泄露风险 |
| 复杂度 | 中等 | 低 |

---

## 附录：完整账户流转图

```
注册流程:
  用户 → POST /auth/register → Register() → hashPassword() → INSERT users → INSERT auth_sessions → 返回 token

登录流程:
  用户 → POST /auth/login → Login() → findAccount() → verifyPassword() → createSession() → 返回 token

验证流程:
  请求 → Current() → bearerToken()/currentFromSession() → currentFromToken()/currentFromSession() → loadAccountByID() → 返回 Account

内部服务认证:
  服务 → RequireRuntime() → CurrentRuntime() → currentFromExportedAppHeader() → 返回 Account

|登出流程:
  用户 → POST /auth/logout → Logout() → DELETE auth_sessions → Clear Session → 返回 logged_in: false
```

---

## 十一、源码级深度：账户查找与归一化

### 11.1 智能标识符归一化

```go
// normalizeIdentifiers — 自动判断用户输入是邮箱还是手机号
func normalizeIdentifiers(account, email, phone string) (string, string) {
    account = strings.TrimSpace(account)
    email = strings.ToLower(strings.TrimSpace(email))
    phone = normalizePhone(phone)
    
    // 如果提供了 account 字段，自动判断类型
    if account != "" {
        if strings.Contains(account, "@") {
            // 包含 @ → 邮箱
            email = strings.ToLower(account)
        } else {
            // 不包含 @ → 手机号
            phone = normalizePhone(account)
        }
    }
    return email, phone
}

// normalizePhone — 清理手机号格式
func normalizePhone(value string) string {
    value = strings.TrimSpace(value)
    // 移除所有非数字字符: ( ) - 空格
    replacer := strings.NewReplacer(" ", "", "-", "", "(", "", ")", "")
    return replacer.Replace(value)
}
```

**设计亮点**：用户只需输入一个 `account` 字段，系统自动判断是邮箱还是手机号。这降低了 UX 复杂度。

### 11.2 动态 SQL 查询构建

```go
// accountLookup — 根据 email/phone 构建查询
func accountLookup(table, email, phone string) (string, []any) {
    // 场景 1: 两者都有 → OR 查询
    if email != "" && phone != "" {
        return fmt.Sprintf(`
            SELECT id, email, COALESCE(phone, ''), name, %s, tenant_id, workspace_id, status, COALESCE(password_hash, '')
            FROM %s
            WHERE LOWER(email) = LOWER(?) OR phone = ?
            LIMIT 1`, roleColumn(table)), []any{email, phone}
    }
    // 场景 2: 只有 email
    if email != "" {
        return fmt.Sprintf(`
            SELECT id, email, COALESCE(phone, ''), name, %s, tenant_id, workspace_id, status, COALESCE(password_hash, '')
            FROM %s
            WHERE LOWER(email) = LOWER(?)
            LIMIT 1`, roleColumn(table)), []any{email}
    }
    // 场景 3: 只有 phone
    return fmt.Sprintf(`
        SELECT id, email, COALESCE(phone, ''), name, %s, tenant_id, workspace_id, status, COALESCE(password_hash, '')
        FROM %s
        WHERE phone = ?
        LIMIT 1`, roleColumn(table), table), []any{phone}
}

// roleColumn — 根据表名返回角色列名
func roleColumn(table string) string {
    if table == "app_users" {
        return "'user'"  // App 用户没有 role 列，用常量
    }
    return "role"  // Platform 用户有 role 列
}
```

**源码级分析**：这里用了 `COALESCE(phone, '')` 来处理 phone 可能为 NULL 的情况。SQLite 中 NULL 比较总是返回 false，所以 `WHERE phone = ?` 在 phone 为 NULL 时不会匹配。

### 11.3 存储邮箱 vs 显示邮箱

```go
// storageEmail — 存储时统一用邮箱，手机号转为 fake email
func storageEmail(email, phone string) string {
    if email != "" {
        return email
    }
    return phone + "@phone.local"  // 手机号用户用 fake email
}

// displayName — 显示名称
func displayName(email, phone string) string {
    if email != "" {
        return email
    }
    return phone
}
```

**设计意图**：`users` 表的 `email` 字段是 UNIQUE 的。对于只有手机号的用户，用 `phone@phone.local` 作为 fake email 来满足唯一约束。

---

## 十二、安全深度：密码哈希方案演进

### 12.1 SHA256 迭代方案的局限性

```
当前方案: SHA256(SHA256(...SHA256(password + salt)...))
迭代次数: 120,000
单次耗时: ~15ms (M1)

问题:
1. SHA256 是硬件加速友好的算法 → GPU/ASIC 破解成本低
2. 内存不敏感 → 无法抵抗内存攻击
3. 迭代次数可调 → 但升级需要重新哈希所有用户密码
```

### 12.2 Argon2id 升级方案

```go
// 升级后的密码哈希（Argon2id）
import "golang.org/x/crypto/argon2"

func hashPasswordArgon2(password string) (string, error) {
    salt := make([]byte, 16)
    if _, err := rand.Read(salt); err != nil {
        return "", err
    }
    
    // Argon2id 参数（OWASP 2024 推荐值）
    // Memory: 64MB, Iterations: 3, Parallelism: 1
    hash := argon2.IDKey([]byte(password), salt, 3, 64*1024, 1, 32)
    
    // 格式: argon2id$v=19$m=65536,t=3,p=1$salt$hash
    b64Salt := base64.RawStdEncoding.EncodeToString(salt)
    b64Hash := base64.RawStdEncoding.EncodeToString(hash)
    return fmt.Sprintf("argon2id$v=19$m=65536,t=3,p=1$%s$%s", b64Salt, b64Hash), nil
}

func verifyPasswordArgon2(encoded, password string) bool {
    parts := strings.Split(encoded, "$")
    // parts: ["argon2id", "v=19", "m=65536", "t=3", "p=1", salt, hash]
    
    salt, _ := base64.RawStdEncoding.DecodeString(parts[5])
    expected, _ := base64.RawStdEncoding.DecodeString(parts[6])
    
    memory := parseUint32(parts[2])  // 65536
    timeCost := parseUint32(parts[3])  // 3
    parallelism := parseUint32(parts[4])  // 1
    
    actual := argon2.IDKey([]byte(password), salt, timeCost, memory, parallelism, 32)
    return subtle.ConstantTimeCompare(actual, expected) == 1
}
```

**OWASP 2024 推荐参数**：

| 场景 | Memory | Iterations | Parallelism | 单次耗时 |
|------|--------|------------|-------------|----------|
| Web 登录 | 64 MB | 3 | 1 | ~500ms |
| API 验证 | 32 MB | 2 | 2 | ~200ms |
| 内部服务 | 16 MB | 1 | 4 | ~50ms |

**升级路径**：
```
Step 1: 用户登录时检测到旧格式 → 后台异步升级到 Argon2
Step 2: 下次登录时用新格式验证
Step 3: 设定截止日期，强制所有用户重置密码
```

### 12.2 密钥派生函数对比

| KDF | 内存敏感 | GPU 抵抗 | 标准状态 | 推荐场景 |
|-----|----------|----------|----------|----------|
| PBKDF2 (SHA256) | ❌ | ⚠️ 弱 | NIST | 遗留系统 |
| bcrypt | ❌ | ✅ 中 | OWASP | 传统 Web |
| scrypt | ✅ | ✅ 强 | IETF | 加密货币 |
| Argon2id | ✅✅ | ✅✅ 最强 | W3C 标准 | 新项目首选 |

---

## 十三、多租户架构深度

### 13.1 租户隔离策略

```
┌─────────────────────────────────────────────────────┐
│                    Tenant Isolation                   │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Level 1: 数据隔离                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
│  │ Tenant A │  │ Tenant B │  │ Tenant C │          │
│  │ users    │  │ users    │  │ users    │          │
│  │ agents   │  │ agents   │  │ agents   │          │
│  │ graphs   │  │ graphs   │  │ graphs   │          │
│  └──────────┘  └──────────┘  └──────────┘          │
│       │              │              │                │
│       └──────────────┴──────────────┘                │
│                    ↓                                 │
│           ┌─────────────────┐                        │
│           │   Shared Schema  │                       │
│           │   (single DB)    │                       │
│           └─────────────────┘                        │
│                                                     │
│  Level 2: 权限隔离                                  │
│  每个请求携带 tenant_id → 所有查询自动附加             │
│  WHERE tenant_id = ?                                │
│                                                     │
│  Level 3: 资源隔离                                  │
│  Workspace 级别的配额管理                            │
│  - Agent 数量限制                                   │
│  - Graph 数量限制                                   │
│  - Skill 数量限制                                   │
│                                                     │
└─────────────────────────────────────────────────────┘
```

### 13.2 源码：租户上下文传递

```go
// setGinAccount — 将账户信息注入 Gin Context
func setGinAccount(c *gin.Context, account *Account) {
    c.Set("account_type", account.AccountType)
    c.Set("user_id", account.ID)
    c.Set("user_role", account.Role)
    c.Set(middleware.SESSION_USER_KEY, account.Email)
    c.Set("user_email", account.Email)
    c.Set("tenant_id", account.TenantID)
    c.Set("workspace_id", account.WorkspaceID)
}

// 在后续中间件/处理器中使用
func someMiddleware(s *auth.Service) gin.HandlerFunc {
    return func(c *gin.Context) {
        account, _, ok := s.Current(c)
        if !ok {
            c.AbortWithStatusJSON(401, gin.H{"error": "unauthorized"})
            return
        }
        
        // 设置租户上下文
        setGinAccount(c, account)
        
        // 后续处理器可以获取 tenant_id
        tenantID, _ := c.Get("tenant_id")
        workspaceID, _ := c.Get("workspace_id")
        
        // 所有 DB 查询都应附加租户过滤
        // SELECT * FROM agents WHERE tenant_id = ? AND workspace_id = ?
        
        c.Next()
    }
}
```

### 13.3 租户级功能授权

```go
// EntitlementService — 检查租户是否有某功能的权限
func (s *EntitlementService) Check(ctx context.Context, req CheckRequest) (CheckDecision, error) {
    decision := CheckDecision{
        Feature:  req.Feature,
        TenantID: req.TenantID,
    }
    
    // 1. 获取租户信息
    tenant, err := s.repo.GetTenant(ctx, req.TenantID)
    if err != nil {
        decision.Reason = fmt.Sprintf("tenant %s not found", req.TenantID)
        return decision, nil
    }
    
    // 2. 检查系统级 capability
    cap, err := s.repo.GetSystemCapabilityByFeature(ctx, req.Feature)
    if err != nil {
        decision.Reason = "capability not found"
        return decision, nil
    }
    
    // 3. 检查租户级 entitlement
    ent, err := s.repo.GetTenantEntitlement(ctx, req.TenantID, req.Feature)
    if err != nil {
        // 没有显式 entitlement → 检查 plan
        decision.Allowed = tenant.Plan == "enterprise"
        decision.Source = "plan_based"
        return decision, nil
    }
    
    // 4. 显式 entitlement 决定
    decision.Allowed = ent.Active
    decision.Source = "entitlement"
    return decision, nil
}
```

---

## 十四、生产排障：认证系统常见问题

### 14.1 问题：并发登录导致 session 表爆炸

**症状**：auth_sessions 表超过 1000 万行，查询变慢

**排查**：
```sql
-- 检查活跃 vs 过期 session 比例
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN expires_at > CURRENT_TIMESTAMP THEN 1 ELSE 0 END) as active,
    SUM(CASE WHEN expires_at <= CURRENT_TIMESTAMP THEN 1 ELSE 0 END) as expired
FROM auth_sessions;

-- 检查哪个用户 session 最多
SELECT user_id, COUNT(*) as session_count
FROM auth_sessions
GROUP BY user_id
ORDER BY session_count DESC
LIMIT 10;
```

**根因**：
1. 没有定期清理过期 session
2. 用户多设备登录（手机+平板+电脑）
3. Token 续期过于激进

**修复**：
```go
// 方案 1: 定时清理（推荐）
func (s *Service) ScheduleCleanup(interval time.Duration) {
    ticker := time.NewTicker(interval)
    go func() {
        for range ticker.C {
            ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
            s.db.ExecContext(ctx, `DELETE FROM auth_sessions WHERE expires_at < CURRENT_TIMESTAMP`)
            cancel()
        }
    }()
}

// 方案 2: 登录时清理该用户的过期 session
func (s *Service) Login(ctx context.Context, req LoginRequest) (*Account, string, error) {
    // 先清理过期 session
    s.db.ExecContext(ctx, `DELETE FROM auth_sessions WHERE user_id = ? AND expires_at < CURRENT_TIMESTAMP`, userID)
    
    // 限制最大活跃 session 数
    var count int
    s.db.QueryRowContext(ctx, `SELECT COUNT(*) FROM auth_sessions WHERE user_id = ? AND expires_at > CURRENT_TIMESTAMP`, userID).Scan(&count)
    if count >= 10 {
        // 删除最旧的 session
        s.db.ExecContext(ctx, `DELETE FROM auth_sessions WHERE user_id = ? ORDER BY expires_at ASC LIMIT ?`, userID, count-10)
    }
    
    // ... 创建新 session
}
```

### 14.2 问题：Session Fixation 攻击

**场景**：攻击者先获取一个 session ID，然后诱导受害者用这个 session ID 登录

**防护**：
```go
func (s *Service) Login(ctx context.Context, req LoginRequest) (*Account, string, error) {
    // ... 验证凭据
    
    // ⭐ 登录后立即销毁旧 session，创建新 session
    // 清除可能的 fixation session
    if existingToken := bearerTokenFromRequest(); existingToken != "" {
        s.db.ExecContext(ctx, `DELETE FROM auth_sessions WHERE token_hash = ?`, hashToken(existingToken))
    }
    
    // 创建新 session
    return s.createSession(ctx, account)
}
```

### 14.3 问题：暴力破解防护

**当前状态**：代码中没有 rate limiting

**实现**：
```go
type BruteForceProtection struct {
    attempts map[string][]time.Time  // email → 失败时间戳
    mu       sync.Mutex
    maxAttempts int
    window     time.Duration
}

func (b *BruteForceProtection) CheckAndRecord(email string) error {
    b.mu.Lock()
    defer b.mu.Unlock()
    
    now := time.Now()
    windowStart := now.Add(-b.window)
    
    // 清理旧记录
    var recentAttempts []time.Time
    for _, t := range b.attempts[email] {
        if t.After(windowStart) {
            recentAttempts = append(recentAttempts, t)
        }
    }
    
    if len(recentAttempts) >= b.maxAttempts {
        return fmt.Errorf("too many attempts, please try again later")
    }
    
    b.attempts[email] = recentAttempts
    return nil
}

func (b *BruteForceProtection) RecordSuccess(email string) {
    b.mu.Lock()
    defer b.mu.Unlock()
    delete(b.attempts, email)
}

func (b *BruteForceProtection) RecordFailure(email string) {
    b.mu.Lock()
    defer b.mu.Unlock()
    b.attempts[email] = append(b.attempts[email], time.Now())
}
```

---

## 十五、与广告平台的集成

### 15.1 API Key 认证（程序化广告场景）

广告平台对接需要 API Key 认证，不同于用户登录：

```go
type APIKeyAuth struct {
    db *sql.DB
}

type APIKey struct {
    ID          string
    KeyHash     string  // SHA256 hash of the actual key
    KeyPrefix   string  // "rk_live_xxxxx" 前缀，用于展示
    TenantID    string
    UserID      string
    Permissions []string  // ["dsp:read", "dsp:write", "billing:read"]
    Active      bool
    ExpiresAt   time.Time
}

func (a *APIKeyAuth) CreateKey(userID, tenantID string, permissions []string) (*APIKey, string, error) {
    // 生成随机 key
    rawKey, _ := randomToken()
    keyHash := hashToken(rawKey)
    
    // 保存
    keyID := uuid.NewString()
    _, err := a.db.Exec(`
        INSERT INTO api_keys (id, user_id, tenant_id, key_hash, key_prefix, permissions, active)
        VALUES (?, ?, ?, ?, ?, ?, true)`,
        keyID, userID, tenantID, keyHash, rawKey[:8], toJSON(permissions))
    
    return &APIKey{ID: keyID, KeyPrefix: rawKey[:8]}, rawKey, err
}

func (a *APIKeyAuth) Authenticate(key string) (*APIKey, error) {
    keyHash := hashToken(key)
    
    var keyObj APIKey
    err := a.db.QueryRow(`
        SELECT id, user_id, tenant_id, key_prefix, permissions, active, expires_at
        FROM api_keys WHERE key_hash = ?`, keyHash).Scan(
        &keyObj.ID, &keyObj.UserID, &keyObj.TenantID, &keyObj.KeyPrefix,
        &keyObj.Permissions, &keyObj.Active, &keyObj.ExpiresAt)
    
    if err != nil {
        return nil, fmt.Errorf("invalid API key")
    }
    
    if !keyObj.Active {
        return nil, fmt.Errorf("API key is deactivated")
    }
    
    if time.Now().After(keyObj.ExpiresAt) {
        return nil, fmt.Errorf("API key expired")
    }
    
    return &keyObj, nil
}
```

### 15.2 广告平台 OAuth2 集成

Facebook/Google 广告平台对接需要 OAuth2：

```go
type OAuth2Config struct {
    Platform   string  // "facebook" | "google"
    ClientID   string
    ClientSecret string
    RedirectURL string
    Scopes     []string
}

func (c *OAuth2Config) GetOAuth2Config() *oauth2.Config {
    var endpoint oauth2.Endpoint
    switch c.Platform {
    case "facebook":
        endpoint = oauth2.Endpoint{
            AuthURL:  "https://www.facebook.com/v18.0/dialog/oauth",
            TokenURL: "https://graph.facebook.com/v18.0/oauth/access_token",
        }
    case "google":
        endpoint = oauth2.Endpoint{
            AuthURL:  "https://accounts.google.com/o/oauth2/v2/auth",
            TokenURL: "https://oauth2.googleapis.com/token",
        }
    }
    
    return &oauth2.Config{
        ClientID:     c.ClientID,
        ClientSecret: c.ClientSecret,
        RedirectURL:  c.RedirectURL,
        Scopes:       c.Scopes,
        Endpoint:     endpoint,
    }
}

// 广告平台 token 刷新
func (c *OAuth2Config) RefreshToken(ctx context.Context, token *oauth2.Token) (*oauth2.Token, error) {
    return c.GetOAuth2Config().TokenSource(ctx, token).(*oauth2.Token), nil
}
```

---

## 十六、总结与最佳实践

### 16.1 认证系统设计 Checklist

- [ ] 密码使用安全的 KDF（Argon2id 优先）
- [ ] Token 以 hash 形式存储在 DB
- [ ] 使用 constant-time comparison 防止时序攻击
- [ ] 实现 rate limiting 防止暴力破解
- [ ] 支持多因素认证（MFA）
- [ ] Session 有明确的过期策略
- [ ] 登出时清除所有相关 session
- [ ] 内部服务间认证不使用用户凭据
- [ ] API Key 有独立的权限体系
- [ ] 多租户数据严格隔离

### 16.2 广告平台认证特殊考虑

1. **程序化广告实时性**：RTB 请求需要在 100ms 内完成认证 → 考虑本地缓存 token
2. **高并发**：DSP 每秒处理百万级请求 → 认证接口需要水平扩展
3. **审计合规**：广告花费涉及资金 → 所有认证事件需要记录到审计日志
4. **多平台集成**：Facebook/Google/TikTok 各有不同的 OAuth2 流程 → 抽象统一接口
5. **API Key 管理**：客户需要自行管理 API Key → 提供自助管理界面

### 16.3 性能基准

| 操作 | 当前实现 | 优化后 |
|------|----------|--------|
| 密码哈希 (120k iterations) | 15-50ms | 5-15ms (Argon2id) |
| Token 验证 (DB lookup) | 1-5ms | <1ms (Redis cache) |
| 并发登录处理 | 受 DB 限制 | 1000+ RPS (连接池) |
| Session 清理 | 手动 | 自动 (定时任务) |

---

## 十七、延伸阅读

### 17.1 推荐书籍

| 书籍 | 相关章节 | 获取方式 |
|------|----------|----------|
| OWASP Authentication Cheat Sheet | 全文 | https://cheatsheetseries.owasp.org/ |
| Go Web Programming | Ch. 8 Session Management | 微信读书 |
| Building Secure Go Software | Ch. 5 Cryptography | GitHub 开源 |

### 17.2 相关源码

| 文件 | 路径 | 行数 |
|------|------|------|
| Auth Service | `internal/auth/service.go` | 628 |
| Auth Handler | `internal/auth/handler.go` | 101 |
| Governance Models | `internal/platform/governance/models.go` | 150+ |
| Entitlement Check | `internal/platform/governance/entitlement.go` | 200+ |
