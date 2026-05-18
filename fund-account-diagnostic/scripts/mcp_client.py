#!/usr/bin/env python3
"""
基金账户诊断报告 - MCP客户端模块

封装与 qieman MCP 服务器的通信逻辑（JSON-RPC 2.0）。
"""

import json
import sys
from typing import Any, Dict, Optional

from constants import QIEMAN_MCP_URL, QIEMAN_API_KEY, HAS_COZE_HTTP

# 条件导入 HTTP 库
if HAS_COZE_HTTP:
    from coze_workload_identity import requests as _coze_http
else:
    import urllib.request
    import urllib.error


def mcp_request(tool_name: str, params: Dict = None) -> Optional[Dict]:
    """
    向qieman MCP服务器发送请求
    MCP协议使用JSON-RPC 2.0
    """
    headers = {
        "Content-Type": "application/json",
        "x-api-key": QIEMAN_API_KEY,
        "Accept": "application/json, text/event-stream"
    }
    
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": tool_name,
        "params": params or {}
    }
    
    try:
        if HAS_COZE_HTTP:
            response = _coze_http.post(
                QIEMAN_MCP_URL,
                headers=headers,
                json=payload,
                timeout=30
            )
        else:
            req = urllib.request.Request(
                QIEMAN_MCP_URL,
                headers=headers,
                data=json.dumps(payload).encode('utf-8'),
                method='POST'
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode()
                # 处理SSE格式
                for line in raw.split('\n'):
                    if line.startswith('data:'):
                        raw = line[5:].strip()
                        break
                return json.loads(raw)
        
        if response.status_code >= 400:
            return None
        
        raw = response.text
        # 处理SSE格式
        for line in raw.split('\n'):
            if line.startswith('data:'):
                raw = line[5:].strip()
                break
        return json.loads(raw)
        
    except Exception as e:
        return None


def mcp_call_tool(tool_name: str, arguments: Dict = None) -> Optional[Any]:
    """
    调用MCP工具
    格式: tools/call
    """
    result = mcp_request("tools/call", {
        "name": tool_name,
        "arguments": arguments or {}
    })

    if not result or "result" not in result:
        return None

    mcp_result = result["result"]

    # MCP protocol: isError=true means the tool invocation failed
    if isinstance(mcp_result, dict) and mcp_result.get("isError"):
        return None

    return mcp_result


def is_api_available() -> bool:
    """检查MCP API是否可用"""
    return bool(QIEMAN_API_KEY)
