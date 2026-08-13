#!/bin/bash
#
# 广告平台 Skills 一键部署脚本
# 用于在任何机器上快速部署 Skills 到 pi 系统
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILLS_SOURCE="$REPO_ROOT/knowledge/skills"
SKILLS_TARGET="$HOME/.agents/skills"

echo "🔧 广告平台 Skills 部署脚本"
echo "================================"
echo ""

# 检查源目录
if [ ! -d "$SKILLS_SOURCE" ]; then
    echo "❌ 错误: Skills 源目录不存在: $SKILLS_SOURCE"
    exit 1
fi

# 检查目标目录
if [ ! -d "$SKILLS_TARGET" ]; then
    echo "📁 创建目标目录: $SKILLS_TARGET"
    mkdir -p "$SKILLS_TARGET"
fi

# 复制 Skills
echo "📦 部署 Skills..."
skills_dirs=$(find "$SKILLS_SOURCE" -maxdepth 1 -type d -name "*expert" -o -name "*tools")

for skill_dir in $skills_dirs; do
    skill_name=$(basename "$skill_dir")
    skill_md="$skill_dir/SKILL.md"
    target_dir="$SKILLS_TARGET/$skill_name"
    
    if [ -f "$skill_md" ]; then
        echo "  → $skill_name"
        mkdir -p "$target_dir"
        cp "$skill_md" "$target_dir/SKILL.md"
    fi
done

echo ""
echo "✅ 部署完成！"
echo ""
echo "📍 Skills 已安装到: $SKILLS_TARGET"
echo ""
echo "🎯 下一步:"
echo "   1. 配置凭证:"
echo "      cp $REPO_ROOT/config/ad_platform_credentials_template.json $REPO_ROOT/config/ad_platform_credentials.json"
echo "      nano $REPO_ROOT/config/ad_platform_credentials.json"
echo ""
echo "   2. 测试连接:"
echo "      cd $REPO_ROOT"
echo "      python3 scripts/ad_platform_api.py --all --test"
echo ""
echo "   3. 重启 pi 使 Skills 生效"
echo ""
