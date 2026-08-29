# Firecrawl 工具索引

Firecrawl MCP（经 mcporter）暴露约 27 个工具。本页是索引：常用命令
优先掌握，其余按家族了解即可。限额按**团队**计算（并发浏览器数 + 每分钟
请求数），多客户端共用同一 Key 会互相挤占——不是按 Key 隔离。

前置：guides/setup-firecrawl.md（免费 Key + mcporter 配置与版本锁定）。
链路验活：`agent-reach doctor --probe`（真实调用一次零消耗的
firecrawl_monitor_list）。工具清单以 `mcporter list firecrawl` 实时输出为准。

## 常用命令

```bash
# 单页抓取（markdown/json/screenshot 等格式；maxAge=0 强制实时抓取）
mcporter call firecrawl.firecrawl_scrape url="URL" formats='["markdown"]'

# 结构化提取：scrape + JSON schema（firecrawl_extract 在 MCP 已弃用，勿用）
mcporter call firecrawl.firecrawl_scrape url="URL" formats='["json"]' jsonOptions='{"schema":{...}}'

# 搜索（网页/新闻/图片；categories 支持 github/research/pdf/developer）
mcporter call firecrawl.firecrawl_search query="query" limit=5

# 面向编码 Agent 的开发者搜索（GitHub issues/合并 PR/README/精选文档索引）
mcporter call firecrawl.firecrawl_developer_search query="报错信息或 API 用法"

# 站点 URL 清单（不抓正文，定位入口页用）
mcporter call firecrawl.firecrawl_map url="https://example.com" search="docs"

# 多页爬取（阻塞轮询到终态才返回，可能数分钟；耗额度大，先 map 估量再 crawl）
mcporter call firecrawl.firecrawl_crawl url="https://example.com/docs" limit=10
mcporter call firecrawl.firecrawl_check_crawl_status id="JOB_ID"

# 本地文档解析（PDF/Word/Excel 文件 → markdown；网络 URL 用 firecrawl_scrape）
mcporter call firecrawl.firecrawl_parse filePath="/path/to/paper.pdf"
```

## 其余家族（一句话索引）

| 家族 | 工具 | 用途 |
|------|------|------|
| research_* | search_papers / inspect_paper / related_papers / read_paper / search_github | 学术文献检索（PubMed/bioRxiv/medRxiv/arXiv 摘要与全文） |
| monitor_* | create / list / get / update / run / delete / checks / check | 页面变更监控（定时快照+对比；monitor_list 零消耗，doctor --probe 用它验活） |
| agent | firecrawl_agent / firecrawl_agent_status | 自主浏览 Agent（额度大，明确需要再用） |
| interact | firecrawl_interact / firecrawl_interact_stop | 会话式页面交互（点击/填表，会改变页面状态，谨慎） |
| feedback | firecrawl_search_feedback / firecrawl_feedback | 搜索质量反馈（合格首评可返 1 积分，团队每日有上限） |

## 成本要点

- scrape ≈ 1 积分/页；crawl / agent 按页数放大——先 map 再 crawl。
- firecrawl_extract 在 MCP 端已弃用（必然失败）；提取用 scrape 的 json 格式。
- 免费档并发 2 个浏览器；402/429 表示额度或并发受限（团队级）。
- 结果可能来自缓存复用窗口；需要实时数据用 `maxAge: 0`。
