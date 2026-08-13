#!/usr/bin/env python3
"""
知识库版本迭代文档清理脚本
将 -v2, -v3 等旧版本文档移动到 archive
"""
import os
import re
import shutil
from pathlib import Path

KB_ROOT = Path("/Users/yanping.ma/ryan-personal-knowledge/knowledge")
ARCHIVE_DIR = KB_ROOT / "archive" / "versioned"

def should_archive(filename: str) -> bool:
    """判断是否应该归档"""
    # 匹配 -v2, -v3 等版本号，但排除 -deep 文档
    if re.search(r'-v\d+\.md$', filename):
        return True
    return False

def main():
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    moved = 0
    for md_file in KB_ROOT.rglob("*.md"):
        if should_archive(md_file.name):
            dest = ARCHIVE_DIR / md_file.name
            # 如果目标已存在，添加时间戳
            if dest.exists():
                stem = md_file.stem
                ext = md_file.suffix
                timestamp = int(md_file.stat().st_mtime)
                dest = ARCHIVE_DIR / f"{stem}_{timestamp}{ext}"
            shutil.move(str(md_file), str(dest))
            moved += 1
            print(f"   归档: {md_file.relative_to(KB_ROOT.parent)}")
    
    print(f"\n✅ 完成: 归档 {moved} 个版本迭代文档")
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())
