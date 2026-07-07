# 程序化广告深度实战：个性化精准投放

## 一、互联网展示广告发展史

### 1.1 广告形态演进

```
传统展示广告 → 程序化展示广告 → 智能展示广告
```

### 1.2 程序化广告定义

**程序化广告**是通过技术手段自动完成广告位购买、售卖和投放的过程。

## 二、程序化广告生态参与者

### 2.1 需求方

| 类型 | 说明 | 示例 |
|------|------|------|
| 广告主 | 投放广告的企业 | Nike, Apple |
| 代理商 | 代理广告主投放 | 4A公司 |
| DSP | 需求方平台 | The Trade Desk |

### 2.2 需求方服务

```
DSP核心功能:
├── 数据接入
├── 算法预估
├── 实时竞价
└── 投放管理
```

### 2.3 流量供应方

| 类型 | 说明 | 示例 |
|------|------|------|
| 媒体 | 提供广告位 | 网站、App |
| SSP | 供应方平台 | PubMatic |
| Ad Exchange | 广告交换平台 | Google AdX |

### 2.4 流量方服务

```
SSP核心功能:
├── 库存管理
├── 价格优化
├── 流量打包
└── 收益最大化
```

### 2.5 广告服务与数据管理

```
DMP核心功能:
├── 数据采集
├── 数据处理
├── 受众分群
└── 数据应用
```

## 三、交易模式

### 3.1 交易模式种类

| 模式 | 说明 | 特点 |
|------|------|------|
| RTB | 实时竞价 | 公开市场，按需购买 |
| PMP | 私有市场 | 邀请制，固定价格 |
| PDB | 程序化直采 | 保证库存，固定价格 |
| PD | 程序化直投 | 非保证库存 |

### 3.2 交易模式差异

```
RTB vs PMP vs PDB:
├── RTB: 公开市场，实时竞价
├── PMP: 私有市场，优先购买
└── PDB: 程序化直采，保证库存
```

### 3.3 交易模式价值

**选择依据：**
- 预算规模
- 投放目标
- 库存需求
- 价格敏感度

## 四、考核指标

### 4.1 广告效果的定义

**核心指标：**

| 指标 | 公式 | 意义 |
|------|------|------|
| CTR | 点击数/展示数 | 广告吸引力 |
| CVR | 转化数/点击数 | 落地页效果 |
| CPC | 花费/点击数 | 获客成本 |
| CPA | 花费/转化数 | 转化成本 |
| ROAS | 收入/花费 | 投资回报率 |

### 4.2 广告效果的层次

```
效果层次:
├── 曝光效果
├── 点击效果
├── 转化效果
└── 商业效果
```

### 4.3 广告效果的评估

**评估方法：**
- A/B测试
- 归因分析
- 增量测试

## 五、广告投放

### 5.1 投放计划

**投放计划要素：**

```
投放计划:
├── 目标设定
├── 预算分配
├── 受众选择
├── 创意准备
└── 排期安排
```

### 5.2 广告策划/提案

**策划流程：**

```
1. 需求分析
2. 策略制定
3. 创意构思
4. 预算规划
5. 效果预估
```

### 5.3 广告投放执行

**执行步骤：**

```
1. 账户搭建
2. 创意上传
3. 定向设置
4. 出价设置
5. 上线投放
```

### 5.4 数据分析及优化调整

**优化策略：**

```
优化方向:
├── 受众优化
├── 创意优化
├── 出价优化
└── 落地页优化
```

### 5.5 项目总结/结案报告

**报告内容：**

```
结案报告:
├── 投放概况
├── 效果分析
├── 问题总结
└── 改进建议
```

## 六、相关技术

### 6.1 RTB竞价逻辑

**竞价流程：**

```
1. 用户访问页面
2. 触发广告请求
3. ADX发送Bid Request
4. DSP接收请求
5. DSP计算出价
6. ADX选择最高出价
7. 返回Winner Ad
8. 广告展示
9. 计费通知
```

**Go 实现RTB竞价：**

```go
package rtb

import (
	"context"
	"fmt"
	"sync"
)

type RTBEngine struct {
	dspClients map[string]DSPClient
	mu         sync.RWMutex
}

type DSPClient interface {
	Bid(ctx context.Context, req *BidRequest) (*BidResponse, error)
}

type BidRequest struct {
	AdSlotID string
	UserID   string
	Device   string
}

type BidResponse struct {
	BidPrice float64
	AdID     string
}

func (e *RTBEngine) ProcessBid(ctx context.Context, req *BidRequest) (*BidResponse, error) {
	e.mu.RLock()
	clients := make([]DSPClient, 0, len(e.dspClients))
	for _, client := range e.dspClients {
		clients = append(clients, client)
	}
	e.mu.RUnlock()
	
	type result struct {
		response *BidResponse
		err      error
	}
	
	ch := make(chan result, len(clients))
	for _, client := range clients {
		go func(c DSPClient) {
			resp, err := c.Bid(ctx, req)
			ch <- result{resp, err}
		}(client)
	}
	
	var winner *BidResponse
	for i := 0; i < len(clients); i++ {
		res := <-ch
		if res.err != nil {
			continue
		}
		if winner == nil || res.response.BidPrice > winner.BidPrice {
			winner = res.response
		}
	}
	
	if winner == nil {
		return nil, fmt.Errorf("no bids received")
	}
	
	return winner, nil
}
```

### 6.2 流量对接

**对接方式：**

```
流量对接:
├── SDK对接
├── API对接
└── 服务器到服务器
```

### 6.3 用户识别与ID映射

**ID类型：**

| 类型 | 说明 | 示例 |
|------|------|------|
| Cookie ID | 浏览器标识 | __cfduid |
| Device ID | 设备标识 | IDFA/OAID |
| User ID | 用户标识 | 登录ID |
| Fingerprint | 设备指纹 | 硬件+软件组合 |

### 6.4 程序化创意

**创意生成：**

```
程序化创意:
├── 模板生成
├── 动态替换
└── A/B测试
```

### 6.5 用户数据中心

**DMP架构：**

```
DMP:
├── 数据采集
├── 数据处理
├── 受众分群
└── 数据应用
```

### 6.6 数据统计原理

**统计方法：**

```
统计:
├── 描述统计
├── 推断统计
└── 预测统计
```

### 6.7 广告验证

**验证方式：**

```
验证:
├── 第三方监测
├── 品牌安全
└── 流量质量
```

### 6.8 算法优化

**优化策略：**

```
优化:
├── 出价优化
├── 定向优化
└── 创意优化
```

## 七、系统实例

### 7.1 DSP系统实例

**DSP核心模块：**

```
DSP:
├── 数据接入
├── 算法预估
├── 实时竞价
└── 投放管理
```

### 7.2 AdX/SSP系统实例

**AdX核心功能：**

```
AdX:
├── 库存管理
├── 竞价撮合
└── 结算计费
```

### 7.3 DMP系统实例

**DMP核心功能：**

```
DMP:
├── 数据采集
├── 数据处理
├── 受众分群
└── 数据应用
```

## 八、总结与展望

### 8.1 买卖双方需求和痛点总结

**买方痛点：**
- 流量质量
- 投放效果
- 成本控制

**卖方痛点：**
- 收益最大化
- 库存利用率
- 用户体验

### 8.2 行业发展的推动因素

**推动因素：**
- 技术进步
- 数据积累
- 市场需求

### 8.3 行业发展的阻碍因素

**阻碍因素：**
- 隐私政策
- 流量作弊
- 标准缺失

### 8.4 对行业发展的展望

**未来趋势：**
- AI驱动
- 隐私保护
- 跨屏投放
- 新兴平台

## 九、自测题

1. 程序化广告的核心优势是什么？
2. RTB、PMP、PDB有什么区别？
3. DSP系统的核心模块有哪些？
4. 如何进行有效的广告投放优化？

## 十、动手验证

```bash
# 1. 实现RTB竞价引擎
# 2. 实现DMP基础功能
# 3. 实现程序化创意生成
# 4. 实现广告投放优化
```
