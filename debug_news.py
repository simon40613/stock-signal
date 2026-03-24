import requests, time, json

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.eastmoney.com/",
}

# 测试公告接口
print("=== 公告接口 ===")
url1 = "https://np-anotice-stock.eastmoney.com/api/security/ann?sr=-1&page_size=3&page_index=1&ann_type=A&client_source=web&stock_list=1.600036"
try:
    r1 = requests.get(url1, headers=headers, timeout=8)
    d1 = r1.json()
    items1 = d1.get("data", {}).get("list", [])
    print(f"条数: {len(items1)}")
    if items1:
        print("第一条字段:", list(items1[0].keys()))
        print("第一条内容:", items1[0])
except Exception as e:
    print("公告接口失败:", e)

# 测试新闻接口
print("\n=== 新闻接口 ===")
url2 = f"https://np-listapi.eastmoney.com/comm/wap/getListInfo?cb=cb&client=wap&type=1&mTypeAndCode=1.600036&pageSize=3&pageIndex=1&_={int(time.time()*1000)}"
try:
    r2 = requests.get(url2, headers=headers, timeout=8)
    text = r2.text
    print("原始前600字符:", text[:600])
    if text.startswith("cb("):
        text = text[3:-1]
    d2 = json.loads(text)
    items2 = d2.get("data", {}).get("list", [])
    print(f"条数: {len(items2)}")
    if items2:
        print("第一条字段:", list(items2[0].keys()))
        print("第一条内容:", items2[0])
except Exception as e:
    print("新闻接口失败:", e)
