# CLI 工具开发实战指南

## 一、入门引导

CLI 工具是开发者日常最高频使用的工具之一，好的 CLI 设计能大幅提升效率。

### 1.1 为什么需要 CLI 工具？

- **自动化**：替代重复的手动操作
- **标准化**：统一团队操作规范
- **可复用**：一次编写，处处使用
- **可集成**：与其他工具管道对接

### 1.2 主流 CLI 框架对比

| 框架 | 语言 | 特点 | 适用场景 |
|------|------|------|----------|
| Cobra | Go | 功能最全，生态最好 | 大型 CLI 项目 |
|spf13/Viper | Go | 配置管理 | 配合 Cobra 使用 |
|urion | Python | 简洁优雅 | 快速原型 |
|Click | Python | 插件化 | 复杂子命令 |
|Argparse | Python | 标准库 | 简单脚本 |
|Clap | Rust | 零成本抽象 | 高性能需求 |

## 二、Go CLI 开发实战

### 2.1 Cobra 框架核心结构

```go
package main

import (
    "fmt"
    "github.com/spf13/cobra"
    "github.com/spf13/viper"
)

var (
    verbose    bool
    configFile string
    outputFormat string
)

// rootCmd 根命令
var rootCmd = &cobra.Command{
    Use:   "mycli",
    Short: "My CLI Tool",
    Long:  `My CLI Tool is a powerful command-line interface tool`,
    Run: func(cmd *cobra.Command, args []string) {
        fmt.Println("Hello, World!")
    },
}

// Execute 启动 CLI
func Execute() {
    if err := rootCmd.Execute(); err != nil {
        fmt.Fprintln(os.Stderr, err)
        os.Exit(1)
    }
}

func init() {
    // 绑定标志
    rootCmd.PersistentFlags().BoolVarP(&verbose, "verbose", "v", false, "verbose output")
    rootCmd.Flags().StringVarP(&configFile, "config", "c", "", "config file")
    rootCmd.Flags().StringVarP(&outputFormat, "format", "f", "json", "output format: json|yaml|table")
    
    // 绑定 Viper
    viper.BindPFlag("verbose", rootCmd.PersistentFlags().Lookup("verbose"))
    viper.BindPFlag("config", rootCmd.Flags().Lookup("config"))
}

// subCmd 子命令
var subCmd = &cobra.Command{
    Use:   "sub",
    Short: "Sub command",
    Run: func(cmd *cobra.Command, args []string) {
        if verbose {
            fmt.Println("Verbose mode enabled")
        }
        fmt.Printf("Config: %s, Format: %s\n", configFile, outputFormat)
    },
}

func init() {
    rootCmd.AddCommand(subCmd)
}

func main() {
    Execute()
}
```

### 2.2 Cobra 最佳实践

```go
// 1. 命令分组
func init() {
    rootCmd.AddCommand(
        NewDeployCmd(),
        NewBuildCmd(),
        NewTestCmd(),
        NewConfigCmd(),
    )
}

// 2. 预运行钩子
var myCmd = &cobra.Command{
    Use:   "mycommand",
    Short: "My command",
    PreRun: func(cmd *cobra.Command, args []string) {
        // 验证前置条件
        if !checkPrerequisites() {
            cmd.SetOut(os.Stderr)
            cmd.PrintErrln("Error: prerequisites not met")
            os.Exit(1)
        }
    },
    RunE: func(cmd *cobra.Command, args []string) error {
        // 返回错误，Cobra 会自动处理
        return doSomething()
    },
}

// 3. 使用 viper 配置
func initConfig() {
    // 1. 命令行 --config flag
    if cfgFile != "" {
        viper.SetConfigFile(cfgFile)
    } else {
        // 2. 环境变量
        viper.AutomaticEnv()
        
        // 3. 默认路径
        home, _ := os.UserHomeDir()
        viper.AddConfigPath(home + "/.mycli")
        viper.SetConfigType("yaml")
    }
    
    if err := viper.ReadInConfig(); err != nil {
        // 配置文件不存在是允许的
        if _, ok := err.(viper.ConfigFileNotFoundError); !ok {
            log.Fatal(err)
        }
    }
}

// 4. 交互式输入
func interactiveInput(prompt string) string {
    reader := bufio.NewReader(os.Stdin)
    fmt.Print(prompt)
    input, _ := reader.ReadString('\n')
    return strings.TrimSpace(input)
}

// 5. 进度条
func progressBar(current, total int, msg string) {
    percent := float64(current) / float64(total) * 100
    fmt.Printf("\r%s: %.1f%% (%d/%d)", msg, percent, current, total)
    if current == total {
        fmt.Println()
    }
}
```

### 2.3 表格输出

```go
package main

import (
    "os"
    "github.com/olekukonko/tablewriter"
)

func printTable(data [][]string) {
    table := tablewriter.NewWriter(os.Stdout)
    table.SetHeader([]string{"Name", "Status", "Age"})
    table.SetAlignment(tablewriter.ALIGN_LEFT)
    table.SetRowSeparator("-")
    table.SetRowLine(true)
    table.SetColWidth(30)
    table.AppendBulk(data)
    table.Render()
}
```

## 三、Python CLI 开发

### 3.1 Click 框架

```python
import click
import yaml
import json

@click.group()
@click.option('--verbose', '-v', is_flag=True, help='Verbose output')
@click.pass_context
def cli(ctx, verbose):
    """My CLI Tool"""
    ctx.ensure_object(dict)
    ctx.obj['VERBOSE'] = verbose

@cli.command()
@click.argument('name')
@click.option('--output', '-o', type=click.Path(), help='Output file')
@click.option('--format', '-f', type=click.Choice(['json', 'yaml', 'table']), default='table')
@click.pass_context
def deploy(ctx, name, output, format):
    """Deploy a service"""
    verbose = ctx.obj['VERBOSE']
    if verbose:
        click.echo(f"Deploying {name} with format {format}")
    
    # 实际部署逻辑
    result = {"name": name, "status": "success"}
    
    if output:
        with open(output, 'w') as f:
            if format == 'json':
                json.dump(result, f, indent=2)
            elif format == 'yaml':
                yaml.dump(result, f)
    else:
        if format == 'json':
            click.echo(json.dumps(result, indent=2))
        elif format == 'yaml':
            click.echo(yaml.dump(result))
        else:
            click.secho(f"Name: {name}\nStatus: {result['status']}", fg='green')

@cli.command()
@click.option('--config', '-c', type=click.Path(exists=True), help='Config file')
def config(config):
    """Show configuration"""
    if config:
        with open(config) as f:
            click.echo(f.read())
    else:
        click.echo("No config file specified")

if __name__ == '__main__':
    cli()
```

### 3.2 进度条与动画

```python
from tqdm import tqdm
import time

def download_with_progress(urls):
    for url in tqdm(urls, desc="Downloading", unit="file"):
        # 模拟下载
        time.sleep(0.1)
    click.echo("\nDownload complete!")

def spinner(message):
    """终端旋转动画"""
    import sys
    import time
    spin = ['|', '/', '-', '\\']
    idx = 0
    while True:
        sys.stdout.write(f'\r{message} {spin[idx]}')
        sys.stdout.flush()
        idx = (idx + 1) % len(spin)
        time.sleep(0.1)

# 使用
# spinner("Processing...")
```

## 四、Shell 脚本最佳实践

### 4.1 基础模板

```bash
#!/usr/bin/env bash
set -euo pipefail

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 日志函数
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; }

# 用法
usage() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] COMMAND

Commands:
  deploy    Deploy application
  build     Build project
  test      Run tests

Options:
  -h, --help      Show help
  -v, --verbose   Verbose output
  -f, --force     Force operation
EOF
    exit 1
}

# 参数解析
VERBOSE=false
FORCE=false
COMMAND=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help) usage ;;
        -v|--verbose) VERBOSE=true; shift ;;
        -f|--force) FORCE=true; shift ;;
        -*) log_error "Unknown option: $1"; usage ;;
        *) COMMAND="$1"; shift ;;
    esac
done

# 命令分发
case $COMMAND in
    deploy)
        log_info "Deploying..."
        if $VERBOSE; then
            echo "Verbose mode enabled"
        fi
        ;;
    build)
        log_info "Building..."
        ;;
    test)
        log_info "Running tests..."
        ;;
    "")
        log_error "No command specified"
        usage
        ;;
    *)
        log_error "Unknown command: $COMMAND"
        usage
        ;;
esac
```

### 4.2 错误处理

```bash
# 捕获错误信号
trap 'log_error "Script failed at line $LINENO"; exit 1' ERR

# 捕获退出信号
trap 'log_info "Cleaning up..."; exit 0' INT TERM

# 检查命令执行结果
run_cmd() {
    local cmd="$1"
    shift
    if $VERBOSE; then
        log_info "Running: $cmd $@"
    fi
    if ! "$cmd" "$@"; then
        log_error "Command failed: $cmd $@"
        return 1
    fi
}

# 使用
run_cmd docker build -t myapp .
run_cmd docker push myapp:latest
```

## 五、自测题

### 5.1 选择题

1. Cobra 框架中，哪个方法用于定义子命令？
   - A) AddCommand()
   - B) SetCommand()
   - C) RegisterCommand()
   - D) AppendCommand()

2. Click 框架中，`@click.pass_context` 装饰器的作用是什么？
   - A) 传递命令行参数
   - B) 传递上下文对象
   - C) 传递环境变量
   - D) 传递配置文件

3. Shell 脚本中 `set -euo pipefail` 的含义是什么？
   - A) 启用错误处理、未定义变量检查、管道失败传播
   - B) 启用调试模式
   - C) 启用颜色输出
   - D) 启用并行执行

### 5.2 编程题

1. 使用 Cobra 创建一个 CLI 工具，支持以下命令：
   - `mycli deploy --env production --verbose`
   - `mycli build --target linux/amd64`
   - `mycli test --coverage`

2. 使用 Click 创建一个文件批量重命名工具

## 六、动手验证

```bash
# 1. 安装 Cobra
go get github.com/spf13/cobra@latest
go get github.com/spf13/viper@latest

# 2. 创建项目
mkdir mycli && cd mycli
go mod init mycli

# 3. 编写 main.go
cat > main.go << 'EOF'
package main

import (
    "fmt"
    "github.com/spf13/cobra"
)

var rootCmd = &cobra.Command{
    Use:   "mycli",
    Short: "My CLI Tool",
    Run: func(cmd *cobra.Command, args []string) {
        fmt.Println("Hello from mycli!")
    },
}

func main() {
    if err := rootCmd.Execute(); err != nil {
        fmt.Println(err)
        os.Exit(1)
    }
}
EOF

# 4. 构建并测试
go build -o mycli .
./mycli --help
./mycli
```
