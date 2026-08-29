# 搜索工具

Exa AI 搜索引擎 + Firecrawl 搜索。

## Exa AI 搜索

高质量 AI 搜索引擎，适合查找技术文档、官方示例和相关网页。

```bash
mcporter call exa.web_search_exa query="query" numResults=5
mcporter call exa.web_search_exa query="library API code example" numResults=5
```

### 使用场景

| 场景 | 参数 |
|-----|------|
| 网页搜索 | `web_search_exa(query: "...", numResults: 5)` |
| 技术/代码资料 | `web_search_exa(query: "框架名 API 示例", numResults: 5)` |

> Exa MCP 的 `get_code_context_exa` 已弃用且默认不注册。代码问题也使用
> `web_search_exa`；需要精确搜索仓库内容时，改用 `dev.md` 中的 GitHub 搜索。

### 特点

- 擅长英文内容和技术文档
- 可通过查询词定位官方文档和代码示例
- 结果质量高

## Firecrawl 搜索（带正文返回）

需要先配置（见 guides/setup-firecrawl.md，需要免费 API Key）。

```bash
# 网页搜索，直接返回带内容的结果
mcporter call firecrawl.firecrawl_search query="query" limit=5

# 搜索并抓取结果正文（markdown）
mcporter call firecrawl.firecrawl_search query="query" limit=5 scrapeOptions='{"formats":["markdown"]}'
```

```bash
# 面向编码 Agent 的开发者搜索（GitHub issues/合并 PR/README/精选文档索引）
mcporter call firecrawl.firecrawl_developer_search query="报错信息或 API 用法"
```

### 特点

- 结果自带页面正文，省一轮抓取
- 新闻/时效性内容支持 `tbs` 时间过滤
- 与 Exa 互补：Exa 找「哪些页面相关」，Firecrawl 把内容完整拿回来
- 完整工具索引（map/crawl/extract/parse/research 等 27 个）见 [firecrawl.md](firecrawl.md)

## 与其他搜索工具对比

| 工具 | 来源 | 适用场景 |
|-----|------|---------|
| Exa | agent-reach | 英文/技术/代码搜索（语义相关性） |
| Firecrawl | agent-reach | 搜索+抓正文一步到位、时效性内容 |
| 智谱搜索 | my-mcp-tools | 中文搜索 |
| GitHub 搜索 | agent-reach (dev.md) | 仓库/代码搜索 |
