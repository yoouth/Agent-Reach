# 网页阅读

通用网页、RSS。

## Firecrawl 抓取（首选）

配置好即为网页读取首选（见 guides/setup-firecrawl.md；完整工具索引见
[firecrawl.md](firecrawl.md)）：

```python
from agent_reach.channels.firecrawl import sdk_client
app = sdk_client()
app.scrape("https://example.com", formats=["markdown"])
app.map("https://example.com", limit=50)
app.crawl("https://example.com/docs", limit=10)
```

```bash
# MCP 兜底
mcporter call firecrawl.firecrawl_scrape url="https://example.com" formats='["markdown"]'
mcporter call firecrawl.firecrawl_map url="https://example.com" limit=50
```

## 通用网页 (Jina Reader)

```bash
# 读取任意网页内容
curl -s "https://r.jina.ai/URL"

# 示例
curl -s "https://r.jina.ai/https://example.com/article"
```

**适用场景**: Firecrawl 未配置时的默认读取方式，及链路兜底（免费零配置）。

## 网页读取链

**firecrawl_scrape → Playwright（references/browser.md）→ Jina Reader**

Firecrawl 优先：质量最好，JS/反爬直接过（耗额度）。Playwright 本机浏览器
做备份（交互/登录态页面）。Jina 免费零配置，作为最终兜底；Firecrawl 未配置
时它就是默认。三级都失败就如实报告，不要发明第四种方案。
宿主有传输方针时按 SKILL 规则 6 优先服从宿主。

## Web Reader (MCP)

```bash
# 读取网页内容 (Markdown 格式)
mcporter call web-reader.webReader url="https://example.com"

# 保留图片
mcporter call web-reader.webReader url="https://example.com" retain_images=true

# 纯文本格式
mcporter call web-reader.webReader url="https://example.com" return_format="text"
```

**适用场景**: 需要更精确控制输出格式时使用。

## RSS (feedparser)

```python
python3 -c "
import feedparser
for e in feedparser.parse('FEED_URL').entries[:5]:
    print(f'{e.title} — {e.link}')
"
```

**适用场景**: 订阅博客、新闻源、播客等 RSS feed。

## 选择指南

| 场景 | 推荐工具 |
|-----|---------|
| 网页读取首选（已配置时） | Firecrawl (`firecrawl_scrape` 等，[firecrawl.md](firecrawl.md)) |
| 交互页面/登录态备份 | Playwright ([browser.md](browser.md)) |
| 零配置兜底 / Firecrawl 未配置 | Jina Reader (`curl r.jina.ai`) |
| 需要图片/格式控制 | web-reader MCP |
| RSS 订阅 | feedparser |
