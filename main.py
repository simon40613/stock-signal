"""
命令行入口
用法：
  python main.py              # 启动 Streamlit 看板（推荐）
  python main.py --screen     # 命令行跑今日筛选
  python main.py --analyze    # 命令行分析自选股
  python main.py --config     # 重新配置 Token / 数据源
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from config import get_config, setup_wizard
from core.data_source import get_provider
from core.analyzer import get_market_state, analyze_stock, explain_action
from core.screener import run_screening
from core.watchlist import get_watchlist
import datetime


def cmd_screen(provider):
    """命令行筛选模式"""
    print("=" * 50)
    print("📊 今日筛选")
    print(datetime.datetime.now().strftime("  %Y-%m-%d %H:%M"))
    print("=" * 50)

    market = get_market_state(provider)
    print(f"🌍 大盘状态：{market}")
    print()

    df = run_screening(provider, sample_size=300, top_n=20)

    if df.empty:
        print("❌ 筛选结果为空，请检查数据源配置")
        return

    print()
    print("🎉 Top 20 候选股：")
    print(df[[
        "股票代码", "股票名称", "收盘价",
        "趋势分", "动能分", "成交量分", "最终评分"
    ]].to_string(index=False))

    # 保存到 data/
    out_path = Path("data") / f"screening_{datetime.date.today()}.csv"
    out_path.parent.mkdir(exist_ok=True)
    df.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"\n💾 结果已保存：{out_path}")


def cmd_analyze(provider):
    """命令行分析自选股"""
    print("=" * 50)
    print("📈 自选股分析")
    print(datetime.datetime.now().strftime("  %Y-%m-%d %H:%M"))
    print("=" * 50)

    market = get_market_state(provider)
    print(f"🌍 大盘状态：{market}")
    print("-" * 50)

    watchlist = get_watchlist()
    if not watchlist:
        print("⚠️ 自选股为空，请先通过看板或命令添加")
        return

    for i, stock in enumerate(watchlist, 1):
        ts_code  = stock["ts_code"]
        name     = stock.get("name", "")
        position = stock.get("position_ratio", 0.0)

        try:
            df = provider.get_daily(ts_code)
            result = analyze_stock(df)
            if result is None:
                print(f"[{i}] {ts_code} {name} → 数据不足，跳过")
                continue

            # 大盘过滤
            if market == "RISK" and result["action"] in ("ADD", "BUY"):
                result["action"] = "WAIT"

            action_name, explain, _ = explain_action(result["action"])
            print(
                f"[{i}/{len(watchlist)}] {ts_code} {name} | "
                f"动作：{result['action']} ({action_name}) | "
                f"收盘：{result['close']} | 仓位：{position*100:.0f}% | {explain}"
            )
            time.sleep(0.1)

        except Exception as e:
            print(f"[{i}] {ts_code} 跳过：{e}")

    print("=" * 50)
    print("✅ 分析完成")


def launch_dashboard():
    """启动 Streamlit 看板"""
    dashboard = Path(__file__).parent / "dashboard.py"
    print("🚀 正在启动可视化看板...")
    print("   浏览器将自动打开，或手动访问 http://localhost:8501")
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(dashboard)])


def main():
    parser = argparse.ArgumentParser(description="Stock Signal — A股辅助决策系统")
    parser.add_argument("--screen",  action="store_true", help="命令行筛选模式")
    parser.add_argument("--analyze", action="store_true", help="命令行分析自选股")
    parser.add_argument("--config",  action="store_true", help="重新配置 Token / 数据源")
    args = parser.parse_args()

    if args.config:
        setup_wizard()
        return

    cfg = get_config()
    provider = get_provider(cfg)

    if args.screen:
        cmd_screen(provider)
    elif args.analyze:
        cmd_analyze(provider)
    else:
        launch_dashboard()


if __name__ == "__main__":
    main()
