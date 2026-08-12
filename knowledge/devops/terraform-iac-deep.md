# Terraform IaC 深度实现

> **文档级别**: Level 5 - 专家级  
> **创建日期**: 2026-08-13  
> **状态**: ✅ 已补齐

---

## 一、State 管理

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      Terraform State 架构                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                │
│   │   Dev       │     │   Staging   │     │   Production│                │
│   │  (独立state) │     │  (独立state)│     │ (独立state) │                │
│   └──────┬──────┘     └──────┬──────┘     └──────┬──────┘                │
│          │                   │                   │                        │
│          └───────────────────┼───────────────────┘                        │
│                              │                                            │
│                    ┌─────────▼─────────┐                                  │
│                    │  Remote Backend   │                                  │
│                    │  (S3 + DynamoDB)  │                                  │
│                    └─────────┬─────────┘                                  │
│                              │                                            │
│                    ┌─────────▼─────────┐                                  │
│                    │   State Locking   │                                   │
│                    │  (DynamoDB)       │                                   │
│                    └───────────────────┘                                  │
│                                                                             │
│  关键设计点:                                                               │
│  • 每个环境独立 state 文件                                                │
│  • 远程存储实现团队协作                                                   │
│  • 状态锁定防止并发修改                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、模块设计模式

```hcl
# 文件: modules/bidding-cluster/main.tf
variable "cluster_name" {
  type = string
}

variable "instance_type" {
  type    = string
  default = "c5.2xlarge"
}

variable "min_size" {
  type    = number
  default = 2
}

variable "max_size" {
  type    = number
  default = 10
}

# ─── VPC 配置 ───
module "vpc" {
  source      = "../../modules/vpc"
  cluster_name = var.cluster_name
}

# ─── ECS Cluster ───
resource "aws_ecs_cluster" "main" {
  name = var.cluster_name
  
  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# ─── Auto Scaling Group ───
resource "aws_autoscaling_group" "main" {
  desired_capacity = var.min_size
  max_capacity     = var.max_size
  min_capacity     = var.min_size
  
  launch_template {
    id      = aws_launch_template.main.id
    version = "$Latest"
  }
  
  tag {
    key                 = "Name"
    value               = var.cluster_name
    propagate_at_launch = true
  }
}

# ─── Output ───
output "cluster_arn" {
  value = aws_ecs_cluster.main.arn
}

output "service_endpoint" {
  value = aws_ecs_service.main.endpoint
}
```

---

## 三、引用模式

```hcl
# 文件: environments/production/main.tf

provider "aws" {
  region = "us-east-1"
}

# ─── 模块引用 ───
module "bidding_cluster" {
  source         = "../../modules/bidding-cluster"
  cluster_name   = "ad-bidding-prod"
  instance_type  = "c5.4xlarge"
  min_size       = 4
  max_size       = 20
}

module "cache_layer" {
  source         = "../../modules/redis-cluster"
  cluster_name   = "ad-cache-prod"
  node_count     = 3
  node_type      = "cache.r6g.large"
}

module "monitoring" {
  source         = "../../modules/monitoring"
  cluster_name   = "ad-bidding-prod"
  retention_days = 30
}

# ─── 数据引用 ───
data "aws_ami" "bidding" {
  most_recent = true
  owners      = ["self"]
  
  filter {
    name   = "name"
    values = ["ad-bidding-ami-*"]
  }
}

# ─── 输出汇总 ───
output "cluster_endpoint" {
  value = module.bidding_cluster.service_endpoint
}

output "cache_endpoint" {
  value = module.cache_layer.cache_endpoint
}
```

---

## 四、参考资料

```
核心文档:
├── Terraform Docs: https://developer.hashicorp.com/terraform/docs
├── AWS Terraform Provider: https://registry.terraform.io/providers/hashicorp/aws
└── Terraform Best Practices: https://www.terraform-best-practices.com/

工具:
├── tflint: 静态检查
├── checkov: 安全扫描
└── tfsec: 合规检查
```

---

*文档版本: v1.0*  
*最后更新: 2026-08-13*  
*作者: Ryan*
