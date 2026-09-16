#!/usr/bin/env python3
"""
A股早报 RSS 抓取脚本
每日抓取 财联社/华尔街见闻/金十 RSS → JSON
输出: news.json (供 event_detector.py 消费)
"""
import json
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree as ET
from urllib.request import urlopen, Request

# ========== RSS 源配置 ==========
RSS_SOURCES = [
    {
        "name": "cls",
        "label": "财联社",
        "url": "https://www.cls.cn/api/sw?app=CailianpressWeb&os=web&sv=8.4.6",
        "type": "api",
    },
    {
        "name": "wallstreetcn",
        "label": "华尔街见闻",
        "url": "https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=20",
        "type": "api",
    },
    {
        "name": "jinshi",
        "label": "金十数据",
        "url": "https://www.jin10.com/flash",
        "type": "html",
    },
]

# ========== 核心函数 ==========

def fetch_cls():
    """财联社 API"""
    req = Request(
        RSS_SOURCES[0]["url"],
        headers={"User-Agent": "Mozilla/5.0", "Referer": "https://www.cls.cn/"}
    )
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    articles = []
    for item in data.get("data", {}).get("roll_data", [])[:30]:
        articles.append({
            "title": item.get("title", ""),
            "summary": item.get("content", "").replace("<p>","").replace("</p>","")[:200],
            "time": item.get("ctime", ""),
            "url": f"https://www.cls.cn/detail/{item.get('id','')}",
            "source": "cls",
            "tags": _extract_tags(item.get("title","") + item.get("content","")),
        })
    return articles


def fetch_wallstreetcn():
    """华尔街见闻 API"""
    req = Request(
        RSS_SOURCES[1]["url"],
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    articles = []
    for item in data.get("data", {}).get("items", [])[:20]:
        articles.append({
            "title": item.get("title", ""),
            "summary": item.get("content_text", "")[:200],
            "time": datetime.fromtimestamp(
                item.get("display_time", 0), tz=timezone(timedelta(hours=8))
            ).strftime("%Y-%m-%d %H:%M") if item.get("display_time") else "",
            "url": item.get("uri", ""),
            "source": "wallstreetcn",
            "tags": _extract_tags(item.get("title","")),
        })
    return articles


def fetch_jinshi():
    """金十数据 HTML 抓取"""
    req = Request(
        RSS_SOURCES[2]["url"],
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36"}
    )
    with urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8")
    articles = []
    # 匹配 flash-item 结构
    items = re.findall(
        r'<div[^>]*class="[^"]*flash-item[^"]*"[^>]*>.*?'
        r'<a[^>]*>(.*?)</a>.*?'
        r'<div[^>]*class="[^"]*content[^"]*"[^>]*>(.*?)</div>.*?'
        r'<span[^>]*class="[^"]*time[^"]*"[^>]*>(.*?)</span>',
        html, re.DOTALL
    )
    for i, (title, content, t) in enumerate(items[:20]):
        title = re.sub(r'<[^>]+>', '', title).strip()
        content = re.sub(r'<[^>]+>', '', content).strip()[:200]
        articles.append({
            "title": title,
            "summary": content if content else title,
            "time": t.strip(),
            "url": f"https://www.jin10.com/",
            "source": "jinshi",
            "tags": _extract_tags(title + content),
        })
    return articles


def _extract_tags(text):
    """从文本中提取关键词标签"""
    keywords = {
        "美联储": ["美联储", "加息", "降息", "缩表", "FOMC"],
        "A股": ["A股", "上证", "深证", "创业板", "科创板"],
        "美股": ["美股", "纳指", "道指", "标普", "Meta", "苹果", "微软"],
        "原油": ["原油", "油价", "WTI", "布油", "OPEC"],
        "黄金": ["黄金", "白银", "贵金属", "COMEX"],
        "人民币": ["人民币", "汇率", "离岸", "在岸"],
        "政策": ["央行", "证监会", "政治局", "国务院", "降准"],
        "科技": ["芯片", "AI", "半导体", "算力", "大模型", "机器人"],
        "新能源": ["新能源", "光伏", "锂电", "储能", "电动车"],
        "地产": ["地产", "房地产", "楼市", "碧桂园", "万科"],
        "医药": ["医药", "创新药", "疫苗", "生物"],
    }
    tags = []
    for tag, kws in keywords.items():
        if any(kw in text for kw in kws):
            tags.append(tag)
    return tags[:5]


# ========== 主流程 ==========
def main():
    all_articles = []
    sources_ok = {}

    fetchers = {
        "cls": fetch_cls,
        "wallstreetcn": fetch_wallstreetcn,
        "jinshi": fetch_jinshi,
    }

    for name, fn in fetchers.items():
        try:
            articles = fn()
            all_articles.extend(articles)
            sources_ok[name] = len(articles)
            print(f"  ✅ {name}: {len(articles)}条")
        except Exception as e:
            sources_ok[name] = 0
            print(f"  ❌ {name}: {e}")

    # 按时间排序（有time字段的排前面）
    all_articles.sort(key=lambda x: x.get("time", ""), reverse=True)

    # 去重（同标题相似度>90%）
    deduped = []
    seen_titles = set()
    for art in all_articles:
        t = art["title"][:30]
        if t not in seen_titles:
            seen_titles.add(t)
            deduped.append(art)

    today = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d")
    output = {
        "date": today,
        "updated": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "articles": deduped[:50],
        "stats": {
            "total": len(deduped),
            "from_sources": len(all_articles),
            "sources": sources_ok,
        }
    }

    # 写 JSON
    with open("news.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n📊 总计: {len(deduped)}条新闻 (去重前{len(all_articles)}条)")
    print(f"📁 输出: news.json ({len(json.dumps(output, ensure_ascii=False))} bytes)")
    return output


if __name__ == "__main__":
    main()
