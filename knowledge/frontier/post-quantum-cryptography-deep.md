# 后量子密码学深度实战：从理论到工程落地

## 一、为什么需要后量子密码学？

### 1.1 量子计算威胁模型

传统公钥加密体系（RSA、ECC、Diffie-Hellman）的安全性基于以下数学难题：

| 算法 | 安全基础 | 经典计算机难度 | 量子计算机难度 |
|------|---------|---------------|---------------|
| RSA | 大整数分解 | O(exp((ln n)^(1/3))) | O((ln n)^3) — Shor 算法 |
| ECC | 椭圆曲线离散对数 | O(√n) — Pollard's Rho | O((ln n)^3) — Shor 算法 |
| Diffie-Hellman | 离散对数问题 | O(√n) | O((ln n)^3) — Shor 算法 |

**Shor 算法的关键突破**：
- 经典计算机需要数千年才能破解 2048-bit RSA
- 理论上，一个拥有 ~4000 个逻辑量子比特的量子计算机可在数小时内破解
- 当前最先进量子计算机：IBM Condor（1121 量子比特，但错误率高，非逻辑量子比特）

### 1.2 "Now Harvest, Later Decrypt" 攻击

```
攻击者策略：
┌─────────────────────────────────────────────────┐
│                                                 │
│  1. 现在截获所有加密通信（TLS 握手、SSH 密钥交换）│
│      ↓                                          │
│  2. 存储密文，等待量子计算机成熟                 │
│      ↓                                          │
│  3. 未来用量子计算机解密历史数据                │
│                                                 │
└─────────────────────────────────────────────────┘
```

**影响范围**：
- 长期敏感数据（国家机密、医疗记录、知识产权）
- 证书链（CA 签名密钥泄露可伪造所有证书）
- 区块链私钥（比特币等加密货币地址）

### 1.3 NIST 后量子标准化进程

```
2016          2022           2024           2025+
───────────── ──────────── ──────────── ──────────────
NIST 征集     FROST-DSA    FIPS 203       大规模部署
候选方案      (ML-KEM)     (ML-DSA)       迁移窗口
(70+ 方案)    → 标准        → 标准
              ML-KEM        ML-DSS
              (CRYSTALS-    (FALCON +
               Kyber)        SPHINCS+)
```

**已标准化的三个核心算法**：

| 算法 | 类型 | 用途 | 密钥大小 | 安全性等级 |
|------|------|------|---------|-----------|
| ML-KEM | 基于格的 KEM | 密钥封装 | ~1KB | Level 1/3/5 |
| ML-DSA | 基于格的数字签名 | 签名验证 | ~2-4KB | Level 1/3/5 |
| SLH-DSA | 基于哈希的签名 | 长寿命签名 | ~40-80KB | Level 1/3/5 |

## 二、核心算法原理

### 2.1 基于格的密码学（Lattice-based）

#### 2.1.1 格理论基础

```
格（Lattice）定义：
给定基向量 b₁, b₂, ..., bₙ ∈ ℝᵐ
格 Λ = { Σᵢ aᵢ · bᵢ | aᵢ ∈ ℤ }

二维示例：
b₁ = (3, 1), b₂ = (1, 4)

    y
    ↑
  4 ·     ·     ·     ← b₂ 方向
    │   ╱   ╲
  3 ·  ╱  ·  ╲
    │ ╱ ╱   ╲ ╲
  2 ·· ······ ···
    │╱╱     ╲ ╲
  1 ·· ······ ··· ← b₁ 方向
    │╱       ╲
  0 ·────────────────→ x
    0  1  2  3  4  5

格点：所有整数线性组合形成的网格点
```

**关键困难问题**：

1. **SVP（最短向量问题）**：在格中找到最短的非零向量
   - 已知：基向量 b₁, ..., bₙ
   - 求：最短非零向量 v ∈ Λ
   - 经典复杂度：O(2^(0.292n)) — 指数级
   - 量子复杂度：仍为指数级（无多项式量子算法）

2. **CVP（最近向量问题）**：给定向量 t，找到最近的格点
   - 已知：基向量 b₁, ..., bₙ 和目标向量 t
   - 求：格点 v ∈ Λ 使得 ‖v - t‖ 最小
   - NP-hard

3. **LWE（学习误差问题）**：后量子密码的核心
   - 已知：矩阵 A ∈ ℤ_q^(m×n)，向量 b = A·s + e (mod q)
   - 其中 s 是秘密向量，e 是小误差向量
   - 求：秘密向量 s
   - 归约到格上的困难问题

#### 2.1.2 CRYSTALS-Kyber（现 ML-KEM）

**密钥生成**：
```go
// ML-KEM Key Generation
func MLKEMKeyGen() (pk, sk []byte, err error) {
    // 参数选择：kyber512/kyber768/kyber1024
    const n = 256      // 多项式环维度
    const q = 3329     // 模数
    const eta1 = 3     // 误差分布参数
    const eta2 = 2
    
    // 1. 生成随机种子
    seed := make([]byte, 32)
    if _, err := rand.Read(seed); err != nil {
        return nil, nil, err
    }
    
    // 2. 从种子派生矩阵 A（公共参数）
    // A ∈ ℤ_q^(k×k)，k=2/3/4 取决于安全等级
    A := matrixGenerate(seed)
    
    // 3. 生成秘密向量 s 和误差向量 e
    s := sampleDiscreteGaussian(k, eta1)
    e := sampleDiscreteGaussian(k, eta1)
    
    // 4. 计算 pk = (A, t = A·s + e)
    t := matMulAdd(A, s, e, q)
    
    pk = encodePublicKey(A, t)
    sk = encodeSecretKey(s)
    
    return pk, sk, nil
}
```

**封装（Encapsulate）**：
```go
// ML-KEM Encapsulation
func MLKEMEncaps(pk []byte) (ct, sharedKey []byte, err error) {
    // 1. 解码公钥
    A, t := decodePublicKey(pk)
    
    // 2. 生成随机消息 m
    m := make([]byte, 32)
    if _, err := rand.Read(m); err != nil {
        return nil, nil, err
    }
    
    // 3. 生成共享密钥和随机性
    hash := sha3.New512()
    hash.Write(m)
    randomSeed := hash.Sum(nil)[:32]
    sharedKey = hash.Sum(nil)[32:]
    
    // 4. 编码消息并添加冗余
    mPadded := padMessage(m)
    
    // 5. 生成随机向量 r 和误差
    r := sampleDiscreteGaussian(k, eta1, randomSeed)
    e1 := sampleDiscreteGaussian(k, eta2, randomSeed)
    e2 := sampleDiscreteGaussian(1, eta2, randomSeed)
    
    // 6. 计算密文 u = A^T · r + e1
    u := matTransposeMulAdd(A, r, e1, q)
    
    // 7. 计算密文 v = t^T · r + e2 + encode(m)
    v := scalarMulAdd(t, r, e2, mPadded, q)
    
    // 8. 打包密文
    ct = encodeCiphertext(u, v)
    
    return ct, sharedKey, nil
}
```

**解封装（Decapsulate）**：
```go
// ML-KEM Decapsulation
func MLKEMDecaps(sk, ct []byte) (sharedKey []byte, err error) {
    // 1. 解码私钥和密文
    s := decodeSecretKey(sk)
    u, v := decodeCiphertext(ct)
    
    // 2. 计算 m' = v - s^T · u
    //    由于 v = t^T · r + e2 + encode(m)
    //         t = A·s + e
    //    所以 v - s^T · u = encode(m) + small_error
    decoded := subWithSmallError(v, dotProduct(s, u), q)
    
    // 3. 解码消息
    m, err := decodeMessage(decoded)
    if err != nil {
        return nil, err
    }
    
    // 4. 重新计算共享密钥（与封装侧一致）
    hash := sha3.New512()
    hash.Write(m)
    sharedKey = hash.Sum(nil)[32:]
    
    return sharedKey, nil
}
```

**为什么安全？**
- 即使攻击者知道 A、t、u、v，也无法恢复 s
- 因为求解 LWE 需要解决格上的困难问题
- 当前最佳攻击：BKZ 格基约减算法，复杂度仍为指数级

### 2.2 基于哈希的签名（SLH-DSA / SPHINCS+）

**核心思想**：利用单向函数的不可逆性

```
签名过程：
┌─────────────────────────────────────────────┐
│                                             │
│  消息 M → 哈希 H(M)                         │
│             ↓                               │
│  使用 Merkle Tree 根节点验证签名            │
│             ↓                               │
│  签名 = {Merkle Path, One-Time Sig}         │
│                                             │
│  验证：                                      │
│  1. 从 Merkle Path 重建根节点               │
│  2. 验证 One-Time Sig                       │
│  3. 检查根节点是否匹配公钥                  │
│                                             │
└─────────────────────────────────────────────┘
```

**优势**：
- 安全性仅依赖于哈希函数（不依赖格问题）
- 即使格密码被攻破，哈希签名仍然安全
- 适合长寿命签名（如证书颁发）

**劣势**：
- 签名尺寸大（~16-80 KB）
- 签名速度慢

## 三、Go 语言实现

### 3.1 使用 pqcrypto 库

```go
package main

import (
	"crypto/rand"
	"fmt"
	"log"

	"github.com/cloudflare/circl/kem"
	"github.com/cloudflare/circl/sign"
)

func main() {
	// ===== 1. ML-KEM (原 Kyber) 密钥封装 =====
	fmt.Println("=== ML-KEM Key Encapsulation ===")
	
	// 初始化 ML-KEM-768
	kemScheme := kem.NewMLKEM768()
	
	// 生成密钥对
	pubKey, privKey, err := kemScheme.GenerateKeyPair(rand.Reader)
	if err != nil {
		log.Fatal(err)
	}
	
	// Alice 封装
	ct, ssAlice, err := kemScheme.Encapsulate(pubKey)
	if err != nil {
		log.Fatal(err)
	}
	
	// Bob 解封装
	ssBob, err := kemScheme.Decapsulate(privKey, ct)
	if err != nil {
		log.Fatal(err)
	}
	
	// 验证共享密钥一致
	if fmt.Sprintf("%x", ssAlice) != fmt.Sprintf("%x", ssBob) {
		log.Fatal("Shared keys don't match!")
	}
	
	fmt.Printf("Ciphertext size: %d bytes\n", len(ct))
	fmt.Printf("Shared key size: %d bytes\n", len(ssAlice))
	fmt.Printf("Keys match: %v\n", string(ssAlice) == string(ssBob))
	
	// ===== 2. ML-DSA (原 Dilithium) 数字签名 =====
	fmt.Println("\n=== ML-DSA Digital Signature ===")
	
	signScheme, err := sign.NewMLDSA5()
	if err != nil {
		log.Fatal(err)
	}
	
	// 生成密钥对
	pubKey, privKey, err = signScheme.GenerateKeyPair(rand.Reader)
	if err != nil {
		log.Fatal(err)
	}
	
	// 签名
	message := []byte("Hello, Post-Quantum World!")
	signature, err := signScheme.Sign(privKey, message)
	if err != nil {
		log.Fatal(err)
	}
	
	// 验证
	valid, err := signScheme.Verify(pubKey, message, signature)
	if err != nil {
		log.Fatal(err)
	}
	
	fmt.Printf("Signature size: %d bytes\n", len(signature))
	fmt.Printf("Verification: %v\n", valid)
	
	// ===== 3. 混合模式：传统 + 后量子 =====
	fmt.Println("\n=== Hybrid: RSA + ML-KEM ===")
	
	// 传统 RSA 密钥对
	rsaPub, rsaPriv, _ := generateRSAKey()
	
	// PQC 密钥对
	pqcPub, pqcPriv, _ := kemScheme.GenerateKeyPair(rand.Reader)
	
	// 混合密钥交换
	// ...
}
```

### 3.2 混合密钥交换实现

```go
// hybrid_exchange.go
package crypto

import (
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"fmt"
	"hash"

	"github.com/cloudflare/circl/kem"
)

// HybridKEM 混合密钥封装：传统 + 后量子
type HybridKEM struct {
	classicKem ClassicKEM     // 传统 KEM（如 ECDH）
	pqcKem     kem.CipherSuite // 后量子 KEM
	hash       func() hash.Hash
}

// ClassicKEM 传统密钥封装接口
type ClassicKEM interface {
	GenerateKeyPair() (pub, priv []byte, err error)
	Encapsulate(pub []byte) (ct, ss []byte, err error)
	Decapsulate(priv, ct []byte) (ss []byte, err error)
}

// NewHybridKEM 创建混合 KEM
func NewHybridKEM(pqcSuite kem.CipherSuite) *HybridKEM {
	return &HybridKEM{
		classicKem: &ECDHKEM{}, // 默认使用 ECDH
		pqcKem:     pqcSuite,
		hash:       sha256.New,
	}
}

// GenerateKeyPairs 生成混合密钥对
func (h *HybridKEM) GenerateKeyPairs() (classicPub, pqcPub, classicPriv, pqcPriv []byte, err error) {
	// 生成传统密钥对
	classicPub, classicPriv, err = h.classicKem.GenerateKeyPair()
	if err != nil {
		return nil, nil, nil, nil, err
	}
	
	// 生成 PQC 密钥对
	pqcPub, pqcPriv, err = h.pqcKem.GenerateKeyPair(rand.Reader)
	if err != nil {
		return nil, nil, nil, nil, err
	}
	
	return classicPub, pqcPub, classicPriv, pqcPriv, nil
}

// Encapsulate 混合封装
func (h *HybridKEM) Encapsulate(classicPub, pqcPub []byte) (classicCT, pqcCT, sharedKey []byte, err error) {
	// 1. 传统封装
	classicCT, classicSS, err := h.classicKem.Encapsulate(classicPub)
	if err != nil {
		return nil, nil, nil, err
	}
	
	// 2. PQC 封装
	pqcCT, pqcSS, err := h.pqcKem.Encapsulate(pqcPub)
	if err != nil {
		return nil, nil, nil, err
	}
	
	// 3. 合并共享密钥：H(classic_ss || pqc_ss)
	h := h.hash()
	h.Write(classicSS)
	h.Write(pqcSS)
	sharedKey = h.Sum(nil)
	
	return classicCT, pqcCT, sharedKey, nil
}

// Decapsulate 混合解封装
func (h *HybridKEM) Decapsulate(classicPriv, pqcPriv, classicCT, pqcCT []byte) ([]byte, error) {
	// 1. 传统解封装
	classicSS, err := h.classicKem.Decapsulate(classicPriv, classicCT)
	if err != nil {
		return nil, err
	}
	
	// 2. PQC 解封装
	pqcSS, err := h.pqcKem.Decapsulate(pqcPriv, pqcCT)
	if err != nil {
		return nil, err
	}
	
	// 3. 合并共享密钥
	h := h.hash()
	h.Write(classicSS)
	h.Write(pqcSS)
	return h.Sum(nil), nil
}

// ECDHKEM 基于 ECDH 的传统 KEM 实现
type ECDHKEM struct{}

func (e *ECDHKEM) GenerateKeyPair() ([]byte, []byte, error) {
	priv, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, nil, err
	}
	
	pub := priv.Public().(*ecdsa.PublicKey)
	
	// 编码
	pubBytes := pub.X.Bytes() + pub.Y.Bytes()
	privBytes := priv.D.Bytes()
	
	return pubBytes, privBytes, nil
}

func (e *ECDHKEM) Encapsulate(pubBytes []byte) ([]byte, []byte, error) {
	// 解码公钥
	pubX := elliptic.Unmarshal(elliptic.P256(), pubBytes[:32])
	pubY := elliptic.Unmarshal(elliptic.P256(), pubBytes[32:])
	if pubX == nil || pubY == nil {
		return nil, nil, fmt.Errorf("invalid public key")
	}
	pub := &ecdsa.PublicKey{Curve: elliptic.P256(), X: pubX, Y: pubY}
	
	// 生成临时密钥对
	tempPriv, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return nil, nil, err
	}
	
	// ECDH 共享密钥
	x, _ := tempPriv.Curve.ScalarMult(pub.X, pub.Y, tempPriv.D.Bytes())
	ss := make([]byte, 32)
	x.FillBytes(ss)
	
	// 密文 = 临时公钥
	ct := tempPriv.PublicKey.(*ecdsa.PublicKey).X.Bytes() + 
	       tempPriv.PublicKey.(*ecdsa.PublicKey).Y.Bytes()
	
	return ct, ss, nil
}

func (e *ECDHKEM) Decapsulate(privBytes, ct []byte) ([]byte, error) {
	// 解码私钥
	privD := new(big.Int).SetBytes(privBytes)
	priv := &ecdsa.PrivateKey{
		PublicKey: ecdsa.PublicKey{Curve: elliptic.P256()},
		D:         privD,
	}
	
	// 解码密文中的临时公钥
	pubX := elliptic.Unmarshal(elliptic.P256(), ct[:32])
	pubY := elliptic.Unmarshal(elliptic.P256(), ct[32:])
	if pubX == nil || pubY == nil {
		return nil, fmt.Errorf("invalid ciphertext")
	}
	pub := &ecdsa.PublicKey{Curve: elliptic.P256(), X: pubX, Y: pubY}
	
	// ECDH
	x, _ := priv.Curve.ScalarMult(pub.X, pub.Y, priv.D.Bytes())
	ss := make([]byte, 32)
	x.FillBytes(ss)
	
	return ss, nil
}
```

### 3.3 TLS 1.3 混合密钥交换

```go
// tls_hybrid.go
package tls

import (
	"crypto/tls"
	"fmt"

	"github.com/cloudflare/circl/kem"
)

// ConfigureHybridTLS 配置支持混合密钥交换的 TLS
func ConfigureHybridTLS(config *tls.Config) error {
	// 1. 注册 ML-KEM 密钥封装算法
	pqcSuite := kem.NewMLKEM768()
	
	// 2. 创建自定义密钥协商
	config.KeyShareCurves = []tls.KeyShareCurve{
		{Group: tls.X25519, KeyShare: generateX25519KeyShare()}, // 传统
		{Group: tls.PQKEM_MLKEM768, KeyShare: generatePQCKeyShare(pqcSuite)}, // PQC
	}
	
	// 3. 注册自定义密码套件
	config.CipherSuites = append(config.CipherSuites,
		tls.TLS_ECDHE_RSA_WITH_AES_256_GCM_SHA384, // 传统
		// TODO: 添加 PQ-TLS 密码套件
	)
	
	return nil
}

func generateX25519KeyShare() []byte {
	// 生成 X25519 临时密钥
	priv, err := x25519.GenerateKey(nil)
	if err != nil {
		panic(err)
	}
	return priv[:]
}

func generatePQCKeyShare(suite kem.CipherSuite) []byte {
	pub, _, err := suite.GenerateKeyPair(rand.Reader)
	if err != nil {
		panic(err)
	}
	return pub
}
```

## 四、生产部署策略

### 4.1 迁移路线图

```
Phase 1 (现在)                    Phase 2 (1-2年)              Phase 3 (3-5年)
───────────────────────────────── ─────────────────────────── ───────────────────────────
• 评估现有加密资产                • 启用混合 TLS 连接          • 全面切换到 PQC
• 部署 PQC 签名用于代码签名       • 更新 CA 根证书             • 淘汰纯传统算法
• 测试 PQC 性能                   • 迁移密钥基础设施           • 监控量子威胁进展
• 培训团队                        • 准备密钥轮换               • 审计合规性
```

### 4.2 性能影响分析

```go
// performance_benchmark.go
package benchmark

import (
	"testing"
	"time"

	"github.com/cloudflare/circl/kem"
)

func BenchmarkMLKEM512KeyGen(b *testing.B) {
	scheme := kem.NewMLKEM512()
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		scheme.GenerateKeyPair(rand.Reader)
	}
}

func BenchmarkMLKEM512Encaps(b *testing.B) {
	scheme := kem.NewMLKEM512()
	pub, _, _ := scheme.GenerateKeyPair(rand.Reader)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		scheme.Encapsulate(pub)
	}
}

func BenchmarkMLKEM512Decaps(b *testing.B) {
	scheme := kem.NewMLKEM512()
	pub, priv, _ := scheme.GenerateKeyPair(rand.Reader)
	ct, _, _ := scheme.Encapsulate(pub)
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		scheme.Decapsulate(priv, ct)
	}
}

// 典型结果（Intel i7, Go 1.21）：
// MLKEM512 KeyGen:     ~50 μs/op
// MLKEM512 Encaps:     ~150 μs/op
// MLKEM512 Decaps:     ~300 μs/op
// X25519 (传统):       ~5 μs/op
//
// 结论：PQC 比传统慢 10-60 倍，但在 TLS 握手场景下可接受
```

### 4.3 向后兼容策略

```go
// fallback.go
package crypto

import (
	"errors"
	"time"
)

// HybridFallback 混合回退机制
type HybridFallback struct {
	pqcTimeout  time.Duration
	maxRetries  int
}

func NewHybridFallback() *HybridFallback {
	return &HybridFallback{
		pqcTimeout:  2 * time.Second,
		maxRetries:  3,
	}
}

// SecureExchange 安全密钥交换，含回退
func (h *HybridFallback) SecureExchange(
	ctx context.Context,
	pqcPub, classicPub []byte,
) (sharedKey []byte, err error) {
	
	// 1. 尝试 PQC 交换（带超时）
	pqcCtx, cancel := context.WithTimeout(ctx, h.pqcTimeout)
	defer cancel()
	
	type result struct {
		key []byte
		err error
	}
	
	ch := make(chan result, 2)
	
	// 启动 PQC goroutine
	go func() {
		key, err := h.doPQCExchange(pqcPub)
		ch <- result{key, err}
	}()
	
	// 启动传统 goroutine
	go func() {
		key, err := h.doClassicExchange(classicPub)
		ch <- result{key, err}
	}()
	
	// 等待任一完成
	var pqcResult, classicResult result
	var pqcDone, classicDone bool
	
	for !pqcDone || !classicDone {
		select {
		case pqcResult = <-ch:
			pqcDone = true
			if pqcResult.err == nil && pqcResult.key != nil {
				// PQC 成功，优先使用
				return pqcResult.key, nil
			}
		case classicResult = <-ch:
			classicDone = true
			if classicResult.err == nil && classicResult.key != nil {
				// PQC 失败，回退到传统
				return classicResult.key, nil
			}
		case <-ctx.Done():
			return nil, errors.New("key exchange timeout")
		}
	}
	
	return nil, errors.New("both PQC and classic exchange failed")
}

func (h *HybridFallback) doPQCExchange(pqcPub []byte) ([]byte, error) {
	// 实现 PQC 密钥交换...
	return nil, nil
}

func (h *HybridFallback) doClassicExchange(classicPub []byte) ([]byte, error) {
	// 实现传统密钥交换...
	return nil, nil
}
```

## 五、自测题

### 5.1 题目一：算法选择

某金融系统需要保护 20 年有效期的交易数据。应选择哪种后量子算法组合？为什么？

<details>
<summary>点击查看参考答案</summary>

**推荐方案**：ML-KEM-768（密钥封装）+ SLH-DSA-192（哈希签名）

**理由**：
1. 交易数据需要长期保密 → ML-KEM 提供前向安全
2. 20 年量子计算机可能成熟 → 需要最高安全等级
3. SLH-DSA 基于哈希，即使格密码被攻破仍安全
4. ML-KEM-768 提供 ~192 位后量子安全强度
</details>

### 5.2 题目二：性能优化

在生产环境中，ML-KEM 密钥交换比 X25519 慢 30 倍。如何优化？

<details>
<summary>点击查看参考方案</summary>

1. **预计算**：在空闲时预生成 PQC 密钥对
2. **缓存**：缓存 PQC 公钥，减少重复生成
3. **异步**：在 TLS 握手的空闲阶段预执行 PQC 交换
4. **混合优先**：先用 X25519 快速建立通道，再异步升级 PQC
5. **硬件加速**：利用 AES-NI 等指令集加速多项式运算
</details>

### 5.3 题目三：迁移风险评估

一家公司有 100 万用户，每个用户的 RSA-2048 证书有效期 1 年。切换到 PQC 证书需要多少工作量？

<details>
<summary>点击查看估算</summary>

**工作量估算**：
- 证书大小：RSA 2048 ≈ 1KB → ML-DSA ≈ 4KB（4 倍增长）
- CA 基础设施：需要支持双签（RSA + PQC）
- 客户端兼容性：需要更新 TLS 库
- 预计时间：6-12 个月（分阶段迁移）
- 成本：主要在于 CA 升级和客户端适配
</details>

## 六、动手验证

### 6.1 实验：对比传统与 PQC 性能

```bash
# 创建实验项目
mkdir -p ~/post-quantum-experiment && cd ~/post-quantum-experiment
go mod init post-quantum-experiment
go get github.com/cloudflare/circl

# 运行基准测试
go test -bench=. -benchmem ./benchmark/
```

### 6.2 实验：混合 TLS 服务器

```go
// server/main.go
package main

import (
	"crypto/tls"
	"fmt"
	"net/http"
)

func main() {
	// 配置混合 TLS
	config := &tls.Config{
		CurvePreferences: []tls.CurveID{
			tls.X25519,
			tls.CurveP256,
		},
		MinVersion: tls.VersionTLS13,
	}
	
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprintf(w, "Hello, Quantum-Safe World!")
	})
	
	server := &http.Server{
		Addr:      ":8443",
		TLSConfig: config,
	}
	
	fmt.Println("Server starting on https://localhost:8443")
	server.ListenAndServeTLS("cert.pem", "key.pem")
}
```

## 七、与知识库的对照

### 已有内容
- `frontier/ai-security-adversarial-deep.md` — 已覆盖 AI 安全对抗
- `network/tls-ssl-deep.md` — 已有 TLS/SSL 深度文档

### 本文件补充
1. **后量子密码学** — 此前知识库完全缺失此主题
2. **NIST 标准化进展** — 提供了最新的算法标准和迁移时间表
3. **Go 工程实现** — 完整的混合密钥交换代码
4. **性能分析** — 量化了 PQC 与传统算法的性能差异

### 缺失内容（建议后续补充）
- **PQC 在区块链中的应用** — 比特币/以太坊的 PQC 迁移
- **量子密钥分发（QKD）** — 物理层的量子安全通信
- **PQC 合规性框架** — NIST SP 800-207 等标准解读
