# MySQL 内核深入 — 源码级 MVCC、锁协议、XA 两阶段提交、存储引擎对比

> 标签: `#MySQL` `#InnoDB` `#MVCC` `#锁` `#XA事务` `#源码级`
> 创建日期: 20260608
> 作者: Ryan

---

## 1. 存储引擎架构源码分析

### 1.1 Storage Engine API 调用路径

```
MySQL 服务层（handler API）→ 存储引擎层（handler 派生类）

调用链（以 SELECT 为例）:
  sql_select.cc::JOIN::exec()
    → handler::read_first()          // handler 指针指向 InnoDB handler
    → ha_innobase::index_read_map()  // InnoDB 层索引读取
    → btr_cur_search_to_nth_level()  // B+Tree 查找第 N 层
    → page_cur_search_with_match()   // 页内定位记录
    → row_sel_read_for_mysql()       // 构建 MySQL 记录格式
    → rec_get_nth_field()           // 提取字段值

核心抽象: struct handler (sql/handler.h)
  class handler {
    virtual int read_first() = 0;
    virtual int index_read_map(...) = 0;
    virtual int write_row(const uchar* buf) = 0;
    virtual int update_row(const uchar* old_data, const uchar* new_data) = 0;
    virtual int delete_row(const uchar* buf) = 0;
    
    // 关键数据成员:
    TABLE* table;           // MySQL 表结构
    mem_root_array<uchar*> ref;   // 当前记录的 ref（行指针）
    ha_rows records;      // 记录计数
  };

InnoDB handler: class ha_innobase : public handler
  关键成员:
    dict_table_t* m_prebuilt->index    // 当前使用的索引
    dtuple_t* prebuilt->search_tuple   // 搜索条件
    ulint* offsets                       // 字段偏移量（缓存）
    que_thr_t* thr                       // 查询线程
    dberr_t err                          // 错误码
```

### 1.2 执行计划生成流程

```
SQL → 解析 → 优化 → 执行

sql_parse.cc::dispatch_command()
  → mysql_parse()         // YACC 解析 SQL → ST_select_stmt
  → mysql_execute_command()  // 生成执行计划
  
  JOIN::optimize()  ← 执行计划优化入口:
    1. 表关联顺序优化（NestLoops + HashJoin 选择）
       - 基于代价模型（Cost Model）:
         cost = scan_cost + join_cost + sort_cost + temp_table_cost
         scan_cost = io_blocks / page_size * io_block_read_cost
         join_cost = n_rows_left * n_rows_right * cpu_cost_factor
    2. 索引选择（Cost Index vs Full Scan）
       - 统计信息: KEY_STATS.n_rows, n_non_null_keys
       - 选择性计算: selectivity = distinct_values / total_rows
       - 使用 B+Tree 索引的代价: log_b(n) * 页读取次数
    3. 谓词下推优化
    4. 生成 PlanNode → 转换为 Execution Plan
    
  JOIN::exec()  ← 执行:
    while (!read_first())
      while (!read_next())
        evaluate_condition()
        emit_row()
```

---

## 2. InnoDB 存储结构 — 源码级

### 2.1 表空间（Tablespace）物理结构

```
共享表空间（ibdata1）:
┌─────────────────────────────────────────────────────────────┐
│ Page 0: File Space Header                                   │
│   - space_id, flags, size, next_page, n_reserved_pages      │
│   - free list, flush_list, RBA (Redo Log Byte Address)      │
├─────────────────────────────────────────────────────────────┤
│ Page 1: System Tablespaces                                  │
│   - INFORMATION_SCHEMA 内部表结构                             │
│   - 数据字典（mysql.data_dict）                               │
├─────────────────────────────────────────────────────────────┤
│ Page 2: Double Write Buffer                                 │
│   - 128 个连续页（默认 16KB 页）                              │
│   - 写数据前先拷贝到这里，crash recovery 时从这里恢复          │
├─────────────────────────────────────────────────────────────┤
│ Page 3-...: Undo Logs (Rollback Segments)                   │
│   - trx_sys_t 中的 rseg 数组                                │
│   - TRX_RSEG_SIZE 个 undo page                             │
└─────────────────────────────────────────────────────────────┘

单表空间（.ibd 文件）:
┌─────────────────────────────────────────────────────────────┐
│ Page 0: File Space Header                                   │
├─────────────────────────────────────────────────────────────┤
│ Page 1: Table Header (FIL_TYPE_TABLE)                       │
│   - table_id, format, n_columns, n_fields, ...              │
│   - 事务 ID 计数器 (last_insert_id, auto_increment counter)  │
├─────────────────────────────────────────────────────────────┤
│ Page 2: Record List Head                                    │
│   - 主键 B+Tree 根页（如果有数据）                            │
│   - 二级索引根页                                            │
├─────────────────────────────────────────────────────────────┤
│ Page 3+: 数据页 / 索引页                                     │
│   - 聚簇索引页                                               │
│   - 二级索引页                                               │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 页（Page）结构 — 源码级

```c
// fil0fil.h — Page Header 结构
struct page_header_t {
  ulint FIL_PAGE_OFFSET;   // 4B: 页在 file space 中的偏移
  ulint FIL_PAGE_PREV;     // 4B: 前向页偏移（用于双向链表）
  ulint FIL_PAGE_NEXT;     // 4B: 后向页偏移
  lsn_t FIL_PAGE_LSN;      // 8B: 页的 LSN（重做日志序列号）
  ulint FIL_PAGE_TYPE;     // 2B: 页类型
    // FIL_PAGE_INDEX (B+Tree 页)
    // FIL_PAGE_IBUF_FREE_LIST (Insert Buffer)
    // FIL_PAGE_FS_INFO
    // FIL_PAGE_TYPE_BLOB
    // FIL_PAGE_TYPE_FSP_HDR
    // FIL_PAGE_TYPE_XDES (Extent Descriptor)
  ulint FIL_PAGE_FLUSH_LSN;// 8B: 页的刷新 LSN（用于判断是否需要 flush）
};

// page0page.h — Index Page Header
struct page_hdr_t {
  ulint PAGE_N_DIR_SLOTS;    // 目录槽数量
  ulint PAGE_HEAP_TOP;       // 堆顶指针（第一条用户记录的起始位置）
  ulint PAGE_HEAP_END;       // 堆底指针（最后一条用户记录的结束位置）
  ulint PAGE_N_HEAP;         // 堆中记录数
  ulint PAGE_FREE;           // 空闲空间起始位置
  ulint PAGE_GARBAGE;        // 已删除记录的空闲空间
  ulint PAGE_LAST_INSERT;    // 最后插入记录的偏移
  ulint PAGE_DIRECTION;      // 最后插入方向
  ulint PAGE_N_OLD_INSERTS;  // 旧插入计数（用于调试/优化）
  ut_d(ulint PAGE_N_DIR_SLOTS_DEBUG);
};

// page0page.h — Record Header (6 字节)
struct rec_t {
  // 变长字段列表（variable length column list）: 变长
  //   每 1 或 2 字节表示一个变长字段的长度是否 > 127 字节
  // NULL 标识符（null bit vector）: 变长
  //   每 1 字节标识最多 8 个 NULL 值字段
  
  // 记录头信息（record header）: 5 字节
  //   delete_mask: 1 bit — 是否被标记删除
  //   min_rec_flag: 1 bit — 是否是最小记录（B+Tree 内部节点使用）
  //   n_owned: 4 bits — 该记录"拥有"的记录数（页目录优化用）
  //   heap_no: 13 bits — 堆编号（0=infimum, 1=supremum）
  //   next_record: 16 bits — 下一个记录的相对偏移
};
```

### 2.3 行格式源码

```c
// row0row.h — InnoDB 内部行结构
struct rec_t {
  // 每个记录的内存布局:
  // [变长字段列表][NULL标识符][记录头(5B)][主键/行ID][定长字段][变长字段数据]
  
  // 定长字段存储方式:
  //   直接按字节排列，小端序
  
  // 变长字段存储方式:
  //   长度 < 768 字节: 直接存储在行内
  //   长度 >= 768 字节: 前 768 字节存储在行内，后续存储在溢出页
  //     overflow page: page_no (4B) + offset (4B) + 实际数据
};

// DYNAMIC 行格式的溢出页结构
struct page_t {
  // 溢出页: 包含一个字段的多页连续存储
  // 第一页: 8B next_page + 字段数据(前N字节)
  // 后续页: 8B next_page + 字段数据
  // 最后一页: 8B next_page(=FIL_ADDR_NULL) + 字段数据
};
```

---

## 3. B+Tree 索引 — 源码级

### 3.1 B+Tree 查找流程

```c
// btr0cur.cc — btr_cur_search_to_nth_level()
// 源码级查找流程:

btr_cur_search_to_nth_level(
    dict_index_t* index,   // 要查找的索引
    ulint level,           // 目标层级（= index->n_levels - 1 表示叶子层）
    dtuple_t* tuple,       // 搜索条件元组
    btr_cur_t* cursor,     // 输出: 定位到的游标
    ulint mode,            // BTR_SEARCH_LEAF / BTR_MODIFY_LEAF / ...
    const dtuple_t* ref_tup,
    mtr_t* mtr)            // mini transaction
{
  // Step 1: 从根页开始
  buf_block_t* block = btr_root_block(index);
  
  // Step 2: 逐层下降（非叶子层）
  for (ulint cur_level = index->n_levels - 1; cur_level > level; ) {
    // 二分查找当前页
    page_cur_search_with_match(
      page,               // 当前页
      index,              // 索引信息
      tuple,              // 搜索键值
      PAGE_CUR_LE,        // 搜索方向
      &offsets,           // 字段偏移量缓存
      &match_rec,         // 匹配记录
      &match_size         // 匹配字节数
    );
    
    // 根据查找结果，确定子节点页
    ulint page_no = page_get_child_page(page, rec);
    block = buf_page_get(dict_table_get_space(table), 
                         dict_table_get_page_size(table),
                         page_no, RW_SXL_LOCK, mtr);
    cur_level--;
  }
  
  // Step 3: 在叶子页执行二分查找
  page_cur_search_btr_cur(level, cursor, mode, mtr);
  
  // Step 4: 定位到具体记录
  // 返回 cursor 指向的记录和偏移量
}

// 页内二分查找: page_cur_search_with_match()
// 利用 Page Directory 加速:
// 1. 先看 Page Directory 中哪一组覆盖目标 key
// 2. 在该组范围内线性查找（每组最多 36 字节，约几十条记录）
// 3. 如果匹配成功，返回 match_rec 和 match_size
```

### 3.2 索引分裂与合并

```c
// btr0cur.cc — 插入时可能的页分裂

// 上溢（Overflow）: 页满了，需要分裂
btr_cur_insert_correct_side(cursor, tuple, offsets, mode, mtr);

// 页分裂算法:
// 1. 创建新页（neighbor page）
// 2. 从原页末尾向前复制记录到新页，直到新页填满一半
// 3. 更新前向/后向页指针（PAGE_PREV/PAGE_NEXT）
// 4. 更新页头信息（PAGE_FREE, PAGE_HEAP_TOP 等）
// 5. 如果这是非叶子层，还需要分裂索引键（递归向上）

// 下溢（Underflow）: 页太空，需要合并
// 当一页中记录数 < 阈值（通常是页容量的一半），尝试与前/后邻居合并
// 合并条件: 前/后邻居也有足够的空闲空间
```

### 3.3 二级索引回表

```c
// 二级索引查找到主键后的回表过程:

// 1. 在二级索引 B+Tree 中找到目标记录
cursor = btr_cur_search(..., secondary_index, ...);
// 获取主键值: ulint primary_key = rec_get_nth_field(rec, offsets, 0, ...);

// 2. 在聚簇索引 B+Tree 中查找完整记录
cursor = btr_cur_search(..., clustered_index, primary_key, ...);

// 3. 提取需要的字段
// 优化: 如果所有需要的字段都在二级索引中（覆盖索引），直接返回，不回表
// 判断逻辑: row_build_check_for_clust_needed()
```

---

## 4. MVCC 源码级深度分析

### 4.1 事务 ID 管理（trx_sys_t）

```c
// trx0trx.h — 全局事务系统
struct trx_sys_t {
  trx_id_t              next_trx_id;      // 下一个分配的事务 ID
  ulint                 n_transactions;   // 活跃事务数
  que_thr_t*            running_trx_list; // 运行中的事务链表
  UT_LIST_BASE_NODE_T(trx_rseg_t) rsegs;  // rollback segments 列表
  
  // 全局一致性读视图
  trx_read_view_t*      rsegs;  // 读写分离视图
  
  // 事务 ID 分配:
  trx_id_t trx_id_get_next() {
    return(++next_trx_id);
  }
  
  // 注意: 事务 ID 是全局单调递增的，不分配给已提交事务
  // 这意味着事务 ID 可能存在"空洞"（已提交事务释放的 ID 不会被复用）
};

// InnoDB 事务分配:
// 1. 事务开始前，获取全局事务 ID: trx->id = trx_sys->next_trx_id++
// 2. 事务结束后，事务 ID 不再分配给新事务（避免 ID 耗尽）
// 3. 事务 ID 耗尽: 达到 trx_sys->max_trx_id 后会等待旧事务提交
```

### 4.2 ReadView 源码 — 核心中的核心

```c
// trx0types.h — ReadView 结构
struct trx_read_view_t {
  trx_id_t    low_trx_id;          // 创建时最小的活跃事务 ID
  trx_id_t    high_trx_id;         // 创建时即将分配的下一个事务 ID
  trx_id_t    creator_trx_id;      // 创建该 ReadView 的事务 ID
  trx_id_t*   low_limit_no;        // 活跃事务 ID 列表（数组）
  trx_id_t    upper_limit_no;      // 活跃事务 ID 列表的数量
  ulint       flags;               // READ_VIEW_ESTIMATED 标志
};

// ha_innobase.cc::read_view_create() — ReadView 创建逻辑
// 关键代码路径:
static void read_view_create(
  trx_read_view_t* view,    // 输出: 创建的 ReadView
  trx_t*     trx,           // 当前事务
  ulint      flags)         // READ_VIEW_IGNORE_HIDDEN
{
  view->creator_trx_id = trx->id;
  
  // 收集当前所有活跃事务
  view->low_limit_no = 0;
  view->upper_limit_no = 0;
  
  // 遍历全局活跃事务链表 trx_sys->running_trx_list
  for (trx_t* t = UT_LIST_GET_FIRST(trx_sys->rsegs); 
       t != NULL; 
       t = UT_LIST_GET_NEXT(rsegs, t)) {
    if (!trx_read_view_check_visibility(view, t->id)) {
      // 添加到活跃事务列表
      // ...
    }
  }
  
  // 如果活跃事务列表为空（常见于单事务场景）
  if (view->upper_limit_no == 0) {
    view->low_limit_no = view->high_trx_id;
  }
  
  // 记录创建时的时间戳
  view->creation_time = os_thread_current_time();
}

// 判断可见性（关键逻辑）
static bool trx_read_view_check_visibility(
  const trx_read_view_t* view,
  trx_id_t    trx_id)
{
  // 情况1: 该事务在 ReadView 创建之前就已经提交
  if (trx_id < view->low_limit_no) {
    return(true);  // 可见
  }
  
  // 情况2: 该事务在 ReadView 创建之后才启动
  if (trx_id >= view->high_limit_no) {
    return(false);  // 不可见（事务还没开始）
  }
  
  // 情况3: 该事务在 ReadView 创建时处于活跃状态
  for (trx_id_t id : view->low_limit_no) {
    if (id == trx_id) {
      return(false);  // 不可见（当前活跃事务）
    }
  }
  
  // 情况4: 该事务在 ReadView 创建后已提交
  return(true);  // 可见
}
```

### 4.3 RC vs RR 的源码差异

```c
// ha_innobase.cc::read_record() — 读取记录
void ha_innobase::read_record()
{
  // 关键: 每次 read_record() 被调用时，是否创建新的 ReadView？
  
  // RR 模式（repeatable_read = true）:
  if (m_prebuilt->select_for_update || 
      m_prebuilt->skip_locking) {
    // 当前读（FOR UPDATE / LOCK IN SHARE MODE）: 不走 MVCC，走当前读
    read_current_record();
  } else if (!m_prebuilt->read_view) {
    // RR 模式第一次查询: 创建 ReadView
    m_prebuilt->read_view = read_view_create();
  }
  // RR 模式后续查询: 复用已有的 m_prebuilt->read_view
  
  // RC 模式（repeatable_read = false）:
  // 每次都创建新的 ReadView
  m_prebuilt->read_view = read_view_create();
  
  // 然后遍历版本链
  rec_t* rec = read_from_version_chain(m_prebuilt->read_view);
  
  if (rec) {
    build_mysql_record(rec);  // 构建 MySQL 格式的记录
  }
}

// ha_innobase.cc::read_from_version_chain() — 版本链遍历
rec_t* ha_innobase::read_from_version_chain(
  const trx_read_view_t* view,
  const rec_t* rec)
{
  while (rec) {
    trx_id_t trx_id = rec_get_trx_id(rec, offsets);
    
    if (trx_read_view_check_visibility(view, trx_id)) {
      // 当前版本可见，返回
      return(rec);
    }
    
    // 当前版本不可见，沿 undo log 链找上一个版本
    roll_ptr_t roll_ptr = rec_get_roll_ptr(rec, offsets);
    undo_rec_t* undo_rec = undo_log_get_prev_rec(roll_ptr);
    
    if (!undo_rec) {
      // 版本链到头了，返回 NULL（记录被删除或不存在）
      return(NULL);
    }
    
    rec = undo_rec->rec;
  }
}
```

### 4.4 Undo Log 物理结构 — 源码级

```c
// trx0undo.h — Undo Log Page 结构
struct undo_log_page_t {
  // 页头（38B）
  page_header_t header;
  
  // 撤销日志头部（17B）
  struct undo_log_hdr_t {
    ulint page_id;        // 页 ID
    ulint page_size;      // 页大小
    ulint space_id;       // 表空间 ID
    ut_d(os_offset_t file_size);
    ulint log_id;         // 日志 ID
    ulint type_and_mode;  // 事务状态
    ulint insert_offset;  // 插入偏移
    ulint update_offset;  // 更新偏移
    ulint delete_offset;  // 删除偏移
    ulint min_trx_id;     // 最小事务 ID
    ulint limit_trx_id;   // 最大事务 ID
    ulint n_unDO;         // undo 记录数
  };
  
  // undo log 记录:
  struct undo_log_record_t {
    ulint type;          // TRX_UNDO_INSERT_REC / TRX_UNDO_UPDATE_REC / TRX_UNDO_DEL_MARK_REC
    ulint length;        // 记录长度
    trx_id_t trx_id;     // 事务 ID
    roll_ptr_t roll_ptr; // 回滚指针（指向上一条 undo 记录）
    
    // 对于 UPDATE 记录:
    //   存储修改前的完整记录（row_copy_t）
    
    // 对于 INSERT 记录:
    //   存储插入的完整记录
    
    // 对于 DELETE MARK 记录:
    //   存储标记删除的原始记录
  };
};

// Roll Pointer 格式（7B）:
// [space_id (4B)] + [page_no (4B)] + [offset (4B)] → 取前 7 字节
// 指向 undo log 中的前一条记录

// undo log 的维护:
// 1. 事务提交时，undo log 标记为可清理
// 2. purge thread 定期清理过期的 undo log
// 3. 清理条件: 没有活跃事务需要该版本（即没有 ReadView 还在引用）
// 4. 清理策略: 从 oldest active transaction 往前清理
```

### 4.5 purge thread — 后台清理机制

```c
// purge0purge.cc — 后台清除线程
// 职责: 清理已提交事务产生的删除标记和无效版本

struct purge_sys_t {
  ulint               n_threads;    // 清除线程数（默认 4）
  UT_LIST_BASE_NODE_T(purge_thr_t) threads;  // 线程链表
  page_cleaner_t*     page_cleaner; // 页清除器
};

// 清除流程:
void purge_thread() {
  while (true) {
    // 1. 获取需要清除的删除记录
    ulint limit = srv_max_n_pending_purge_threads;
    queue = purge_get_updates_to_apply(limit);
    
    // 2. 标记删除的记录: 将 record_header 的 delete_mask 设为 1
    //    但物理数据不删除（等待后续 merge）
    
    // 3. 清理无效版本: 删除已不在任何 ReadView 版本链中的记录
    
    // 4. 释放被标记删除的记录占用的空间
    //    在页分裂/合并时自动回收
    
    // 5. 刷新到磁盘
    buf_flush_write_block(dirty_pages);
  }
}

// 注意: InnoDB 不立即物理删除记录，而是标记删除（lazy cleanup）
// 这是 InnoDB 写优化的核心: 写少、读多时性能好
// 代价: 随着删除累积，查询性能下降（需要遍历更多无效记录）
```

---

## 5. 锁协议深度分析

### 5.1 锁管理器（lock0lock.h）

```c
// 锁数据结构:
struct lock_t {
  ut_list_node_t      gen_list;    // 全局锁链表
  ut_list_node_t      thr_list;    // 线程锁链表
  ulint               type_mode;   // 锁类型 + 锁模式
  ulint               n_extrinsic; // 互斥锁数量
  trx_t*              trx;         // 持有锁的事务
  dict_index_t*       index;       // 锁所在的索引
  rec_t*              rec;         // 锁住的记录
  mem_block_info_t*   block_info;  // 内存块信息
};

// 锁模式（type_mode）:
// LOCK_X: 排他锁（Exclusive）
// LOCK_S: 共享锁（Shared）
// LOCK_IS: 意向共享锁（Intent Shared）
// LOCK_IX: 意向排他锁（Intent Exclusive）
// LOCK_AUTO_INC: 自增锁（Auto-Increment）
// LOCK_WAIT: 等待锁（标记该锁正在等待）
// LOCK_WAIT_UPDATE: 更新锁（用于当前读 + 更新）

// 锁类型（type）:
// LOCK_REC: 记录锁（Record Lock）
// LOCK_GAP: 间隙锁（Gap Lock）
// LOCK_ORD: 排序间隙锁（Ordinary Gap Lock）
// LOCK_TABLE: 表锁
// LOCK_PRED: 预测锁（用于 MVCC 优化）
```

### 5.2 Next-Key Lock 的源码实现

```c
// lock0lock.cc — Next-Key Lock 加锁逻辑
static dberr_t lock_rec_convert_impl_to_extrinsic(
  lock_t* lock,         // 锁对象
  dict_index_t* index,  // 索引
  rec_t* rec,           // 记录
  ulint mode)           // 锁模式
{
  // Next-Key Lock = Record Lock + Gap Lock
  
  // 1. 获取当前记录的前一个记录
  rec_t* prev_rec = rec_get_prev_record_cons(rec, index);
  
  // 2. 在 prev_rec 和 rec 之间的间隙上加 Gap Lock
  lock_gap_add(index, prev_rec, rec, mode, trx);
  
  // 3. 在 rec 上加 Record Lock
  lock_rec_add(index, rec, mode, trx);
  
  // 4. 如果 rec 是 supremum（页最大记录），只加 Gap Lock
  if (rec_is_supremum(rec)) {
    lock_gap_add(index, prev_rec, rec, mode, trx);
    return(DB_SUCCESS);
  }
  
  return(DB_SUCCESS);
}

// Gap Lock 的作用:
// 防止其他事务在 (prev_rec, rec) 间隙中插入新记录
// 注意: Gap Lock 只防插入，不防更新/删除（因为 Gap Lock 不锁记录本身）
// 所以 RR 级别下，UPDATE / DELETE 不会触发 Gap Lock（只会触发 Record Lock）
```

### 5.3 锁等待与死锁检测

```c
// lock0lock.cc — 锁等待队列
struct lock_wait_t {
  que_thr_t*          thr;       // 等待的查询线程
  lock_t*             lock;      // 等待的锁
  ulint               type_mode; // 请求的锁模式
  ulint               n_extrinsic; // 互斥锁数
  ulint               wait_time; // 等待时间
};

// 死锁检测算法:
// 1. 构建等待图（Wait-for Graph）
//    节点: 事务
//    边: 事务 A 等待事务 B 持有的锁 → A → B
// 2. 检测环（DFS 遍历）
// 3. 找到环后，选择回滚代价最小的事务

dberr_t lock_deadlock_detect() {
  // 构建等待图
  for_each_waiting_transaction(w) {
    for_each_holding_transaction(h) {
      if (w->waiting_for == h->lock) {
        add_edge(w->trx, h->trx);
      }
    }
  }
  
  // DFS 检测环
  if (find_cycle()) {
    // 选择回滚代价最小的事务
    trx_t* victim = select_victim();  // 基于 undo_log 大小 / 已修改行数
    trx_rollback(victim);
    return(DB_DEADLOCK);
  }
  
  return(DB_SUCCESS);
}

// 死锁预防:
// InnoDB 默认: 检测+回滚（detect and rollback）
// 可以配置: innodb_deadlock_detect=0（关闭检测，等待超时）
// 配合: innodb_lock_wait_timeout=50（默认50秒）
```

---

## 6. XA 两阶段提交 — 源码级

### 6.1 MySQL 事务提交流程

```c
// sql/handler.cc::ha_commit_low() — 事务提交
int ha_commit_low(
  THD* thd,
  bool all,
  bool xid_has_gtid)
{
  // Step 1: 存储引擎层提交（InnoDB）
  // 写入 Redo Log，标记事务为已提交
  innobase_commit(thd->trx);
  
  // Step 2: 写入 binlog
  // 这是两阶段提交的关键步骤
  mysql_bin_log.write(thd->xid, thd->query(), thd->query_length);
  mysql_bin_log.flush();  // fsync
  
  // Step 3: 通知存储引擎正式提交
  innobase_prepare(thd->trx);  // PREPARE 阶段
  innobase_commit(thd->trx);   // COMMIT 阶段
  
  return(DB_SUCCESS);
}

// 两阶段提交的关键:
// 1. Redo Log 先写入磁盘（innodb_flush_log_at_trx_commit=1）
// 2. binlog 写入磁盘
// 3. 如果步骤 2 失败但步骤 1 成功 → 回滚（通过 undo log）
// 4. 如果步骤 3 失败但步骤 2 成功 → 重试（通过 binlog 重放）
```

### 6.2 XA 分布式事务

```c
// XA 规范: X/Open XA 标准
// 两阶段: PREPARE → COMMIT / ROLLBACK

// MySQL XA 实现:
// XA START 'tx_id'  ← 开始 XA 事务
// XA END 'tx_id'    ← 结束 XA 事务
// XA PREPARE 'tx_id' ← 准备阶段
// XA COMMIT 'tx_id'  ← 提交阶段
// XA ROLLBACK 'tx_id'← 回滚

// PREPARE 阶段（源码: ha_innobase::xa_prepare()）:
int ha_innobase::xa_prepare() {
  // 1. 写入 XA 日志
  xid_log.write();
  
  // 2. 写入 Redo Log（标记为 PREPARED）
  redo_log.write(PREPARED_STATE);
  
  // 3. 返回 PREPARED 给 Coordinator
  return(DB_PREPARED);
}

// COMMIT 阶段（源码: ha_innobase::xa_commit()）:
int ha_innobase::xa_commit() {
  // 1. 确认所有参与者返回 PREPARED
  // 2. 写入 Redo Log（标记为 COMMITTED）
  redo_log.write(COMMITTED_STATE);
  
  // 3. 清理 XA 日志
  xid_log.cleanup();
  
  return(DB_SUCCESS);
}

// XA 的性能问题:
// 1. 两阶段提交需要等待所有参与者响应 → 高延迟
// 2. 参与者持有锁直到 commit → 锁持有时间长
// 3. Coordinator 单点故障 → 需要分布式协调
```

### 6.3 binlog 与 Redo Log 的一致性

```c
// 关键参数:
// innodb_flush_log_at_trx_commit = 1  // redo log 每次提交刷盘
// sync_binlog = 1                      // binlog 每次提交刷盘

// 为什么需要两阶段提交?
// 因为 Redo Log 和 binlog 是分开写的，可能出现不一致:

// 场景: 事务 T
// 1. 写 Redo Log（标记 committed）→ fsync
// 2. 写 binlog → fsync  ← 如果这一步失败
// 3. 通知存储引擎提交
// 
// 如果步骤 2 失败:
//   - Redo Log 有记录，崩溃恢复时会重放 → 数据在磁盘上
//   - binlog 没有记录 → 从库不会重放 → 主从不一致
// 
// 解决方案: innodb_flush_log_at_trx_commit=1 + sync_binlog=1
// 保证两个日志同时刷盘，要么都有，要么都没有

// 性能优化: innodb_flush_log_at_trx_commit=2
//   redo log 写入 OS Buffer（不 fsync），每秒刷一次
//   binlog 每次 fsync
//   代价: 可能丢失 1 秒数据（os crash 时 redo log 未刷盘）
```

---

## 7. 存储引擎对比

### 7.1 MVCC 实现对比

```
┌──────────┬──────────────────────┬──────────────────────┬──────────────┐
│          │      InnoDB          │   PostgreSQL         │  SQLite      │
├──────────┼──────────────────────┼──────────────────────┼──────────────┤
│ 实现方式 │ Undo Log + ReadView  │ Heap Tuple + xmin/   │ WAL +        │
│          │                      │ xmax 标记            │ 多版本页面   │
├──────────┼──────────────────────┼──────────────────────┼──────────────┤
│ RC       │ 每次 SELECT 创建     │ 每次 SELECT 创建     │ 不适用(无    │
│          │ ReadView             │ ReadView             │ 隔离级别    │
├──────────┼──────────────────────┼──────────────────────┼──────────────┤
│ RR       │ 首次 SELECT 创建     │ 每次 SELECT 创建     │ 不适用       │
│          │ ReadView 并复用      │ (通过 xmin/xmax       │              │
│          │                      │ 实现快照)             │              │
├──────────┼──────────────────────┼──────────────────────┼──────────────┤
│ 版本链   │ Undo Log 中的        │ Heap 页中的           │ 独立版本页面  │
│          │ undo 记录            │ tuple 版本链         │              │
├──────────┼──────────────────────┼──────────────────────┼──────────────┤
│ 冲突检测 │ 无乐观锁            │ 乐观锁 (xmin/xmax)   │ 无           │
│          │                      │ 冲突时回滚            │              │
└──────────┴──────────────────────┴──────────────────────┴──────────────┘

PostgreSQL MVCC 实现细节:
  Heap Tuple 结构:
    - xmin: 创建该元组的事务 ID
    - xmax: 删除/更新该元组的事务 ID
    - ctid: 指向当前版本的物理位置 (block, offset)
  
  查询时的可见性判断:
    - xmin < 当前事务可见 → 可见
    - xmax != 0 且 xmax < 当前事务可见 → 被删除，不可见
    - xmin > 当前事务可见 → 未提交，不可见（当前读）
  
  特点: 
  - 每次 UPDATE 都会产生新版本，旧版本不立即删除
  - VACUUM 进程定期清理死元组
  - 没有 Undo Log 概念，版本链在 Heap 页中
```

### 7.2 锁机制对比

```
┌──────────┬────────────┬──────────────┬──────────────────┐
│          │  InnoDB    │  PostgreSQL  │    Redis         │
├──────────┼────────────┼──────────────┼──────────────────┤
│ 行锁     │ Next-Key   │ Heap Lock    │ 无（单线程+     │
│          │ Lock       │              │  乐观并发）      │
├──────────┼────────────┼──────────────┼──────────────────┤
│ 表锁     │ MDL (元    │ AccessShare/ │ 无（所有操作    │
│          │ 数据锁)    │ AccessExclusive│  原子执行）    │
├──────────┼────────────┼──────────────┼──────────────────┤
│ 分布式   │ XA /       │ XA /         │ 无（单实例）     │
│ 锁       │ 2PC        │ 分布式锁     │                  │
├──────────┼────────────┼──────────────┼──────────────────┤
│ 乐观锁   │ 无         │ xmin/xmax    │ WATCH/MULTI      │
└──────────┴────────────┴──────────────┴──────────────────┘
```

---

## 8. 实战排障

### 8.1 InnoDB 死锁调试

```sql
-- 查看当前锁等待
SELECT * FROM information_schema.innodb_locks;
SELECT * FROM information_schema.innodb_lock_waits;

-- MySQL 8.0+ 更直观
SELECT * FROM performance_schema.data_locks;
SELECT * FROM performance_schema.data_lock_waits;

-- 最近死锁信息
SHOW ENGINE INNODB STATUS\G
-- 查看 LATEST DETECTED DEADLOCK 部分

-- 监控死锁次数
SHOW STATUS LIKE 'Innodb_deadlocks';
```

### 8.2 慢查询优化 — 执行计划深度分析

```sql
-- 完整执行计划
EXPLAIN ANALYZE SELECT * FROM user WHERE age = 25 AND city = '北京';

-- 关注字段:
-- type: ALL/index/range/ref/eq_ref/const/system
-- key: 实际使用的索引
-- key_len: 索引使用的字节数
-- rows: 预估扫描行数
-- Extra: Using filesort/Using temporary/Using index/Using where

-- 索引优化建议:
-- 1. 避免 Using filesort: 增加 ORDER BY 对应的索引
-- 2. 避免 Using temporary: 优化 GROUP BY 或 JOIN
-- 3. 确保 Using index: 使用覆盖索引
```

---

*本文档基于 MySQL 8.0 InnoDB 源码整理，覆盖内核核心机制与实战*
