#!/usr/bin/env python3
"""
基金账户诊断报告 - 报告生成模块

包含各分析模块的报告生成函数（概览、收益、诊断、配置、相关性、评价、调仓、风险、总结）。
"""

import math
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta

from constants import (
    HAS_PANDAS, HAS_NUMPY, HAS_EMPYRICAL,
    TARGET_ALLOCATION, BENCHMARK_ALLOCATION, DEFAULT_ANALYSIS_PERIOD_DAYS,
)
from calculations import (
    calculate_returns_stats, calculate_max_drawdown,
    calculate_sharpe_ratio, calculate_correlation,
    calculate_hhi, calculate_portfolio_nav,
    calculate_multi_period_returns, calculate_per_fund_risk_metrics,
    nav_to_returns, calculate_portfolio_metrics,
    compute_benchmark_nav, compute_stock_concentration,
    compute_sub_dimension_scores, compute_rank_percentile,
    generate_operational_recommendation, select_benchmark_index,
)
from data_fetcher import generate_mock_nav_series

if HAS_PANDAS:
    import pandas as pd
if HAS_NUMPY:
    import numpy as np
if HAS_EMPYRICAL:
    import empyrical


def generate_overview(funds: List[Dict], fund_infos: Dict, current_prices: Dict,
                      fund_scores: Dict = None, transaction_stats: Dict = None) -> Dict:
    """生成持仓概览"""

    holdings_detail = []
    for fund in funds:
        code = fund["code"]
        shares = fund.get("shares", 0)
        cost = fund.get("cost", 0)
        nav = current_prices.get(code, 0)
        market_value = round(shares * nav, 2)
        profit = round(market_value - cost, 2)
        profit_rate = round(profit / cost, 4) if cost > 0 else 0

        info = fund_infos.get(code, {})
        score_info = (fund_scores.get(code, {}) or {}) if fund_scores else {}

        holdings_detail.append({
            "index": 0,  # will be set after sorting
            "code": code,
            "name": info.get("name", fund.get("name", code)),
            "weight": 0,  # will be set after total calculation
            "profit_rate": profit_rate,
            "profit": profit,
            "market_value": market_value,
            "cost": round(cost, 2),
            "fund_type": info.get("type", ""),
            "manager": info.get("manager", ""),
            "comprehensive_score": score_info.get("score", "N/A") if isinstance(score_info.get("score"), (int, float)) else "N/A",
            "suggestion": score_info.get("suggestion", "持有"),
            "nav": nav,
            "shares": round(shares, 2),
        })

    # 用已四舍五入的市值计算总市值和权重，保证一致性
    total_market_value = sum(h["market_value"] for h in holdings_detail)
    total_cost = sum(h["cost"] for h in holdings_detail)
    profit = round(total_market_value - total_cost, 2)
    profit_rate = round(profit / total_cost, 4) if total_cost > 0 else 0

    for h in holdings_detail:
        if total_market_value == 0:
            h["weight"] = 0.0
        else:
            h["weight"] = round(h["market_value"] / total_market_value, 4)
    
    holdings_detail.sort(key=lambda x: x["market_value"], reverse=True)
    
    for i, h in enumerate(holdings_detail, 1):
        h["index"] = i
    
    result = {
        "basic_info": {
            "fund_count": len(funds),
            "total_market_value": total_market_value,
            "total_cost": total_cost,
            "profit": profit,
            "profit_rate": profit_rate
        },
        "holdings_detail": holdings_detail
    }

    # 集中度预警：任何基金权重 > 20%
    concentration_alerts = []
    for h in holdings_detail:
        if h.get("weight", 0) > 0.20:
            concentration_alerts.append({
                "code": h["code"],
                "name": h.get("name", h["code"]),
                "weight": h["weight"],
                "message": f"权重{round(h['weight']*100, 1)}%超过20%阈值，集中度偏高",
            })
    # 过度分散预警：基金数量 > 12
    if len(holdings_detail) > 12:
        concentration_alerts.append({
            "code": "",
            "name": "组合整体",
            "weight": 0,
            "message": f"持有{len(holdings_detail)}只基金，数量偏多(>12)，建议精简至8-12只核心基金",
        })
    if concentration_alerts:
        result["concentration_alerts"] = concentration_alerts

    # 添加交易统计
    if transaction_stats:
        total_fee = transaction_stats.get("total_fee", 0) or 0
        total_sub = transaction_stats.get("total_subscribe_amount", 0)
        fee_rate = total_fee / total_sub if total_sub > 0 else 0

        result["transaction_summary"] = {
            "total_records": transaction_stats.get("total_records", 0),
            "subscribe_count": transaction_stats.get("subscribe_count", 0),
            "redeem_count": transaction_stats.get("redeem_count", 0),
            "dividend_count": transaction_stats.get("dividend_count", 0),
            "convert_count": transaction_stats.get("convert_count", 0),
            "total_subscribe_amount": round(transaction_stats.get("total_subscribe_amount", 0), 2),
            "total_redeem_amount": round(transaction_stats.get("total_redeem_amount", 0), 2),
            "total_dividend_amount": round(transaction_stats.get("total_dividend_amount", 0), 2),
            "total_convert_amount": round(transaction_stats.get("total_convert_amount", 0), 2),
            "total_fee": round(total_fee, 2),
            "fee_rate": round(fee_rate, 4),
        }

        # 已实现盈亏 = 赎回金额 - 已清仓基金的买入成本
        liquidated = transaction_stats.get("liquidated_funds", [])
        realized_pnl = round(
            transaction_stats.get("total_redeem_amount", 0)
            - transaction_stats.get("total_liquidated_buy_cost", 0),
            2,
        )
        result["realized_pnl"] = realized_pnl

        # 换手率
        holding_count = len(holdings_detail)
        liquidated_count = len(liquidated)
        turnover_ratio = round(liquidated_count / holding_count, 2) if holding_count > 0 else 0
        result["turnover_ratio"] = turnover_ratio

        # 投资年限
        first_date = transaction_stats.get("first_transaction_date", "")
        last_date = transaction_stats.get("last_transaction_date", "")
        result["investment_years"] = None
        result["first_transaction_date"] = None
        if first_date and last_date:
            try:
                fd = datetime.strptime(str(first_date), "%Y-%m-%d")
                ld = datetime.strptime(str(last_date), "%Y-%m-%d")
                years = round((ld - fd).days / 365.25, 1)
                result["investment_years"] = years
                result["first_transaction_date"] = str(first_date)
            except (ValueError, TypeError):
                pass

        if liquidated:
            result["liquidated_funds"] = liquidated

    return result


def generate_performance(funds: List[Dict], fund_navs: Dict[str, List[float]],
                        fund_weights: Dict[str, float],
                        dates: List[str] = None,
                        benchmark_returns: List[float] = None,
                        fund_nav_dates: Dict[str, List[str]] = None,
                        benchmark_data: Dict = None) -> Dict:
    """生成组合收益风险表现报告"""

    portfolio_nav = calculate_portfolio_nav(fund_navs, fund_weights, [f["code"] for f in funds])

    if not portfolio_nav:
        portfolio_nav = generate_mock_nav_series("portfolio", DEFAULT_ANALYSIS_PERIOD_DAYS)
        dates = None
        data_source_note = "模拟数据（API不可用）"
    else:
        data_source_note = "基于基金净值加权计算"

    returns = nav_to_returns(portfolio_nav)

    total_return = (portfolio_nav[-1] / portfolio_nav[0] - 1) if portfolio_nav and portfolio_nav[0] > 0 else 0
    cagr = (1 + total_return) ** (252 / len(portfolio_nav)) - 1 if len(portfolio_nav) > 1 else 0
    if math.isnan(cagr) or math.isinf(cagr):
        cagr = 0.0

    returns_stats = calculate_returns_stats(returns)
    max_drawdown = calculate_max_drawdown(portfolio_nav, dates)
    sharpe_ratio = calculate_sharpe_ratio(returns)

    # Bug fix: compound benchmark returns instead of simple sum
    if benchmark_returns:
        benchmark_total_return = 1.0
        for r in benchmark_returns:
            benchmark_total_return *= (1 + r)
        benchmark_total_return -= 1.0
    else:
        benchmark_total_return = 0
    excess_return = total_return - benchmark_total_return

    # --- Compute advanced metrics via empyrical ---
    sortino_ratio = 0.0
    calmar_ratio = 0.0
    downside_risk = 0.0
    tail_ratio = 0.0
    alpha = 0.0
    beta = 0.0
    annual_volatility = returns_stats["std"] * math.sqrt(252)
    annual_return = cagr

    if HAS_EMPYRICAL and HAS_PANDAS and returns:
        try:
            returns_s = pd.Series(returns, dtype=float)
            sr = empyrical.sortino_ratio(returns_s, required_return=0)
            if sr is not None and not pd.isna(sr):
                sortino_ratio = round(float(sr), 4)

            cal = empyrical.calmar_ratio(returns_s)
            if cal is not None and not pd.isna(cal):
                calmar_ratio = round(float(cal), 4)

            ds = empyrical.downside_risk(returns_s)
            if ds is not None and not pd.isna(ds):
                downside_risk = round(float(ds), 4)

            tr = empyrical.tail_ratio(returns_s)
            if tr is not None and not pd.isna(tr):
                tail_ratio = round(float(tr), 4)

            ar = empyrical.annual_return(returns_s)
            if ar is not None and not pd.isna(ar):
                annual_return = float(ar)

            av = empyrical.annual_volatility(returns_s)
            if av is not None and not pd.isna(av):
                annual_volatility = float(av)

            # Alpha & Beta vs benchmark
            if benchmark_returns and len(benchmark_returns) == len(returns):
                bench_s = pd.Series(benchmark_returns, dtype=float)
                b = empyrical.beta(returns_s, bench_s)
                if b is not None and not pd.isna(b):
                    beta = round(float(b), 4)
                a = empyrical.alpha(returns_s, bench_s)
                if a is not None and not pd.isna(a):
                    alpha = round(float(a), 4)
        except Exception:
            pass

    fund_returns_list = []
    for fund in funds:
        code = fund["code"]
        navs = fund_navs.get(code, [])
        fund_dates_list = None
        if fund_nav_dates and code in fund_nav_dates:
            fund_dates_list = fund_nav_dates[code]
        if len(navs) >= 2:
            fund_return = (navs[-1] / navs[0] - 1)
        else:
            fund_return = 0
        # Per-fund multi-period returns
        mp_returns = calculate_multi_period_returns(navs, fund_dates_list)
        entry = {
            "code": code,
            "name": fund.get("name", code),
            "return": round(fund_return, 4),
            "data_source": "真实净值" if navs else "模拟数据"
        }
        if mp_returns:
            for period_label, period_ret in mp_returns.items():
                entry[f"returns_{period_label}"] = period_ret
        fund_returns_list.append(entry)
    fund_returns_list.sort(key=lambda x: x["return"], reverse=True)

    attribution_summary = {}
    # 优先使用 benchmark_returns 参数，其次使用 benchmark_data 中的真实基准数据
    if benchmark_returns and abs(benchmark_total_return) > 0.001:
        attribution_summary = {
            "outperform_reason": "超配优质成长板块，低配周期板块" if excess_return > 0 else "权益仓位配置合理",
            "underperform_reason": "部分持仓受行业轮动影响" if excess_return < 0 else "相对基准表现稳健"
        }
    elif benchmark_data and benchmark_data.get("nav_series"):
        bm_nav = benchmark_data["nav_series"]
        if len(bm_nav) >= 2 and bm_nav[0] > 0:
            bm_total = bm_nav[-1] / bm_nav[0] - 1
            if abs(bm_total) > 0.001:
                exc_ret = total_return - bm_total
                attribution_summary = {
                    "outperform_reason": "超配优质成长板块，低配周期板块" if exc_ret > 0 else "权益仓位配置合理",
                    "underperform_reason": "部分持仓受行业轮动影响" if exc_ret < 0 else "相对基准表现稳健"
                }

    # 组合多期收益
    multi_period_returns = calculate_multi_period_returns(portfolio_nav, dates)

    # 最佳/最差单日收益
    returns_list = nav_to_returns(portfolio_nav)
    best_day = round(max(returns_list), 4) if returns_list else 0
    worst_day = round(min(returns_list), 4) if returns_list else 0

    # performance_metrics: 只包含有意义的非零指标
    perf_metrics = {
        "cumulative_return": round(total_return, 4),
        "cagr": round(cagr, 4),
        "volatility": round(annual_volatility, 4),
        "max_drawdown": round(max_drawdown["max_drawdown"], 4),
        "var_95": round(returns_stats["var_95"] * math.sqrt(252), 4),
        "cvar_95": round(returns_stats["cvar_95"] * math.sqrt(252), 4),
        "sharpe_ratio": sharpe_ratio,
        "best_day": best_day,
        "worst_day": worst_day,
    }
    # 仅在非零时追加 empyrical 高级指标
    if sortino_ratio != 0:
        perf_metrics["sortino_ratio"] = sortino_ratio
    if calmar_ratio != 0:
        perf_metrics["calmar_ratio"] = calmar_ratio
    if downside_risk != 0:
        perf_metrics["downside_risk"] = downside_risk
    if tail_ratio != 0:
        perf_metrics["tail_ratio"] = tail_ratio
    if alpha != 0:
        perf_metrics["alpha"] = alpha
    if beta != 0:
        perf_metrics["beta"] = beta

    # comparison_table: 仅在有基准数据时包含 benchmark
    comparison = {
        "portfolio": {"total_return": round(total_return, 4), "cagr": round(cagr, 4)},
    }
    if benchmark_returns and abs(benchmark_total_return) > 0.0001:
        comparison["benchmark"] = {"total_return": round(benchmark_total_return, 4)}
        comparison["excess_return"] = round(excess_return, 4)

    result = {
        "multi_period_returns": multi_period_returns,
        "comparison_table": comparison,
        "performance_metrics": perf_metrics,
        "max_drawdown_detail": max_drawdown,
        "fund_return_ranking": fund_returns_list,
        "data_source_note": data_source_note,
    }
    if attribution_summary:
        result["attribution_summary"] = attribution_summary

    # 组合净值曲线数据（用于HTML折线图）
    fund_codes_list = [f["code"] for f in funds]
    fund_weights_map = {f["code"]: f.get("weight", 1.0/len(funds)) for f in funds}

    # 使用真实指数数据或虚拟基准
    real_benchmark_nav = None
    real_benchmark_name = "偏股混合型基金指数"
    real_benchmark_dates = None
    if benchmark_data and benchmark_data.get("nav_series"):
        real_benchmark_nav = benchmark_data["nav_series"]
        real_benchmark_dates = benchmark_data.get("dates")
        # 指数名称映射
        idx_code = benchmark_data.get("index_code", "")
        idx_names = {
            "885001.WI": "偏股混合型基金指数",
            "885005.WI": "债券型基金总指数",
            "885065.WI": "QDII股票型基金指数",
        }
        real_benchmark_name = idx_names.get(idx_code, f"指数{idx_code}")

    benchmark_nav, benchmark_name = compute_benchmark_nav(fund_navs, fund_weights_map, fund_codes_list)

    if portfolio_nav and dates:
        # 标准化：截取等长
        min_len = min(len(portfolio_nav), len(dates))
        if benchmark_nav:
            min_len = min(min_len, len(benchmark_nav))

        # 标准化组合净值起始=1
        norm_base = portfolio_nav[0] if portfolio_nav[0] > 0 else 1.0
        normalized_nav = [round(v / norm_base, 4) for v in portfolio_nav[:min_len]]

        result["nav_curve"] = {
            "dates": dates[:min_len],
            "portfolio_nav": [round(v, 4) for v in portfolio_nav[:min_len]],
            "benchmark_nav": [round(v, 4) for v in benchmark_nav[:min_len]],
            "benchmark_name": benchmark_name,
        }

        # 新增：portfolio_nav_curve（标准化起始=1）
        result["portfolio_nav_curve"] = {
            "dates": dates[:min_len],
            "nav_series": [round(v, 4) for v in portfolio_nav[:min_len]],
            "normalized": normalized_nav,
        }

        # 新增：benchmark_nav_curve（使用真实指数数据优先）
        if real_benchmark_nav and real_benchmark_dates:
            rb_min = min(len(real_benchmark_nav), len(real_benchmark_dates), min_len)
            rb_norm_base = real_benchmark_nav[0] if real_benchmark_nav[0] > 0 else 1.0
            result["benchmark_nav_curve"] = {
                "name": real_benchmark_name,
                "dates": real_benchmark_dates[:rb_min],
                "nav_series": [round(v, 4) for v in real_benchmark_nav[:rb_min]],
                "normalized": [round(v / rb_norm_base, 4) for v in real_benchmark_nav[:rb_min]],
            }
            # 用真实指数计算 benchmark metrics
            bm_nav = real_benchmark_nav[:rb_min]
            if len(bm_nav) >= 2:
                bm_total_ret = (bm_nav[-1] / bm_nav[0] - 1) if bm_nav[0] > 0 else 0
                bm_cagr = (1 + bm_total_ret) ** (252 / max(len(bm_nav), 1)) - 1 if len(bm_nav) > 1 else 0
                bm_mdd = calculate_max_drawdown(bm_nav)
                result["benchmark_metrics"] = {
                    "name": real_benchmark_name,
                    "cumulative_return": round(bm_total_ret, 4),
                    "cagr": round(bm_cagr, 4),
                    "max_drawdown": round(bm_mdd.get("max_drawdown", 0), 4),
                }
                result["excess_vs_benchmark"] = {
                    "return_diff": round(total_return - bm_total_ret, 4),
                    "cagr_diff": round(cagr - bm_cagr, 4),
                    "mdd_diff": round(max_drawdown.get("max_drawdown", 0) - bm_mdd.get("max_drawdown", 0), 4),
                }
                # 使用真实基准的 alpha/beta
                if HAS_EMPYRICAL and HAS_PANDAS and returns:
                    try:
                        bm_returns = nav_to_returns(bm_nav)
                        min_ret_len = min(len(returns), len(bm_returns))
                        if min_ret_len > 10:
                            ret_s = pd.Series(returns[:min_ret_len], dtype=float)
                            bm_s = pd.Series(bm_returns[:min_ret_len], dtype=float)
                            b = empyrical.beta(ret_s, bm_s)
                            a = empyrical.alpha(ret_s, bm_s)
                            if b is not None and not pd.isna(b):
                                perf_metrics["beta"] = round(float(b), 4)
                            if a is not None and not pd.isna(a):
                                perf_metrics["alpha"] = round(float(a), 4)
                    except Exception:
                        pass

        # 原有基准对比（虚拟基准兼容）
        if benchmark_nav and len(benchmark_nav) >= 2:
            bench_total_return = (benchmark_nav[-1] / benchmark_nav[0] - 1) if benchmark_nav[0] > 0 else 0
            bench_cagr = (1 + bench_total_return) ** (252 / max(len(benchmark_nav), 1)) - 1 if len(benchmark_nav) > 1 else 0
            bench_mdd_detail = calculate_max_drawdown(benchmark_nav)
            result["benchmark_comparison"] = {
                "benchmark_name": benchmark_name,
                "benchmark_cumulative_return": round(bench_total_return, 4),
                "benchmark_cagr": round(bench_cagr, 4),
                "benchmark_max_drawdown": round(bench_mdd_detail.get("max_drawdown", 0), 4),
                "excess_return_vs_benchmark": round(total_return - bench_total_return, 4),
            }

    return result


def generate_diagnosis(funds: List[Dict], fund_scores: Dict = None,
                       asset_allocation: Dict = None,
                       fund_manager_ratings: Dict = None,
                       fund_subscores_map: Dict = None,
                       stock_concentration: Dict = None,
                       correlation_level: str = None,
                       industry_allocations: Dict = None) -> Dict:
    """生成账户诊断总览"""
    
    total_weight = 0
    weighted_score = 0
    for fund in funds:
        code = fund["code"]
        weight = fund.get("weight", 1.0 / len(funds))
        score_info = (fund_scores.get(code) or {}) if fund_scores else {}
        score = score_info.get("score", 75) if isinstance(score_info.get("score"), (int, float)) else 75
        weighted_score += score * weight
        total_weight += weight
    
    comprehensive_score = round(weighted_score / total_weight) if total_weight > 0 else 75
    comprehensive_score = max(0, min(100, comprehensive_score))
    
    if comprehensive_score >= 90:
        grade = "A+"
    elif comprehensive_score >= 80:
        grade = "A"
    elif comprehensive_score >= 70:
        grade = "B+"
    elif comprehensive_score >= 60:
        grade = "B"
    else:
        grade = "C"
    
    fund_score_details = []
    for fund in funds:
        code = fund["code"]
        score_info = (fund_scores.get(code) or {}) if fund_scores else {}
        
        fund_score_details.append({
            "code": code,
            "name": fund.get("name", code),
            "return_score": score_info.get("return_score", 75) if isinstance(score_info.get("return_score"), (int, float)) else 75,
            "risk_score": score_info.get("risk_score", 70) if isinstance(score_info.get("risk_score"), (int, float)) else 70,
            "comprehensive_score": score_info.get("score", 72) if isinstance(score_info.get("score"), (int, float)) else 72,
            "grade": score_info.get("grade", "B+")
        })
    
    current_alloc = {}
    if asset_allocation:
        for item in asset_allocation:
            current_alloc[item.get("type", "")] = item.get("weight", 0)
    
    allocation_deviation = {}
    for asset in ["equity", "fixed_income", "cash"]:
        current_weight = current_alloc.get(asset, 0)
        target_weight = TARGET_ALLOCATION.get(asset, 0)
        deviation = current_weight - target_weight
        allocation_deviation[asset] = {
            "current": round(current_weight, 4),
            "target": round(target_weight, 4),
            "deviation": round(deviation, 4)
        }
    
    max_deviation = max(abs(d["deviation"]) for d in allocation_deviation.values())
    if max_deviation > 0.15:
        diagnosis_suggestion = "配置偏离度较大，建议进行再平衡调整"
    elif max_deviation > 0.05:
        diagnosis_suggestion = "配置存在轻度偏离，可择机调整"
    else:
        diagnosis_suggestion = "配置整体合理，保持现有配置"

    result = {
        "comprehensive_score": comprehensive_score,
        "grade": grade,
        "fund_score_details": fund_score_details,
        "allocation_deviation": allocation_deviation,
        "diagnosis_suggestion": diagnosis_suggestion
    }

    # 新增：基金经理评分
    if fund_manager_ratings:
        total_w = sum(f.get("weight", 1.0 / len(funds)) for f in funds) or 1
        w_1y = w_2y = w_3y = 0
        for fund in funds:
            code = fund["code"]
            w = fund.get("weight", 1.0 / len(funds))
            mgr = fund_manager_ratings.get(code, {})
            w_1y += mgr.get("overall_1y", 0) * w
            w_2y += mgr.get("overall_2y", 0) * w
            w_3y += mgr.get("overall_3y", 0) * w
        result["manager_rating"] = {
            "weighted_score_1y": round(w_1y / total_w),
            "weighted_score_2y": round(w_2y / total_w),
            "weighted_score_3y": round(w_3y / total_w),
        }
        manager_ratings_detail = []
        for fund in funds:
            code = fund["code"]
            mgr = fund_manager_ratings.get(code, {})
            if mgr:
                manager_ratings_detail.append({
                    "code": code,
                    "name": fund.get("name", code),
                    "overall_1y": mgr.get("overall_1y", 0),
                    "overall_2y": mgr.get("overall_2y", 0),
                    "overall_3y": mgr.get("overall_3y", 0),
                    "rank_1y": mgr.get("rank_1y", 0),
                    "rank_2y": mgr.get("rank_2y", 0),
                    "ret_1y": mgr.get("ret_1y", 0),
                    "ret_2y": mgr.get("ret_2y", 0),
                    "mdd_1y": mgr.get("mdd_1y", 0),
                    "mdd_2y": mgr.get("mdd_2y", 0),
                    "sca_1y": mgr.get("sca_1y", 0),
                    "sca_2y": mgr.get("sca_2y", 0),
                })
        result["manager_ratings_detail"] = manager_ratings_detail

    # 新增：相关性水平
    if correlation_level:
        result["correlation_level"] = correlation_level

    # 新增：穿透后个股集中度
    if stock_concentration:
        result["stock_concentration"] = stock_concentration

    # 新增：评分子维度
    if fund_subscores_map:
        fund_subscores_detail = []
        for fund in funds:
            code = fund["code"]
            sub = fund_subscores_map.get(code, {})
            if sub:
                fund_subscores_detail.append({
                    "code": code,
                    "name": fund.get("name", code),
                    "rank_1y": sub.get("rank_1y", 0),
                    "rank_2y": sub.get("rank_2y", 0),
                    "nhi_1y": sub.get("nhi_1y", 0),
                    "nhi_2y": sub.get("nhi_2y", 0),
                    "sec_1y": sub.get("sec_1y", 0),
                    "sec_2y": sub.get("sec_2y", 0),
                    "tim_1y": sub.get("tim_1y", 0),
                    "tim_2y": sub.get("tim_2y", 0),
                    "sca_1y": sub.get("sca_1y", 0),
                    "sca_2y": sub.get("sca_2y", 0),
                })
        result["fund_subscores_detail"] = fund_subscores_detail

    # 新增：穿透后行业集中度
    if industry_allocations:
        all_industries = {}
        for fund in funds:
            code = fund["code"]
            w = fund.get("weight", 1.0 / len(funds))
            for ind in industry_allocations.get(code, []):
                name = ind.get("industry", "")
                ind_w = ind.get("weight", 0) * w
                all_industries[name] = all_industries.get(name, 0) + ind_w
        sorted_ind = sorted(all_industries.items(), key=lambda x: x[1], reverse=True)
        if sorted_ind:
            max_ind_name, max_ind_w = sorted_ind[0]
            ind_top5 = [{"name": n, "weight": round(w, 4)} for n, w in sorted_ind[:5]]
            ind_level = "偏高" if max_ind_w > 0.25 else "适中" if max_ind_w > 0.10 else "分散"
            industry_concentration = {
                "max_industry": max_ind_name,
                "max_industry_weight": round(max_ind_w, 4),
                "industry_top5": ind_top5,
                "level": ind_level,
            }
            # 合并到 stock_concentration 中或单独输出
            if stock_concentration:
                result["stock_concentration"]["industry_concentration"] = industry_concentration
            else:
                result["industry_concentration"] = industry_concentration

    return result



def generate_allocation(funds: List[Dict],
                       industry_allocations: Dict[str, List[Dict]],
                       fund_holdings: Dict[str, List[Dict]],
                       fund_infos: Dict = None) -> Dict:
    """生成组合配置诊断"""

    fund_codes = [f["code"] for f in funds]
    fund_weights = {f["code"]: f.get("weight", 1.0/len(funds)) for f in funds}

    # 从基金类型信息推断资产配置
    asset_map = {"equity": 0, "fixed_income": 0, "cash": 0, "commodity": 0, "overseas": 0, "other": 0}
    country_map = {"China": 0, "US": 0, "Japan": 0, "Europe": 0, "India": 0, "HongKong": 0, "Other": 0}

    # QDII/海外基金关键词
    overseas_keywords = ["纳斯达克", "标普", "美国", "全球", "日本", "德国", "DAX", "印度",
                         "香港", "恒生", "沪港深", "QDII", "海外", "标普500"]
    bond_keywords = ["债券", "纯债", "增强债", "信用债", "利率债", "可转债"]
    money_keywords = ["货币", "活钱", "现金"]

    for fund in funds:
        code = fund["code"]
        w = fund_weights.get(code, 0)
        info = (fund_infos or {}).get(code, {})
        ftype = info.get("type", "")
        fname = info.get("name", "") or fund.get("name", "")

        # 判断是否QDII/海外
        is_overseas = any(kw in fname for kw in overseas_keywords)
        is_bond = any(kw in fname for kw in bond_keywords) or any(kw in ftype for kw in bond_keywords)
        is_money = any(kw in fname for kw in money_keywords) or any(kw in ftype for kw in money_keywords)

        if is_overseas:
            asset_map["overseas"] += w
            # 进一步判断国家
            if "纳斯达克" in fname or "标普" in fname or "美国" in fname:
                country_map["US"] += w
            elif "日本" in fname:
                country_map["Japan"] += w
            elif "德国" in fname or "DAX" in fname:
                country_map["Europe"] += w
            elif "印度" in fname:
                country_map["India"] += w
            elif "恒生" in fname or "香港" in fname or "沪港深" in fname:
                country_map["HongKong"] += w
            else:
                country_map["Other"] += w
        elif is_bond:
            asset_map["fixed_income"] += w
            country_map["China"] += w
        elif is_money:
            asset_map["cash"] += w
            country_map["China"] += w
        else:
            asset_map["equity"] += w
            country_map["China"] += w

    # 归一化确保总和为1
    total_asset = sum(asset_map.values())
    if total_asset == 0:
        total_asset = 1.0
    asset_allocation = [
        {"type": k, "weight": round(v / total_asset, 4)}
        for k, v in sorted(asset_map.items(), key=lambda x: x[1], reverse=True) if v > 0
    ]
    total_country = sum(country_map.values())
    if total_country == 0:
        total_country = 1.0
    country_allocation = [
        {"region": k, "weight": round(v / total_country, 4)}
        for k, v in sorted(country_map.items(), key=lambda x: x[1], reverse=True) if v > 0
    ]
    
    all_industries = {}
    for code in fund_codes:
        weight = fund_weights.get(code, 0)
        industries = industry_allocations.get(code, [])
        for ind in industries:
            name = ind.get("industry", "")
            ind_weight = ind.get("weight", 0) * weight
            if name in all_industries:
                all_industries[name]["weight"] += ind_weight
                all_industries[name]["change"] = (all_industries[name]["change"] + ind.get("change", 0)) / 2
            else:
                all_industries[name] = {
                    "weight": ind_weight,
                    "change": ind.get("change", 0)
                }
    
    industry_data = [
        {"industry": k, "weight": round(v["weight"], 4), "change": round(v["change"], 4)}
        for k, v in sorted(all_industries.items(), key=lambda x: x[1]["weight"], reverse=True)[:15]
    ]

    # 新增：QDII基金行业穿透（Wind全球行业11分类）
    qdii_industry_keywords = {
        "信息技术": ["纳斯达克", "半导体", "芯片", "科技", "互联网", "人工智能", "AI"],
        "金融": ["标普", "金融", "银行"],
        "医疗保健": ["生物", "医药", "医疗", "健康"],
        "可选消费": ["消费", "汽车", "零售", "电商"],
        "工业": ["工业", "制造", "DAX", "德国"],
        "能源": ["能源", "石油", "天然气"],
        "公用事业": ["公用事业", "水电", "环保"],
        "材料": ["材料", "化工", "矿业"],
        "必选消费": ["食品", "日用品", "白酒"],
        "房地产": ["房地产", "REIT"],
        "通信服务": ["通信", "传媒", "娱乐"],
    }
    qdii_industries = {}
    for fund in funds:
        code = fund["code"]
        w = fund_weights.get(code, 0)
        fname = ((fund_infos or {}).get(code, {}).get("name", "")) or fund.get("name", "")
        is_overseas = any(kw in fname for kw in overseas_keywords)
        if not is_overseas:
            continue
        # 根据基金名称匹配QDII行业
        matched = False
        for ind_name, keywords in qdii_industry_keywords.items():
            if any(kw in fname for kw in keywords):
                qdii_industries[ind_name] = qdii_industries.get(ind_name, 0) + w
                matched = True
                break
        if not matched:
            qdii_industries["综合"] = qdii_industries.get("综合", 0) + w
    qdii_industry_allocation = [
        {"industry": k, "weight": round(v, 4)}
        for k, v in sorted(qdii_industries.items(), key=lambda x: x[1], reverse=True) if v > 0
    ]

    all_holdings = {}
    for code in fund_codes:
        weight = fund_weights.get(code, 0)
        holdings = fund_holdings.get(code, [])
        for hold in holdings:
            stock = hold.get("stock", "")
            hold_weight = hold.get("weight", 0) * weight
            if stock in all_holdings:
                all_holdings[stock]["weight"] += hold_weight
            else:
                all_holdings[stock] = {
                    "weight": hold_weight,
                    "style": hold.get("style", "未知")
                }
    
    top_holdings = [
        {"stock": k, "weight": round(v["weight"], 4), "style": v["style"]}
        for k, v in sorted(all_holdings.items(), key=lambda x: x[1]["weight"], reverse=True)[:15]
    ]
    
    if fund_infos:
        # 从 fund_infos 构建基金经理数据（合并同名经理）
        mgr_agg = {}
        for code in fund_codes:
            mgr_name = (fund_infos.get(code) or {}).get("manager", "")
            if not mgr_name or "基金经理" in mgr_name:
                continue
            w = fund_weights.get(code, 0)
            if mgr_name in mgr_agg:
                mgr_agg[mgr_name]["weight"] += w
                mgr_agg[mgr_name]["funds"].append(code)
            else:
                mgr_agg[mgr_name] = {"weight": w, "funds": [code]}
        manager_data = [
            {"name": k, "weight": round(v["weight"], 4), "funds": v["funds"]}
            for k, v in sorted(mgr_agg.items(), key=lambda x: x[1]["weight"], reverse=True)
        ]
    else:
        manager_data = []
    
    industry_weights = [item["weight"] for item in industry_data[:10] if item["weight"] > 0]
    hhi = calculate_hhi(industry_weights)
    concentration_risk = "高" if hhi > 0.15 else "中" if hhi > 0.10 else "低"
    
    style_distribution = {"价值": 0.40, "成长": 0.45, "防御": 0.15}
    if top_holdings:
        style_totals = {}
        for hold in top_holdings:
            style = hold.get("style", "未知")
            weight = hold.get("weight", 0)
            style_totals[style] = style_totals.get(style, 0) + weight
        if style_totals:
            total_style_weight = sum(style_totals.values())
            if total_style_weight > 0:
                style_distribution = {
                    k: round(v / total_style_weight, 4) 
                    for k, v in sorted(style_totals.items(), key=lambda x: x[1], reverse=True)
                }
    
    # 新增：基金公司穿透（按管理公司聚合持仓占比）
    company_agg = {}
    for code in fund_codes:
        info = (fund_infos or {}).get(code, {})
        company = info.get("company", "")
        if not company:
            continue
        w = fund_weights.get(code, 0)
        if company in company_agg:
            company_agg[company]["weight"] += w
            company_agg[company]["funds"].append(code)
        else:
            company_agg[company] = {"weight": w, "funds": [code]}
    fund_companies = [
        {"name": k, "weight": round(v["weight"], 4), "funds": v["funds"]}
        for k, v in sorted(company_agg.items(), key=lambda x: x[1]["weight"], reverse=True)
    ]

    # 新增：组合配置评价定性字段
    # 计算当前各资产权重
    equity_ratio = sum(item["weight"] for item in asset_allocation if item["type"] == "equity")
    overseas_ratio = sum(item["weight"] for item in asset_allocation if item["type"] == "overseas")
    fixed_income_ratio = sum(item["weight"] for item in asset_allocation if item["type"] == "fixed_income")

    # 行情适配性评语
    market_comments = []
    if equity_ratio > 0.70:
        market_comments.append("权益仓位偏高，在震荡市中需关注回撤风险")
    elif equity_ratio > 0.40:
        market_comments.append("权益仓位适中，攻守兼备")
    else:
        market_comments.append("权益仓位偏低，可适当增加以提升长期收益空间")
    if overseas_ratio > 0.20:
        market_comments.append("海外配置占比较高，需关注汇率及地缘风险")
    elif overseas_ratio > 0:
        market_comments.append("海外配置有助于分散单一市场风险")
    if fixed_income_ratio > 0.30:
        market_comments.append("固收配置充裕，组合防御性较好")
    market_comment = "；".join(market_comments) if market_comments else "配置整体均衡"

    # 建议配置方向
    suggestions = []
    for asset in ["equity", "fixed_income", "cash"]:
        current_w = sum(item["weight"] for item in asset_allocation if item["type"] == asset)
        target_w = TARGET_ALLOCATION.get(asset, 0)
        deviation = current_w - target_w
        asset_cn = {"equity": "权益", "fixed_income": "固收", "cash": "现金"}.get(asset, asset)
        if abs(deviation) > 0.05:
            if deviation > 0:
                suggestions.append(f"{asset_cn}超配{deviation*100:.1f}%，建议减配")
            else:
                suggestions.append(f"{asset_cn}低配{abs(deviation)*100:.1f}%，建议加配")
    if concentration_risk != "低":
        suggestions.append("行业集中度偏高，建议分散至不同行业板块")
    suggested_direction = "；".join(suggestions) if suggestions else "当前配置基本合理，建议维持"

    return {
        "asset_allocation": asset_allocation,
        "country_allocation": country_allocation,
        "industry_allocation": industry_data,
        "qdii_industry_allocation": qdii_industry_allocation,
        "top_holdings": top_holdings,
        "fund_managers": manager_data,
        "fund_companies": fund_companies,
        "concentration_risk": {
            "hhi": hhi,
            "level": concentration_risk,
            "warning": "行业集中度偏高，建议适当分散" if concentration_risk != "低" else ""
        },
        "holding_style_tags": style_distribution,
        "market_comment": market_comment,
        "suggested_direction": suggested_direction,
    }


def generate_correlation(funds: List[Dict], fund_navs: Dict[str, List[float]]) -> Dict:
    """生成相关性分析"""

    fund_codes = [f["code"] for f in funds]
    n = len(fund_codes)

    if n < 2:
        return {
            "correlation_matrix": {"funds": fund_codes, "matrix": [[1.0]]},
            "groups": [],
            "high_correlation_pairs": [],
            "rebalancing_suggestion": "基金数量不足，无法进行相关性分析"
        }

    fund_returns_map = {}
    for code in fund_codes:
        navs = fund_navs.get(code, [])
        fund_returns_map[code] = nav_to_returns(navs)

    # Pandas path: build DataFrame, use .corr()
    if HAS_PANDAS:
        try:
            # Align all return series to the same length (use minimum)
            min_len = min(len(r) for r in fund_returns_map.values() if r)
            if min_len >= 2:
                aligned = {code: returns[:min_len] for code, returns in fund_returns_map.items() if returns}
                df = pd.DataFrame(aligned, dtype=float)
                corr_df = df.corr()
                correlation_matrix = []
                for i, code1 in enumerate(fund_codes):
                    row = []
                    for j, code2 in enumerate(fund_codes):
                        if code1 in corr_df.columns and code2 in corr_df.columns:
                            row.append(round(float(corr_df.loc[code1, code2]), 4))
                        else:
                            row.append(1.0 if i == j else 0.0)
                    correlation_matrix.append(row)
            else:
                correlation_matrix = None
        except Exception:
            correlation_matrix = None
    else:
        correlation_matrix = None

    # Fallback: pairwise calculate_correlation
    if correlation_matrix is None:
        correlation_matrix = []
        for i, code1 in enumerate(fund_codes):
            row = []
            returns1 = fund_returns_map.get(code1, [])
            for j, code2 in enumerate(fund_codes):
                if i == j:
                    row.append(1.0)
                else:
                    returns2 = fund_returns_map.get(code2, [])
                    corr = calculate_correlation(returns1, returns2)
                    row.append(corr)
            correlation_matrix.append(row)

    high_correlation_pairs = []
    for i, code1 in enumerate(fund_codes):
        for j, code2 in enumerate(fund_codes):
            if i < j and correlation_matrix[i][j] > 0.85:
                high_correlation_pairs.append({
                    "fund1": code1,
                    "fund1_name": funds[i].get("name", code1),
                    "fund2": code2,
                    "fund2_name": funds[j].get("name", code2),
                    "correlation": correlation_matrix[i][j]
                })

    groups = []
    used = set()
    for i, fund in enumerate(funds):
        if i in used:
            continue
        group = [fund["code"]]
        used.add(i)
        for j in range(i + 1, n):
            if j not in used and correlation_matrix[i][j] > 0.7:
                group.append(funds[j]["code"])
                used.add(j)
        if len(group) > 1:
            corr_sum = 0
            corr_count = 0
            for code1 in group:
                idx1 = fund_codes.index(code1)
                for code2 in group:
                    idx2 = fund_codes.index(code2)
                    if code1 != code2:
                        corr_sum += correlation_matrix[idx1][idx2]
                        corr_count += 1
            avg_corr = corr_sum / corr_count if corr_count > 0 else 0

            group_pairs = [p for p in high_correlation_pairs
                          if p["fund1"] in group or p["fund2"] in group]

            group_names = [funds[fund_codes.index(code)].get("name", code) for code in group]

            groups.append({
                "funds": group,
                "fund_names": group_names,
                "average_correlation": round(avg_corr, 4),
                "high_correlation_pairs": group_pairs
            })

    if high_correlation_pairs:
        rebalancing_suggestion = f"发现{len(high_correlation_pairs)}对高相关基金，建议合并或选择差异化产品"
    elif groups:
        rebalancing_suggestion = "存在中等相关性基金组，可考虑优化配置"
    else:
        rebalancing_suggestion = "基金相关性整体可控"

    # 计算平均两两相关性（上三角非对角线元素均值）
    avg_pairwise = 0.0
    if n >= 2:
        upper_vals = []
        for i in range(n):
            for j in range(i + 1, n):
                upper_vals.append(correlation_matrix[i][j])
        if upper_vals:
            avg_pairwise = round(sum(upper_vals) / len(upper_vals), 4)

    return {
        "correlation_matrix": {
            "funds": fund_codes,
            "matrix": correlation_matrix
        },
        "average_pairwise_correlation": avg_pairwise,
        "groups": groups,
        "high_correlation_pairs": high_correlation_pairs,
        "rebalancing_suggestion": rebalancing_suggestion
    }


def generate_evaluation(funds: List[Dict], fund_evaluations: Dict = None,
                       fund_infos: Dict = None, fund_navs: Dict[str, List[float]] = None,
                       fund_nav_dates: Dict[str, List[str]] = None,
                       fund_holdings: Dict[str, List[Dict]] = None,
                       fund_manager_ratings: Dict = None,
                       fund_subscores_map: Dict = None,
                       fund_announcements: Dict = None,
                       benchmark_nav_series: List[float] = None,
                       benchmark_nav_dates: List[str] = None) -> Dict:
    """生成单只基金评价"""

    evaluations = []
    index_fund_valuations = []

    for fund in funds:
        code = fund["code"]
        info_name = fund.get("name", code)
        is_index = "指数" in info_name or "ETF" in info_name

        eval_data = (fund_evaluations.get(code) or {}) if fund_evaluations else {}
        info = (fund_infos.get(code) or {}) if fund_infos else {}

        # Per-fund risk metrics
        navs = (fund_navs or {}).get(code, [])
        dates_list = (fund_nav_dates or {}).get(code, None)
        risk_metrics = calculate_per_fund_risk_metrics(navs, dates_list)

        # Per-fund multi-period returns
        mp_returns = calculate_multi_period_returns(navs, dates_list)

        # Top 5 holdings
        holdings = (fund_holdings or {}).get(code, [])
        top_5 = holdings[:5] if holdings else []

        # 基金净值 vs 基准（近3年）
        fund_nav_vs_benchmark = {}
        if navs and benchmark_nav_series:
            min_nav_len = min(len(navs), len(benchmark_nav_series))
            if min_nav_len >= 10:
                fund_nav_vs_benchmark = {
                    "fund_nav": [round(v, 4) for v in navs[-min_nav_len:]],
                    "benchmark_nav": [round(v, 4) for v in benchmark_nav_series[-min_nav_len:]],
                }

        if is_index:
            idx_entry = {
                "code": code,
                "name": info_name,
                "fund_type": info.get("type", ""),
                "manager": info.get("manager", ""),
                "evaluation_path": "指数型",
                "excess_return": eval_data.get("excess_return", 0),
                "pe_percentile": eval_data.get("pe_percentile", 50),
                "valuation": eval_data.get("valuation", "适中"),
                "suggestion": eval_data.get("suggestion", "估值适中"),
                **risk_metrics,
                "multi_period_returns": mp_returns,
                "top_5_holdings": top_5,
            }
            # 跟踪标的指数
            track_idx = info.get("benchmark", info.get("track_index", ""))
            if not track_idx:
                # 基于基金名称推断跟踪指数
                track_index_map = [
                    (["纳斯达克100"], "纳斯达克100指数"),
                    (["纳斯达克"], "纳斯达克综合指数"),
                    (["标普500"], "标普500指数"),
                    (["标普"], "标普500指数"),
                    (["德国DAX", "DAX"], "德国DAX指数"),
                    (["恒生科技"], "恒生科技指数"),
                    (["恒生"], "恒生指数"),
                    (["日经"], "日经225指数"),
                    (["创业板"], "创业板指"),
                    (["沪深300"], "沪深300指数"),
                    (["中证500"], "中证500指数"),
                    (["上证50"], "上证50指数"),
                    (["科创"], "科创50指数"),
                    (["中证1000"], "中证1000指数"),
                    (["国证2000"], "国证2000指数"),
                ]
                for keywords, idx_name in track_index_map:
                    if any(kw in info_name for kw in keywords):
                        track_idx = idx_name
                        break
            idx_entry["track_index"] = track_idx
            if fund_nav_vs_benchmark:
                idx_entry["fund_nav_vs_benchmark"] = fund_nav_vs_benchmark
            index_fund_valuations.append(idx_entry)
        else:
            entry = {
                "code": code,
                "name": info_name,
                "fund_type": info.get("type", ""),
                "manager": info.get("manager", ""),
                "evaluation_path": "主动型",
                "comprehensive_score": eval_data.get("score", 75),
                "score_1y": eval_data.get("score_1y", eval_data.get("score", 75)),
                "score_2y": eval_data.get("score_2y", eval_data.get("score", 75)),
                "score_3y": eval_data.get("score_3y", eval_data.get("score", 75)),
                "grade": eval_data.get("grade", "B+"),
                "suggestion": eval_data.get("suggestion", "持有"),
                **risk_metrics,
                "multi_period_returns": mp_returns,
                "top_5_holdings": top_5,
            }

            # 新增：子维度得分
            sub = (fund_subscores_map or {}).get(code, {})
            if sub:
                entry["subscores"] = {
                    "rank_1y": sub.get("rank_1y", 0),
                    "rank_2y": sub.get("rank_2y", 0),
                    "nhi_1y": sub.get("nhi_1y", 0),
                    "nhi_2y": sub.get("nhi_2y", 0),
                    "sec_1y": sub.get("sec_1y", 0),
                    "sec_2y": sub.get("sec_2y", 0),
                    "tim_1y": sub.get("tim_1y", 0),
                    "tim_2y": sub.get("tim_2y", 0),
                    "sca_1y": sub.get("sca_1y", 0),
                    "sca_2y": sub.get("sca_2y", 0),
                }

            # 新增：基金经理评分（多期限）
            mgr = (fund_manager_ratings or {}).get(code, {})
            if mgr:
                entry["manager_rating"] = {
                    "overall_1y": mgr.get("overall_1y", 0),
                    "overall_2y": mgr.get("overall_2y", 0),
                    "overall_3y": mgr.get("overall_3y", 0),
                    "rank_1y": mgr.get("rank_1y", 0),
                    "rank_2y": mgr.get("rank_2y", 0),
                    "ret_1y": mgr.get("ret_1y", 0),
                    "ret_2y": mgr.get("ret_2y", 0),
                    "mdd_1y": mgr.get("mdd_1y", 0),
                    "mdd_2y": mgr.get("mdd_2y", 0),
                    "sca_1y": mgr.get("sca_1y", 0),
                    "sca_2y": mgr.get("sca_2y", 0),
                }

            # 新增：公告/舆情
            ann = (fund_announcements or {}).get(code, {})
            if ann:
                entry["announcement"] = {
                    "negative_events": ann.get("negative_events", []),
                    "has_negative": ann.get("has_negative", False),
                    "summary": ann.get("summary", ""),
                }

            # 新增：操作建议
            rec, rec_reason = generate_operational_recommendation(
                entry["comprehensive_score"],
                eval_data.get("return_score", 75),
                eval_data.get("risk_score", 70),
                entry["grade"],
                mgr if mgr else None,
            )
            entry["recommendation"] = rec
            entry["recommendation_reason"] = rec_reason

            if fund_nav_vs_benchmark:
                entry["fund_nav_vs_benchmark"] = fund_nav_vs_benchmark

            evaluations.append(entry)

    evaluations.sort(key=lambda x: x.get("comprehensive_score", 0), reverse=True)

    return {
        "fund_evaluations": evaluations,
        "index_fund_valuations": index_fund_valuations
    }


def generate_rebalance(funds: List[Dict], current_allocation: Dict = None,
                       fund_evaluations: Dict = None,
                       fund_scores: Dict = None,
                       correlation_data: Dict = None) -> Dict:
    """生成调仓建议"""

    current = current_allocation or {
        "equity": 0.72,
        "fixed_income": 0.15,
        "cash": 0.13
    }

    target = TARGET_ALLOCATION

    allocation_comparison = []
    for asset in ["equity", "fixed_income", "cash"]:
        current_weight = current.get(asset, 0)
        target_weight = target.get(asset, 0)
        deviation = current_weight - target_weight
        status = "超配" if deviation > 0.01 else "低配" if deviation < -0.01 else "正常"
        allocation_comparison.append({
            "asset": asset,
            "current": round(current_weight, 4),
            "target": round(target_weight, 4),
            "deviation": round(deviation, 4),
            "status": status
        })

    reduce_suggestions = []
    for item in allocation_comparison:
        if item["deviation"] > 0.01:
            reduce_suggestions.append({
                "asset": item["asset"],
                "overweight": round(item["deviation"], 4),
                "suggested_action": f"减配{item['asset']}，建议赎回比例: {round(item['deviation'] * 100, 1)}%",
                "funds_to_reduce": ["建议选择近期表现较弱或相关性高的基金"]
            })

    increase_suggestions = []
    for item in allocation_comparison:
        if item["deviation"] < -0.01:
            increase_suggestions.append({
                "asset": item["asset"],
                "underweight": round(abs(item["deviation"]), 4),
                "target_weight": round(item["target"], 4),
                "suggested_action": f"加配{item['asset']}，建议增持比例: {round(abs(item['deviation']) * 100, 1)}%",
                "funds_to_increase": ["建议选择优质固收基金或货币基金"]
            })

    # 新增：基金替换建议（评分最低的基金）
    fund_replacement_suggestions = []
    if fund_scores:
        scored_funds = []
        for fund in funds:
            code = fund["code"]
            sc = fund_scores.get(code, {})
            score = sc.get("score", 75) if isinstance(sc.get("score"), (int, float)) else 75
            scored_funds.append((fund, score))
        scored_funds.sort(key=lambda x: x[1])
        for fund, score in scored_funds:
            if score < 70:
                action = "替换" if score < 60 else "减仓"
                reason = f"综合评分{score}分，" + ("表现较差建议替换" if score < 60 else "表现中下建议减仓")
                fund_replacement_suggestions.append({
                    "code": fund["code"],
                    "name": fund.get("name", fund["code"]),
                    "reason": reason,
                    "action": action,
                    "score": score,
                })

    # 新增：推荐基金（从同类型高评分基金推断）
    recommended_funds = []
    if fund_evaluations:
        for fund in funds:
            code = fund["code"]
            ev = fund_evaluations.get(code, {})
            score = ev.get("score", 0) if isinstance(ev.get("score"), (int, float)) else 0
            if score >= 80:
                recommended_funds.append({
                    "name": fund.get("name", code),
                    "code": code,
                    "score": score,
                    "manager_score": None,
                    "brief": f"当前持仓中评分较高({score}分)，可作为核心持仓保留",
                })
    # 只保留 top 3 推荐
    recommended_funds = sorted(recommended_funds, key=lambda x: x["score"], reverse=True)[:3]

    # 新增：外部基金池推荐（占位，需要接入创金量化基金池数据源）
    external_recommendations = {
        "note": "需接入创金量化外部基金池数据源",
        "data_source": "创金量化基金池",
        "recommendations": [],
    }

    # 新增：替换批次安排
    batch_schedule = []
    if fund_replacement_suggestions:
        total_funds_to_replace = len(fund_replacement_suggestions)
        batch_size = max(1, (total_funds_to_replace + 2) // 3)
        now = datetime.now()
        for batch_idx in range(3):
            start = batch_idx * batch_size
            end = min(start + batch_size, total_funds_to_replace)
            batch_funds = [f["name"] for f in fund_replacement_suggestions[start:end]]
            if not batch_funds:
                break
            batch_time = (now + timedelta(days=30 * batch_idx)).strftime("%Y-%m")
            batch_schedule.append({
                "batch": batch_idx + 1,
                "time": batch_time,
                "funds": batch_funds,
                "amount": f"约{len(batch_funds)}只基金",
            })

    # 新增：调仓后预期
    post_rebalance = None
    if allocation_comparison:
        max_dev = max(abs(item["deviation"]) for item in allocation_comparison)
        post_rebalance = {
            "allocation": [
                {"type": item["asset"], "weight": round(item["target"], 4)}
                for item in allocation_comparison
            ],
            "correlation_improvement": "通过替换低评分基金，预计组合相关性结构将改善",
            "expected_improvement": f"调整后最大配置偏离度从{max_dev*100:.1f}%降至<3%，风险收益比优化",
        }

        # 新增：调仓后相关系数矩阵（移除替换基金后的子矩阵）
        if correlation_data and fund_replacement_suggestions:
            replace_codes = {f["code"] for f in fund_replacement_suggestions}
            corr_matrix_data = correlation_data.get("correlation_matrix", {})
            fund_codes_list = corr_matrix_data.get("funds", [])
            matrix = corr_matrix_data.get("matrix", [])
            # 计算保留基金的索引
            keep_indices = [i for i, c in enumerate(fund_codes_list) if c not in replace_codes]
            keep_codes = [fund_codes_list[i] for i in keep_indices]
            keep_matrix = []
            for i in keep_indices:
                row = [matrix[i][j] for j in keep_indices]
                keep_matrix.append(row)
            # 计算调仓后平均相关性
            n_keep = len(keep_codes)
            post_avg_corr = 0.0
            if n_keep >= 2:
                upper_vals = []
                for i in range(n_keep):
                    for j in range(i + 1, n_keep):
                        upper_vals.append(keep_matrix[i][j])
                post_avg_corr = round(sum(upper_vals) / len(upper_vals), 4) if upper_vals else 0.0
            post_rebalance["post_correlation_matrix"] = {
                "funds": keep_codes,
                "matrix": keep_matrix,
                "average_pairwise_correlation": post_avg_corr,
            }

    result = {
        "allocation_comparison": allocation_comparison,
        "reduce_suggestions": reduce_suggestions,
        "increase_suggestions": increase_suggestions,
        "expected_improvement": "调整后组合风险收益比将更接近目标水平，预期年化波动率降低约5%"
    }

    if fund_replacement_suggestions:
        result["fund_replacement_suggestions"] = fund_replacement_suggestions
    if recommended_funds:
        result["recommended_funds"] = recommended_funds
    result["external_recommendations"] = external_recommendations
    if batch_schedule:
        result["batch_schedule"] = batch_schedule
    if post_rebalance:
        result["post_rebalance"] = post_rebalance

    return result


def generate_risk(funds: List[Dict], returns: List[float] = None,
                  asset_allocation: List[Dict] = None,
                  current_weights: List[float] = None,
                  max_drawdown_detail: Dict = None) -> Dict:
    """生成风险提示"""

    if returns:
        returns_stats = calculate_returns_stats(returns)
    else:
        mock_returns = []
        for i, fund in enumerate(funds):
            mock_returns.append(generate_mock_nav_series(fund["code"], DEFAULT_ANALYSIS_PERIOD_DAYS))
        if mock_returns:
            avg_nav = [sum(nav[i] for nav in mock_returns) / len(mock_returns) for i in range(len(mock_returns[0]))]
            returns = nav_to_returns(avg_nav)
        else:
            returns = []
        returns_stats = calculate_returns_stats(returns)

    # Empyrical path: use library-calculated annual values
    if HAS_EMPYRICAL and HAS_PANDAS and returns:
        try:
            returns_s = pd.Series(returns, dtype=float)
            vol = empyrical.annual_volatility(returns_s)
            ann_ret = empyrical.annual_return(returns_s)
            volatility = float(vol) if vol is not None and not pd.isna(vol) else returns_stats["std"] * math.sqrt(252)
            base_return = float(ann_ret) if ann_ret is not None and not pd.isna(ann_ret) else returns_stats["mean"] * 252
        except Exception:
            volatility = returns_stats["std"] * math.sqrt(252) if returns_stats["std"] else 0.18
            base_return = returns_stats["mean"] * 252 if returns_stats["mean"] else 0.08
    else:
        volatility = returns_stats["std"] * math.sqrt(252) if returns_stats["std"] else 0.18
        base_return = returns_stats["mean"] * 252 if returns_stats["mean"] else 0.08

    scenario_analysis = [
        {"scenario": "牛市(+1σ)", "expected_return": round(base_return + volatility, 4),
         "expected_drawdown": round(-volatility * 0.5, 4), "probability": "约16%"},
        {"scenario": "基准", "expected_return": round(base_return, 4),
         "expected_drawdown": round(-volatility * 0.8, 4), "probability": "约68%"},
        {"scenario": "熊市(-1σ)", "expected_return": round(base_return - volatility, 4),
         "expected_drawdown": round(-volatility * 1.5, 4), "probability": "约16%"}
    ]

    equity_ratio = 0.72
    overseas_ratio = 0.15
    if asset_allocation:
        for item in asset_allocation:
            if item.get("type") == "equity":
                equity_ratio = item.get("weight", 0.72)
            elif item.get("type") == "overseas":
                overseas_ratio = item.get("weight", 0.15)

    market_risks = []
    if equity_ratio > 0.70:
        market_risks.append(f"权益仓位偏高({round(equity_ratio * 100, 1)}%)，市场下跌时组合回撤风险较大")
    if overseas_ratio > 0.20:
        market_risks.append(f"海外资产占比({round(overseas_ratio * 100, 1)}%)较高，面临汇率风险")
    if len(funds) > 15:
        market_risks.append(f"基金数量({len(funds)}只)偏多，管理复杂度上升")
    if not market_risks:
        market_risks.append("市场风险整体可控")

    low_weight_count = sum(1 for w in (current_weights or []) if w < 0.03)
    liquidity_risks = []
    if low_weight_count > 5:
        liquidity_risks.append(f"低权重基金({low_weight_count}只)占比较高，可能影响组合灵活性")
    liquidity_risks.append("整体流动性风险可控，主流基金赎回通常T+3到账")

    result = {
        "risk_level": "高" if volatility > 0.25 else "中" if volatility > 0.15 else "低",
        "scenario_analysis": scenario_analysis,
        "market_risks": market_risks,
        "liquidity_risks": liquidity_risks
    }

    # 最大回撤时间区间
    if max_drawdown_detail:
        dd_period = {}
        if max_drawdown_detail.get("start_date") and max_drawdown_detail.get("end_date"):
            dd_period = {
                "start_date": max_drawdown_detail["start_date"],
                "end_date": max_drawdown_detail["end_date"],
            }
        if dd_period:
            result["max_drawdown_period"] = dd_period

    return result


def generate_summary(report: Dict) -> Dict:
    """生成报告总结（核心发现/关键风险/优化建议）"""
    findings = []
    risks = []
    suggestions = []

    diag = report.get("diagnosis", {})
    ov = report.get("overview", {})
    perf = report.get("performance", {})
    alloc = report.get("allocation", {})
    corr = report.get("correlation", {})
    risk_mod = report.get("risk", {})
    reb = report.get("rebalance", {})

    # 核心发现
    bi = ov.get("basic_info", {})
    score = diag.get("comprehensive_score", 0)
    grade = diag.get("grade", "")
    findings.append(f"综合诊断得分{score}分（等级{grade}），持有{bi.get('fund_count', 0)}只基金")

    profit_rate = bi.get("profit_rate", 0)
    total_mv = bi.get("total_market_value", 0)
    total_cost = bi.get("total_cost", 0)
    if total_mv > 0:
        profit = total_mv - total_cost
        findings.append(f"总市值{total_mv:,.0f}元，总成本{total_cost:,.0f}元，浮盈亏{profit:+,.0f}元（{profit_rate*100:+.2f}%）")

    pm = perf.get("performance_metrics", {})
    cum_ret = pm.get("cumulative_return", 0)
    mdd = pm.get("max_drawdown", 0)
    sharpe = pm.get("sharpe_ratio", 0)
    findings.append(f"组合累计收益{cum_ret*100:.2f}%，最大回撤{mdd*100:.2f}%，夏普比率{sharpe:.2f}")

    avg_corr = corr.get("average_pairwise_correlation", 0)
    findings.append(f"平均两两相关性{avg_corr:.4f}，{'分散度良好' if avg_corr < 0.3 else '相关性偏高需关注'}")

    investment_years = ov.get("investment_years")
    if investment_years:
        findings.append(f"投资年限{investment_years}年")

    # 关键风险
    alerts = ov.get("concentration_alerts", [])
    for a in alerts:
        risks.append(a.get("message", ""))

    risk_level = risk_mod.get("risk_level", "")
    risks.append(f"整体风险等级: {risk_level}")

    for mr in risk_mod.get("market_risks", []):
        risks.append(mr)

    conc = alloc.get("concentration_risk", {})
    if conc.get("level") in ("高", "中"):
        risks.append(f"行业集中度{conc.get('level')}（HHI={conc.get('hhi', 0):.4f}）")

    high_pairs = corr.get("high_correlation_pairs", [])
    if high_pairs:
        risks.append(f"存在{len(high_pairs)}对高相关基金(>0.85)，分散化效果受限")

    # 优化建议
    diag_suggestion = diag.get("diagnosis_suggestion", "")
    if diag_suggestion:
        suggestions.append(diag_suggestion)

    alloc_dev = diag.get("allocation_deviation", {})
    for asset, dev in alloc_dev.items():
        if abs(dev.get("deviation", 0)) > 0.05:
            asset_name = {"equity": "权益", "fixed_income": "固收", "cash": "现金"}.get(asset, asset)
            status = "超配" if dev["deviation"] > 0 else "低配"
            suggestions.append(f"{asset_name}资产{status}{abs(dev['deviation'])*100:.1f}%，建议调整至目标配置")

    corr_suggestion = corr.get("rebalancing_suggestion", "")
    if corr_suggestion and corr_suggestion != "基金相关性整体可控":
        suggestions.append(corr_suggestion)

    # 基金评价汇总
    ev = report.get("evaluation", {})
    replace_funds = []
    for fe in ev.get("fund_evaluations", []):
        rec = fe.get("recommendation", "继续持有")
        if "替换" in rec:
            replace_funds.append(fe.get("name", fe.get("code", "")))
    if replace_funds:
        suggestions.append(f"建议替换以下基金: {', '.join(replace_funds[:5])}")

    overall = "账户整体表现" + ("优秀" if score >= 85 else "良好" if score >= 70 else "一般" if score >= 60 else "待优化")
    overall += f"，得分{score}分{grade}级。"

    return {
        "core_findings": findings[:5],
        "key_risks": risks[:5],
        "optimization_suggestions": suggestions[:5],
        "overall_assessment": overall
    }
