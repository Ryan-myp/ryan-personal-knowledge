#!/usr/bin/env python3
"""
知识蒸馏执行器
自动化获取 GitHub 源码并生成深度蒸馏文档
"""

import asyncio
import aiohttp
import yaml
from pathlib import Path
from datetime import datetime
from typing import Optional
import logging

# 导入配置
from distill_config import DistillProject, get_all_projects, get_projects_by_category

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DistillationEngine:
    """知识蒸馏引擎"""
    
    def __init__(self, kb_root: str = "/Users/yanping.ma/ryan-personal-knowledge"):
        self.kb_root = Path(kb_root)
        self.tmp_dir = self.kb_root / "tmp"
        self.tmp_dir.mkdir(exist_ok=True)
        
        # GitHub API 限流
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        if self.session:
            await self.session.close()
    
    async def fetch_source(self, project: DistillProject, file_path: str) -> Optional[str]:
        """从 GitHub 获取源码"""
        url = f"https://raw.githubusercontent.com/{project.github_url.split('/')[-2]}/{project.github_url.split('/')[-1]}/{project.branch}/{file_path}"
        
        try:
            async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                if resp.status == 200:
                    content = await resp.text()
                    logger.info(f"✅ 获取: {file_path} ({len(content)} chars)")
                    return content
                else:
                    logger.error(f"❌ HTTP {resp.status}: {url}")
                    return None
        except Exception as e:
            logger.error(f"❌ 获取失败 {file_path}: {e}")
            return None
    
    async def fetch_all_sources(self, project: DistillProject) -> dict[str, str]:
        """获取项目所有源文件"""
        results = {}
        
        for file_path in project.source_files:
            content = await self.fetch_source(project, file_path)
            if content:
                results[file_path] = content
        
        return results
    
    def generate_document(self, project: DistillProject, sources: dict[str, str], 
                          target_path: str) -> str:
        """生成深度蒸馏文档"""
        # 读取核心片段
        snippets = {}
        for path, content in sources.items():
            # 提取关键代码片段（前 100-200 行）
            lines = content.split('\n')
            key_lines = lines[:min(150, len(lines))]
            snippets[path] = '\n'.join(key_lines)
        
        # 生成文档
        doc = f"""# {project.name} 架构深度蒸馏

> 来源：{project.github_url.split('/')[-1]} 官方源码（GitHub）
> 蒸馏日期：{datetime.now().strftime('%Y-%m-%d')}
> 核心价值：{project.core_value}

---

## 一、核心架构分析

"""
        
        # 添加源码片段
        for path, snippet in snippets.items():
            lang = self._detect_language(path)
            doc += f"### 1.{list(snippets.keys()).index(path)+1} {Path(path).stem}\n\n"
            doc += f"**文件路径**: `{path}`\n\n"
            doc += f"```{lang}\n{snippet[:2000]}\n```\n\n"
        
        # 添加架构分析模板
        doc += """
## 二、设计洞察

### 2.1 核心设计模式
- **单一职责**: 每个模块专注单一功能
- **依赖注入**: 降低模块间耦合
- **异步处理**: 提升并发性能

### 2.2 关键实现细节
- 使用原子操作保证线程安全
- 采用分页内存管理避免碎片
- 通过缓存减少重复计算

### 2.3 性能优化策略
- 批处理提升吞吐量
- 预分配减少内存分配开销
- 懒加载优化启动时间

## 三、生产级应用

### 3.1 配置示例
\`\`\`yaml
# 生产配置最佳实践
key1: value1
key2: value2
\`\`\`

### 3.2 监控指标
- **延迟**: P99 < 100ms
- **吞吐**: > 10000 qps
- **可用性**: 99.99%

### 3.3 故障排查
1. 检查核心指标异常
2. 分析堆栈跟踪
3. 定位瓶颈所在

## 四、核心洞察总结

\`\`\`
1. 架构设计原则
   - 解耦与内聚
   - 可扩展性
   - 容错性
   
2. 关键实现技巧
   - 线程安全设计
   - 内存管理优化
   - 并发控制策略
   
3. 生产部署建议
   - 资源规划
   - 监控告警
   - 容量评估
\`\`\`

---

**核心价值**：通过源码蒸馏提取的独家洞察，结合个人实战经验，形成无法被替代的知识资产。

**参考资料**：
- [官方文档](https://github.com/{project.github_url.split('/')[-2]}/{project.github_url.split('/')[-1]}/wiki)
- [GitHub 仓库]({project.github_url})

"""
        
        # 写入文件
        target_file = self.kb_root / target_path
        target_file.parent.mkdir(parents=True, exist_ok=True)
        target_file.write_text(doc, encoding='utf-8')
        
        logger.info(f"✅ 生成文档: {target_path}")
        return target_path
    
    def _detect_language(self, filepath: str) -> str:
        """检测编程语言"""
        ext = Path(filepath).suffix.lower()
        lang_map = {
            '.go': 'go',
            '.java': 'java',
            '.py': 'python',
            '.rs': 'rust',
            '.cpp': 'cpp',
            '.c': 'c',
            '.h': 'c',
            '.hpp': 'cpp',
            '.scala': 'scala',
            '.kt': 'kotlin',
            '.ts': 'typescript',
            '.js': 'javascript',
        }
        return lang_map.get(ext, 'text')
    
    async def distill_project(self, project: DistillProject) -> list[str]:
        """蒸馏单个项目"""
        logger.info(f"🚀 开始蒸馏项目: {project.name}")
        
        # 获取源码
        sources = await self.fetch_all_sources(project)
        
        if not sources:
            logger.error(f"❌ 无法获取项目源码: {project.name}")
            return []
        
        # 生成文档
        generated_docs = []
        for i, target_path in enumerate(project.target_docs):
            if i < len(sources):
                source_key = list(sources.keys())[i]
                doc_path = self.generate_document(
                    project, 
                    {source_key: sources[source_key]},
                    target_path
                )
                generated_docs.append(doc_path)
        
        logger.info(f"✅ 完成项目蒸馏: {project.name} ({len(generated_docs)} 文档)")
        return generated_docs
    
    async def distill_all(self, category: Optional[str] = None, 
                         max_projects: Optional[int] = None):
        """蒸馏所有项目"""
        projects = get_all_projects()
        
        if category:
            projects = [p for p in projects if p.category == category]
        
        if max_projects:
            projects = projects[:max_projects]
        
        logger.info(f"🚀 开始批量蒸馏，共 {len(projects)} 个项目")
        
        all_generated = []
        for project in projects:
            docs = await self.distill_project(project)
            all_generated.extend(docs)
        
        logger.info(f"🎉 批量蒸馏完成，共生成 {len(all_generated)} 篇文档")
        return all_generated


async def main():
    """主函数"""
    import sys
    
    # 解析命令行参数
    category = sys.argv[1] if len(sys.argv) > 1 else None
    max_projects = int(sys.argv[2]) if len(sys.argv) > 2 else None
    
    async with DistillationEngine() as engine:
        await engine.distill_all(category, max_projects)


if __name__ == "__main__":
    asyncio.run(main())
