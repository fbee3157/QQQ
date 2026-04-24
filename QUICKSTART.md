# 快速参考卡 (Cheat Sheet)

## ⚡ 5 分钟快速启动

### 第1步：克隆和配置
```bash
# 克隆项目
git clone https://github.com/fbee3157/QQQ.git
cd QQQ

# 安装依赖
pip install -r requirements.txt

# 配置密钥
cp .env.example .env
# 编辑 .env，填入:
# LONGPORT_APP_KEY=你的APP_KEY
# LONGPORT_APP_SECRET=你的APP_SECRET
# LONGPORT_ACCESS_TOKEN=你的ACCESS_TOKEN
```

### 第2步：验证配置
```bash
python -c "
import os
with open('.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            os.environ.setdefault(*line.strip().split('=', 1))

from longbridge.openapi import Config, QuoteContext
config = Config.from_apikey_env()
ctx = QuoteContext(config)
quotes = ctx.quote(['QQQ.US'])
print(f'✓ QQQ: \${float(quotes[0].last_done):.2f}')
"
```

### 第3步：启动系统
```bash
# 终端1：启动交易引擎
python live_trader.py

# 终端2：启动 Web 仪表盘
python trader_web.py

# 或使用守护进程（自动管理两个进程）
# python watchdog.py
```

### 第4步：打开仪表盘
浏览器打开 `http://127.0.0.1:8080`

---

## 📊 系统架构速览

```
┌─────────────────────────────────────┐
│   Web Dashboard (Flask)             │  ← 访问 :8080
│   - 实时状态                        │
│   - 交易记录表                      │
│   - REST API (/api/state, records)  │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│  Live Trader (核心交易引擎)          │
│  - 信号生成                          │
│  - 下单/平仓                         │
│  - 持仓管理                          │
│  - 风控管理                          │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│  Longbridge API (长桥)              │
│  - 获取 K 线数据                    │
│  - 执行交易                         │
│  - 获取行情                         │
└─────────────────────────────────────┘
```

---

## 🎯 策略速览

### 两条信号路径

#### 信号1：趋势突破 (顺势)
```
检测到: 价格突破前 5 根 K 线高点 + 多个过滤条件
动作: 买入 Call（做多）

检测到: 价格跌破前 5 根 K 线低点 + 多个过滤条件
动作: 买入 Put（做空）
```

#### 信号2：衰竭反转 (逆势)
```
检测到: 从日内高点回落 ≥ 0.2%
动作: 买入 Call（抄底）

检测到: 从日内低点反弹 ≥ 0.2%
动作: 买入 Put（逃顶）
```

### 止盈管理 (4 层)

| 条件 | 动作 | 优先级 |
|------|------|--------|
| 亏损 ≥ 25% | 立即平仓 | 最高 ⭐ |
| 持仓 > 15 分钟 | 立即平仓 | 高 ⭐⭐ |
| 盈利 ≥ 100% | 平仓一半 | 中 ⭐⭐⭐ |
| 最高盈利回撤 ≥ 30% | 全部平仓 | 低 ⭐⭐⭐⭐ |

### 风控管理

```
单笔交易: 最少 10 张期权
日最大交易: 8 笔
日亏损限制: 5% (达到时停止交易)
交易窗口: 美东 09:35-15:50
```

---

## 📁 关键文件说明

| 文件 | 作用 | 何时需要 |
|------|------|----------|
| `.env` | API 密钥配置 | 首次启动 |
| `state.json` | 实时运行状态 | 自动生成 |
| `records/*.json` | 交易记录 | 自动生成 |
| `config.py` | 参数加载 | 修改参数时 |
| `live_trader.py` | 交易引擎 | 优化策略时 |
| `trader_web.py` | Web 仪表盘 | 自定义 UI 时 |

---

## 🔧 常用命令

### 查看实时状态
```bash
# 查看状态文件
cat state.json | python -m json.tool

# 查看交易记录数
ls records/ | wc -l

# 查看最新交易
ls -lt records/ | head -5
```

### 调整参数
编辑 `live_trader.py` 中的 CONFIG 字典，常见参数：

```python
CONFIG = {
    "sl": 0.25,              # 止损率（调小=激进，调大=保守）
    "tp_partial_pct": 1.0,   # 部分止盈点（调大=等待更高收益）
    "vol_mult": 0.8,         # 量能倍数（调小=更多交易，调大=更少假信号）
    "max_trades": 8,         # 日最大交易笔数
    "daily_limit": 0.05,     # 日亏损限制（5% = 5000 USD/100K 账户）
    "check_interval": 20,    # 检测间隔（秒）
}
```

### 导出交易记录
```bash
# 导出本周记录
find records/ -mtime -7 -name "*.json" > weekly_trades.txt

# 汇总成 CSV
python << 'EOF'
import json, glob
from datetime import datetime

records = []
for f in sorted(glob.glob('records/*.json')):
    data = json.load(open(f))
    records.append(data)

# 导出为 CSV
import csv
with open('trades.csv', 'w') as f:
    w = csv.DictWriter(f, fieldnames=['time', 'event', 'signal', 'price', 'pnl_pct', 'quantity'])
    w.writeheader()
    for r in records:
        w.writerow({
            'time': r.get('time'),
            'event': r.get('event'),
            'signal': r.get('signal'),
            'price': r.get('entry_price') or r.get('exit_price'),
            'pnl_pct': r.get('pnl_pct', ''),
            'quantity': r.get('quantity'),
        })

print("✓ 已导出 trades.csv")
EOF
```

---

## 📈 监控关键指标

在 Web 仪表盘上关注：

| 指标 | 正常范围 | 警告 |
|------|---------|------|
| 连接状态 | 已连接 ✓ | 已断开 ✗ |
| 运行状态 | 运行中 ▶ | 已停止 ⏸ |
| 日成交数 | 0-8 笔 | >8 超限 |
| 日收益率 | ±10% | <-5% 停止 |
| 持仓状态 | Call/Put | 无 (正常) |

---

## 🚨 故障速查表

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 连接失败 | API 密钥错误 | 检查 .env 中的 LONGPORT_* |
| 信号无输出 | K 线数据不足 | 等待 5+ 分钟数据积累 |
| | 不在交易窗口 | 检查时间是否 09:35-15:50 |
| | 已有持仓 | 等待前一笔交易平仓 |
| 下单失败 | 账户无期权权限 | 联系长桥开通权限 |
| | 行权价不合规 | 系统自动调整到 ±$2 范围 |
| 仪表盘无法访问 | 端口占用 | 修改 trader_web.py 中的 port |
| 进程自动退出 | 长桥 API 超时 | 检查网络连接 / 使用 watchdog.py |

---

## 💡 性能优化建议

### 提高成功率
```python
CONFIG = {
    "vol_mult": 0.8,      # ↓ 降低量能要求
    "min_body": 0.0001,   # ↓ 降低 K 线实体要求
    "lookback": 3,        # ↓ 缩短突破窗口（更敏感）
}
```

### 提高利润
```python
CONFIG = {
    "tp_partial_pct": 1.5,  # ↑ 等待 150% 利润再平一半
    "tp_trail_drop": 0.40,  # ↑ 回撤 40% 再平仓
    "sl": 0.30,             # ↑ 扩大止损到 30%
}
```

### 降低风险
```python
CONFIG = {
    "vol_mult": 1.2,        # ↑ 提高量能要求
    "min_body": 0.0005,     # ↑ 提高 K 线实体要求
    "daily_limit": 0.03,    # ↓ 日亏损限制改为 3%
    "max_trades": 5,        # ↓ 减少日交易笔数
}
```

---

## 🎓 回测数据解读

从 `references/backtest-results.md` 查看：

```
总交易: 761 笔
胜率: 75.8%
年化收益: 354.8%
最大回撤: 25.19%

→ 这意味着:
  - 平均 3-4 笔交易中赚 3 笔
  - 年投资 100K 能赚 354.8K（前提是严格执行策略）
  - 最坏情况下下跌 25.19%（需要足够风险承受力）
```

---

## 📞 常见问题

**Q: 如何修改交易标的?**
```python
# 在 .env 中添加
TRADE_SYMBOL=SPY.US  # 改为 SPY
```

**Q: 如何提高每笔交易的张数?**
```python
# 在 live_trader.py 的 CONFIG 中
MIN_CONTRACTS=20  # 改为 20 张
```

**Q: 如何每天自动备份交易记录?**
```bash
# 添加 cron 任务 (Linux/WSL)
0 16 * * * python /path/to/update_gist.py
```

**Q: 可以同时交易多个标的吗?**
当前版本仅支持单个标的。多标的支持在开发中。

---

## 📚 进阶参考

- 详细参数说明：`references/config.md`
- 部署指南：`references/deployment.md`
- 开发文档：`README_DEV.md`
- 回测结果：`references/backtest-results.md`

---

最后更新：2026-04-24 | 版本：v26.4.24
