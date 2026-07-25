
---

## Go 代码实战：GitOps 部署工具

### 1. K8s Manifest 生成器

```go
package k8s

import (
	"fmt"
	"strings"
)

// Deployment K8s Deployment 定义
type Deployment struct {
	Name        string
	Namespace   string
	Replicas    int
	Image       string
	Port        int
	Resources   Resources
	Env         map[string]string
}

type Resources struct {
	CPURequest    string
	CPULimit      string
	MemRequest    string
	MemLimit      string
}

func (d *Deployment) ToYAML() string {
	var sb strings.Builder
	
	sb.WriteString(fmt.Sprintf("apiVersion: apps/v1\n"))
	sb.WriteString(fmt.Sprintf("kind: Deployment\n"))
	sb.WriteString(fmt.Sprintf("metadata:\n"))
	sb.WriteString(fmt.Sprintf("  name: %s\n", d.Name))
	sb.WriteString(fmt.Sprintf("  namespace: %s\n", d.Namespace))
	sb.WriteString(fmt.Sprintf("spec:\n"))
	sb.WriteString(fmt.Sprintf("  replicas: %d\n", d.Replicas))
	sb.WriteString(fmt.Sprintf("  selector:\n"))
	sb.WriteString(fmt.Sprintf("    matchLabels:\n"))
	sb.WriteString(fmt.Sprintf("      app: %s\n", d.Name))
	sb.WriteString(fmt.Sprintf("  template:\n"))
	sb.WriteString(fmt.Sprintf("    metadata:\n"))
	sb.WriteString(fmt.Sprintf("      labels:\n"))
	sb.WriteString(fmt.Sprintf("        app: %s\n", d.Name))
	sb.WriteString(fmt.Sprintf("    spec:\n"))
	sb.WriteString(fmt.Sprintf("      containers:\n"))
	sb.WriteString(fmt.Sprintf("      - name: %s\n", d.Name))
	sb.WriteString(fmt.Sprintf("        image: %s\n", d.Image))
	sb.WriteString(fmt.Sprintf("        ports:\n"))
	sb.WriteString(fmt.Sprintf("        - containerPort: %d\n", d.Port))
	sb.WriteString(fmt.Sprintf("        resources:\n"))
	sb.WriteString(fmt.Sprintf("          requests:\n"))
	sb.WriteString(fmt.Sprintf("            cpu: %s\n", d.Resources.CPURequest))
	sb.WriteString(fmt.Sprintf("            memory: %s\n", d.Resources.MemRequest))
	sb.WriteString(fmt.Sprintf("          limits:\n"))
	sb.WriteString(fmt.Sprintf("            cpu: %s\n", d.Resources.CPULimit))
	sb.WriteString(fmt.Sprintf("            memory: %s\n", d.Resources.MemLimit))
	
	if len(d.Env) > 0 {
		sb.WriteString(fmt.Sprintf("        env:\n"))
		for k, v := range d.Env {
			sb.WriteString(fmt.Sprintf("        - name: %s\n", k))
			sb.WriteString(fmt.Sprintf("          value: \"%s\"\n", v))
		}
	}
	
	return sb.String()
}

// HPA 水平自动扩缩容
type HPA struct {
	DeploymentName string
	MinReplicas    int
	MaxReplicas    int
	CPUTarget      int
}

func (h *HPA) ToYAML() string {
	return fmt.Sprintf(`apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: %s-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: %s
  minReplicas: %d
  maxReplicas: %d
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: %d
`, h.DeploymentName, h.DeploymentName, h.MinReplicas, h.MaxReplicas, h.CPUTarget)
}
```

### 2. GitOps Sync Controller

```go
package gitops

import (
	"context"
	"os/exec"
	"sync"
	"time"
)

// SyncController GitOps 同步控制器
type SyncController struct {
	repoURL     string
	localPath   string
	branch      string
	syncInterval time.Duration
	mu          sync.Mutex
	lastSync    time.Time
}

func NewSyncController(repoURL, localPath, branch string, interval time.Duration) *SyncController {
	return &SyncController{
		repoURL:      repoURL,
		localPath:    localPath,
		branch:       branch,
		syncInterval: interval,
	}
}

func (c *SyncController) Start(ctx context.Context) error {
	// 克隆仓库
	cmd := exec.Command("git", "clone", "--depth", "1", c.repoURL, c.localPath)
	if err := cmd.Run(); err != nil {
		return err
	}
	
	// 定期同步
	ticker := time.NewTicker(c.syncInterval)
	defer ticker.Stop()
	
	for {
		select {
		case <-ticker.C:
			c.sync(ctx)
		case <-ctx.Done():
			return ctx.Err()
		}
	}
}

func (c *SyncController) sync(ctx context.Context) {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	cmd := exec.CommandContext(ctx, "git", "-C", c.localPath, "pull", "origin", c.branch)
	output, err := cmd.CombinedOutput()
	if err != nil {
		// 同步失败，记录日志
		fmt.Printf("sync failed: %v, output: %s\n", err, output)
		return
	}
	
	c.lastSync = time.Now()
	fmt.Println("synced successfully")
}

// Status 同步状态
func (c *SyncController) Status() string {
	c.mu.Lock()
	defer c.mu.Unlock()
	
	if c.lastSync.IsZero() {
		return "never synced"
	}
	
	age := time.Since(c.lastSync)
	if age > 5*time.Minute {
		return fmt.Sprintf("stale (last sync: %s ago)", age.Round(time.Second))
	}
	return fmt.Sprintf("ok (last sync: %s ago)", age.Round(time.Second))
}
```

### 自测题

<details>
<summary>Q1: GitOps 相比传统 CI/CD Pipeline 有什么核心优势？</summary>

**答案**：

| 特性 | CI/CD Pipeline | GitOps |
|------|---------------|--------|
| 状态管理 | 中心化（Jenkins等） | **声明式（Git是source of truth）** |
| 回滚 | 手动操作 | `git revert` + 自动同步 |
| 审计 | 需要额外工具 | **Git commit history** |
| 多环境 | 复杂配置 | **Git branch per environment** |

广告平台推荐 GitOps——K8s 原生支持，ArgoCD 自动同步，零运维。

</details>

<details>
<summary>Q2: HPA 的 CPU Target 设为 70% 还是 80%？为什么？</summary>

**答案**：

**70% vs 80%**：
- 70% → 更早扩容，延迟更低，但资源利用率低
- 80% → 资源利用率高，但可能短暂过载

**广告平台推荐 70%**：因为竞价请求延迟敏感（<50ms），宁可多用一些机器也不能增加延迟。

</details>

<details>
<summary>Q3: Git pull --depth 1 在 GitOps 中有什么风险？</summary>

**答案**：

**浅克隆的风险**：
1. 无法回滚到之前的版本（没有历史）
2. 标签/分支引用不完整
3. 某些 git 操作（如 bisect）不可用

**生产方案**：用 `--depth 10` 或完整克隆 + 定期 fetch。ArgoCD 默认用完整克隆。

</details>
