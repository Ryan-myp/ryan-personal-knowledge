# 安全测试深度实现 - 自动化渗透测试

> **版本**: v2.0  
> **日期**: 2026-08-13  
> **作者**: Ryan  
> **分类**: 测试/安全  
> **代码密度**: 30%

---

## 一、安全测试框架

```
┌─────────────────────────────────────────────────────────────────────┐
│                    安全测试分层架构                                   │
│                                                                     │
│  Layer 1: SAST (静态应用安全测试)                                   │
│  ┌─────────────────────────────────────────────────────┐           │
│  │  Semgrep / Gosec / ESLint Security                  │           │
│  │  扫描源码中的安全漏洞 (SQL注入/XSS/硬编码密钥)        │           │
│  └─────────────────────────────────────────────────────┘           │
│                           ↓                                         │
│  Layer 2: DAST (动态应用安全测试)                                   │
│  ┌─────────────────────────────────────────────────────┐           │
│  │  OWASP ZAP / Burp Suite / Nuclei                    │           │
│  │  对运行中的应用进行渗透测试                          │           │
│  └─────────────────────────────────────────────────────┘           │
│                           ↓                                         │
│  Layer 3: SCA (软件组成分析)                                        │
│  ┌─────────────────────────────────────────────────────┐           │
│  │  Dependabot / Snyk / Trivy                          │           │
│  │  扫描依赖库的已知漏洞 (CVE)                          │           │
│  └─────────────────────────────────────────────────────┘           │
│                           ↓                                         │
│  Layer 4: IAST (交互式应用安全测试)                                 │
│  ┌─────────────────────────────────────────────────────┐           │
│  │  Contrast / Veracode                                │           │
│  │  在运行时监控应用行为                                │           │
│  └─────────────────────────────────────────────────────┘           │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 二、Go 安全扫描

### 2.1 Gosec 集成

```go
// test/security/gosec_test.go
package security_test

import (
    "os/exec"
    "testing"
)

func TestGosec(t *testing.T) {
    cmd := exec.Command("gosec", "-fmt=json", "-out", "results.json", "./...")
    cmd.Dir = "../.."
    
    out, err := cmd.CombinedOutput()
    if err != nil {
        t.Logf("Gosec findings: %s", out)
    }
    
    // 解析结果
    var results GosecResults
    // ... 解析 JSON
}

type GosecResults struct {
    Issues []Issue `json:"issues"`
}

type Issue struct {
    Severity int    `json:"severity"`
    Confidence int  `json:"confidence"`
    RuleID   string `json:"rule_id"`
    File     string `json:"file"`
    Line     int    `json:"line"`
    Code     string `json:"code"`
}
```

### 2.2 自定义规则

```go
// test/security/custom_rules.go
package security

import (
    "go/ast"
    "go/token"
    "strings"
)

// HardcodedSecretRule 检测硬编码密钥
type HardcodedSecretRule struct{}

func (r *HardcodedSecretRule) ID() string {
    return "HARDCODED_SECRET"
}

func (r *HardcodedSecretRule) Match(node ast.Node, pass *gosec.ISSelection) {
    // 检测字符串字面量中的密钥模式
    lit, ok := node.(*ast.BasicLit)
    if !ok {
        return
    }
    
    value := lit.Value
    // 常见密钥模式
    patterns := []string{
        `API[-_]?KEY`,
        `SECRET[-_]?KEY`,
        `PASSWORD`,
        `PRIVATE[-_]?KEY`,
        `TOKEN`,
    }
    
    for _, p := range patterns {
        if strings.Contains(value, p) {
            pass.Report(ast.Range(lit.Pos(), lit.End(), r.ID(), "hardcoded secret"))
        }
    }
}
```

---

## 三、OWASP ZAP 自动化

```yaml
# zap-automation.yaml
# Docker 运行 ZAP 扫描
services:
  zap:
    image: owasp/zap2docker-weekly
    command: >
      zap-baseline.py
      -t https://target.com
      -j zap-report.json
      -r zap-report.html
      -I
    volumes:
      - ./reports:/zap/wrk
```

```bash
# 扫描命令
docker run --rm -v $(pwd)/reports:/zap/wrk \
  owasp/zap2docker-weekly \
  zap-baseline.py -t https://api.example.com -J report.json
```

---

## 四、依赖漏洞扫描

### 4.1 Trivy 集成

```go
// test/security/trivy_test.go
package security

import (
    "testing"
    "github.com/aquasecurity/trivy/pkg/types"
)

func TestTrivyScan(t *testing.T) {
    results, err := scanner.ScanImage("myapp:latest")
    if err != nil {
        t.Fatal(err)
    }
    
    for _, result := range results {
        for _, vuln := range result.Vulnerabilities {
            if vuln.Severity == "CRITICAL" || vuln.Severity == "HIGH" {
                t.Errorf("Critical vulnerability: %s (%s)", 
                    vuln.VulnerabilityID, vuln.PkgName)
            }
        }
    }
}
```

### 4.2 Dependabot 配置

```yaml
# .github/dependabot.yml
version: 2
updates:
  - package-ecosystem: "gomod"
    directory: "/"
    schedule:
      interval: "daily"
    open-pull-requests-limit: 10
    
  - package-ecosystem: "npm"
    directory: "/frontend"
    schedule:
      interval: "daily"
      
  - package-ecosystem: "docker"
    directory: "/"
    schedule:
      interval: "weekly"
```

---

## 五、安全测试报告模板

```go
// test/security/report.go
package security

import (
    "encoding/json"
    "time"
)

// SecurityReport 安全测试报告
type SecurityReport struct {
    Metadata struct {
        Scanner    string    `json:"scanner"`
        Version    string    `json:"version"`
        RunAt      time.Time `json:"run_at"`
        TargetURL  string    `json:"target_url"`
    } `json:"metadata"`
    
    Summary struct {
        Critical int `json:"critical"`
        High     int `json:"high"`
        Medium   int `json:"medium"`
        Low      int `json:"low"`
        Info     int `json:"info"`
    } `json:"summary"`
    
    Findings []Finding `json:"findings"`
}

type Finding struct {
    ID          string `json:"id"`
    Title       string `json:"title"`
    Severity    string `json:"severity"`
    URL         string `json:"url"`
    Description string `json:"description"`
    Remediation string `json:"remediation"`
    Evidence    string `json:"evidence"`
}
```

---

## 六、CI/CD 安全门禁

```yaml
# .github/workflows/security.yaml
name: Security Scan
on: [push, pull_request]

jobs:
  sast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Gosec
        run: docker run --rm -v $(pwd):/src securego/gosec ./...
      - name: Upload Results
        uses: actions/upload-artifact@v4
        with:
          name: security-report
          path: results.json
  
  dast:
    runs-on: ubuntu-latest
    steps:
      - name: Run ZAP Baseline
        run: |
          docker run -i \
            -v $(pwd)/zap-report:/zap/wrk \
            owasp/zap2docker-weekly \
            zap-baseline.py -t http://localhost:8080
  
  dependency:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Run Trivy
        uses: aquasecurity/trivy-action@master
        with:
          scan-type: 'fs'
          severity: 'CRITICAL,HIGH'
          exit-code: '1'  # 失败时拒绝合并
```

---

## 七、自测题

1. **SAST 和 DAST 的区别？**
   - SAST 静态分析代码，DAST 动态测试运行中的应用

2. **Trivy 扫描哪些层面？**
   - 容器镜像、文件系统、Kubernetes 配置

3. **如何防止依赖漏洞？**
   - Dependabot 自动更新 + 定期扫描 + 修复流程

