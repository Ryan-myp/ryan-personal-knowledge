# 数据压缩算法深度解析

> 深入数据压缩：无损压缩、有损压缩、压缩算法原理。
> 源码级分析，包含生产环境应用。
> 适用对象：数据工程师、系统工程师

---

## 1. 压缩算法分类

### 1.1 无损压缩

```
无损压缩算法：

1. 字典编码
   ├── LZ77 / LZ78
   ├── LZW (Lempel-Ziv-Welch)
   └── DEFLATE (gzip/zip)

2. 统计编码
   ├── Huffman Coding
   ├── Arithmetic Coding
   └── Range Coding

3. 现代算法
   ├── LZ4 (快速压缩)
   ├── Snappy (平衡压缩)
   ├── ZSTD (高压缩比)
   └── Brotli (Web 优化)
```

### 1.2 有损压缩

```
有损压缩算法：

1. 图像压缩
   ├── JPEG (离散余弦变换)
   ├── WebP (预测编码)
   └── AVIF (AV1 编码)

2. 音频压缩
   ├── MP3 (心理声学模型)
   ├── AAC (高级音频编码)
   └── Opus (低延迟编码)

3. 视频压缩
   ├── H.264/AVC
   ├── H.265/HEVC
   └── AV1
```

---

## 2. Huffman 编码

### 2.1 算法原理

```
Huffman 编码流程：

1. 统计字符频率
   └── 构建频率表

2. 构建 Huffman 树
   ├── 将字符作为叶子节点
   ├── 合并频率最低的两个节点
   └── 重复直到只剩一个节点

3. 生成编码
   └── 左分支 0，右分支 1
```

### 2.2 Go 实现

```go
// huffman.go

package compression

import (
    "container/heap"
)

type Node struct {
    Char    byte
   Freq     int
    Left   *Node
    Right  *Node
}

type PriorityQueue []*Node

func (p PriorityQueue) Len() int { return len(p) }
func (p PriorityQueue) Less(i, j int) bool { return p[i].Freq < p[j].Freq }
func (p PriorityQueue) Swap(i, j int) { p[i], p[j] = p[j], p[i] }

func (p *PriorityQueue) Push(x interface{}) {
    *p = append(*p, x.(*Node))
}

func (p *PriorityQueue) Pop() interface{} {
    old := *p
    n := len(old)
    x := old[n-1]
    *p = old[:n-1]
    return x
}

func BuildHuffmanTree(freq map[byte]int) *Node {
    pq := &PriorityQueue{}
    heap.Init(pq)
    
    for ch, f := range freq {
        heap.Push(pq, &Node{Char: ch, Freq: f})
    }
    
    for pq.Len() > 1 {
        left := heap.Pop(pq).(*Node)
        right := heap.Pop(pq).(*Node)
        heap.Push(pq, &Node{
            Freq: left.Freq + right.Freq,
            Left: left,
            Right: right,
        })
    }
    
    return heap.Pop(pq).(*Node)
}

func BuildCodes(node *Node, prefix string, codes map[byte]string) {
    if node == nil {
        return
    }
    if node.Char != 0 {
        codes[node.Char] = prefix
        return
    }
    BuildCodes(node.Left, prefix+"0", codes)
    BuildCodes(node.Right, prefix+"1", codes)
}
```

---

## 3. LZ4 压缩

### 3.1 算法原理

```
LZ4 压缩原理：

1. 查找重复字符串
   └── 在已处理数据中查找匹配

2. 编码策略
   ├── 匹配：存储 (offset, length)
   └── 不匹配：直接存储字

3. 快速解压
   └── 线性时间复杂度 O(n)
```

### 3.2 Go 实现

```go
// lz4.go

package compression

import (
    "encoding/binary"
)

const (
    COMPRESSIBLE_MAGIC = 0
    INCOMPRESSIBLE_MAGIC = 1
    MAXMATCHLEN = 0xFFFF
)

type LZ4Compressor struct {
    hashTable [1 << 16]byte
}

func (c *LZ4Compressor) Compress(src []byte) []byte {
    // 简化版 LZ4 压缩
    var dst []byte
    var pos int
    
    for pos < len(src) {
        // 查找匹配
        matchPos := c.findMatch(src, pos)
        
        if matchPos >= 0 && pos+4 < len(src) {
            // 有匹配，存储字面量和匹配
            literalLen := pos - matchPos
            dst = append(dst, byte(literalLen))
            dst = append(dst, src[matchPos:pos]...)
            dst = append(dst, binary.LittleEndian.Uint16([]byte{byte(matchPos&0xFF), byte(matchPos>>8)}))
            pos += 4
        } else {
            // 无匹配，存储字面量
            literalLen := 0
            for pos+literalLen < len(src) && literalLen < 15 {
                if pos+literalLen+1 < len(src) && isRepeat(src[pos+literalLen:pos+literalLen+2]) {
                    break
                }
                literalLen++
            }
            dst = append(dst, byte(literalLen))
            dst = append(dst, src[pos:pos+literalLen]...)
            pos += literalLen
        }
    }
    
    return dst
}

func (c *LZ4Compressor) findMatch(src []byte, pos int) int {
    // 简化版匹配查找
    if pos+4 > len(src) {
        return -1
    }
    key := binary.LittleEndian.Uint16(src[pos:pos+2])
    return int(c.hashTable[key])
}

func isRepeat(data []byte) bool {
    return len(data) >= 2 && data[0] == data[1]
}
```

---

## 4. ZSTD 压缩

### 4.1 算法特性

```
ZSTD 算法特性：

1. 多阶段压缩
   ├── 字典编码
   ├── 匹配查找
   └── 熵编码

2. 可配置压缩级别
   └── 1-19 级（1 最快，19 最高压缩比）

3. 流式压缩
   └── 适合大数据流
```

### 4.2 Go 使用示例

```go
// zstd_usage.go

package compression

import (
    "github.com/klauspost/compress/zstd"
)

func ZSTDCompress(data []byte, level int) ([]byte, error) {
    encoder, err := zstd.NewWriter(nil, zstd.WithEncoderLevel(zstd.EncoderLevelFromZstd(level)))
    if err != nil {
        return nil, err
    }
    defer encoder.Close()
    
    return encoder.EncodeAll(data, nil), nil
}

func ZSTDDecompress(data []byte) ([]byte, error) {
    decoder, err := zstd.NewReader(nil)
    if err != nil {
        return nil, err
    }
    defer decoder.Close()
    
    return decoder.DecodeAll(data, nil)
}
```

---

## 5. 压缩对比

### 5.1 性能对比

```
压缩算法性能对比：

┌────────────┬──────────┬──────────┬────────────┐
│ 算法       │ 压缩速度 │ 解压速度 │ 压缩比     │
├────────────┼──────────┼──────────┼────────────┤
│ LZ4        │ 最快     │ 最快     │ 中等       │
│ Snappy     │ 快       │ 快       │ 中等       │
│ ZSTD(1)    │ 快       │ 快       │ 较好       │
│ ZSTD(9)    │ 中       │ 中       │ 好         │
│ ZSTD(19)   │ 慢       │ 中       │ 最好       │
│ GZIP(9)    │ 中       │ 中       │ 好         │
│ Brotli     │ 慢       │ 中       │ 最好       │
└────────────┴──────────┴──────────┴────────────┘
```

### 5.2 选型建议

```
压缩算法选型：

场景：日志压缩
├── 推荐：LZ4
└── 原因：速度快，解压快

场景：Web 资源压缩
├── 推荐：Brotli
└── 原因：压缩比高，浏览器支持

场景：数据库存储
├── 推荐：ZSTD
└── 原因：平衡压缩比和速度

场景：网络传输
├── 推荐：Snappy
└── 原因：速度快，压缩比可接受
```

---

## 6. 总结

### 6.1 核心原理回顾

| 算法 | 原理 | 特点 |
|------|------|------|
| Huffman | 频率编码 | 最优前缀码 |
| LZ4 | 字典编码 | 极快 |
| ZSTD | 多阶段 | 平衡 |
| Brotli | 增强 LZ77+Huffman | Web 优化 |

### 6.2 最佳实践

- [ ] 根据场景选择算法
- [ ] 考虑压缩级别
- [ ] 监控压缩率
- [ ] 评估 CPU 开销

---

*最后更新：2026-08-11*
*作者：Ryan*
