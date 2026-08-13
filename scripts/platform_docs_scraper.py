#!/usr/bin/env python3
"""
广告平台官方文档接入器
支持四种接入模式：
1. 爬虫抓取（静态页面）
2. 实时搜索总结
3. API 文档聚合
4. 知识蒸馏
"""

import os
import sys
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# 配置
KNOWLEDGE_ROOT = Path(__file__).parent.parent / "knowledge" / "advertising" / "platform-docs"
LOG_FILE = Path(__file__).parent.parent / "logs" / "platform_docs_scraper.log"

# 官方文档配置
PLATFORMS = {
    "tiktok-ads": {
        "name": "TikTok Ads API",
        "base_url": "https://business-api.tiktok.com/portal/docs",
        "docs_list": [
            "https://business-api.tiktok.com/portal/docs?id=1735712062490625",
            "https://business-api.tiktok.com/portal/docs?id=1735711874570290",
            "https://business-api.tiktok.com/portal/docs?id=1735712466163713",
        ],
        "output_dir": "tiktok-ads",
    },
    "facebook-ads": {
        "name": "Meta Marketing API",
        "base_url": "https://developers.facebook.com/docs/marketing-api",
        "docs_list": [
            "https://developers.facebook.com/docs/marketing-api/getting-started",
            "https://developers.facebook.com/docs/marketing-api/reference",
            "https://developers.facebook.com/docs/marketing-apis/billing",
        ],
        "output_dir": "facebook-ads",
    },
    "google-ads": {
        "name": "Google Ads API",
        "base_url": "https://developers.google.com/google-ads/api",
        "docs_list": [
            "https://developers.google.com/google-ads/api/docs/start",
            "https://developers.google.com/google-ads/api/docs/guides",
            "https://developers.google.com/google-ads/api/reference/rest",
        ],
        "output_dir": "google-ads",
    },
    "display-video-360": {
        "name": "Display & Video 360 API",
        "base_url": "https://developers.google.com/display-video/api",
        "docs_list": [
            "https://developers.google.com/display-video/api/guides/overview",
            "https://developers.google.com/display-video/api/reference/rest",
            "https://developers.google.com/display-video/api/guides/quickstart",
        ],
        "output_dir": "display-video-360",
    },
}


class PlatformDocScraper:
    """广告平台官方文档接入器"""
    
    def __init__(self, platform: str, mode: str = "hybrid"):
        """
        初始化
        
        Args:
            platform: 平台名称
            mode: 接入模式 (crawler/search/hybrid/distill)
        """
        self.platform = platform
        self.mode = mode
        self.config = PLATFORMS.get(platform)
        if not self.config:
            raise ValueError(f"未知平台: {platform}")
        
        self.output_dir = KNOWLEDGE_ROOT / self.config["output_dir"]
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 日志
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        
    def log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] [{level}] [{self.platform}] {message}"
        print(log_entry)
        
        with open(LOG_FILE, "a") as f:
            f.write(log_entry + "\n")
    
    def generate_doc_id(self, title: str, content: str) -> str:
        """生成文档唯一 ID"""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:8]
        title_safe = title.replace("/", "-").replace(" ", "_")[:50]
        return f"{title_safe}_{content_hash}"
    
    def crawl_static_page(self, url: str) -> Optional[str]:
        """爬取静态页面"""
        import urllib.request
        import urllib.parse
        
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                }
            )
            
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode("utf-8", errors="ignore")
                return self.extract_content(html)
        except Exception as e:
            self.log(f"爬取失败 {url}: {e}", "ERROR")
            return None
    
    def extract_content(self, html: str) -> Optional[str]:
        """从 HTML 提取内容"""
        import re
        
        # 尝试提取主要内容
        patterns = [
            r'<article[^>]*>(.*?)</article>',
            r'<main[^>]*>(.*?)</main>',
            r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
            r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                content = match.group(1)
                # 清理 HTML 标签
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'\s+', ' ', content)
                return content.strip()[:5000]  # 限制长度
        
        return None
    
    def search_docs(self, platform: str, keyword: str) -> List[Dict]:
        """使用搜索工具查找文档"""
        self.log(f"搜索文档: {platform} - {keyword}")
        
        # 这里可以集成真实的搜索 API
        # 暂时返回模拟数据
        return []
    
    def distill_from_docs(self, docs: List[Dict]) -> str:
        """从文档中提取精华"""
        content = "\n\n".join([d.get("content", "") for d in docs])
        
        # 提取关键章节
        sections = re.split(r'(#{1,3}\s+.+)', content)
        
        result = []
        current_section = []
        
        for i, part in enumerate(sections):
            if part.startswith("#"):
                if current_section:
                    result.append("\n".join(current_section))
                current_section = [part]
            else:
                current_section.append(part)
        
        if current_section:
            result.append("\n".join(current_section))
        
        return "\n\n---\n\n".join(result[:5])  # 取前 5 个章节
    
    def generate_markdown(self, title: str, content: str, metadata: Dict) -> str:
        """生成 Markdown 文档"""
        
        doc_id = self.generate_doc_id(title, content)
        
        markdown = f"""# {title}

> **来源**: {metadata.get('source', '官方文档')}
> **更新时间**: {datetime.now().strftime('%Y-%m-%d')}
> **版本**: {metadata.get('version', 'v1.0')}
> **类型**: api-reference/documentation
> **标签**: {self.platform}, api, documentation
"""
        
        if metadata.get("summary"):
            markdown += f"\n## 📌 概述\n\n{metadata['summary']}\n"
        
        markdown += f"\n---\n\n{content[:8000]}\n"  # 限制长度
        
        markdown += f"""
---

## 📚 参考资料

- **原始文档**: {metadata.get('original_url', 'N/A')}
- **获取时间**: {datetime.now().isoformat()}
- **版本**: {metadata.get('version', 'latest')}

## 🔗 相关链接

- [TikTok Ads API 门户](https://business-api.tiktok.com/portal)
- [Meta Marketing API](https://developers.facebook.com/docs/marketing-api)
- [Google Ads API](https://developers.google.com/google-ads/api)
- [Display & Video 360 API](https://developers.google.com/display-video/api)
"""
        
        return markdown
    
    def save_doc(self, title: str, markdown: str, doc_id: Optional[str] = None) -> str:
        """保存文档"""
        if not doc_id:
            doc_id = self.generate_doc_id(title, markdown)
        
        filename = f"{doc_id}.md"
        filepath = self.output_dir / filename
        
        # 检查是否已存在
        if filepath.exists():
            self.log(f"文档已存在: {filepath}", "WARNING")
            return str(filepath)
        
        # 保存文档
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)
        
        self.log(f"文档已保存: {filepath}")
        return str(filepath)
    
    def run(self) -> Dict:
        """执行文档接入"""
        self.log(f"开始接入 {self.platform} 官方文档")
        
        results = {
            "platform": self.platform,
            "mode": self.mode,
            "docs_fetched": 0,
            "docs_saved": 0,
            "errors": [],
        }
        
        # 获取文档列表
        urls = self.config.get("docs_list", [])
        
        for url in urls:
            self.log(f"处理: {url}")
            
            # 根据模式获取内容
            content = None
            
            if self.mode in ["crawler", "hybrid"]:
                content = self.crawl_static_page(url)
            
            if not content and self.mode in ["search", "hybrid"]:
                # 尝试搜索补充
                keyword = url.split("/")[-1]
                search_results = self.search_docs(self.platform, keyword)
                if search_results:
                    content = self.distill_from_docs(search_results)
            
            if content:
                # 生成文档
                title = f"{self.config['name']} - {url.split('/')[-1]}"
                metadata = {
                    "source": self.config["name"],
                    "original_url": url,
                    "version": "latest",
                    "summary": f"来自 {self.config['name']} 官方文档",
                }
                
                markdown = self.generate_markdown(title, content, metadata)
                filepath = self.save_doc(title, markdown)
                
                results["docs_fetched"] += 1
                results["docs_saved"] += 1
            else:
                results["errors"].append(f"无法获取内容: {url}")
        
        self.log(f"完成 {self.platform}: 获取 {results['docs_fetched']} 篇，保存 {results['docs_saved']} 篇")
        return results


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="广告平台官方文档接入器")
    parser.add_argument("--platform", type=str, choices=list(PLATFORMS.keys()), help="平台名称")
    parser.add_argument("--mode", type=str, default="hybrid", choices=["crawler", "search", "hybrid", "distill"],
                        help="接入模式")
    parser.add_argument("--all", action="store_true", help="处理所有平台")
    
    args = parser.parse_args()
    
    platforms = [args.platform] if args.platform else list(PLATFORMS.keys())
    
    all_results = {}
    
    for platform in platforms:
        scraper = PlatformDocScraper(platform, mode=args.mode)
        result = scraper.run()
        all_results[platform] = result
        
        # 避免请求过快
        time.sleep(1)
    
    # 输出汇总
    print("\n" + "="*60)
    print("📊 文档接入汇总")
    print("="*60)
    
    total_fetched = sum(r["docs_fetched"] for r in all_results.values())
    total_saved = sum(r["docs_saved"] for r in all_results.values())
    total_errors = sum(len(r["errors"]) for r in all_results.values())
    
    print(f"✅ 获取文档: {total_fetched} 篇")
    print(f"💾 保存文档: {total_saved} 篇")
    print(f"❌ 错误: {total_errors} 个")
    
    if total_errors > 0:
        print("\n错误详情:")
        for platform, result in all_results.items():
            if result["errors"]:
                print(f"  {platform}: {result['errors']}")
    
    # 保存结果
    result_file = Path(__file__).parent.parent / "logs" / f"platform_docs_{datetime.now().strftime('%Y%m%d')}.json"
    with open(result_file, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n详细结果: {result_file}")


if __name__ == "__main__":
    main()
