"""
数据源统一封装
- Tushare 为主，AKShare 为备用
- 对外暴露统一接口，调用方无需关心底层
"""

import pandas as pd
import time


def get_provider(cfg: dict):
    """根据配置返回对应 provider 实例"""
    source = cfg.get("data_source", "tushare")
    if source == "tushare":
        return TushareProvider(cfg["tushare_token"])
    else:
        return AKShareProvider()


# ─────────────────────────────────────────
# Tushare Provider
# ─────────────────────────────────────────
class TushareProvider:
    def __init__(self, token: str):
        import tushare as ts
        ts.set_token(token)
        self.pro = ts.pro_api()
        self._ts = ts

    def get_stock_list(self, exchange: str = "SSE", prefix: str = "6") -> pd.DataFrame:
        """获取股票基础列表"""
        df = self.pro.stock_basic(
            exchange=exchange,
            list_status="L",
            fields="ts_code,symbol,name"
        )
        if prefix:
            df = df[df["symbol"].str.startswith(prefix)]
        return df.reset_index(drop=True)

    def get_daily(self, ts_code: str, start_date: str = "20240101") -> pd.DataFrame:
        """获取日线数据"""
        df = self.pro.daily(ts_code=ts_code, start_date=start_date)
        if df is not None and not df.empty:
            df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def get_index_daily(self, ts_code: str = "000001.SH", start_date: str = "20240101") -> pd.DataFrame:
        """获取指数日线（用于判断大盘）"""
        df = self.pro.index_daily(ts_code=ts_code, start_date=start_date)
        if df is not None and not df.empty:
            df = df.sort_values("trade_date").reset_index(drop=True)
        return df

    def get_realtime(self, ts_code: str) -> dict | None:
        """获取实时行情"""
        import tushare as ts
        df = ts.realtime_quote(ts_code)
        if df is None or df.empty:
            return None
        row = df.iloc[0]
        return {
            "price": float(row["PRICE"]),
            "pre_close": float(row["PRE_CLOSE"]),
            "pct_chg": (float(row["PRICE"]) - float(row["PRE_CLOSE"])) / float(row["PRE_CLOSE"])
        }


# ─────────────────────────────────────────
# AKShare Provider（免费备用）
# ─────────────────────────────────────────
class AKShareProvider:
    def __init__(self):
        import akshare as ak
        self._ak = ak

    def get_stock_list(self, exchange: str = "SSE", prefix: str = "6") -> pd.DataFrame:
        """获取沪市 A 股列表"""
        df = self._ak.stock_info_a_code_name()
        df = df.rename(columns={"code": "symbol", "name": "name"})
        if prefix:
            df = df[df["symbol"].str.startswith(prefix)]
        df["ts_code"] = df["symbol"] + ".SH"
        return df[["ts_code", "symbol", "name"]].reset_index(drop=True)

    def get_daily(self, ts_code: str, start_date: str = "20240101") -> pd.DataFrame:
        """获取日线数据，转换为 tushare 格式"""
        symbol = ts_code.replace(".SH", "").replace(".SZ", "")
        df = self._ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start_date.replace("-", ""),
            adjust="qfq"
        )
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={
            "日期": "trade_date",
            "开盘": "open",
            "收盘": "close",
            "最高": "high",
            "最低": "low",
            "成交量": "vol",
            "成交额": "amount",
            "涨跌幅": "pct_chg"
        })
        df["trade_date"] = df["trade_date"].astype(str).str.replace("-", "")
        return df.sort_values("trade_date").reset_index(drop=True)

    def get_index_daily(self, ts_code: str = "000001.SH", start_date: str = "20240101") -> pd.DataFrame:
        """获取上证指数日线"""
        df = self._ak.stock_zh_index_daily(symbol="sh000001")
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns={"date": "trade_date", "close": "close"})
        df["trade_date"] = df["trade_date"].astype(str).str.replace("-", "")
        df = df[df["trade_date"] >= start_date]
        return df.sort_values("trade_date").reset_index(drop=True)

    def get_realtime(self, ts_code: str) -> dict | None:
        """获取实时行情（近似，akshare 用当日快照）"""
        symbol = ts_code.replace(".SH", "").replace(".SZ", "")
        try:
            df = self._ak.stock_zh_a_spot_em()
            row = df[df["代码"] == symbol]
            if row.empty:
                return None
            r = row.iloc[0]
            pre_close = float(r["昨收"])
            price = float(r["最新价"])
            return {
                "price": price,
                "pre_close": pre_close,
                "pct_chg": (price - pre_close) / pre_close if pre_close else 0
            }
        except Exception:
            return None
