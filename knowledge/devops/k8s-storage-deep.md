# Kubernetes存储系统深度实现 - 资深专家

## 一、存储架构

### 1.1 PV/PVC模型

```go
// PersistentVolume
type PersistentVolume struct {
    apiVersion string
    kind       string
    metadata   metav1.ObjectMeta
    spec       PVSpec
    status     PVStatus
}

type PVSpec struct {
    Capacity       ResourceList
    AccessModes    []PersistentVolumeAccessMode
    ReclaimPolicy  PersistentVolumeReclaimPolicy
    StorageClass   string
    MountOptions   []string
    VolumeMode     *VolumeMode
    NodeAffinity   *VolumeNodeAffinity
    ClaimRef       *ObjectReference
    CSI            *CSIPersistentVolumeSource
    NFS            *NFSVolumeSource
    AWSElasticBlockStore *AWSElasticBlockStoreVolumeSource
}

// PersistentVolumeClaim
type PersistentVolumeClaim struct {
    apiVersion string
    kind       string
    metadata   metav1.ObjectMeta
    spec       PVCSpec
    status     PVCStatus
}

type PVCSpec struct {
    AccessModes      []PersistentVolumeAccessMode
    VolumeName       string
    StorageClassName *string
    Resources        ResourceRequirements
    VolumeMode       *VolumeMode
    Selector         *metav1.LabelSelector
}
```

### 1.2 StorageClass

```go
// StorageClass
type StorageClass struct {
    apiVersion string
    kind       string
    metadata   metav1.ObjectMeta
    provisioner string
    parameters map[string]string
    reclaimPolicy *PersistentVolumeReclaimPolicy
    volumeBindingMode *VolumeBindingMode
}

// 动态 Provisioner
type Provisioner interface {
    // 创建PV
    Create(pvc *v1.PersistentVolumeClaim) (*v1.PersistentVolume, error)
    
    // 删除PV
    Delete(volume *v1.PersistentVolume) error
    
    // 更新PV
    Update(oldVolume, newVolume *v1.PersistentVolume) error
}

// AWS EBS Provisioner
type EBSProvisioner struct {
    ec2      *ec2.EC2
    iamRole  string
    region   string
}

func (p *EBSProvisioner) Create(pvc *v1.PersistentVolumeClaim) (*v1.PersistentVolume, error) {
    // 1. 创建EBS卷
    volume, err := p.ec2.CreateVolume(&ec2.CreateVolumeInput{
        AvailabilityZone: aws.String(p.region + "a"),
        Size:             aws.Int64(int64(pvc.Spec.Resources.Requests.Storage().Value() / 1024 / 1024 / 1024)),
        VolumeType:       aws.String("gp3"),
    })
    if err != nil {
        return nil, err
    }
    
    // 2. 创建PV
    pv := &v1.PersistentVolume{
        ObjectMeta: metav1.ObjectMeta{
            GenerateName: "pv-",
            Labels: map[string]string{
                "storage-class": pvc.Spec.StorageClassName,
            },
        },
        Spec: v1.PVSpec{
            Capacity: v1.ResourceList{
                v1.ResourceStorage: pvc.Spec.Resources.Requests.Storage(),
            },
            AccessModes: pvc.Spec.AccessModes,
            PersistentVolumeSource: v1.PersistentVolumeSource{
                CSI: &v1.CSIPersistentVolumeSource{
                    Driver:       "ebs.csi.aws.com",
                    VolumeHandle: aws.String(*volume.VolumeId),
                },
            },
            MountOptions: []string{"noatime"},
        },
    }
    
    return pv, nil
}
```

## 二、CSI驱动

### 2.1 CSI规范

```go
// CSI Controller Service
type ControllerService.go interface {
    CreateVolume(ctx context.Context, req *csi.CreateVolumeRequest) (*csi.CreateVolumeResponse, error)
    DeleteVolume(ctx context.Context, req *csi.DeleteVolumeRequest) (*csi.DeleteVolumeResponse, error)
    ControllerPublishVolume(ctx context.Context, req *csi.ControllerPublishVolumeRequest) (*csi.ControllerPublishVolumeResponse, error)
    ControllerUnpublishVolume(ctx context.Context, req *csi.ControllerUnpublishVolumeRequest) (*csi.ControllerUnpublishVolumeResponse, error)
    ControllerGetCapabilities(ctx context.Context, req *csi.ControllerGetCapabilitiesRequest) (*csi.ControllerGetCapabilitiesResponse, error)
}

// CSI Node Service
type NodeService interface {
    NodePublishVolume(ctx context.Context, req *csi.NodePublishVolumeRequest) (*csi.NodePublishVolumeResponse, error)
    NodeUnpublishVolume(ctx context.Context, req *csi.NodeUnpublishVolumeRequest) (*csi.NodeUnpublishVolumeResponse, error)
    NodeGetInfo(ctx context.Context, req *csi.NodeGetInfoRequest) (*csi.NodeGetInfoResponse, error)
    NodeGetCapabilities(ctx context.Context, req *csi.NodeGetCapabilitiesRequest) (*csi.NodeGetCapabilitiesResponse, error)
}

// CSI实现
type CSIDriver struct {
    name    string
    version string
    nodeID  string
}

func (d *CSIDriver) CreateVolume(ctx context.Context, req *csi.CreateVolumeRequest) (*csi.CreateVolumeResponse, error) {
    params := req.GetParameters()
    size := req.GetCapacityRange().GetRequiredBytes()
    
    // 调用底层存储API
    volume, err := d.storageClient.CreateVolume(size, params)
    if err != nil {
        return nil, err
    }
    
    return &csi.CreateVolumeResponse{
        Volume: &csi.Volume{
            VolumeId:      volume.ID,
            CapacityBytes: volume.Size,
            VolumeContext: params,
        },
    }, nil
}
```

### 2.2 Pod挂载

```go
// Volume挂载器
type VolumeMounter struct {
    kubeClient kubernetes.Interface
    csiclient  *grpc.ClientConn
}

// 执行挂载
func (m *VolumeMounter) MountVolume(pod *v1.Pod, volume *v1.Volume, mountPath string) error {
    // 1. 获取PV
    pvName := volume.PersistentVolumeClaim.ClaimName
    pv, err := m.kubeClient.CoreV1().PersistentVolumes().Get(context.Background(), pvName, metav1.GetOptions{})
    if err != nil {
        return err
    }
    
    // 2. 调用CSI插件
    req := &csi.NodePublishVolumeRequest{
        VolumeId:         pv.Spec.CSI.VolumeHandle,
        TargetPath:       mountPath,
        StagingTargetPath: stagingPath,
        VolumeCapability: &mountCapability,
        ReadOnly:         false,
    }
    
    resp, err := m.csiclient.NodePublishVolume(context.Background(), req)
    if err != nil {
        return err
    }
    
    // 3. 创建挂载点
    os.MkdirAll(mountPath, 0755)
    
    return nil
}
```

## 三、存储策略

### 3.1 备份恢复

```go
// 备份控制器
type BackupController struct {
    kubeClient kubernetes.Interface
    veleroClient *velerov1api.Clientset
}

// 创建备份
func (c *BackupController) CreateBackup(namespace, name string) (*velerov1api.Backup, error) {
    backup := &velerov1api.Backup{
        ObjectMeta: metav1.ObjectMeta{
            Name:      name,
            Namespace: namespace,
        },
        Spec: velerov1api.BackupSpec{
            IncludedNamespaces: []string{namespace},
            StorageLocation:    "default",
            TTL:                metav1.Duration{Duration: 7 * 24 * time.Hour},
        },
    }
    
    return c.veleroClient.Velerov1api().Backups(namespace).Create(context.Background(), backup, metav1.CreateOptions{})
}

// 恢复备份
func (c *BackupController) RestoreBackup(namespace, backupName string) error {
    restore := &velerov1api.Restore{
        ObjectMeta: metav1.ObjectMeta{
            Name:      fmt.Sprintf("restore-%s", time.Now().Format("20060102150405")),
            Namespace: namespace,
        },
        Spec: velerov1api.RestoreSpec{
            BackupName:    backupName,
            IncludedNamespaces: []string{namespace},
        },
    }
    
    _, err := c.veleroClient.Velerov1api().Restores(namespace).Create(context.Background(), restore, metav1.CreateOptions{})
    return err
}
```

### 3.2 监控告警

```go
// 存储监控
type StorageMonitor struct {
    kubeClient kubernetes.Interface
    alerts     AlertManager
}

// 检查存储使用率
func (m *StorageMonitor) CheckCapacity(namespace string) error {
    pvcs, err := m.kubeClient.CoreV1().PersistentVolumeClaims(namespace).List(context.Background(), metav1.ListOptions{})
    if err != nil {
        return err
    }
    
    for _, pvc := range pvcs.Items {
        usage := pvc.Status.Capacity.Storage().Value()
        requested := pvc.Spec.Resources.Requests.Storage().Value()
        
        // 使用率超过80%告警
        if float64(usage)/float64(requested) > 0.8 {
            m.alerts.Send(Alert{
                Type:    Warning,
                Message: fmt.Sprintf("PVC %s/%s usage exceeding 80%%", namespace, pvc.Name),
                Metric:  "pvc_usage_percent",
                Value:   float64(usage) / float64(requested) * 100,
            })
        }
    }
    
    return nil
}
```

## 四、面试高频题

### Q1: PV和PVC有什么区别？

```
A:
- PV: 集群中的存储资源，管理员创建
- PVC: 用户对存储的请求，用户创建
- PV和PVC绑定后，用户才能使用
```

### Q2: 如何选择StorageClass？

```
A:
1. 性能需求: SSD vs HDD
2. 持久性: 本地 vs 网络
3. 备份需求: 是否需要快照
4. 成本考虑: 不同tier价格不同
```

## 五、自测题

1. 解释PV/PVC绑定流程
2. 如何实现CSI驱动？
3. 存储备份如何设计？

---

## 参考文档

- [K8s调度器深入](./k8s-scheduler-deep.md)
- [K8s网络深入](./k8s-network-deep.md)
- [GitOps工作流](../devops/gitops-workflow-deep.md)
