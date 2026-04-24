from typing import List, Optional


def sma(values: List[float], window: int) -> Optional[float]:
    """简单移动平均线"""
    if not values or len(values) < window or window <= 0:
        return None
    return sum(values[-window:]) / window


def ema(values: List[float], window: int) -> Optional[float]:
    """指数移动平均线"""
    if not values or len(values) < window or window <= 0:
        return None
    
    # 简化版本：直接使用尾部加权
    multiplier = 2 / (window + 1)
    ema_val = values[0]
    for price in values[1:]:
        ema_val = price * multiplier + ema_val * (1 - multiplier)
    return ema_val


def momentum(values: List[float], window: int = 10) -> Optional[float]:
    """动量指标：当前价格与 window 周期前的价格差"""
    if not values or len(values) < window + 1:
        return None
    return values[-1] - values[-window - 1]


def momentum_rate(values: List[float], window: int = 3) -> Optional[float]:
    """动量变化率（百分比）"""
    if not values or len(values) < window + 1:
        return None
    prev_price = values[-window - 1]
    if prev_price == 0:
        return None
    return (values[-1] - prev_price) / prev_price


def rsi(values: List[float], window: int = 14) -> Optional[float]:
    """相对强弱指标"""
    if not values or len(values) < window + 1:
        return None
    
    gains = []
    losses = []
    for i in range(1, len(values)):
        change = values[i] - values[i - 1]
        if change > 0:
            gains.append(change)
            losses.append(0)
        else:
            gains.append(0)
            losses.append(abs(change))
    
    avg_gain = sum(gains[-window:]) / window if gains else 0
    avg_loss = sum(losses[-window:]) / window if losses else 0
    
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def average(values: List[float]) -> Optional[float]:
    """简单平均"""
    if not values:
        return None
    return sum(values) / len(values)


def std_dev(values: List[float], window: int = 20) -> Optional[float]:
    """标准差"""
    if not values or len(values) < window:
        return None
    
    recent = values[-window:]
    mean = sum(recent) / len(recent)
    variance = sum((x - mean) ** 2 for x in recent) / len(recent)
    return variance ** 0.5


def atr(candles: List[dict], window: int = 14) -> Optional[float]:
    """平均真实波幅"""
    if not candles or len(candles) < window + 1:
        return None
    
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)
    
    return sum(true_ranges[-window:]) / window


def price_range(candles: List[dict]) -> dict:
    """日内价格范围统计"""
    if not candles:
        return {"high": 0.0, "low": 0.0, "close": 0.0}
    
    highs = [c["high"] for c in candles if c["high"] > 0]
    lows = [c["low"] for c in candles if c["low"] > 0]
    
    return {
        "high": max(highs) if highs else 0.0,
        "low": min(lows) if lows else 0.0,
        "close": candles[-1]["close"] if candles[-1]["close"] > 0 else 0.0,
    }
