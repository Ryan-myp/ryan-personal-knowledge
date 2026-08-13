#!/usr/bin/env python3
"""
知识蒸馏简化执行脚本
"""

import asyncio
import sys
sys.path.insert(0, 'scripts')
from distill_engine import DistillationEngine


class SimpleProject:
    """简单项目配置"""
    def __init__(self, name, github_url, branch="main", core_value=""):
        self.name = name
        self.github_url = github_url
        self.branch = branch
        self.core_value = core_value
        self.category = "database"


async def main():
    async with DistillationEngine() as engine:
        projects = [
            ("TiDB", "https://github.com/pingcap/tidb", "master", 
             "pkg/session/session.go", "knowledge/database/tidb-session-deep-dive.md"),
            ("TiKV", "https://github.com/tikv/tikv", "master",
             "src/server/service/kv.rs", "knowledge/database/tikv-kv-service-deep-dive.md"),
        ]
        
        for name, url, branch, path, doc_path in projects:
            print(f"🔥 执行: {name}")
            project = SimpleProject(name, url, branch)
            
            content = await engine.fetch_source(project, path)
            if content:
                print(f"   ✅ 获取源码: {len(content)} chars")
                engine.generate_document(project, {path: content}, doc_path)
                print(f"   📄 生成文档: {doc_path}")
            else:
                print(f"   ❌ 获取失败")
            print()


if __name__ == "__main__":
    asyncio.run(main())
