import json
import logging
import os
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

try:
    import requests
except ImportError:
    requests = None

from config import RECORDS_DIR, ensure_paths

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
GIST_ID = os.environ.get("GIST_ID")


def latest_record() -> dict:
    """获取最新交易记录"""
    ensure_paths()
    files = sorted(RECORDS_DIR.glob("record_*.json"), reverse=True)
    if not files:
        return {}
    try:
        return json.loads(files[0].read_text(encoding="utf-8"))
    except Exception as e:
        logging.error("读取最新记录失败: %s", e)
        return {}


def sync_to_gist() -> None:
    """同步最新交易记录到 GitHub Gist"""
    if not requests:
        logging.error("缺少 requests 模块。请运行: pip install requests")
        return

    if not GITHUB_TOKEN:
        logging.error("未设置 GITHUB_TOKEN 环境变量")
        return

    if not GIST_ID:
        logging.error("未设置 GIST_ID 环境变量")
        return

    record = latest_record()
    if not record:
        logging.warning("没有可同步的交易记录。")
        return

    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "files": {
            "qqq-trading-latest.json": {
                "content": json.dumps(record, indent=2, ensure_ascii=False)
            }
        }
    }

    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        logging.info("✓ 已将最新交易记录同步到 Gist")
    except requests.exceptions.RequestException as e:
        logging.error("同步到 Gist 失败: %s", e)


def sync_daily_summary(date_str: str = None) -> None:
    """同步当日总结"""
    if not requests or not GITHUB_TOKEN or not GIST_ID:
        return

    ensure_paths()
    from datetime import datetime
    if date_str is None:
        date_str = datetime.utcnow().date().isoformat()

    records = sorted(RECORDS_DIR.glob("record_*.json"), reverse=True)
    daily_records = [
        json.loads(f.read_text(encoding="utf-8"))
        for f in records
        if date_str in f.name
    ]

    if not daily_records:
        logging.info("该日期无交易记录")
        return

    # 统计信息
    entries = [r for r in daily_records if r.get("event") == "entry"]
    exits = [r for r in daily_records if r.get("event") == "exit"]
    
    pnls = [r.get("pnl_pct", 0) for r in exits if r.get("pnl_pct") is not None]
    total_trades = len(entries)
    wins = sum(1 for p in pnls if p > 0)
    win_rate = wins / len(pnls) * 100 if pnls else 0

    summary = {
        "date": date_str,
        "total_trades": total_trades,
        "total_exits": len(exits),
        "win_rate": f"{win_rate:.1f}%",
        "avg_pnl": f"{sum(pnls) / len(pnls) * 100:.2f}%" if pnls else "N/A",
        "best_trade": f"{max(pnls) * 100:.2f}%" if pnls else "N/A",
        "worst_trade": f"{min(pnls) * 100:.2f}%" if pnls else "N/A",
    }

    url = f"https://api.github.com/gists/{GIST_ID}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    payload = {
        "files": {
            "qqq-daily-summary.json": {
                "content": json.dumps(summary, indent=2, ensure_ascii=False)
            }
        }
    }

    try:
        response = requests.patch(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        logging.info("✓ 已同步当日总结到 Gist: %s", summary)
    except requests.exceptions.RequestException as e:
        logging.error("同步当日总结失败: %s", e)


if __name__ == "__main__":
    sync_to_gist()

