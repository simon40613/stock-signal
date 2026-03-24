"""
Streamlit 可视化看板
运行方式：streamlit run dashboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import mplfinance as mpf
import datetime
import time
from pathlib import Path
from stqdm import stqdm

from config import get_config, save_config, load_config
from core.data_source import get_provider
from core.analyzer import get_market_state, analyze_stock, explain_action, score_stock
from core.watchlist import (
    get_watchlist, add_stock, remove_stock,
    update_position, update_buy_price, import_from_list
)
from core.news_crawler import fetch_news, fetch_news_batch


# ── 中文字体设置 ──────────────────────────────────────────
matplotlib.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "Arial Unicode MS"]
matplotlib.rcParams["axes.unicode_minus"] = False

# ── 页面配置 ──────────────────────────────────────────────
st.set_page_config(
    page_title="Stock Signal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── 颜色常量（A股：涨红跌绿）─────────────────────────────
COLOR_UP   = "#e53935"
COLOR_DOWN = "#43a047"
COLOR_HOLD = "#fb8c00"
COLOR_WAIT = "#757575"

ACTION_COLOR = {
    "ADD":  COLOR_UP,
    "BUY":  COLOR_UP,
    "HOLD": COLOR_HOLD,
    "WAIT": COLOR_WAIT,
    "EXIT": COLOR_DOWN,
}

# ─────────────────────────────────────────────────────────
# 初始化：加载配置 / 数据源
# ─────────────────────────────────────────────────────────
@st.cache_resource(show_spinner=False)
def init_provider(token: str, source: str):
    cfg = {"data_source": source, "tushare_token": token}
    return get_provider(cfg)


def get_or_setup_config():
    cfg = load_config()
    if not cfg.get("tushare_token") and cfg.get("data_source", "tushare") == "tushare":
        return None
    return cfg


# ─────────────────────────────────────────────────────────
# 侧边栏
# ─────────────────────────────────────────────────────────
def sidebar():
    st.sidebar.title("📈 Stock Signal")
    st.sidebar.markdown("---")

    # 配置区
    with st.sidebar.expander("⚙️ 数据源配置", expanded=False):
        source = st.selectbox("数据源", ["tushare", "akshare"], key="source_select")
        if source == "tushare":
            cfg = load_config()
            token = st.text_input(
                "Tushare Token",
                value=cfg.get("tushare_token", ""),
                type="password"
            )
            if st.button("保存 Token"):
                cfg["tushare_token"] = token
                cfg["data_source"] = "tushare"
                save_config(cfg)
                st.success("✅ 已保存")
                st.cache_resource.clear()
                st.rerun()
        else:
            cfg = load_config()
            cfg["data_source"] = "akshare"
            save_config(cfg)

    st.sidebar.markdown("---")

    # 自选股管理
    st.sidebar.subheader("⭐ 自选股管理")
    new_code = st.sidebar.text_input("添加股票代码（如 600036.SH）")
    new_name = st.sidebar.text_input("股票名称（可选）")
    if st.sidebar.button("➕ 添加"):
        if new_code:
            add_stock(new_code.strip().upper(), new_name.strip())
            st.sidebar.success(f"已添加 {new_code}")
            st.rerun()

    watchlist = get_watchlist()
    if watchlist:
        del_code = st.sidebar.selectbox(
            "删除自选股",
            [""] + [f"{s['ts_code']} {s['name']}" for s in watchlist]
        )
        if st.sidebar.button("🗑️ 删除"):
            if del_code:
                remove_stock(del_code.split()[0])
                st.rerun()

    st.sidebar.markdown("---")
    st.sidebar.caption(f"更新时间：{datetime.datetime.now().strftime('%H:%M:%S')}")

    return load_config()


# ─────────────────────────────────────────────────────────
# K线图
# ─────────────────────────────────────────────────────────
def plot_kline(df: pd.DataFrame, ts_code: str, title: str = "") -> plt.Figure:
    df2 = df.copy()
    df2["trade_date"] = pd.to_datetime(df2["trade_date"])
    df2 = df2.set_index("trade_date")
    df2 = df2[["open", "high", "low", "close", "vol"]].tail(60)
    df2.columns = ["Open", "High", "Low", "Close", "Volume"]

    ma5  = df2["Close"].rolling(5).mean()
    ma10 = df2["Close"].rolling(10).mean()
    ma20 = df2["Close"].rolling(20).mean()

    add_plots = [
        mpf.make_addplot(ma5,  color="#e53935", width=1.0, label="MA5"),
        mpf.make_addplot(ma10, color="#1565c0", width=1.0, label="MA10"),
        mpf.make_addplot(ma20, color="#f9a825", width=1.2, label="MA20"),
    ]

    # A股配色：涨红跌绿，通过 make_mpf_style 传入
    mc = mpf.make_marketcolors(
        up=COLOR_UP, down=COLOR_DOWN,
        edge="inherit", wick="inherit",
        volume={"up": COLOR_UP, "down": COLOR_DOWN}
    )
    astyle = mpf.make_mpf_style(base_mpf_style="charles", marketcolors=mc)

    fig, axes = mpf.plot(
        df2,
        type="candle",
        style=astyle,
        addplot=add_plots,
        volume=True,
        returnfig=True,
        figsize=(10, 5),
        title=f" {title or ts_code}",
    )
    return fig


# ─────────────────────────────────────────────────────────
# 评分雷达图
# ─────────────────────────────────────────────────────────
def plot_radar(trend: float, momentum: float, volume_score: float) -> plt.Figure:
    """
    绘制三维度评分雷达图
    """
    categories = ["趋势", "动能", "成交量"]
    values = [trend, momentum, volume_score]
    values += values[:1]  # 闭合多边形

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles += angles[:1]

    fig, ax = plt.subplots(figsize=(3.2, 3.2), subplot_kw=dict(polar=True))
    ax.fill(angles, values, color=COLOR_UP, alpha=0.25)
    ax.plot(angles, values, color=COLOR_UP, linewidth=2)
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories, fontsize=10)
    ax.set_ylim(0, 100)
    ax.set_yticks([25, 50, 75, 100], fontsize=7)
    ax.set_yticklabels(["25", "50", "75", "100"], fontsize=7)
    ax.set_title("评分雷达图", fontsize=11, pad=12)
    fig.tight_layout()
    return fig


# ─────────────────────────────────────────────────────────
# 迷你K线图（嵌卡片内）
# ─────────────────────────────────────────────────────────
def plot_mini_kline(df: pd.DataFrame, ts_code: str) -> plt.Figure:
    """
    绘制迷你K线图（不显示成交量，节省空间）
    """
    df2 = df.tail(20).copy()
    df2.index = pd.to_datetime(df2.index)
    df2.columns = [c.capitalize() for c in df2.columns]

    mc = mpf.make_marketcolors(up=COLOR_UP, down=COLOR_DOWN, edge="inherit", wick="inherit")
    astyle = mpf.make_mpf_style(base_mpf_style="charles", marketcolors=mc)

    fig, _ = mpf.plot(
        df2,
        type="candle",
        style=astyle,
        returnfig=True,
        figsize=(4, 2.2),
        title=f" {ts_code}",
        show_nontrading=False,
    )
    fig.tight_layout(pad=0.5)
    return fig


# ─────────────────────────────────────────────────────────
# 操作建议卡片（含雷达图 + 迷你K线）
# ─────────────────────────────────────────────────────────
def action_card(ts_code: str, name: str, result: dict, position: float,
                buy_price: float, df: pd.DataFrame = None):
    action = result["action"]
    action_name, explain, color = explain_action(action)

    # 信号徽章样式
    badge_html = (
        f"<div style='background:{color};color:white;padding:8px 16px;"
        f"border-radius:20px;text-align:center;font-weight:bold;font-size:18px;"
        f"letter-spacing:2px;box-shadow:2px 2px 8px rgba(0,0,0,0.2)'>"
        f"{action} {action_name}</div>"
    )

    # 雷达图
    trend = result.get("trend_score", 0)
    momentum = result.get("momentum_score", 0)
    volume_score = result.get("volume_score", 0)
    radar_fig = plot_radar(trend, momentum, volume_score)

    # 迷你K线
    kline_fig = plot_mini_kline(df, ts_code) if df is not None else None

    # 浮盈亏计算
    current_price = result["close"]
    if buy_price and buy_price > 0:
        profit_pct = (current_price - buy_price) / buy_price * 100
        pct_color = COLOR_UP if profit_pct >= 0 else COLOR_DOWN
        profit_str = f"<b style='color:{pct_color}'>{'+' if profit_pct >= 0 else ''}{profit_pct:.2f}%</b>"
    else:
        profit_str = "—"

    # 布局：左侧信息 + 信号 | 右侧雷达图 | 右下迷你K线
    col_info, col_action, col_radar = st.columns([3, 1.5, 2.5])

    with col_info:
        st.markdown(f"**{ts_code}**  {name}")
        st.metric("当前价", f"¥{current_price:.2f}")
        st.caption(f"趋势 {trend:.0f}  动能 {momentum:.0f}  成交量 {volume_score:.0f}")

    with col_action:
        st.markdown(badge_html, unsafe_allow_html=True)
        st.caption(f"仓位 {position*100:.0f}% | 浮盈亏 {profit_str}")
        st.markdown(f"<small style='color:{color}'>{explain}</small>", unsafe_allow_html=True)

    with col_radar:
        st.pyplot(radar_fig)

    if kline_fig is not None:
        col_kline, _ = st.columns([2.5, 7.5])
        with col_kline:
            st.pyplot(kline_fig)


# ─────────────────────────────────────────────────────────
# 资讯缓存（避免重复请求，5分钟自动刷新）
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def cached_news(ts_code: str) -> list:
    return fetch_news(ts_code, limit=3)


@st.cache_data(ttl=300, show_spinner=False)
def cached_news_batch(ts_codes: list) -> dict:
    return fetch_news_batch(ts_codes, limit=3, delay=0.2)


# ─────────────────────────────────────────────────────────
# 主页面
# ─────────────────────────────────────────────────────────
def main():
    cfg = sidebar()

    # 未配置 token 时提示
    if cfg.get("data_source") == "tushare" and not cfg.get("tushare_token"):
        st.warning("⚠️ 请先在左侧「数据源配置」中输入 Tushare Token")
        st.stop()

    # 初始化数据源
    try:
        provider = init_provider(
            cfg.get("tushare_token", ""),
            cfg.get("data_source", "tushare")
        )
    except Exception as e:
        st.error(f"数据源初始化失败：{e}")
        st.stop()

    tab1, tab2, tab3 = st.tabs(["📊 自选股分析", "🔍 今日筛选", "📈 K线详情"])

    # ────────────────────────────────────────
    # Tab1：自选股分析
    # ────────────────────────────────────────
    with tab1:
        st.subheader("自选股操作建议")

        col_m1, col_m2 = st.columns([3, 1])
        with col_m2:
            if st.button("🔄 刷新分析", use_container_width=True):
                st.rerun()

        # 大盘状态
        with st.spinner("判断大盘状态..."):
            try:
                market = get_market_state(provider)
            except Exception:
                market = "UNKNOWN"

        market_color = {"OK": COLOR_UP, "RISK": COLOR_DOWN, "UNKNOWN": COLOR_WAIT}
        market_label = {"OK": "✅ 大盘偏强，可以操作", "RISK": "⚠️ 大盘偏弱，谨慎操作", "UNKNOWN": "❓ 大盘状态未知"}
        st.markdown(
            f"<div style='background:{market_color.get(market, COLOR_WAIT)};color:white;"
            f"padding:8px 16px;border-radius:8px;margin-bottom:12px'>"
            f"🌍 {market_label.get(market)}</div>",
            unsafe_allow_html=True
        )

        watchlist = get_watchlist()
        if not watchlist:
            st.info("自选股为空，请在左侧添加股票")
        else:
            st.markdown("---")
            for stock in watchlist:
                ts_code  = stock["ts_code"]
                name     = stock.get("name", "")
                position = stock.get("position_ratio", 0.0)

                try:
                    df = provider.get_daily(ts_code)
                    result = analyze_stock(df)
                    if result is None:
                        st.warning(f"{ts_code} 数据不足，跳过")
                        continue

                    if market == "RISK" and result["action"] in ("ADD", "BUY"):
                        result["action"] = "WAIT"

                    action_card(ts_code, name, result, position, buy_price, df)

                    # 仓位 + 买入价快速调整
                    col_pos, col_buy = st.columns([1, 1])
                    new_pos = col_pos.slider(
                        f"{ts_code} 仓位", 0.0, 1.0, position, 0.05,
                        key=f"pos_{ts_code}",
                        format="%.0f%%"
                    )
                    default_buy = stock.get("buy_price", 0.0) or 0.0
                    new_buy = col_buy.number_input(
                        f"{ts_code} 买入价", 0.0, 10000.0, default_buy, 0.01,
                        key=f"buy_{ts_code}",
                        format="%.2f"
                    )
                    if new_pos != position:
                        update_position(ts_code, new_pos)
                    if abs(new_buy - default_buy) > 0.001:
                        update_buy_price(ts_code, new_buy)

                    # 最近资讯（后台缓存，加载更快）
                    with st.expander(f"📰 {name or ts_code} 最近资讯", expanded=False):
                        news_list = cached_news(ts_code)
                        if not news_list:
                            st.caption("暂无相关资讯")
                        else:
                            for news in news_list:
                                st.markdown(
                                    f"• [{news['title']}]({news['url']})  "
                                    f"<span style='color:#999;font-size:12px'>{news['time']} · {news['source']}</span>",
                                    unsafe_allow_html=True
                                )

                    st.markdown("---")

                except Exception as e:
                    st.error(f"{ts_code} 分析失败：{e}")

    # ────────────────────────────────────────
    # Tab2：今日筛选
    # ────────────────────────────────────────
    with tab2:
        st.subheader("今日选股筛选")

        col_s1, col_s2, col_s3 = st.columns(3)
        sample_size = col_s1.slider("抽样数量", 100, 600, 300, 50)
        top_n       = col_s2.slider("返回 Top N", 5, 50, 20, 5)

        st.markdown("**自定义评分权重**")
        wc1, wc2, wc3 = st.columns(3)
        w_trend  = wc1.number_input("趋势权重", 10, 60, 40, 5)
        w_mom    = wc2.number_input("动能权重", 10, 60, 30, 5)
        w_vol    = wc3.number_input("成交量权重", 10, 60, 30, 5)
        weights  = {"trend": w_trend, "momentum": w_mom, "volume": w_vol}

        if st.button("🚀 开始筛选", type="primary"):
            try:
                # 获取股票池
                df_basic = provider.get_stock_list(exchange="SSE", prefix="6")
                sample_n = min(sample_size, len(df_basic))
                sample_df = df_basic.sample(n=sample_n, random_state=None).reset_index(drop=True)
                total_n = len(sample_df)

                # 导入分析函数（避免顶层循环引用）
                from core.analyzer import score_stock as _score_fn
                results = []

                # stqdm 带进度条遍历
                for _, row in stqdm(sample_df.iterrows(), total=total_n, desc="📊 股票评分中"):
                    ts_code = row["ts_code"]
                    try:
                        df_daily = provider.get_daily(ts_code)
                        score = _score_fn(df_daily, weights=weights)
                        time.sleep(0.25)
                        if score:
                            results.append({"股票代码": ts_code, "股票名称": row["name"], **score})
                    except Exception:
                        pass

                if not results:
                    st.error("筛选结果为空")
                else:
                    df_result = pd.DataFrame(results)
                    df_top = df_result.sort_values("最终评分", ascending=False).head(top_n).reset_index(drop=True)

                    st.success(f"✅ 筛选完成，共找到 {len(df_top)} 只候选股")
                    display_cols = ["股票代码", "股票名称", "收盘价", "5日涨幅%", "量比", "趋势分", "动能分", "成交量分", "最终评分"]
                    st.dataframe(
                        df_top[display_cols].style.background_gradient(
                            subset=["最终评分"], cmap="Reds"
                        ),
                        use_container_width=True
                    )

                    # 候选股资讯展示（后台缓存）
                    st.markdown("### 📰 候选股资讯")
                    st.caption("点击展开查看各股最近资讯（来源：东方财富）")
                    news_map = cached_news_batch(df_top["股票代码"].tolist())
                    for _, row in df_top.iterrows():
                        code = row["股票代码"]
                        sname = row["股票名称"]
                        news_list = news_map.get(code, [])
                        with st.expander(f"📌 {code} {sname}", expanded=False):
                            if not news_list:
                                st.caption("暂无相关资讯")
                            else:
                                for news in news_list:
                                    st.markdown(
                                        f"• [{news['title']}]({news['url']})  "
                                        f"<span style='color:#999;font-size:12px'>{news['time']} · {news['source']}</span>",
                                        unsafe_allow_html=True
                                    )

                    st.markdown("---")
                    selected = st.multiselect(
                        "选择要加入自选股的股票",
                        [f"{r['股票代码']} {r['股票名称']}" for _, r in df_top.iterrows()]
                    )
                    if st.button("⭐ 加入自选股"):
                        for item in selected:
                            code, *name_parts = item.split()
                            add_stock(code, " ".join(name_parts))
                        st.success(f"已添加 {len(selected)} 只")
                        st.rerun()

                    csv = df_top.to_csv(index=False, encoding="utf-8-sig")
                    st.download_button(
                        "💾 下载 CSV",
                        csv,
                        file_name=f"screening_{datetime.date.today()}.csv",
                        mime="text/csv"
                    )

            except Exception as e:
                st.error(f"筛选出错：{e}")

    # ────────────────────────────────────────
    # Tab3：K线详情
    # ────────────────────────────────────────
    with tab3:
        st.subheader("K线详情")

        watchlist = get_watchlist()
        options = [""] + [f"{s['ts_code']} {s['name']}" for s in watchlist]
        manual  = st.text_input("或直接输入股票代码（如 600036.SH）")
        select  = st.selectbox("选择自选股", options)

        ts_code = manual.strip().upper() if manual.strip() else (select.split()[0] if select else "")
        title   = select if select else ts_code

        if ts_code:
            if st.button("📈 加载K线"):
                with st.spinner(f"加载 {ts_code} 数据..."):
                    try:
                        df = provider.get_daily(ts_code)
                        if df is None or df.empty:
                            st.error("数据为空")
                        else:
                            fig = plot_kline(df, ts_code, title)
                            st.pyplot(fig)

                            # 显示当前分析结论
                            result = analyze_stock(df)
                            if result:
                                action_name, explain, color = explain_action(result["action"])
                                st.markdown(
                                    f"**当前信号：**"
                                    f"<span style='color:{color};font-weight:bold;font-size:18px'>"
                                    f" {result['action']} {action_name}</span>"
                                    f" — {explain}",
                                    unsafe_allow_html=True
                                )
                                m1, m2, m3, m4 = st.columns(4)
                                m1.metric("收盘价", f"¥{result['close']}")
                                m2.metric("MA5",   f"¥{result['ma5']}")
                                m3.metric("MA20",  f"¥{result['ma20']}")
                                m4.metric("趋势",   "上升 ↑" if result["trend"] == "up" else "下降 ↓")

                    except Exception as e:
                        st.error(f"加载失败：{e}")


if __name__ == "__main__":
    main()
