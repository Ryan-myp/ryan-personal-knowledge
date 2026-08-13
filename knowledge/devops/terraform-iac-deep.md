# Terraform IaC实战 - 资深专家深度实现

## 一、核心概念

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Terraform架构                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Provider      Resource     State       Module        Workspace         │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│   │ AWS      │ │ EC2      │ │ local.tf │ │ network  │ │ production  │  │
│   │ Azure    │ │ S3       │ │ remote   │ │ compute  │ │ staging     │  │
│   │ K8s      │ │ RDS      │ │ state    │ │ security │ │ development │  │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘ └─────────────┘  │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Provider配置

```hcl
# providers.tf
terraform {
  required_version = ">= 1.0.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
  
  backend "s3" {
    bucket         = "terraform-state-ryan"
    key            = "production/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "terraform"
      Team        = "platform"
    }
  }
}

variable "aws_region" {
  default = "us-east-1"
}

variable "environment" {
  type    = string
  default = "production"
}
```

## 三、资源管理

```hcl
# modules/vpc/main.tf
resource "aws_vpc" "main" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true
  
  tags = {
    Name = "${var.environment}-vpc"
  }
}

resource "aws_subnet" "public" {
  count             = length(var.public_subnets)
  vpc_id            = aws_vpc.main.id
  cidr_block        = var.public_subnets[count.index]
  availability_zone = var.azs[count.index]
  
  map_public_ip_on_launch = true
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

output "vpc_id" {
  value = aws_vpc.main.id
}

output "public_subnet_ids" {
  value = aws_subnet.public[*].id
}
```

## 四、State管理

```go
package tfstate

import (
    "encoding/json"
    "fmt"
)

// State 资源状态
type State struct {
    Version    int               `json:"version"`
    Serial     int               `json:"serial"`
    Lineage    string            `json:"lineage"`
    Resources  []Resource        `json:"resources"`
    Outputs    map[string]Output `json:"outputs"`
}

type Resource struct {
    Type     string          `json:"type"`
    Name     string          `json:"name"`
    Provider string          `json:"provider"`
    Instances []Instance     `json:"instances"`
}

type Instance struct {
    SchemaVersion int                `json:"schema_version"`
    Attributes    map[string]interface{} `json:"attributes"`
    Dependencies  []string           `json:"dependencies"`
}

// Plan 计划内容
type Plan struct {
    FormatVersion    string            `json:"format_version"`
    TFVersion        string            `json:"terraform_version"`
    PlannedValues    PlannedValues     `json:"planned_values"`
    ResourceChanges  []ResourceChange  `json:"resource_changes"`
}

type ResourceChange struct {
    Address      string            `json:"address"`
    Mode         string            `json:"mode"`
    Type         string            `json:"type"`
    Name         string            `json:"name"`
    Change       Change            `json:"change"`
}

type Change struct {
    Actions   []string          `json:"actions"`
    Before    map[string]interface{} `json:"before"`
    After     map[string]interface{} `json:"after"`
}
```

## 五、面试高频题

### Q1: Terraform State是什么？为什么重要？

```
A:
• State记录了基础设施的实际状态
• 用于追踪资源ID和属性
• 支持依赖关系管理
• 可以锁定防止并发修改
```

### Q2: 如何处理State漂移？

```
A:
• 定期运行 terraform plan 检测漂移
• 使用 terraform import 重新导入
• 配置 CI/CD 流水线自动检测
```

## 六、自测题

1. 如何管理多环境配置？
2. Terraform模块化有什么好处？
3. 如何处理依赖顺序问题？

---

## 参考文档

- [Terraform文档](https://www.terraform.io/docs/)
- [Terraform最佳实践](https://www.terraform-best-practices.com/)
