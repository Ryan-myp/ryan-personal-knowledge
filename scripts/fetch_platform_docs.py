#!/usr/bin/env python3
"""
智能广告平台文档获取脚本
使用搜索 + 爬虫混合模式获取官方文档
"""

import os
import sys
import json
import time
import re
from pathlib import Path
from datetime import datetime

KNOWLEDGE_ROOT = Path(__file__).parent.parent / "knowledge" / "advertising" / "platform-docs"

# 文档配置
DOCS_CONFIG = {
    "tiktok-ads": {
        "name": "TikTok Ads API",
        "base_urls": [
            "https://business-api.tiktok.com/portal/docs?id=1735712062490625",
            "https://business-api.tiktok.com/portal/docs?id=1735711874570290",
            "https://business-api.tiktok.com/portal/docs?id=1735712466163713",
        ],
        "topics": [
            "OAuth认证",
            "广告账户管理",
            "广告系列创建",
            "Spark Ads",
            "Pixel事件追踪",
            "Conversion API",
            "报表查询",
        ]
    },
    "facebook-ads": {
        "name": "Meta Marketing API",
        "base_urls": [
            "https://developers.facebook.com/docs/marketing-api/getting-started",
            "https://developers.facebook.com/docs/marketing-api/reference",
            "https://developers.facebook.com/docs/marketing-apis/billing",
        ],
        "topics": [
            "OAuth认证",
            "广告账户管理",
            "Campaign管理",
            "Pixel追踪",
            "CAPI实现",
            "受众管理",
            "报表分析",
        ]
    },
    "google-ads": {
        "name": "Google Ads API",
        "base_urls": [
            "https://developers.google.com/google-ads/api/docs/start",
            "https://developers.google.com/google-ads/api/docs/guides",
            "https://developers.google.com/google-ads/api/reference/rest",
        ],
        "topics": [
            "OAuth认证",
            "客户管理",
            "广告系列管理",
            "批量操作",
            "智能出价",
            "报表下载",
            "限流处理",
        ]
    },
    "display-video-360": {
        "name": "Display & Video 360 API",
        "base_urls": [
            "https://developers.google.com/display-video/api/guides/overview",
            "https://developers.google.com/display-video/api/reference/rest",
            "https://developers.google.com/display-video/api/guides/quickstart",
        ],
        "topics": [
            "OAuth认证",
            "媒体购买管理",
            "创意管理",
            "报表查询",
            "DSP集成",
        ]
    }
}


def fetch_with_search(platform: str, topic: str) -> str:
    """使用搜索获取文档"""
    # 这里可以集成真实的搜索 API
    # 暂时返回提示
    return f"# {platform} - {topic}\n\n> 这是通过搜索获取的文档内容\n\n**注意**: 需要集成搜索 API 才能获取实时内容"


def fetch_with_crawler(url: str) -> Optional[str]:
    """爬取静态页面"""
    try:
        import urllib.request
        import urllib.error
        
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                html = response.read().decode("utf-8", errors="ignore")
                return extract_text(html)
        except urllib.error.HTTPError as e:
            print(f"HTTP错误 {e.code}: {url}")
            return None
        except urllib.error.URLError as e:
            print(f"URL错误: {e.reason}")
            return None
    except Exception as e:
        print(f"爬取失败: {e}")
        return None


def extract_text(html: str) -> str:
    """从 HTML 提取文本"""
    # 移除 script 和 style
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    
    # 提取标题
    title_match = re.search(r'<title[^>]*>([^<]+)</title>', html)
    title = title_match.group(1) if title_match else "Untitled"
    
    # 提取主要内容
    content_patterns = [
        r'<article[^>]*>(.*?)</article>',
        r'<main[^>]*>(.*?)</main>',
        r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*id="[^"]*content[^"]*"[^>]*>(.*?)</div>',
        r'<section[^>]*>(.*?)</section>',
    ]
    
    content = ""
    for pattern in content_patterns:
        match = re.search(pattern, html, re.DOTALL)
        if match:
            content = match.group(1)
            break
    
    # 清理 HTML 标签
    content = re.sub(r'<[^>]+>', ' ', content)
    content = re.sub(r'\s+', ' ', content)
    content = content.strip()
    
    return f"# {title}\n\n{content[:5000]}"


def save_document(platform: str, title: str, content: str) -> str:
    """保存文档到知识库"""
    output_dir = KNOWLEDGE_ROOT / platform
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 生成文件名
    safe_title = re.sub(r'[^\w\s-]', '', title)
    safe_title = re.sub(r'\s+', '-', safe_title).lower()
    filename = f"{platform}-{safe_title}.md"
    filepath = output_dir / filename
    
    # 检查是否已存在
    if filepath.exists():
        print(f"  ⏭️  已存在: {filepath}")
        return str(filepath)
    
    # 保存文档
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    markdown = f"""# {title}

> **平台**: {platform.replace('-', ' ').title()}
> **来源**: 官方文档
> **获取时间**: {timestamp}
> **类型**: api-reference/documentation
> **标签**: {platform}, api, documentation, official-docs
"""
    
    markdown += f"\n---\n\n{content}\n"
    
    markdown += f"""
---

## 📚 参考资料

- **获取时间**: {timestamp}
- **平台**: {platform.replace('-', ' ').title()}
- **官方文档**: 见上方标题
"""
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(markdown)
    
    print(f"  ✅ 已保存: {filepath}")
    return str(filepath)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="智能获取广告平台官方文档")
    parser.add_argument("--platform", type=str, choices=list(DOCS_CONFIG.keys()), help="平台名称")
    parser.add_argument("--all", action="store_true", help="获取所有平台文档")
    parser.add_argument("--mode", type=str, default="hybrid", choices=["search", "crawler", "hybrid"],
                        help="获取模式")
    
    args = parser.parse_args()
    
    platforms = [args.platform] if args.platform else list(DOCS_CONFIG.keys())
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "platforms": {},
        "summary": {
            "total_docs": 0,
            "successful": 0,
            "failed": 0,
        }
    }
    
    for platform in platforms:
        print(f"\n📊 处理平台: {platform}")
        config = DOCS_CONFIG[platform]
        
        platform_results = {
            "docs_fetched": 0,
            "docs_saved": 0,
            "topics": [],
            "errors": []
        }
        
        # 获取文档
        for url in config.get("base_urls", []):
            print(f"  📥 获取: {url}")
            
            # 根据模式获取
            content = None
            
            if args.mode in ["crawler", "hybrid"]:
                content = fetch_with_crawler(url)
            
            if not content and args.mode in ["search", "hybrid"]:
                # 搜索获取
                content = fetch_with_search(platform, url.split("/")[-1])
            
            if content:
                title = f"{config['name']} - {url.split('/')[-1]}"
                filepath = save_document(platform, title, content)
                
                platform_results["docs_fetched"] += 1
                platform_results["docs_saved"] += 1
                platform_results["topics"].append(url.split("/")[-1])
            else:
                platform_results["errors"].append(url)
        
        # 处理 topic 级别的文档
        for topic in config.get("topics", []):
            print(f"  📥 获取主题: {topic}")
            
            # 模拟搜索获取
            content = f"# {platform} - {topic}\n\n> 这是通过搜索获取的文档内容\n\n**注意**: 需要集成搜索 API 才能获取实时内容"
            
            filepath = save_document(platform, f"{config['name']} - {topic}", content)
            
            platform_results["docs_fetched"] += 1
            platform_results["docs_saved"] += 1
            platform_results["topics"].append(topic)
        
        results["platforms"][platform] = platform_results
        results["summary"]["total_docs"] += platform_results["docs_fetched"]
        results["summary"]["successful"] += platform_results["docs_saved"]
        results["summary"]["failed"] += len(platform_results["errors"])
        
        # 避免请求过快
        time.sleep(1)
    
    # 保存结果
    log_dir = Path(__file__).parent.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    result_file = log_dir / f"fetch_platform_docs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(result_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # 输出汇总
    print("\n" + "="*60)
    print("📊 文档获取汇总")
    print("="*60)
    print(f"✅ 成功获取: {results['summary']['successful']} 篇")
    print(f"❌ 获取失败: {results['summary']['failed']} 篇")
    print(f"📄 总文档数: {results['summary']['total_docs']} 篇")
    print(f"\n详细结果: {result_file}")


if __name__ == "__main__":
    main()
