#!/usr/bin/env python3
"""
基金账户诊断报告 - HTML格式生成器
读取JSON诊断报告，生成自包含HTML文件（ECharts可视化）
品牌色: #0052D9
"""

import argparse
import json
import sys
import os

# ============================================================
# 映射字典
# ============================================================

ASSET_NAMES = {
    "equity": "权益", "fixed_income": "固收", "cash": "现金",
    "overseas": "海外", "commodity": "商品", "other": "其他",
}

REGION_NAMES = {
    "China": "中国", "US": "美国", "Japan": "日本", "Europe": "欧洲",
    "India": "印度", "HongKong": "中国香港", "Other": "其他",
}

PERIOD_LABELS = {
    "1m": "近1月", "3m": "近3月", "6m": "近6月",
    "1y": "近1年", "2y": "近2年", "3y": "近3年",
    "since_inception": "成立以来",
}

GRADE_COLORS = {
    "A+": "#E53E3E", "A": "#E53E3E",
    "B+": "#3182CE", "B": "#DD6B20",
    "C": "#805AD5", "D": "#718096",
}

CHART_COLORS = [
    "#0052D9", "#36A3F7", "#80B3FF", "#4D94FF",
    "#1A76FF", "#0041AD", "#003182", "#E53E3E",
    "#38A169", "#DD6B20", "#805AD5", "#D69E2E",
    "#00B5D8", "#F56565", "#48BB78", "#ECC94B",
]


# ============================================================
# 格式化工具函数
# ============================================================

def fmt_currency(val):
    if val is None:
        return "¥0.00"
    v = float(val)
    if abs(v) >= 10000:
        return f"¥{v/10000:,.2f}万"
    return f"¥{v:,.2f}"


def fmt_percent(val, decimals=2):
    if val is None:
        return "0.00%"
    v = float(val) * 100
    return f"{v:,.{decimals}f}%"


def fmt_number(val, decimals=2):
    if val is None:
        return "0.00"
    return f"{float(val):,.{decimals}f}"


def color_class(val):
    v = float(val) if val is not None else 0
    return "text-up" if v > 0 else "text-down" if v < 0 else ""


def grade_badge(grade):
    bg = GRADE_COLORS.get(grade, "#718096")
    return f'<span class="grade-badge" style="background:{bg}">{grade}</span>'


def safe_text(val):
    if val is None:
        return ""
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def short_name(name, max_len=8):
    """截断过长的基金名称，用于 ECharts 轴标签"""
    if not name:
        return ""
    s = str(name)
    if len(s) <= max_len:
        return s
    return s[:max_len - 1] + "…"


def echarts_bar_config(element_id, title, categories, values, orientation='vertical', colors=None, value_suffix='',
                       *, container_class='chart-container', grid=None, bar_max_width=None,
                       color_fn=None, full_names=None, category_axis_label=None, value_axis_max=None):
    """生成 ECharts 柱状图的通用 JS 配置代码。

    Args:
        element_id: DOM 元素 ID
        title: 图表标题
        categories: 分类标签列表（JSON 字符串）
        values: 数据值列表（JSON 字符串）
        orientation: 方向，'vertical' 或 'horizontal'
        colors: 颜色列表（JSON 字符串），可选
        value_suffix: 值后缀（如 '%'）
        container_class: 外层容器 CSS 类名
        grid: 网格配置字典，可选
        bar_max_width: 柱状图最大宽度
        color_fn: 自定义 JS 颜色函数字符串（覆盖 colors）
        full_names: 完整名称列表（JSON 字符串），用于 tooltip 显示
        category_axis_label: 分类轴 axisLabel 配置字典
        value_axis_max: 值轴最大值

    Returns:
        str: 完整的 ECharts 初始化 HTML+JS 代码块
    """
    if orientation == 'horizontal':
        label_position = 'right'
    else:
        label_position = 'top'

    # Grid
    if grid is None:
        if orientation == 'horizontal':
            grid = {'left': 100, 'right': 40, 'top': 50, 'bottom': 20}
        else:
            grid = {'left': 60, 'right': 20, 'top': 50, 'bottom': 30}
    grid_js = json.dumps(grid)

    # Tooltip
    if full_names:
        tooltip_js = f"trigger: 'axis', formatter: function(p){{ var fn = {full_names}; return fn[p[0].dataIndex] + ': ' + p[0].value + '{value_suffix}'; }}"
    elif value_suffix:
        tooltip_js = f"trigger: 'axis', formatter: function(p){{ return p[0].name + ': ' + p[0].value + '{value_suffix}'; }}"
    else:
        tooltip_js = "trigger: 'axis'"

    # Color
    if color_fn:
        color_js = f"color: {color_fn}"
    elif colors:
        color_list = json.loads(colors) if isinstance(colors, str) else colors
        if len(color_list) == 1:
            color_js = f"color: '{color_list[0]}'"
        else:
            color_js = f"color: {json.dumps(color_list)}"
    else:
        color_js = "color: '#0052D9'"

    # Value axis
    val_axis_parts = ["type: 'value'"]
    if value_axis_max is not None:
        val_axis_parts.append(f"max: {value_axis_max}")
    if value_suffix:
        val_axis_parts.append(f"axisLabel: {{ formatter: '{{value}}{value_suffix}' }}")
    val_axis_opts = ", ".join(val_axis_parts)

    # Category axis
    cat_axis_parts = [f"type: 'category', data: {categories}"]
    if category_axis_label:
        cat_axis_parts.append(f"axisLabel: {json.dumps(category_axis_label, ensure_ascii=False)}")
    cat_axis_opts = ", ".join(cat_axis_parts)

    # Bar max width
    bmw_str = f"barMaxWidth: {bar_max_width}," if bar_max_width else ""

    # Label formatter
    label_fmt = f"'{{c}}{value_suffix}'"

    # Axes assignment based on orientation
    if orientation == 'horizontal':
        x_axis_opts = val_axis_opts
        y_axis_opts = cat_axis_opts
    else:
        x_axis_opts = cat_axis_opts
        y_axis_opts = val_axis_opts

    return f'''
    <div class="{container_class}">
      <div id="{element_id}" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('{element_id}');
      if(!el) return;
      var chart = echarts.init(el);
      chart.setOption({{
        title: {{ text: '{title}', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ {tooltip_js} }},
        grid: {grid_js},
        xAxis: {{ {x_axis_opts} }},
        yAxis: {{ {y_axis_opts} }},
        series: [{{
          type: 'bar', data: {values},
          itemStyle: {{ {color_js} }},
          {bmw_str}
          label: {{ show: true, position: '{label_position}', formatter: {label_fmt}, fontSize: 10 }}
        }}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''


def echarts_line_config(element_id, title, x_labels, series_list,
                        *, container_class='chart-container', grid=None,
                        x_axis_label=None, y_scale=False):
    """生成 ECharts 折线图的通用 JS 配置代码。

    Args:
        element_id: DOM 元素 ID
        title: 图表标题
        x_labels: X 轴标签（JSON 字符串）
        series_list: 系列数据列表，每项包含 name、data（JSON 字符串）、
                     可选 line_type（如 'dashed'）和 color

    Returns:
        str: 完整的 ECharts 初始化 HTML+JS 代码块
    """
    # Grid
    if grid is None:
        grid = {'left': 60, 'right': 20, 'top': 70, 'bottom': 30}
    grid_js = json.dumps(grid)

    # X axis label
    x_label_js = ""
    if x_axis_label:
        x_label_js = f", axisLabel: {json.dumps(x_axis_label)}"

    # Y axis
    y_axis_opts = "type: 'value'"
    if y_scale:
        y_axis_opts += ", scale: true"

    # Legend
    legend_names = [s["name"] for s in series_list]
    legend_js = json.dumps(legend_names, ensure_ascii=False)

    # Series
    series_parts = []
    for s in series_list:
        name = s["name"]
        data = s["data"]
        line_type = s.get("line_type")
        color = s.get("color")
        line_style_js = f", lineStyle: {{ width: 2, type: '{line_type}' }}" if line_type else ", lineStyle: { width: 2 }"
        color_js = f", itemStyle: {{ color: '{color}' }}" if color else ""
        series_parts.append(
            f"{{ name: '{name}', type: 'line', data: {data}, showSymbol: false{line_style_js}{color_js} }}"
        )
    series_js = ", ".join(series_parts)

    return f'''
    <div class="{container_class}">
      <div id="{element_id}" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('{element_id}');
      if(!el) return;
      var chart = echarts.init(el);
      chart.setOption({{
        title: {{ text: '{title}', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ trigger: 'axis' }},
        legend: {{ data: {legend_js}, top: 35 }},
        grid: {grid_js},
        xAxis: {{ type: 'category', data: {x_labels}{x_label_js} }},
        yAxis: {{ {y_axis_opts} }},
        series: [{series_js}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''


# ============================================================
# 各模块 HTML 片段生成
# ============================================================

def render_header(data):
    hdr = data.get("report_header", {})
    time_str = safe_text(hdr.get("generate_time", ""))
    api_ok = hdr.get("api_available", False)
    api_status = '<span class="api-ok">API正常</span>' if api_ok else '<span class="api-err">API不可用</span>'
    data_src = safe_text(hdr.get("data_source", ""))
    version = safe_text(hdr.get("tool_version", ""))
    return f'''
    <header class="hero" id="section-header">
      <div class="hero-content">
        <h1>基金账户诊断报告</h1>
        <div class="hero-meta">
          <span>生成时间: {time_str}</span>
          <span>数据源: {data_src}</span>
          <span>版本: v{version}</span>
          {api_status}
        </div>
      </div>
    </header>'''


def render_overview(data):
    ov = data.get("overview")
    if not ov:
        return ""
    bi = ov.get("basic_info", {})
    total_mv = bi.get("total_market_value", 0)
    total_cost = bi.get("total_cost", 0)
    profit = bi.get("profit", 0)
    profit_rate = bi.get("profit_rate", 0)
    fund_count = bi.get("fund_count", 0)

    holdings = ov.get("holdings_detail", [])

    # KPI cards
    kpi_html = f'''
    <div class="kpi-grid">
      <div class="kpi-card">
        <div class="kpi-label">总市值</div>
        <div class="kpi-value">{fmt_currency(total_mv)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">总成本</div>
        <div class="kpi-value">{fmt_currency(total_cost)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">总盈亏</div>
        <div class="kpi-value {color_class(profit)}">{fmt_currency(profit)}</div>
      </div>
      <div class="kpi-card">
        <div class="kpi-label">收益率</div>
        <div class="kpi-value {color_class(profit_rate)}">{fmt_percent(profit_rate)}</div>
      </div>
    </div>'''

    # Pie chart data
    pie_data = json.dumps([
        {"name": safe_text(h.get("name", h.get("code", ""))), "value": round(float(h.get("market_value", 0)), 2)}
        for h in holdings[:10]
    ], ensure_ascii=False)

    # Holdings table
    table_rows = ""
    for h in holdings:
        pr = h.get("profit_rate", 0)
        table_rows += f'''
        <tr>
          <td>{h.get("index", "")}</td>
          <td class="fund-name">{safe_text(h.get("name", ""))}</td>
          <td>{fmt_percent(h.get("weight", 0))}</td>
          <td class="{color_class(pr)}">{fmt_percent(pr)}</td>
          <td>{fmt_currency(h.get("market_value", 0))}</td>
          <td class="{color_class(h.get('profit', 0))}">{fmt_currency(h.get("profit", 0))}</td>
          <td>{safe_text(h.get("fund_type", ""))}</td>
        </tr>'''

    table_html = f'''
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>#</th><th>基金名称</th><th>权重</th><th>收益率</th><th>市值</th><th>盈亏</th><th>类型</th></tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>'''

    # Concentration alerts
    alerts_html = ""
    alerts = ov.get("concentration_alerts", [])
    if alerts:
        alert_items = "".join(
            f'<div class="alert-item alert-warn">{safe_text(a.get("message", ""))}</div>'
            for a in alerts
        )
        alerts_html = f'<div class="alert-group">{alert_items}</div>'

    # Transaction summary
    tx_html = ""
    tx = ov.get("transaction_summary")
    if tx:
        tx_html = f'''
        <div class="kpi-grid kpi-grid-3">
          <div class="kpi-card"><div class="kpi-label">申购次数</div><div class="kpi-value">{tx.get("subscribe_count",0)}</div></div>
          <div class="kpi-card"><div class="kpi-label">赎回次数</div><div class="kpi-value">{tx.get("redeem_count",0)}</div></div>
          <div class="kpi-card"><div class="kpi-label">分红次数</div><div class="kpi-value">{tx.get("dividend_count",0)}</div></div>
        </div>'''

    return f'''
    <section id="section-overview" class="card-section">
      <h2>持仓概览</h2>
      {kpi_html}
      <div class="chart-row">
        <div class="chart-container chart-half">
          <div id="chart-holdings-pie" class="echarts-box"></div>
        </div>
        <div class="chart-container chart-half">
          {alerts_html}
          {tx_html}
        </div>
      </div>
      {table_html}
    </section>
    <script>
    (function(){{
      var el = document.getElementById('chart-holdings-pie');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {pie_data};
      chart.setOption({{
        title: {{ text: '持仓分布', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ trigger: 'item', formatter: '{{b}}: {{d}}%' }} ,
        legend: {{ orient: 'vertical', right: 10, top: 'middle', type: 'scroll' }},
        color: {json.dumps(CHART_COLORS)},
        series: [{{
          type: 'pie', radius: ['40%','70%'], center: ['40%','55%'],
          label: {{ show: false }},
          emphasis: {{ label: {{ show: true, fontWeight: 'bold' }} }},
          data: data
        }}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''


def render_diagnosis(data):
    diag = data.get("diagnosis")
    if not diag:
        return ""
    score = diag.get("comprehensive_score", 0)
    grade = diag.get("grade", "")
    suggestion = safe_text(diag.get("diagnosis_suggestion", ""))
    fund_details = diag.get("fund_score_details", [])
    alloc_dev = diag.get("allocation_deviation", {})

    # Gauge chart
    gauge_html = f'''
    <div class="chart-container chart-half">
      <div id="chart-diagnosis-gauge" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-diagnosis-gauge');
      if(!el) return;
      var chart = echarts.init(el);
      chart.setOption({{
        title: {{ text: '综合评分', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        series: [{{
          type: 'gauge', startAngle: 200, endAngle: -20,
          min: 0, max: 100, splitNumber: 10,
          center: ['50%','60%'], radius: '85%',
          axisLine: {{ lineStyle: {{ width: 18, color: [[0.6,'#DD6B20'],[0.8,'#3182CE'],[1,'#38A169']] }} }},
          pointer: {{ itemStyle: {{ color: 'auto' }} }},
          axisTick: {{ distance: -18, length: 6, lineStyle: {{ color: '#fff', width: 1 }} }},
          splitLine: {{ distance: -18, length: 18, lineStyle: {{ color: '#fff', width: 2 }} }},
          axisLabel: {{ color: 'auto', distance: 25, fontSize: 11 }},
          detail: {{ valueAnimation: true, formatter: '{{value}}分', fontSize: 20, offsetCenter: [0,'70%'] }},
          data: [{{ value: {score} }}]
        }}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # Fund scores bar chart
    fund_score_categories = json.dumps([
        short_name(f.get("name", f.get("code", "")), 10) for f in fund_details
    ][::-1], ensure_ascii=False)
    fund_score_values = json.dumps([
        max(0, min(100, f.get("comprehensive_score", 0) if isinstance(f.get("comprehensive_score", 0), (int, float)) else 0))
        for f in fund_details
    ][::-1])
    fund_score_full_names = json.dumps([
        safe_text(f.get("name", f.get("code", ""))) for f in fund_details
    ][::-1], ensure_ascii=False)

    scores_html = echarts_bar_config(
        'chart-fund-scores', '基金得分', fund_score_categories, fund_score_values,
        orientation='horizontal', value_suffix='',
        container_class='chart-container chart-half',
        grid={'left': 140, 'right': 30, 'top': 50, 'bottom': 20},
        bar_max_width=14,
        color_fn="function(params) { var v = params.value; if(v >= 80) return '#38A169'; if(v >= 60) return '#3182CE'; return '#DD6B20'; }",
        full_names=fund_score_full_names,
        category_axis_label={"fontSize": 10, "width": 120, "overflow": "truncate", "ellipsis": "…"},
        value_axis_max=100
    )

    # Allocation deviation chart
    dev_series = []
    for asset in ["equity", "fixed_income", "cash"]:
        d = alloc_dev.get(asset, {})
        dev_series.append({
            "name": ASSET_NAMES.get(asset, asset),
            "current": round(float(d.get("current", 0)) * 100, 1),
            "target": round(float(d.get("target", 0)) * 100, 1),
        })
    dev_data = json.dumps(dev_series, ensure_ascii=False)

    deviation_html = f'''
    <div class="chart-container">
      <div id="chart-allocation-deviation" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-allocation-deviation');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {dev_data};
      var cats = data.map(function(d){{ return d.name; }});
      chart.setOption({{
        title: {{ text: '配置偏离对比', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ trigger: 'axis' }},
        legend: {{ data: ['当前','目标'], top: 35 }},
        grid: {{ left: 60, right: 20, top: 70, bottom: 30 }},
        xAxis: {{ type: 'category', data: cats }},
        yAxis: {{ type: 'value', axisLabel: {{ formatter: '{{value}}%' }} }},
        series: [
          {{ name: '当前', type: 'bar', data: data.map(function(d){{ return d.current; }}),
             itemStyle: {{ color: '#0052D9' }}, barMaxWidth: 30 }},
          {{ name: '目标', type: 'bar', data: data.map(function(d){{ return d.target; }}),
             itemStyle: {{ color: '#B3D1FF' }}, barMaxWidth: 30 }}
        ]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # Manager rating card
    mgr_rating = diag.get("manager_rating", {})
    mgr_html = ""
    if mgr_rating:
        mgr_html = f'''
        <div class="detail-card chart-half">
          <h3>基金经理加权评分</h3>
          <div class="detail-row"><span>近1年</span><span>{mgr_rating.get("weighted_score_1y",0)}分</span></div>
          <div class="detail-row"><span>近2年</span><span>{mgr_rating.get("weighted_score_2y",0)}分</span></div>
          <div class="detail-row"><span>近3年</span><span>{mgr_rating.get("weighted_score_3y",0)}分</span></div>
        </div>'''

    # Stock concentration card
    stock_conc = diag.get("stock_concentration", {})
    conc_html = ""
    if stock_conc and stock_conc.get("max_stock"):
        level = stock_conc.get("level", "")
        level_color = "#E53E3E" if level == "偏高" else "#DD6B20" if level == "适中" else "#38A169"
        top5_rows = ""
        for s in stock_conc.get("top5", []):
            top5_rows += f'''<tr><td>{safe_text(s.get("name",""))}</td><td>{fmt_percent(s.get("weight",0))}</td></tr>'''
        conc_html = f'''
        <div class="detail-card chart-half">
          <h3>穿透后个股集中度</h3>
          <div class="detail-row"><span>最高集中度</span><span>{safe_text(stock_conc.get("max_stock",""))} ({fmt_percent(stock_conc.get("max_weight",0))})</span></div>
          <div class="detail-row"><span>集中度等级</span><span class="grade-badge" style="background:{level_color}">{level}</span></div>
          <table class="mini-table"><thead><tr><th>股票</th><th>权重</th></tr></thead><tbody>{top5_rows}</tbody></table>
        </div>'''

    # Fund subscores detail
    subscores = diag.get("fund_subscores_detail", [])
    sub_html = ""
    if subscores:
        sub_data = json.dumps([
            {"name": short_name(s.get("name", s.get("code","")), 8),
             "nhi": s.get("nhi_1y", 0), "sec": s.get("sec_1y", 0),
             "tim": s.get("tim_1y", 0), "sca": s.get("sca_1y", 0)}
            for s in subscores
        ], ensure_ascii=False)
        sub_html = f'''
    <div class="chart-container">
      <div id="chart-subscores" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-subscores');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {sub_data};
      var names = data.map(function(d){{ return d.name; }});
      chart.setOption({{
        title: {{ text: '子维度评分（近1年）', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ trigger: 'axis' }},
        legend: {{ data: ['创新高','择股','择时','规模'], top: 35 }},
        grid: {{ left: 100, right: 20, top: 70, bottom: 30 }},
        xAxis: {{ type: 'value', max: 100 }},
        yAxis: {{ type: 'category', data: names }},
        series: [
          {{ name: '创新高', type: 'bar', stack: 'score', data: data.map(function(d){{ return d.nhi; }}), itemStyle: {{ color: '#0052D9' }} }},
          {{ name: '择股', type: 'bar', stack: 'score', data: data.map(function(d){{ return d.sec; }}), itemStyle: {{ color: '#36A3F7' }} }},
          {{ name: '择时', type: 'bar', stack: 'score', data: data.map(function(d){{ return d.tim; }}), itemStyle: {{ color: '#80B3FF' }} }},
          {{ name: '规模', type: 'bar', stack: 'score', data: data.map(function(d){{ return d.sca; }}), itemStyle: {{ color: '#4D94FF' }} }}
        ]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # Correlation level indicator
    corr_level = diag.get("correlation_level", "")
    if corr_level == '高':
        corr_color = '#E53E3E'
    elif corr_level == '中':
        corr_color = '#DD6B20'
    else:
        corr_color = '#38A169'
    corr_html = f'<div class="diag-suggestion">组合相关性: <span class="grade-badge" style="background:{corr_color}">{corr_level}</span></div>' if corr_level else ''

    return f'''
    <section id="section-diagnosis" class="card-section">
      <h2>账户诊断总览</h2>
      <div class="diag-summary">
        <div class="diag-score">{grade_badge(grade)} <span class="score-num">{score}分</span></div>
        <div class="diag-suggestion">{suggestion}</div>
        {corr_html}
      </div>
      <div class="chart-row">
        {gauge_html}
        {scores_html}
      </div>
      <div class="chart-row">
        {mgr_html}
        {conc_html}
      </div>
      {sub_html}
      {deviation_html}
    </section>'''


def render_performance(data):
    perf = data.get("performance")
    if not perf:
        return ""
    metrics = perf.get("performance_metrics", {})
    mp = perf.get("multi_period_returns", {})
    mdd = perf.get("max_drawdown_detail", {})
    ranking = perf.get("fund_return_ranking", [])
    nav_curve = perf.get("nav_curve", {})
    benchmark_metrics = perf.get("benchmark_metrics", {})
    excess = perf.get("excess_vs_benchmark", {})

    # 8 KPI cards
    kpi_items = [
        ("累计收益", metrics.get("cumulative_return"), True),
        ("年化收益(CAGR)", metrics.get("cagr"), True),
        ("年化波动率", metrics.get("volatility"), False),
        ("最大回撤", metrics.get("max_drawdown"), False),
        ("VaR(95%)", metrics.get("var_95"), False),
        ("CVaR(95%)", metrics.get("cvar_95"), False),
        ("夏普比率", metrics.get("sharpe_ratio"), None),
        ("Sortino", metrics.get("sortino_ratio"), None),
    ]
    kpi_html = '<div class="kpi-grid">'
    for label, val, is_pct in kpi_items:
        if val is None:
            continue
        cls = ""
        display = ""
        if is_pct is True:
            cls = color_class(val)
            display = fmt_percent(val)
        elif is_pct is False:
            display = fmt_percent(val)
        else:
            if isinstance(val, (int, float)) and val > 0:
                cls = "text-up"
            display = fmt_number(val, 4) if abs(float(val)) < 1 else fmt_number(val)
        kpi_html += f'''<div class="kpi-card">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value {cls}">{display}</div>
        </div>'''
    kpi_html += '</div>'

    # Multi-period bar chart
    mp_categories = json.dumps([PERIOD_LABELS.get(k, k) for k, v in mp.items()], ensure_ascii=False)
    mp_values = json.dumps([round(float(v) * 100, 2) for k, v in mp.items()])

    mp_chart = echarts_bar_config(
        'chart-multi-period', '多期收益', mp_categories, mp_values,
        orientation='vertical', value_suffix='%',
        grid={'left': 60, 'right': 20, 'top': 50, 'bottom': 30},
        bar_max_width=40,
        color_fn="function(params) { return params.value >= 0 ? '#E53E3E' : '#38A169'; }"
    )

    # Nav curve chart (portfolio vs benchmark)
    nav_chart = ""
    if nav_curve and nav_curve.get("dates"):
        nc_dates = json.dumps(nav_curve["dates"])
        nc_portfolio = json.dumps(nav_curve.get("portfolio_nav", []))
        nc_benchmark = json.dumps(nav_curve.get("benchmark_nav", []))
        nc_bench_name = safe_text(nav_curve.get("benchmark_name", "基准"))
        nav_chart = echarts_line_config(
            'chart-nav-curve', '净值曲线', nc_dates,
            [
                {"name": "组合净值", "data": nc_portfolio},
                {"name": nc_bench_name, "data": nc_benchmark, "line_type": "dashed", "color": "#DD6B20"},
            ],
            x_axis_label={"fontSize": 10, "rotate": 30},
            y_scale=True
        )

    # Benchmark comparison table
    bench_table = ""
    if benchmark_metrics:
        bm = benchmark_metrics
        rows = f'''
          <tr><td>累计收益</td><td class="{color_class(metrics.get('cumulative_return',0))}">{fmt_percent(metrics.get('cumulative_return',0))}</td><td class="{color_class(bm.get('cumulative_return',0))}">{fmt_percent(bm.get('cumulative_return',0))}</td></tr>
          <tr><td>年化收益</td><td class="{color_class(metrics.get('cagr',0))}">{fmt_percent(metrics.get('cagr',0))}</td><td class="{color_class(bm.get('cagr',0))}">{fmt_percent(bm.get('cagr',0))}</td></tr>
          <tr><td>最大回撤</td><td>{fmt_percent(metrics.get('max_drawdown',0))}</td><td>{fmt_percent(bm.get('max_drawdown',0))}</td></tr>'''
        if excess:
            rows += f'''<tr><td>超额收益</td><td colspan="2" class="{color_class(excess.get('return_diff',0))}">{fmt_percent(excess.get('return_diff',0))}</td></tr>'''
        bench_table = f'''
    <div class="detail-card chart-half">
      <h3>组合 vs {safe_text(bm.get('name','基准'))}</h3>
      <table class="data-table">
        <thead><tr><th>指标</th><th>组合</th><th>基准</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>'''

    # Max drawdown detail card
    mdd_html = ""
    if mdd:
        mdd_html = f'''
        <div class="detail-card chart-half">
          <h3>最大回撤详情</h3>
          <div class="detail-row"><span>回撤幅度</span><span class="text-down">{fmt_percent(mdd.get("max_drawdown",0))}</span></div>
          <div class="detail-row"><span>峰值</span><span>{fmt_number(mdd.get("peak_value",0),4)}</span></div>
          <div class="detail-row"><span>谷值</span><span>{fmt_number(mdd.get("trough_value",0),4)}</span></div>
          <div class="detail-row"><span>起始日</span><span>{safe_text(mdd.get("start_date",""))}</span></div>
          <div class="detail-row"><span>结束日</span><span>{safe_text(mdd.get("end_date",""))}</span></div>
        </div>'''

    # Fund ranking horizontal bar
    rank_categories = json.dumps([short_name(f.get("name", f.get("code", "")), 10) for f in ranking][::-1], ensure_ascii=False)
    rank_values = json.dumps([round(float(f.get("return", 0)) * 100, 2) for f in ranking][::-1])
    rank_full_names = json.dumps([safe_text(f.get("name", f.get("code", ""))) for f in ranking][::-1], ensure_ascii=False)

    rank_chart = echarts_bar_config(
        'chart-fund-ranking', '基金收益排名', rank_categories, rank_values,
        orientation='horizontal', value_suffix='%',
        grid={'left': 140, 'right': 50, 'top': 50, 'bottom': 20},
        bar_max_width=14,
        color_fn="function(params) { return params.value >= 0 ? '#E53E3E' : '#38A169'; }",
        full_names=rank_full_names,
        category_axis_label={"fontSize": 10, "width": 120, "overflow": "truncate", "ellipsis": "…"}
    )

    return f'''
    <section id="section-performance" class="card-section">
      <h2>收益风险表现</h2>
      {kpi_html}
      {nav_chart}
      <div class="chart-row">
        {bench_table}
        {mdd_html}
      </div>
      {mp_chart}
      {rank_chart}
    </section>'''


def render_allocation(data):
    alloc = data.get("allocation")
    if not alloc:
        return ""
    asset_alloc = alloc.get("asset_allocation", [])
    country_alloc = alloc.get("country_allocation", [])
    industry = alloc.get("industry_allocation", [])
    top_holdings = alloc.get("top_holdings", [])
    style_tags = alloc.get("holding_style_tags", {})
    conc = alloc.get("concentration_risk", {})

    # Asset allocation pie
    asset_data = json.dumps([
        {"name": ASSET_NAMES.get(a.get("type", ""), a.get("type", "")), "value": round(float(a.get("weight", 0)) * 100, 2)}
        for a in asset_alloc
    ], ensure_ascii=False)

    asset_chart = f'''
    <div class="chart-container chart-half">
      <div id="chart-asset-alloc" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-asset-alloc');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {asset_data};
      chart.setOption({{
        title: {{ text: '资产配置', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ trigger: 'item', formatter: '{{b}}: {{c}}% ({{d}}%)' }},
        legend: {{ bottom: 5, type: 'scroll' }},
        color: {json.dumps(CHART_COLORS)},
        series: [{{
          type: 'pie', radius: ['35%','60%'], center: ['50%','48%'],
          label: {{ formatter: '{{b}}\\n{{c}}%' }},
          data: data
        }}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # Country allocation pie
    country_data = json.dumps([
        {"name": REGION_NAMES.get(c.get("region", ""), c.get("region", "")), "value": round(float(c.get("weight", 0)) * 100, 2)}
        for c in country_alloc
    ], ensure_ascii=False)

    country_chart = f'''
    <div class="chart-container chart-half">
      <div id="chart-country-alloc" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-country-alloc');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {country_data};
      chart.setOption({{
        title: {{ text: '国家/地区分布', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ trigger: 'item', formatter: '{{b}}: {{c}}%' }},
        legend: {{ bottom: 5, type: 'scroll' }},
        color: {json.dumps(CHART_COLORS)},
        series: [{{
          type: 'pie', radius: ['35%','60%'], center: ['50%','48%'],
          label: {{ formatter: '{{b}}\\n{{c}}%' }},
          data: data
        }}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # Industry bar chart
    ind_categories = json.dumps([safe_text(i.get("industry", "")) for i in industry[:15]][::-1], ensure_ascii=False)
    ind_values = json.dumps([round(float(i.get("weight", 0)) * 100, 2) for i in industry[:15]][::-1])

    ind_chart = echarts_bar_config(
        'chart-industry', '行业配置 (Top15)', ind_categories, ind_values,
        orientation='horizontal', value_suffix='%', colors=json.dumps(["#0052D9"]),
        grid={'left': 100, 'right': 40, 'top': 50, 'bottom': 20},
        bar_max_width=16,
        category_axis_label={"fontSize": 11}
    )

    # Top holdings treemap
    holdings_data = json.dumps([
        {"name": safe_text(h.get("stock", "")), "value": round(float(h.get("weight", 0)) * 100, 2)}
        for h in top_holdings[:15]
    ], ensure_ascii=False)

    holdings_chart = f'''
    <div class="chart-container">
      <div id="chart-top-holdings" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-top-holdings');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {holdings_data};
      chart.setOption({{
        title: {{ text: '重仓股 (Top15)', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ formatter: '{{b}}: {{c}}%' }},
        series: [{{
          type: 'treemap', width: '90%', height: '75%', top: 45,
          roam: false, nodeClick: false,
          breadcrumb: {{ show: false }},
          label: {{ show: true, formatter: '{{b}}\\n{{c}}%', fontSize: 11 }},
          itemStyle: {{ borderColor: '#fff', borderWidth: 2, gapWidth: 2 }},
          levels: [{{
            itemStyle: {{ borderColor: '#fff', borderWidth: 2, gapWidth: 2 }}
          }}],
          data: data.map(function(d) {{
            return {{ name: d.name, value: d.value,
              itemStyle: {{ color: '#0052D9' }} }};
          }})
        }}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # Style tags pie
    style_data = json.dumps([
        {"name": k, "value": round(float(v) * 100, 2)}
        for k, v in style_tags.items()
    ], ensure_ascii=False)

    style_chart = f'''
    <div class="chart-container chart-half">
      <div id="chart-style-tags" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-style-tags');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {style_data};
      chart.setOption({{
        title: {{ text: '持仓风格', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ trigger: 'item', formatter: '{{b}}: {{c}}%' }},
        color: ['#0052D9','#36A3F7','#80B3FF'],
        series: [{{
          type: 'pie', radius: ['35%','60%'], center: ['50%','55%'],
          label: {{ formatter: '{{b}}\\n{{c}}%' }},
          data: data
        }}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # Concentration card
    conc_html = ""
    if conc:
        conc_html = f'''
        <div class="detail-card chart-half">
          <h3>集中度分析</h3>
          <div class="detail-row"><span>HHI指数</span><span>{fmt_number(conc.get('hhi',0),4)}</span></div>
          <div class="detail-row"><span>集中度等级</span><span class="grade-badge" style="background:{'#E53E3E' if conc.get('level')=='高' else '#DD6B20' if conc.get('level')=='中' else '#38A169'}">{conc.get('level','')}</span></div>
          {"<div class='alert-item alert-warn'>" + safe_text(conc.get("warning","")) + "</div>" if conc.get("warning") else ""}
        </div>'''

    return f'''
    <section id="section-allocation" class="card-section">
      <h2>组合配置诊断</h2>
      <div class="chart-row">
        {asset_chart}
        {country_chart}
      </div>
      {ind_chart}
      {holdings_chart}
      <div class="chart-row">
        {style_chart}
        {conc_html}
      </div>
    </section>'''


def render_correlation(data):
    corr = data.get("correlation")
    if not corr:
        return ""
    cm = corr.get("correlation_matrix", {})
    fund_codes = cm.get("funds", [])
    matrix = cm.get("matrix", [])
    avg_corr = corr.get("average_pairwise_correlation", 0)
    high_pairs = corr.get("high_correlation_pairs", [])
    groups = corr.get("groups", [])
    suggestion = safe_text(corr.get("rebalancing_suggestion", ""))

    # Heatmap data
    heatmap_data = []
    fund_names = []
    fund_full_names = []
    # Try to get names from evaluation or overview
    overview_holdings = data.get("overview", {}).get("holdings_detail", [])
    name_map = {h.get("code", ""): h.get("name", "") for h in overview_holdings}
    for code in fund_codes:
        full = name_map.get(code, code)
        fund_full_names.append(full)
        fund_names.append(short_name(full, 6))

    for i, row in enumerate(matrix):
        for j, val in enumerate(row):
            heatmap_data.append([j, i, round(float(val), 2)])

    hm_data = json.dumps(heatmap_data)
    hm_names = json.dumps([safe_text(n) for n in fund_names], ensure_ascii=False)
    hm_full = json.dumps([safe_text(n) for n in fund_full_names], ensure_ascii=False)

    heatmap_chart = f'''
    <div class="chart-container heatmap-wrap">
      <div id="chart-correlation-heatmap" class="echarts-box echarts-tall"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-correlation-heatmap');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {hm_data};
      var names = {hm_names};
      var fullNames = {hm_full};
      var n = names.length;
      chart.setOption({{
        title: {{ text: '相关系数热力图', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ formatter: function(p){{ return fullNames[p.value[1]] + ' vs ' + fullNames[p.value[0]] + ': ' + p.value[2]; }} }},
        grid: {{ left: 100, right: 30, top: 50, bottom: 100 }},
        xAxis: {{ type: 'category', data: names, axisLabel: {{ rotate: 45, fontSize: 9, width: 60, overflow: 'truncate' }}, splitArea: {{ show: true }} }},
        yAxis: {{ type: 'category', data: names, axisLabel: {{ fontSize: 9, width: 60, overflow: 'truncate' }}, splitArea: {{ show: true }} }},
        visualMap: {{ min: -1, max: 1, calculable: true, orient: 'horizontal', left: 'center', bottom: 5,
          inRange: {{ color: ['#38A169','#F7F7F7','#E53E3E'] }} }},
        series: [{{
          type: 'heatmap', data: data,
          label: {{ show: n <= 10, fontSize: 9, formatter: function(p){{ return p.value[2]; }} }},
          emphasis: {{ itemStyle: {{ shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.3)' }} }}
        }}]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # High correlation cards
    pairs_html = ""
    if high_pairs:
        pair_items = ""
        for p in high_pairs:
            pair_items += f'''<div class="alert-item alert-warn">
              {safe_text(p.get("fund1_name",""))} ↔ {safe_text(p.get("fund2_name",""))}
              相关系数: {p.get("correlation",0)}
            </div>'''
        pairs_html = f'<div class="alert-group">{pair_items}</div>'

    groups_html = ""
    if groups:
        grp_items = ""
        for g in groups:
            names_list = ", ".join(safe_text(n) for n in g.get("fund_names", g.get("funds", [])))
            grp_items += f'''<div class="detail-card">
              <h4>高相关组</h4>
              <p>{names_list}</p>
              <p>组内平均相关性: {g.get("average_correlation",0)}</p>
            </div>'''
        groups_html = grp_items

    return f'''
    <section id="section-correlation" class="card-section">
      <h2>相关性分析</h2>
      <div class="kpi-grid kpi-grid-3">
        <div class="kpi-card">
          <div class="kpi-label">平均两两相关性</div>
          <div class="kpi-value">{fmt_number(avg_corr, 4)}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">基金数量</div>
          <div class="kpi-value">{len(fund_codes)}</div>
        </div>
        <div class="kpi-card">
          <div class="kpi-label">高相关对数</div>
          <div class="kpi-value">{len(high_pairs)}</div>
        </div>
      </div>
      {heatmap_chart}
      {pairs_html}
      {groups_html}
      <div class="suggestion-box"><p>{suggestion}</p></div>
    </section>'''


def render_evaluation(data):
    ev = data.get("evaluation")
    if not ev:
        return ""
    evaluations = ev.get("fund_evaluations", [])
    index_vals = ev.get("index_fund_valuations", [])

    cards_html = ""
    for f in evaluations:
        mp = f.get("multi_period_returns", {})
        top5 = f.get("top_5_holdings", [])
        grade = f.get("grade", "")
        score = f.get("comprehensive_score", 0)
        subscores = f.get("subscores", {})
        mgr_rating = f.get("manager_rating", {})
        announcement = f.get("announcement", {})
        recommendation = f.get("recommendation", "")
        rec_reason = f.get("recommendation_reason", "")

        # Mini bar chart via CSS
        mp_bars = ""
        for period_key in ["1m", "3m", "6m", "1y", "2y", "3y", "since_inception"]:
            val = mp.get(period_key)
            if val is None:
                continue
            label = PERIOD_LABELS.get(period_key, period_key)
            pct = round(float(val) * 100, 2)
            bar_w = min(abs(pct) * 2, 100)
            bar_color = "#E53E3E" if pct >= 0 else "#38A169"
            mp_bars += f'''<div class="mini-bar-row">
              <span class="mini-bar-label">{label}</span>
              <div class="mini-bar-track">
                <div class="mini-bar-fill" style="width:{bar_w:.1f}%;background:{bar_color}"></div>
              </div>
              <span class="mini-bar-val {color_class(val)}">{pct}%</span>
            </div>'''

        # Subscores mini bar
        sub_bars = ""
        sub_labels = {"nhi_1y": "创新高", "sec_1y": "择股", "tim_1y": "择时", "sca_1y": "规模"}
        if subscores:
            for key, label in sub_labels.items():
                val = subscores.get(key, 0)
                bar_w = min(abs(val), 100)
                sub_bars += f'''<div class="mini-bar-row">
                  <span class="mini-bar-label" style="width:40px">{label}</span>
                  <div class="mini-bar-track">
                    <div class="mini-bar-fill" style="width:{bar_w:.1f}%;background:#0052D9"></div>
                  </div>
                  <span class="mini-bar-val">{val}</span>
                </div>'''

        # Manager rating tag
        mgr_tag = ""
        if mgr_rating:
            mgr_1y = mgr_rating.get("overall_1y", 0)
            mgr_tag = f'<span class="risk-tag" style="background:#E6F0FF;color:#0052D9">经理评分 {mgr_1y}</span>'

        # Announcement alert
        ann_html = ""
        if announcement and announcement.get("has_negative"):
            events = announcement.get("negative_events", [])
            ev_text = "、".join(str(e) for e in events[:3])
            ann_html = f'''<div class="alert-item alert-warn">公告预警: {safe_text(ev_text)}</div>'''
        elif announcement and announcement.get("summary"):
            ann_html = f'''<div class="eval-meta"><span style="color:#718096;font-size:11px">{safe_text(announcement["summary"])}</span></div>'''

        # Recommendation tag
        rec_tag = ""
        rec_colors = {
            "保留": "#38A169", "重点保留": "#38A169", "继续持有": "#3182CE",
            "观察": "#DD6B20", "替换": "#E53E3E", "部分替换": "#E53E3E",
        }
        if recommendation:
            rec_color = rec_colors.get(recommendation, "#718096")
            rec_tag = f'<span class="rec-tag" style="background:{rec_color};color:#fff;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700">{safe_text(recommendation)}</span>'

        # Top 5 holdings mini table
        t5_rows = ""
        for h in top5[:5]:
            t5_rows += f'''<tr>
              <td>{safe_text(h.get("stock",""))}</td>
              <td>{fmt_percent(h.get("weight",0))}</td>
            </tr>'''
        t5_table = ""
        if t5_rows:
            t5_table = f'''<table class="mini-table">
              <thead><tr><th>重仓股</th><th>占比</th></tr></thead>
              <tbody>{t5_rows}</tbody>
            </table>'''

        fund_full_name = safe_text(f.get("name",""))
        cards_html += f'''
        <div class="eval-card">
          <div class="eval-header">
            <span class="eval-name" title="{fund_full_name}">{fund_full_name}</span>
            {grade_badge(grade)}
            {rec_tag}
          </div>
          <div class="eval-body">
            <div class="eval-meta">
              <span class="eval-score">得分: {score}</span>
              <span class="eval-type">{safe_text(f.get("fund_type",""))}</span>
              <span class="eval-mgr">{safe_text(f.get("manager",""))}</span>
              {mgr_tag}
            </div>
            <div class="eval-risks">
              <span class="risk-tag">回撤 {fmt_percent(f.get("max_drawdown",0))}</span>
              <span class="risk-tag">波动 {fmt_percent(f.get("volatility",0))}</span>
              <span class="risk-tag">夏普 {fmt_number(f.get("sharpe_ratio",0),2)}</span>
            </div>
            {ann_html}
            {f'<div class="eval-meta" style="font-size:11px;color:#718096">{safe_text(rec_reason)}</div>' if rec_reason else ''}
            {sub_bars}
            <div class="eval-mp">{mp_bars}</div>
            {t5_table}
          </div>
        </div>'''

    # Index fund table
    idx_table = ""
    if index_vals:
        idx_rows = ""
        for iv in index_vals:
            pe = iv.get("pe_percentile", 50)
            val_label = iv.get("valuation", "适中")
            val_color = "#38A169" if "低" in val_label else "#E53E3E" if "高" in val_label else "#718096"
            idx_rows += f'''<tr>
              <td>{safe_text(iv.get("name",""))}</td>
              <td>{fmt_percent(iv.get("excess_return",0))}</td>
              <td>{pe}%</td>
              <td><span style="color:{val_color};font-weight:600">{safe_text(val_label)}</span></td>
              <td>{safe_text(iv.get("suggestion",""))}</td>
            </tr>'''
        idx_table = f'''
        <h3>指数基金估值</h3>
        <div class="table-wrap">
          <table class="data-table">
            <thead><tr><th>基金</th><th>超额收益</th><th>PE百分位</th><th>估值</th><th>建议</th></tr></thead>
            <tbody>{idx_rows}</tbody>
          </table>
        </div>'''

    return f'''
    <section id="section-evaluation" class="card-section">
      <h2>单只基金评价</h2>
      <div class="eval-grid">
        {cards_html}
      </div>
      {idx_table}
    </section>'''


def render_rebalance(data):
    reb = data.get("rebalance")
    if not reb:
        return ""
    comparison = reb.get("allocation_comparison", [])
    reduce_sug = reb.get("reduce_suggestions", [])
    increase_sug = reb.get("increase_suggestions", [])
    expected = safe_text(reb.get("expected_improvement", ""))

    # Butterfly chart
    butterfly_data = json.dumps([
        {
            "name": ASSET_NAMES.get(c.get("asset", ""), c.get("asset", "")),
            "current": round(float(c.get("current", 0)) * 100, 1),
            "target": round(float(c.get("target", 0)) * 100, 1),
        }
        for c in comparison
    ], ensure_ascii=False)

    butterfly_chart = f'''
    <div class="chart-container">
      <div id="chart-rebalance-compare" class="echarts-box"></div>
    </div>
    <script>
    (function(){{
      var el = document.getElementById('chart-rebalance-compare');
      if(!el) return;
      var chart = echarts.init(el);
      var data = {butterfly_data};
      var cats = data.map(function(d){{ return d.name; }});
      chart.setOption({{
        title: {{ text: '当前 vs 目标配置', left: 'center', top: 10, textStyle: {{ fontSize: 14 }} }},
        tooltip: {{ trigger: 'axis' }},
        legend: {{ data: ['当前','目标'], top: 35 }},
        grid: {{ left: 60, right: 20, top: 70, bottom: 30 }},
        xAxis: {{ type: 'category', data: cats }},
        yAxis: {{ type: 'value', axisLabel: {{ formatter: '{{value}}%' }} }},
        series: [
          {{ name: '当前', type: 'bar', data: data.map(function(d){{ return d.current; }}),
             itemStyle: {{ color: '#0052D9' }}, barMaxWidth: 35 }},
          {{ name: '目标', type: 'bar', data: data.map(function(d){{ return d.target; }}),
             itemStyle: {{ color: '#B3D1FF' }}, barMaxWidth: 35 }}
        ]
      }});
      window._charts.push(chart);
    }})();
    </script>'''

    # Suggestion cards
    sug_cards = ""
    for s in reduce_sug:
        sug_cards += f'''<div class="sug-card sug-reduce">
          <h4>减仓建议 - {ASSET_NAMES.get(s.get("asset",""), s.get("asset",""))}</h4>
          <p>超配: {fmt_percent(s.get("overweight",0))}</p>
          <p>{safe_text(s.get("suggested_action",""))}</p>
        </div>'''

    for s in increase_sug:
        sug_cards += f'''<div class="sug-card sug-increase">
          <h4>加仓建议 - {ASSET_NAMES.get(s.get("asset",""), s.get("asset",""))}</h4>
          <p>低配: {fmt_percent(s.get("underweight",0))}</p>
          <p>{safe_text(s.get("suggested_action",""))}</p>
        </div>'''

    # Fund replacement suggestions table
    replacement_html = ""
    replacements = reb.get("fund_replacement_suggestions", [])
    if replacements:
        rep_rows = ""
        for r in replacements:
            action_color = "#E53E3E" if r.get("action") == "替换" else "#DD6B20"
            rep_rows += f'''<tr>
              <td>{safe_text(r.get("name",""))}</td>
              <td>{r.get("score","")}</td>
              <td><span style="color:{action_color};font-weight:600">{safe_text(r.get("action",""))}</span></td>
              <td>{safe_text(r.get("reason",""))}</td>
            </tr>'''
        replacement_html = f'''
    <h3>基金替换建议</h3>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>基金</th><th>评分</th><th>操作</th><th>理由</th></tr></thead>
        <tbody>{rep_rows}</tbody>
      </table>
    </div>'''

    # Recommended funds
    recommended_html = ""
    recommended = reb.get("recommended_funds", [])
    if recommended:
        rec_rows = ""
        for r in recommended:
            rec_rows += f'''<tr>
              <td>{safe_text(r.get("name",""))}</td>
              <td>{r.get("score","")}</td>
              <td>{safe_text(r.get("brief",""))}</td>
            </tr>'''
        recommended_html = f'''
    <h3>推荐核心持仓</h3>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>基金</th><th>评分</th><th>说明</th></tr></thead>
        <tbody>{rec_rows}</tbody>
      </table>
    </div>'''

    # Batch schedule
    batch_html = ""
    batches = reb.get("batch_schedule", [])
    if batches:
        batch_rows = ""
        for b in batches:
            funds_str = "、".join(safe_text(f) for f in b.get("funds", []))
            batch_rows += f'''<tr>
              <td>第{b.get("batch",1)}批</td>
              <td>{safe_text(b.get("time",""))}</td>
              <td>{funds_str}</td>
              <td>{safe_text(b.get("amount",""))}</td>
            </tr>'''
        batch_html = f'''
    <h3>替换批次安排</h3>
    <div class="table-wrap">
      <table class="data-table">
        <thead><tr><th>批次</th><th>时间</th><th>基金</th><th>数量</th></tr></thead>
        <tbody>{batch_rows}</tbody>
      </table>
    </div>'''

    # Post-rebalance improvement
    post_reb = reb.get("post_rebalance", {})
    post_html = ""
    if post_reb:
        post_html = f'''
    <div class="detail-card">
      <h3>调仓后预期改善</h3>
      <div class="detail-row"><span>相关性改善</span><span>{safe_text(post_reb.get("correlation_improvement",""))}</span></div>
      <div class="detail-row"><span>预期效果</span><span>{safe_text(post_reb.get("expected_improvement",""))}</span></div>
    </div>'''

    return f'''
    <section id="section-rebalance" class="card-section">
      <h2>调仓建议</h2>
      {butterfly_chart}
      <div class="sug-grid">
        {sug_cards}
      </div>
      {replacement_html}
      {recommended_html}
      {batch_html}
      {post_html}
      <div class="suggestion-box"><p>{expected}</p></div>
    </section>'''


def render_risk(data):
    risk = data.get("risk")
    if not risk:
        return ""
    risk_level = risk.get("risk_level", "")
    scenarios = risk.get("scenario_analysis", [])
    market_risks = risk.get("market_risks", [])
    liquidity_risks = risk.get("liquidity_risks", [])
    mdd_period = risk.get("max_drawdown_period", {})

    level_color = "#38A169" if risk_level == "低" else "#DD6B20" if risk_level == "中" else "#E53E3E"

    # Risk level badge
    level_html = f'''<div class="risk-level-badge" style="background:{level_color}">风险等级: {risk_level}</div>'''

    # Scenario cards
    scenario_cards = ""
    for s in scenarios:
        ret = float(s.get("expected_return", 0))
        dd = float(s.get("expected_drawdown", 0))
        prob = safe_text(s.get("probability", ""))
        ret_w = min(abs(ret) * 600, 100)
        dd_w = min(abs(dd) * 600, 100)
        ret_color = "#E53E3E" if ret > 0 else "#38A169"
        dd_color = "#38A169"
        scenario_cards += f'''
        <div class="scenario-card">
          <h4>{safe_text(s.get("scenario",""))}</h4>
          <div class="scenario-prob">{prob}</div>
          <div class="scenario-metric">
            <span>预期收益</span>
            <div class="progress-bar"><div class="progress-fill" style="width:{ret_w:.1f}%;background:{ret_color}"></div></div>
            <span class="{color_class(ret)}">{fmt_percent(s.get('expected_return',0))}</span>
          </div>
          <div class="scenario-metric">
            <span>预期回撤</span>
            <div class="progress-bar"><div class="progress-fill" style="width:{dd_w:.1f}%;background:{dd_color}"></div></div>
            <span class="text-down">{fmt_percent(s.get('expected_drawdown',0))}</span>
          </div>
        </div>'''

    # Risk lists
    mr_html = ""
    if market_risks:
        mr_items = "".join(f"<li>{safe_text(r)}</li>" for r in market_risks)
        mr_html = f'''<div class="risk-list"><h4>市场风险</h4><ul>{mr_items}</ul></div>'''

    lr_html = ""
    if liquidity_risks:
        lr_items = "".join(f"<li>{safe_text(r)}</li>" for r in liquidity_risks)
        lr_html = f'''<div class="risk-list"><h4>流动性风险</h4><ul>{lr_items}</ul></div>'''

    # Max drawdown period
    mdd_html = ""
    if mdd_period:
        mdd_html = f'''<div class="detail-card">
          <h3>最大回撤时间区间</h3>
          <div class="detail-row"><span>起始日</span><span>{safe_text(mdd_period.get("start_date",""))}</span></div>
          <div class="detail-row"><span>结束日</span><span>{safe_text(mdd_period.get("end_date",""))}</span></div>
        </div>'''

    return f'''
    <section id="section-risk" class="card-section">
      <h2>风险提示</h2>
      {level_html}
      <div class="scenario-grid">
        {scenario_cards}
      </div>
      <div class="chart-row">
        {mr_html}
        {lr_html}
      </div>
      {mdd_html}
    </section>'''


def render_footer(data):
    footer = data.get("report_footer", {})
    disclaimer = safe_text(footer.get("disclaimer", "本报告仅供参考，不构成投资建议。基金有风险，投资需谨慎。"))
    return f'''
    <footer class="report-footer">
      <p class="disclaimer">{disclaimer}</p>
    </footer>'''


def render_summary(data):
    summary = data.get("summary")
    if not summary:
        return ""
    findings = summary.get("core_findings", [])
    risks = summary.get("key_risks", [])
    suggestions = summary.get("optimization_suggestions", [])
    overall = safe_text(summary.get("overall_assessment", ""))

    findings_html = ""
    for f_item in findings:
        findings_html += f'''<li>{safe_text(f_item)}</li>'''

    risks_html = ""
    for r in risks:
        risks_html += f'''<li>{safe_text(r)}</li>'''

    suggestions_html = ""
    for s in suggestions:
        suggestions_html += f'''<li>{safe_text(s)}</li>'''

    return f'''
    <section id="section-summary" class="card-section">
      <h2>报告总结</h2>
      <div class="suggestion-box" style="margin-bottom:16px">
        <p style="font-weight:700">{overall}</p>
      </div>
      <div class="chart-row">
        <div class="detail-card chart-half" style="border-left:4px solid #3182CE">
          <h3>核心发现</h3>
          <ul style="padding-left:20px;font-size:13px">{findings_html}</ul>
        </div>
        <div class="detail-card chart-half" style="border-left:4px solid #E53E3E">
          <h3>关键风险</h3>
          <ul style="padding-left:20px;font-size:13px">{risks_html}</ul>
        </div>
      </div>
      <div class="detail-card" style="border-left:4px solid #38A169">
        <h3>优化建议</h3>
        <ul style="padding-left:20px;font-size:13px">{suggestions_html}</ul>
      </div>
    </section>'''


# ============================================================
# 侧边导航
# ============================================================

def render_nav():
    nav_items = [
        ("#section-diagnosis", "诊断总览"),
        ("#section-overview", "持仓概览"),
        ("#section-performance", "收益风险"),
        ("#section-risk", "风险提示"),
        ("#section-allocation", "配置诊断"),
        ("#section-correlation", "相关性"),
        ("#section-evaluation", "基金评价"),
        ("#section-rebalance", "调仓建议"),
        ("#section-summary", "报告总结"),
    ]
    items_html = "".join(f'<li><a href="{href}">{label}</a></li>' for href, label in nav_items)
    return f'''
    <nav class="sidebar" id="sidebar">
      <div class="sidebar-brand">诊断报告</div>
      <ul class="nav-list">{items_html}</ul>
    </nav>
    <div class="sidebar-backdrop" id="sidebarBackdrop"></div>
    <button class="menu-toggle" id="menuToggle">&#9776;</button>'''


# ============================================================
# 完整 HTML 组装
# ============================================================

def build_html(data):
    """构建完整的 HTML 报告。"""
    # 输入数据验证
    if not isinstance(data, dict):
        raise ValueError("输入数据必须是字典类型")

    # 验证必要字段
    required_sections = ["report_header"]
    for section in required_sections:
        if section not in data:
            print(f"警告: 缺少报告章节 '{section}'", file=sys.stderr)

    body_content = ""
    body_content += render_header(data)
    body_content += render_diagnosis(data)
    body_content += render_overview(data)
    body_content += render_performance(data)
    body_content += render_risk(data)
    body_content += render_allocation(data)
    body_content += render_correlation(data)
    body_content += render_evaluation(data)
    body_content += render_rebalance(data)
    body_content += render_summary(data)
    body_content += render_footer(data)

    nav_html = render_nav()

    report_json = json.dumps(data, ensure_ascii=False)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>基金账户诊断报告</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"></script>
<script>
if (typeof echarts === 'undefined') {{
    document.addEventListener('DOMContentLoaded', function() {{
        var charts = document.querySelectorAll('[id^="chart-"]');
        charts.forEach(function(el) {{
            el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#999;font-size:14px;">图表库加载失败，请检查网络连接后刷新页面</div>';
        }});
    }});
}}
</script>
<style>
:root {{
  --brand-50: #E6F0FF; --brand-100: #B3D1FF; --brand-200: #80B3FF;
  --brand-300: #4D94FF; --brand-400: #1A76FF; --brand-500: #0052D9;
  --brand-600: #0041AD; --brand-700: #003182;
  --bg: #F5F7FA; --card-bg: #FFFFFF; --text: #1A202C; --text-sec: #718096;
  --red: #E53E3E; --green: #38A169; --orange: #DD6B20; --purple: #805AD5;
  --font: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif;
  --radius: 10px; --shadow: 0 2px 8px rgba(0,0,0,0.06);
  --sidebar-w: 180px;
}}
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
html {{ scroll-behavior: smooth; }}
body {{ font-family: var(--font); background: var(--bg); color: var(--text); line-height: 1.6; }}

/* Sidebar */
.sidebar {{
  position: fixed; top: 0; left: 0; width: var(--sidebar-w); height: 100vh;
  background: #fff; border-right: 1px solid #E2E8F0; z-index: 100;
  padding: 20px 0; overflow-y: auto;
  transition: transform 0.3s;
}}
.sidebar-brand {{
  font-size: 16px; font-weight: 700; color: var(--brand-500);
  padding: 0 20px 16px; border-bottom: 1px solid #E2E8F0; margin-bottom: 8px;
}}
.nav-list {{ list-style: none; }}
.nav-list li a {{
  display: block; padding: 10px 20px; font-size: 13px; color: var(--text-sec);
  text-decoration: none; transition: all 0.2s;
}}
.nav-list li a:hover {{ color: var(--brand-500); background: var(--brand-50); }}
.menu-toggle {{
  display: none; position: fixed; top: 12px; left: 12px; z-index: 200;
  background: var(--brand-500); color: #fff; border: none; border-radius: 6px;
  width: 36px; height: 36px; font-size: 18px; cursor: pointer;
}}
/* Mobile backdrop */
.sidebar-backdrop {{
  display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.3); z-index: 90;
}}
.sidebar-backdrop.show {{ display: block; }}

/* Main */
main {{
  margin-left: var(--sidebar-w); max-width: 1380px; margin-right: auto;
  padding: 20px 24px 60px;
}}

/* Hero */
.hero {{
  background: linear-gradient(135deg, var(--brand-500), var(--brand-400));
  color: #fff; border-radius: var(--radius); padding: 32px; margin-bottom: 24px;
}}
.hero h1 {{ font-size: 24px; margin-bottom: 12px; }}
.hero-meta {{ display: flex; flex-wrap: wrap; gap: 16px; font-size: 13px; opacity: 0.9; }}
.api-ok {{ color: #C6F6D5; }} .api-err {{ color: #FED7D7; }}

/* Cards / Sections */
.card-section {{
  background: var(--card-bg); border-radius: var(--radius); padding: 24px;
  margin-bottom: 24px; box-shadow: var(--shadow);
  overflow: hidden;
}}
.card-section h2 {{
  font-size: 18px; color: var(--brand-500); margin-bottom: 16px;
  padding-bottom: 8px; border-bottom: 2px solid var(--brand-50);
}}

/* KPI Grid */
.kpi-grid {{
  display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 20px;
}}
.kpi-grid-3 {{ grid-template-columns: repeat(3, 1fr); }}
.kpi-card {{
  background: var(--bg); border-radius: 8px; padding: 14px 16px; text-align: center;
}}
.kpi-label {{ font-size: 12px; color: var(--text-sec); margin-bottom: 4px; }}
.kpi-value {{ font-size: 20px; font-weight: 700; }}

/* Colors */
.text-up {{ color: var(--red); }} .text-down {{ color: var(--green); }}

/* Grade badge */
.grade-badge {{
  display: inline-block; color: #fff; font-size: 12px; font-weight: 700;
  padding: 2px 10px; border-radius: 12px;
}}

/* Charts — align-items: flex-start prevents stretch on short side panels */
.chart-row {{ display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 16px; align-items: flex-start; }}
.chart-container {{ flex: 1; min-width: 0; min-width: 280px; }}
.chart-half {{ max-width: 50%; flex-basis: calc(50% - 10px); }}
.echarts-box {{ width: 100%; height: 380px; }}
.echarts-tall {{ height: 520px; }}

/* Tables */
.table-wrap {{ overflow-x: auto; -webkit-overflow-scrolling: touch; }}
.data-table {{
  width: 100%; border-collapse: collapse; font-size: 13px;
}}
.data-table th, .data-table td {{
  padding: 10px 12px; text-align: left; border-bottom: 1px solid #E2E8F0;
}}
.data-table th {{ background: var(--bg); color: var(--text-sec); font-weight: 600; white-space: nowrap; }}
.fund-name {{ max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}

/* Alerts */
.alert-group {{ margin-bottom: 16px; }}
.alert-item {{
  padding: 10px 14px; border-radius: 6px; margin-bottom: 8px; font-size: 13px;
  line-height: 1.5;
}}
.alert-warn {{ background: #FFFAF0; border-left: 3px solid var(--orange); color: #7B341E; }}

/* Diagnosis summary */
.diag-summary {{
  display: flex; align-items: center; gap: 16px; margin-bottom: 20px;
  padding: 16px; background: var(--bg); border-radius: 8px; flex-wrap: wrap;
}}
.score-num {{ font-size: 28px; font-weight: 700; }}
.diag-suggestion {{ font-size: 14px; color: var(--text-sec); }}

/* Detail card */
.detail-card {{
  background: var(--bg); border-radius: 8px; padding: 16px; margin-bottom: 16px;
  overflow-wrap: break-word;
}}
.detail-card h3 {{
  font-size: 14px; color: var(--brand-500); margin-bottom: 12px;
}}
.detail-row {{
  display: flex; justify-content: space-between; padding: 6px 0;
  font-size: 13px; border-bottom: 1px solid #E2E8F0;
}}
.detail-row:last-child {{ border-bottom: none; }}

/* Suggestion box */
.suggestion-box {{
  background: var(--brand-50); border-radius: 8px; padding: 14px 18px; margin-top: 16px;
}}
.suggestion-box p {{ font-size: 14px; color: var(--brand-700); }}

/* Evaluation cards */
.eval-grid {{
  display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 16px;
}}
.eval-card {{
  background: var(--bg); border-radius: 8px; overflow: hidden;
  border: 1px solid #E2E8F0;
}}
.eval-header {{
  display: flex; justify-content: space-between; align-items: center;
  padding: 12px 16px; background: #fff; border-bottom: 1px solid #E2E8F0;
  gap: 8px;
}}
.eval-name {{ font-weight: 600; font-size: 14px; flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
.eval-body {{ padding: 12px 16px; }}
.eval-meta {{ display: flex; gap: 10px; font-size: 12px; color: var(--text-sec); margin-bottom: 8px; flex-wrap: wrap; }}
.eval-score {{ font-weight: 600; color: var(--brand-500); }}
.eval-risks {{ display: flex; gap: 6px; margin-bottom: 10px; flex-wrap: wrap; }}
.risk-tag {{
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: #EDF2F7; color: var(--text-sec);
}}
.eval-mp {{ margin-bottom: 8px; }}
.mini-bar-row {{ display: flex; align-items: center; gap: 6px; margin-bottom: 3px; font-size: 11px; }}
.mini-bar-label {{ width: 50px; text-align: right; color: var(--text-sec); flex-shrink: 0; }}
.mini-bar-track {{ flex: 1; height: 8px; background: #EDF2F7; border-radius: 4px; position: relative; overflow: hidden; min-width: 60px; }}
.mini-bar-fill {{ height: 100%; border-radius: 4px; }}
.mini-bar-val {{ width: 55px; font-weight: 600; flex-shrink: 0; }}
.mini-table {{ width: 100%; font-size: 12px; }}
.mini-table th, .mini-table td {{ padding: 4px 8px; text-align: left; border-bottom: 1px solid #EDF2F7; }}
.mini-table th {{ color: var(--text-sec); font-weight: 600; }}

/* Risk */
.risk-level-badge {{
  display: inline-block; color: #fff; font-size: 14px; font-weight: 700;
  padding: 8px 20px; border-radius: 20px; margin-bottom: 20px;
}}
.scenario-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 20px; }}
.scenario-card {{
  background: var(--bg); border-radius: 8px; padding: 16px;
}}
.scenario-card h4 {{ font-size: 14px; margin-bottom: 6px; }}
.scenario-prob {{ font-size: 12px; color: var(--text-sec); margin-bottom: 10px; }}
.scenario-metric {{ display: flex; align-items: center; gap: 8px; margin-bottom: 6px; font-size: 13px; }}
.scenario-metric > span:first-child {{ width: 56px; color: var(--text-sec); font-size: 12px; flex-shrink: 0; }}
.progress-bar {{ flex: 1; height: 8px; background: #EDF2F7; border-radius: 4px; overflow: hidden; min-width: 40px; }}
.progress-fill {{ height: 100%; border-radius: 4px; }}
.risk-list {{ flex: 1; min-width: 0; margin-bottom: 16px; }}
.risk-list h4 {{ font-size: 14px; color: var(--brand-500); margin-bottom: 8px; }}
.risk-list ul {{ padding-left: 20px; font-size: 13px; }}
.risk-list li {{ margin-bottom: 6px; color: var(--text-sec); overflow-wrap: break-word; }}

/* Rebalance suggestions */
.sug-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; margin: 16px 0; }}
.sug-card {{
  padding: 16px; border-radius: 8px; border-left: 4px solid;
}}
.sug-reduce {{ background: #FFF5F5; border-color: var(--red); }}
.sug-increase {{ background: #F0FFF4; border-color: var(--green); }}
.sug-card h4 {{ font-size: 14px; margin-bottom: 8px; }}
.sug-card p {{ font-size: 13px; color: var(--text-sec); margin-bottom: 4px; overflow-wrap: break-word; }}

/* Footer */
.report-footer {{
  text-align: center; padding: 24px; color: var(--text-sec); font-size: 12px;
}}
.disclaimer {{
  background: var(--bg); border-radius: 8px; padding: 14px; max-width: 600px; margin: 0 auto;
}}

/* Responsive */
@media (max-width: 1024px) {{
  .sidebar {{ transform: translateX(-100%); }}
  .sidebar.open {{ transform: translateX(0); }}
  .menu-toggle {{ display: block; }}
  main {{ margin-left: 0; }}
  .kpi-grid {{ grid-template-columns: repeat(2, 1fr); }}
  .chart-half {{ max-width: 100%; flex-basis: 100%; }}
  .scenario-grid {{ grid-template-columns: 1fr; }}
}}
@media (max-width: 768px) {{
  main {{ padding: 56px 12px 40px; }}
  .kpi-grid {{ grid-template-columns: 1fr 1fr; }}
  .eval-grid {{ grid-template-columns: 1fr; }}
  .echarts-box {{ height: 300px; }}
  .echarts-tall {{ height: 400px; }}
  .hero {{ padding: 20px; }}
  .hero h1 {{ font-size: 20px; }}
  .card-section {{ padding: 16px; }}
  .chart-container {{ min-width: 0; }}
  .data-table {{ font-size: 12px; }}
  .data-table th, .data-table td {{ padding: 8px 6px; }}
}}
</style>
</head>
<body>
{nav_html}
<main>
{body_content}
</main>
<script>
window.REPORT_DATA = {report_json};
window._charts = [];
window.addEventListener('load', function() {{
  window.addEventListener('resize', function() {{
    window._charts.forEach(function(c) {{ c.resize(); }});
  }});
  var toggle = document.getElementById('menuToggle');
  var sidebar = document.getElementById('sidebar');
  var backdrop = document.getElementById('sidebarBackdrop');
  function closeSidebar() {{
    sidebar.classList.remove('open');
    if(backdrop) backdrop.classList.remove('show');
    document.body.style.overflow = '';
  }}
  function openSidebar() {{
    sidebar.classList.add('open');
    if(backdrop) backdrop.classList.add('show');
    document.body.style.overflow = 'hidden';
  }}
  if(toggle && sidebar) {{
    toggle.addEventListener('click', function(e) {{
      e.stopPropagation();
      if(sidebar.classList.contains('open')) closeSidebar();
      else openSidebar();
    }});
    if(backdrop) {{
      backdrop.addEventListener('click', closeSidebar);
    }}
    document.addEventListener('click', function(e) {{
      if(!sidebar.contains(e.target) && e.target !== toggle) {{
        closeSidebar();
      }}
    }});
  }}
}});
</script>
</body>
</html>'''


# ============================================================
# 公共入口函数
# ============================================================

def generate_html_from_report(report_data: dict, output_path: str):
    """从报告字典生成HTML文件

    Args:
        report_data: 诊断报告字典
        output_path: 输出HTML文件路径
    """
    html = build_html(report_data)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML报告已保存至: {output_path}")


# ============================================================
# CLI 入口
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="基金账户诊断报告 HTML 生成器")
    parser.add_argument("--input", type=str, required=True, help="输入JSON报告文件路径")
    parser.add_argument("--output", type=str, default="diagnostic_report.html", help="输出HTML文件路径")
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"错误: 文件不存在: {args.input}")
        sys.exit(1)

    # 验证输出路径
    output_dir = os.path.dirname(args.output) or "."
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir, exist_ok=True)
        except OSError as e:
            print(f"错误: 无法创建输出目录 '{output_dir}': {e}", file=sys.stderr)
            sys.exit(1)
    if not os.access(output_dir, os.W_OK):
        print(f"错误: 无写入权限: {output_dir}", file=sys.stderr)
        sys.exit(1)

    with open(args.input, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    generate_html_from_report(report_data, args.output)


if __name__ == "__main__":
    main()
