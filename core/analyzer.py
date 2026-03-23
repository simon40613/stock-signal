"""
核心分析模块
- 大盘状态判断
- 单股评分（趋势 + 动能 + 成交量）
- 持仓分析（ADD / HOLD / WAIT / EXIT）
- 买入最终确认
"""

import pandas as pd
import datetime


# ─────────────────────────────────────────
# 大盘状态
# ─────────────────────────────────────────
def get_market_state(provider) -> str:
    """
    用上证指数 MA20 判断大盘：
    - OK   : 收盘 > MA20，可以操作
    - RISK : 收盘 < MA20，谨慎
    """
    df = provider.get_index_daily("000001.SH", start_date="20240101")
    if df is None or len(df) < 20:
        return "UNKNOWN"
    df["ma20"] = df["close"].rolling(20).mean()
    latest = df.iloc[-1]
    return "OK" if latest["close"] > latest["ma20"] else "RISK"


# ─────────────────────────────────────────
# 单股评分（用于筛选）
# ─────────────────────────────────────────
def score_stock(df: pd.DataFrame, weights: dict = None) -> dict | None:
    """
    对一只股票打分，返回评分字典。
    weights 可自定义各维度权重，默认：趋势40 动能30 成交量30
    """
    if df is None or len(df) < 30:
        return None

    w = weights or {"trend": 40, "momentum": 30, "volume": 30}

    close = df["close"]
    vol = df["vol"]

    ma5  = close.rolling(5).mean()
    ma10 = close.rolling(10).mean()
    ma20 = close.rolling(20).mean()

    # ① 趋势分
    if ma5.iloc[-1] > ma10.iloc[-1] > ma20.iloc[-1]:
        trend_score = w["trend"]
    elif ma5.iloc[-1] > ma10.iloc[-1]:
        trend_score = round(w["trend"] * 0.625)
    elif ma5.iloc[-1] > ma20.iloc[-1]:
        trend_score = round(w["trend"] * 0.375)
    else:
        trend_score = 0

    # ② 动能分（5日涨幅）
    momentum = (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100
    if momentum > 6:
        momentum_score = w["momentum"]
    elif momentum > 3:
        momentum_score = round(w["momentum"] * 0.667)
    elif momentum > 1:
        momentum_score = round(w["momentum"] * 0.333)
    else:
        momentum_score = 0

    # ③ 成交量分（量比）
    vol_ratio = vol.iloc[-1] / vol.iloc[-6:-1].mean()
    if vol_ratio > 1.8:
        volume_score = w["volume"]
    elif vol_ratio > 1.3:
        volume_score = round(w["volume"] * 0.667)
    elif vol_ratio > 1.0:
        volume_score = round(w["volume"] * 0.333)
    else:
        volume_score = 0

    base_score = trend_score + momentum_score + volume_score

    # 放大系数（趋势和动能同时强时加分）
    multiplier = 1.0
    if trend_score >= round(w["trend"] * 0.75):
        multiplier += 0.3
    if momentum_score >= round(w["momentum"] * 0.667):
        multiplier += 0.2

    final_score = round(base_score * multiplier, 1)

    return {
        "收盘价":   round(close.iloc[-1], 2),
        "ma5":      round(ma5.iloc[-1], 2),
        "ma10":     round(ma10.iloc[-1], 2),
        "ma20":     round(ma20.iloc[-1], 2),
        "5日涨幅%": round(momentum, 2),
        "量比":     round(vol_ratio, 2),
        "趋势分":   trend_score,
        "动能分":   momentum_score,
        "成交量分": volume_score,
        "基础分":   base_score,
        "最终评分": final_score,
    }


# ─────────────────────────────────────────
# 持仓分析（ADD / HOLD / WAIT / EXIT）
# ─────────────────────────────────────────
def analyze_stock(df: pd.DataFrame) -> dict | None:
    """
    对持仓/关注股给出操作建议
    """
    if df is None or len(df) < 30:
        return None

    df["ma5"]  = df["close"].rolling(5).mean()
    df["ma20"] = df["close"].rolling(20).mean()

    latest = df.iloc[-1]
    prev   = df.iloc[-2]

    trend    = "up"     if latest["ma5"]   > latest["ma20"] else "down"
    momentum = "strong" if latest["close"] > prev["close"]  else "weak"
    break_ma20 = latest["close"] < latest["ma20"]

    if break_ma20:
        action = "EXIT"
    elif trend == "up" and momentum == "strong":
        action = "ADD"
    elif trend == "up":
        action = "HOLD"
    else:
        action = "WAIT"

    return {
        "action":     action,
        "trend":      trend,
        "momentum":   momentum,
        "break_ma20": break_ma20,
        "close":      round(latest["close"], 2),
        "ma5":        round(latest["ma5"], 2),
        "ma20":       round(latest["ma20"], 2),
    }


# ─────────────────────────────────────────
# 买入最终确认（最后一道门）
# ─────────────────────────────────────────
def can_buy(
    ts_code: str,
    provider,
    today_position_ratio: float,
    system_action: str,
    max_position: float = 0.20,
    chase_limit: float = 0.095,
) -> tuple[bool, str]:
    """
    买入前最终检查：
    1. 仓位上限
    2. 系统信号
    3. 是否追涨
    4. 14点后暴跌
    """
    if today_position_ratio >= max_position:
        return False, f"已达试仓上限 {max_position*100:.0f}%，禁止继续买入"

    if system_action == "EXIT":
        return False, "系统信号 EXIT，禁止买入"

    rt = provider.get_realtime(ts_code)
    if rt is None:
        return False, "无法获取实时行情，跳过"

    pct = rt["pct_chg"]

    if pct > chase_limit:
        return False, f"涨幅 {pct:.2%}，属于追涨，禁止买入"

    now = datetime.datetime.now()
    if now.hour >= 14 and pct < -0.04:
        return False, f"14点后暴跌 {pct:.2%}，放弃买入"

    return True, f"满足全部条件，当前涨幅 {pct:.2%}，可以买入"


# ─────────────────────────────────────────
# 操作建议说明
# ─────────────────────────────────────────
ACTION_EXPLAIN = {
    "ADD":  ("加仓", "趋势延续，动能仍在 → 可考虑加仓",  "#e53935"),   # 红色
    "HOLD": ("持有", "趋势未破，动能减弱 → 持有观察",    "#fb8c00"),   # 橙色
    "WAIT": ("观望", "方向不明 → 继续观望，不操作",       "#757575"),   # 灰色
    "EXIT": ("清仓", "跌破关键均线 → 退出保护资金",       "#43a047"),   # 绿色（A股跌 → 绿）
    "BUY":  ("买入", "趋势向上，市场环境允许 → 小仓试错", "#e53935"),
}

def explain_action(action: str) -> tuple[str, str, str]:
    """返回 (操作名, 解释文字, 颜色)"""
    return ACTION_EXPLAIN.get(action, ("未知", "状态不明确 → 不操作", "#9e9e9e"))
