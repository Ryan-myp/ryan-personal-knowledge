# Web3 智能合约与边缘计算深度实战

## 一、Web3 智能合约

### 1.1 智能合约架构

```
智能合约结构:
├── 状态变量 (Storage)
│   └── 持久化数据
├── 函数 (Functions)
│   ├── 纯函数 (Pure)
│   ├── 视图函数 (View)
│   └── 修改状态函数
├── 事件 (Events)
│   └── 链下监听
└── 修饰器 (Modifiers)
    └── 权限控制
```

### 1.2 Solidity 实战

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract AdToken {
    address public owner;
    mapping(address => uint256) public balances;
    mapping(address => mapping(address => uint256)) public allowances;
    
    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    
    constructor() {
        owner = msg.sender;
        balances[msg.sender] = 1000000 * 10**18;
    }
    
    modifier onlyOwner() {
        require(msg.sender == owner, "Not owner");
        _;
    }
    
    function transfer(address to, uint256 amount) public returns (bool) {
        require(balances[msg.sender] >= amount, "Insufficient balance");
        require(to != address(0), "Invalid address");
        
        balances[msg.sender] -= amount;
        balances[to] += amount;
        
        emit Transfer(msg.sender, to, amount);
        return true;
    }
    
    function approve(address spender, uint256 amount) public returns (bool) {
        allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }
}
```

## 二、边缘计算

### 2.1 边缘计算架构

```
边缘计算层级:
├── 云端 (Cloud)
│   ├── 集中训练
│   └── 全局管理
├── 边缘节点 (Edge)
│   ├── 模型推理
│   └── 数据预处理
└── 终端设备 (Device)
    ├── 数据采集
    └── 实时响应
```

### 2.2 Go 实现边缘推理

```go
package edge

import (
	"context"
	"log"
	"time"
)

type EdgeNode struct {
	model     Model
	localDB   *LocalDB
	cloudConn *CloudConnection
}

func (e *EdgeNode) Predict(ctx context.Context, data []byte) (*Prediction, error) {
	start := time.Now()
	
	result, err := e.model.Infer(data)
	if err != nil {
		log.Printf("Local infer failed: %v", err)
		return e.cloudConn.RemoteInfer(ctx, data)
	}
	
	e.localDB.Save(result)
	log.Printf("Prediction completed in %v", time.Since(start))
	return result, nil
}
```

## 三、自测题

1. 智能合约的核心组件有哪些？
2. 边缘计算相比云计算有什么优势？

## 四、动手验证

```bash
# 1. 部署智能合约
# 2. 测试边缘推理
# 3. 监控性能
```
