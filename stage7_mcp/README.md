# 第 7 关 · MCP + 外部征信接入 → 供应商风险审核

**时长**：2~3 个晚上 ｜ **难度**：中等
**对标真项目**：工具集管理 / MCP Server + 供应商风险评估 AI 插件

## 本关目标

两件事：
1. 上手 **MCP（Model Context Protocol）**——当前工具生态标准化的事实标准；
2. 用它实现西高院方案里的高价值场景：**供应商风险智能审核**。

## 前置阅读

modelcontextprotocol.io 的 Quickstart（Server + Client 各 10 分钟）。

一句话理解 MCP：第 3 关的工具是"焊死在自己 harness 里的函数"；
MCP 把工具做成**独立进程/服务**，用标准协议描述和调用，于是同一个工具服务能同时给
Cursor、Coze、你自己的 agent 用——"AI 界的 USB 接口"。真项目里企业征信就是这种"外部插件"。

## 动手任务

### 任务 1：写一个"征信"MCP Server（一晚）

用官方 `mcp` SDK（FastMCP 风格几行就能起），基于 `采购数据/外部数据/` 暴露两个工具：

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("credit-tools")

@mcp.tool()
def query_credit(credit_code: str) -> str:
    """按统一社会信用代码查询企业征信：工商状态、法律纠纷、行政处罚、
    经营异常、失信信息、股权冻结、舆情。数据来自 征信.json。"""

@mcp.tool()
def check_litigation_blacklist(name_or_code: str) -> str:
    """查询企业是否命中中国西电涉诉风险客户名单。"""
```

先用官方 Inspector 验证：`npx @modelcontextprotocol/inspector uv run python server.py`，
在网页里手动调这两个工具，确认协议通了。

### 任务 2：把 Server 接进 Cursor（半晚，直观感受）

在 Cursor 的 MCP 设置里注册你的 server，在聊天里问"帮我查一下信用代码 91440300MA5R7890XE 的征信"，
看你自己写的工具被 Cursor 调用。这一步给你最直观的"写一次、处处可用"体感。

### 任务 3：harness 作为 MCP Client + 落地风险审核（一晚）

1. 用 `mcp` SDK client 端连接 server，`list_tools()` 拿到工具，转成 harness 工具格式，和本地供应商工具混合注册
2. 实现**供应商风险智能审核**流程，问："帮我审一下远东电力工程有限公司这家供应商的风险"，让 agent：
   - 先查供应商库拿到信用代码（第 2 关工具）
   - 调 `query_credit` 查外部征信
   - 调 `check_litigation_blacklist` 查涉诉名单
   - 综合给出**风险分级（低/中/高）+ 处置建议**

### 任务 4：可追溯纪律（关键，半晚）

要求输出**严格区分两类信息**：
- **外部数据命中的事实**："失信被执行人：是（来源：征信接口，更新时间 2026-07-01）""命中涉诉风险名单"
- **AI 综合分析建议**："综合判断为高风险，建议不予准入"

对照《供应商准入管理办法》第六条的风险分级标准，看 agent 的分级是否站得住。
这就是方案反复强调的"不能把模型推断当权威风险事实"。

## 验收标准

- [ ] Inspector 里能手动调通两个工具
- [ ] Cursor 能调用你的 server
- [ ] harness 能混用本地工具和 MCP 工具，跑通远东电力（高风险）和中原电气（低风险）两个对照案例
- [ ] 输出严格区分"外部事实"与"AI 建议"

## 思考题

1. 什么工具适合做成 MCP server，什么留在 harness 本地就好？（征信 vs 查本地库）
2. 真项目里征信是付费接口、有限流，MCP server 层该加什么？（缓存、限流、失败降级——对照方案）
3. 如果征信接口挂了，风险审核该怎么办？（降级策略：先出"外部数据暂不可用"而不是瞎判低风险）
