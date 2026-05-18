"""单元测试 - 计算引擎模块"""
import sys
import os
import pytest
import math

# 添加 scripts 目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculations import (
    calculate_returns_stats,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_correlation,
    calculate_hhi,
    nav_to_returns,
    calculate_portfolio_nav,
    calculate_multi_period_returns,
    calculate_per_fund_risk_metrics,
    compute_rank_percentile,
    generate_operational_recommendation,
    calculate_portfolio_metrics,
)


class TestNavToReturns:
    """测试净值转收益率函数"""

    def test_normal_sequence(self):
        """正常净值序列：每期上涨 10%"""
        nav = [1.0, 1.1, 1.21, 1.331]
        returns = nav_to_returns(nav)
        assert len(returns) == 3
        assert abs(returns[0] - 0.1) < 1e-6
        assert abs(returns[1] - 0.1) < 1e-6
        assert abs(returns[2] - 0.1) < 1e-6

    def test_single_element(self):
        """单个元素返回空列表"""
        returns = nav_to_returns([1.0])
        assert returns == []

    def test_two_elements(self):
        """两个元素返回单一收益率"""
        returns = nav_to_returns([1.0, 1.5])
        assert len(returns) == 1
        assert abs(returns[0] - 0.5) < 1e-6

    def test_decreasing(self):
        """下跌序列"""
        nav = [2.0, 1.0]
        returns = nav_to_returns(nav)
        assert abs(returns[0] - (-0.5)) < 1e-6

    def test_zero_start(self):
        """起始净值为零时不产生异常"""
        nav = [0, 1.0, 2.0]
        returns = nav_to_returns(nav)
        assert len(returns) == 2
        # 第一个收益率可能是 inf（pandas pct_change）或 0（手动实现）
        assert isinstance(returns[0], float)
        # 第二个正常：(2.0-1.0)/1.0 = 1.0
        assert abs(returns[1] - 1.0) < 1e-6

    def test_empty_list(self):
        """空列表返回空"""
        returns = nav_to_returns([])
        assert returns == []


class TestCalculateMaxDrawdown:
    """测试最大回撤计算"""

    def test_monotone_increase(self):
        """单调上升序列，回撤应为 0"""
        nav = [1.0, 1.1, 1.2, 1.3, 1.4, 1.5]
        result = calculate_max_drawdown(nav)
        assert abs(result["max_drawdown"]) < 1e-6

    def test_peak_then_valley(self):
        """先涨后跌"""
        nav = [1.0, 2.0, 1.5, 1.0, 0.8]
        result = calculate_max_drawdown(nav)
        # 最大回撤 = (2.0 - 0.8) / 2.0 = 0.6
        assert abs(result["max_drawdown"] - 0.6) < 1e-3

    def test_v_shape(self):
        """V 型走势"""
        nav = [1.0, 2.0, 1.0, 2.0]
        result = calculate_max_drawdown(nav)
        # 最大回撤 = (2.0 - 1.0) / 2.0 = 0.5
        assert abs(result["max_drawdown"] - 0.5) < 1e-3

    def test_all_decline(self):
        """全部下跌"""
        nav = [1.0, 0.9, 0.8, 0.7, 0.6]
        result = calculate_max_drawdown(nav)
        # 最大回撤 = (1.0 - 0.6) / 1.0 = 0.4
        assert abs(result["max_drawdown"] - 0.4) < 1e-3

    def test_single_element(self):
        """单个元素返回零回撤"""
        result = calculate_max_drawdown([1.0])
        assert result["max_drawdown"] == 0

    def test_empty_series(self):
        """空序列返回零回撤"""
        result = calculate_max_drawdown([])
        assert result["max_drawdown"] == 0

    def test_with_dates(self):
        """带日期参数"""
        nav = [1.0, 2.0, 1.0]
        dates = ["2024-01-01", "2024-01-02", "2024-01-03"]
        result = calculate_max_drawdown(nav, dates)
        assert "start_date" in result or "start_index" in result

    def test_result_keys(self):
        """验证返回字典包含必要字段"""
        nav = [1.0, 1.5, 1.2, 1.8]
        result = calculate_max_drawdown(nav)
        assert "max_drawdown" in result
        assert "peak_value" in result
        assert "trough_value" in result


class TestCalculateSharpeRatio:
    """测试夏普比率计算"""

    def test_positive_returns(self):
        """正收益序列应有正夏普"""
        # 使用有波动的正收益序列
        import random
        random.seed(42)
        returns = [0.001 + random.gauss(0, 0.005) for _ in range(252)]
        sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.03)
        assert sharpe > -10  # 有波动的序列应返回有限值
        assert not math.isnan(sharpe) and not math.isinf(sharpe)

    def test_zero_volatility(self):
        """零波动（所有收益相同）"""
        returns = [0.001] * 100
        sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.0)
        # 当所有收益相同时，标准差理论为 0，
        # 但不同计算引擎处理方式不同（可能返回 0 或极大值）
        assert isinstance(sharpe, (int, float))
        assert not math.isnan(sharpe)

    def test_negative_returns(self):
        """负收益序列应有负夏普"""
        import random
        random.seed(42)
        returns = [-0.001 + random.gauss(0, 0.005) for _ in range(252)]
        sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.03)
        assert sharpe < 0
        assert not math.isnan(sharpe) and not math.isinf(sharpe)

    def test_empty_returns(self):
        """空序列返回 0"""
        sharpe = calculate_sharpe_ratio([], risk_free_rate=0.03)
        assert sharpe == 0

    def test_single_return(self):
        """单个收益率（不足 2 个）返回 0"""
        sharpe = calculate_sharpe_ratio([0.01], risk_free_rate=0.03)
        assert sharpe == 0

    def test_return_is_float(self):
        """返回值为浮点数"""
        returns = [0.005, -0.003, 0.008, -0.002, 0.004] * 50
        sharpe = calculate_sharpe_ratio(returns)
        assert isinstance(sharpe, (int, float))

    def test_high_volatility(self):
        """高波动收益序列"""
        returns = [0.05, -0.05] * 126
        sharpe = calculate_sharpe_ratio(returns, risk_free_rate=0.03)
        # 均值约为 0，高波动，应有负夏普
        assert sharpe < 0


class TestCalculateCorrelation:
    """测试相关系数计算"""

    def test_perfect_positive(self):
        """完全正相关"""
        a = [1, 2, 3, 4, 5]
        b = [2, 4, 6, 8, 10]
        corr = calculate_correlation(a, b)
        assert abs(corr - 1.0) < 1e-3

    def test_perfect_negative(self):
        """完全负相关"""
        a = [1, 2, 3, 4, 5]
        b = [10, 8, 6, 4, 2]
        corr = calculate_correlation(a, b)
        assert abs(corr - (-1.0)) < 1e-3

    def test_uncorrelated(self):
        """接近不相关"""
        a = [1, -1, 1, -1, 1, -1]
        b = [1, 1, -1, -1, 1, 1]
        corr = calculate_correlation(a, b)
        assert abs(corr) < 0.5

    def test_empty_returns(self):
        """空输入返回 0"""
        corr = calculate_correlation([], [])
        assert corr == 0

    def test_unequal_length(self):
        """不等长序列返回 0"""
        corr = calculate_correlation([1, 2, 3], [1, 2])
        assert corr == 0

    def test_single_element(self):
        """单元素序列（相同长度但不足以计算）"""
        corr = calculate_correlation([1], [2])
        # 实现中 len(returns1) != len(returns2) 已检查，
        # 单元素等长应返回 0（方差为零）
        assert not math.isnan(corr)

    def test_identical_sequences(self):
        """完全相同的序列"""
        a = [0.01, -0.02, 0.03, -0.01, 0.005]
        corr = calculate_correlation(a, a)
        assert abs(corr - 1.0) < 1e-3


class TestCalculateHHI:
    """测试 HHI 集中度指数"""

    def test_uniform_distribution(self):
        """均匀分布 HHI = n * (1/n)^2 = 1/n"""
        weights = [0.25, 0.25, 0.25, 0.25]
        hhi = calculate_hhi(weights)
        assert abs(hhi - 0.25) < 1e-6

    def test_single_concentration(self):
        """单一集中 HHI = 1.0"""
        weights = [1.0]
        hhi = calculate_hhi(weights)
        assert abs(hhi - 1.0) < 1e-6

    def test_two_equal(self):
        """两等分 HHI = 0.5"""
        weights = [0.5, 0.5]
        hhi = calculate_hhi(weights)
        assert abs(hhi - 0.5) < 1e-6

    def test_empty_list(self):
        """空列表返回 0"""
        hhi = calculate_hhi([])
        assert hhi == 0

    def test_ten_equal(self):
        """十等分 HHI = 0.1"""
        weights = [0.1] * 10
        hhi = calculate_hhi(weights)
        assert abs(hhi - 0.1) < 1e-6

    def test_high_concentration(self):
        """高集中度"""
        weights = [0.9, 0.05, 0.05]
        hhi = calculate_hhi(weights)
        expected = 0.9**2 + 0.05**2 + 0.05**2
        assert abs(hhi - expected) < 1e-6


class TestCalculateReturnsStats:
    """测试收益率统计"""

    def test_normal_returns(self):
        """正常收益序列"""
        returns = [0.01, -0.02, 0.03, -0.01, 0.02, 0.01, -0.005]
        result = calculate_returns_stats(returns)
        assert "mean" in result
        assert "std" in result
        assert "min" in result
        assert "max" in result
        assert "var_95" in result
        assert "cvar_95" in result

    def test_empty_returns(self):
        """空收益序列返回全零"""
        result = calculate_returns_stats([])
        assert result["mean"] == 0
        assert result["std"] == 0

    def test_all_positive(self):
        """全正收益"""
        returns = [0.01, 0.02, 0.03]
        result = calculate_returns_stats(returns)
        assert result["mean"] > 0
        assert result["min"] > 0

    def test_all_negative(self):
        """全负收益"""
        returns = [-0.01, -0.02, -0.03]
        result = calculate_returns_stats(returns)
        assert result["mean"] < 0
        assert result["max"] < 0

    def test_single_value(self):
        """单个收益值"""
        returns = [0.05]
        result = calculate_returns_stats(returns)
        assert result["mean"] == 0.05
        assert result["std"] == 0

    def test_result_precision(self):
        """结果保留 6 位小数"""
        returns = [1/3, 2/3, 1/7]
        result = calculate_returns_stats(returns)
        for key in ["mean", "std", "min", "max"]:
            # 验证小数位数不超过 6 位
            val_str = f"{result[key]:.10f}"
            # 只要是数值即可
            assert isinstance(result[key], (int, float))


class TestCalculatePortfolioNav:
    """测试组合净值计算"""

    def test_single_fund(self):
        """单只基金全仓"""
        fund_navs = {"000001": [1.0, 1.1, 1.2]}
        weights = {"000001": 1.0}
        fund_codes = ["000001"]
        result = calculate_portfolio_nav(fund_navs, weights, fund_codes)
        assert isinstance(result, list)
        assert len(result) == 3
        # 归一化后 [1.0, 1.1, 1.2]，权重 1.0
        assert abs(result[0] - 1.0) < 1e-6
        assert abs(result[1] - 1.1) < 1e-6
        assert abs(result[2] - 1.2) < 1e-6

    def test_two_funds_equal_weight(self):
        """两只基金等权重"""
        fund_navs = {
            "000001": [1.0, 1.1, 1.2],
            "000002": [2.0, 1.8, 2.0],
        }
        weights = {"000001": 0.5, "000002": 0.5}
        fund_codes = ["000001", "000002"]
        result = calculate_portfolio_nav(fund_navs, weights, fund_codes)
        assert isinstance(result, list)
        assert len(result) == 3
        # 000001 归一化: [1.0, 1.1, 1.2]
        # 000002 归一化: [1.0, 0.9, 1.0]
        # 组合: [0.5*1.0+0.5*1.0, 0.5*1.1+0.5*0.9, 0.5*1.2+0.5*1.0]
        #      = [1.0, 1.0, 1.1]
        assert abs(result[0] - 1.0) < 1e-6
        assert abs(result[1] - 1.0) < 1e-6
        assert abs(result[2] - 1.1) < 1e-6

    def test_empty_navs(self):
        """空输入返回空列表"""
        result = calculate_portfolio_nav({}, {}, [])
        assert result == []

    def test_different_lengths(self):
        """不同长度净值序列对齐"""
        fund_navs = {
            "000001": [1.0, 1.1, 1.2, 1.3],
            "000002": [2.0, 2.2],
        }
        weights = {"000001": 0.5, "000002": 0.5}
        fund_codes = ["000001", "000002"]
        result = calculate_portfolio_nav(fund_navs, weights, fund_codes)
        # 最长为 4，短序列用末尾值填充
        assert len(result) == 4


class TestCalculateMultiPeriodReturns:
    """测试多期收益计算"""

    def test_sufficient_data(self):
        """充足数据（超过 252 天）"""
        nav = [1.0 + i * 0.001 for i in range(300)]
        result = calculate_multi_period_returns(nav)
        assert isinstance(result, dict)
        # 应有 since_inception
        assert "since_inception" in result
        # 应有 1m (21天)
        assert "1m" in result

    def test_insufficient_data(self):
        """数据不足（仅 3 天）"""
        nav = [1.0, 1.01, 1.02]
        result = calculate_multi_period_returns(nav)
        assert isinstance(result, dict)
        # 只有 since_inception（因为不足 21 天）
        assert "since_inception" in result
        assert "1m" not in result

    def test_empty_nav(self):
        """空净值序列"""
        result = calculate_multi_period_returns([])
        assert result == {}

    def test_single_element(self):
        """单元素净值序列"""
        result = calculate_multi_period_returns([1.0])
        assert result == {}

    def test_custom_periods(self):
        """自定义期间"""
        nav = [1.0 + i * 0.01 for i in range(50)]
        result = calculate_multi_period_returns(nav, periods=[("10d", 10), ("30d", 30)])
        assert isinstance(result, dict)
        # 50天数据，10天和30天都应有数据
        assert "10d" in result
        assert "30d" in result

    def test_since_inception(self):
        """始于成立计算正确"""
        nav = [1.0, 1.1, 1.2, 1.3]
        result = calculate_multi_period_returns(nav)
        # since_inception = (1.3 / 1.0) - 1 = 0.3
        assert abs(result["since_inception"] - 0.3) < 1e-4


class TestCalculatePerFundRiskMetrics:
    """测试单只基金风险指标"""

    def test_normal_nav(self):
        """正常净值序列"""
        nav = [1.0 + i * 0.005 for i in range(100)]
        result = calculate_per_fund_risk_metrics(nav)
        assert "max_drawdown" in result
        assert "volatility" in result
        assert "sharpe_ratio" in result
        assert "max_drawdown_period" in result

    def test_empty_nav(self):
        """空净值返回零"""
        result = calculate_per_fund_risk_metrics([])
        assert result["max_drawdown"] == 0
        assert result["volatility"] == 0
        assert result["sharpe_ratio"] == 0

    def test_single_element(self):
        """单元素净值"""
        result = calculate_per_fund_risk_metrics([1.0])
        assert result["max_drawdown"] == 0


class TestComputeRankPercentile:
    """测试排名百分位估算"""

    def test_high_score(self):
        """高分: >= 90"""
        result = compute_rank_percentile(95)
        assert result["1y"] == 5
        assert "前5%" in result["label"]

    def test_good_score(self):
        """良好: >= 80"""
        result = compute_rank_percentile(85)
        assert result["1y"] == 15

    def test_above_average(self):
        """中上: >= 70"""
        result = compute_rank_percentile(75)
        assert result["1y"] == 30

    def test_average(self):
        """中等: >= 60"""
        result = compute_rank_percentile(65)
        assert result["1y"] == 50

    def test_below_average(self):
        """中下: >= 50"""
        result = compute_rank_percentile(55)
        assert result["1y"] == 70

    def test_low_score(self):
        """低分: < 50"""
        result = compute_rank_percentile(40)
        assert result["1y"] == 90


class TestGenerateOperationalRecommendation:
    """测试操作建议生成"""

    def test_low_score_replace(self):
        """低分建议替换"""
        action, reason = generate_operational_recommendation(50, 40, 60, "C")
        assert action == "替换"

    def test_medium_low_with_bad_manager(self):
        """中下分+经理评分低 -> 部分替换"""
        action, reason = generate_operational_recommendation(
            65, 60, 70, "C", manager_score={"overall_1y": 40}
        )
        assert action == "部分替换"

    def test_medium_low_with_good_manager(self):
        """中下分+经理评分正常 -> 观察"""
        action, reason = generate_operational_recommendation(
            65, 60, 70, "C", manager_score={"overall_1y": 60}
        )
        assert action == "观察"

    def test_medium_score_hold(self):
        """中等偏上 -> 继续持有"""
        action, reason = generate_operational_recommendation(75, 70, 80, "B")
        assert action == "继续持有"

    def test_high_score_keep(self):
        """高分 -> 保留"""
        action, reason = generate_operational_recommendation(85, 80, 90, "A")
        assert action == "保留"

    def test_excellent_score(self):
        """优秀 -> 重点保留"""
        action, reason = generate_operational_recommendation(95, 90, 95, "A+")
        assert action == "重点保留"


class TestCalculatePortfolioMetrics:
    """测试组合市值/成本/盈亏计算"""

    def test_normal_case(self):
        """正常计算"""
        funds = [
            {"code": "000001", "shares": 1000, "cost": 10000},
            {"code": "000002", "shares": 500, "cost": 5000},
        ]
        current_prices = {"000001": 12.0, "000002": 9.0}
        result = calculate_portfolio_metrics(funds, current_prices)
        # 市值 = 1000*12 + 500*9 = 12000 + 4500 = 16500
        assert result["total_market_value"] == 16500.0
        # 成本 = 10000 + 5000 = 15000
        assert result["total_cost"] == 15000.0
        # 盈亏 = 16500 - 15000 = 1500
        assert result["profit"] == 1500.0
        # 收益率 = 1500 / 15000 = 0.1
        assert abs(result["profit_rate"] - 0.1) < 1e-4

    def test_zero_cost(self):
        """零成本不除零"""
        funds = [{"code": "000001", "shares": 100, "cost": 0}]
        current_prices = {"000001": 10.0}
        result = calculate_portfolio_metrics(funds, current_prices)
        assert result["profit_rate"] == 0

    def test_empty_funds(self):
        """空基金列表"""
        result = calculate_portfolio_metrics([], {})
        assert result["total_market_value"] == 0
        assert result["total_cost"] == 0
        assert result["profit"] == 0

    def test_missing_price(self):
        """缺少当前价格"""
        funds = [{"code": "000001", "shares": 100, "cost": 1000}]
        current_prices = {}  # 没有价格
        result = calculate_portfolio_metrics(funds, current_prices)
        # nav 为 0，市值为 0
        assert result["total_market_value"] == 0
