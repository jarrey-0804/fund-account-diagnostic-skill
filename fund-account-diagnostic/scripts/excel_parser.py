#!/usr/bin/env python3
"""
基金账户诊断报告 - Excel交易记录解析模块

解析交易记录Excel文件，计算持仓和交易统计。
"""

import os
import sys
import math
from typing import Dict, List, Tuple
from datetime import datetime

from constants import HAS_PANDAS, EXCEL_COLUMN_MAPPING
from utils import parse_amount, normalize_operation, find_column

if HAS_PANDAS:
    import pandas as pd


def parse_transaction_excel(file_path: str) -> Tuple[List[Dict], Dict]:
    """
    解析交易记录Excel文件
    
    支持的列名映射：
    - 基金代码: 基金代码、代码
    - 业务名称: 业务名称、操作、交易类型
    - 申请金额: 申请金额
    - 确认金额: 确认金额
    - 确认份额: 确认份额
    - 产品单位净值: 产品单位净值、净值、单位净值
    
    返回: (持仓列表, 交易统计)
    """
    if not HAS_PANDAS:
        raise ImportError("pandas is required to parse Excel files")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    
    # 读取Excel（支持单sheet或多sheet合并）
    try:
        # 尝试读取所有sheet
        all_sheets = pd.read_excel(file_path, sheet_name=None)
        
        # 合并所有sheet
        if len(all_sheets) == 1:
            df = list(all_sheets.values())[0]
        else:
            dfs = []
            for sheet_name, sheet_df in all_sheets.items():
                if not sheet_df.empty:
                    sheet_df['_sheet_name'] = sheet_name
                    dfs.append(sheet_df)
            df = pd.concat(dfs, ignore_index=True) if dfs else pd.DataFrame()
    except Exception as e:
        raise ValueError(f"读取Excel文件失败: {str(e)}")
    
    if df.empty:
        raise ValueError("Excel文件中没有数据")

    # 查找列名
    columns = list(df.columns)
    fund_code_col = find_column(columns, "fund_code")
    operation_col = find_column(columns, "operation")
    apply_amount_col = find_column(columns, "apply_amount")
    confirm_amount_col = find_column(columns, "confirm_amount")
    confirm_shares_col = find_column(columns, "confirm_shares")
    nav_col = find_column(columns, "nav")
    fund_name_col = find_column(columns, "fund_name")
    confirm_date_col = find_column(columns, "confirm_date")
    confirm_result_col = find_column(columns, "confirm_result") if "confirm_result" in EXCEL_COLUMN_MAPPING else None
    # 手动查找确认结果列（常见列名）
    if not confirm_result_col:
        for col in columns:
            if str(col).strip() in ["确认结果", "确认状态"]:
                confirm_result_col = col
                break

    # 过滤只保留确认成功的记录（排除合计行等非数据行）
    if confirm_result_col:
        df = df[df[confirm_result_col].astype(str).str.strip() == "确认成功"].copy()
        if df.empty:
            raise ValueError("Excel文件中没有确认成功的记录")

    if not fund_code_col:
        raise ValueError(f"未找到基金代码列，可用列: {columns}")
    
    # 查找目标基金代码列（用于基金转换）
    target_fund_code_col = None
    target_fund_name_col = None
    for col in columns:
        col_s = str(col).strip()
        if col_s in ["目标基金代码"]:
            target_fund_code_col = col
        elif col_s in ["目标基金名称"]:
            target_fund_name_col = col

    # 初始化持仓和统计
    holdings = {}
    last_transaction_dates: Dict[str, str] = {}
    # 记录每只基金的最后一笔有效操作类型（用于清仓原因判断）
    last_op_types: Dict[str, str] = {}
    stats = {
        "total_records": len(df),
        "subscribe_count": 0,
        "redeem_count": 0,
        "dividend_count": 0,
        "convert_count": 0,
        "total_convert_amount": 0.0,
        "convert_in_count": 0,
        "convert_out_count": 0,
        "unknown_count": 0,
        "total_subscribe_amount": 0.0,
        "total_redeem_amount": 0.0,
        "total_dividend_amount": 0.0,
        "total_fee": 0.0,
        "first_transaction_date": "",
        "last_transaction_date": "",
        "total_liquidated_buy_cost": 0.0,
        "funds": {}
    }
    
    for _, row in df.iterrows():
        # 获取基金代码（处理整数、浮点、字符串等类型）
        raw_code = row.get(fund_code_col)
        if raw_code is None or (isinstance(raw_code, float) and math.isnan(raw_code)):
            continue
        # 保留前导零：基金代码固定6位
        if isinstance(raw_code, (int, float)):
            fund_code = str(int(raw_code)).zfill(6)
        else:
            fund_code = str(raw_code).strip().zfill(6)
        if not fund_code or fund_code == "nan":
            continue
        
        # 获取基金名称（如果有）
        fund_name = ""
        if fund_name_col:
            fund_name = str(row.get(fund_name_col, "")) or ""
        
        # 获取业务类型
        operation = str(row.get(operation_col, "")) if operation_col else ""
        op_type = normalize_operation(operation)

        # 跳过不影响持仓的操作（设置分红方式、定投协议开通等）
        if op_type == "ignore":
            continue
        
        # 获取净值
        nav = 1.0
        if nav_col:
            nav_val = row.get(nav_col, 1.0)
            if nav_val is not None and not (isinstance(nav_val, float) and math.isnan(nav_val)):
                nav = float(nav_val) if isinstance(nav_val, (int, float)) else parse_amount(nav_val)
                if nav <= 0:
                    nav = 1.0
        
        # 获取金额和份额
        apply_amount = 0.0
        confirm_amount = 0.0
        confirm_shares = 0.0
        
        if apply_amount_col:
            apply_amount = parse_amount(row.get(apply_amount_col, 0))
        if confirm_amount_col:
            confirm_amount = parse_amount(row.get(confirm_amount_col, 0))
        if confirm_shares_col:
            confirm_shares = parse_amount(row.get(confirm_shares_col, 0))

        # 获取手续费
        fee_col = find_column(list(df.columns), "fee")
        fee = 0.0
        if fee_col:
            fee = parse_amount(row.get(fee_col, 0))
        stats["total_fee"] = stats.get("total_fee", 0) + fee

        # 记录最近交易日期
        if confirm_date_col:
            date_val = row.get(confirm_date_col)
            if date_val is not None and not (isinstance(date_val, float) and math.isnan(date_val)):
                date_str = str(int(date_val)) if isinstance(date_val, (int, float)) else str(date_val).strip()
                # 格式化日期为 YYYY-MM-DD（原始可能是 YYYYMMDD）
                if len(date_str) == 8 and date_str.isdigit():
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                if date_str and date_str != "nan":
                    last_transaction_dates[fund_code] = date_str
                    # 更新全局 first/last date
                    if not stats["first_transaction_date"] or date_str < stats["first_transaction_date"]:
                        stats["first_transaction_date"] = date_str
                    if not stats["last_transaction_date"] or date_str > stats["last_transaction_date"]:
                        stats["last_transaction_date"] = date_str

        # 初始化基金持仓
        if fund_code not in holdings:
            holdings[fund_code] = {
                "code": fund_code,
                "name": fund_name or f"基金{fund_code}",
                "shares": 0.0,
                "cost": 0.0,
                "total_dividend": 0.0,
                "subscribe_count": 0,
                "redeem_count": 0,
                "dividend_count": 0,
                "convert_count": 0
            }
            stats["funds"][fund_code] = {
                "name": fund_name or f"基金{fund_code}",
                "subscribe_count": 0,
                "redeem_count": 0,
                "dividend_count": 0,
                "convert_count": 0
            }
        
        # 记录每只基金的最后一笔有效操作类型
        if op_type in ("subscribe", "redeem", "convert"):
            last_op_types[fund_code] = operation  # 记录原始操作名称

        # 处理各种业务类型
        if op_type == "subscribe":
            # 申购：优先使用确认份额，如果没有则用确认金额/净值计算
            actual_shares = confirm_shares if confirm_shares > 0 else (confirm_amount / nav if nav > 0 else 0)
            if actual_shares > 0:
                holdings[fund_code]["shares"] += actual_shares
                holdings[fund_code]["cost"] += confirm_amount
                holdings[fund_code]["subscribe_count"] += 1
                stats["subscribe_count"] += 1
                stats["total_subscribe_amount"] += confirm_amount
                stats["funds"][fund_code]["subscribe_count"] += 1
                
        elif op_type == "redeem":
            # 赎回：使用确认份额（如果有）或者用确认金额/净值计算
            if confirm_shares > 0:
                # 直接使用确认份额
                holdings[fund_code]["shares"] -= confirm_shares
                # 按比例减少成本
                if holdings[fund_code]["shares"] > 0 and holdings[fund_code]["cost"] > 0:
                    cost_ratio = confirm_shares / (holdings[fund_code]["shares"] + confirm_shares)
                    holdings[fund_code]["cost"] *= (1 - cost_ratio)
                elif holdings[fund_code]["shares"] <= 0:
                    holdings[fund_code]["cost"] = 0
                holdings[fund_code]["redeem_count"] += 1
                stats["redeem_count"] += 1
                stats["total_redeem_amount"] += confirm_amount
                stats["funds"][fund_code]["redeem_count"] += 1
            elif confirm_amount > 0 and nav > 0:
                # 没有确认份额时，用金额和净值推算
                redeem_shares = confirm_amount / nav
                holdings[fund_code]["shares"] -= redeem_shares
                if holdings[fund_code]["shares"] > 0 and holdings[fund_code]["cost"] > 0:
                    cost_ratio = redeem_shares / (holdings[fund_code]["shares"] + redeem_shares)
                    holdings[fund_code]["cost"] *= (1 - cost_ratio)
                elif holdings[fund_code]["shares"] <= 0:
                    holdings[fund_code]["cost"] = 0
                holdings[fund_code]["redeem_count"] += 1
                stats["redeem_count"] += 1
                stats["total_redeem_amount"] += confirm_amount
                stats["funds"][fund_code]["redeem_count"] += 1

        elif op_type == "convert":
            # 基金转换：分为转出(convert_out)和转入(convert_in)
            # 判断是转出还是转入：如果有目标基金代码，则当前基金是转出方
            is_convert_out = target_fund_code_col is not None
            
            if is_convert_out:
                # 当前基金是转出方：减少份额，按比例减成本
                # 确保不会出现负份额
                actual_convert_shares = 0
                if confirm_shares > 0:
                    actual_convert_shares = min(confirm_shares, holdings[fund_code]["shares"])
                    holdings[fund_code]["shares"] -= actual_convert_shares
                    if holdings[fund_code]["shares"] > 0 and holdings[fund_code]["cost"] > 0:
                        cost_ratio = actual_convert_shares / (holdings[fund_code]["shares"] + actual_convert_shares)
                        holdings[fund_code]["cost"] *= (1 - cost_ratio)
                    elif holdings[fund_code]["shares"] <= 0:
                        holdings[fund_code]["cost"] = 0
                elif confirm_amount > 0 and nav > 0:
                    convert_shares = confirm_amount / nav
                    actual_convert_shares = min(convert_shares, holdings[fund_code]["shares"])
                    holdings[fund_code]["shares"] -= actual_convert_shares
                    if holdings[fund_code]["shares"] > 0 and holdings[fund_code]["cost"] > 0:
                        cost_ratio = actual_convert_shares / (holdings[fund_code]["shares"] + actual_convert_shares)
                        holdings[fund_code]["cost"] *= (1 - cost_ratio)
                    elif holdings[fund_code]["shares"] <= 0:
                        holdings[fund_code]["cost"] = 0

                holdings[fund_code]["convert_count"] += 1
                stats["convert_count"] += 1
                stats["total_convert_amount"] += confirm_amount
                stats["funds"][fund_code]["convert_count"] += 1
                # 记录转出基金的最后操作为转换
                last_op_types[fund_code] = operation

                # 目标基金：增加份额和成本（不计入subscribe统计）
                if target_fund_code_col and actual_convert_shares > 0:
                    tgt_raw = row.get(target_fund_code_col)
                    if tgt_raw is not None and not (isinstance(tgt_raw, float) and math.isnan(tgt_raw)):
                        tgt_code = str(int(tgt_raw)).zfill(6) if isinstance(tgt_raw, (int, float)) else str(tgt_raw).strip().zfill(6)
                        tgt_name = ""
                        if target_fund_name_col:
                            tgt_name = str(row.get(target_fund_name_col, "")) or ""
                        # 目标基金确认份额（如果有"目标产品确认份额"列则用之）
                        tgt_shares_col = None
                        for col in columns:
                            if str(col).strip() in ["目标产品确认份额"]:
                                tgt_shares_col = col
                                break
                        tgt_confirm_shares = 0.0
                        if tgt_shares_col:
                            tgt_confirm_shares = parse_amount(row.get(tgt_shares_col, 0))
                        if tgt_confirm_shares <= 0:
                            # 使用实际转出的份额
                            tgt_confirm_shares = actual_convert_shares
                        if tgt_confirm_shares > 0 and tgt_code:
                            if tgt_code not in holdings:
                                holdings[tgt_code] = {
                                    "code": tgt_code,
                                    "name": tgt_name or f"基金{tgt_code}",
                                    "shares": 0.0,
                                    "cost": 0.0,
                                    "total_dividend": 0.0,
                                    "subscribe_count": 0,
                                    "redeem_count": 0,
                                    "dividend_count": 0,
                                    "convert_count": 0
                                }
                                stats["funds"][tgt_code] = {
                                    "name": tgt_name or f"基金{tgt_code}",
                                    "subscribe_count": 0,
                                    "redeem_count": 0,
                                    "dividend_count": 0,
                                    "convert_count": 0
                                }
                            holdings[tgt_code]["shares"] += tgt_confirm_shares
                            # 按照实际转出份额对应的成本来计算转入成本
                            if holdings[fund_code]["cost"] > 0 and holdings[fund_code]["shares"] + actual_convert_shares > 0:
                                cost_per_share = holdings[fund_code]["cost"] / (holdings[fund_code]["shares"] + actual_convert_shares)
                                transfer_cost = cost_per_share * actual_convert_shares
                            else:
                                transfer_cost = confirm_amount
                            holdings[tgt_code]["cost"] += transfer_cost
                            # 记录目标基金的最后操作也是转换
                            last_op_types[tgt_code] = operation
            else:
                # 没有目标基金代码列，可能是单纯的转入操作
                if confirm_shares > 0:
                    holdings[fund_code]["shares"] += confirm_shares
                    if nav > 0:
                        holdings[fund_code]["cost"] += confirm_shares * nav
                    stats["convert_in_count"] += 1

        elif op_type == "dividend":
            # 分红：确认份额>0为分红再投（增加份额），否则为现金分红（仅记账）
            stats["dividend_count"] += 1
            holdings[fund_code]["dividend_count"] += 1
            stats["funds"][fund_code]["dividend_count"] += 1
            stats["total_dividend_amount"] = stats.get("total_dividend_amount", 0) + confirm_amount
            if confirm_shares > 0:
                # 分红再投：增加份额
                dividend_amount = confirm_shares * nav
                holdings[fund_code]["shares"] += confirm_shares
                holdings[fund_code]["total_dividend"] += dividend_amount
                
        elif op_type == "convert_in":
            # 转入
            if confirm_shares > 0:
                holdings[fund_code]["shares"] += confirm_shares
                if nav > 0:
                    holdings[fund_code]["cost"] += confirm_shares * nav
                stats["convert_in_count"] += 1
                
        elif op_type == "convert_out":
            # 转出
            if confirm_shares > 0:
                holdings[fund_code]["shares"] -= confirm_shares
                stats["convert_out_count"] += 1
        else:
            stats["unknown_count"] += 1
    
    # 构建结果：仅包含当前有持仓的基金（份额 > 0）
    # 份额为负时设为0（表示已清仓或超卖）
    # 浮点精度：份额 < 1e-6 视为已清仓（赎回确认份额的浮点误差残留）
    SHARES_DUST_THRESHOLD = 1e-6
    result = []
    liquidated_funds = []
    for h in holdings.values():
        h_copy = {**h}
        if h_copy["shares"] < 0:
            h_copy["shares"] = 0
        if h_copy["shares"] > SHARES_DUST_THRESHOLD:
            result.append(h_copy)
        else:
            # 基金已清仓/赎回完毕，记录为 liquidated
            if h.get("subscribe_count", 0) > 0 or h.get("cost", 0) > 0 or h.get("convert_count", 0) > 0:
                # 根据最后一笔有效操作判断清仓原因
                last_op = last_op_types.get(h["code"], "")
                if "转换" in last_op:
                    reason = "基金转换清仓"
                elif "强行赎回" in last_op:
                    reason = "强行赎回清仓"
                elif h.get("redeem_count", 0) > 0:
                    reason = "赎回清仓"
                else:
                    reason = "转出清仓"
                liquidated_funds.append({
                    "code": h["code"],
                    "name": h.get("name", h["code"]),
                    "last_transaction_date": last_transaction_dates.get(h["code"], ""),
                    "reason": reason,
                })
                stats["total_liquidated_buy_cost"] = stats.get("total_liquidated_buy_cost", 0) + h.get("cost", 0)

    # 按成本降序排序
    result.sort(key=lambda x: x.get("cost", 0), reverse=True)
    stats["liquidated_funds"] = liquidated_funds

    return result, stats
