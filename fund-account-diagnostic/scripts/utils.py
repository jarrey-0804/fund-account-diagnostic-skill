#!/usr/bin/env python3
"""
基金账户诊断报告 - 工具函数模块

提供金额解析、业务类型标准化、列名查找等通用工具。
"""

import math
from typing import Any, List, Optional

from constants import OPERATION_TYPES, EXCEL_COLUMN_MAPPING


def parse_amount(value: Any) -> float:
    """解析金额，处理字符串格式（带逗号）和数值格式。

    Args:
        value: 待解析的金额值，支持 None、int、float、str（含逗号分隔符）。

    Returns:
        解析后的浮点数金额，无法解析时返回 0.0。
    """
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # 去除逗号和空格
        cleaned = value.replace(",", "").replace(" ", "").strip()
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    return 0.0


def normalize_operation(operation: str) -> str:
    """标准化业务类型"""
    if not operation or (isinstance(operation, float) and math.isnan(operation)):
        return "unknown"
    operation = str(operation)
    # 优先精确匹配 ignore 类型（设置分红方式等），避免被"分红"等子串提前匹配
    for keyword in OPERATION_TYPES.get("ignore", []):
        if operation == keyword:
            return "ignore"
    for op_type, keywords in OPERATION_TYPES.items():
        if op_type == "ignore":
            continue
        for keyword in keywords:
            if keyword in operation:
                return op_type
    return "unknown"


def find_column(df_columns: List[str], field: str) -> Optional[str]:
    """在DataFrame列中查找对应字段
    
    优先精确匹配，然后按优先级模糊匹配
    """
    possible_names = EXCEL_COLUMN_MAPPING.get(field, [field])
    
    # 第一轮：精确匹配
    for col in df_columns:
        col_clean = str(col).strip()
        for name in possible_names:
            if col_clean == name:
                return col
    
    # 第二轮：按优先级模糊匹配（避免匹配到无关列）
    for col in df_columns:
        col_clean = str(col).strip()
        for name in possible_names:
            # 优先匹配前缀相同的列（如"基金代码"匹配"基金代码"）
            if col_clean.startswith(name) or col_clean.endswith(name):
                return col
    
    return None
