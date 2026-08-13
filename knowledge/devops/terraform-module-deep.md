# Terraform 模块开发 - 资深专家深度实现

## 一、模块结构

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    Terraform 模块结构                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   module/                                                                │
│   ├── main.tf      # 资源定义                                            │
│   ├── variables.tf # 输入变量                                            │
│   ├── outputs.tf   # 输出值                                              │
│   ├── versions.tf  # 版本约束                                            │
│   └── README.md    # 使用说明                                            │
│                                                                         →
└─────────────────────────────────────────────────────────────────────────┘
```

## 二、模块实现

```hcl
# main.tf
resource "aws_instance" "app" {
  count         = var.instance_count
  ami           = var.ami_id
  instance_type = var.instance_type
  
  tags = {
    Name        = "${var.project_name}-app-${count.index}"
    Environment = var.environment
  }
}

# variables.tf
variable "instance_count" {
  description = "实例数量"
  type        = number
  default     = 1
}

variable "ami_id" {
  description = "AMI ID"
  type        = string
}

variable "instance_type" {
  description = "实例类型"
  type        = string
  default     = "t3.micro"
}

# outputs.tf
output "instance_ids" {
  description = "实例ID列表"
  value       = aws_instance.app[*].id
}

output "public_ips" {
  description = "公网IP列表"
  value       = aws_instance.app[*].public_ip
}
```

## 三、模块调用

```hcl
module "app_server" {
  source = "./modules/ec2"
  
  instance_count = 3
  ami_id         = var.ami_id
  instance_type  = "t3.medium"
  project_name   = "my-app"
  environment    = "production"
}

output "app_instance_ids" {
  value = module.app_server.instance_ids
}
```

## 四、面试高频题

### Q1: 模块如何复用？

```
A:
1. 本地模块: source = "./modules/x"
2. 远程模块: source = "git::..."
3. 注册表: source = "app.terraform.io/..."
```

### Q2: 如何处理循环依赖？

```
A:
1. 拆分模块
2. 使用external data
3. 调整资源依赖
```

## 五、自测题

1. 解释模块结构
2. 如何调用模块？
3. 如何处理依赖？

---

## 参考文档

- [Terraform Modules](https://developer.hashicorp.com/terraform/language/modules)
- [Terraform Registry](https://registry.terraform.io/)
