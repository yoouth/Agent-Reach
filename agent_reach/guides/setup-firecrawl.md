# Firecrawl 配置指南

## 功能说明
Firecrawl 是一个面向 Agent 的网页抓取/搜索引擎。**首选官方 Python SDK**
（`firecrawl-py`），MCP 是兜底。需要 API Key。配置后解锁：
- JS 渲染 / 反爬抓取
- 结构化提取（JSON schema）
- 整站 map + crawl、batch_scrape
- 带正文的网页搜索与 developer_search
- parse 本地文档、agent、interact、browser、monitors、文献索引

完整方法面见 references/firecrawl.md。

## 需要用户手动做的步骤

1. 在 https://www.firecrawl.dev 注册并创建 API Key（免费档每月 1000 credits；付费档更高。额度与并发按团队共享，以账户实际套餐为准）。
2. 把 Key 导出到 shell 环境（写入 `~/.zshrc` 或 `~/.bashrc`）。同一台机器上
   有其他系统（Hermes / Claude / Codex）时，为 Agent Reach **单独**建 Key：
   ```bash
   export FIRECRAWL_AGENT_REACH_API_KEY="fc-..."
   # 若只有一把 Key，SDK 也会读 FIRECRAWL_API_KEY
   ```
   禁止在命令回显、日志、文档里写下 Key 的值。

## Agent 可自动完成的步骤

### 1. 安装官方 Python SDK（首选）
```bash
pip install 'firecrawl-py>=4.42.0,<5'
```

```python
from agent_reach.channels.firecrawl import sdk_client
app = sdk_client()
print(app.get_concurrency())  # 零积分验活
```

### 2. （可选）注册 Firecrawl MCP 兜底
```bash
npm install -g mcporter
```
编辑 `~/.mcporter/mcporter.json`，在 `mcpServers` 中加入：
```json
{
  "mcpServers": {
    "firecrawl": {
      "command": "npx",
      "args": ["-y", "firecrawl-mcp@3.24.0"],
      "env": { "FIRECRAWL_API_KEY": "${FIRECRAWL_API_KEY}" }
    }
  }
}
```
Agent 编辑该文件时禁止读取或回显 Key 的值，始终用环境变量引用。

版本锁定 `@3.24.0` 是有意的：不锁版本时每次冷启动 `npx -y` 都可能拉到未审
的新版（含 major）。升级应当是显式决定。

### 3. 验证
```bash
# 零消耗链路验活（SDK 优先 get_concurrency；否则 MCP monitor_list）
agent-reach doctor --probe
```
注意：mcporter 对工具级失败仍以退出码 0 结束，错误在输出文本里
（如 `Unauthorized: Invalid token`）——判断成败要看输出，不能只看退出码。

## 常见问题

**Q: 什么时候用 Firecrawl，什么时候用 Jina Reader？**
A: 配置好 Firecrawl 后它就是首选（质量最好、JS/反爬直接过）；Playwright 做
备份（交互/登录态页面，见 references/browser.md）；Jina 免费零配置，作为最
终兜底或未配置 Firecrawl 时的默认。

**Q: 和 Exa 什么关系？**
A: Exa 管语义搜索（找到哪些页面相关），Firecrawl 管抓取与带正文搜索（把页面
内容完整拿回来）。调研任务两者组合使用。

**Q: 免费额度用完了？**
A: 1 credit ≈ 1 页。用完当月重置；也可以自托管开源版（仅核心抓取功能）。
