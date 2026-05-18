# 基金账户诊断 Skill

<p align="center">
  <strong>Qoder Agent Skill — 基金投资组合综合诊断分析</strong><br>
  持仓分析 · 收益计算 · 风险评估 · 配置诊断 · 调仓建议
</p>

---

## 项目简介

本项目是一个 **Qoder Agent Skill**，为 AI 智能体提供基金账户综合诊断分析能力。通过上传交易记录 Excel 或提供基金代码列表，Skill 可自动生成包含 9 大分析模块的结构化诊断报告（JSON / HTML），帮助用户全面了解基金组合的健康状况。

### 什么是 Qoder Skill？

Qoder Skill 是一种 AI 智能体技能包，定义了 AI 在特定场景下的角色、知识和操作流程。本 Skill 会被 Qoder 平台打包为 `.skill` 文件（zip 格式），供 AI 智能体在对话中按需调用。

### 核心能力

- **交易记录解析** — 自动识别 Excel 中的申购/赎回/分红/转换/定投等多种业务类型
- **9 大诊断模块** — 账户总览、持仓概览、收益风险、风险提示、配置诊断、相关性分析、基金评价、调仓建议、报告总结
- **HTML 可视化报告** — 内置 13 种 ECharts 交互式图表，品牌色设计，响应式布局
- **自动降级机制** — API 不可用时自动切换为模拟数据，确保报告正常生成

## 快速开始

### 安装 Skill

将本项目导入 Qoder 平台，或直接使用打包好的 `fund-account-diagnostic.skill` 文件。

### 运行环境

- Python 3.8+
- 依赖：pandas、numpy、empyrical（可选加速）、coze_workload_identity

```bash
cd fund-account-diagnostic
pip3 install -r requirements.txt
```

### 使用方式

用户在 Qoder 对话中触发 Skill，例如：

- "诊断我的基金账户"
- "分析我的基金持仓"
- "根据交易记录生成诊断报告"

也可以通过命令行直接运行脚本：

**通过基金代码列表**

```bash
python scripts/diagnostic_report.py --funds 000001,000002,000003
```

**通过交易记录 Excel（推荐）**

```bash
python scripts/diagnostic_report.py --transaction-file ./transactions.xlsx
```

**生成 HTML 可视化报告**

```bash
python scripts/diagnostic_report.py --funds 000001,000002 --format html --output report.html
```

**指定模块诊断**

```bash
python scripts/diagnostic_report.py --funds 000001,000002 --modules overview,performance,risk
```

## 诊断报告模块

| 模块 | 说明 | 关键指标 |
|------|------|----------|
| **diagnosis** | 账户诊断总览 | 综合得分、等级、配置偏离度、经理评分 |
| **overview** | 持仓概览 | 基金数量、总市值、盈亏、集中度预警 |
| **performance** | 收益风险表现 | 累计收益、年化收益、最大回撤、夏普比率、多期收益 |
| **risk** | 风险提示 | 情景分析(牛市/基准/熊市)、市场风险、流动性风险 |
| **allocation** | 组合配置诊断 | 大类资产、国家地区、行业穿透、重仓股 |
| **correlation** | 相关性分析 | 相关系数矩阵、高相关对、相关性水平 |
| **evaluation** | 单只基金评价 | 主动型/指数型双轨评价、子维度、操作建议 |
| **rebalance** | 调仓建议 | 超配/低配分析、加减仓建议、替换建议、批次安排 |
| **summary** | 报告总结 | 核心发现、关键风险、优化建议 |

## 支持的交易类型

| 业务类型 | 处理逻辑 |
|---------|---------|
| 申购 / 认购 / 定投 | 份额增加，成本增加 |
| 赎回 | 份额减少，成本按比例减少 |
| 分红 | 份额增加（分红再投） |
| 基金转换 | 转出端份额减少，转入端份额增加 |
| 转入 / 转出 | 对应份额和成本的增减 |

## 项目结构

```
fund-account-diagnostic/
├── SKILL.md                      # Skill 定义文件（角色、步骤、指标规格）
├── scripts/
│   ├── diagnostic_report.py      # 主入口，编排 9 模块报告生成
│   ├── generators.py             # 9 个模块生成器函数
│   ├── calculations.py           # 纯计算函数（收益率/回撤/夏普/相关性等）
│   ├── data_fetcher.py           # MCP 数据获取 + 模拟降级
│   ├── excel_parser.py           # 交易记录 Excel 解析
│   ├── generate_html_report.py   # JSON → HTML 可视化转换
│   ├── constants.py              # 常量 / 依赖检测 / 环境变量
│   ├── utils.py                  # 金额解析 / 业务类型标准化
│   ├── mcp_client.py             # JSON-RPC 2.0 MCP 协议客户端
│   └── tests/                    # pytest 单元测试
├── references/
│   ├── indicator_spec.md         # 指标规格说明
│   └── output_format.md          # 报告输出格式定义
├── requirements.txt              # Python 依赖
└── .gitignore
fund-account-diagnostic.skill    # Skill 打包文件（zip 格式，可直接导入 Qoder）
```

## 数据源

本系统使用 **qieman MCP 服务器** 获取基金数据（基金信息、净值、行业配置、重仓股、评价等 9 种数据接口）。当 API 不可用时，自动降级为确定性模拟数据，确保报告正常生成。

如需使用真实 API 数据，需配置环境变量 `COZE_QIEMAN_API_{SKILL_ID}`。

## 运行测试

```bash
cd fund-account-diagnostic/scripts
python -m pytest tests/ -v
```

## 免责声明

> 本报告仅基于历史数据和量化模型生成，不构成投资建议。基金投资有风险，过往业绩不预示未来表现，投资者应根据自身风险承受能力做出独立判断。

## 许可证

MIT License
