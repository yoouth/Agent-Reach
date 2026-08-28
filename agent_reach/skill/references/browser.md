# 浏览器自动化（Playwright MCP）

重 JS 页面 / 需要交互的页面的最后兜底。前置（见 guides/setup-playwright.md）：
`~/.mcporter/mcporter.json` 里已配置 `playwright` server、`mcporter daemon start`
已运行（daemon 提供 keep-alive，跨调用复用同一浏览器）、浏览器二进制已装
（`npx @playwright/mcp install-browser chrome-for-testing`）。
没配置时不要现场发明方案，提示用户运行配置指南。

## 基本读取（navigate → snapshot）

```bash
# 打开页面（keep-alive 下浏览器实例跨调用复用）
mcporter call playwright.browser_navigate url="https://example.com"

# 读取页面可访问性快照（结构化文本，token 友好，优先于截图）
mcporter call playwright.browser_snapshot
```

## 交互后读取

```bash
# 点击（ref 来自上一次 snapshot 输出）
mcporter call playwright.browser_click element="Load more button" ref="e42"

# 输入
mcporter call playwright.browser_type element="Search box" ref="e10" text="query" submit=true

# 等待内容出现后再读
mcporter call playwright.browser_wait_for text="Results"
mcporter call playwright.browser_snapshot
```

## 其他常用

```bash
mcporter call playwright.browser_take_screenshot     # 证据留存
mcporter call playwright.browser_console_messages    # 调试页面报错
mcporter call playwright.browser_close               # 任务结束后关闭
```

## 规则

- **重试链位置**：Jina Reader → firecrawl_scrape → Playwright。不要跳过前两级。
- **不是反爬工具**：Cloudflare 类防护拦住就停，报告拿不到，不要尝试绕过。
- **登录态**：只用用户明确授权的会话；不替用户登录，不绕过访问控制。
- **状态假设**：每次 navigate 后重新 snapshot 拿 ref，不要复用旧 ref。
- 任务结束 `browser_close`，不留后台浏览器。
