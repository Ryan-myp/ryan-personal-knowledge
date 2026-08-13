# etcd 生产环境实战指南

> 深入 etcd 生产部署：集群设计、Raft 共识、备份恢复。

---

## 1. 集群架构

```
Node 1 (Leader) ──▶ 处理所有写请求
     │
     ├───▶ Node 2 (Follower) 复制日志
     │
     └───▶ Node 3 (Follower) 复制日志

Raft 共识: 3 节点集群容忍 1 个故障
         5 节点集群容忍 2 个故障
```

---

## 2. 部署配置

```bash
#!/bin/bash
ETCD_NAME=$(hostname)
ETCD_INITIAL_CLUSTER="node1=http://10.0.0.1:2380,node2=http://10.0.0.2:2380,node3=http://10.0.0.3:2380"

/usr/local/bin/etcd \
  --name ${ETCD_NAME} \
  --data-dir /var/lib/etcd \
  --initial-advertise-peer-urls http://${ETCD_NAME}:2380 \
  --listen-peer-urls http://0.0.0.0:2380 \
  --advertise-client-urls http://${ETCD_NAME}:2379 \
  --listen-client-urls http://0.0.0.0:2379 \
  --initial-cluster ${ETCD_INITIAL_CLUSTER} \
  --snapshot-count=10000 \
  --auto-compaction-retention="1"
```

---

## 3. 备份恢复

```bash
# 快照备份
etcdctl snapshot save backup.db

# 快照恢复
etcdctl snapshot restore backup.db --data-dir=/var/lib/etcd-backup
```

---

## 4. 实践 Checklist
- [ ] 奇数个节点 (3/5/7)
- [ ] SSD 磁盘部署
- [ ] 配置自动压缩
- [ ] 定期备份快照

**参考**: etcd 官方文档、Kubernetes etcd 最佳实践
