import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
PARAMS_FILE = BASE_DIR / "config_params.json"

# 默认参数配置（与 live_trader.py CONFIG 保持一致）
DEFAULT_PARAMS = {
    # 基础参数
    "symbol": "QQQ.US",
    "capital": 100000,
    "check_interval": 20,
    
    # 策略参数
    "sl": 0.25,
    "tp": 0.30,
    "lookback": 5,
    
    # 动态止盈
    "tp_partial_pct": 1.00,
    "tp_trail_drop": 0.30,
    
    # 期权参数
    "option_offset": 2.0,
    "min_contracts": 10,
    "contract_multiplier": 100,
    
    # 资金管理
    "pos_pct": 0.02,
    "max_trades": 8,
    "daily_limit": 0.05,
    
    # 交易窗口
    "start_time": "09:35",
    "end_time": "15:50",
    
    # 过滤参数
    "max_gap": 0.002,
    "vol_mult": 0.8,
    "min_body": 0.0003,
    
    # 衰竭反转参数
    "reversal_drop": 0.002,
    "reversal_bounce": 0.001,
}

# 参数说明和约束
PARAM_METADATA = {
    "symbol": {
        "description": "交易标的",
        "type": "string",
        "options": ["QQQ.US", "SPY.US", "QQQA.US"],
    },
    "capital": {
        "description": "账户资金（USD）",
        "type": "number",
        "min": 1000,
        "max": 10000000,
    },
    "check_interval": {
        "description": "检测间隔（秒）",
        "type": "integer",
        "min": 5,
        "max": 60,
    },
    "sl": {
        "description": "止损率",
        "type": "float",
        "min": 0.10,
        "max": 0.50,
        "hint": "亏损达到此比例时平仓",
    },
    "tp": {
        "description": "止盈率",
        "type": "float",
        "min": 0.10,
        "max": 1.00,
        "hint": "兼容旧逻辑，优先使用动态止盈",
    },
    "lookback": {
        "description": "突破窗口（K线数）",
        "type": "integer",
        "min": 3,
        "max": 10,
        "hint": "检测前 N 根 K 线的高低点",
    },
    "tp_partial_pct": {
        "description": "部分止盈点（百分比）",
        "type": "float",
        "min": 0.30,
        "max": 2.00,
        "hint": "盈利达到此比例时平仓一半",
    },
    "tp_trail_drop": {
        "description": "回撤止盈（百分比）",
        "type": "float",
        "min": 0.10,
        "max": 0.50,
        "hint": "从最高盈利回撤此比例时全部平仓",
    },
    "vol_mult": {
        "description": "成交量倍数",
        "type": "float",
        "min": 0.5,
        "max": 2.0,
        "hint": "相对 20 周期均量的倍数",
    },
    "min_body": {
        "description": "K线实体比例",
        "type": "float",
        "min": 0.0001,
        "max": 0.01,
        "hint": "K线实体占收盘价的最小比例",
    },
    "max_trades": {
        "description": "日最大交易笔数",
        "type": "integer",
        "min": 1,
        "max": 20,
    },
    "daily_limit": {
        "description": "日亏损限制",
        "type": "float",
        "min": 0.01,
        "max": 0.20,
        "hint": "日亏损达到此比例时停止交易",
    },
    "start_time": {
        "description": "交易开始时间（美东）",
        "type": "string",
        "pattern": "HH:MM",
    },
    "end_time": {
        "description": "交易结束时间（美东）",
        "type": "string",
        "pattern": "HH:MM",
    },
    "reversal_drop": {
        "description": "衰竭反转：高点跌幅",
        "type": "float",
        "min": 0.001,
        "max": 0.01,
        "hint": "从日内高点回落的最小幅度",
    },
    "reversal_bounce": {
        "description": "衰竭反转：反弹实体",
        "type": "float",
        "min": 0.0001,
        "max": 0.01,
        "hint": "反弹 K 线实体的最小比例",
    },
}


def load_params() -> Dict[str, Any]:
    """加载参数配置"""
    if PARAMS_FILE.exists():
        try:
            return json.loads(PARAMS_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error("加载参数文件失败: %s，使用默认参数", e)
            return DEFAULT_PARAMS.copy()
    return DEFAULT_PARAMS.copy()


def save_params(params: Dict[str, Any]) -> bool:
    """保存参数配置"""
    try:
        PARAMS_FILE.write_text(json.dumps(params, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.info("✓ 参数已保存")
        return True
    except Exception as e:
        logger.error("保存参数失败: %s", e)
        return False


def validate_param(key: str, value: Any) -> tuple[bool, Optional[str]]:
    """验证单个参数"""
    if key not in PARAM_METADATA:
        return False, f"未知参数: {key}"
    
    meta = PARAM_METADATA[key]
    param_type = meta.get("type")
    
    # 类型检查
    if param_type == "string":
        if not isinstance(value, str):
            return False, f"{key} 必须是字符串"
        options = meta.get("options")
        if options and value not in options:
            return False, f"{key} 只能是: {', '.join(options)}"
    
    elif param_type == "integer":
        if not isinstance(value, int):
            try:
                value = int(value)
            except (ValueError, TypeError):
                return False, f"{key} 必须是整数"
        
        min_val = meta.get("min")
        max_val = meta.get("max")
        if min_val is not None and value < min_val:
            return False, f"{key} 最小值: {min_val}"
        if max_val is not None and value > max_val:
            return False, f"{key} 最大值: {max_val}"
    
    elif param_type == "float" or param_type == "number":
        try:
            value = float(value)
        except (ValueError, TypeError):
            return False, f"{key} 必须是数字"
        
        min_val = meta.get("min")
        max_val = meta.get("max")
        if min_val is not None and value < min_val:
            return False, f"{key} 最小值: {min_val}"
        if max_val is not None and value > max_val:
            return False, f"{key} 最大值: {max_val}"
    
    return True, None


def validate_params(params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """验证整个参数集"""
    for key, value in params.items():
        valid, error = validate_param(key, value)
        if not valid:
            return False, error
    return True, None


def update_params(updates: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """更新参数"""
    # 验证所有更新
    valid, error = validate_params(updates)
    if not valid:
        return False, error
    
    # 加载现有参数
    params = load_params()
    
    # 更新参数
    params.update(updates)
    
    # 保存参数
    return save_params(params), None


def get_param_metadata():
    """获取参数元数据（用于 UI 渲染）"""
    return {
        "defaults": DEFAULT_PARAMS,
        "metadata": PARAM_METADATA,
    }


def get_param_categories() -> Dict[str, list]:
    """按类别组织参数"""
    categories = {
        "基础配置": ["symbol", "capital", "check_interval"],
        "风险管理": ["sl", "tp", "tp_partial_pct", "tp_trail_drop", "max_trades", "daily_limit"],
        "信号过滤": ["lookback", "vol_mult", "min_body", "max_gap"],
        "衰竭反转": ["reversal_drop", "reversal_bounce"],
        "交易窗口": ["start_time", "end_time"],
        "期权参数": ["option_offset", "min_contracts", "contract_multiplier", "pos_pct"],
    }
    return categories
