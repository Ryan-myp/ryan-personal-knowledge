# Terraform IaC - 资深专家深度实现

## 一、核心架构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Terraform架构                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   Provider Registry         State File            Backend               │
│   ┌─────────────┐         ┌─────────────┐      ┌─────────────┐         │
│   │   AWS       │         │  local.tf   │      │   S3      │         │
│   │   Azure     │    ───► │  state.json │◄────►│  Remote   │         │
│   │   GCP       │         └─────────────┘      └─────────────┘         │
│   │   ...       │                                              │         │
│   └─────────────┘                                              │         │
│            ▲                                                      ▼         │
│            │                                                 ┌──────────┐   │
│            └─────────────────────────────────────────────────►│  Apply   │   │
│                                                              └──────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、资源定义

```hcl
# 主资源
resource "aws_instance" "web" {
  ami           = var.ami_id
  instance_type = var.instance_type
  
  tags = {
    Name        = "web-server"
    Environment = "production"
  }
  
  lifecycle {
    create_before_destroy = true
  }
}

# 数据源
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]
  
  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-focal-20.04-amd64-server-*"]
  }
}
```

## 三、模块系统

```hcl
# modules/vpc/main.tf
variable "cidr_block" {
  type = string
}

resource "aws_vpc" "main" {
  cidr_block = var.cidr_block
  
  tags = {
    Name = "main-vpc"
  }
}

# main.tf
module "vpc" {
  source     = "./modules/vpc"
  cidr_block = "10.0.0.0/16"
}
```

## 四、面试高频题

### Q1: Terraform状态文件管理？

```
A:
1. 使用远程后端 (S3+DynamoDB)
2. 状态锁定防止并发
3. 状态加密
```

### Q2: 如何处理依赖关系？

```
A:
1. 显式依赖 (depends_on)
2. 引用输出 (outputs)
3. 隐式依赖 (自动检测)
```

## 五、自测题

1. 解释Terraform工作流程
2. 如何实现状态隔离？
3. 如何处理漂移检测？

---

## 参考文档

- [Terraform官方文档](https://developer.hashicorp.com/terraform/docs)
- [Terraform源码](https://github.com/hashicorp/terraform)
