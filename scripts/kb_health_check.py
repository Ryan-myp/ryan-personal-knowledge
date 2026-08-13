#!/usr/bin/env python3
"""
知识库健康度检查工具
检查断链、孤儿页面、内容质量、重复文件等
"""

import sys
import re
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Any

# 配置
KB_ROOT = Path(__file__).parent.parent / "knowledge"
EXCLUDE_DIRS = {".git", "__pycache__", ".cache", "node_modules"}
MIN_DOC_LINES = 50  # 最小文档行数
MAX_DOC_LINES = 3000  # 最大文档行数


class KBHealthChecker:
    def __init__(self, kb_root: Path):
        self.kb_root = kb_root
        self.stats = {
            "total_files": 0,
            "total_lines": 0,
            "total_dirs": 0,
            "by_domain": defaultdict(int),
            "broken_links": [],
            "orphan_pages": [],
            "too_short": [],
            "too_long": [],
            "duplicate_titles": [],
        }
    
    def collect_files(self) -> List[Path]:
        """收集所有 Markdown 文件"""
        files = []
        for md_file in self.kb_root.rglob("*.md"):
            # 排除特定目录
            if any(excl in str(md_file) for excl in EXCLUDE_DIRS):
                continue
            files.append(md_file)
        return files
    
    def analyze_domain(self, file_path: Path) -> str:
        """分析文件所属领域"""
        rel_path = file_path.relative_to(self.kb_root)
        parts = rel_path.parts
        if len(parts) > 1:
            return parts[0]
        return "root"
    
    def check_links(self, files: List[Path]) -> List[Dict]:
        """检查断链"""
        broken = []
        all_titles = set()
        
        # 收集所有标题
        for f in files:
            try:
                content = f.read_text(encoding="utf-8")
                titles = re.findall(r'^#\s+(.+)$', content, re.MULTILINE)
                all_titles.update(t.lower() for t in titles)
            except:
                pass
        
        # 检查 wikilinks
        link_pattern = re.compile(r'\[\[([^\]|]+)')
        for f in files:
            try:
                content = f.read_text(encoding="utf-8")
                for match in link_pattern.finditer(content):
                    link = match.group(1).strip()
                    if link and link not in all_titles:
                        broken.append({
                            "file": str(f.relative_to(self.kb_root)),
                            "link": link,
                            "type": "broken_link"
                        })
            except:
                pass
        
        return broken
    
    def check_content_quality(self, files: List[Path]) -> Tuple[List[Dict], List[Dict]]:
        """检查内容质量"""
        too_short = []
        too_long = []
        
        for f in files:
            try:
                content = f.read_text(encoding="utf-8")
                lines = content.count('\n') + 1
                
                if lines < MIN_DOC_LINES:
                    too_short.append({
                        "file": str(f.relative_to(self.kb_root)),
                        "lines": lines,
                        "type": "too_short"
                    })
                elif lines > MAX_DOC_LINES:
                    too_long.append({
                        "file": str(f.relative_to(self.kb_root)),
                        "lines": lines,
                        "type": "too_long"
                    })
            except:
                pass
        
        return too_short, too_long
    
    def check_duplicates(self, files: List[Path]) -> List[Dict]:
        """检查重复标题"""
        title_map = defaultdict(list)
        
        for f in files:
            try:
                content = f.read_text(encoding="utf-8")
                first_heading = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                if first_heading:
                    title = first_heading.group(1).strip().lower()
                    title_map[title].append(str(f.relative_to(self.kb_root)))
            except:
                pass
        
        duplicates = []
        for title, paths in title_map.items():
            if len(paths) > 1:
                duplicates.append({
                    "title": title,
                    "files": paths,
                    "type": "duplicate_title"
                })
        
        return duplicates
    
    def run(self) -> Dict[str, Any]:
        """运行所有检查"""
        print(f"📊 开始检查知识库: {self.kb_root}")
        print("=" * 60)
        
        # 收集文件
        files = self.collect_files()
        self.stats["total_files"] = len(files)
        print(f"📁 发现 {len(files)} 个 Markdown 文件")
        
        # 统计领域分布
        for f in files:
            domain = self.analyze_domain(f)
            self.stats["by_domain"][domain] += 1
        
        print("\n📈 领域分布:")
        for domain, count in sorted(self.stats["by_domain"].items(), 
                                     key=lambda x: -x[1])[:10]:
            print(f"   {domain}: {count} 文件")
        
        # 检查链接
        print("\n🔗 检查断链...")
        self.stats["broken_links"] = self.check_links(files)
        print(f"   发现 {len(self.stats['broken_links'])} 个潜在断链")
        
        # 检查内容质量
        print("\n📝 检查内容质量...")
        self.stats["too_short"], self.stats["too_long"] = self.check_content_quality(files)
        print(f"   过短(<{MIN_DOC_LINES}行): {len(self.stats['too_short'])} 篇")
        print(f"   过长(>{MAX_DOC_LINES}行): {len(self.stats['too_long'])} 篇")
        
        # 检查重复
        print("\n🔄 检查重复标题...")
        self.stats["duplicate_titles"] = self.check_duplicates(files)
        print(f"   发现 {len(self.stats['duplicate_titles'])} 组重复标题")
        
        # 计算健康度
        total_issues = (len(self.stats["broken_links"]) + 
                       len(self.stats["too_short"]) + 
                       len(self.stats["duplicate_titles"]))
        max_issues = len(files) * 0.1  # 允许 10% 的问题率
        health_score = max(0, 100 - (total_issues / max(1, len(files)) * 100))
        self.stats["health_score"] = round(health_score, 1)
        
        print("\n" + "=" * 60)
        print(f"🏥 健康度评分: {self.stats['health_score']}/100")
        
        return self.stats


def main():
    checker = KBHealthChecker(KB_ROOT)
    stats = checker.run()
    
    # 输出详细问题
    if stats["broken_links"]:
        print("\n⚠️  断链详情:")
        for bl in stats["broken_links"][:10]:
            print(f"   {bl['file']} → [[{bl['link']}]]")
    
    if stats["too_short"]:
        print("\n⚠️  过短文档:")
        for ts in stats["too_short"][:10]:
            print(f"   {ts['file']} ({ts['lines']} 行)")
    
    if stats["duplicate_titles"]:
        print("\n⚠️  重复标题:")
        for dt in stats["duplicate_titles"][:5]:
            print(f"   '{dt['title']}': {dt['files']}")
    
    return 0 if stats["health_score"] >= 90 else 1


if __name__ == "__main__":
    sys.exit(main())
