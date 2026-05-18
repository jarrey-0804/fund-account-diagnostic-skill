# 基金账户诊断报告输出格式

## 概览

报告输出为标准化 JSON 格式，包含报告头部、各分析模块和报告尾部三部分。

---

## 报告结构

```json
{
  "report_header": { ... },
  "diagnosis": { ... },
  "overview": { ... },
  "performance": { ... },
  "risk": { ... },
  "allocation": { ... },
  "correlation": { ... },
  "evaluation": { ... },
  "rebalance": { ... },
  "summary": { ... },
  "report_footer": { ... }
}
```

---

## report_header

报告通用头部信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| generate_time | string | 报告生成时间，格式: YYYY-MM-DD HH:MM:SS |
| data_source | string | 数据来源说明（固定为 "qieman MCP API"） |
| api_available | boolean | MCP API是否可用 |
| mcp_url | string | MCP服务器地址 |
| tool_version | string | 工具版本号 |
| analysis_period | string | 分析基准期 |

**示例**:
```json
{
  "generate_time": "2024-01-15 14:30:00",
  "data_source": "qieman MCP API",
  "api_available": true,
  "mcp_url": "https://stargate.yingmi.com/mcp/v2",
  "tool_version": "1.0.0",
  "analysis_period": "近252个交易日"
}
```

---

## overview (持仓概览)

### basic_info

组合基本信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| fund_count | integer | 基金数量 |
| total_market_value | float | 总市值（元） |
| total_cost | float | 总成本（元） |
| profit | float | 盈亏金额（元） |
| profit_rate | float | 盈亏比例 |

### holdings_detail

持仓明细列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| index | integer | 序号 |
| code | string | 基金代码 |
| name | string | 基金名称 |
| fund_type | string | 基金类型（如：混合型、债券型） |
| manager | string | 基金经理 |
| weight | float | 权重（占比） |
| market_value | float | 市值（元） |
| cost | float | 成本（元） |
| profit | float | 盈亏（元） |
| profit_rate | float | 盈亏比例 |
| comprehensive_score | mixed | 综合得分（数字或"N/A"） |
| suggestion | string | 建议 |

### concentration_alerts *(新增)*

集中度预警列表，当任意基金权重超过20%时生成，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| weight | float | 权重 |
| message | string | 预警信息 |

### liquidated_funds *(新增)*

已清仓基金列表（仅从交易记录解析时可用），每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| last_transaction_date | string | 最后交易日期 |
| reason | string | 清仓原因（赎回清仓/转出清仓） |

**示例**:
```json
{
  "basic_info": {
    "fund_count": 6,
    "total_market_value": 500000.00,
    "total_cost": 450000.00,
    "profit": 50000.00,
    "profit_rate": 0.1111
  },
  "holdings_detail": [
    {
      "index": 1,
      "code": "000001",
      "name": "华夏成长混合",
      "weight": 0.25,
      "market_value": 125000.00,
      "cost": 100000.00,
      "profit": 25000.00,
      "profit_rate": 0.25,
      "comprehensive_score": 82,
      "suggestion": "持有"
    }
  ],
  "concentration_alerts": [
    {"code": "000001", "name": "华夏成长混合", "weight": 0.25, "message": "权重25.0%超过20%阈值，集中度偏高"}
  ]
}
```

---

## performance (组合收益风险表现)

### 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| data_source_note | string | 数据来源说明（基于基金净值加权计算 / 模拟数据） |

`data_source_note` 字段取值范围：
- `"全部数据来源于实时API"` — 所有基金数据均通过 API 获取成功
- `"部分基金数据使用模拟数据"` — 部分基金 API 调用失败，使用模拟数据替代
- `"全部数据为模拟数据"` — API 完全不可用，所有数据使用模拟生成
- `"数据来源于Excel导入"` — 用户通过 Excel 文件提供持仓数据

### comparison_table

组合与基准对比。

| 字段 | 类型 | 说明 |
|------|------|------|
| portfolio | object | 组合收益指标 |
| portfolio.total_return | float | 累计收益率 |
| portfolio.cagr | float | 年化收益率 |
| benchmark | object | 基准收益指标 |
| benchmark.total_return | float | 基准累计收益率 |
| excess_return | float | 超额收益 |

### performance_metrics

绩效指标汇总。

| 字段 | 类型 | 说明 |
|------|------|------|
| cumulative_return | float | 累计收益率 |
| cagr | float | 年化收益率(CAGR) |
| volatility | float | 年化波动率 |
| max_drawdown | float | 最大回撤 |
| var_95 | float | 95% VaR（年化） |
| cvar_95 | float | 95% CVaR（年化） |
| sharpe_ratio | float | 夏普比率 |
| sortino_ratio | float | 索提诺比率（下行风险调整后收益），需empyrical，默认0.0 |
| calmar_ratio | float | 卡玛比率（收益与最大回撤比），需empyrical，默认0.0 |
| downside_risk | float | 年化下行偏差，需empyrical，默认0.0 |
| tail_ratio | float | 尾部比率（95%分位/5%分位），需empyrical，默认0.0 |
| alpha | float | 相对基准的Alpha，需empyrical及基准数据，默认0.0 |
| beta | float | 相对基准的Beta，需empyrical及基准数据，默认0.0 |

> 新增字段（sortino_ratio, calmar_ratio, downside_risk, tail_ratio, alpha, beta）在未安装empyrical库或无基准数据时默认为0.0，不影响已有字段。

### max_drawdown_detail

最大回撤详情。

| 字段 | 类型 | 说明 |
|------|------|------|
| max_drawdown | float | 最大回撤幅度 |
| peak_value | float | 峰值 |
| trough_value | float | 谷值 |
| start_index | integer | 峰值索引 |
| end_index | integer | 谷值索引 |
| start_date | string | 峰值日期（可选） |
| end_date | string | 谷值日期（可选） |

### attribution_summary

归因分析摘要。

| 字段 | 类型 | 说明 |
|------|------|------|
| outperform_reason | string | 跑赢原因 |
| underperform_reason | string | 跑输原因 |

### fund_return_ranking

单基金收益排名列表，**新增 data_source 字段**:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| return | float | 收益率 |
| data_source | string | 数据来源（真实净值 / 模拟数据） |
| returns_1m | float | 近1月收益率（可选，取决于数据长度） |
| returns_3m | float | 近3月收益率（可选） |
| returns_6m | float | 近6月收益率（可选） |
| returns_1y | float | 近1年收益率（可选） |
| returns_2y | float | 近2年收益率（可选） |
| returns_3y | float | 近3年收益率（可选） |
| returns_since_inception | float | 成立以来收益率（可选） |

### portfolio_nav_curve *(新增)*

标准化组合净值曲线（起始=1）。

| 字段 | 类型 | 说明 |
|------|------|------|
| dates | array[string] | 日期序列 |
| nav_series | array[float] | 组合净值序列 |
| normalized | array[float] | 标准化净值（起始=1） |

### benchmark_nav_curve *(新增)*

对比指数净值曲线。

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 指数名称（如"偏股混合型基金指数"） |
| dates | array[string] | 日期序列 |
| nav_series | array[float] | 指数净值序列 |
| normalized | array[float] | 标准化净值 |

### benchmark_metrics *(新增)*

基准对比指标。

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 基准名称 |
| cumulative_return | float | 基准累计收益率 |
| cagr | float | 基准年化收益率 |
| max_drawdown | float | 基准最大回撤 |

### excess_vs_benchmark *(新增)*

超额收益对比。

| 字段 | 类型 | 说明 |
|------|------|------|
| return_diff | float | 超额累计收益（组合-基准） |
| cagr_diff | float | 超额年化收益 |
| mdd_diff | float | 回撤差值（组合-基准） |

### multi_period_returns *(新增)*

组合多期收益，基于组合净值序列按回溯窗口切片计算:

| 字段 | 类型 | 说明 |
|------|------|------|
| 1m | float | 近1月收益率（21交易日） |
| 3m | float | 近3月收益率（63交易日） |
| 6m | float | 近6月收益率（126交易日） |
| 1y | float | 近1年收益率（252交易日） |
| 2y | float | 近2年收益率（504交易日，可选） |
| 3y | float | 近3年收益率（756交易日，可选） |
| since_inception | float | 成立以来收益率 |

> 历史数据不足以覆盖某个回溯期时，该期间字段被省略。 |

#### 边界处理说明

当历史数据不足以计算某期收益时：
- 对应期的收益率字段设为 `null`（而非省略该字段）
- 在该期数据旁附加 `"data_insufficient": true` 标记
- 计算逻辑：近1月=21交易日，近3月=63交易日，近6月=126交易日，近1年=252交易日

示例（数据不足时）：
```json
"multi_period_returns": {
  "1m": 0.0523,
  "3m": 0.1245,
  "6m": null,
  "1y": null,
  "data_insufficient_periods": ["6m", "1y"]
}
```

**示例**:
```json
{
  "data_source_note": "基于基金净值加权计算",
  "multi_period_returns": {
    "1m": 0.0230, "3m": 0.0650, "6m": 0.1120,
    "1y": 0.1523, "since_inception": 0.1523
  },
  "comparison_table": {
    "portfolio": {"total_return": 0.1523, "cagr": 0.1456},
    "benchmark": {"total_return": 0.1020},
    "excess_return": 0.0503
  },
  "performance_metrics": {
    "cumulative_return": 0.1523,
    "cagr": 0.1456,
    "volatility": 0.1820,
    "max_drawdown": -0.1215,
    "var_95": -0.0285,
    "cvar_95": -0.0420,
    "sharpe_ratio": 0.7560,
    "sortino_ratio": 1.0230,
    "calmar_ratio": 0.9520,
    "downside_risk": 0.1240,
    "tail_ratio": 1.1500,
    "alpha": 0.0320,
    "beta": 0.8700
  },
  "max_drawdown_detail": {
    "max_drawdown": 0.1215,
    "peak_value": 1.1523,
    "trough_value": 1.0122,
    "start_index": 45,
    "end_index": 78,
    "start_date": "2023-06-15",
    "end_date": "2023-09-20"
  },
  "attribution_summary": {
    "outperform_reason": "超配优质成长板块，低配周期板块",
    "underperform_reason": "部分持仓受行业轮动影响"
  },
  "fund_return_ranking": [
    {"code": "000001", "name": "华夏成长", "return": 0.2530, "data_source": "真实净值"},
    {"code": "000002", "name": "易方达消费", "return": 0.1820, "data_source": "真实净值"}
  ]
}
```

---

## diagnosis (账户诊断总览)

### 综合评分

| 字段 | 类型 | 说明 |
|------|------|------|
| comprehensive_score | integer | 综合得分(0-100) |
| grade | string | 等级(A+/A/B+/B/C) |

### fund_score_details

基金得分明细列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| return_score | integer | 收益得分 |
| risk_score | integer | 风险得分 |
| comprehensive_score | integer | 综合得分 |
| grade | string | 等级 |

### allocation_deviation

配置偏离度，键为资产类型，值为:

| 字段 | 类型 | 说明 |
|------|------|------|
| current | float | 当前配置比例 |
| target | float | 目标配置比例 |
| deviation | float | 偏离度 |

### diagnosis_suggestion

诊断建议字符串，根据偏离度动态生成。

### manager_rating *(新增)*

基金经理加权评分。

| 字段 | 类型 | 说明 |
|------|------|------|
| weighted_score_1y | integer | 近1年加权经理评分 |
| weighted_score_2y | integer | 近2年加权经理评分 |
| weighted_score_3y | integer | 近3年加权经理评分 |

### manager_ratings_detail *(新增)*

各基金经理评分明细列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| overall_1y | integer | 近1年综合评分 |
| rank_1y | integer | 近1年排名百分位 |
| ret_1y | integer | 近1年收益评分 |
| mdd_1y | integer | 近1年回撤评分 |
| sca_1y | integer | 近1年规模评分 |

### correlation_level *(新增)*

组合相关性水平: "低" | "中" | "高"。

### stock_concentration *(新增)*

穿透后个股集中度。

| 字段 | 类型 | 说明 |
|------|------|------|
| max_stock | string | 最高集中度股票名称 |
| max_weight | float | 最高集中度权重 |
| top5 | array | Top5集中度个股列表 |
| top5[].name | string | 股票名称 |
| top5[].weight | float | 权重 |
| level | string | 集中度等级（偏高/适中/分散/无数据） |

### fund_subscores_detail *(新增)*

各基金评分子维度列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| rank_1y | integer | 近1年排名百分位 |
| nhi_1y | integer | 创新高得分 |
| sec_1y | integer | 择股得分 |
| tim_1y | integer | 择时得分 |
| sca_1y | integer | 规模得分 |

**示例**:
```json
{
  "comprehensive_score": 78,
  "grade": "B+",
  "fund_score_details": [
    {
      "code": "000001",
      "name": "华夏成长",
      "return_score": 82,
      "risk_score": 75,
      "comprehensive_score": 79,
      "grade": "B+"
    }
  ],
  "allocation_deviation": {
    "equity": {"current": 0.72, "target": 0.70, "deviation": 0.02},
    "fixed_income": {"current": 0.15, "target": 0.15, "deviation": 0.00},
    "cash": {"current": 0.13, "target": 0.15, "deviation": -0.02}
  },
  "diagnosis_suggestion": "配置存在轻度偏离，可择机调整"
}
```

---

## allocation (组合配置诊断)

### asset_allocation

大类资产分布列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| type | string | 资产类型 |
| weight | float | 权重 |

### country_allocation

国家/地区分布列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| region | string | 地区 |
| weight | float | 权重 |

### industry_allocation

国内行业穿透列表(Top 15)，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| industry | string | 行业名称 |
| weight | float | 加权后的权重 |
| change | float | 环比变化 |

### top_holdings

重仓股穿透列表(Top 15)，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| stock | string | 股票名称 |
| weight | float | 持仓权重（加权合并后） |
| style | string | 风格标签（价值/成长/防御） |

### fund_managers

基金经理穿透列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 基金经理姓名 |
| weight | float | 管理权重 |
| funds | array | 管理的基金代码列表 |

### concentration_risk

行业集中度风险。

| 字段 | 类型 | 说明 |
|------|------|------|
| hhi | float | HHI指数 |
| level | string | 风险等级(高/中/低) |
| warning | string | 风险提示 |

### holding_style_tags

重仓股风格分布，键为风格类型，值为权重。

**示例**:
```json
{
  "asset_allocation": [
    {"type": "equity", "weight": 0.72},
    {"type": "fixed_income", "weight": 0.15}
  ],
  "country_allocation": [
    {"region": "China", "weight": 0.85},
    {"region": "US", "weight": 0.10}
  ],
  "industry_allocation": [
    {"industry": "电子", "weight": 0.18, "change": 0.02},
    {"industry": "医药生物", "weight": 0.15, "change": -0.01}
  ],
  "top_holdings": [
    {"stock": "贵州茅台", "weight": 0.05, "style": "价值"},
    {"stock": "宁德时代", "weight": 0.04, "style": "成长"}
  ],
  "fund_managers": [
    {"name": "张伟", "weight": 0.35, "funds": ["000001", "000002"]}
  ],
  "concentration_risk": {
    "hhi": 0.18,
    "level": "高",
    "warning": "行业集中度偏高，建议适当分散"
  },
  "holding_style_tags": {
    "价值": 0.40,
    "成长": 0.45,
    "防御": 0.15
  }
}
```

---

## correlation (相关性分析)

### correlation_matrix

相关系数矩阵。

| 字段 | 类型 | 说明 |
|------|------|------|
| funds | array | 基金代码列表 |
| matrix | array | N×N相关系数矩阵 |

### average_pairwise_correlation *(新增)*

平均两两相关系数，取相关系数矩阵上三角非对角线元素的均值。

| 字段 | 类型 | 说明 |
|------|------|------|
| average_pairwise_correlation | float | 平均两两相关系数 |

### groups

高相关基金组列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| funds | array | 组内基金代码列表 |
| fund_names | array | 组内基金名称列表 |
| average_correlation | float | 组内平均相关系数 |
| high_correlation_pairs | array | 组内高相关对 |

### high_correlation_pairs

高相关基金对列表:

| 字段 | 类型 | 说明 |
|------|------|------|
| fund1 | string | 基金代码1 |
| fund1_name | string | 基金名称1 |
| fund2 | string | 基金代码2 |
| fund2_name | string | 基金名称2 |
| correlation | float | 相关系数 |

### rebalancing_suggestion

调仓建议字符串。

**示例**:
```json
{
  "correlation_matrix": {
    "funds": ["000001", "000002", "000003"],
    "matrix": [
      [1.0, 0.82, 0.65],
      [0.82, 1.0, 0.58],
      [0.65, 0.58, 1.0]
    ]
  },
  "average_pairwise_correlation": 0.6833,
  "groups": [
    {
      "funds": ["000001", "000002"],
      "fund_names": ["华夏成长", "易方达消费"],
      "average_correlation": 0.82,
      "high_correlation_pairs": [
        {"fund1": "000001", "fund1_name": "华夏成长", "fund2": "000002", "fund2_name": "易方达消费", "correlation": 0.82}
      ]
    }
  ],
  "high_correlation_pairs": [
    {"fund1": "000001", "fund1_name": "华夏成长", "fund2": "000002", "fund2_name": "易方达消费", "correlation": 0.82}
  ],
  "rebalancing_suggestion": "存在高度相关的基金组，建议合并或选择差异化产品"
}
```

---

## evaluation (单只基金评价)

### fund_evaluations

主动型基金评价列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| fund_type | string | 基金类型（新增） |
| manager | string | 基金经理（新增） |
| evaluation_path | string | 评价路径 |
| comprehensive_score | integer | 综合得分 |
| grade | string | 等级 |
| suggestion | string | 建议 |
| max_drawdown | float | 最大回撤（新增） |
| max_drawdown_period | object | 最大回撤时间区间，含start_date/end_date（新增） |
| volatility | float | 年化波动率（新增） |
| sharpe_ratio | float | 夏普比率（新增） |
| multi_period_returns | object | 多期收益，键为1m/3m/6m/1y/2y/3y/since_inception（新增） |
| top_5_holdings | array | 前5大重仓股列表（新增） |
| subscores | object | 子维度评分（创新高/择股/择时/规模）（新增） |
| manager_rating | object | 基金经理评分（overall_1y/rank_1y等）（新增） |
| announcement | object | 公告/舆情信息（negative_events/has_negative/summary）（新增） |
| recommendation | string | 操作建议（保留/观察/替换/部分替换）（新增） |
| recommendation_reason | string | 操作建议理由（新增） |
| fund_nav_vs_benchmark | object | 基金净值vs基准净值（fund_nav/benchmark_nav）（新增） |

### index_fund_valuations

指数型基金估值分析列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| fund_type | string | 基金类型（新增） |
| manager | string | 基金经理（新增） |
| evaluation_path | string | 评价路径 |
| excess_return | float | 超额收益 |
| pe_percentile | float | PE分位数(%) |
| valuation | string | 估值判断(偏低/适中/偏高) |
| suggestion | string | 建议 |
| max_drawdown | float | 最大回撤（新增） |
| max_drawdown_period | object | 最大回撤时间区间（新增） |
| volatility | float | 年化波动率（新增） |
| sharpe_ratio | float | 夏普比率（新增） |
| multi_period_returns | object | 多期收益（新增） |
| top_5_holdings | array | 前5大重仓股列表（新增） |
| track_index | string | 跟踪标的指数名称（新增） |
| fund_nav_vs_benchmark | object | 基金净值vs基准净值（新增） |

**示例**:
```json
{
  "fund_evaluations": [
    {
      "code": "000001",
      "name": "华夏成长混合",
      "fund_type": "混合型",
      "manager": "张伟",
      "evaluation_path": "主动型",
      "comprehensive_score": 82,
      "grade": "B+",
      "suggestion": "良好",
      "max_drawdown": 0.1215,
      "max_drawdown_period": {"start_date": "2023-06-15", "end_date": "2023-09-20"},
      "volatility": 0.1820,
      "sharpe_ratio": 0.7560,
      "multi_period_returns": {"1m": 0.02, "3m": 0.05, "6m": 0.08, "1y": 0.15},
      "top_5_holdings": [
        {"stock": "贵州茅台", "weight": 0.06, "style": "价值"}
      ]
    }
  ],
  "index_fund_valuations": [
    {
      "code": "510300",
      "name": "沪深300ETF",
      "fund_type": "指数型",
      "manager": "",
      "evaluation_path": "指数型",
      "excess_return": 0.0250,
      "pe_percentile": 35.5,
      "valuation": "偏低",
      "suggestion": "估值偏低，可关注",
      "max_drawdown": 0.1520,
      "max_drawdown_period": {"start_date": "2023-05-10", "end_date": "2023-10-15"},
      "volatility": 0.2010,
      "sharpe_ratio": 0.5200,
      "multi_period_returns": {"1m": 0.01, "3m": 0.04, "6m": 0.07, "1y": 0.10},
      "top_5_holdings": []
    }
  ]
}
```

---

## rebalance (调仓建议)

### allocation_comparison

配置对比列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| asset | string | 资产类型 |
| current | float | 当前权重 |
| target | float | 目标权重 |
| deviation | float | 偏离度 |
| status | string | 状态(超配/低配/正常) |

### reduce_suggestions

减仓建议列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| asset | string | 资产类型 |
| overweight | float | 超配幅度 |
| suggested_action | string | 建议操作 |
| funds_to_reduce | array | 建议减仓的基金 |

### increase_suggestions

加仓建议列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| asset | string | 资产类型 |
| underweight | float | 低配幅度 |
| target_weight | float | 目标权重 |
| suggested_action | string | 建议操作 |
| funds_to_increase | array | 建议加仓的基金 |

### expected_improvement

预期改善说明字符串。

### fund_replacement_suggestions *(新增)*

基金替换建议列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| code | string | 基金代码 |
| name | string | 基金名称 |
| reason | string | 替换理由 |
| action | string | 操作（替换/减仓） |
| score | integer | 基金评分 |

### recommended_funds *(新增)*

推荐核心持仓列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| name | string | 基金名称 |
| code | string | 基金代码 |
| score | integer | 评分 |
| manager_score | mixed | 经理评分 |
| brief | string | 推荐说明 |

### batch_schedule *(新增)*

替换批次安排列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| batch | integer | 批次序号 |
| time | string | 计划时间（年月） |
| funds | array[string] | 该批次基金名称列表 |
| amount | string | 数量描述 |

### post_rebalance *(新增)*

调仓后预期改善。

| 字段 | 类型 | 说明 |
|------|------|------|
| allocation | array | 调仓后配置列表 |
| correlation_improvement | string | 相关性改善说明 |
| expected_improvement | string | 预期改善说明 |

**示例**:
```json
{
  "allocation_comparison": [
    {"asset": "equity", "current": 0.72, "target": 0.70, "deviation": 0.02, "status": "正常"}
  ],
  "reduce_suggestions": [
    {
      "asset": "equity",
      "overweight": 0.12,
      "suggested_action": "减配equity，建议赎回比例: 12.0%",
      "funds_to_reduce": ["建议选择近期表现较弱或相关性高的基金"]
    }
  ],
  "increase_suggestions": [
    {
      "asset": "fixed_income",
      "underweight": 0.25,
      "target_weight": 0.15,
      "suggested_action": "加配fixed_income，建议增持比例: 25.0%",
      "funds_to_increase": ["建议选择优质固收基金"]
    }
  ],
  "expected_improvement": "调整后组合风险收益比将更接近目标水平"
}
```

---

## risk (风险提示)

### scenario_analysis

情景分析列表，每项包含:

| 字段 | 类型 | 说明 |
|------|------|------|
| scenario | string | 情景名称 |
| expected_return | float | 预期收益率 |
| expected_drawdown | float | 预期回撤 |
| probability | string | 发生概率 |

### market_risks

市场风险列表，每项为字符串风险描述。

### liquidity_risks

流动性风险列表，每项为字符串风险描述。

### max_drawdown_period *(新增)*

最大回撤时间区间（仅当performance模块提供了max_drawdown_detail时包含）。

| 字段 | 类型 | 说明 |
|------|------|------|
| start_date | string | 回撤起始日期（峰值日） |
| end_date | string | 回撤结束日期（谷值日） |

**示例**:
```json
{
  "scenario_analysis": [
    {"scenario": "牛市(+1σ)", "expected_return": 0.2520, "expected_drawdown": -0.0910, "probability": "约16%"},
    {"scenario": "基准", "expected_return": 0.1520, "expected_drawdown": -0.1456, "probability": "约68%"},
    {"scenario": "熊市(-1σ)", "expected_return": 0.0520, "expected_drawdown": -0.2730, "probability": "约16%"}
  ],
  "market_risks": [
    "权益仓位偏高(72.0%)，市场下跌时组合回撤风险较大"
  ],
  "liquidity_risks": [
    "整体流动性风险可控，主流基金赎回通常T+3到账"
  ],
  "max_drawdown_period": {
    "start_date": "2023-06-15",
    "end_date": "2023-09-20"
  }
}
```

---

## summary (报告总结) *(新增)*

### core_findings

核心发现列表（最多5条），每项为字符串。

### key_risks

关键风险列表（最多5条），每项为字符串。

### optimization_suggestions

优化建议列表（最多5条），每项为字符串。

### overall_assessment

总体评价字符串（如"账户整体表现良好，得分78分B+级。"）。

**示例**:
```json
{
  "core_findings": [
    "综合诊断得分78分（等级B+），持有6只基金",
    "总市值500,000元，总成本450,000元，浮盈亏+50,000元（+11.11%）",
    "组合累计收益15.23%，最大回撤-12.15%，夏普比率0.76"
  ],
  "key_risks": [
    "整体风险等级: 中",
    "权益仓位偏高(72.0%)，市场下跌时组合回撤风险较大"
  ],
  "optimization_suggestions": [
    "配置存在轻度偏离，可择机调整",
    "建议替换以下基金: XXX基金"
  ],
  "overall_assessment": "账户整体表现良好，得分78分B+级。"
}
```

---

## report_footer

报告尾部信息。

| 字段 | 类型 | 说明 |
|------|------|------|
| disclaimer | string | 免责声明 |
| modules | array | 本次输出的分析模块列表 |

**示例**:
```json
{
  "disclaimer": "本报告仅供参考，不构成投资建议。基金有风险，投资需谨慎。",
  "modules": ["diagnosis", "overview", "performance", "risk", "allocation", "correlation", "evaluation", "rebalance", "summary"]
}
```

---

## 错误响应格式

当发生错误时，返回以下格式:

```json
{
  "error": "错误描述字符串",
  "traceback": "详细错误堆栈（可选）"
}
```

---

## 数据来源标注

### MCP API vs 模拟数据

报告头部包含数据来源标注：

| 字段 | 说明 |
|------|------|
| data_source | 固定为 "qieman MCP API" |
| api_available | true（已配置凭证）或 false（未配置） |
| mcp_url | MCP服务器地址 |

### 各模块数据来源

| 模块 | 数据来源说明 |
|------|-------------|
| overview | qieman fund_info |
| performance | qieman fund_nav + 加权计算 |
| diagnosis | qieman fund_evaluate |
| allocation | qieman fund_industry_allocation + fund_holdings |
| correlation | 基于净值计算的收益率相关性 |
| evaluation | qieman fund_evaluate |
| rebalance | 基于配置诊断结果 |
| risk | 收益率统计 + 配置分析 |

### MCP工具列表

| 工具名称 | 说明 |
|----------|------|
| fund_info | 基金基础信息 |
| fund_nav | 基金净值序列 |
| fund_industry_allocation | 行业配置 |
| fund_holdings | 重仓股数据 |
| fund_evaluate | 基金评价 |
| index_nav | 指数净值数据 *(新增)* |
| fund_manager_rating | 基金经理评分 *(新增)* |
| fund_subscores | 基金评分子维度 *(新增)* |
| fund_announcement | 基金公告/舆情 *(新增)* |

---

## 输出控制

### 模块选择

通过 `--modules` 参数可选择输出特定模块，多个模块用逗号分隔。

可用模块值（按默认输出顺序排列）:
- `diagnosis` - 账户诊断总览
- `overview` - 持仓概览
- `performance` - 收益风险表现
- `risk` - 风险提示
- `allocation` - 组合配置诊断
- `correlation` - 相关性分析
- `evaluation` - 单只基金评价
- `rebalance` - 调仓建议
- `summary` - 报告总结

设置为 `all` 或省略参数时输出所有模块。

### 文件输出

使用 `--output` 参数指定输出文件路径，JSON格式保存。

---

## 数据类型规范

为确保数据一致性，所有模块统一遵循以下类型约定：

| 数据类型 | 表示方式 | 示例 | 说明 |
|---------|---------|------|------|
| 权重 | 小数 (0-1) | 0.25 | 表示 25%，前端显示时乘以 100 |
| 收益率 | 小数 | 0.1523 | 表示 15.23%，前端显示时乘以 100 |
| 百分比值 | 数字 (0-100) | 15.23 | 已乘以 100 的百分比，如评分、占比展示值 |
| 金额 | 数字 | 50000.00 | 单位：元，保留 2 位小数 |
| 日期 | 字符串 | "2024-01-15" | ISO 8601 格式，YYYY-MM-DD |
| 基金代码 | 字符串 | "000001" | 6 位字符串，保留前导零 |
| 评分 | 数字 (0-100) | 85.5 | 综合评分或子项评分 |
| 布尔值 | boolean | true/false | 标准 JSON 布尔值 |

---

## 字段可选性规范

### 可选字段处理规则

1. **标记为"可选"的字段**：当数据不可用时，字段保留但值设为 `null`，不应完全省略该字段
2. **标记为"新增"的字段**：为向后兼容而新增的字段，客户端应做存在性检查
3. **条件字段**：某些字段仅在特定条件下存在（如 `multi_period_returns` 中的各期数据），当数据不足时设为 `null` 并附带说明字段

### 客户端处理建议

- 读取任何字段前应先检查是否存在及是否为 `null`
- 数值字段为 `null` 时，前端应显示为 "—" 或 "N/A"
- 不应假设 JSON 结构中的字段总是完整的

---

## 数据验证规则

| 字段 | 验证规则 |
|------|----------|
| 权重(weight) | 0 ≤ value ≤ 1 |
| 收益率(return) | -1 ≤ value ≤ 10 |
| 得分(score) | 0 ≤ value ≤ 100 |
| 相关系数(correlation) | -1 ≤ value ≤ 1 |
| HHI指数 | 0 ≤ value ≤ 1 |
| 市值(market_value) | ≥ 0 |
| 成本(cost) | ≥ 0 |
