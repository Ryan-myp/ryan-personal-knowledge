	store.SetEx("session", "abc123", 30*time.Minute)
	if v, ok := store.Get("name"); ok { fmt.Printf("name=%s\n", v) }

	ps := NewPubSub()
	ch := ps.Subscribe("news")
	ps.Publish("news", "Hello")
	fmt.Printf("Received: %s\n", <-ch)
}

---

## 自测题

### 问题 1
Redis 的 RDB 和 AOF 持久化各有什么优缺点？

<details>
<summary>查看答案</summary>

1. **RDB**: 定时快照，恢复快，数据可能丢失（最后一次快照到崩溃）
2. **AOF**: 每命令追加，数据更安全，文件更大，恢复更慢
3. **混合持久化**: RDB 快照 + AOF 增量，兼顾速度和安全性
4. **实际生产**: 推荐 AOF+混合持久化，RDB 仅做冷备

</details>

### 问题 2
Redis 的过期策略为什么用惰性删除+定期删除？

<details>
<summary>查看答案</summary>

1. **惰性删除**: 访问键时检查过期，延迟释放内存，但可能大量过期键堆积
2. **定期删除**: 周期性抽查 key space，逐步清理过期键
3. **组合策略**: 惰性删除保证实时性，定期删除防止堆积
4. **内存淘汰**: 如果内存满了，触发 LRU/LFU 淘汰策略

</details>