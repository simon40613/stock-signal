"""
news_crawler.py — 东方财富上市公司资讯爬取模块

接口说明：
    东方财富提供半公开的 JSON 接口，通过 stock code 直接拉取公司相关新闻。
    无需登录，requests 直接访问。
"""

import requests
import time
from typing import List, Dict

# 请求头，模拟浏览器，避免被拦截
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.eastmoney.com/",
}

# 请求超时（秒）
_TIMEOUT = 8


def _ts_to_em_code(ts_code: str) -> str:
    """
    将 Tushare 格式股票代码转为东方财富格式
    例：600036.SH → 1.600036
         000001.SZ → 0.000001
    """
    code, market = ts_code.upper().split(".")
    prefix = "1" if market == "SH" else "0"
    return f"{prefix}.{code}"


def fetch_news(ts_code: str, limit: int = 3) -> List[Dict]:
    """
    获取指定股票最近 N 条资讯

    :param ts_code: Tushare 格式股票代码，如 '600036.SH'
    :param limit:   返回条数，默认 3
    :return: list of dict，每条包含 title / time / url / source

    返回示例：
    [
        {
            "title": "招商银行：一季度营收同比增长...",
            "time":  "2026-03-24 10:15:00",
            "url":   "https://finance.eastmoney.com/...",
            "source": "东方财富网"
        },
        ...
    ]
    若请求失败，返回空列表，不抛异常。
    """
    try:
        em_code = _ts_to_em_code(ts_code)
        url = (
            "https://np-anotice-stock.eastmoney.com/api/security/ann"
            f"?sr=-1&page_size={limit}&page_index=1"
            f"&ann_type=A&client_source=web&stock_list={em_code}"
        )
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        items = data.get("data", {}).get("list", [])
        results = []
        for item in items[:limit]:
            results.append({
                "title":  item.get("NOTICE_TITLE", "无标题"),
                "time":   item.get("NOTICE_DATE", "")[:16].replace("T", " "),
                "url":    f"https://www.eastmoney.com/a/{item.get('ANN_ID', '')}.html",
                "source": "东方财富·公告",
            })
        if results:
            return results

        # 公告接口没数据，尝试新闻接口
        return _fetch_news_fallback(ts_code, limit)

    except Exception:
        return _fetch_news_fallback(ts_code, limit)


def _fetch_news_fallback(ts_code: str, limit: int = 3) -> List[Dict]:
    """
    备用接口：东方财富股票新闻流
    """
    try:
        code = ts_code.split(".")[0]
        market = ts_code.split(".")[1].upper()
        # 东方财富新闻列表接口
        url = (
            "https://np-listapi.eastmoney.com/comm/wap/getListInfo"
            f"?cb=cb&client=wap&type=1&mTypeAndCode={(1 if market == 'SH' else 0)}.{code}"
            f"&pageSize={limit}&pageIndex=1&_={int(time.time() * 1000)}"
        )
        resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
        text = resp.text
        # 去掉 JSONP 包裹
        if text.startswith("cb("):
            text = text[3:-1]
        import json
        data = json.loads(text)
        items = data.get("data", {}).get("list", [])
        results = []
        for item in items[:limit]:
            results.append({
                "title":  item.get("title", "无标题"),
                "time":   item.get("datetime", "")[:16],
                "url":    item.get("url", ""),
                "source": item.get("mediaName", "东方财富"),
            })
        return results
    except Exception:
        return []


def fetch_news_batch(ts_codes: List[str], limit: int = 3, delay: float = 0.3) -> Dict[str, List[Dict]]:
    """
    批量获取多只股票的资讯

    :param ts_codes: 股票代码列表
    :param limit:    每只股票返回条数
    :param delay:    每次请求间隔（秒），防止限频
    :return: {ts_code: [news_list]}
    """
    result = {}
    for ts_code in ts_codes:
        result[ts_code] = fetch_news(ts_code, limit=limit)
        time.sleep(delay)
    return result
