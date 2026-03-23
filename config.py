"""
配置管理模块
- 首次运行引导用户输入 Token
- 支持 Tushare（主）/ AKShare（备用/免费）
- Token 保存在本地，不写入代码
"""

import json
import os
from pathlib import Path

CONFIG_DIR = Path.home() / ".stock_signal"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "data_source": "tushare",   # "tushare" 或 "akshare"
    "tushare_token": "",
    "version": "1.0"
}


def load_config() -> dict:
    """读取配置，不存在则返回默认值"""
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    """保存配置到本地"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def setup_wizard():
    """
    首次运行引导流程：
    1. 选择数据源
    2. 若选 Tushare，录入 Token
    """
    print("=" * 50)
    print("  Stock Signal — 首次配置向导")
    print("=" * 50)
    print()
    print("请选择默认数据源：")
    print("  [1] Tushare Pro（推荐，数据更全，需要 Token）")
    print("  [2] AKShare（免费，无需 Token，数据略少）")
    print()

    while True:
        choice = input("输入 1 或 2：").strip()
        if choice in ("1", "2"):
            break
        print("请输入 1 或 2")

    cfg = DEFAULT_CONFIG.copy()

    if choice == "1":
        cfg["data_source"] = "tushare"
        print()
        print("请前往 https://tushare.pro/user/token 复制你的 Token")
        print()
        while True:
            token = input("粘贴 Tushare Token：").strip()
            if len(token) > 20:
                break
            print("Token 格式不对，请重新粘贴")
        cfg["tushare_token"] = token
        print()
        print("✅ Tushare Token 已保存")
    else:
        cfg["data_source"] = "akshare"
        print()
        print("✅ 已选择 AKShare（无需 Token，直接使用）")

    save_config(cfg)
    print("✅ 配置已保存到", CONFIG_FILE)
    print()
    return cfg


def get_config() -> dict:
    """
    获取配置。
    若从未配置过，自动启动引导向导。
    """
    cfg = load_config()
    if not cfg.get("tushare_token") and cfg.get("data_source") == "tushare":
        # 未配置 token，启动向导
        cfg = setup_wizard()
    return cfg


def update_token(new_token: str):
    """手动更新 Tushare Token"""
    cfg = load_config()
    cfg["tushare_token"] = new_token
    cfg["data_source"] = "tushare"
    save_config(cfg)
    print(f"✅ Token 已更新")


def switch_source(source: str):
    """切换数据源：'tushare' 或 'akshare'"""
    assert source in ("tushare", "akshare"), "数据源只能是 tushare 或 akshare"
    cfg = load_config()
    cfg["data_source"] = source
    save_config(cfg)
    print(f"✅ 数据源已切换为 {source}")


if __name__ == "__main__":
    # 直接运行此文件可重新配置
    cfg = setup_wizard()
    print("当前配置：", cfg)
