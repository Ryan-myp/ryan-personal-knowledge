# ClickHouse内核 - 资深专家深度实现

## 一、列式存储

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ClickHouse列存架构                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Row (行式存储 - 写入)                                                  │
│   └── [id: 1, name: "Alice", age: 25, city: "Beijing"]                  │
│                                                                         →
│   Column (列式存储 - 查询)                                               │
│   └── id: [1, 2, 3, ...]                                                 │
│      name: ["Alice", "Bob", ...]                                          │
│      age: [25, 30, ...]                                                  │
│                                                                         →
│   Advantage: 只读需要的列，减少IO                                          │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、数据格式

```cpp
// Native格式
struct ColumnVector {
    int8_t data[N];
    int8_t null_map[N];
    int32_t hash[N];
};

// 压缩: LZ4/ZSTD
class ColumnCompressed : public ColumnVector {
    uint8_t compressed[N];
    size_t decompressed_size;
    
    void decompress() {
        lz4_decompress(compressed, decompressed);
    }
};
```

## 三、面试高频题

### Q1: ClickHouse为什么快？

```
A:
1. 列式存储
2. 向量化执行
3. 数据压缩
```

### Q2: 如何实现MergeTree？

```
A:
1. 分区
2. 主键
3. 主键稀疏索引
```

## 四、自测题

1. 解释列式存储
2. 如何实现MergeTree？
3. 如何进行聚合优化？

---

## 参考文档

- [ClickHouse文档](https://clickhouse.com/docs)
- [ClickHouse源码](https://github.com/ClickHouse/ClickHouse)
