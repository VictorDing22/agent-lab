"""第 7 关参考实现：征信 MCP Server。

启动（stdio 传输）：
    uv run python stage7_mcp/server.py
用官方 Inspector 手动验证：
    npx @modelcontextprotocol/inspector uv run python stage7_mcp/server.py
也可在 Cursor 的 MCP 设置里注册本 server。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from credit_tools import check_litigation_blacklist, query_credit

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("credit-tools")

mcp.tool()(query_credit)
mcp.tool()(check_litigation_blacklist)

if __name__ == "__main__":
    mcp.run()
