# Firecrawl 工具索引

首选 **官方 Python SDK**（`firecrawl-py` ≥ 4.42）。MCP（经 mcporter）是兜底。
限额按**团队**计算（并发浏览器数 + 每分钟请求数），多客户端共用同一 Key
会互相挤占——不是按 Key 隔离。

前置：guides/setup-firecrawl.md。
链路验活：`agent-reach doctor --probe`
（SDK：`get_concurrency`；MCP：`firecrawl_monitor_list`，都是零积分）。

```python
from agent_reach.channels.firecrawl import sdk_client
app = sdk_client()  # FIRECRAWL_AGENT_REACH_API_KEY，否则 FIRECRAWL_API_KEY
```

## Python SDK（首选，firecrawl-py v2）

```python
# 单页 scrape（markdown / html / json schema / screenshot）
doc = app.scrape("https://example.com", formats=["markdown"])
print(doc.markdown)

# 结构化提取：scrape formats=["json"] 或 extract()
doc = app.scrape("https://example.com", formats=["json"], json_options={"schema": {...}})
job = app.extract(urls=["https://example.com"], schema={...})
app.start_extract(...)
app.get_extract_status(job_id)

# parse 本地文件（PDF/Word/Excel → markdown）
parsed = app.parse("/path/to/paper.pdf")

# search / developer_search
app.search("query", limit=5)
app.developer_search("error message or API usage")

# map 站点 URL（不抓正文）再 crawl
app.map("https://example.com", limit=50)
app.crawl("https://example.com/docs", limit=10)          # 阻塞等到终态
job = app.start_crawl("https://example.com/docs", limit=10)
app.get_crawl_status(job.id)
app.cancel_crawl(job.id)

# batch_scrape
app.batch_scrape(["https://a.example", "https://b.example"], formats=["markdown"])
job = app.start_batch_scrape([...])
app.get_batch_scrape_status(job.id)
app.cancel_batch_scrape(job.id)

# agent
app.agent(prompt="Find the founders of Stripe")
job = app.start_agent(prompt="...")
app.get_agent_status(job.id)
app.cancel_agent(job.id)

# interact（用完必须 stop_interaction，否则占团队并发）
doc = app.scrape("https://example.com", formats=["markdown"])
app.interact(doc.metadata.scrape_id, prompt="点击「更多」")
app.stop_interaction(doc.metadata.scrape_id)

# browser 云端会话
session = app.browser()
app.browser_execute(session.id, code='print(await page.title())', language="python")
app.list_browsers(status="active")
app.delete_browser(session.id)

# monitors
app.list_monitors()
app.create_monitor(...)

# 零积分用量 / 队列（doctor --probe 用 get_concurrency）
app.get_concurrency()
app.get_credit_usage()
app.get_queue_status()

# 文献索引
app.search_papers("query")
app.inspect_paper(paper_id)
app.read_paper(paper_id, query="...")
app.related_papers(paper_id, intent="...")
app.search_github("query")  # 2026-11-03 后上游将停
```

`AsyncFirecrawl` 方法名与上表对齐，全部 `await`。v1 冻结面在 `app.v1`。

## MCP 兜底（mcporter）

SDK 不可用时再用。工具清单以 `mcporter list firecrawl` 为准。

```bash
mcporter call firecrawl.firecrawl_scrape url="URL" formats='["markdown"]'
mcporter call firecrawl.firecrawl_search query="query" limit=5
mcporter call firecrawl.firecrawl_map url="https://example.com" search="docs"
mcporter call firecrawl.firecrawl_crawl url="https://example.com/docs" limit=10
mcporter call firecrawl.firecrawl_parse filePath="/path/to/paper.pdf"
mcporter call firecrawl.firecrawl_interact url="URL" prompt="点击「更多」"
mcporter call firecrawl.firecrawl_interact_stop scrapeId="SCRAPE_ID"
mcporter call firecrawl.firecrawl_developer_search query="报错信息或 API 用法"
```

## 成本要点

- scrape ≈ 1 积分/页；crawl / agent / batch_scrape 按页数放大——先 map 再 crawl。
- MCP 的 firecrawl_extract 已弃用；提取用 scrape json 或 SDK `extract()`。
- 并发按**账户套餐、团队级**计算。`crawl` 的 max_concurrency 按本次任务份额设，不要填账户上限；大批量前 `get_queue_status()`。
- 结果可能来自缓存；需要实时数据用 `max_age=0`。
- 用完浏览器会话：`stop_interaction` / `delete_browser`。
