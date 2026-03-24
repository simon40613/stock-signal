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
import io
from pathlib import Path
from stqdm import stqdm

from config import get_config, save_config, load_config
from core.data_source import get_provider
from core.analyzer import get_market_state, analyze_stock, explain_action, score_stock
from core.watchlist import (
    get_watchlist, add_stock, remove_stock,
    update_position, import_from_list
)
from core.news_crawler import fetch_news, fetch_news_batch


# ─────────────────────────────────────────────────────────
# 股票代码标准化：自动补全 .SH / .SZ 后缀
# 例如：输入 600036 → 600036.SH，000001 → 000001.SZ
# ─────────────────────────────────────────────────────────
def normalize_ts_code(raw: str) -> str:
    """将简码或混合格式的股票代码转为标准 Tushare 格式"""
    code = raw.strip().upper()
    # 去掉已有的后缀
    if code.endswith(".SH") or code.endswith(".SZ"):
        return code
    # 纯数字，根据开头判断市场
    if code.isdigit():
        if code.startswith("6") or code.startswith("9"):
            return f"{code}.SH"
        else:
            return f"{code}.SZ"
    return code


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
    st.sidebar.markdown(
        "<style>"
        "section[data-testid='stSidebar'] .stTextInput input {"
        "  border: 1.5px solid #555 !important;"
        "  border-radius: 6px;"
        "  background: #3a3a3a !important;"
        "  color: #e0e0e0 !important;"
        "}"
        "section[data-testid='stSidebar'] .stTextInput input::placeholder {"
        "  color: #999 !important;"
        "}"
        "</style>",
        unsafe_allow_html=True
    )
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
    new_code = st.sidebar.text_input("添加股票代码（输入纯数字即可，如 600036）")
    new_name = st.sidebar.text_input("股票名称（可选）")
    if st.sidebar.button("➕ 添加"):
        if new_code:
            ts_code = normalize_ts_code(new_code)
            add_stock(ts_code, new_name.strip())
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
    # 资讯来源筛选
    st.sidebar.subheader("🔍 资讯筛选")
    news_source_filter = st.sidebar.multiselect(
        "只看指定来源（留空为全部）",
        options=["东方财富", "财联社", "证券时报", "上海证券报", "中国证券网"],
        default=[],
        format_func=lambda x: x
    )

    st.sidebar.markdown("---")
    st.sidebar.caption(f"更新时间：{datetime.datetime.now().strftime('%H:%M:%S')}")

    return load_config(), news_source_filter


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
def plot_radar(trend: float, momentum: float, volume_score: float) -> io.BytesIO:
    """
    绘制三维度评分雷达图（极坐标，动态最大值）。
    """
    # 设置中文字体
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS"]
    plt.rcParams["axes.unicode_minus"] = False

    categories = ["趋势", "动能", "成交量"]
    values     = [trend, momentum, volume_score]
    values_closed = values + [values[0]]

    raw_max = max(values + [1])
    dyn_max = max(20, int(np.ceil(raw_max / 10) * 10))

    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
    angles_closed = angles + [angles[0]]
    dyn_ticks = [dyn_max * p for p in [0.25, 0.5, 0.75, 1.0]]

    fig = plt.figure(figsize=(3.6, 3.6), facecolor="black")
    ax  = fig.add_subplot(111, polar=True, facecolor="black")
    ax.fill(angles_closed, values_closed, color=COLOR_UP, alpha=0.30)
    ax.plot(angles_closed, values_closed, color=COLOR_UP, linewidth=3.5)
    ax.set_xticks(angles)
    ax.set_xticklabels(categories, fontsize=13, color="#eeeeee", fontweight="bold")
    ax.set_ylim(0, dyn_max)
    ax.set_yticks(dyn_ticks)
    ax.tick_params(axis="y", labelsize=9, colors="#aaaaaa")
    ax.spines["polar"].set_color("#666666")
    ax.grid(color="#444444", linewidth=0.8)

    # 端点标注分数
    for angle, val in zip(angles, values):
        ax.annotate(
            f"{val:.0f}",
            xy=(angle, val),
            xytext=(angle, dyn_max * 0.88),
            textcoords="data",
            fontsize=13, fontweight="bold",
            ha="center", va="center",
            color=COLOR_UP,
            clip_on=False,
        )

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, facecolor="black")
    buf.seek(0)
    plt.close(fig)
    return buf


# ─────────────────────────────────────────────────────────
# 迷你K线图（嵌卡片内）
# ─────────────────────────────────────────────────────────
def plot_mini_kline(df: pd.DataFrame, ts_code: str) -> io.BytesIO:
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

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    buf.seek(0)
    plt.close(fig)
    return buf


# ─────────────────────────────────────────────────────────
# 操作建议卡片（含雷达图 + 迷你K线）
# ─────────────────────────────────────────────────────────
def action_card(ts_code: str, name: str, result: dict, position: float, df: pd.DataFrame = None):
    action = result["action"]
    action_name, explain, color = explain_action(action)
    current_price = result["close"]

    # 调用 score_stock 获取评分数据（analyze_stock 不返回这些字段）
    scores = score_stock(df) if df is not None else None
    if scores:
        trend = scores["趋势分"]
        momentum = scores["动能分"]
        volume_score = scores["成交量分"]
    else:
        trend = momentum = volume_score = 0

    # 自动检测参考买入价：取近30日最低收盘价
    if df is not None and len(df) >= 5:
        ref_price = float(df["close"].tail(30).min())
        profit_pct = (current_price - ref_price) / ref_price * 100
        pct_color = COLOR_UP if profit_pct >= 0 else COLOR_DOWN
        profit_str = f"<b style='color:{pct_color}'>{'+' if profit_pct >= 0 else ''}{profit_pct:.1f}%</b>"
    else:
        profit_str = "—"

    # 信号徽章
    badge_html = (
        f"<div style='background:{color};color:white;padding:8px 18px;"
        f"border-radius:20px;text-align:center;font-weight:bold;font-size:17px;"
        f"letter-spacing:3px;box-shadow:2px 2px 8px rgba(0,0,0,0.2)'>"
        f"{action} {action_name}</div>"
    )

    # 左侧：股票信息 + 信号
    # 右侧：K线图 + 雷达图并排
    col_left, col_right = st.columns([1, 1.6])

    with col_left:
        st.markdown(f"**{ts_code}**  {name}")
        st.metric("当前价", f"¥{current_price:.2f}")
        st.markdown(badge_html, unsafe_allow_html=True)
        st.markdown(
            f"<small style='color:#666'>趋势 <b>{trend:.0f}</b>"
            f"  动能 <b>{momentum:.0f}</b>"
            f"  成交量 <b>{volume_score:.0f}</b></small>",
            unsafe_allow_html=True
        )
        st.markdown(f"<small style='color:{color}'>{explain}</small>", unsafe_allow_html=True)
        st.caption(f"仓位 {position*100:.0f}%  |  参考盈亏 {profit_str}")

    with col_right:
        radar_buf = plot_radar(trend, momentum, volume_score)
        kline_buf = plot_mini_kline(df, ts_code) if df is not None else None
        col_kline, col_radar = st.columns([1.4, 1])
        with col_kline:
            if kline_buf:
                st.image(kline_buf, use_container_width=True)
        with col_radar:
            st.image(radar_buf, width=200)


# ─────────────────────────────────────────────────────────
# 资讯缓存（避免重复请求，5分钟自动刷新）
# ─────────────────────────────────────────────────────────
@st.cache_data(ttl=300, show_spinner=False)
def cached_news(ts_code: str) -> list:
    return fetch_news(ts_code, limit=5)


@st.cache_data(ttl=300, show_spinner=False)
def cached_news_batch(ts_codes: list) -> dict:
    return fetch_news_batch(ts_codes, limit=5, delay=0.2)


def _filter_news(news_list: list, sources: list) -> list:
    """根据来源筛选新闻，sources 为空时返回全部"""
    if not sources:
        return news_list
    return [n for n in news_list if any(s in n.get("source", "") for s in sources)]


# ─────────────────────────────────────────────────────────
# 主页面
# ─────────────────────────────────────────────────────────
def main():
    cfg, news_filter = sidebar()

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

    # ─────────────────────────────────────────────────────────
    # 渲染筛选结果的函数（被缓存分支和新鲜计算共用）
    # ─────────────────────────────────────────────────────────
    def _render_filter_results(df_top: pd.DataFrame):
        def _color_score(val, max_val=100):
            if val >= 75:   return "background:rgba(229,57,53,0.35);color:#c62828;font-weight:700"
            if val >= 50:   return "background:rgba(251,140,0,0.3);color:#e65100;font-weight:600"
            if val >= 25:   return "background:rgba(253,216,53,0.3);color:#555;font-weight:500"
            if val > 0:     return "background:rgba(129,199,132,0.3);color:#2e7d32;font-weight:400"
            return "color:#999"

        news_map = cached_news_batch(df_top["股票代码"].tolist())

        for _, row in df_top.iterrows():
            code = row["股票代码"];  sname = row["股票名称"]
            trend = row["趋势分"];  mom = row["动能分"];  vol = row["成交量分"]
            final = row["最终评分"]

            # 信息行
            c1, c2, c3, c4, c5, c6 = st.columns([1.2, 1.2, 0.9, 0.9, 0.9, 1.2])
            c1.markdown(f"**{code}**  {sname}")
            c2.metric("收盘价", f"¥{row['收盘价']:.2f}")
            c3.markdown(f"<div style='text-align:center;padding:4px 0'>"
                        f"<div style='background:#e53935;color:white;border-radius:4px;padding:2px 6px;font-size:12px'>{trend:.0f}分</div>"
                        f"<small>趋势</small></div>", unsafe_allow_html=True)
            c4.markdown(f"<div style='text-align:center;padding:4px 0'>"
                        f"<div style='background:#fb8c00;color:white;border-radius:4px;padding:2px 6px;font-size:12px'>{mom:.0f}分</div>"
                        f"<small>动能</small></div>", unsafe_allow_html=True)
            c5.markdown(f"<div style='text-align:center;padding:4px 0'>"
                        f"<div style='background:#1565c0;color:white;border-radius:4px;padding:2px 6px;font-size:12px'>{vol:.0f}分</div>"
                        f"<small>成交量</small></div>", unsafe_allow_html=True)
            c6.markdown(f"<div style='text-align:center;padding:4px 0'>"
                        f"<div style='background:#b71c1c;color:white;border-radius:6px;padding:6px 10px;font-size:15px;font-weight:bold'>{final:.1f}分</div>"
                        f"<small>综合评分</small></div>", unsafe_allow_html=True)

            # 按钮行
            col_btn, col_news = st.columns([1, 3])
            if col_btn.button(f"⭐ 加入自选", key=f"add_{code}"):
                add_stock(code, sname)
                col_btn.success(f"✅ 已加入 {sname}")
            with col_news.expander(f"📰 {code} {sname} 最新资讯", expanded=False):
                all_news  = news_map.get(code, [])
                news_list = _filter_news(all_news, news_filter)
                if not news_list:
                    st.caption("暂无相关资讯")
                else:
                    for n in news_list:
                        st.markdown(
                            f"• [{n['title']}]({n['url']})  "
                            f"<span style='color:#999;font-size:12px'>{n['time']} · {n['source']}</span>",
                            unsafe_allow_html=True
                        )
            st.markdown("---")

        csv = df_top.to_csv(index=False, encoding="utf-8-sig")
        st.download_button("💾 下载筛选结果 CSV", csv,
                           file_name=f"screening_{datetime.date.today()}.csv",
                           mime="text/csv")


    # 初始化筛选结果缓存（跨 rerun 持久化）
    if "filter_done" not in st.session_state:
        st.session_state["filter_done"] = False
    if "filter_df" not in st.session_state:
        st.session_state["filter_df"] = None
    if "filter_triggered" not in st.session_state:
        st.session_state["filter_triggered"] = False

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

        # 持仓总览：一次性拉取所有股票的当前价和评分
        watchlist = get_watchlist()
        if watchlist:
            overview_cols = st.columns([1, 1, 1, 1])
            total_count = len(watchlist)
            total_close_sum = 0.0
            total_ref_sum = 0.0
            action_counts = {"ADD": 0, "HOLD": 0, "WAIT": 0, "EXIT": 0}
            loaded = 0

            for stock in watchlist:
                try:
                    df_temp = provider.get_daily(stock["ts_code"])
                    if df_temp is None or len(df_temp) < 30:
                        continue
                    close = float(df_temp["close"].iloc[-1])
                    ref = float(df_temp["close"].tail(30).min())
                    total_close_sum += close
                    total_ref_sum += ref
                    res = analyze_stock(df_temp)
                    if res:
                        action_counts[res["action"]] = action_counts.get(res["action"], 0) + 1
                    loaded += 1
                except Exception:
                    continue

            # 参考整体盈亏
            if loaded > 0 and total_ref_sum > 0:
                avg_profit = (total_close_sum - total_ref_sum) / total_ref_sum * 100
                profit_color = COLOR_UP if avg_profit >= 0 else COLOR_DOWN
                profit_icon = "📈" if avg_profit >= 0 else "📉"
                overview_cols[0].metric("自选股数量", f"{total_count} 只")
                overview_cols[1].metric("已分析", f"{loaded} 只")
                overview_cols[2].metric(
                    "参考盈亏",
                    f"{profit_icon} {avg_profit:+.1f}%",
                    delta_color="normal" if avg_profit >= 0 else "inverse"
                )
                add_count = action_counts.get("ADD", 0) + action_counts.get("HOLD", 0)
                overview_cols[3].metric("可操作信号", f"{add_count} 个")
            else:
                for col in overview_cols:
                    col.metric("—", "加载中...")

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

                    action_card(ts_code, name, result, position, df)

                    # 仓位快速调整
                    new_pos = st.slider(
                        f"{ts_code} 仓位", 0.0, 1.0, position, 0.05,
                        key=f"pos_{ts_code}",
                        format="%.0f%%"
                    )
                    if new_pos != position:
                        update_position(ts_code, new_pos)

                    # 最近资讯（后台缓存，支持来源筛选）
                    with st.expander(f"📰 {name or ts_code} 最近资讯", expanded=False):
                        all_news = cached_news(ts_code)
                        news_list = _filter_news(all_news, news_filter)
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

        # ── 有缓存时：直接展示（rerun 后不会丢失）───
        if st.session_state["filter_done"] and st.session_state["filter_df"] is not None:
            df_top = st.session_state["filter_df"]
            st.success(f"📋 筛选结果（共 {len(df_top)} 只）")
            _render_filter_results(df_top)
            st.divider()

        # 用标志位判断按钮是否被点击（比 st.button 返回值更可靠）
        if st.button("🚀 开始筛选", type="primary"):
            st.session_state["filter_triggered"] = True

        if st.session_state.get("filter_triggered"):
            st.session_state["filter_triggered"] = False  # 重置标志
            try:
                df_basic = provider.get_stock_list(exchange="SSE", prefix="6")
                sample_n = min(sample_size, len(df_basic))
                sample_df = df_basic.sample(n=sample_n, random_state=None).reset_index(drop=True)
                total_n = len(sample_df)

                from core.analyzer import score_stock as _score_fn
                results = []

                # 用 st.progress 替代 stqdm + spinner
                progress_bar = st.progress(0, text="📊 股票评分中...")
                for i, (_, row) in enumerate(sample_df.iterrows()):
                    ts_code = row["ts_code"]
                    try:
                        df_daily = provider.get_daily(ts_code)
                        score = _score_fn(df_daily, weights=weights)
                        time.sleep(0.25)
                        if score:
                            results.append({"股票代码": ts_code, "股票名称": row["name"], **score})
                    except Exception:
                        pass
                    progress_bar.progress((i + 1) / total_n, text=f"📊 股票评分中... {(i+1)*100//total_n}%")
                progress_bar.empty()

                if not results:
                    st.error("筛选结果为空")
                else:
                    df_result = pd.DataFrame(results)
                    df_top = df_result.sort_values("最终评分", ascending=False).head(top_n).reset_index(drop=True)
                    st.session_state["filter_df"]   = df_top
                    st.session_state["filter_done"] = True
                    st.rerun()
            except Exception as e:
                st.error(f"筛选出错：{e}")

    # ────────────────────────────────────────
    # Tab3：K线详情（完整个股分析页）
    # ────────────────────────────────────────
    with tab3:
        st.subheader("个股 K线分析")

        watchlist = get_watchlist()
        options = [""] + [f"{s['ts_code']} {s['name']}" for s in watchlist]
        manual  = st.text_input("输入股票代码（输入纯数字即可，如 600036）")
        select  = st.selectbox("或从自选股选择", options)

        ts_code = normalize_ts_code(manual) if manual.strip() else (select.split()[0] if select else "")
        title   = select if select else ts_code

        if ts_code:
            if st.button("🔍 分析该股票", type="primary"):
                st.session_state["tab3_ts_code"] = ts_code
                st.session_state["tab3_title"] = title

        # 记忆最后一次分析的股票
        current_code = st.session_state.get("tab3_ts_code", "")
        current_title = st.session_state.get("tab3_title", "")

        if current_code:
            with st.spinner(f"加载 {current_code} 数据..."):
                try:
                    df = provider.get_daily(current_code)
                    if df is None or df.empty:
                        st.error("数据为空，请检查股票代码是否正确")
                    else:
                        # 评分数据
                        scores = score_stock(df)
                        result = analyze_stock(df)
                        action_name, explain, color = explain_action(result["action"])

                        # 上半部分：雷达图 + 指标
                        col_radar, col_metrics = st.columns([1.2, 2.8])
                        with col_radar:
                            radar_buf = plot_radar(
                                scores["趋势分"], scores["动能分"], scores["成交量分"]
                            )
                            st.image(radar_buf, width=210)

                        with col_metrics:
                            m1, m2, m3, m4 = st.columns(4)
                            m1.metric("收盘价", f"¥{scores['收盘价']:.2f}")
                            m2.metric("MA5", f"¥{scores['ma5']:.2f}")
                            m3.metric("MA10", f"¥{scores['ma10']:.2f}")
                            m4.metric("MA20", f"¥{scores['ma20']:.2f}")

                            # 信号徽章
                            badge_html = (
                                f"<div style='background:{color};color:white;padding:8px 20px;"
                                f"border-radius:20px;text-align:center;font-weight:bold;"
                                f"font-size:20px;letter-spacing:3px;"
                                f"box-shadow:2px 2px 8px rgba(0,0,0,0.3)'>"
                                f"{result['action']} {action_name}</div>"
                            )
                            st.markdown(badge_html, unsafe_allow_html=True)
                            st.markdown(f"<small style='color:{color}'>{explain}</small>",
                                        unsafe_allow_html=True)
                            m5, m6, m7 = st.columns(3)
                            m5.metric("趋势分", f"{scores['趋势分']:.0f}", delta="强" if scores["趋势分"] >= 30 else "弱", delta_color="off")
                            m6.metric("动能分", f"{scores['动能分']:.0f}", delta="强" if scores["动能分"] >= 20 else "弱", delta_color="off")
                            m7.metric("成交量分", f"{scores['成交量分']:.0f}", delta="活跃" if scores["成交量分"] >= 20 else "弱", delta_color="off")

                        # K线图
                        fig = plot_kline(df, current_code, current_title)
                        st.pyplot(fig)

                        # 加入自选按钮
                        col_add, _ = st.columns([1, 5])
                        if col_add.button(f"⭐ 加入自选", key=f"add_{current_code}"):
                            add_stock(current_code, current_title)
                            col_add.success("✅ 已加入自选")

                        # 资讯
                        st.markdown("#### 📰 最新资讯")
                        all_news = cached_news(current_code)
                        news_list = _filter_news(all_news, news_filter)
                        if not news_list:
                            st.caption("暂无相关资讯")
                        else:
                            for news in news_list:
                                st.markdown(
                                    f"• [{news['title']}]({news['url']})  "
                                    f"<span style='color:#999;font-size:12px'>{news['time']} · {news['source']}</span>",
                                    unsafe_allow_html=True
                                )

                except Exception as e:
                    st.error(f"加载失败：{e}")


if __name__ == "__main__":
    main()
