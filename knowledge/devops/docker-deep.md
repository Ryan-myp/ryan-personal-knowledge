# Docker容器化深度实现 - 资深专家

## 一、容器运行时架构

### 1.1 containerd-shim实现

```go
// containerd-shim 核心接口
type shim interface {
    Start(ctx context.Context, r *taskspb.StartRequest) (*emptypb.Empty, error)
    DeleteTask(ctx context.Context, r *taskspb.DeleteTaskRequest) (*taskspb.DeleteTaskResponse, error)
    Wait(*taskspb.WaitRequest, taskpb.Task_WaitServer) error
    Exec(ctx context.Context, r *taskspb.ExecRequest) (*emptypb.Empty, error)
    ResizePty(ctx context.Context, r *tasks.ResizePtyRequest) (*emptypb.Empty, error)
}

// shim实现核心逻辑
type Shim struct {
    bundle      string
    namespace   string
    containerID string
    pid         int
    stdout      io.Writer
    stderr      io.Writer
    stdin       io.Reader
}

func (s *Shim) Start(ctx context.Context, r *taskspb.StartRequest) (*emptypb.Empty, error) {
    // 1. 创建执行环境
    env := s.createEnv()
    
    // 2. 启动进程
    cmd := exec.CommandContext(ctx, r.ExecID, r.Args...)
    cmd.Env = env
    cmd.Stdout = s.stdout
    cmd.Stderr = s.stderr
    cmd.Stdin = s.stdin
    
    if err := cmd.Start(); err != nil {
        return nil, err
    }
    
    s.pid = cmd.Process.Pid
    return &emptypb.Empty{}, nil
}

// OCI Runtime Spec完整结构
type Spec struct {
    Version  string     `json:"ociVersion"`
    Platform Platform   `json:"platform"`
    Root     Root       `json:"root"`
    Process  Process    `json:"process"`
    Linux    Linux      `json:"linux"`
    Unix     Unix       `json:"unix"`
    Hooks    Hooks      `json:"hooks"`
    Mounts   []Mount    `json:"mounts"`
    Annotations map[string]string `json:"annotations"`
    ConfigPath string                     `json:"configPath"`
}

type Process struct {
    User             User            `json:"user"`
    Args             []string        `json:"args"`
    Env              []string        `json:"env"`
    Cwd              string          `json:"cwd"`
    Capabilities     Capabilities    `json:"capabilities"`
    NoNewPrivileges  bool            `json:"noNewPrivileges"`
    ApparmorProfile  string          `json:"apparmorProfile"`
    OOMScoreAdj      *int            `json:"oomScoreAdj"`
}

type Linux struct {
    UIDMappings []LinuxIDMapping `json:"uidMappings"`
    GIDMappings []LinuxIDMapping `json:"gidMappings"`
    CgroupsPath string           `json:"cgroupsPath"`
    Resources   *LinuxResources  `json:"resources"`
    Namespaces  []LinuxNamespace `json:"namespaces"`
    Seccomp     *Seccomp         `json:"seccomp"`
}
```

### 1.2 runc实现原理

```go
// runc初始化流程
func init() {
    // 1. 创建命名空间
    setupNamespaces()
    
    // 2. 设置cgroup
    setupCgroups()
    
    // 3. 挂载根文件系统
    mountRootfs()
    
    // 4. 执行容器进程
    executeContainerProcess()
}

// 命名空间隔离实现
func setupNamespaces() {
    namespaces := []struct {
        name  string
        flag  int
        path  string
    }{
        {"mount", CLONE_NEWNS, "/proc/self/ns/mnt"},
        {"pid", CLONE_NEWPID, "/proc/self/ns/pid"},
        {"network", CLONE_NEWNET, "/proc/self/ns/net"},
        {"ipc", CLONE_NEWIPC, "/proc/self/ns/ipc"},
        {"uts", CLONE_NEWUTS, "/proc/self/ns/uts"},
        {"user", CLONE_NEWUSER, "/proc/self/ns/user"},
    }
    
    for _, ns := range namespaces {
        if err := unix.Unshare(ns.flag); err != nil {
            log.Fatalf("unshare %s: %v", ns.name, err)
        }
    }
}

// cgroup配置
func setupCgroups() error {
    cgroupPath := "/docker/containers/" + containerID
    
    // 创建cgroup目录
    if err := os.MkdirAll(cgroupPath, 0755); err != nil {
        return err
    }
    
    // 写入cgroup配置
    cgroupConfigs := map[string]string{
        "memory.limit_in_bytes": "536870912",  // 512MB
        "memory.max_usage_in_bytes": "536870912",
        "cpu.shares": "1024",
        "pids.max": "100",
    }
    
    for key, value := range cgroupConfigs {
        if err := os.WriteFile(path.Join(cgroupPath, key), []byte(value), 0644); err != nil {
            return err
        }
    }
    
    return nil
}
```

## 二、镜像分层与存储驱动

### 2.1 联合文件系统

```
┌─────────────────────────────────────────────────────┐
│              Union Mount (合并视图)                  │
├─────────────────────────────────────────────────────┤
│  Layer 3: Container RW Layer (可读写)               │  ← 容器内修改
│  ┌─────────────────────────────────────────────────┐│
│  │  /etc/config.yml (新增/修改)                    ││
│  │  /var/log/app.log (新增)                        ││
│  └─────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────┤
│  Layer 2: Application Layer (只读)                  │  ← 应用层
│  ┌─────────────────────────────────────────────────┐│
│  │  /app/*.so                                      ││
│  │  /usr/bin/*                                     ││
│  └─────────────────────────────────────────────────┘│
├─────────────────────────────────────────────────────┤
│  Layer 1: Base Image Layer (只读)                   │  ← 基础镜像
│  ┌─────────────────────────────────────────────────┐│
│  │  /bin, /sbin, /lib, /usr                        ││
│  └─────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────┘
```

```go
// OverlayFS实现
type OverlayFS struct {
    workDir  string
    upperDir string
    lowerDirs []string
    mergeDir string
}

func (fs *OverlayFS) Mount(target string) error {
    options := fmt.Sprintf(
        "lowerdir=%s,upperdir=%s,workdir=%s",
        strings.Join(fs.lowerDirs, ":"),
        fs.upperDir,
        fs.workDir,
    )
    
    return unix.Mount("overlay", target, "overlay", 0, options)
}

// 镜像层解析
type Layer struct {
    ID          string
    Parent      string
    DiffID      digest.Digest
    Size        int64
    MediaType   string
    Content     io.ReadSeeker
}

func (l *Layer) Apply(rootfs string) error {
    // 1. 创建层目录
    layerDir := path.Join(rootfs, l.ID)
    if err := os.MkdirAll(layerDir, 0755); err != nil {
        return err
    }
    
    // 2. 解压diff
    diff, err := l.Content.Seek(0, io.SeekStart)
    if err != nil {
        return err
    }
    
    return untar(diff, layerDir, &tar.Options{
        PreserveUIDGID: true,
    })
}
```

### 2.2 存储驱动对比

| 驱动 | 特点 | 适用场景 | 性能 |
|------|------|----------|------|
| overlay2 | 内核原生支持 | 生产环境首选 | ⭐⭐⭐⭐⭐ |
| vfs | 简单可靠 | 测试环境 | ⭐⭐ |
| btrfs | 快照支持 | 特殊需求 | ⭐⭐⭐⭐ |
| zfs | 高级功能 | 企业级 | ⭐⭐⭐⭐ |

```go
// 存储驱动接口
type StorageDriver interface {
    Name() string
    Create(id, parent string, mountLabel string, storageOpts map[string]string) error
    Path(id string) string
    Stat(id string) (os.FileInfo, error)
    Exists(id string) bool
    Remove(id string) error
    Get(id, mountLabel string) (string, error)
    Put(id string) error
    ChangedPaths(id string) (ChangedPaths, error)
}

// Overlay2实现核心方法
func (d *Overlay2Driver) Get(id, mountLabel string) (string, error) {
    // 获取层路径
    dir, err := d.dir(id)
    if err != nil {
        return "", err
    }
    
    // 检查是否已挂载
    if count := d.refcount.Get(dir); count > 0 {
        d.refcount.Add(dir, 1)
        return dir, nil
    }
    
    // 创建挂载点
    workDir := filepath.Join(dir, "work")
    upperDir := filepath.Join(dir, "upper")
    lowerDir := d.getLowerDirs(id)
    
    mergedDir := filepath.Join(dir, "merged")
    if err := os.MkdirAll(mergedDir, 0755); err != nil {
        return "", err
    }
    
    // 挂载overlay
    options := fmt.Sprintf(
        "lowerdir=%s,upperdir=%s,workdir=%s",
        lowerDir, upperDir, workDir,
    )
    
    if err := unix.Mount("overlay", mergedDir, "overlay", 0, options); err != nil {
        return "", err
    }
    
    d.refcount.Add(dir, 1)
    return mergedDir, nil
}
```

## 三、网络模式实现

### 3.1 网络模型对比

```go
type NetworkMode string

const (
    BridgeNetwork  NetworkMode = "bridge"
    HostNetwork    NetworkMode = "host"
    NoneNetwork    NetworkMode = "none"
    ContainerNet   NetworkMode = "container"
    OverlayNetwork NetworkMode = "overlay"
    MacvlanNetwork NetworkMode = "macvlan"
)

// 网络配置
type NetworkConfig struct {
    Name         string
    Driver       string
    IPAM         IPAMConfig
    Options      map[string]string
    Containers   map[string]*Endpoint
    Internal     bool
    EnableIPv6   bool
}

type IPAMConfig struct {
    Driver  string
    Config  []IPAMPool
}

type IPAMPool struct {
    Subnet     string
    Gateway    string
    IPRange    string
    AuxAddress map[string]string
}
```

### 3.2 Bridge网络实现

```go
// Bridge网络创建
func createBridgeNetwork(config *NetworkConfig) error {
    // 1. 创建网桥
    bridgeName := config.Name
    if err := createBridge(bridgeName); err != nil {
        return err
    }
    
    // 2. 配置IP
    if config.IPAM != nil && len(config.IPAM.Config) > 0 {
        pool := config.IPAM.Config[0]
        if err := configureBridgeIP(bridgeName, pool.Subnet, pool.Gateway); err != nil {
            return err
        }
    }
    
    // 3. 设置iptables规则
    if err := setupIptables(bridgeName); err != nil {
        return err
    }
    
    return nil
}

// 创建网桥
func createBridge(name string) error {
    // 使用netlink创建网桥
    link := &netlink.Bridge{
        LinkAttrs: netlink.LinkAttrs{
            Name: name,
        },
    }
    
    if err := netlink.LinkAdd(link); err != nil {
        return err
    }
    
    return netlink.LinkSetUp(link)
}

// 配置IP地址
func configureBridgeIP(bridgeName, subnet, gateway string) error {
    link, err := netlink.LinkByName(bridgeName)
    if err != nil {
        return err
    }
    
    addr := &netlink.Addr{
        IPNet: parseCIDR(subnet),
    }
    
    return netlink.AddrAdd(link, addr)
}

// iptables规则
func setupIptables(bridgeName string) error {
    // MASQUERADE规则
    cmd := exec.Command("iptables", "-t", "nat", "-A", "POSTROUTING",
        "-s", "172.17.0.0/16", "-j", "MASQUERADE")
    if err := cmd.Run(); err != nil {
        return err
    }
    
    // FORWARD规则
    cmd = exec.Command("iptables", "-I", "FORWARD", "-r", bridgeName+"-", "-j", "ACCEPT")
    return cmd.Run()
}
```

### 3.3 Container共享网络

```go
// 容器共享网络
func connectContainerToNetwork(containerID, networkID string) error {
    // 1. 获取网络信息
    network, err := getNetwork(networkID)
    if err != nil {
        return err
    }
    
    // 2. 创建veth pair
    hostVeth := generateRandomName("veth", 12)
    containerVeth := generateRandomName("eth", 9)
    
    veth := &netlink.Veth{
        LinkAttrs: netlink.LinkAttrs{
            Name: hostVeth,
        },
        PeerName: containerVeth,
    }
    
    if err := netlink.LinkAdd(veth); err != nil {
        return err
    }
    
    // 3. 连接到网桥
    bridge, _ := netlink.LinkByName(network.Name)
    if err := netlink.LinkSetMaster(veth.LinkAttrs, bridge); err != nil {
        return err
    }
    
    // 4. 移动到容器网络命名空间
    ns, err := ns.NewNS(containerID)
    if err != nil {
        return err
    }
    defer ns.Close()
    
    return ns.Do(func(_ ns.NetNS) error {
        link, err := netlink.LinkByName(containerVeth)
        if err != nil {
            return err
        }
        return netlink.LinkSetUp(link)
    })
}
```

## 四、多阶段构建优化

### 4.1 优化策略

```dockerfile
# 第一阶段：编译
FROM golang:1.21-alpine AS builder

# 安装构建依赖
RUN apk add --no-cache git ca-certificates

# 设置工作目录
WORKDIR /app

# 复制go.mod和go.sum
COPY go.mod go.sum ./
RUN go mod download

# 复制源代码
COPY . .

# 编译二进制文件
RUN CGO_ENABLED=0 GOOS=linux go build -ldflags="-w -s" -o /app/server .

# 第二阶段：运行
FROM alpine:3.18

# 安装运行时依赖
RUN apk add --no-cache ca-certificates tzdata

# 从builder阶段复制二进制
COPY --from=builder /app/server /app/server

# 设置非root用户
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

USER appuser

# 暴露端口
EXPOSE 8080

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/health || exit 1

# 启动命令
CMD ["/app/server"]
```

### 4.2 镜像大小优化

```dockerfile
# 基础镜像选择对比
# Alpine: ~5MB (推荐)
FROM alpine:3.18

# Distroless: ~2MB (更安全)
FROM gcr.io/distroless/base-debian12

# Slim版本: ~40MB
FROM ubuntu:22.04-slim

# 完整版本: ~77MB (不推荐)
FROM ubuntu:22.04
```

```go
// 镜像大小分析工具
type ImageAnalyzer struct {
    image    ocispec.Image
    layers   []ocispec.Descriptor
}

func (a *ImageAnalyzer) Analyze() *ImageReport {
    report := &ImageReport{}
    
    for _, layer := range a.layers {
        size := layer.Size
        diffID := layer.Digest
        
        report.TotalSize += size
        report.LayerCount++
        
        // 分析层内容
        layerReport := a.analyzeLayer(diffID)
        report.Layers = append(report.Layers, layerReport)
    }
    
    // 找出最大层
    sort.Slice(report.Layers, func(i, j int) bool {
        return report.Layers[i].Size > report.Layers[j].Size
    })
    
    return report
}

func (a *ImageAnalyzer) analyzeLayer(diffID digest.Digest) *LayerReport {
    // 使用binwalk分析层内容
    content := a.getImageLayerContent(diffID)
    
    report := &LayerReport{
        DiffID: diffID.String(),
        Size:   len(content),
    }
    
    // 统计文件类型
    files := a.extractFiles(content)
    report.FileCount = len(files)
    report.TopFiles = a.getTopFiles(files)
    
    return report
}
```

## 五、安全最佳实践

### 5.1 安全加固

```dockerfile
# 安全配置
FROM alpine:3.18

# 不运行root用户
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

USER appuser

# 只读根文件系统
# RUN chmod 555 /

# 不暴露敏感端口
EXPOSE 8080

# 禁用历史命令
ENV HISTSIZE=0
ENV HISTFILE=/dev/null

# 使用seccomp配置文件
# docker run --security-opt seccomp=path/to/profile.json
```

### 5.2 安全扫描

```go
// 镜像安全扫描
type SecurityScanner struct {
    image    ocispec.Image
    scanner  *trivy.Scanner
}

func (s *SecurityScanner) Scan() (*SecurityReport, error) {
    report := &SecurityReport{}
    
    // 1. CVE扫描
    cveResults, err := s.scanner.ScanCVE(s.image)
    if err != nil {
        return nil, err
    }
    report.CVEs = cveResults
    
    // 2. 配置检查
    configResults, err := s.scanner.CheckConfig(s.image)
    if err != nil {
        return nil, err
    }
    report.ConfigIssues = configResults
    
    // 3. 敏感信息检测
    secretResults, err := s.scanner.FindSecrets(s.image)
    if err != nil {
        return nil, err
    }
    report.Secrets = secretResults
    
    return report, nil
}

// 安全报告
type SecurityReport struct {
    CVEs          []CVEFinding
    ConfigIssues  []ConfigIssue
    Secrets       []SecretFinding
    Severity      string
    Score         int
}
```

## 六、面试高频题

### Q1: Docker和K8s的区别？

```
Docker:
• 容器运行时，管理单个容器
• 提供镜像、容器、网络、卷等基础功能
• 适合开发测试环境

K8s:
• 容器编排平台，管理容器集群
• 提供自动扩缩容、服务发现、负载均衡等高级功能
• 适合生产环境

关系: K8s使用Docker/containerd作为运行时
```

### Q2: 如何优化镜像大小？

```
1. 使用多阶段构建
   - 编译和运行分离
   - 只复制需要的文件

2. 选择小基础镜像
   - Alpine (~5MB)
   - Distroless (~2MB)

3. 减少层数
   - 合并RUN指令
   - 利用缓存

4. 清理缓存
   - 删除apt/yum缓存
   - 删除构建临时文件
```

### Q3: 解释容器隔离原理

```
Linux Namespaces:
• PID: 进程隔离
• NET: 网络隔离
• MNT: 挂载点隔离
• UTS: 主机名隔离
• IPC: 进程通信隔离
• USER: 用户隔离

cgroups:
• cpu: CPU资源限制
• memory: 内存限制
• pids: 进程数量限制
• devices: 设备访问控制
```

## 七、自测题

1. 解释OCI Spec结构
2. 如何实现多阶段构建？
3. Bridge网络工作原理？
4. 如何加固Docker安全？
5. 存储驱动有哪些选择？

---

## 参考文档

- [Docker官方文档](https://docs.docker.com/)
- [containerd源码](https://github.com/containerd/containerd)
- [runc源码](https://github.com/opencontainers/runc)
- [OCI Runtime Spec](https://github.com/opencontainers/runtime-spec)
