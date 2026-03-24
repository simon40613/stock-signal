"""
自选股管理
- 持久化存储在本地 JSON
- 支持增删查、标注仓位
"""

import json
from pathlib import Path

WATCHLIST_FILE = Path(__file__).parent.parent / "data" / "watchlist.json"


def _load() -> list:
    if WATCHLIST_FILE.exists():
        try:
            return json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _save(data: list):
    WATCHLIST_FILE.parent.mkdir(parents=True, exist_ok=True)
    WATCHLIST_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_watchlist() -> list[dict]:
    """获取全部自选股，格式：[{ts_code, name, position_ratio}]"""
    return _load()


def add_stock(ts_code: str, name: str = "", position_ratio: float = 0.0):
    """添加自选股"""
    data = _load()
    codes = [s["ts_code"] for s in data]
    if ts_code in codes:
        print(f"⚠️ {ts_code} 已在自选股中")
        return
    data.append({"ts_code": ts_code, "name": name, "position_ratio": position_ratio})
    _save(data)
    print(f"✅ 已添加 {ts_code} {name}")


def remove_stock(ts_code: str):
    """删除自选股"""
    data = _load()
    data = [s for s in data if s["ts_code"] != ts_code]
    _save(data)
    print(f"✅ 已删除 {ts_code}")


def update_position(ts_code: str, position_ratio: float):
    """更新某只股票的仓位"""
    data = _load()
    for s in data:
        if s["ts_code"] == ts_code:
            s["position_ratio"] = position_ratio
            _save(data)
            print(f"✅ {ts_code} 仓位已更新为 {position_ratio*100:.0f}%")
            return
    print(f"⚠️ 未找到 {ts_code}")


def update_buy_price(ts_code: str, buy_price: float):
    """更新买入价（用于计算浮盈亏）"""
    data = _load()
    for s in data:
        if s["ts_code"] == ts_code:
            s["buy_price"] = buy_price
            _save(data)
            return
    print(f"⚠️ 未找到 {ts_code}")


def import_from_list(stock_list: list[dict]):
    """批量导入，stock_list 格式：[{ts_code, name}]"""
    data = _load()
    existing = {s["ts_code"] for s in data}
    added = 0
    for s in stock_list:
        if s["ts_code"] not in existing:
            data.append({
                "ts_code": s["ts_code"],
                "name": s.get("name", ""),
                "position_ratio": 0.0
            })
            added += 1
    _save(data)
    print(f"✅ 批量导入完成，新增 {added} 只")


if __name__ == "__main__":
    # 测试
    add_stock("600036.SH", "招商银行", 0.0)
    add_stock("000001.SZ", "平安银行", 0.1)
    print(get_watchlist())
