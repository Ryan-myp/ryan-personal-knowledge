# ClickHouse内核 - 资深专家深度实现

## 一、列式存储架构

### 1.1 存储引擎层次

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     ClickHouse存储引擎层次                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   SQL层          │  Parser → Query Planner → Executor                   │
│   ───────────────┼─────────────────────────────────────────────────────│
│   Storage层      │  MergeTree家族 / JointStorage / Dictionary           │
│   ───────────────┼─────────────────────────────────────────────────────│
│   Part层         │  Part → Block → Column → Compression                 │
│   ───────────────┼─────────────────────────────────────────────────────│
│   物理层         │  .bin (数据) / .mrk (标记) / .ck (校验和)             │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

### 1.2 列存储实现

```cpp
// src/Storages/ColumnsWithTypeAndName.h
class ColumnWithTypeAndName {
public:
    String name;              // 列名
    DataTypePtr type;        // 数据类型
    ColumnRawPtrs columns;   // 原始列数据
    
    // 列数据布局
    struct ColumnData {
        std::vector<UInt8> offsets;    // 可变长数据偏移
        std::vector<UInt8> null_map;   // NULL标记
        std::vector<UInt8> data;       // 实际数据
        String compression_codec;      // 压缩算法
    };
};

// 向量化读取
class IColumn {
public:
    virtual Field operator[](size_t n) const = 0;
    virtual void get(size_t n, Field &res) const = 0;
    virtual size_t size() const = 0;
    
    // 批量读取（向量化核心）
    void get(size_t n, ColumnVector<UInt64>::Container &res) const {
        // SIMD优化读取
        #pragma GCC ivdep
        for (size_t i = 0; i < n; ++i) {
            res[i] = data[i];
        }
    }
};
```

## 二、MergeTree引擎核心

### 2.1 Part结构

```
/part_0_0_0_0/                    # Part目录
├── count.txt                     # 行数
├── checksums.txt                 # 校验和
├── primary.idx                   # 主键索引（稀疏索引）
├── skp.idx                       # 跳过索引
├── columns.txt                   # 列元数据
├── column_1.bin                  # 列数据（LZ4压缩）
├── column_1.mrk2                 # 列标记
├── column_2.bin
├── column_2.mrk2
├── minmax_date.idx               # 范围索引
├── partition.dat                 # 分区信息
└── query_parts.bin               # 查询优化信息
```

### 2.2 主键索引实现

```cpp
// 稀疏索引：每8192行一个索引点
class PrimaryIndex {
public:
    static constexpr size_t INDEX_GRANULARITY = 8192;
    
    struct IndexPoint {
        String min;      // 最小值
        String max;      // 最大值
        size_t offset;   // 在part中的行偏移
    };
    
    std::vector<IndexPoint> points;
    
    // 二分查找定位
    size_t findRow(const String &key) {
        // 找到第一个 min <= key 的索引点
        auto it = std::lower_bound(points.begin(), points.end(), key,
            [](const IndexPoint& p, const String& k) {
                return p.min < k;
            });
        
        if (it == points.end()) return -1;
        
        // 在granule内线性搜索
        size_t start = it->offset;
        size_t end = std::min(start + INDEX_GRANULARITY, total_rows);
        
        for (size_t i = start; i < end; ++i) {
            if (getRow(i) >= key) return i;
        }
        return -1;
    }
};

// 创建稀疏索引
void buildIndex() {
    for (size_t i = 0; i < rows; i += INDEX_GRANULARITY) {
        IndexPoint point;
        point.min = getMinValue(i);
        point.max = getMaxValue(std::min(i + INDEX_GRANULARITY, rows));
        point.offset = i;
        points.push_back(point);
    }
}
```

### 2.3 数据写入流程

```cpp
class MergeTreeWriter {
public:
    void write(const Block &block) {
        // 1. 写入数据到临时文件
        for (const auto &col : block.getColumns()) {
            writeColumn(col);
        }
        
        // 2. 更新索引
        updateIndex(block.rows());
        
        // 3. 写标记文件
        writeMarks();
        
        // 4. 刷盘
        fsync();
    }
    
private:
    void writeColumn(const ColumnWithTypeAndName &col) {
        // 压缩写入
        auto compressed = compress(col.data, col.type);
        
        // 写入.bin文件
        writeFile(col.name + ".bin", compressed);
        
        // 记录偏移量
        offsets.push_back(current_file_size);
    }
    
    void updateIndex(size_t rows_added) {
        if (rows_added % INDEX_GRANULARITY == 0) {
            // 添加一个新的索引点
            addIndexPoint();
        }
    }
};
```

## 三、向量执行引擎

### 3.1 基础概念

```cpp
// 向量化执行：一次性处理8192行
class VectorizedBlock {
public:
    // 批量处理
    void executeBatch(size_t batch_size) {
        // SIMD优化：一次性处理多个元素
        #pragma GCC target("avx2")
        for (size_t i = 0; i < batch_size; i += 8) {
            // 8个元素并行处理
            __m256i v = _mm256_load_si256((__m256i*)&data[i]);
            __m256i result = _mm256_add_epi64(v, constant);
            _mm256_store_si256((__m256i*)&output[i], result);
        }
    }
    
    // 谓词下推
    void filter(const ColumnUInt8 &filter_column) {
        // 只读取需要的列
        for (size_t i = 0; i < block.columns(); ++i) {
            if (should_read(i, filter_column)) {
                readColumn(i);
            }
        }
    }
};
```

### 3.2 聚合优化

```cpp
// 部分聚合 + 合并聚合
class AggregationOptimizer {
public:
    // Step 1: 局部聚合（每个Part内）
    PartialResult partialAggregate(const Block &block) {
        HashMap<Key, AggregateState> state;
        
        for (size_t i = 0; i < block.rows(); ++i) {
            Key key = getKey(i);
            state.merge(key, getValue(i));
        }
        
        return PartialResult(state);
    }
    
    // Step 2: 全局合并
    GlobalResult mergeAggregates(const std::vector<PartialResult> &partials) {
        GlobalResult result;
        
        for (const auto &partial : partials) {
            result.merge(partial.state);
        }
        
        return result;
    }
};

// 示例：COUNT聚合
template <typename T>
class CountAggregator {
public:
    void add(T value) {
        if (!null_map[value]) {
            count++;
        }
    }
    
    T combine(const CountAggregator &other) {
        return count + other.count;
    }
    
private:
    UInt64 count = 0;
    ColumnUInt8 null_map;
};
```

## 四、查询执行优化

### 4.1 谓词下推

```sql
-- 原始查询
SELECT user_id, amount 
FROM orders 
WHERE date >= '2024-01-01' 
  AND user_id IN (1, 2, 3)
  AND amount > 100;

-- 优化后：谓词下推到Storage层
-- 1. 先过滤date分区（利用范围索引）
-- 2. 再过滤user_id（利用稀疏索引）
-- 3. 最后过滤amount（列存储，只读需要的列）
```

### 4.2 数据跳过索引

```cpp
// 数据跳过索引：加速IN查询
class SkipsIndex {
public:
    struct GranuleStats {
        Float64 min_value;
        Float64 max_value;
        Float64 mean_value;
        Float64 stddev;
        size_t rows;
    };
    
    // 构建跳过索引
    void build(const ColumnFloat64 &column) {
        for (size_t i = 0; i < column.size(); i += GRANULE_SIZE) {
            GranuleStats stats;
            stats.min_value = column[i];
            stats.max_value = column[i];
            
            for (size_t j = i; j < std::min(i + GRANULE_SIZE, column.size()); ++j) {
                stats.min_value = std::min(stats.min_value, column[j]);
                stats.max_value = std::max(stats.max_value, column[j]);
            }
            
            stats.rows = GRANULE_SIZE;
            stats.mean_value = calculateMean(column, i, GRANULE_SIZE);
            stats.stddev = calculateStddev(column, i, GRANULE_SIZE);
            
            indexes.push_back(stats);
        }
    }
    
    // 查询优化：跳过不匹配的granule
    bool skipGranule(size_t granule_id, const Set &values) {
        const auto &stats = indexes[granule_id];
        
        // 如果granule的最小值大于所有查询值，跳过
        if (stats.min_value > *std::max_element(values.begin(), values.end())) {
            return true;
        }
        
        // 如果granule的最大值小于所有查询值，跳过
        if (stats.max_value < *std::min_element(values.begin(), values.end())) {
            return true;
        }
        
        return false;
    }
};
```

## 五、压缩算法

### 5.1 压缩策略

```cpp
class CompressionStrategy {
public:
    // 列级压缩选择
    CompressionCodecPtr chooseCodec(const DataTypePtr &type) {
        // 整数类型：Delta + ZSTD
        if (type->isInteger()) {
            return std::make_shared<ColumnDelta>(
                std::make_shared<CompressionZSTD>(1)
            );
        }
        
        // 字符串类型：LZ4
        if (type->isString()) {
            return std::make_shared<CompressionLZ4>();
        }
        
        // 日期时间：DoubleDelta
        if (type->isDate() || type->isDateTime()) {
            return std::make_shared<ColumnDoubleDelta>(
                std::make_shared<CompressionLZ4>()
            );
        }
        
        return std::make_shared<CompressionLZ4>();
    }
};

// Delta编码：利用数据相关性
class ColumnDelta {
public:
    void encode(const ColumnUInt64 &input) {
        UInt64 prev = 0;
        for (size_t i = 0; i < input.size(); ++i) {
            diffs.push_back(input[i] - prev);
            prev = input[i];
        }
    }
    
    void decode(ColumnUInt64 &output) {
        UInt64 prev = 0;
        for (auto diff : diffs) {
            prev += diff;
            output.push_back(prev);
        }
    }
};
```

## 六、面试高频题

### Q1: ClickHouse为什么比MySQL快100倍？

```
A:
1. 列式存储：只读需要的列，减少IO
2. 向量化执行：SIMD指令批量处理
3. 数据压缩：LZ4/ZSTD降低存储和IO
4. 稀疏索引：快速定位数据范围
5. 预聚合：物化视图加速查询
```

### Q2: MergeTree如何实现高效写入？

```
A:
1. 顺序写：Part按时间顺序追加
2. 异步提交：后台Merge线程
3. 零拷贝：直接使用mmap读取
4. 批量写入：单次大写优于多次小写
```

### Q3: 如何处理ClickHouse的插入性能问题？

```
A:
1. 批量插入：单次10000+行
2. 禁用索引：INSERT IGNORE INDEX
3. 异步写入：ASYNC INSERT
4. 分区设计：合理选择分区键
5. 压缩调整：降低压缩级别提速
```

## 七、自测题

1. 解释列式存储的优势
2. 稀疏索引如何工作？
3. 如何实现数据跳过索引？
4. ClickHouse的压缩策略是什么？

---

## 参考文档

- [ClickHouse官方文档](https://clickhouse.com/docs)
- [ClickHouse源码](https://github.com/ClickHouse/ClickHouse)
- [列式数据库原理](https://www.cloudera.com/documentation/enterprise/latest/topics/cdh_ig_columnar.html)
