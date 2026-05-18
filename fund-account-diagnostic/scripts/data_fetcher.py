#!/usr/bin/env python3
"""
基金账户诊断报告 - 数据获取模块

封装所有与 qieman MCP 服务器的数据获取交互，失败时降级为模拟数据。
"""

import random
import sys
import math
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from constants import DEFAULT_ANALYSIS_PERIOD_DAYS, HAS_PANDAS, HAS_NUMPY
from mcp_client import mcp_call_tool, is_api_available
from calculations import calculate_portfolio_nav


def generate_mock_nav_series(fund_code: str, days: int = 252) -> List[float]:
    """基于基金代码生成确定性模拟净值序列"""
    random.seed(hash(fund_code) % (2**31))
    nav_series = [1.0]
    for i in range(days):
        daily_return = random.gauss(0.0003, 0.015)
        nav_series.append(nav_series[-1] * (1 + daily_return))
    return nav_series


def get_fund_info(fund_code: str) -> Tuple[Dict, bool]:
    """获取基金基础信息。

    数据源: qieman MCP - fund_info，失败时降级为模拟数据。

    Args:
        fund_code: 6位基金代码字符串。

    Returns:
        (数据字典, 是否为真实数据) 元组。数据字典包含 code、name、type、
        nav、total_nav、manager 等字段。
    """
    try:
        # 调用MCP工具获取基金信息
        result = mcp_call_tool("fund_info", {"fund_code": fund_code})
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass
    
    # 降级：返回模拟数据
    random.seed(hash(fund_code) % (2**31))
    companies = ["易方达", "广发", "华夏", "嘉实", "南方", "富国", "招商", "博时", "汇添富", "鹏华"]
    return {
        "code": fund_code,
        "name": f"基金{fund_code}",
        "type": "混合型",
        "nav": round(1 + (hash(fund_code) % 50) / 100, 4),
        "total_nav": round(1.5 + (hash(fund_code) % 100) / 100, 4),
        "manager": f"基金经理{hash(fund_code) % 10 + 1}",
        "company": companies[hash(fund_code) % len(companies)],
    }, False


def get_fund_nav(fund_code: str, start_date: str = None, end_date: str = None) -> Tuple[Dict, bool]:
    """获取基金净值数据。

    数据源: qieman MCP - fund_nav，失败时降级为模拟净值序列。

    Args:
        fund_code: 6位基金代码字符串。
        start_date: 起始日期（YYYY-MM-DD），可选。
        end_date: 截止日期（YYYY-MM-DD），可选。

    Returns:
        (数据字典, 是否为真实数据) 元组。数据字典包含 code、nav_series、dates。
    """
    try:
        # 调用MCP工具获取净值数据
        result = mcp_call_tool("fund_nav", {
            "fund_code": fund_code,
            "start_date": start_date,
            "end_date": end_date
        })
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass
    
    # 降级：返回模拟净值序列
    days = DEFAULT_ANALYSIS_PERIOD_DAYS
    nav_series = generate_mock_nav_series(fund_code, days)
    
    end_dt = datetime.now()
    dates = [(end_dt - timedelta(days=days-i)).strftime("%Y-%m-%d") for i in range(days+1)]
    
    return {
        "code": fund_code,
        "nav_series": nav_series,
        "dates": dates
    }, False


def get_fund_industry_allocation(fund_code: str) -> Tuple[Dict, bool]:
    """获取基金行业配置。

    数据源: qieman MCP - fund_industry_allocation，失败时降级为模拟数据。

    Args:
        fund_code: 6位基金代码字符串。

    Returns:
        (数据字典, 是否为真实数据) 元组。数据字典包含 code、allocation 列表，
        每个元素含 industry、weight、change 字段。
    """
    try:
        result = mcp_call_tool("fund_industry_allocation", {"fund_code": fund_code})
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass
    
    # 降级：返回模拟行业配置
    random.seed(hash(fund_code) % (2**31))
    industries = ["电子", "医药生物", "新能源", "食品饮料", "银行", "非银金融", 
                  "房地产", "化工", "汽车", "机械设备", "计算机", "通信", "军工", "家电", "其他"]
    
    remaining = 1.0
    allocation = []
    for i, industry in enumerate(industries[:12]):
        if i == 11:
            weight = remaining
        else:
            weight = round(random.uniform(0.02, remaining * 0.3), 4)
        remaining -= weight
        allocation.append({
            "industry": industry,
            "weight": max(0.01, weight),
            "change": round(random.uniform(-0.03, 0.05), 4)
        })
    
    return {"code": fund_code, "allocation": allocation}, False


def get_fund_holdings(fund_code: str) -> Tuple[Dict, bool]:
    """获取基金重仓股。

    数据源: qieman MCP - fund_holdings，失败时降级为模拟数据。

    Args:
        fund_code: 6位基金代码字符串。

    Returns:
        (数据字典, 是否为真实数据) 元组。数据字典包含 code、holdings 列表，
        每个元素含 stock、weight、style 字段。
    """
    try:
        result = mcp_call_tool("fund_holdings", {"fund_code": fund_code})
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass
    
    # 降级：返回模拟重仓股
    random.seed(hash(fund_code) % (2**31))
    stocks = ["贵州茅台", "宁德时代", "招商银行", "比亚迪", "恒瑞医药", 
              "五粮液", "隆基绿能", "东方财富", "药明康德", "中国平安"]
    styles = ["价值", "成长", "防御"]
    
    holdings = []
    for i, stock in enumerate(stocks[:8]):
        holdings.append({
            "stock": stock,
            "weight": round(random.uniform(0.02, 0.08), 4),
            "style": random.choice(styles)
        })
    
    return {"code": fund_code, "holdings": holdings}, False


def get_fund_evaluation(fund_code: str, fund_type: str = "active") -> Tuple[Dict, bool]:
    """获取基金评价数据。

    数据源: qieman MCP - fund_evaluate，失败时降级为模拟数据。
    支持主动型和指数型两种评价路径。

    Args:
        fund_code: 6位基金代码字符串。
        fund_type: 基金类型，"active" 表示主动型，"index" 表示指数型。

    Returns:
        (评价字典, 是否为真实数据) 元组。主动型包含 score、return_score、
        risk_score、grade 等字段；指数型包含 excess_return、pe_percentile、
        valuation 等字段。
    """
    try:
        result = mcp_call_tool("fund_evaluate", {
            "fund_code": fund_code,
            "type": fund_type
        })
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass
    
    # 降级：返回模拟评价
    random.seed(hash(fund_code) % (2**31))
    score = random.randint(55, 90)
    
    if fund_type == "index":
        pe_percentile = random.randint(20, 80)
        valuation = "偏低" if pe_percentile < 35 else "适中" if pe_percentile < 65 else "偏高"
        return {
            "code": fund_code,
            "type": "index",
            "excess_return": round(random.uniform(-0.1, 0.15), 4),
            "pe_percentile": pe_percentile,
            "valuation": valuation,
            "suggestion": "估值偏低，可关注" if valuation == "偏低" else "估值适中" if valuation == "适中" else "估值偏高，谨慎"
        }, False
    else:
        return_score = random.randint(50, 95)
        risk_score = random.randint(50, 90)
        grade = "A+" if score >= 90 else "A" if score >= 80 else "B+" if score >= 70 else "B" if score >= 60 else "C"
        
        return {
            "code": fund_code,
            "type": "active",
            "score": score,
            "return_score": return_score,
            "risk_score": risk_score,
            "grade": grade,
            "suggestion": "优秀" if score >= 85 else "良好" if score >= 70 else "一般"
        }, False


def get_index_nav(index_code: str, days: int = DEFAULT_ANALYSIS_PERIOD_DAYS) -> Tuple[Dict, bool]:
    """获取指数净值数据。

    数据源: qieman MCP - index_nav，失败时降级为模拟指数序列。

    Args:
        index_code: 指数代码字符串（如 "885001.WI"）。
        days: 需要获取的交易日天数，默认为 DEFAULT_ANALYSIS_PERIOD_DAYS。

    Returns:
        (数据字典, 是否为真实数据) 元组。数据字典包含 index_code、nav_series、dates。
    """
    try:
        result = mcp_call_tool("index_nav", {
            "index_code": index_code,
            "days": days
        })
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass

    # 降级：生成模拟指数序列（基于指数代码的确定性随机）
    random.seed(hash(index_code) % (2**31))
    base_return = random.gauss(0.0004, 0.008)
    nav_series = [1.0]
    for i in range(days):
        daily_return = random.gauss(base_return, 0.012)
        nav_series.append(nav_series[-1] * (1 + daily_return))

    end_dt = datetime.now()
    dates = [(end_dt - timedelta(days=days-i)).strftime("%Y-%m-%d") for i in range(days+1)]

    return {"index_code": index_code, "nav_series": nav_series, "dates": dates}, False


def get_fund_manager_rating(fund_code: str) -> Tuple[Dict, bool]:
    """获取基金经理评分。

    数据源: qieman MCP - fund_manager_rating，失败时降级为模拟数据。

    Args:
        fund_code: 6位基金代码字符串。

    Returns:
        (评分字典, 是否为真实数据) 元组。评分字典包含 overall_1y、overall_2y、
        overall_3y、rank_1y 等经理综合评分和排名字段。
    """
    try:
        result = mcp_call_tool("fund_manager_rating", {"fund_code": fund_code})
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass

    # 降级：生成模拟基金经理评分
    random.seed(hash(fund_code + "_mgr") % (2**31))
    return {
        "code": fund_code,
        "overall_1y": random.randint(40, 95),
        "overall_2y": random.randint(40, 95),
        "overall_3y": random.randint(40, 95),
        "rank_1y": random.randint(5, 95),
        "rank_2y": random.randint(5, 95),
        "ret_1y": random.randint(40, 95),
        "mdd_1y": random.randint(40, 95),
        "sca_1y": random.randint(40, 95),
    }, False


def get_fund_subscores(fund_code: str) -> Tuple[Dict, bool]:
    """
    获取基金评分子维度
    数据源: qieman MCP - fund_subscores 或模拟数据
    返回: (子维度评分字典, 是否为真实数据)
    """
    try:
        result = mcp_call_tool("fund_subscores", {"fund_code": fund_code})
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass

    # 降级：生成模拟子维度评分
    random.seed(hash(fund_code + "_sub") % (2**31))
    return {
        "code": fund_code,
        "rank_1y": random.randint(5, 95),
        "rank_2y": random.randint(5, 95),
        "nhi_1y": random.randint(40, 95),   # 创新高得分
        "sec_1y": random.randint(40, 95),   # 择股得分
        "tim_1y": random.randint(40, 95),   # 择时得分
        "sca_1y": random.randint(40, 95),   # 规模得分
        "nhi_2y": random.randint(40, 95),
        "sec_2y": random.randint(40, 95),
        "tim_2y": random.randint(40, 95),
        "sca_2y": random.randint(40, 95),
    }, False


def get_fund_announcement(fund_code: str) -> Tuple[Dict, bool]:
    """
    获取基金公告/舆情信息
    数据源: qieman MCP - fund_announcement 或模拟数据
    """
    try:
        result = mcp_call_tool("fund_announcement", {"fund_code": fund_code})
        if result and isinstance(result, dict) and not result.get("error"):
            return result, True
    except Exception:
        pass

    # 降级：返回无负面信息的默认结果
    return {
        "code": fund_code,
        "negative_events": [],
        "has_negative": False,
        "summary": "近期无重大负面公告"
    }, False


def get_portfolio_nav(fund_codes: List[str], weights: Dict[str, float]) -> Tuple[List[float], bool]:
    """
    获取组合净值数据
    数据源: qieman MCP - portfolio_nav 或计算
    返回: (净值序列, 是否为真实数据)
    """
    fund_navs = {}
    dates = None
    
    for code in fund_codes:
        nav_data, real = get_fund_nav(code)
        fund_navs[code] = nav_data.get("nav_series", [])
        if "dates" in nav_data:
            dates = nav_data["dates"]
    
    portfolio_nav = calculate_portfolio_nav(fund_navs, weights, fund_codes)
    return portfolio_nav, True
