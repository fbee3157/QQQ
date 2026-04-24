import os
import logging
from pathlib import Path

from longbridge.openapi import Config

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"
RECORDS_DIR = BASE_DIR / "records"
DEFAULT_SYMBOL = "QQQ.US"

logger = logging.getLogger(__name__)


def load_dotenv(dotenv_path: Path = None) -> None:
    """从 .env 文件加载环境变量"""
    dotenv_path = dotenv_path or BASE_DIR / ".env"
    if not dotenv_path.exists():
        logger.warning(".env 文件不存在: %s", dotenv_path)
        return

    for line in dotenv_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
        if key.startswith("LONGPORT_"):
            logger.debug("已加载密钥: %s=***", key)


def get_longbridge_config() -> Config:
    """获取长桥配置"""
    load_dotenv()
    try:
        return Config.from_apikey_env()
    except Exception as e:
        logger.error("无法加载长桥配置: %s", e)
        raise


def get_symbol() -> str:
    """获取交易标的"""
    return os.environ.get("TRADE_SYMBOL", DEFAULT_SYMBOL)


def ensure_paths() -> None:
    """确保所有必要的目录存在"""
    RECORDS_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        default_state = {
            "connected": False,
            "running": False,
            "candle_count": 0,
            "last_updated": None,
            "position": None,
            "daily_trades": 0,
            "daily_loss_rate": 0.0,
            "daily_realized_pnl": 0.0,
            "last_signal": None,
            "last_trade_date": None,
        }
        import json
        STATE_FILE.write_text(json.dumps(default_state, indent=2, ensure_ascii=False), encoding="utf-8")
