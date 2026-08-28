# 网页阅读

通用网页、RSS。

## 通用网页 (Jina Reader)

```bash
# 读取任意网页内容
curl -s "https://r.jina.ai/URL"

# 示例
curl -s "https://r.jina.ai/https://example.com/article"
```

**适用场景**: 大多数网页可以直接用 Jina Reader 读取。

## Firecrawl 抓取（JS 渲染 / 反爬兜底）

Jina 返回反爬验证页、空内容或明显残缺时，换 Firecrawl（需配置，见
guides/setup-firecrawl.md）：

```bash
# 单页抓取（markdown）
mcporter call firecrawl.firecrawl_scrape url="https://example.com" formats='["markdown"]'

# 结构化提取（JSON schema）
mcporter call firecrawl.firecrawl_scrape url="https://example.com" formats='["json"]' jsonOptions='{"schema":{...}}'

# 站点 URL 发现 / 小范围爬取
mcporter call firecrawl.firecrawl_map url="https://example.com" limit=50
mcporter call firecrawl.firecrawl_crawl url="https://example.com/docs" limit=10
```

## 网页读取重试链

**Jina Reader → firecrawl_scrape → Playwright（references/browser.md）**

按顺序降级，不要跳级：Jina 免费零配置；Firecrawl 处理 JS/反爬但耗额度；
Playwright 本机浏览器兜底（交互页面）。三级都失败就如实报告，不要发明第四种方案。

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
| 通用网页 | Jina Reader (`curl r.jina.ai`) |
| JS 渲染/反爬/结构化提取/整站 | Firecrawl (`firecrawl_scrape` 等) |
| 交互页面/登录态兜底 | Playwright ([browser.md](browser.md)) |
| 需要图片/格式控制 | web-reader MCP |
| RSS 订阅 | feedparser |
