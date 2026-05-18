"""单元测试 - 工具函数模块"""
import sys
import os
import pytest
import math

# 添加 scripts 目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import parse_amount, normalize_operation, find_column


class TestParseAmount:
    """测试 parse_amount 函数"""

    def test_normal_float(self):
        """正常浮点数"""
        assert parse_amount(1234.56) == 1234.56

    def test_normal_int(self):
        """正常整数"""
        assert parse_amount(1000) == 1000.0

    def test_string_with_commas(self):
        """带逗号的字符串"""
        assert parse_amount("1,234.56") == 1234.56

    def test_string_without_commas(self):
        """无逗号的字符串"""
        assert parse_amount("1234.56") == 1234.56

    def test_none_returns_zero(self):
        """None 返回 0.0"""
        assert parse_amount(None) == 0.0

    def test_nan_returns_zero(self):
        """NaN 返回 0.0"""
        assert parse_amount(float('nan')) == 0.0

    def test_empty_string(self):
        """空字符串返回 0.0"""
        assert parse_amount("") == 0.0

    def test_zero(self):
        """零值"""
        assert parse_amount(0) == 0.0

    def test_negative(self):
        """负数"""
        assert parse_amount(-500.0) == -500.0

    def test_string_negative(self):
        """负数字符串（含逗号）"""
        assert parse_amount("-1,000.50") == -1000.50

    def test_string_with_spaces(self):
        """带空格的字符串"""
        assert parse_amount(" 1,234.56 ") == 1234.56

    def test_invalid_string(self):
        """无法解析的字符串返回 0.0"""
        assert parse_amount("abc") == 0.0

    def test_large_number(self):
        """大数字"""
        assert parse_amount("1,000,000.00") == 1000000.0


class TestNormalizeOperation:
    """测试 normalize_operation 函数"""

    def test_subscribe(self):
        """申购 -> subscribe"""
        assert normalize_operation("申购") == "subscribe"

    def test_subscribe_regular(self):
        """定投 -> subscribe"""
        assert normalize_operation("定投") == "subscribe"

    def test_subscribe_recognize(self):
        """认购 -> subscribe"""
        assert normalize_operation("认购") == "subscribe"

    def test_subscribe_auto(self):
        """定期定额申购 -> subscribe"""
        assert normalize_operation("定期定额申购") == "subscribe"

    def test_redeem(self):
        """赎回 -> redeem"""
        assert normalize_operation("赎回") == "redeem"

    def test_redeem_convert(self):
        """基金转换 -> convert"""
        assert normalize_operation("基金转换") == "convert"

    def test_dividend(self):
        """分红 -> dividend"""
        assert normalize_operation("分红") == "dividend"

    def test_convert_in(self):
        """转入 -> convert_in"""
        assert normalize_operation("转入") == "convert_in"

    def test_convert_out(self):
        """转出 -> convert_out"""
        assert normalize_operation("转出") == "convert_out"

    def test_ignore_set_dividend_mode(self):
        """设置分红方式 -> ignore（精确匹配）"""
        assert normalize_operation("设置分红方式") == "ignore"

    def test_ignore_auto_invest_agreement(self):
        """定投协议开通 -> ignore（精确匹配）"""
        assert normalize_operation("定投协议开通") == "ignore"

    def test_unknown_operation(self):
        """未知操作返回 unknown"""
        assert normalize_operation("未知操作类型xyz") == "unknown"

    def test_partial_match_subscribe(self):
        """包含申购关键字的操作"""
        assert normalize_operation("基金申购确认") == "subscribe"

    def test_empty_string(self):
        """空字符串返回 unknown"""
        assert normalize_operation("") == "unknown"

    def test_none_input(self):
        """None 输入返回 unknown"""
        assert normalize_operation(None) == "unknown"

    def test_nan_input(self):
        """NaN 输入返回 unknown"""
        assert normalize_operation(float('nan')) == "unknown"

    def test_force_increase(self):
        """强行调增 -> subscribe"""
        assert normalize_operation("强行调增") == "subscribe"

    def test_force_redeem(self):
        """强行赎回 -> redeem"""
        assert normalize_operation("强行赎回") == "redeem"


class TestFindColumn:
    """测试 find_column 函数"""

    def test_exact_match_fund_code(self):
        """精确匹配基金代码"""
        columns = ["基金代码", "基金名称", "申请金额"]
        result = find_column(columns, "fund_code")
        assert result == "基金代码"

    def test_alternative_name_fund_code(self):
        """备选名称匹配代码"""
        columns = ["代码", "基金名称", "申请金额"]
        result = find_column(columns, "fund_code")
        assert result == "代码"

    def test_exact_match_fund_name(self):
        """精确匹配基金名称"""
        columns = ["基金代码", "基金名称", "申请金额"]
        result = find_column(columns, "fund_name")
        assert result == "基金名称"

    def test_match_operation(self):
        """匹配业务名称"""
        columns = ["基金代码", "业务名称", "申请金额"]
        result = find_column(columns, "operation")
        assert result == "业务名称"

    def test_match_nav(self):
        """匹配净值列"""
        columns = ["基金代码", "产品单位净值", "确认金额"]
        result = find_column(columns, "nav")
        assert result == "产品单位净值"

    def test_not_found(self):
        """找不到匹配列返回 None"""
        columns = ["无关列1", "无关列2"]
        result = find_column(columns, "fund_code")
        assert result is None

    def test_empty_columns(self):
        """空列列表返回 None"""
        result = find_column([], "fund_code")
        assert result is None

    def test_fuzzy_match_prefix(self):
        """模糊匹配前缀"""
        columns = ["基金代码(6位)", "基金名称"]
        result = find_column(columns, "fund_code")
        assert result == "基金代码(6位)"

    def test_confirm_date(self):
        """匹配确认日期"""
        columns = ["确认日期", "确认金额"]
        result = find_column(columns, "confirm_date")
        assert result == "确认日期"

    def test_confirm_amount(self):
        """匹配确认金额"""
        columns = ["确认日期", "确认金额"]
        result = find_column(columns, "confirm_amount")
        assert result == "确认金额"
        assert result == "确认金额"
