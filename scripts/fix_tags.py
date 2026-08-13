#!/usr/bin/env python3
"""知识库标签规范化脚本"""
import re
import sys
from pathlib import Path

def is_valid_tag(tag: str) -> bool:
    tag = tag.strip()
    if not tag or len(tag) < 2:
        return False
    invalid = {'#', '# ', '#\n', '1', '2', '3', '查看', '分析', '定位', '抓取'}
    if tag in invalid:
        return False
    if tag[0].isdigit():
        return False
    if re.match(r'^[\d\s\.\(\)\{\}\[\]:]+$', tag):
        return False
    return True

def fix_file_tags(file_path: Path) -> int:
    try:
        content = file_path.read_text(encoding='utf-8')
    except:
        return 0
    lines = content.split('\n')
    new_lines = []
    in_frontmatter = False
    fixed = 0
    for line in lines:
        if line.strip() == '---':
            in_frontmatter = not in_frontmatter
            new_lines.append(line)
            continue
        if not in_frontmatter and line.startswith('# ') and not line.startswith('##'):
            tag_content = line[2:].strip()
            if not is_valid_tag(tag_content):
                fixed += 1
                continue
        new_lines.append(line)
    if fixed > 0:
        file_path.write_text('\n'.join(new_lines), encoding='utf-8')
    return fixed

def main():
    kb_root = Path("/Users/yanping.ma/ryan-personal-knowledge/knowledge")
    total_files = total_fixed = 0
    print(f"🔧 开始修复标签: {kb_root}")
    for md_file in kb_root.rglob("*.md"):
        if not md_file.exists():
            continue
        total_files += 1
        fixed = fix_file_tags(md_file)
        total_fixed += fixed
        if total_files % 200 == 0:
            print(f"   已处理 {total_files} 文件，修复 {total_fixed} 个")
    print(f"✅ 完成: 处理 {total_files} 文件，修复 {total_fixed} 个无效标签")
    return 0

if __name__ == "__main__":
    sys.exit(main())
