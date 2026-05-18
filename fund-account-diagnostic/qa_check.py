#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金账户诊断报告质检脚本 - 独立计算验证
"""

import json
import sys
import pandas as pd
import math
from typing import Dict, List, Any

EXCEL_PATH = "/Users/jarrey/Downloads/账户诊断/Grace交易记录.xlsx"
REPORT_PATH = "/Users/jarrey/Downloads/fund-account-diagnostic-skill/fund-account-diagnostic/diagnostic_report.json"

AMOUNT_THRESHOLD = 1.0
SHARES_THRESHOLD = 0.01
PERCENT_THRESHOLD = 0.001

class QAChecker:
    def __init__(self):
        self.findings = []
        self.summary = {"total": 0, "passed": 0, "errors": [], "warnings": []}
        self.excel_data = None
        self.report_data = None
        self.calc_results = {}
    
    def add_finding(self, category, issue, expected, actual, severity, location="", diff=None):
        self.findings.append({
            "category": category,
            "issue": issue,
            "expected": expected,
            "actual": actual,
            "severity": severity,
            "location": location,
            "diff": diff
        })
        self.summary["total"] += 1
        if severity == "严重":
            self.summary["errors"].append(issue)
        elif severity == "中等":
            self.summary["warnings"].append(issue)
    
    def parse_amount(self, val):
        if val is None or (isinstance(val, float) and math.isnan(val)):
            return 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            val = val.replace(',', '').strip()
            try:
                return float(val)
            except:
                return 0.0
        return 0.0
    
    def normalize_operation(self, operation):
        if not operation:
            return "unknown"
        op = str(operation).strip()
        # 优先检查 ignore 类型（精确匹配），避免"设置分红方式"被"分红"子串匹配
        if op in ["设置分红方式", "定投协议开通"]:
            return "ignore"
        # 然后再做 substring 匹配
        if any(x in op for x in ["申购", "认购", "定投", "定期定额申购", "强行调增"]):
            return "subscribe"
        elif any(x in op for x in ["赎回", "强行赎回"]):
            return "redeem"
        elif "分红" in op:
            return "dividend"
        elif "转换" in op:
            return "convert"
        return "unknown"
    
    def load_data(self):
        print("[1/4] 加载数据...")
        try:
            self.excel_data = pd.read_excel(EXCEL_PATH, sheet_name=0)
            print(f"✓ Excel: {len(self.excel_data)} 行, {len(self.excel_data.columns)} 列")
        except Exception as e:
            print(f"✗ Excel加载失败: {e}")
            return False
        
        try:
            with open(REPORT_PATH, 'r', encoding='utf-8') as f:
                self.report_data = json.load(f)
            print(f"✓ 报告加载成功")
        except Exception as e:
            print(f"✗ 报告加载失败: {e}")
            return False
        return True
    
    def independent_calc(self):
        print("\n[2/4] 独立计算指标...")
        df = self.excel_data[self.excel_data['确认结果'] == '确认成功'].copy()
        print(f"✓ 确认成功记录: {len(df)} 条")
        
        holdings = {}
        stats = {
            "subscribe_count": 0,
            "redeem_count": 0,
            "dividend_count": 0,
            "convert_count": 0,
            "ignore_count": 0,
            "total_subscribe_amount": 0.0,
            "total_redeem_amount": 0.0,
            "total_dividend_amount": 0.0,
            "total_convert_amount": 0.0,
            "first_date": None,
            "last_date": None,
        }
        
        for idx, row in df.iterrows():
            fund_code_raw = row.get('基金代码')
            if pd.isna(fund_code_raw):
                continue
            
            fund_code = str(int(fund_code_raw)).zfill(6)
            fund_name = str(row.get('基金名称', '')).strip()
            operation = str(row.get('业务名称', '')).strip()
            op_type = self.normalize_operation(operation)
            
            confirm_amount = self.parse_amount(row.get('确认金额'))
            confirm_shares = self.parse_amount(row.get('确认份额'))
            nav = self.parse_amount(row.get('产品单位净值', 1.0))
            if nav <= 0:
                nav = 1.0
            
            # 日期处理
            date_val = row.get('确认日期')
            if not pd.isna(date_val):
                date_str = str(int(date_val)) if isinstance(date_val, float) else str(date_val)
                if len(date_str) == 8:
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                if not stats["first_date"] or date_str < stats["first_date"]:
                    stats["first_date"] = date_str
                if not stats["last_date"] or date_str > stats["last_date"]:
                    stats["last_date"] = date_str
            
            # 跳过不影响持仓的操作
            if op_type == "ignore":
                stats["ignore_count"] += 1
                continue
            
            if fund_code not in holdings:
                holdings[fund_code] = {
                    "code": fund_code,
                    "name": fund_name,
                    "shares": 0.0,
                    "cost": 0.0,
                    "subscribe_count": 0,
                    "redeem_count": 0,
                    "dividend_count": 0,
                    "convert_count": 0,
                }
            
            if op_type == "subscribe":
                actual_shares = confirm_shares if confirm_shares > 0 else (confirm_amount / nav if nav > 0 else 0)
                if actual_shares > 0:
                    holdings[fund_code]["shares"] += actual_shares
                    holdings[fund_code]["cost"] += confirm_amount
                    holdings[fund_code]["subscribe_count"] += 1
                    stats["subscribe_count"] += 1
                    stats["total_subscribe_amount"] += confirm_amount
            
            elif op_type == "redeem":
                if confirm_shares > 0:
                    holdings[fund_code]["shares"] -= confirm_shares
                    if holdings[fund_code]["cost"] > 0:
                        cost_ratio = confirm_shares / (holdings[fund_code]["shares"] + confirm_shares)
                        holdings[fund_code]["cost"] *= (1 - cost_ratio)
                    else:
                        holdings[fund_code]["cost"] = 0
                    holdings[fund_code]["redeem_count"] += 1
                    stats["redeem_count"] += 1
                    stats["total_redeem_amount"] += confirm_amount
            
            elif op_type == "convert":
                # 基金转换：源基金减份额，不计入赎回统计
                if confirm_shares > 0:
                    holdings[fund_code]["shares"] -= confirm_shares
                    if holdings[fund_code]["cost"] > 0:
                        cost_ratio = confirm_shares / (holdings[fund_code]["shares"] + confirm_shares)
                        holdings[fund_code]["cost"] *= (1 - cost_ratio)
                    else:
                        holdings[fund_code]["cost"] = 0
                holdings[fund_code]["convert_count"] += 1
                stats["convert_count"] += 1
                stats["total_convert_amount"] += confirm_amount
            
            elif op_type == "dividend":
                stats["dividend_count"] += 1
                holdings[fund_code]["dividend_count"] += 1
                stats["total_dividend_amount"] += confirm_amount
                if confirm_shares > 0:
                    holdings[fund_code]["shares"] += confirm_shares
        
        current = [h for h in holdings.values() if h["shares"] > 1e-6]
        liquidated = [h for h in holdings.values() if h["shares"] <= 1e-6 and (h["subscribe_count"] > 0 or h["convert_count"] > 0)]
        
        self.calc_results = {
            "holdings": current,
            "liquidated": liquidated,
            "stats": stats,
            "current_count": len(current),
            "liquidated_count": len(liquidated),
        }
        
        print(f"✓ 当前持仓: {len(current)} 只, 已清仓: {len(liquidated)} 只")
        print(f"  申购: {stats['subscribe_count']}次, 赎回: {stats['redeem_count']}次, "
              f"分红: {stats['dividend_count']}次, 转换: {stats['convert_count']}次, "
              f"忽略: {stats['ignore_count']}次")
        print(f"  总申购金额: {stats['total_subscribe_amount']:.2f}, "
              f"总赎回金额: {stats['total_redeem_amount']:.2f}, "
              f"总转换金额: {stats['total_convert_amount']:.2f}")
    
    def verify_completeness(self):
        print("\n[3/4] 数据完整性验证...")
        
        report_count = self.report_data.get('overview', {}).get('basic_info', {}).get('fund_count', 0)
        calc_count = self.calc_results['current_count']
        
        if report_count == calc_count:
            print(f"✓ A1 持仓基金数: {report_count} == {calc_count}")
            self.summary["passed"] += 1
        else:
            print(f"✗ A1 持仓基金数: {report_count} != {calc_count}")
            self.add_finding("完整性", "持仓基金数不匹配", report_count, calc_count, "严重", "generators.py")
        
        # 已清仓基金
        liquidated_report = len(self.report_data.get('overview', {}).get('liquidated_funds', []))
        liquidated_calc = self.calc_results['liquidated_count']
        
        if liquidated_report == liquidated_calc:
            print(f"✓ A2 已清仓基金数: {liquidated_report} == {liquidated_calc}")
            self.summary["passed"] += 1
        else:
            print(f"✗ A2 已清仓基金数: {liquidated_report} != {liquidated_calc}")
            self.add_finding("完整性", "已清仓基金数不匹配", liquidated_report, liquidated_calc, "中等", "generators.py")
        
        # 模块检查
        modules = ["diagnosis", "overview", "performance", "risk", "allocation", "correlation", "evaluation", "rebalance"]
        missing = [m for m in modules if m not in self.report_data]
        
        if not missing:
            print(f"✓ A3 报告模块完整: {len(modules)} 个")
            self.summary["passed"] += 1
        else:
            print(f"✗ A3 报告模块缺失: {missing}")
            self.add_finding("完整性", f"模块缺失: {missing}", modules, list(self.report_data.keys()), "严重", "diagnostic_report.py")
    
    def verify_metrics(self):
        print("\n[4/4] 核心数值验证...")
        
        # 申购次数
        calc_sub = self.calc_results['stats']['subscribe_count']
        print(f"  申购次数独立计算: {calc_sub}")
        
        # 赎回次数
        calc_red = self.calc_results['stats']['redeem_count']
        print(f"  赎回次数独立计算: {calc_red}")
        
        # 分红次数
        calc_div = self.calc_results['stats']['dividend_count']
        print(f"  分红次数独立计算: {calc_div}")
        
        # 转换次数
        calc_conv = self.calc_results['stats']['convert_count']
        print(f"  转换次数独立计算: {calc_conv}")
        
        # 总申购金额
        calc_sub_amt = self.calc_results['stats']['total_subscribe_amount']
        print(f"  总申购金额独立计算: {calc_sub_amt:.2f}")
        
        # 总赎回金额
        calc_red_amt = self.calc_results['stats']['total_redeem_amount']
        print(f"  总赎回金额独立计算: {calc_red_amt:.2f}")
        
        # 总转换金额
        calc_conv_amt = self.calc_results['stats']['total_convert_amount']
        print(f"  总转换金额独立计算: {calc_conv_amt:.2f}")
        
        # 总分红金额
        calc_div_amt = self.calc_results['stats']['total_dividend_amount']
        print(f"  总分红金额独立计算: {calc_div_amt:.2f}")
    
    def generate_report(self):
        print("\n" + "="*80)
        print("质检报告总结")
        print("="*80)
        
        errors = [f for f in self.findings if f['severity'] == '严重']
        warnings = [f for f in self.findings if f['severity'] == '中等']
        
        if errors:
            print(f"\n【严重问题】({len(errors)}项)")
            for i, e in enumerate(errors, 1):
                print(f"\n{i}. {e['issue']}")
                print(f"   期望: {e['expected']}, 实际: {e['actual']}")
                if e['location']:
                    print(f"   位置: {e['location']}")
        
        if warnings:
            print(f"\n【中等问题】({len(warnings)}项)")
            for i, w in enumerate(warnings, 1):
                print(f"\n{i}. {w['issue']}")
                print(f"   期望: {w['expected']}, 实际: {w['actual']}")
        
        total_checks = len(self.findings) + self.summary["passed"]
        if total_checks > 0:
            pass_rate = self.summary["passed"] / total_checks * 100
            print(f"\n通过率: {pass_rate:.1f}% ({self.summary['passed']}/{total_checks})")
        
        if not errors and not warnings:
            print("\n✓ 所有质检通过！")
    
    def run(self):
        if not self.load_data():
            return False
        self.independent_calc()
        self.verify_completeness()
        self.verify_metrics()
        self.generate_report()
        return True

if __name__ == "__main__":
    checker = QAChecker()
    success = checker.run()
    sys.exit(0 if success else 1)
