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

### 2. 注册 Playwright MCP（stdio）
```bash
mcporter config add playwright --command npx \
  --arg '@playwright/mcp@latest' --arg --headless --arg '--browser=chromium' \
  --scope home
```

### 3. 启动 keep-alive daemon（硬性要求）
```bash
mcporter daemon start
mcporter daemon status   # 应显示 playwright: connected
```
浏览器会话是有状态的：没有 daemon 时每次 `mcporter call` 起新进程，会导致
「navigate 完再 snapshot 时页面没了」。mcporter 会自动把 playwright 识别为
keep-alive server，由 daemon 复用同一个浏览器实例。

### 4. 安装浏览器二进制（首次一次性）
```bash
npx -y @playwright/mcp@latest install-browser chrome-for-testing
```
MCP 不会自动下载浏览器（报错会提示这条命令），约 100–150 MB。

### 5. 验证
```bash
agent-reach doctor | grep -i playwright
mcporter call playwright.browser_navigate url="https://example.com"
mcporter call playwright.browser_snapshot   # 单独一次调用仍能看到页面 = daemon 生效
```

## 需要用户手动做的步骤

**无。** 无需 API Key。磁盘占用约 500 MB（含 Chromium）。

## 常见问题

**Q: 什么时候用它？**
A: 网页读取链的备份级：firecrawl_scrape → Playwright → Jina Reader。
Firecrawl 失败或页面需要交互（点击、滚动、输入）时用；Jina 是最终兜底。

**Q: 登录态页面怎么处理？**
A: 只用用户明确授权的会话。不要替用户登录，不要绕过访问控制；
需要账号的平台优先走各平台专用后端（OpenCLI 等）。
