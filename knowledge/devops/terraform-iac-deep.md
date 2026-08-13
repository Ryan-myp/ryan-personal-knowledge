# Terraform IaC - 资深专家深度实现

## 一、核心概念

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Terraform核心概念                                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Provider:                                                              │
│   • AWS / Azure / GCP / K8s                                           │
│   • API封装                                                              │
│                                                                         │
│   Resource:                                                              │
│   • 实际基础设施                                                          │
│   • 声明式配置                                                           │
│                                                                         │
│   State:                                                                 │
│   • 当前状态跟踪                                                          │
│   • 增量更新                                                             │
│                                                                         │
│   Module:                                                                │
│   • 代码复用                                                             │
│   • 层次化组织                                                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、Provider配置

```hcl
terraform {
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
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
```

## 三、Resource定义

```hcl
resource "aws_instance" "web" {
  ami           = data.aws_ami.latest.id
  instance_type = var.instance_type
  
  tags = {
    Name = "${var.environment}-web"
  }
  
  lifecycle {
    create_before_destroy = true
    prevent_destroy       = false
  }
}

resource "aws_autoscaling_group" "web" {
  desired_capacity = var.desired_capacity
  max_size         = var.max_size
  min_size         = var.min_size
  
  tag {
    key                 = "Name"
    value               = "${var.environment}-asg"
    propagate_at_launch = true
  }
}
```

## 四、面试高频题

### Q1: Terraform工作原理？

```
A:
1. 读取配置文件
2. 生成执行计划
3. 应用变更
4. 更新状态
```

### Q2: 如何处理状态冲突？

```
A:
1. 远程状态锁
2. 分支管理
3. 人工审核
```

## 五、自测题

1. 解释Terraform工作流程
2. 如何实现多环境部署？
3. 如何处理敏感数据？

---

## 参考文档

- [Terraform文档](https://www.terraform.io/docs)
- [Terraform源码](https://github.com/hashicorp/terraform)
