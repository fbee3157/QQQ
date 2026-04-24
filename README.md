# 基於長橋 Python SDK，全自動交易 QQQ 0DTE 虛值期權


本系統僅供參考學習部署，具體交易策略還需要自己優化。
---

# QQQ 0DTE 自动交易系统（基于长桥 Python SDK）
本系统仅供参考学习部署，具体交易策略还需要自己优化。

---

## 一、策略说明

### 做什么
全自动交易 QQQ 当日到期（0DTE）期权，在美盘 9:30-15:50 期间自动检测信号、下单、持仓管理、平仓。

### 怎么做
两条信号路径同时运行：

1.  **趋势突破（顺势）**
    - 价格突破前 5 根 1 分钟 K 线的高点 → 买入 Call（做多）
    - 价格跌破前 5 根 1 分钟 K 线的低点 → 买入 Put（做空）
    - 4 层过滤：SMA20 趋势 + 量能确认 + 动量确认 + K 线实体

2.  **衰竭反转（逆势）**
    - 从日内高点回落≥0.2% → 买入 Call（抄底）
    - 从日内低点反弹≥0.2% → 买入 Put（逃顶）
    - 每天最多 1 次，防止频繁抄底

### 怎么管
**动态止盈：**
1.  亏损 25% → 止损全部平仓
2.  盈利 100% → 平仓一半（锁定利润）
3.  从最高盈利回撤 30% → 全部平仓
4.  持仓超过 15 分钟 → 超时平仓

**风控：**
- 每笔最小 10 张期权
- 日最大交易 8 笔
- 日亏损达 5% 停止交易

### 回测结果
| 指标 | 数值 |
| :--- | :--- |
| 总交易 | 761 笔 / 2.3 年 |
| 胜率 | 75.8% |
| 总收益 | +3111% |
| 年化收益 | 354.8% |
| 最大回撤 | 25.19% |

---

## 二、环境准备

### 1. 系统要求
- Python 3.10+
- Linux 或 WSL（Windows 原生不推荐）
- 长桥 API 密钥（需开通美股期权权限） 关于'longportapp'文档[https://open.longportapp.com/docs]

### 2. 安装依赖
```bash
pip install longbridge flask numpy scipy
```

---

## 三、获取代码
```bash
git clone https://github.com/fbee3157/QQQ.git
cd QQQ
```

---

## 四、配置密钥

### 1. 申请长桥 API
1.  访问 https://open.longportapp.com 注册账号
2.  创建应用，获取以下三个密钥：
    - `APP_KEY`
    - `APP_SECRET`
    - `ACCESS_TOKEN`
      
   <img width="772" height="465" alt="image" src="https://github.com/user-attachments/assets/3775c567-26d1-4f82-b015-6a60eddc0b82" />

3.  确保账户已开通美股期权交易权限
   <img width="1024" height="502" alt="image" src="https://github.com/user-attachments/assets/be0b9f92-9b3a-4340-b539-0b4f3a0db727" />


### 2. 创建 `.env` 文件
在项目目录创建 `.env` 文件，填入你自己的密钥：
```env
LONGPORT_APP_KEY=你的 APP_KEY
LONGPORT_APP_SECRET=你的 APP_SECRET
LONGPORT_ACCESS_TOKEN=你的 ACCESS_TOKEN
```

> ⚠️ **重要**：`.env` 文件绝对不能提交到 Git！

### 3. 验证密钥
```python
import os

with open('.env') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"'))

from longbridge.openapi import Config, QuoteContext

config = Config.from_apikey_env()
ctx = QuoteContext(config)
quotes = ctx.quote(['QQQ.US'])
print(f"QQQ: ${float(quotes[0].last_done):.2f}")
```
如果输出 QQQ 价格，说明密钥配置成功。

---

## 五、启动系统

### 方式一：直接启动
```bash
# 终端 1：启动交易引擎
PYTHONUNBUFFERED=1 python live_trader.py

# 终端 2：启动 Web 仪表盘
PYTHONUNBUFFERED=1 python trader_web.py
```

### 方式二：后台启动
```bash
# 后台启动交易引擎
nohup PYTHONUNBUFFERED=1 python live_trader.py > trader.log 2>&1 &

# 后台启动 Web 仪表盘
nohup PYTHONUNBUFFERED=1 python trader_web.py > web.log 2>&1 &
```

### 方式三：watchdog 守护（推荐）
```bash
python watchdog.py
```
`watchdog` 会自动管理 `live_trader.py` 的生命周期，崩溃后自动重启。

---

## 六、验证部署

### 1. 检查进程
```bash
ps aux | grep -E 'live_trader|trader_web' | grep -v grep
```
应该看到两个 Python 进程在运行。

### 2. 检查状态文件
```bash
python -c "import json; d = json.load(open('state.json')); print(f'连接: {d[\"connected\"]}'); print(f'运行: {d[\"running\"]}'); print(f'K 线数: {d[\"candle_count\"]}')"
```

### 3. 访问 Web 仪表盘
浏览器打开 `http://127.0.0.1:8080`

---

## 七、文件说明

| 文件 | 说明 |
| :--- | :--- |
| `live_trader.py` | 核心交易引擎 |
| `trader_web.py` | Web 仪表盘 |
| `watchdog.py` | 守护进程 |
| `update_gist.py` | 同步交易记录 |
| `.env` | 密钥配置（不入库） |
| `state.json` | 实时状态（自动生成） |
| `today.csv` | 当日 K 线（自动生成） |
| `records/*.json` | 交易记录（自动生成） |

---

## 八、常见问题

**Q: `ImportError: No module named 'longbridge'`**
```bash
pip install longbridge
```

**Q: 长桥 API 连接失败**
检查：
1.  `.env` 文件是否存在且格式正确
2.  环境变量名是 `LONGPORT_*` 不是 `LONGBRIDGE_*`
3.  使用 `Config.from_apikey_env()` 不是 `Config.from_env()`

**Q: 信号检测无输出**
检查：
1.  `state.json` 的 `candle_count` 是否 > 0
2.  当前时间是否在交易窗口内（美东 09:35-15:50）
3.  是否有持仓阻塞

**Q: 期权下单失败**
检查：
1.  期权合约代码格式是否正确（`.US` 后缀 + 整数行权价）
2.  到期日是否用美东时间生成
3.  账户是否有期权交易权限
    当你拥有正确的报价权限时，情况可能如下：
   <img width="718" height="473" alt="image" src="https://github.com/user-attachments/assets/b37b65f6-8b20-41f0-a95b-3d69ce7963d9" />


---

## 九、策略参数
如需调整策略，修改 `live_trader.py` 中的 `CONFIG`：
```python
CONFIG = {
    'sl': 0.25,          # 止损 25%
    'lookback': 5,       # 突破窗口 5 根 K 线
    'vol_mult': 0.8,     # 量能倍数
    'min_body': 0.0003,  # K 线实体 0.03%
    'max_trades': 8,     # 日最大交易
    'start_time': '09:35', # 入场开始（美东）
    'end_time': '15:50', # 入场结束（美东）
    # ... 其他参数见代码注释
}
```

> ⚠️ **修改后必须同步修改 `trader_web.py` 中的 `CONFIG`，然后重启两个进程。**

---

## 开源地址
https://github.com/fbee3157/QQQ

---

## 免责声明
本系统仅供学习研究使用。期权交易具有高风险，可能导致本金损失。作者不对使用本系统产生的任何损失负责。

---
# QQQ
