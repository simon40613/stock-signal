# Stock Signal 📈

> 基于 Python 的 A 股辅助决策系统，支持股票筛选、持仓分析、上市公司资讯抓取与可视化看板。

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red)
![License](https://img.shields.io/badge/License-MIT-green)

---

## ✨ 功能

| 模块 | 说明 |
|------|------|
| **今日筛选** | 从沪市随机抽样，按趋势/动能/成交量打分，输出 Top N 候选股 |
| **持仓分析** | 对自选股给出 ADD / HOLD / WAIT / EXIT 操作建议 |
| **可视化看板** | K线图 + 均线 + 操作信号卡片，颜色直观（涨红跌绿） |
| **自选股管理** | 增删自选股，记录仓位，一键导入筛选结果 |
| **多数据源** | 支持 Tushare Pro（主）/ AKShare（免费备用），引导配置 Token |
| **资讯抓取 🆕** | 自动爬取东方财富最新公告/新闻，在持仓页和筛选结果中同步展示 |

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 启动看板（推荐）

```bash
python main.py
```

首次运行会引导你配置数据源和 Token，之后无需重复操作。

也可以直接启动 Streamlit：

```bash
streamlit run dashboard.py
```

### 3. 命令行模式

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
├── main.py           # 统一入口
├── dashboard.py      # Streamlit 可视化看板
├── config.py         # Token 配置管理
├── requirements.txt
├── .gitignore
├── core/
│   ├── data_source.py   # 数据源封装（Tushare / AKShare）
│   ├── analyzer.py      # 分析逻辑（评分、信号、确认）
│   ├── screener.py      # 筛选模块
│   ├── watchlist.py     # 自选股管理
│   └── news_crawler.py  # 资讯爬取（东方财富）🆕
└── data/             # 本地数据（不上传）
```

---

## 📊 评分逻辑

每只股票的最终评分由三个维度组成（权重可在看板自定义）：

| 维度 | 默认权重 | 说明 |
|------|---------|------|
| 趋势分 | 40 | MA5 > MA10 > MA20 多头排列 |
| 动能分 | 30 | 近 5 日涨幅 |
| 成交量分 | 30 | 量比（当日成交量 vs 近 5 日均量） |

当趋势和动能同时较强时，额外乘以放大系数（最高 ×1.5）。

---

## 🗺️ 版本计划

- **V1.0** — 技术面分析 + 可视化看板
- **V2.0（当前）** — 爬虫模块，抓取东方财富上市公司公告/资讯，持仓页和筛选页同步展示

---

## ⚠️ 免责声明

本项目仅供学习和技术研究，不构成任何投资建议。股市有风险，投资须谨慎。

---

## 📄 License

MIT

---

> 本项目在开发过程中借助 AI（WorkBuddy）辅助代码生成与架构设计。


