"""
股票筛选模块
- 从沪市6开头股票中随机抽样
- 对每只股票打分
- 返回 Top N 候选股
"""

import pandas as pd
import time
import random

from core.analyzer import score_stock


def run_screening(
    provider,
    sample_size: int = 300,
    top_n: int = 20,
    start_date: str = "20240101",
    weights: dict = None,
    delay: float = 0.25,
) -> pd.DataFrame:
    """
    主筛选函数（生成器版，配合 stqdm 使用）
    每次 yield 一个 (idx, total, ts_code, name, score_or_None)
    :return: DataFrame，按最终评分降序
    """
    print("📦 正在获取股票池...")
    df_basic = provider.get_stock_list(exchange="SSE", prefix="6")

    if len(df_basic) < sample_size:
        sample_size = len(df_basic)

    sample_df = df_basic.sample(n=sample_size, random_state=None).reset_index(drop=True)
    total = len(sample_df)
    print(f"📦 本次随机抽取：{total} 只，目标 Top {top_n}")
    print("-" * 50)

    results = []

    for idx, row in sample_df.iterrows():
        ts_code = row["ts_code"]
        name    = row["name"]

        print(f"  [{idx+1}/{total}] {ts_code} {name}", end="\r")

        score = None
        try:
            df = provider.get_daily(ts_code, start_date=start_date)
            score = score_stock(df, weights=weights)
            time.sleep(delay)

            if score:
                results.append({
                    "股票代码": ts_code,
                    "股票名称": name,
                    **score
                })
        except Exception:
            pass

        yield idx + 1, total, ts_code, name, score

    print()
    print(f"✅ 有效数据：{len(results)} 只")

    if not results:
        return pd.DataFrame()

    df_result = pd.DataFrame(results)
    df_top = df_result.sort_values("最终评分", ascending=False).head(top_n).reset_index(drop=True)
    return df_top
