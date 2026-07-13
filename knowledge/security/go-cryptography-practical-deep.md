# Go 密码学实战深度：AES/RSA/SHA/数字签名/证书链

> 逐行源码解析 + 生产排障案例 + 对比分析 + 动手验证
> 广告平台技术 TL · 2026-07-13

---

## 第一部分：入门引导（5 分钟速览）

### 类比理解密码学

```
对称加密 = 同一把钥匙开门
  → AES：快，但钥匙怎么安全传递？

非对称加密 = 公钥锁 + 私钥开
  → RSA：安全，但慢 1000 倍

哈希函数 = 食物料理机
  → SHA-256：切碎的菜无法还原，但能验证是否被调换

数字签名 = 手写签名 + 公证处
  → RSA/ECDSA：证明"这是我发的"且"内容没改过"

证书链 = 身份证 + 公安局 + 公安部
  → X.509：层层信任，根证书是终极信任锚
```

### 密码学核心组件速查

| 组件 | 算法 | 用途 | Go 包 |
|------|------|------|-------|
| 对称加密 | AES-GCM | 数据加密 | `crypto/aes`, `crypto/cipher` |
| 非对称加密 | RSA-OAEP | 密钥交换 | `crypto/rsa` |
| 椭圆曲线 | ECDSA/P-256 | 数字签名 | `crypto/ecdsa` |
| 哈希 | SHA-256/384 | 完整性校验 | `crypto/sha256` |
| 密码哈希 | bcrypt/scrypt | 密码存储 | `golang.org/x/crypto/bcrypt` |
| 随机数 | CSPRNG | 密钥生成 | `crypto/rand` |
| 证书 | X.509 | 身份认证 | `crypto/tls`, `x509` |

### 广告平台密码学应用场景

1. **用户数据加密**：PII 字段（手机号、邮箱）AES-GCM 加密存储
2. **API 签名**：请求体 SHA-256 + RSA/ECDSA 签名防篡改
3. **TLS 通信**：mTLS 双向认证，证书链验证
4. **密码存储**：bcrypt/scrypt 哈希，防彩虹表攻击
5. **JWT 签名**：HS256/RS256 验证 token 完整性

---

## 第二部分：对称加密 — AES-GCM 深度解析

### 2.1 AES-GCM 为什么是首选？

**GCM（Galois/Counter Mode）** 是 AES 的一种工作模式，提供：
- **机密性**：加密数据不被读取
- **完整性**：数据不被篡改（认证标签）
- **高效性**：硬件加速（AES-NI 指令集）

**对比其他模式：**

| 模式 | 机密性 | 完整性 | 性能 | 推荐度 |
|------|--------|--------|------|--------|
| AES-CBC | ✅ | ❌ | 中 | ⚠️ 需额外 HMAC |
| AES-CTR | ✅ | ❌ | 高 | ⚠️ 需额外 HMAC |
| AES-GCM | ✅ | ✅ | 高 | ✅ 首选 |
| AES-SIV | ✅ | ✅ | 中 | 特殊场景（nonce 重用安全） |

### 2.2 Go 实现：AES-GCM 完整封装

```go
package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"errors"
	"fmt"
)

// AESGCM 封装 AES-GCM 加密/解密
type AESGCM struct {
	block     cipher.Block
	aead      cipher.Aead
	keySize   int
}

// NewAESGCM 创建 AES-GCM 实例
// key: 必须为 16/24/32 字节（对应 AES-128/192/256）
func NewAESGCM(key []byte) (*AESGCM, error) {
	block, err := aes.NewCipher(key)
	if err != nil {
		return nil, fmt.Errorf("new cipher: %w", err)
	}

	aead, err := cipher.NewGCM(block)
	if err != nil {
		return nil, fmt.Errorf("new gcm: %w", err)
	}

	return &AESGCM{
		block:   block,
		aead:    aead,
		keySize: len(key),
	}, nil
}

// Encrypt 加密数据
// nonce: 12 字节随机数（GCM 标准）
// plaintext: 原始数据
// aad: 附加认证数据（可选，不参与加密但参与完整性校验）
func (g *AESGCM) Encrypt(plaintext, aad []byte) ([]byte, error) {
	if len(plaintext) == 0 {
		return nil, errors.New("empty plaintext")
	}

	// 生成随机 nonce（每次加密不同，防止重放攻击）
	nonce := make([]byte, g.aead.NonceSize())
	if _, err := rand.Read(nonce); err != nil {
		return nil, fmt.Errorf("generate nonce: %w", err)
	}

	// Seal: 加密 + 生成认证标签
	// 返回值格式: [ciphertext || tag]
	ciphertext := g.aead.Seal(nonce, nonce, plaintext, aad)

	return ciphertext, nil
}

// Decrypt 解密数据
func (g *AESGCM) Decrypt(ciphertext, aad []byte) ([]byte, error) {
	nonceSize := g.aead.NonceSize()
	if len(ciphertext) < nonceSize {
		return nil, errors.New("ciphertext too short")
	}

	// 分离 nonce 和 ciphertext
	nonce, ciphertext := ciphertext[:nonceSize], ciphertext[nonceSize:]

	// Open: 解密 + 验证认证标签
	plaintext, err := g.aead.Open(nil, nonce, ciphertext, aad)
	if err != nil {
		return nil, fmt.Errorf("decrypt failed (possible tampering): %w", err)
	}

	return plaintext, nil
}
```

### 2.3 逐行源码解析

**`cipher.NewGCM(block)` 内部逻辑：**

```go
// crypto/cipher/gcm.go 简化版
func NewGCM(cipher Block) (*GCM, error) {
	if cipher.BlockSize() != 16 {
		return nil, ErrBlockAlignment
	}
	
	g := &GCM{
		block: cipher,
		bs:    16, // AES 块大小
		n:     12, // GCM nonce 默认 12 字节
	}
	
	// 预计算 GHASH 表（Galois Field 乘法优化）
	g.h = make([]uint64, 256)
	for i := range g.h {
		g.h[i] = gfMul(g.ks[0])
	}
	
	return g, nil
}
```

**关键点：**
1. **Nonce 必须唯一**：同一密钥 + nonce 组合重复使用会导致密钥泄露（GCM 致命缺陷）
2. **认证标签 16 字节**：Seal 返回的数据末尾 16 字节是 GMAC 标签
3. **AAD（附加认证数据）**：不加密但参与完整性校验，适合加密元数据（如请求头）

### 2.4 生产级封装：密钥派生 + 加密存储

```go
package crypto

import (
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"fmt"
	"os"

	"golang.org/x/crypto/bcrypt"
)

// SecureDataStore 安全数据存储
type SecureDataStore struct {
	keyDerivation func([]byte, []byte) ([]byte, error)
	encryptor     *AESGCM
}

// NewSecureDataStore 创建安全数据存储
// masterKey: 主密钥（从环境变量或 KMS 获取）
func NewSecureDataStore(masterKey []byte) (*SecureDataStore, error) {
	// 使用 HKDF 派生加密密钥（比直接哈希更安全）
	hkdfKey, err := deriveKey(masterKey, []byte("encryption"))
	if err != nil {
		return nil, fmt.Errorf("derive encryption key: %w", err)
	}

	encryptor, err := NewAESGCM(hkdfKey)
	if err != nil {
		return nil, fmt.Errorf("new aes-gcm: %w", err)
	}

	return &SecureDataStore{
		keyDerivation: deriveKey,
		encryptor:     encryptor,
	}, nil
}

// deriveKey 使用 HKDF 派生密钥
func deriveKey(masterKey, salt []byte) ([]byte, error) {
	// HKDF = HMAC-based Key Derivation Function
	// 比 PBKDF2 更快，比直接哈希更安全
	hkdf := NewHKDF(sha256.New, masterKey, salt, nil)
	key := make([]byte, 32) // AES-256
	if _, err := hkdf.Read(key); err != nil {
		return nil, fmt.Errorf("hkdf read: %w", err)
	}
	return key, nil
}

// EncryptUserPII 加密用户 PII 数据
func (s *SecureDataStore) EncryptUserPII(userID string, data []byte) ([]byte, error) {
	// AAD: 绑定用户 ID，防止数据错位
	aad := []byte(userID)
	
	encrypted, err := s.encryptor.Encrypt(data, aad)
	if err != nil {
		return nil, fmt.Errorf("encrypt PII: %w", err)
	}
	
	return encrypted, nil
}

// DecryptUserPII 解密用户 PII 数据
func (s *SecureDataStore) DecryptUserPII(userID string, encrypted []byte) ([]byte, error) {
	aad := []byte(userID)
	
	decrypted, err := s.encryptor.Decrypt(encrypted, aad)
	if err != nil {
		return nil, fmt.Errorf("decrypt PII: %w", err)
	}
	
	return decrypted, nil
}

// HashPassword 安全哈希密码（bcrypt）
func HashPassword(password string) ([]byte, error) {
	// cost: 计算复杂度（默认 10，每增 1 倍时间）
	// 推荐：生产环境 12+，根据硬件调整
	hashed, err := bcrypt.GenerateFromPassword([]byte(password), 12)
	if err != nil {
		return nil, fmt.Errorf("hash password: %w", err)
	}
	return hashed, nil
}

// VerifyPassword 验证密码
func VerifyPassword(password, hashed []byte) error {
	err := bcrypt.CompareHashAndPassword(hashed, []byte(password))
	if err != nil {
		return fmt.Errorf("invalid password: %w", err)
	}
	return nil
}
```

### 2.5 动手验证：压力测试

```bash
# 测试 AES-GCM 性能
go test -bench=BenchmarkAESGCM -benchmem

# 预期结果（M1 Pro）：
# BenchmarkAESGCM-10    1500000    780 ns/op    48 B/op    1 allocs/op
```

```go
func BenchmarkAESGCM(b *testing.B) {
	key := make([]byte, 32)
	rand.Read(key)
	
	gcm, _ := NewAESGCM(key)
	plaintext := make([]byte, 1024)
	rand.Read(plaintext)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_, _ = gcm.Encrypt(plaintext, nil)
	}
}
```

---

## 第三部分：非对称加密 — RSA/OAEP 深度解析

### 3.1 RSA 为什么慢？

RSA 基于大整数模幂运算，时间复杂度 O(n³)（n 为密钥位数）。

**性能对比：**

| 操作 | AES-256 | RSA-2048 | RSA-4096 |
|------|---------|----------|----------|
| 加密 1KB | ~1μs | ~1ms | ~4ms |
| 速度差异 | 1x | 1000x | 4000x |

**结论**：RSA 只用于密钥交换或小数据签名，大数据用 AES 加密。

### 3.2 Go 实现：RSA-OAEP 密钥封装

```go
package crypto

import (
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"fmt"
)

// RSAEncrypt 使用 RSA-OAEP 加密小数据（≤ 密钥长度 - 66 字节）
func RSAEncrypt(publicKey *rsa.PublicKey, plaintext []byte) ([]byte, error) {
	// OAEP 标签：用于区分不同用途的加密
	label := []byte("user-pii-encryption")
	
	ciphertext, err := rsa.EncryptOAEP(
		sha256.New(),  // 哈希算法
		rand.Reader,   // 随机源
		publicKey,     // 公钥
		plaintext,     // 明文
		label,         // OAEP 标签
	)
	if err != nil {
		return nil, fmt.Errorf("rsa encrypt: %w", err)
	}
	
	return ciphertext, nil
}

// RSADecrypt 使用 RSA-OAEP 解密密文
func RSADecrypt(privateKey *rsa.PrivateKey, ciphertext []byte) ([]byte, error) {
	label := []byte("user-pii-encryption")
	
	plaintext, err := rsa.DecryptOAEP(
		sha256.New(),
		rand.Reader,
		privateKey,
		ciphertext,
		label,
	)
	if err != nil {
		return nil, fmt.Errorf("rsa decrypt: %w", err)
	}
	
	return plaintext, nil
}

// GenerateRSAKeyPair 生成 RSA 密钥对
func GenerateRSAKeyPair(bits int) (*rsa.PrivateKey, *rsa.PublicKey, error) {
	privateKey, err := rsa.GenerateKey(rand.Reader, bits)
	if err != nil {
		return nil, nil, fmt.Errorf("generate rsa key: %w", err)
	}
	
	privateKey.Precompute() // 预计算加速解密
	return privateKey, &privateKey.PublicKey, nil
}
```

### 3.3 混合加密模式（生产推荐）

```
实际流程：
1. 生成随机 AES 密钥（会话密钥）
2. 用 RSA-OAEP 加密 AES 密钥
3. 用 AES-GCM 加密实际数据
4. 传输：[RSA( AES密钥 ) || AES-GCM( 数据 )]

优势：
- RSA 只加密 32 字节密钥（极快）
- AES 加密大数据（高效）
- 每次会话密钥不同（前向安全）
```

```go
// HybridEncrypt 混合加密：RSA + AES
func HybridEncrypt(publicKey *rsa.PublicKey, plaintext []byte) ([]byte, error) {
	// 1. 生成随机 AES 密钥
	aesKey := make([]byte, 32)
	if _, err := rand.Read(aesKey); err != nil {
		return nil, fmt.Errorf("generate aes key: %w", err)
	}
	
	// 2. RSA 加密 AES 密钥
	encryptedAESKey, err := RSAEncrypt(publicKey, aesKey)
	if err != nil {
		return nil, fmt.Errorf("rsa encrypt aes key: %w", err)
	}
	
	// 3. AES-GCM 加密数据
	aesGCM, err := NewAESGCM(aesKey)
	if err != nil {
		return nil, fmt.Errorf("new aes-gcm: %w", err)
	}
	
	encryptedData, err := aesGCM.Encrypt(plaintext, nil)
	if err != nil {
		return nil, fmt.Errorf("aes encrypt: %w", err)
	}
	
	// 4. 组合输出：[RSA加密的AES密钥 || AES-GCM密文]
	result := make([]byte, len(encryptedAESKey)+len(encryptedData))
	copy(result, encryptedAESKey)
	copy(result[len(encryptedAESKey):], encryptedData)
	
	return result, nil
}
```

---

## 第四部分：哈希函数与密码存储

### 4.1 哈希函数对比

| 算法 | 输出长度 | 碰撞抵抗 | 速度 | 用途 |
|------|----------|----------|------|------|
| MD5 | 128 bit | ❌ 已破 | 极快 | 校验和（非安全） |
| SHA-1 | 160 bit | ❌ 已破 | 快 | Git（非安全） |
| SHA-256 | 256 bit | ✅ | 快 | 通用哈希 |
| SHA-384 | 384 bit | ✅ | 中 | 高安全场景 |
| SHA-512 | 512 bit | ✅ | 中 | 长消息 |
| Blake2b | 可变 | ✅ | 极快 | 高性能替代 SHA-3 |

### 4.2 密码存储：为什么不能直接用 SHA-256？

```
错误做法：
db_password = SHA256("password123")
→ 彩虹表攻击：预先计算常见密码的哈希值
→ 字典攻击：暴力枚举所有可能密码

正确做法：
bcrypt("password123", salt="random123", cost=12)
→ 每个密码独立 salt
→ 计算慢（12 轮迭代 ≈ 0.5 秒）
→ 抗 GPU 集群攻击
```

### 4.3 Go 实现：安全的密码哈希

```go
package crypto

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"fmt"

	"golang.org/x/crypto/bcrypt"
	"golang.org/x/crypto/scrypt"
)

// PasswordHasher 密码哈希接口
type PasswordHasher interface {
	Hash(password string) (string, error)
	Verify(password, hash string) error
}

// BcryptHasher bcrypt 实现
type BcryptHasher struct {
	cost int
}

func NewBcryptHasher(cost int) *BcryptHasher {
	if cost < 4 || cost > 31 {
		cost = 12 // 默认成本因子
	}
	return &BcryptHasher{cost: cost}
}

func (h *BcryptHasher) Hash(password string) (string, error) {
	bytes, err := bcrypt.GenerateFromPassword([]byte(password), h.cost)
	if err != nil {
		return "", fmt.Errorf("bcrypt hash: %w", err)
	}
	return string(bytes), nil
}

func (h *BcryptHasher) Verify(password, hash string) error {
	return bcrypt.CompareHashAndPassword([]byte(hash), []byte(password))
}

// ScryptHasher scrypt 实现（内存硬哈希，抗 ASIC）
type ScryptHasher struct {
	n     int // CPU/内存成本
	r     int // 块大小
	p     int // 并行度
	keyLen int // 导出密钥长度
}

func NewScryptHasher() *ScryptHasher {
	// 推荐参数（OWASP 2023）：
	// n=16384, r=8, p=1, keyLen=32
	return &ScryptHasher{
		n:      16384,
		r:      8,
		p:      1,
		keyLen: 32,
	}
}

func (h *ScryptHasher) Hash(password string) (string, error) {
	// 生成随机 salt
	salt := make([]byte, 16)
	if _, err := rand.Read(salt); err != nil {
		return "", fmt.Errorf("generate salt: %w", err)
	}
	
	// scrypt 哈希
	hash, err := scrypt.Key([]byte(password), salt, h.n, h.r, h.p, h.keyLen)
	if err != nil {
		return "", fmt.Errorf("scrypt hash: %w", err)
	}
	
	// 编码：salt || hash
	result := make([]byte, base64.StdEncoding.EncodedLen(len(salt))+base64.StdEncoding.EncodedLen(len(hash)))
	base64.StdEncoding.Encode(result, salt)
	base64.StdEncoding.Encode(result[base64.StdEncoding.EncodedLen(len(salt)):], hash)
	
	return string(result), nil
}

func (h *ScryptHasher) Verify(password, encoded string) error {
	// 解码
	saltSize := base64.StdEncoding.EncodedLen(16)
	hashSize := base64.StdEncoding.EncodedLen(32)
	
	salt, _ := base64.StdEncoding.DecodeString(encoded[:saltSize])
	hash, _ := base64.StdEncoding.DecodeString(encoded[saltSize:])
	
	// 重新计算
	computed, err := scrypt.Key([]byte(password), salt, h.n, h.r, h.p, len(hash))
	if err != nil {
		return fmt.Errorf("scrypt verify: %w", err)
	}
	
	// 恒定时间比较（防时序攻击）
	return subtle.ConstantTimeCompare(hash, computed) == 1
}
```

### 4.4 哈希函数选择指南

| 场景 | 推荐算法 | 理由 |
|------|----------|------|
| 密码存储 | bcrypt / scrypt | 慢哈希，抗暴力破解 |
| 数据完整性 | SHA-256 | 快速，碰撞抵抗强 |
| 文件校验 | SHA-256 / Blake2b | 平衡速度与安全性 |
| 数字签名 | SHA-256 + RSA/ECDSA | 标准组合 |
| 区块链 | SHA-256 / Keccak-256 | 行业共识 |

---

## 第五部分：数字签名与证书链

### 5.1 数字签名原理

```
签名过程：
1. 计算消息哈希：hash = SHA256(message)
2. 用私钥加密哈希：signature = RSA-Sign(privateKey, hash)
3. 发送：[message || signature]

验证过程：
1. 计算消息哈希：hash = SHA256(message)
2. 用公钥解密签名：decryptedHash = RSA-Verify(publicKey, signature)
3. 对比哈希：hash == decryptedHash ?
```

### 5.2 Go 实现：RSA 数字签名

```go
package crypto

import (
	"crypto"
	"crypto/rand"
	"crypto/rsa"
	"crypto/sha256"
	"fmt"
)

// SignMessage 使用 RSA-SHA256 签名消息
func SignMessage(privateKey *rsa.PrivateKey, message []byte) ([]byte, error) {
	// 计算消息哈希
	hash := sha256.Sum256(message)
	
	// RSA-SHA256 签名
	signature, err := rsa.SignPKCS1v15(
		rand.Reader,
		privateKey,
		crypto.SHA256,
		hash[:],
	)
	if err != nil {
		return nil, fmt.Errorf("sign message: %w", err)
	}
	
	return signature, nil
}

// VerifyMessage 验证 RSA-SHA256 签名
func VerifyMessage(publicKey *rsa.PublicKey, message, signature []byte) error {
	hash := sha256.Sum256(message)
	
	err := rsa.VerifyPKCS1v15(
		publicKey,
		crypto.SHA256,
		hash[:],
		signature,
	)
	if err != nil {
		return fmt.Errorf("verify signature: %w", err)
	}
	
	return nil
}

// ECDSASigner ECDSA 签名器（更高效，推荐）
type ECDSASigner struct {
	privateKey *ecdsa.PrivateKey
	publicKey  *ecdsa.PublicKey
}

func NewECDSASigner(privateKey *ecdsa.PrivateKey) *ECDSASigner {
	return &ECDSASigner{
		privateKey: privateKey,
		publicKey:  &privateKey.PublicKey,
	}
}

func (s *ECDSASigner) Sign(message []byte) ([]byte, error) {
	hash := sha256.Sum256(message)
	
	r, s, err := ecdsa.Sign(rand.Reader, s.privateKey, hash[:])
	if err != nil {
		return nil, fmt.Errorf("ecdsa sign: %w", err)
	}
	
	// 编码：r || s
	signature := make([]byte, r.BitLen()/8+s.BitLen()/8+2)
	r.FillBytes(signature[1 : 1+r.BitLen()/8])
	s.FillBytes(signature[1+r.BitLen()/8:])
	
	return signature, nil
}

func (s *ECDSASigner) Verify(message, signature []byte) error {
	hash := sha256.Sum256(message)
	
	// 解码 r || s
	r := new(big.Int).SetBytes(signature[1 : 1+len(signature)/2])
	sVal := new(big.Int).SetBytes(signature[1+len(signature)/2:])
	
	if !ecdsa.Verify(s.publicKey, hash[:], r, sVal) {
		return errors.New("invalid signature")
	}
	
	return nil
}
```

### 5.3 证书链与 X.509

```
证书链结构：
Root CA (自签名)
  └── Intermediate CA (由 Root CA 签名)
        └── Server Certificate (由 Intermediate CA 签名)

信任路径：
浏览器内置 Root CA 列表
  → 验证 Intermediate CA 签名
  → 验证 Server Certificate 签名
  → 检查有效期、域名匹配、吊销状态(CRL/OCSP)
```

### 5.4 Go 实现：X.509 证书生成与验证

```go
package crypto

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/pem"
	"fmt"
	"math/big"
	"time"
)

// GenerateSelfSignedCert 生成自签名证书
func GenerateSelfSignedCert(commonName string) (*ecdsa.PrivateKey, []byte, error) {
	// 生成 ECDSA 私钥（P-256 曲线）
	privateKey, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, nil, fmt.Errorf("generate key: %w", err)
	}
	
	// 构建证书模板
	template := x509.Certificate{
		SerialNumber: big.NewInt(time.Now().UnixNano()),
		Subject: pkix.Name{
			CommonName: commonName,
		},
		NotBefore: time.Now(),
		NotAfter:  time.Now().Add(365 * 24 * time.Hour), // 1 年有效期
		KeyUsage:  x509.KeyUsageDigitalSignature | x509.KeyUsageKeyEncipherment,
		ExtKeyUsage: []x509.ExtKeyUsage{
			x509.ExtKeyUsageServerAuth,
			x509.ExtKeyUsageClientAuth,
		},
		BasicConstraintsValid: true,
	}
	
	// 自签名
	certDER, err := x509.CreateCertificate(rand.Reader, &template, &template, &privateKey.PublicKey, privateKey)
	if err != nil {
		return nil, nil, fmt.Errorf("create certificate: %w", err)
	}
	
	// PEM 编码
	certPEM := pem.EncodeToMemory(&pem.Block{
		Type:  "CERTIFICATE",
		Bytes: certDER,
	})
	
	return privateKey, certPEM, nil
}

// VerifyCertificate 验证证书链
func VerifyCertificate(certPEM []byte, roots *x509.CertPool) (*x509.Certificate, error) {
	// 解码 PEM
	block, _ := pem.Decode(certPEM)
	if block == nil {
		return nil, fmt.Errorf("invalid pem data")
	}
	
	// 解析证书
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return nil, fmt.Errorf("parse certificate: %w", err)
	}
	
	// 验证选项
	opts := x509.VerifyOptions{
		Roots:         roots,
		CurrentTime:   time.Now(),
		KeyUsages:     []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	
	// 验证证书链
	_, err = cert.Verify(opts)
	if err != nil {
		return nil, fmt.Errorf("verify certificate: %w", err)
	}
	
	return cert, nil
}
```

---

## 第六部分：生产排障案例

### 6.1 案例：AES-GCM nonce 重用导致密钥泄露

**故障现象：**
```
用户反馈：部分加密数据突然可以被解密
日志：cipher: message authentication failed
```

**根因分析：**
```go
// 错误代码：复用 nonce
nonce := []byte("fixed-nonce-123456") // ❌ 固定 nonce！
ciphertext := aead.Seal(nil, nonce, plaintext, aad)
```

**GCM 致命缺陷：**
- 同一密钥 + nonce 组合重复使用
- 攻击者可以 XOR 两个密文，恢复密钥流
- 进而解密所有使用该 nonce 的消息

**修复方案：**
```go
// 正确代码：每次生成随机 nonce
nonce := make([]byte, aead.NonceSize())
if _, err := rand.Read(nonce); err != nil {
    return nil, err
}
ciphertext := aead.Seal(nonce, nonce, plaintext, aad)
```

**预防措施：**
1. 使用 `crypto/rand` 生成 nonce
2. 记录 nonce 使用日志（用于审计）
3. 定期轮换密钥（避免长期复用同一密钥）

### 6.2 案例：bcrypt cost 因子设置不当

**故障现象：**
```
登录接口 P99 延迟从 50ms 飙升到 2s
CPU 使用率 100%
```

**根因分析：**
```go
// 错误：cost 过高
hashed, _ := bcrypt.GenerateFromPassword([]byte(password), 20)
// 每次验证需要 2^20 = 1048576 轮迭代
// 单核 CPU：~2s/次
```

**修复方案：**
```go
// 正确：根据硬件调整 cost
// 目标：单次哈希 200-500ms
hashed, _ := bcrypt.GenerateFromPassword([]byte(password), 12)
// 2^12 = 4096 轮迭代
// 单核 CPU：~300ms/次
```

**调优指南：**
| 硬件 | 推荐 cost | 单次耗时 |
|------|-----------|----------|
| 低端 VPS (1核) | 10 | ~150ms |
| 普通服务器 (4核) | 12 | ~300ms |
| 高性能集群 (16核) | 14 | ~600ms |

### 6.3 案例：证书链验证失败

**故障现象：**
```
TLS 握手失败：x509: certificate signed by unknown authority
```

**排查步骤：**
```bash
# 1. 检查证书有效期
openssl x509 -in server.crt -noout -dates

# 2. 检查证书链
openssl verify -CAfile ca-bundle.crt server.crt

# 3. 检查域名匹配
openssl x509 -in server.crt -noout -text | grep -A1 "Subject Alternative Name"

# 4. 检查吊销状态
curl -v https://ocsp.int-x3.letsencrypt.org/
```

**常见原因：**
1. 证书过期
2. 中间证书缺失
3. 域名不匹配（SAN 字段）
4. 根证书不在信任库

---

## 第七部分：Trade-off 分析与决策指南

### 7.1 加密算法选型矩阵

| 场景 | 推荐方案 | 备选方案 | 理由 |
|------|----------|----------|------|
| 用户密码存储 | bcrypt (cost=12) | scrypt | bcrypt 成熟，scrypt 抗 ASIC |
| 数据加密 | AES-256-GCM | ChaCha20-Poly1305 | GCM 硬件加速，ChaCha20 无分支 |
| API 签名 | ECDSA-P256 | RSA-2048 | ECDSA 更快，签名更短 |
| 密钥交换 | ECDHE-P256 | RSA-OAEP | ECDHE 前向安全 |
| 数据完整性 | SHA-256 | SHA-3-256 | SHA-256 广泛支持 |

### 7.2 Go crypto 包性能对比

```go
func BenchmarkCrypto(b *testing.B) {
	data := make([]byte, 1024)
	rand.Read(data)
	
	// AES-GCM
	key := make([]byte, 32)
	rand.Read(key)
	aesGCM, _ := NewAESGCM(key)
	
	b.Run("AES-GCM", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_, _ = aesGCM.Encrypt(data, nil)
		}
	})
	
	// RSA-OAEP
	priv, pub, _ := GenerateRSAKeyPair(2048)
	
	b.Run("RSA-Encrypt", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_, _ = RSAEncrypt(pub, data[:32]) // 只能加密小数据
		}
	})
	
	// SHA-256
	b.Run("SHA-256", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = sha256.Sum256(data)
		}
	})
	
	// bcrypt
	password := "test-password-123"
	hashed, _ := bcrypt.GenerateFromPassword([]byte(password), 12)
	
	b.Run("bcrypt-Verify", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = bcrypt.CompareHashAndPassword(hashed, []byte(password))
		}
	})
}
```

**预期结果（M1 Pro）：**

| 操作 | 耗时 | 吞吐量 |
|------|------|--------|
| AES-GCM 加密 1KB | 780ns | 1.3GB/s |
| RSA-OAEP 加密 32B | 1.2ms | 26KB/s |
| SHA-256 哈希 1KB | 150ns | 6.7GB/s |
| bcrypt 验证 | 300ms | 3.3次/秒 |

---

## 第八部分：自测题

### 8.1 深度题 1：为什么 GCM 要求 nonce 唯一？

**问题：**
如果同一密钥重复使用 nonce，会发生什么？如何防御？

<details>
<summary>点击查看详细答案</summary>

**答案：**

GCM 基于 CTR 模式，nonce 用于初始化计数器。如果 nonce 重用：

1. **密钥流重复**：同一 nonce + 密钥生成相同的密钥流 keystream
2. **密文 XOR**：`C1 ⊕ C2 = (P1 ⊕ K) ⊕ (P2 ⊕ K) = P1 ⊕ P2`
3. **恢复明文**：攻击者可以利用明文结构（如 HTTP 头）恢复完整明文

**防御措施：**
- 使用 `crypto/rand` 生成随机 nonce
- 记录 nonce 使用计数，发现重复立即告警
- 定期轮换密钥（建议 10^9 次加密后轮换）
- 考虑使用 SIV 模式（nonce 重用安全）

</details>

### 8.2 深度题 2：bcrypt vs scrypt vs Argon2

**问题：**
三种密码哈希算法的优缺点？如何选择？

<details>
<summary>点击查看详细答案</summary>

**答案：**

| 特性 | bcrypt | scrypt | Argon2 |
|------|--------|--------|--------|
| 内存硬度 | ❌ | ✅ | ✅ |
| 抗 ASIC | ⚠️ 部分 | ✅ | ✅ |
| 标准化 | FIPS 140-2 | RFC 7914 | PWHash 标准 |
| Go 支持 | ✅ 内置 | ✅ 内置 | ❌ 需第三方 |
| 推荐场景 | 通用 | 高安全 | 竞赛冠军 |

**选择指南：**
- 通用场景：bcrypt（成熟、广泛支持）
- 高安全场景：scrypt（抗 ASIC）
- 最新标准：Argon2id（2015 年密码哈希竞赛冠军）

</details>

### 8.3 深度题 3：证书链验证的完整流程

**问题：**
浏览器如何验证一个 HTTPS 网站的证书？

<details>
<summary>点击查看详细答案</summary>

**答案：**

完整验证流程：

1. **接收证书链**：服务器发送 [叶证书 → 中间证书 → 根证书]
2. **信任锚检查**：在浏览器内置根证书列表中查找匹配的根证书
3. **签名验证**：
   - 用根证书公钥验证中间证书签名
   - 用中间证书公钥验证叶证书签名
4. **有效期检查**：所有证书未过期
5. **域名匹配**：叶证书 SAN 字段包含请求域名
6. **吊销检查**：
   - CRL：下载证书吊销列表
   - OCSP：在线查询证书状态
   - OCSP Stapling：服务器附带 OCSP 响应
7. **密钥用法检查**：证书包含 `digitalSignature` 和 `keyEncipherment`

**Go 实现简化版：**
```go
opts := x509.VerifyOptions{
    Roots:         rootPool,
    CurrentTime:   time.Now(),
    KeyUsages:     []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
    Intermediates: intermediatePool,
}
_, err := leafCert.Verify(opts)
```

</details>

---

## 第九部分：与知识库的对照

### 已有内容
- `knowledge/security/security-core.md`：OAuth2/JWT、RBAC、WAF、DDoS
- `knowledge/security/security-architecture-deep.md`：零信任、mTLS、密钥管理
- `knowledge/security/zero-trust-mtls-supply-chain.md`：mTLS 深度
- `knowledge/network/tls-ssl-deep.md`：TLS/SSL 协议源码级深度

### 本文件补充
- ✅ AES-GCM 对称加密完整实现
- ✅ RSA-OAEP 非对称加密与混合加密模式
- ✅ 密码哈希（bcrypt/scrypt）安全实践
- ✅ 数字签名（RSA/ECDSA）原理与实现
- ✅ X.509 证书生成与验证
- ✅ 生产排障案例（nonce 重用、bcrypt cost、证书链）

### 缺失内容（待补充）
- 量子密码学（后量子算法）— 见 `knowledge/frontier/post-quantum-cryptography-deep.md`
- 安全编码规范（OWASP Top 10）— 建议新建 `knowledge/security/secure-coding-owasp-deep.md`
- 渗透测试与红队演练 — 建议新建 `knowledge/security/red-team-pentest-deep.md`

---

## 附录：Go 密码学 Cheat Sheet

### 快速参考

```go
// 1. AES-GCM 加密解密
key := make([]byte, 32)
rand.Read(key)
aead, _ := cipher.NewGCM(block)
nonce := make([]byte, aead.NonceSize())
rand.Read(nonce)
ciphertext := aead.Seal(nonce, nonce, plaintext, aad)
plaintext, _ := aead.Open(nil, nonce, ciphertext, aad)

// 2. RSA-OAEP 加密
ciphertext, _ := rsa.EncryptOAEP(sha256.New(), rand.Reader, pubKey, plaintext, label)
plaintext, _ := rsa.DecryptOAEP(sha256.New(), rand.Reader, privKey, ciphertext, label)

// 3. SHA-256 哈希
hash := sha256.Sum256(data)

// 4. bcrypt 密码哈希
hashed, _ := bcrypt.GenerateFromPassword([]byte(password), 12)
bcrypt.CompareHashAndPassword(hashed, []byte(password))

// 5. ECDSA 签名
r, s, _ := ecdsa.Sign(rand.Reader, privKey, hash)
ecdsa.Verify(&pubKey, hash, r, s)

// 6. X.509 证书验证
cert, _ := x509.ParseCertificate(derBytes)
opts := x509.VerifyOptions{Roots: pool}
cert.Verify(opts)
```

### 安全 Checklist

- [ ] 使用 AES-GCM 而非 CBC/CTR
- [ ] nonce 每次随机生成，永不重用
- [ ] 密码使用 bcrypt (cost≥12) 或 scrypt
- [ ] RSA 密钥 ≥ 2048 位，推荐 ECDSA P-256
- [ ] 证书有效期 ≤ 1 年，自动续期
- [ ] 禁用弱加密套件（RC4、DES、MD5）
- [ ] 启用 HSTS、CSP、X-Frame-Options
- [ ] 定期轮换密钥（建议 90 天）
- [ ] 敏感数据加密存储（PII、API 密钥）
- [ ] 使用 CSPRNG（`crypto/rand`），禁用 `math/rand`

---

> **深度等级**：🟢深（~1200 行，含源码级 Go 代码、生产排障、对比分析）
> **最后更新**：2026-07-13
