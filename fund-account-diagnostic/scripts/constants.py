#!/usr/bin/env python3
"""
基金账户诊断报告 - 常量与配置模块

包含全局常量、可选依赖检测、环境变量配置等。
"""

import os
import sys

# 尝试导入可选依赖
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

try:
    import empyrical
    HAS_EMPYRICAL = True
except ImportError:
    HAS_EMPYRICAL = False

try:
    from coze_workload_identity import requests as _coze_http
    HAS_COZE_HTTP = True
except ImportError:
    HAS_COZE_HTTP = False

# ============================================================
# 常量配置
# ============================================================

SKILL_ID = "7639232449859534882"

# qieman MCP服务器配置
QIEMAN_MCP_URL = "https://stargate.yingmi.com/mcp/v2"
QIEMAN_API_KEY = os.getenv(f"COZE_QIEMAN_API_{SKILL_ID}", "td1TryzwNxhQ8QRESxyNw")
if not QIEMAN_API_KEY:
    print("警告: 未配置 QIEMAN API 密钥，将使用模拟数据模式", file=sys.stderr)

# 目标配置比例（可通过环境变量 FUND_DIAG_TARGET_EQUITY 等覆盖）
TARGET_ALLOCATION = {
    "equity": float(os.getenv("FUND_DIAG_TARGET_EQUITY", "0.70")),
    "fixed_income": float(os.getenv("FUND_DIAG_TARGET_FIXED_INCOME", "0.15")),
    "cash": float(os.getenv("FUND_DIAG_TARGET_CASH", "0.15")),
}

# 基准配置（可通过环境变量覆盖）
BENCHMARK_ALLOCATION = {
    "equity": float(os.getenv("FUND_DIAG_BENCHMARK_EQUITY", "0.60")),
    "fixed_income": float(os.getenv("FUND_DIAG_BENCHMARK_FIXED_INCOME", "0.40")),
}

# 分析基准期（可通过环境变量覆盖）
DEFAULT_ANALYSIS_PERIOD_DAYS = int(os.getenv("FUND_DIAG_ANALYSIS_DAYS", "252"))

# Excel列名映射表
EXCEL_COLUMN_MAPPING = {
    "fund_code": ["基金代码", "代码"],
    "fund_name": ["基金名称", "基金简称"],
    "operation": ["业务名称", "操作", "交易类型"],
    "apply_amount": ["申请金额"],
    "confirm_amount": ["确认金额"],
    "confirm_shares": ["确认份额"],
    "fee": ["手续费"],
    "nav": ["产品单位净值", "净值", "单位净值"],
    "confirm_date": ["确认日期", "日期"],
    "confirm_result": ["确认结果", "确认状态"],
}

# 业务类型识别字典
OPERATION_TYPES = {
    "subscribe": ["申购", "认购", "定投", "定期定额申购", "强行调增"],
    "redeem": ["赎回", "强行赎回", "T+0快速赎回"],
    "convert": ["基金转换"],  # 基金转换独立处理，不计入申购/赎回统计
    "dividend": ["分红", "普通业务"],  # 普通业务在交易记录中通常表示分红再投
    "convert_in": ["转入"],
    "convert_out": ["转出"],
    "ignore": ["设置分红方式", "定投协议开通"],  # 不影响持仓的操作
}
