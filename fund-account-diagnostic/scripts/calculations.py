#!/usr/bin/env python3
"""
基金账户诊断报告 - 计算函数模块

包含收益率统计、最大回撤、夏普比率、相关性、HHI、组合净值等纯计算函数。
"""

import math
import random
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from constants import (
    HAS_PANDAS, HAS_NUMPY, HAS_EMPYRICAL,
    DEFAULT_ANALYSIS_PERIOD_DAYS, TARGET_ALLOCATION,
)

if HAS_PANDAS:
    import pandas as pd
if HAS_NUMPY:
    import numpy as np
if HAS_EMPYRICAL:
    import empyrical


def calculate_returns_stats(returns: List[float]) -> Dict:
    """计算收益率统计指标。

    基于日收益率序列计算均值、标准差、最小值、最大值、VaR(95%)和CVaR(95%)。
    优先使用 pandas/numpy 进行向量化计算，回退到纯 Python 实现。

    Args:
        returns: 日收益率序列。

    Returns:
        包含 mean、std、min、max、var_95、cvar_95 的字典，所有值保留6位小数。
    """
    if not returns:
        return {"mean": 0, "std": 0, "min": 0, "max": 0, "var_95": 0, "cvar_95": 0}

    # Pandas path: vectorized statistics + quantile
    if HAS_PANDAS:
        s = pd.Series(returns, dtype=float)
        mean_return = float(s.mean())
        std_return = float(s.std(ddof=0))
        var_95 = float(s.quantile(0.05))
        tail = s[s <= var_95]
        cvar_95 = float(tail.mean()) if len(tail) > 0 else var_95
        return {
            "mean": round(mean_return, 6),
            "std": round(std_return, 6),
            "min": round(float(s.min()), 6),
            "max": round(float(s.max()), 6),
            "var_95": round(var_95, 6),
            "cvar_95": round(cvar_95, 6)
        }

    # NumPy path: vectorized mean/std, percentile for VaR
    if HAS_NUMPY:
        arr = np.array(returns, dtype=float)
        mean_return = float(np.mean(arr))
        std_return = float(np.std(arr, ddof=0))
        var_95 = float(np.percentile(arr, 5))
        tail = arr[arr <= var_95]
        cvar_95 = float(np.mean(tail)) if len(tail) > 0 else var_95
        return {
            "mean": round(mean_return, 6),
            "std": round(std_return, 6),
            "min": round(float(np.min(arr)), 6),
            "max": round(float(np.max(arr)), 6),
            "var_95": round(var_95, 6),
            "cvar_95": round(cvar_95, 6)
        }

    # Manual fallback (original code preserved verbatim)
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_return = math.sqrt(variance)

    sorted_returns = sorted(returns)
    var_index = max(0, int(len(returns) * 0.05) - 1)
    var_95 = sorted_returns[var_index] if sorted_returns else 0
    cvar_95 = sum(sorted_returns[:var_index + 1]) / (var_index + 1) if sorted_returns else 0

    return {
        "mean": round(mean_return, 6),
        "std": round(std_return, 6),
        "min": round(min(returns), 6) if returns else 0,
        "max": round(max(returns), 6) if returns else 0,
        "var_95": round(var_95, 6),
        "cvar_95": round(cvar_95, 6)
    }


def calculate_max_drawdown(nav_series: List[float], dates: List[str] = None) -> Dict:
    """计算最大回撤及持续时间。

    从净值序列中寻找峰值到谷值的最大跌幅，并记录对应的起止索引和日期。

    Args:
        nav_series: 净值序列（按日期升序排列）。
        dates: 与净值序列等长的日期字符串列表，可选。

    Returns:
        包含 max_drawdown、peak_value、trough_value、start_index、end_index
        以及可选的 start_date、end_date 的字典。
    """
    if not nav_series or len(nav_series) < 2:
        return {"max_drawdown": 0, "peak_value": 0, "trough_value": 0, "start_date": "", "end_date": ""}

    # Pandas path: vectorized cummax
    if HAS_PANDAS:
        s = pd.Series(nav_series, dtype=float)
        cummax = s.cummax()
        drawdown = (cummax - s) / cummax
        max_dd_end = int(drawdown.idxmax())
        max_dd = float(drawdown.iloc[max_dd_end])
        # Search backwards from trough to find peak index
        peak_val = s.iloc[max_dd_end]
        peak_idx = max_dd_end
        for k in range(max_dd_end - 1, -1, -1):
            if s.iloc[k] > peak_val:
                peak_val = s.iloc[k]
                peak_idx = k
                break
        if peak_idx == max_dd_end:
            peak_val = cummax.iloc[max_dd_end]
            for k in range(max_dd_end, -1, -1):
                if s.iloc[k] == peak_val:
                    peak_idx = k
                    break
        result = {
            "max_drawdown": round(max_dd, 4),
            "peak_value": round(float(s.iloc[peak_idx]), 4),
            "trough_value": round(float(s.iloc[max_dd_end]), 4),
            "start_index": peak_idx,
            "end_index": max_dd_end
        }
        if dates and peak_idx < len(dates) and max_dd_end < len(dates):
            result["start_date"] = dates[peak_idx]
            result["end_date"] = dates[max_dd_end]
        return result

    # NumPy path: vectorized cumulative maximum
    if HAS_NUMPY:
        arr = np.array(nav_series, dtype=float)
        cummax = np.maximum.accumulate(arr)
        drawdown = (cummax - arr) / np.where(cummax > 0, cummax, 1.0)
        max_dd_end = int(np.argmax(drawdown))
        max_dd = float(drawdown[max_dd_end])
        peak_val = cummax[max_dd_end]
        candidates = np.where(cummax[:max_dd_end + 1] == peak_val)[0]
        peak_idx = int(candidates[0]) if len(candidates) > 0 else max_dd_end
        result = {
            "max_drawdown": round(max_dd, 4),
            "peak_value": round(float(arr[peak_idx]), 4),
            "trough_value": round(float(arr[max_dd_end]), 4),
            "start_index": peak_idx,
            "end_index": max_dd_end
        }
        if dates and peak_idx < len(dates) and max_dd_end < len(dates):
            result["start_date"] = dates[peak_idx]
            result["end_date"] = dates[max_dd_end]
        return result

    # Manual fallback (original code preserved verbatim)
    current_peak = nav_series[0]
    current_peak_idx = 0
    max_dd = 0
    max_dd_start = 0
    max_dd_end = 0

    for i, nav in enumerate(nav_series):
        if nav > current_peak:
            current_peak = nav
            current_peak_idx = i
        dd = (current_peak - nav) / current_peak if current_peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
            max_dd_start = current_peak_idx
            max_dd_end = i

    result = {
        "max_drawdown": round(max_dd, 4),
        "peak_value": round(nav_series[max_dd_start], 4),
        "trough_value": round(nav_series[max_dd_end], 4),
        "start_index": max_dd_start,
        "end_index": max_dd_end
    }

    if dates and max_dd_start < len(dates) and max_dd_end < len(dates):
        result["start_date"] = dates[max_dd_start]
        result["end_date"] = dates[max_dd_end]

    return result


def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.03) -> float:
    """计算年化夏普比率。

    夏普比率 = (年化收益率 - 无风险利率) / 年化波动率。
    优先使用 empyrical 库计算，回退到 numpy 或纯 Python。

    Args:
        returns: 日收益率序列。
        risk_free_rate: 年化无风险利率，默认 0.03（3%）。

    Returns:
        年化夏普比率，保留4位小数。序列不足时返回 0。
    """
    if not returns or len(returns) < 2:
        return 0

    # Empyrical path: battle-tested annualized sharpe
    if HAS_EMPYRICAL:
        try:
            returns_s = pd.Series(returns, dtype=float) if HAS_PANDAS else None
            if returns_s is not None:
                daily_rfr = (1 + risk_free_rate) ** (1 / 252) - 1
                sr = empyrical.sharpe_ratio(returns_s, risk_free=daily_rfr)
                if not pd.isna(sr):
                    return round(float(sr), 4)
        except Exception:
            pass

    # NumPy path
    if HAS_NUMPY:
        arr = np.array(returns, dtype=float)
        mean_daily = float(np.mean(arr))
        std_daily = float(np.std(arr, ddof=0))
        if std_daily == 0:
            return 0
        annual_return = mean_daily * 252
        annual_std = std_daily * math.sqrt(252)
        sharpe = (annual_return - risk_free_rate) / annual_std
        return round(sharpe, 4)

    # Manual fallback (original code preserved verbatim)
    mean_daily = sum(returns) / len(returns)
    variance = sum((r - mean_daily) ** 2 for r in returns) / len(returns)
    std_daily = math.sqrt(variance)

    if std_daily == 0:
        return 0

    annual_return = mean_daily * 252
    annual_std = std_daily * math.sqrt(252)
    sharpe = (annual_return - risk_free_rate) / annual_std

    if math.isnan(sharpe) or math.isinf(sharpe):
        sharpe = 0.0

    return round(sharpe, 4)


def calculate_correlation(returns1: List[float], returns2: List[float]) -> float:
    """计算两组收益率的相关系数。

    使用 Pearson 相关系数衡量两只基金收益率的线性相关程度。
    优先使用 numpy corrcoef，回退到纯 Python 实现。

    Args:
        returns1: 第一只基金的日收益率序列。
        returns2: 第二只基金的日收益率序列，需与 returns1 等长。

    Returns:
        相关系数，取值范围 [-1, 1]，保留4位小数。输入无效时返回 0。
    """
    if not returns1 or not returns2 or len(returns1) != len(returns2):
        return 0

    # NumPy path: corrcoef
    if HAS_NUMPY:
        try:
            r = np.corrcoef(np.array(returns1, dtype=float),
                            np.array(returns2, dtype=float))[0, 1]
            if np.isnan(r):
                return 0
            return round(float(r), 4)
        except Exception:
            pass

    # Manual fallback (original code preserved verbatim)
    n = len(returns1)
    mean1 = sum(returns1) / n
    mean2 = sum(returns2) / n

    numerator = sum((r1 - mean1) * (r2 - mean2) for r1, r2 in zip(returns1, returns2))
    denom1 = math.sqrt(sum((r - mean1) ** 2 for r in returns1))
    denom2 = math.sqrt(sum((r - mean2) ** 2 for r in returns2))

    if denom1 == 0 or denom2 == 0:
        return 0

    result = numerator / (denom1 * denom2)
    if math.isnan(result) or math.isinf(result):
        result = 0.0
    return round(result, 4)


def calculate_hhi(weights: List[float]) -> float:
    """计算行业集中度指数 (HHI)。

    HHI = Σ(wi²)，用于衡量行业集中程度。值越大集中度越高。

    Args:
        weights: 各行业权重列表，各元素通常在 [0, 1] 范围内。

    Returns:
        HHI 值，保留6位小数。空列表返回 0。
    """
    if not weights:
        return 0
    # NumPy path
    if HAS_NUMPY:
        return round(float(np.sum(np.array(weights, dtype=float) ** 2)), 6)
    # Manual fallback
    return round(sum(w ** 2 for w in weights), 6)


def nav_to_returns(nav_series: List[float]) -> List[float]:
    """从净值序列计算收益率序列"""
    if len(nav_series) < 2:
        return []
    # Pandas path: vectorized pct_change
    if HAS_PANDAS:
        s = pd.Series(nav_series, dtype=float)
        return s.pct_change().iloc[1:].tolist()
    # NumPy path: vectorized diff
    if HAS_NUMPY:
        arr = np.array(nav_series, dtype=float)
        prev = arr[:-1]
        curr = arr[1:]
        with np.errstate(divide='ignore', invalid='ignore'):
            rets = np.where(prev != 0, (curr - prev) / prev, 0.0)
        return rets.tolist()
    # Manual fallback
    returns = []
    for i in range(1, len(nav_series)):
        if nav_series[i-1] != 0:
            ret = (nav_series[i] - nav_series[i-1]) / nav_series[i-1]
            returns.append(ret)
        else:
            returns.append(0)
    return returns


def calculate_portfolio_nav(fund_navs: Dict[str, List[float]],
                            fund_weights: Dict[str, float],
                            fund_codes: List[str]) -> List[float]:
    """根据各基金净值序列和权重计算组合净值序列。

    将各基金净值归一化后按权重加权求和，得到组合净值曲线。
    各序列长度不一时按最长对齐，短序列使用末尾值前向填充。

    Args:
        fund_navs: 各基金净值序列字典，键为基金代码。
        fund_weights: 各基金权重字典，键为基金代码。
        fund_codes: 需要纳入计算的基金代码列表。

    Returns:
        组合净值序列（列表），空输入时返回空列表。
    """
    if not fund_navs or not fund_codes:
        return []

    # Pandas path: vectorized operations
    if HAS_PANDAS:
        series_map = {}
        for code in fund_codes:
            navs = fund_navs.get(code, [1.0])
            if navs and navs[0] > 0:
                normalized = [n / navs[0] for n in navs]
            else:
                normalized = [1.0]
            series_map[code] = pd.Series(normalized, dtype=float)

        max_len = max(len(s) for s in series_map.values())

        # Reindex all series to max_len, forward-filling
        reindexed = {}
        for code, s in series_map.items():
            if len(s) < max_len:
                s = s.reindex(range(max_len), method='ffill')
            reindexed[code] = s

        # Weighted sum
        portfolio_s = pd.Series(0.0, index=range(max_len))
        for code in fund_codes:
            weight = fund_weights.get(code, 0)
            portfolio_s += weight * reindexed[code]

        return portfolio_s.tolist()

    # NumPy path
    if HAS_NUMPY:
        max_len = max(len(fund_navs.get(code, [1.0])) for code in fund_codes)

        arrays = {}
        for code in fund_codes:
            navs = fund_navs.get(code, [1.0])
            if navs and navs[0] > 0:
                normalized = np.array([n / navs[0] for n in navs], dtype=float)
            else:
                normalized = np.array([1.0], dtype=float)
            # Pad to max_len using last value
            if len(normalized) < max_len:
                padded = np.full(max_len, normalized[-1], dtype=float)
                padded[:len(normalized)] = normalized
                normalized = padded
            arrays[code] = normalized

        portfolio = np.zeros(max_len, dtype=float)
        for code in fund_codes:
            weight = fund_weights.get(code, 0)
            portfolio += weight * arrays[code]

        return portfolio.tolist()

    # Manual fallback (original code preserved verbatim)
    max_len = max(len(fund_navs.get(code, [1.0])) for code in fund_codes)

    normalized_navs = {}
    for code in fund_codes:
        navs = fund_navs.get(code, [1.0])
        if navs and navs[0] > 0:
            normalized_navs[code] = [n / navs[0] for n in navs]
        else:
            normalized_navs[code] = [1.0]

    portfolio_nav = []
    for i in range(max_len):
        weighted_nav = 0
        for code in fund_codes:
            weight = fund_weights.get(code, 0)
            navs = normalized_navs.get(code, [1.0])
            nav = navs[i] if i < len(navs) else navs[-1]
            weighted_nav += weight * nav
        portfolio_nav.append(weighted_nav)

    return portfolio_nav


def calculate_multi_period_returns(nav_series: List[float], dates: List[str] = None,
                                    periods: List[Tuple[str, int]] = None) -> Dict[str, Optional[float]]:
    """计算多个回溯区间的收益率

    Args:
        nav_series: 净值序列（按日期升序）
        dates: 日期序列（与nav_series等长），可选
        periods: 回溯期列表，元素为 (标签, 交易日天数)，默认 1m/3m/6m/1y/2y/3y

    Returns:
        字典，如 {"1m": 0.05, "3m": 0.12, ...}，缺少数据的期间被省略
    """
    if not nav_series or len(nav_series) < 2:
        return {}

    if periods is None:
        periods = [
            ("1m", 21), ("3m", 63), ("6m", 126),
            ("1y", 252), ("2y", 504), ("3y", 756),
        ]

    n = len(nav_series)
    latest_nav = nav_series[-1]
    result = {}

    for label, trading_days in periods:
        idx = n - 1 - trading_days
        if idx < 0:
            # 历史不足该回溯期，跳过
            continue
        past_nav = nav_series[idx]
        if past_nav and past_nav > 0:
            ret = (latest_nav / past_nav) - 1
            result[label] = round(ret, 4)

    # since_inception: 从首个净值到最新
    if nav_series[0] and nav_series[0] > 0:
        result["since_inception"] = round((latest_nav / nav_series[0]) - 1, 4)

    return result


def calculate_per_fund_risk_metrics(nav_series: List[float], dates: List[str] = None,
                                     risk_free_rate: float = 0.03) -> Dict[str, Any]:
    """计算单只基金的风险指标

    Args:
        nav_series: 净值序列（按日期升序）
        dates: 日期序列（与nav_series等长），可选
        risk_free_rate: 无风险利率（年化）

    Returns:
        包含 max_drawdown, max_drawdown_period, volatility, sharpe_ratio 的字典
    """
    if not nav_series or len(nav_series) < 2:
        return {
            "max_drawdown": 0,
            "max_drawdown_period": {},
            "volatility": 0,
            "sharpe_ratio": 0,
        }

    returns = nav_to_returns(nav_series)
    if not returns:
        return {
            "max_drawdown": 0,
            "max_drawdown_period": {},
            "volatility": 0,
            "sharpe_ratio": 0,
        }

    dd_detail = calculate_max_drawdown(nav_series, dates)

    # 年化波动率 = std(returns) * sqrt(252)
    if HAS_NUMPY:
        arr = np.array(returns, dtype=float)
        vol = float(np.std(arr, ddof=0)) * math.sqrt(252)
    elif HAS_PANDAS:
        s = pd.Series(returns, dtype=float)
        vol = float(s.std(ddof=0)) * math.sqrt(252)
    else:
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
        vol = math.sqrt(variance) * math.sqrt(252)

    sharpe = calculate_sharpe_ratio(returns, risk_free_rate)

    dd_period = {}
    if dd_detail.get("start_date") and dd_detail.get("end_date"):
        dd_period = {
            "start_date": dd_detail["start_date"],
            "end_date": dd_detail["end_date"],
        }

    return {
        "max_drawdown": round(dd_detail["max_drawdown"], 4),
        "max_drawdown_period": dd_period,
        "volatility": round(vol, 4),
        "sharpe_ratio": sharpe,
    }


def compute_sub_dimension_scores(nav_series: List[float], dates: List[str] = None) -> Dict:
    """从净值序列计算评分子维度（创新高/择股/择时/规模）

    Args:
        nav_series: 净值序列（按日期升序）
        dates: 日期序列

    Returns:
        包含各子维度得分的字典
    """
    if not nav_series or len(nav_series) < 30:
        return {"innovation": 50, "stock_picking": 50, "timing": 50, "scale": 50}

    returns = nav_to_returns(nav_series)
    if not returns:
        return {"innovation": 50, "stock_picking": 50, "timing": 50, "scale": 50}

    # 创新高得分: 近期创新高次数占比
    cummax = []
    cm = nav_series[0]
    new_high_count = 0
    for n in nav_series:
        if n > cm:
            cm = n
            new_high_count += 1
        cummax.append(cm)
    innovation_ratio = new_high_count / len(nav_series) if nav_series else 0
    innovation_score = min(100, int(innovation_ratio * 500))

    # 择股得分: 基于累计收益和超额波动比
    total_return = (nav_series[-1] / nav_series[0] - 1) if nav_series[0] > 0 else 0
    annual_return = total_return * (252 / max(len(nav_series), 1))
    stock_picking_score = min(100, max(10, int(50 + annual_return * 200)))

    # 择时得分: 基于下行捕获比(简化：正收益日占比 × 负收益日的逆表现)
    positive_days = sum(1 for r in returns if r > 0)
    negative_days = sum(1 for r in returns if r < 0)
    win_rate = positive_days / len(returns) if returns else 0.5
    avg_positive = sum(r for r in returns if r > 0) / max(positive_days, 1)
    avg_negative = sum(r for r in returns if r < 0) / max(negative_days, 1)
    # 简化的盈亏比
    pl_ratio = abs(avg_positive / avg_negative) if avg_negative != 0 else 2.0
    timing_score = min(100, max(10, int(win_rate * 60 + pl_ratio * 20)))

    # 规模得分: 中性默认(无法从净值推断规模)
    scale_score = 50

    return {
        "innovation": max(0, min(100, innovation_score)),
        "stock_picking": max(0, min(100, stock_picking_score)),
        "timing": max(0, min(100, timing_score)),
        "scale": max(0, min(100, scale_score))
    }


def compute_rank_percentile(score: float, category: str = "mixed") -> Dict:
    """估算评分同类排名百分位

    基于评分分位数映射估算排名
    """
    # 基于评分的分位数映射（近似）
    if score >= 90:
        return {"1y": 5, "label": "前5%"}
    elif score >= 80:
        return {"1y": 15, "label": "前15%"}
    elif score >= 70:
        return {"1y": 30, "label": "前30%"}
    elif score >= 60:
        return {"1y": 50, "label": "前50%"}
    elif score >= 50:
        return {"1y": 70, "label": "前70%"}
    else:
        return {"1y": 90, "label": "后10%"}


def generate_operational_recommendation(score: float, return_score: float,
                                         risk_score: float, grade: str,
                                         manager_score: Dict = None) -> Tuple[str, str]:
    """生成操作建议（保留/观察/替换/部分替换）

    规则:
    - 综合评分 < 60 → 替换
    - 综合评分 60-70 且 经理评分低 → 观察或部分替换
    - 综合评分 > 80 → 保留
    - 其他 → 继续持有

    Returns: (建议, 理由)
    """
    mgr_1y = (manager_score or {}).get("overall_1y", 50)

    if score < 60:
        return "替换", f"基金综合评分{score}分处于较低水平，建议替换为同类型评分更高的基金"
    elif score < 70:
        if mgr_1y < 50:
            return "部分替换", f"基金评分{score}分处于中下水平，基金经理评分{mgr_1y}分偏低，建议部分替换"
        return "观察", f"基金评分{score}分处于中等偏下，建议持续观察"
    elif score < 80:
        return "继续持有", f"基金评分{score}分处于中等偏上水平，建议继续持有"
    elif score < 90:
        return "保留", f"基金评分{score}分表现良好，建议保留"
    else:
        return "重点保留", f"基金评分{score}分表现优秀，属于组合核心持仓"


def compute_benchmark_nav(fund_navs: Dict[str, List[float]],
                          fund_weights: Dict[str, float],
                          fund_codes: List[str],
                          target_allocation: Dict = None) -> Tuple[List[float], str]:
    """计算基准净值序列（基于目标配置的虚拟组合）

    Args:
        fund_navs: 各基金净值序列
        fund_weights: 各基金当前权重
        fund_codes: 基金代码列表
        target_allocation: 目标配置（默认60/40）

    Returns:
        (基准净值序列, 基准名称)
    """
    # 简化：使用60/40股债基准，从实际基金数据中构造
    # 取所有基金净值的加权平均作为简化基准
    portfolio_nav = calculate_portfolio_nav(fund_navs, fund_weights, fund_codes)
    if not portfolio_nav:
        return [], "60/40基准"

    # 构造一个更保守的基准：取组合净值的80%波动
    # 实际应用中应取真实指数数据
    benchmark_name = "60/40基准"
    benchmark_nav = []
    # 简化计算：每期收益取组合收益的70%（模拟低仓位）
    benchmark_nav.append(1.0)
    for i in range(1, len(portfolio_nav)):
        if portfolio_nav[i-1] > 0:
            ret = (portfolio_nav[i] / portfolio_nav[i-1] - 1) * 0.7 + 0.0001  # 降波动+小漂移
            benchmark_nav.append(benchmark_nav[-1] * (1 + ret))
        else:
            benchmark_nav.append(benchmark_nav[-1])

    return benchmark_nav, benchmark_name


def compute_stock_concentration(fund_holdings: Dict[str, List[Dict]],
                                 fund_weights_map: Dict[str, float]) -> Dict:
    """计算穿透后个股集中度

    Args:
        fund_holdings: 各基金重仓股数据
        fund_weights_map: 各基金在组合中的权重

    Returns:
        {"max_stock": 名称, "max_weight": 权重, "top5": [...], "level": 适中/偏高}
    """
    all_stocks = {}
    for code, holdings in fund_holdings.items():
        fund_weight = fund_weights_map.get(code, 0)
        for h in holdings:
            stock = h.get("stock", "")
            hold_weight = h.get("weight", 0)
            combined = fund_weight * hold_weight
            if stock in all_stocks:
                all_stocks[stock] += combined
            else:
                all_stocks[stock] = combined

    if not all_stocks:
        return {"max_stock": "", "max_weight": 0, "top5": [], "level": "无数据"}

    sorted_stocks = sorted(all_stocks.items(), key=lambda x: x[1], reverse=True)
    max_stock, max_weight = sorted_stocks[0]
    top5 = [{"name": s, "weight": round(w, 4)} for s, w in sorted_stocks[:5]]
    level = "偏高" if max_weight > 0.05 else "适中" if max_weight > 0.02 else "分散"

    return {
        "max_stock": max_stock,
        "max_weight": round(max_weight, 4),
        "top5": top5,
        "level": level
    }


def select_benchmark_index(fund_infos: Dict) -> str:
    """根据持仓特征选择对比指数

    Args:
        fund_infos: 各基金基础信息 {code: {name, type, manager}}

    Returns:
        指数代码字符串
    """
    type_counts = {"equity": 0, "fixed_income": 0, "qdii": 0, "other": 0}
    type_keywords = {
        "equity": ["混合", "股票", "成长", "价值", "消费", "医药", "科技",
                   "新能源", "半导体", "军工", "金融", "周期", "制造", "创业板"],
        "fixed_income": ["债券", "纯债", "增利", "货币", "短债", "中短债", "理财"],
        "qdii": ["QDII", "纳斯达克", "标普", "恒生", "海外", "全球", "港股", "美股", "日经"],
    }
    for code, info in fund_infos.items():
        name = info.get("name", "") + info.get("type", "")
        matched = False
        for cat, keywords in type_keywords.items():
            if any(kw in name for kw in keywords):
                type_counts[cat] += 1
                matched = True
                break
        if not matched:
            type_counts["other"] += 1

    total = sum(type_counts.values()) or 1
    eq_ratio = type_counts["equity"] / total
    fi_ratio = type_counts["fixed_income"] / total
    qd_ratio = type_counts["qdii"] / total

    if qd_ratio > 0.5:
        return "885065.WI"  # QDII股票型基金指数
    if fi_ratio > 0.5:
        return "885005.WI"  # 债券型基金总指数
    # 默认返回偏股混合型基金指数
    return "885001.WI"


def calculate_portfolio_metrics(funds: List[Dict], current_prices: Dict) -> Dict:
    """计算组合市值、成本、盈亏"""
    total_market_value = 0
    total_cost = 0
    
    for fund in funds:
        code = fund["code"]
        shares = fund.get("shares", 0)
        cost = fund.get("cost", 0)
        nav = current_prices.get(code, 0)
        
        market_value = shares * nav
        total_market_value += market_value
        total_cost += cost
    
    profit = total_market_value - total_cost
    profit_rate = profit / total_cost if total_cost > 0 else 0
    
    return {
        "total_market_value": round(total_market_value, 2),
        "total_cost": round(total_cost, 2),
        "profit": round(profit, 2),
        "profit_rate": round(profit_rate, 4)
    }
