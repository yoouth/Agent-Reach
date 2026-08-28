# Firecrawl 配置指南

## 功能说明
Firecrawl 是一个面向 Agent 的网页抓取/搜索引擎。通过 MCP 接入，**需要免费 API Key**。配置后解锁：
- JS 渲染页面抓取（Jina Reader 读不到的动态页面）
- 反爬页面抓取（云端托管浏览器）
- 结构化提取（JSON schema）
- 整站爬取（map + crawl）
- 带正文的网页搜索（firecrawl_search）
- 文档解析（PDF / DOCX 等）

## 需要用户手动做的步骤

1. 在 https://www.firecrawl.dev 注册并创建 API Key（免费档每月 1000 credits）。
2. 把 Key 导出到 shell 环境（写入 `~/.zshrc` 或 `~/.bashrc`）：
   ```bash
   export FIRECRAWL_API_KEY="fc-..."
   ```
   如果同一台机器上有其他系统（如 Hermes 档案）已在用 Firecrawl，建议为
   agent-reach 单独建一个 Key，避免争抢并发与额度。

## Agent 可自动完成的步骤

### 1. 安装 mcporter
```bash
npm install -g mcporter
```

### 2. 注册 Firecrawl MCP（stdio）
编辑 `~/.mcporter/mcporter.json`，在 `mcpServers` 中加入：
```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp"],
      "env": { "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}" }
    }
  }
}
```
Agent 编辑该文件时禁止读取或回显 Key 的值，始终用环境变量引用。

### 3. 验证
```bash
agent-reach doctor | grep -i firecrawl
mcporter call firecrawl.firecrawl_scrape url="https://example.com" formats='["markdown"]'
```

## 常见问题

**Q: 什么时候用 Firecrawl，什么时候用 Jina Reader？**
A: 先 `curl r.jina.ai`（零配置、免费）；Jina 返回反爬验证页或空内容时，换
`firecrawl_scrape`；仍失败再走 Playwright（见 references/browser.md）。

**Q: 和 Exa 什么关系？**
A: Exa 管语义搜索（找到哪些页面相关），Firecrawl 管抓取与带正文搜索（把页面
内容完整拿回来）。调研任务两者组合使用。

**Q: 免费额度用完了？**
A: 1 credit ≈ 1 页。用完当月重置；也可以自托管开源版（仅核心抓取功能）。
