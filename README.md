# Stock Signal 📈

> 基于 Python 的 A 股辅助决策系统，支持股票筛选、持仓分析、上市公司资讯抓取与可视化看板。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red)
![License](https://img.shields.io/badge/License-MIT-green)
![A-Stock](https://img.shields.io/badge/A股-技术面分析-green)
![Data](https://img.shields.io/badge/数据源-Tushare|AKShare-orange)

<!-- 截图区域（建议尺寸 1200×675） -->
<details>
<summary><b>📸 截图预览（点击展开）</b></summary>

![Dashboard Preview](docs/screenshot-dashboard.png)
*可视化看板 — K线图、均线、信号卡片*

![Radar Chart](docs/screenshot-radar.png)
*多维度评分雷达图*

</details>

---

## ✨ 功能特性

### 🗂️ 今日筛选
从沪市股票中按技术指标打分，输出 Top N 候选股。

| 指标 | 权重 | 说明 |
|:----:|:----:|------|
| 趋势分 | 40% | MA5 > MA10 > MA20 多头排列 |
| 动能分 | 30% | 近 5 日涨幅 |
| 成交量分 | 30% | 量比（当日成交量 vs 近 5 日均量）|

> 当趋势和动能同时较强时，额外乘以放大系数（最高 ×1.5）

### 📊 持仓分析
对自选股给出 **ADD / HOLD / WAIT / EXIT** 四档操作建议，结合多周期均线综合判断。

### 📈 K线可视化
- K线图 + 均线叠加
- 操作信号标注（买入/卖出点）
- 雷达图展示趋势/动能/成交量三维评分
- **A股惯例**：涨红跌绿

### 📰 资讯聚合 🆕
自动爬取东方财富最新公告/新闻，在持仓页和筛选结果中同步展示，支持手动刷新。

### ⚙️ 数据源
- **主数据源**：Tushare Pro（需 Token）
- **备用数据源**：AKShare（免费，无需 Token）
- 首次运行自动引导配置

---

## 🚀 快速开始

### 环境要求
- Python 3.10+
- Windows / macOS / Linux

### 1. 克隆项目

```bash
git clone https://github.com/simon40613/stock-signal.git
cd stock-signal
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 启动看板

```bash
# 方式一：使用主入口（推荐，首次运行引导配置Token）
python main.py

# 方式二：直接启动 Streamlit
streamlit run dashboard.py
```

> 首次启动会自动引导配置 Tushare Token，之后无需重复操作。

### 4. 命令行模式

```bash
# 今日筛选
python main.py --screen

# 分析自选股
python main.py --analyze

# 重新配置 Token / 数据源
python main.py --config
```

---

## 📁 项目结构

```
stock-signal/
├── main.py              # 统一入口
├── dashboard.py         # Streamlit 可视化看板
├── config.py            # Token 配置管理
├── requirements.txt     # 依赖列表
├── .gitignore
│
├── core/
│   ├── data_source.py   # 数据源封装（Tushare / AKShare）
│   ├── analyzer.py      # 分析逻辑（评分、信号、判断）
│   ├── screener.py      # 筛选模块
│   ├── watchlist.py     # 自选股管理
│   └── news_crawler.py  # 资讯爬取（东方财富）🆕
│
└── data/                # 本地数据（自动创建，不上传）
```

---

## 🔧 配置说明

### Tushare Token

1. 注册 [Tushare Pro](https://tushare.pro/)
2. 获取 Token
3. 首次运行 `python main.py` 自动提示输入

### 自定义权重

在看板右侧边栏可实时调整三个指标的评分权重，立即生效。

---

## 🗺️ 路线图

| 版本 | 状态 | 内容 |
|:----:|:----:|------|
| V1.0 | ✅ 已发布 | 技术面分析 + 可视化看板 |
| V2.0 | ✅ 当前 | 爬虫模块，资讯抓取与展示 |
| V3.0 | 🔜 规划中 | 策略回测 / 持仓管理 / 异动预警 |

---

## ⚠️ 免责声明

本项目仅供**学习和技术研究**，不构成任何投资建议。股市有风险，投资须谨慎。

---

## 📄 License

MIT License

---

> 💡 开发过程中借助 AI（WorkBuddy）辅助代码生成与架构设计。
