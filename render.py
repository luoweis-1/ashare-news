#!/usr/bin/env python3
"""渲染脚本：将 news.json + template.html → index.html"""
import json
import os
from datetime import datetime, timezone, timedelta

# Jinja2 简易替代（避免 GitHub Actions 装依赖失败时卡住）
try:
    from jinja2 import Template
    HAS_JINJA2 = True
except ImportError:
    HAS_JINJA2 = False


def render_simple(template_path, data):
    """无 Jinja2 的简单模板渲染（兜底）"""
    with open(template_path, 'r', encoding='utf-8') as f:
        html = f.read()

    # 替换变量
    html = html.replace('{{ date }}', data.get('date', ''))
    html = html.replace('{{ updated }}', data.get('updated', '')[:19])
    html = html.replace('{{ stats.total }}', str(data['stats']['total']))
    html = html.replace('{{ stats.sources|length }}', str(len(data['stats']['sources'])))

    # 替换各源计数
    for src in ['cls', 'wallstreetcn', 'jinshi']:
        html = html.replace(
            f"{{{{ stats.sources.get('{src}', 0) }}}}",
            str(data['stats']['sources'].get(src, 0))
        )

    # 新闻列表
    articles_html = ""
    sources_label = {"cls": "财联社", "wallstreetcn": "见闻", "jinshi": "金十"}
    for art in data.get('articles', []):
        src = art.get('source', '')
        label = sources_label.get(src, src)
        tags_html = ''.join(
            f'<span class="tag">{t}</span>' for t in art.get('tags', [])[:4]
        )

        url = art.get('url', '')
        if url and url != 'https://www.jin10.com/':
            title_html = f'<a href="{url}" target="_blank" style="color:var(--text);text-decoration:none;">{art["title"]}</a>'
        else:
            title_html = art['title']

        summary_html = ''
        if art.get('summary') and art['summary'] != art['title']:
            summary_html = f'<div class="summary">{art["summary"][:150]}</div>'

        articles_html += f"""
    <div class="news-card" data-source="{src}">
      <span class="source-tag source-{src}">{label}</span>
      <div class="body">
        <div class="title">{title_html}</div>
        {summary_html}
        <div class="footer">
          <span>{art.get('time', '')}</span>
          {'<span class="tags">' + tags_html + '</span>' if tags_html else ''}
        </div>
      </div>
    </div>"""

    # 插入新闻列表
    html = html.replace(
        '{% for article in articles %}',
        ''
    )
    # 找到 </div> 前面插入
    html = html.replace(
        '{% endif %}',
        ''
    )
    html = html.replace('{% endfor %}', '')
    html = html.replace('{% if article.url', '')
    html = html.replace('{% else %}', '')
    html = html.replace('{% endif %}', '')
    html = html.replace('{% if article.tags %}', '')
    html = html.replace('{% for tag in article.tags[:4] %}', '')
    html = html.replace('{% endfor %}', '')

    # 简单替换：把整个 for 循环块替换为实际内容
    import re
    html = re.sub(
        r'\{% for article in articles %\}.*?\{% endfor %\}',
        articles_html,
        html, flags=re.DOTALL
    )

    # 替换 repo
    repo = os.environ.get('GITHUB_REPOSITORY', 'user/ashare-news')
    html = html.replace('{{ repo }}', repo)

    # 替换 sources dict
    for key, val in sources_label.items():
        html = html.replace(
            f"{{{{ sources['{key}'] }}}}",
            val
        )
    html = re.sub(r'\{\{ sources\[[\"\\\'](\w+)[\"\\\']\] \}\}', 
                  lambda m: sources_label.get(m.group(1), m.group(1)), html)

    return html


def render_jinja2(template_path, data):
    """Jinja2 渲染"""
    with open(template_path, 'r', encoding='utf-8') as f:
        tmpl = Template(f.read())

    sources_label = {"cls": "财联社", "wallstreetcn": "见闻", "jinshi": "金十"}
    repo = os.environ.get('GITHUB_REPOSITORY', 'user/ashare-news')
    return tmpl.render(**data, sources=sources_label, repo=repo)


def main():
    # 读 JSON
    json_path = "news.json"
    if not os.path.exists(json_path):
        print("❌ news.json 不存在，请先运行 fetch_news.py")
        return

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 补充时间
    if not data.get('updated'):
        data['updated'] = datetime.now(timezone(timedelta(hours=8))).isoformat()

    # 渲染
    template_path = "template.html"
    if HAS_JINJA2:
        html = render_jinja2(template_path, data)
        print("✅ Jinja2 渲染完成")
    else:
        html = render_simple(template_path, data)
        print("✅ 简易渲染完成 (无 Jinja2)")

    # 写 index.html
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)

    size_kb = len(html) / 1024
    print(f"📁 index.html ({size_kb:.1f} KB)")
    print(f"📊 {data['stats']['total']}条新闻 | {len(data['stats']['sources'])}来源")


if __name__ == "__main__":
    main()
