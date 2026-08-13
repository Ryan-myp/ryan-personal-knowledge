# CLI 工具开发实战

> Cobra、spf13/pflag、交互式终端。

---

## 1. Cobra 命令结构

```go
var rootCmd = &cobra.Command{
    Use:   "adtool",
    Short: "广告平台工具集",
    Long:  "广告平台 CLI 工具集",
}

var getCmd = &cobra.Command{
    Use:   "get [resource]",
    Short: "获取资源",
    Run: func(cmd *cobra.Command, args []string) {
        // ...
    },
}

func init() {
    rootCmd.AddCommand(getCmd)
}
```

---

## 2. 交互式终端

```go
import "github.com/AlecAivazis/survey"

var question = &survey.Select{
    Message: "选择广告平台:",
    Options: []string{"Facebook", "Google", "TikTok"},
}
var selected string
survey.AskOne(question, &selected)
```

---

## 3. 输出格式化

```go
// Table 输出
table := tablewriter.NewWriter(os.Stdout)
table.SetHeader([]string{"平台", "预算", "状态"})
table.AppendRow([]string{"Facebook", "$1000", "active"})
table.Render()

// JSON 输出
json.NewEncoder(os.Stdout).Encode(result)
```

---

**参考**: Cobra 官方文档、cli 工具最佳实践
