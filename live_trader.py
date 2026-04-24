import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from longbridge.openapi import Config, QuoteContext, TradeContext

from config import BASE_DIR, RECORDS_DIR, STATE_FILE, ensure_paths, get_longbridge_config, get_symbol
from indicators import average, momentum_rate, price_range, sma
from params import load_params, DEFAULT_PARAMS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# 从参数文件加载配置，或使用默认值
def get_config() -> Dict[str, Any]:
    """获取当前配置（从参数文件）"""
    try:
        return load_params()
    except Exception as e:
        logging.warning("加载参数文件失败，使用默认配置: %s", e)
        return DEFAULT_PARAMS.copy()


# 初始化全局配置
CONFIG = get_config()

MAX_DAILY_TRADES = CONFIG["max_trades"]
MAX_DAILY_LOSS_RATE = CONFIG["daily_limit"]
MIN_CONTRACTS = CONFIG["min_contracts"]
MAX_POSITION_MINUTES = 15
STOP_LOSS_RATE = -CONFIG["sl"]
TAKE_PROFIT_RATE = CONFIG["tp_partial_pct"]

# 解析交易窗口时间
_start_time = CONFIG["start_time"].split(":")
_end_time = CONFIG["end_time"].split(":")
TRADE_WINDOW_START = (int(_start_time[0]), int(_start_time[1]))
TRADE_WINDOW_END = (int(_end_time[0]), int(_end_time[1]))


def load_state() -> Dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    return json.loads(STATE_FILE.read_text(encoding="utf-8"))


def save_state(state: Dict[str, Any]) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def append_record(record: Dict[str, Any]) -> None:
    ensure_paths()
    filename = RECORDS_DIR / f"record_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    filename.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")


def safe_get(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def normalize_candle(raw: Any) -> Dict[str, Any]:
    return {
        "time": safe_get(raw, "time", safe_get(raw, "datetime", None)) or safe_get(raw, "date", None),
        "open": float(safe_get(raw, "open", 0.0)),
        "high": float(safe_get(raw, "high", 0.0)),
        "low": float(safe_get(raw, "low", 0.0)),
        "close": float(safe_get(raw, "close", 0.0)),
        "volume": float(safe_get(raw, "volume", 0.0)),
    }


def fetch_minute_candles(qctx: QuoteContext, symbol: str, size: int = 30) -> List[Dict[str, Any]]:
    try:
        results = qctx.history(symbol, period="1m", size=size)
        if hasattr(results, "to_dict"):
            items = results.to_dict().get("data", [])
        elif isinstance(results, list):
            items = results
        else:
            items = getattr(results, "data", []) or []
        return [normalize_candle(item) for item in items if normalize_candle(item)["close"] > 0]
    except Exception as e:
        logging.error("获取 K 线失败: %s", e)
        return []


def build_signal(candles: List[Dict[str, Any]], daily_high: float, daily_low: float) -> Optional[str]:
    if len(candles) < CONFIG["lookback"] + 5:
        return None

    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]
    volumes = [c["volume"] for c in candles]

    current_close = closes[-1]
    current_high = highs[-1]
    current_low = lows[-1]
    
    # 前 lookback+1 根 K 线的高低点
    lookback = CONFIG["lookback"]
    prev_high = max(highs[-lookback - 1 : -1]) if len(highs) > lookback else current_high
    prev_low = min(lows[-lookback - 1 : -1]) if len(lows) > lookback else current_low
    
    current_sma20 = sma(closes, 20) or current_close
    current_momentum = momentum_rate(closes, window=3) or 0.0
    average_volume = average(volumes[-6:]) or 1.0
    prev_close = closes[-2] if len(closes) > 1 else current_close
    
    # 计算 K 线实体
    current_body = abs(current_close - closes[-2]) / prev_close if len(closes) > 1 and prev_close > 0 else 0.0
    
    # 信号1：趋势突破（顺势）
    # 价格突破前 lookback 根 K 线高点 + 趋势滤波 + 量能滤波
    if (current_close > prev_high 
        and current_close > current_sma20 
        and current_momentum > 0 
        and volumes[-1] >= average_volume * CONFIG["vol_mult"]
        and current_body >= CONFIG["min_body"]):
        logging.info("触发 CALL 信号（趋势突破）")
        return "CALL"

    if (current_close < prev_low 
        and current_close < current_sma20 
        and current_momentum < 0 
        and volumes[-1] >= average_volume * CONFIG["vol_mult"]
        and current_body >= CONFIG["min_body"]):
        logging.info("触发 PUT 信号（趋势突破）")
        return "PUT"

    # 信号2：衰竭反转（逆势）- 从日内高点/低点的跳空反转
    if daily_high > 0 and current_close <= daily_high * (1 - CONFIG["reversal_drop"]):
        if current_body >= CONFIG["reversal_bounce"]:
            logging.info("触发 CALL 信号（衰竭反转）")
            return "CALL"
    
    if daily_low > 0 and current_close >= daily_low * (1 + CONFIG["reversal_drop"]):
        if current_body >= CONFIG["reversal_bounce"]:
            logging.info("触发 PUT 信号（衰竭反转）")
            return "PUT"

    return None


def is_in_trade_window(now: datetime) -> bool:
    start = now.replace(hour=TRADE_WINDOW_START[0], minute=TRADE_WINDOW_START[1], second=0, microsecond=0)
    end = now.replace(hour=TRADE_WINDOW_END[0], minute=TRADE_WINDOW_END[1], second=0, microsecond=0)
    return start <= now <= end


def build_order_payload(symbol: str, signal: str, quantity: int) -> Dict[str, Any]:
    return {
        "symbol": symbol,
        "order_type": "MARKET",
        "side": "BUY" if signal == "CALL" else "SELL",
        "quantity": quantity,
    }


def place_market_order(tctx: TradeContext, payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return tctx.place_order(**payload)
    except TypeError:
        return tctx.place_order(payload)


def calculate_pnl_percent(position: Dict[str, Any], mark_price: float) -> float:
    """计算 PnL 百分比"""
    if not position or position.get("entry_price", 0) == 0:
        return 0.0
    entry = float(position["entry_price"])
    return (mark_price - entry) / entry if entry > 0 else 0.0


def trade_loop() -> None:
    global CONFIG
    ensure_paths()
    config = get_longbridge_config()
    symbol = get_symbol()
    state = load_state()
    state["running"] = True
    state["connected"] = False
    state.setdefault("daily_trades", 0)
    state.setdefault("daily_loss_rate", 0.0)
    state.setdefault("daily_realized_pnl", 0.0)
    state.setdefault("last_trade_date", None)
    save_state(state)

    with QuoteContext(config) as qctx, TradeContext(config) as tctx:
        state["connected"] = True
        save_state(state)
        
        position_peak_pnl = 0.0  # 追踪最高盈利用于回撤止盈
        last_param_reload = time.time()

        while True:
            try:
                now = datetime.utcnow()
                today = now.date()
                today_str = today.isoformat()
                
                # 每 30 秒检查一次参数是否更新（热加载）
                if time.time() - last_param_reload > 30:
                    try:
                        new_config = load_params()
                        if new_config != CONFIG:
                            CONFIG = new_config
                            logging.info("✓ 参数已更新（热加载）")
                            # 更新相关常量
                            globals()["MAX_DAILY_TRADES"] = CONFIG["max_trades"]
                            globals()["MAX_DAILY_LOSS_RATE"] = CONFIG["daily_limit"]
                            globals()["MIN_CONTRACTS"] = CONFIG["min_contracts"]
                            globals()["STOP_LOSS_RATE"] = -CONFIG["sl"]
                            globals()["TAKE_PROFIT_RATE"] = CONFIG["tp_partial_pct"]
                    except Exception as e:
                        logging.warning("参数热加载失败: %s", e)
                    last_param_reload = time.time()

                # 日重置逻辑
                if state.get("last_trade_date") != today_str:
                    state["daily_trades"] = 0
                    state["daily_loss_rate"] = 0.0
                    state["daily_realized_pnl"] = 0.0
                    state["last_trade_date"] = today_str
                    logging.info("===== 新的交易日开始 =====")

                if not is_in_trade_window(now):
                    logging.debug("当前不在交易窗口内，休眠 30 秒。")
                    time.sleep(30)
                    continue

                # 检查日亏损限制
                if state["daily_loss_rate"] <= -MAX_DAILY_LOSS_RATE:
                    logging.warning("日亏损达到 %.2f%%，停止交易。", state["daily_loss_rate"] * 100)
                    time.sleep(60)
                    continue

                candles = fetch_minute_candles(qctx, symbol, size=30)
                if len(candles) < CONFIG["lookback"] + 5:
                    logging.debug("K 线数据不足，等待下一次刷新。")
                    time.sleep(10)
                    continue

                state["candle_count"] = len(candles)
                state["last_updated"] = now.isoformat()

                daily_stats = price_range(candles)
                position = state.get("position")

                if not position:
                    # 没有持仓，检查是否生成新信号
                    signal = build_signal(candles, daily_stats["high"], daily_stats["low"])
                    
                    if signal and state["daily_trades"] < MAX_DAILY_TRADES:
                        order_payload = build_order_payload(symbol, signal, MIN_CONTRACTS)
                        try:
                            result = place_market_order(tctx, order_payload)
                            logging.info("✓ 下单成功 [%s] @ %.2f", signal, candles[-1]["close"])
                            
                            position = {
                                "direction": signal,
                                "entry_price": float(candles[-1]["close"]),
                                "entry_time": now.isoformat(),
                                "quantity": MIN_CONTRACTS,
                                "symbol": symbol,
                                "peak_pnl_pct": 0.0,
                            }
                            position_peak_pnl = 0.0
                            state["position"] = position
                            state["daily_trades"] += 1
                            state["last_signal"] = signal
                            
                            append_record({
                                "event": "entry",
                                "time": now.isoformat(),
                                "symbol": symbol,
                                "signal": signal,
                                "entry_price": position["entry_price"],
                                "quantity": MIN_CONTRACTS,
                            })
                        except Exception as e:
                            logging.error("下单失败: %s", e)
                else:
                    # 有持仓，检查平仓条件
                    mark_price = float(candles[-1]["close"])
                    pnl_pct = calculate_pnl_percent(position, mark_price)
                    elapsed = now - datetime.fromisoformat(position["entry_time"])
                    exit_reason = None

                    # 更新最高盈利用于回撤止盈
                    if pnl_pct > position_peak_pnl:
                        position_peak_pnl = pnl_pct
                        position["peak_pnl_pct"] = pnl_pct

                    # 平仓条件检查（优先级从高到低）
                    # 1. 止损：亏损达到 -25%
                    if pnl_pct <= STOP_LOSS_RATE:
                        exit_reason = "stop_loss"
                    
                    # 2. 超时止损：持仓超过 15 分钟
                    elif elapsed >= timedelta(minutes=MAX_POSITION_MINUTES):
                        exit_reason = "timeout"
                    
                    # 3. 部分止盈：盈利 100% 时平仓一半
                    elif pnl_pct >= TAKE_PROFIT_RATE and not state.get("partial_closed"):
                        exit_reason = "take_profit_partial"
                        state["partial_closed"] = True
                    
                    # 4. 回撤止盈：从最高盈利回撤 30%
                    elif position_peak_pnl > 0 and (position_peak_pnl - pnl_pct) >= CONFIG["tp_trail_drop"]:
                        exit_reason = "profit_trail"

                    if exit_reason:
                        # 平仓订单
                        if exit_reason == "take_profit_partial":
                            qty = position["quantity"] // 2
                        else:
                            qty = position["quantity"]
                        
                        order_payload = {
                            "symbol": symbol,
                            "order_type": "MARKET",
                            "side": "SELL" if position["direction"] == "CALL" else "BUY",
                            "quantity": qty,
                        }
                        
                        try:
                            result = place_market_order(tctx, order_payload)
                            pnl_dollar = (mark_price - position["entry_price"]) * qty
                            logging.info("✓ 平仓 [%s] @ %.2f (PnL: %.2f%% / $%.2f)", 
                                        exit_reason, mark_price, pnl_pct * 100, pnl_dollar)
                            
                            state["daily_realized_pnl"] += pnl_dollar
                            if exit_reason != "take_profit_partial":
                                # 完全平仓
                                state["position"] = None
                                state["partial_closed"] = False
                                position_peak_pnl = 0.0
                            else:
                                # 部分平仓
                                position["quantity"] = position["quantity"] - qty
                            
                            # 更新日亏损率
                            daily_loss = state["daily_realized_pnl"] / CONFIG["capital"]
                            state["daily_loss_rate"] = daily_loss
                            
                            append_record({
                                "event": "exit",
                                "time": now.isoformat(),
                                "symbol": symbol,
                                "reason": exit_reason,
                                "exit_price": mark_price,
                                "quantity": qty,
                                "pnl_pct": pnl_pct,
                                "pnl_dollar": pnl_dollar,
                                "elapsed_minutes": elapsed.total_seconds() / 60,
                            })
                        except Exception as e:
                            logging.error("平仓失败: %s", e)

                state["daily_loss_rate"] = state.get("daily_realized_pnl", 0) / CONFIG["capital"]
                save_state(state)
                time.sleep(CONFIG["check_interval"])
                
            except KeyboardInterrupt:
                logging.info("交易引擎收到退出信号，停止运行。")
                break
            except Exception as exc:
                logging.exception("交易循环发生错误: %s", exc)
                time.sleep(10)
            finally:
                save_state(state)


if __name__ == "__main__":
    trade_loop()
