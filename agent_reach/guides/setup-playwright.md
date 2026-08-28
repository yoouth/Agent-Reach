# Playwright MCP 配置指南

## 功能说明
Playwright MCP（微软官方）在本机跑一个真实浏览器，是 Jina Reader 和 Firecrawl
都拿不到内容时的最后兜底：登录态页面、重 JS 单页应用、需要点击/输入的页面。
注意：它不是反爬工具（无代理轮换），Cloudflare 类防护照样会拦。

## Agent 可自动完成的步骤

### 1. 安装 mcporter
```bash
npm install -g mcporter
```

### 2. 注册 Playwright MCP（stdio，必须 keep-alive）
编辑 `~/.mcporter/mcporter.json`，在 `mcpServers` 中加入：
```json
{
  "mcpServers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest", "--headless", "--browser=chromium"],
      "lifecycle": "keep-alive"
    }
  }
}
```
**`lifecycle: keep-alive` 是硬性要求**：浏览器会话是有状态的，mcporter 默认
每次调用起新进程，会导致「navigate 完再 snapshot 时页面没了」。keep-alive
让 mcporter 守护进程复用同一个浏览器实例。

### 3. 验证
```bash
agent-reach doctor | grep -i playwright
mcporter call playwright.browser_navigate url="https://example.com"
mcporter call playwright.browser_snapshot
```
首次调用会自动下载 Chromium（约 150 MB），耐心等待。

## 需要用户手动做的步骤

**无。** 无需 API Key。磁盘占用约 500 MB（含 Chromium）。

## 常见问题

**Q: 什么时候用它？**
A: 重试链末端：Jina Reader → firecrawl_scrape → Playwright。前两个都失败或
页面需要交互（点击、滚动、输入）时才用。

**Q: 登录态页面怎么处理？**
A: 只用用户明确授权的会话。不要替用户登录，不要绕过访问控制；
需要账号的平台优先走各平台专用后端（OpenCLI 等）。
