# K8s存储体系 - 资深专家深度实现

## 一、存储架构

### 1.1 CSI架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Kubernetes CSI架构                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Application ──► PVC ──► Pod                                         │
│                    │                                                    │
│                    ▼                                                    │
│              VolumeAttach                                              │
│                    │                                                    │
│                    ▼                                                    │
│              Controller Service（节点级）                               │
│                    │                                                    │
│                    ▼                                                    │
│              Node Service（附件）                                        │
│                    │                                                    │
│                    ▼                                                    │
│              CSI Driver                                                │
│                    │                                                    │
│                    ▼                                                    │
│              External Storage System                                  │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 CSI核心组件

```go
// CSI驱动程序接口
type CSIDriver interface {
    // 卷操作
    CreateVolume(req *CreateVolumeRequest) (*CreateVolumeResponse, error)
    DeleteVolume(req *DeleteVolumeRequest) (*DeleteVolumeResponse, error)
    ControllerPublishVolume(req *ControllerPublishVolumeRequest) (*ControllerPublishVolumeResponse, error)
    ControllerUnpublishVolume(req *ControllerUnpublishVolumeRequest) (*ControllerUnpublishVolumeResponse, error)
    
    // 节点操作
    NodePublishVolume(req *NodePublishVolumeRequest) (*NodePublishVolumeResponse, error)
    NodeUnpublishVolume(req *NodeUnpublishVolumeRequest) (*NodeUnpublishVolumeResponse, error)
    
    // 能力查询
    GetPluginInfo() (*GetPluginInfoResponse, error)
    GetCapabilities() (*GetPluginCapabilitiesResponse, error)
}

// 存储类定义
type StorageClass struct {
    Name           string
    Provisioner    string
    Parameters     map[string]string
    ReclaimPolicy  ReclaimPolicy
    VolumeBinding  VolumeBindingMode
    AllowVolumeExpansion bool
}
```

## 二、PV/PVC管理

### 2.1 生命周期管理

```go
type PersistentVolume struct {
    Spec   PVSpec
    Status PVStatus
}

type PVSpec struct {
    Capacity         ResourceList
    AccessModes      []AccessMode
    PersistentVolumeReclaimPolicy ReclaimPolicy
    StorageClassName string
    MountOptions     []string
    VolumeMode       *VolumeMode
    Source           PVSource
}

type PVStatus struct {
    Phase      VolumePhase
    Message    string
    Reason     string
}

// 生命周期状态转换
type VolumePhase string

const (
    VolumePending   VolumePhase = "Pending"
    VolumeAvailable VolumePhase = "Available"
    VolumeBound     VolumePhase = "Bound"
    VolumeReleased  VolumePhase = "Released"
    VolumeFailed    VolumePhase = "Failed"
)
```

### 2.2 动态供给

```go
type Provisioner interface {
    Provision(options ProvisionOptions) (*ProvisionedVolume, error)
    Delete(volume *ProvisionedVolume) error
}

type ProvisionOptions struct {
    StorageClass *StorageClass
    PVName       string
    Capacity     ResourceQuantity
    Parameters   map[string]string
}

type ProvisionedVolume struct {
    PV *PersistentVolume
}

// 实现动态供给
func (p *NFSProvisioner) Provision(options ProvisionOptions) (*ProvisionedVolume, error) {
    // 1. 创建NFS目录
    path := p.createNFSDirectory(options.PVName)
    
    // 2. 创建PV对象
    pv := &PersistentVolume{
        ObjectMeta: metav1.ObjectMeta{
            Name: options.PVName,
        },
        Spec: PVSpec{
            Capacity: options.Capacity,
            AccessModes: []v1.PersistentVolumeAccessMode{
                v1.ReadWriteOnce,
            },
            PersistentVolumeReclaimPolicy: v1.PersistentVolumeReclaimRetain,
            StorageClassName: options.StorageClass.Name,
            NFS: &v1.NFSVolumeSource{
                Server: p.server,
                Path:   path,
            },
        },
    }
    
    return &ProvisionedVolume{PV: pv}, nil
}
```

## 三、存储插件实现

### 3.1 自定义CSI驱动

```go
type MyCSIControllerServer struct {
    driver *MyCSIDriver
    volumeLocks *volumeLocks
}

func (c *MyCSIControllerServer) CreateVolume(ctx context.Context, req *csi.CreateVolumeRequest) (*csi.CreateVolumeResponse, error) {
    name := req.GetName()
    
    // 验证容量范围
    capacity := req.GetCapacityRange().GetRequiredBytes()
    if capacity < minCapacity || capacity > maxCapacity {
        return nil, status.Errorf(codes.InvalidArgument, "Invalid capacity")
    }
    
    // 生成唯一ID
    volID := generateVolumeID(name)
    
    // 创建存储卷
    vol, err := c.driver.createVolume(volID, capacity, req.GetParameters())
    if err != nil {
        return nil, err
    }
    
    // 返回响应
    return &csi.CreateVolumeResponse{
        Volume: &csi.Volume{
            VolumeId:      volID,
            CapacityBytes: capacity,
            AccessPoints:  vol.GetAccessPoints(),
        },
    }, nil
}
```

### 3.2 节点服务实现

```go
type MyCSINodeServer struct {
    driver *MyCSIDriver
    mount  *mount.SafeFormatAndMount
}

func (n *MyCSINodeServer) NodePublishVolume(ctx context.Context, req *csi.NodePublishVolumeRequest) (*csi.NodePublishVolumeResponse, error) {
    volumeID := req.GetVolumeId()
    targetPath := req.GetTargetPath()
    
    // 检查目标路径
    exists, err := n.mount.PathExists(targetPath)
    if err != nil {
        return nil, err
    }
    if !exists {
        if err := os.MkdirAll(targetPath, 0750); err != nil {
            return nil, err
        }
    }
    
    // 获取卷信息
    vol, err := n.driver.getVolume(volumeID)
    if err != nil {
        return nil, err
    }
    
    // 挂载卷
    source := vol.GetSource()
    fstype := req.GetVolumeCapability().GetMount().GetFsType()
    
    options := extractMountOptions(req.GetVolumeCapability().GetMount())
    
    if err := n.mount.Mount(source, targetPath, fstype, options); err != nil {
        return nil, status.Errorf(codes.Internal, "Failed to mount: %v", err)
    }
    
    return &csi.NodePublishVolumeResponse{}, nil
}
```

## 四、存储优化策略

### 4.1 性能调优

```yaml
# StorageClass配置
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
provisioner: kubernetes.io/aws-ebs
parameters:
  type: gp3
  iopsPerGB: "100"
  throughput: "500"
  encrypted: "true"
reclaimPolicy: Delete
volumeBindingMode: WaitForFirstConsumer
allowVolumeExpansion: true
```

### 4.2 容量规划

```go
type CapacityPlanner struct {
    metrics *MetricsCollector
    alerts  *AlertManager
}

func (p *CapacityPlanner) plan() (*CapacityPlan, error) {
    // 收集指标
    currentUsage := p.metrics.getCurrentUsage()
    growthRate := p.metrics.calculateGrowthRate()
    
    // 预测未来需求
    projected := currentUsage * (1 + growthRate)
    
    // 计算推荐容量
    recommended := projected * 1.2 // 20% buffer
    
    // 检查告警阈值
    if currentUsage > recommended * 0.8 {
        p.alerts.trigger("CapacityWarning", currentUsage, recommended)
    }
    
    return &CapacityPlan{
        Current:     currentUsage,
        Projected:   projected,
        Recommended: recommended,
    }, nil
}
```

## 五、数据备份恢复

### 5.1 Velero备份

```yaml
# Backup配置
apiVersion: velero.io/v1
kind: Backup
metadata:
  name: daily-backup
  namespace: velero
spec:
  includedNamespaces:
    - production
    - staging
  excludedNamespaces:
    - kube-system
  includeClusterResources: true
  storageLocation: default
  ttl: 720h
  snapshotVolumes: true
  volumeSnapshotLocations:
    - aws-default
```

### 5.2 恢复流程

```go
type RestoreManager struct {
    veleroClient *veleroclientset.Velerov1client
    scheduler    *Scheduler
}

func (m *RestoreManager) restore(backupName string, targetNamespace string) error {
    // 创建恢复请求
    restore := &velerov1.Restore{
        ObjectMeta: metav1.ObjectMeta{
            GenerateName: "restore-",
        },
        Spec: velerov1.RestoreSpec{
            BackupRef: &corev1.ObjectReference{
                Name: backupName,
            },
            IncludedNamespaces: []string{targetNamespace},
            ExistingResourcePolicy: "update",
            RestorePVs: true,
        },
    }
    
    // 执行恢复
    result, err := m.veleroClient.Velerov1().Restores(veleroNamespace).Create(context.TODO(), restore, metav1.CreateOptions{})
    if err != nil {
        return err
    }
    
    // 等待完成
    return m.scheduler.waitForRestore(result.Name)
}
```

## 六、面试高频题

### Q1: PV和PVC的区别？

```
A:
• PV: 集群中的存储资源
• PVC: 用户对存储的请求
• 关系: PVC绑定到PV
```

### Q2: StorageClass的作用？

```
A:
1. 动态供给存储
2. 定义存储类型
3. 配置参数（IOPS、吞吐量等）
4. 控制回收策略
```

### Q3: 如何实现存储高可用？

```
A:
1. 多副本部署
2. 跨可用区分布
3. 定期备份
4. 故障自动迁移
```

## 七、自测题

1. 解释CSI架构
2. 如何实现动态供给？
3. 存储容量如何规划？

---

## 参考文档

- [K8s存储文档](https://kubernetes.io/docs/concepts/storage/)
- [CSI规范](https://github.com/container-storage-interface/spec)

---

## 交叉引用

### 相关文档
- [K8s调度器深入](./k8s-scheduler-deep.md) - 调度算法
- [K8s网络插件](./k8s-network-plugin-deep.md) - 网络存储
- [GitOps工作流](./gitops-workflow-deep.md) - 配置管理
- [容器安全](./containers-security-deep.md) - 安全存储

### 引用链
```
k8s-storage-deep.md
├── CSI驱动 → k8s-scheduler-deep.md
├── 网络存储 → k8s-network-plugin-deep.md
├── 配置管理 → gitops-workflow-deep.md
└── 安全策略 → containers-security-deep.md
```
