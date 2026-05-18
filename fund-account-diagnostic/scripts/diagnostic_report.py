#!/usr/bin/env python3
"""
基金账户诊断报告生成器 - 主入口

Usage:
    python diagnostic_report.py --funds "000001,000002" --output report.json
    python diagnostic_report.py --transaction-file trades.xlsx --format html --output report.html
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional

from constants import (
    QIEMAN_MCP_URL, QIEMAN_API_KEY, DEFAULT_ANALYSIS_PERIOD_DAYS,
    HAS_PANDAS, TARGET_ALLOCATION,
)
from mcp_client import is_api_available
from data_fetcher import (
    get_fund_info, get_fund_nav, get_fund_industry_allocation,
    get_fund_holdings, get_fund_evaluation, get_index_nav,
    get_fund_manager_rating, get_fund_subscores, get_fund_announcement,
    get_portfolio_nav,
)
from calculations import (
    calculate_portfolio_nav, nav_to_returns,
    compute_stock_concentration, select_benchmark_index,
    calculate_portfolio_metrics,
)
from excel_parser import parse_transaction_excel
from generators import (
    generate_overview, generate_performance, generate_diagnosis,
    generate_allocation, generate_correlation, generate_evaluation,
    generate_rebalance, generate_risk, generate_summary,
)


# ============================================================
# 主报告生成
# ============================================================

def generate_full_report(funds: List[Dict], options: Dict = None, transaction_stats: Dict = None) -> Dict:
    """生成完整诊断报告"""
    
    opts = options or {}
    # 模块顺序按用户阅读习惯: 总评→持仓→收益→风险→配置→相关→评价→建议
    DEFAULT_MODULES = ["diagnosis", "overview", "performance", "risk", "allocation",
                       "correlation", "evaluation", "rebalance", "summary"]
    modules = opts.get("modules", DEFAULT_MODULES)
    
    report_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    api_available = is_api_available()
    
    # 获取基金信息（批量）
    fund_infos = {}
    current_prices = {}
    fund_scores = {}
    fund_navs = {}
    fund_dates = {}
    industry_allocations = {}
    fund_holdings = {}
    fund_evaluations = {}
    fund_manager_ratings = {}
    fund_subscores_map = {}
    fund_announcements = {}
    dates = None

    for fund in funds:
        code = fund["code"]

        # 获取基金基础信息
        info, info_real = get_fund_info(code)
        # 优先使用从Excel解析出的基金名称，其次使用API返回的名称，最后使用code
        parsed_name = fund.get("name", "")
        fund_name = parsed_name if parsed_name and not parsed_name.startswith("基金") else info.get("name", parsed_name or code)
        fund_infos[code] = {"name": fund_name, "type": info.get("type", ""), "manager": info.get("manager", ""), "company": info.get("company", "")}
        current_prices[code] = info.get("nav", info.get("total_nav", 1.0))

        # 获取基金净值序列
        nav_data, nav_real = get_fund_nav(code)
        fund_navs[code] = nav_data.get("nav_series", [])
        if "dates" in nav_data:
            fund_dates[code] = nav_data["dates"]

        # 获取行业配置
        industry_data, _ = get_fund_industry_allocation(code)
        industry_allocations[code] = industry_data.get("allocation", [])

        # 获取重仓股
        holdings_data, _ = get_fund_holdings(code)
        fund_holdings[code] = holdings_data.get("holdings", [])

        # 获取基金评价
        eval_data, _ = get_fund_evaluation(code, "active")
        fund_evaluations[code] = eval_data
        fund_scores[code] = {
            "score": eval_data.get("score", 75),
            "suggestion": eval_data.get("suggestion", "持有"),
            "return_score": eval_data.get("return_score", 75),
            "risk_score": eval_data.get("risk_score", 70),
            "grade": eval_data.get("grade", "B+")
        }

        # 新增：获取基金经理评分
        mgr_data, _ = get_fund_manager_rating(code)
        fund_manager_ratings[code] = mgr_data

        # 新增：获取基金评分子维度
        sub_data, _ = get_fund_subscores(code)
        fund_subscores_map[code] = sub_data

        # 新增：获取基金公告/舆情
        ann_data, _ = get_fund_announcement(code)
        fund_announcements[code] = ann_data
    
    # 补充基金名称和计算权重
    total_market_value = 0
    for fund in funds:
        code = fund["code"]
        fund["name"] = fund_infos.get(code, {}).get("name", fund.get("name", code))
        shares = fund.get("shares", 0)
        nav = current_prices.get(code, 1.0)
        fund["market_value"] = shares * nav
        total_market_value += fund["market_value"]
    
    for fund in funds:
        if total_market_value == 0:
            fund["weight"] = 1.0 / len(funds)
        else:
            fund["weight"] = fund["market_value"] / total_market_value
    
    report = {
        "report_header": {
            "generate_time": report_time,
            "data_source": "qieman MCP API" if api_available else "交易记录解析",
            "api_available": api_available,
            "mcp_url": QIEMAN_MCP_URL,
            "tool_version": "1.5.0",
            "analysis_period": f"近{DEFAULT_ANALYSIS_PERIOD_DAYS}个交易日",
            "data_from_transaction": transaction_stats is not None
        }
    }
    
    if fund_dates:
        dates = list(fund_dates.values())[0]

    # --- 新增：获取基准指数数据 ---
    benchmark_data = None
    benchmark_index = select_benchmark_index(fund_infos)
    benchmark_result, _ = get_index_nav(benchmark_index, 756)  # 3年数据
    if benchmark_result and benchmark_result.get("nav_series"):
        benchmark_data = benchmark_result

    # --- 新增：计算穿透后个股集中度 ---
    fund_weights_for_conc = {f["code"]: f.get("weight", 1.0 / len(funds)) for f in funds}
    stock_concentration = compute_stock_concentration(fund_holdings, fund_weights_for_conc)

    # --- 先生成所有模块数据（到临时变量），再按用户阅读顺序插入 ---
    _alloc_data = None
    if ("diagnosis" in modules or "risk" in modules or "allocation" in modules
            or "rebalance" in modules):
        _alloc_data = generate_allocation(funds, industry_allocations, fund_holdings,
                                           fund_infos=fund_infos)

    _perf_data = None
    max_drawdown_detail = None
    if "performance" in modules:
        fund_weights = {f["code"]: f["weight"] for f in funds}
        _perf_data = generate_performance(funds, fund_navs, fund_weights, dates,
                                           fund_nav_dates=fund_dates,
                                           benchmark_data=benchmark_data)
        max_drawdown_detail = _perf_data.get("max_drawdown_detail")

    # --- 新增：计算相关性水平 ---
    _corr_data = None
    correlation_level = None
    if "correlation" in modules:
        _corr_data = generate_correlation(funds, fund_navs)
        avg_pw = _corr_data.get("average_pairwise_correlation", 0)
        if avg_pw > 0.6:
            correlation_level = "高"
        elif avg_pw > 0.3:
            correlation_level = "中"
        else:
            correlation_level = "低"

    # --- 按用户阅读习惯顺序插入report字典 ---
    # 顺序: diagnosis → overview → performance → risk → allocation → correlation → evaluation → rebalance

    # 1. 账户诊断总览（用户最想先看）
    if "diagnosis" in modules:
        asset_alloc = _alloc_data["asset_allocation"] if _alloc_data else None
        report["diagnosis"] = generate_diagnosis(
            funds, fund_scores, asset_alloc,
            fund_manager_ratings=fund_manager_ratings,
            fund_subscores_map=fund_subscores_map,
            stock_concentration=stock_concentration,
            correlation_level=correlation_level,
            industry_allocations=industry_allocations,
        )

    # 2. 持仓概览
    if "overview" in modules:
        report["overview"] = generate_overview(funds, fund_infos, current_prices, fund_scores, transaction_stats)

    # 3. 收益分析
    if _perf_data:
        report["performance"] = _perf_data

    # 4. 风险评估
    if "risk" in modules:
        current_weights = [f["weight"] for f in funds]
        asset_alloc = _alloc_data["asset_allocation"] if _alloc_data else None
        report["risk"] = generate_risk(funds, None, asset_alloc, current_weights,
                                        max_drawdown_detail=max_drawdown_detail)

    # 5. 配置分析
    if "allocation" in modules and _alloc_data:
        report["allocation"] = _alloc_data

    # 6. 相关性分析
    if "correlation" in modules:
        report["correlation"] = _corr_data if _corr_data else generate_correlation(funds, fund_navs)

    # 7. 单只基金评价
    if "evaluation" in modules:
        bm_nav = benchmark_data.get("nav_series") if benchmark_data else None
        bm_dates = benchmark_data.get("dates") if benchmark_data else None
        report["evaluation"] = generate_evaluation(
            funds, fund_evaluations,
            fund_infos=fund_infos,
            fund_navs=fund_navs,
            fund_nav_dates=fund_dates,
            fund_holdings=fund_holdings,
            fund_manager_ratings=fund_manager_ratings,
            fund_subscores_map=fund_subscores_map,
            fund_announcements=fund_announcements,
            benchmark_nav_series=bm_nav,
            benchmark_nav_dates=bm_dates,
        )

    # 8. 调仓建议（放在最后，基于前面所有分析）
    if "rebalance" in modules:
        current_alloc = _alloc_data["asset_allocation"] if _alloc_data else None
        if current_alloc:
            current_alloc = {item["type"]: item["weight"] for item in current_alloc}
        report["rebalance"] = generate_rebalance(
            funds, current_alloc,
            fund_evaluations=fund_evaluations,
            fund_scores=fund_scores,
            correlation_data=_corr_data,
        )

    # 9. 报告总结
    if "summary" in modules:
        report["summary"] = generate_summary(report)

    report["report_footer"] = {
        "disclaimer": "本报告仅供参考，不构成投资建议。基金有风险，投资需谨慎。",
        "modules": list(modules)
    }
    
    return report


# ============================================================
# 命令行入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="基金账户诊断报告生成器")
    parser.add_argument("--funds", type=str, help="基金代码列表，逗号分隔，如: 000001,000002")
    parser.add_argument("--transaction-file", type=str, help="交易记录Excel文件路径")
    parser.add_argument("--output", type=str, help="输出JSON文件路径")
    parser.add_argument("--modules", type=str, default="all",
                       help="分析模块，逗号分隔，可用值: diagnosis,overview,performance,risk,allocation,correlation,evaluation,rebalance")
    parser.add_argument("--show-stats", action="store_true", help="显示交易记录统计")
    parser.add_argument("--format", type=str, default="json", choices=["json", "html"],
                       help="输出格式: json 或 html")

    args = parser.parse_args()
    
    funds = []
    transaction_stats = None
    
    if args.funds:
        codes = args.funds.split(",")
        funds = [{"code": code.strip()} for code in codes if code.strip()]
    elif args.transaction_file:
        funds, transaction_stats = parse_transaction_excel(args.transaction_file)
        if not funds:
            print(json.dumps({"error": "未从交易记录中解析出有效持仓"}))
            sys.exit(1)
        if args.show_stats:
            print("=== 交易记录统计 ===")
            print(f"总记录数: {transaction_stats.get('total_records', 0)}")
            print(f"申购次数: {transaction_stats.get('subscribe_count', 0)}")
            print(f"赎回次数: {transaction_stats.get('redeem_count', 0)}")
            print(f"分红次数: {transaction_stats.get('dividend_count', 0)}")
            print(f"总申购金额: {transaction_stats.get('total_subscribe_amount', 0):.2f}")
            print(f"总赎回金额: {transaction_stats.get('total_redeem_amount', 0):.2f}")
            print(f"总分红金额: {transaction_stats.get('total_dividend_amount', 0):.2f}")
            print(f"解析到持仓基金数: {len(funds)}")
            print()
    else:
        print(json.dumps({"error": "请提供 --funds 或 --transaction-file 参数"}))
        sys.exit(1)
    
    if args.modules == "all":
        modules = ["diagnosis", "overview", "performance", "risk", "allocation",
                  "correlation", "evaluation", "rebalance", "summary"]
    else:
        modules = [m.strip() for m in args.modules.split(",")]
    
    try:
        report = generate_full_report(funds, {"modules": modules}, transaction_stats)
        
        if args.format == "html":
            from generate_html_report import generate_html_from_report
            output_path = args.output or "diagnostic_report.html"
            generate_html_from_report(report, output_path)
        elif args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"报告已保存至: {args.output}")
        else:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            
    except Exception as e:
        import traceback
        error_result = {"error": str(e), "traceback": traceback.format_exc()}
        print(json.dumps(error_result, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
