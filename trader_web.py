import json
import logging
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from config import STATE_FILE, ensure_paths, RECORDS_DIR
from params import load_params, save_params, validate_param, get_param_metadata, get_param_categories

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

TEMPLATE = """
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>QQQ 自动交易仪表盘</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
      background: #f5f5f5;
    }
    .header {
      background: white;
      border-bottom: 1px solid #e0e0e0;
      padding: 0;
      box-shadow: 0 2px 8px rgba(0,0,0,0.05);
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .header-content {
      max-width: 1200px;
      margin: 0 auto;
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 20px;
    }
    .header h1 { font-size: 20px; color: #333; }
    .nav {
      display: flex;
      gap: 20px;
    }
    .nav a {
      text-decoration: none;
      padding: 8px 16px;
      border-radius: 4px;
      color: #666;
      cursor: pointer;
      transition: all 0.3s;
    }
    .nav a:hover { background: #f0f0f0; }
    .nav a.active { background: #0066cc; color: white; }
    
    .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
    
    .page { display: none; }
    .page.active { display: block; }
    
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
    .card {
      background: white;
      border-radius: 8px;
      padding: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
      border-left: 4px solid #0066cc;
    }
    .card h2 { font-size: 14px; color: #666; margin-bottom: 10px; }
    .card .value { font-size: 28px; font-weight: bold; color: #333; }
    .card.positive { border-left-color: #28a745; }
    .card.negative { border-left-color: #dc3545; }
    
    .status {
      display: inline-block;
      padding: 4px 12px;
      border-radius: 20px;
      font-size: 12px;
      font-weight: bold;
    }
    .status.connected { background: #d4edda; color: #155724; }
    .status.disconnected { background: #f8d7da; color: #721c24; }
    .status.running { background: #cfe2ff; color: #084298; }
    .status.stopped { background: #e2e3e5; color: #383d41; }
    
    table { width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    th { background: #f8f9fa; padding: 12px; text-align: left; font-weight: 600; color: #666; border-bottom: 1px solid #e0e0e0; }
    td { padding: 12px; border-bottom: 1px solid #e0e0e0; }
    tr:hover { background: #f9f9f9; }
    
    .signal { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .signal.call { background: #e8f4f8; color: #0066cc; }
    .signal.put { background: #f8e8e8; color: #cc0000; }
    .pnl { font-weight: bold; }
    .pnl.positive { color: #28a745; }
    .pnl.negative { color: #dc3545; }
    
    .section { margin-bottom: 30px; }
    .section h3 { margin-bottom: 15px; color: #333; }
    
    /* 参数表单样式 */
    .param-group {
      background: white;
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 20px;
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .param-group h3 {
      margin-bottom: 15px;
      color: #333;
      font-size: 16px;
      border-bottom: 2px solid #0066cc;
      padding-bottom: 10px;
    }
    .param-row {
      display: grid;
      grid-template-columns: 200px 1fr 200px;
      gap: 15px;
      align-items: end;
      margin-bottom: 15px;
      padding-bottom: 15px;
      border-bottom: 1px solid #f0f0f0;
    }
    .param-row:last-child { border-bottom: none; }
    
    .param-label {
      font-weight: 600;
      color: #333;
    }
    .param-hint {
      font-size: 12px;
      color: #999;
      margin-top: 4px;
    }
    .param-input {
      padding: 8px 12px;
      border: 1px solid #ddd;
      border-radius: 4px;
      font-size: 14px;
    }
    .param-input:focus {
      outline: none;
      border-color: #0066cc;
      box-shadow: 0 0 0 3px rgba(0, 102, 204, 0.1);
    }
    .param-value {
      text-align: right;
      color: #0066cc;
      font-weight: bold;
    }
    
    .button {
      padding: 10px 20px;
      border: none;
      border-radius: 4px;
      font-size: 14px;
      cursor: pointer;
      transition: all 0.3s;
      font-weight: 600;
    }
    .button.primary {
      background: #0066cc;
      color: white;
    }
    .button.primary:hover { background: #0052a3; }
    .button.secondary {
      background: #f0f0f0;
      color: #333;
    }
    .button.secondary:hover { background: #e0e0e0; }
    
    .button-group {
      display: flex;
      gap: 10px;
      margin-top: 20px;
    }
    
    .alert {
      padding: 12px 16px;
      border-radius: 4px;
      margin-bottom: 15px;
    }
    .alert.success {
      background: #d4edda;
      color: #155724;
      border: 1px solid #c3e6cb;
    }
    .alert.error {
      background: #f8d7da;
      color: #721c24;
      border: 1px solid #f5c6cb;
    }
    
    footer { text-align: right; color: #999; font-size: 12px; margin-top: 40px; padding: 20px; }
    a { color: #0066cc; text-decoration: none; }
    a:hover { text-decoration: underline; }
  </style>
  <script>
    function switchPage(pageName) {
      document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
      document.querySelectorAll('.nav a').forEach(a => a.classList.remove('active'));
      
      document.getElementById(pageName).classList.add('active');
      event.target.classList.add('active');
    }
    
    function updateParam(key) {
      const input = document.getElementById('param_' + key);
      const value = input.value;
      
      fetch('/api/update_param', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [key]: value })
      })
      .then(r => r.json())
      .then(data => {
        if (data.success) {
          showAlert('参数已保存', 'success');
          setTimeout(loadParams, 1000);
        } else {
          showAlert('保存失败: ' + (data.error || '未知错误'), 'error');
        }
      })
      .catch(e => showAlert('请求失败: ' + e, 'error'));
    }
    
    function loadParams() {
      fetch('/api/params')
        .then(r => r.json())
        .then(data => {
          Object.entries(data).forEach(([key, value]) => {
            const input = document.getElementById('param_' + key);
            if (input) {
              input.value = value;
              const display = input.parentElement.querySelector('.param-value');
              if (display) display.textContent = value;
            }
          });
        });
    }
    
    function showAlert(msg, type) {
      const alertDiv = document.createElement('div');
      alertDiv.className = 'alert ' + type;
      alertDiv.textContent = msg;
      document.body.insertBefore(alertDiv, document.body.firstChild);
      setTimeout(() => alertDiv.remove(), 3000);
    }
    
    function resetParams() {
      if (confirm('确认重置所有参数为默认值?')) {
        fetch('/api/reset_params', { method: 'POST' })
          .then(r => r.json())
          .then(data => {
            if (data.success) {
              showAlert('参数已重置', 'success');
              setTimeout(loadParams, 500);
            } else {
              showAlert('重置失败', 'error');
            }
          });
      }
    }
    
    window.addEventListener('load', loadParams);
  </script>
</head>
<body>
  <div class="header">
    <div class="header-content">
      <h1>📊 QQQ 0DTE 自动交易系统</h1>
      <div class="nav">
        <a class="active" onclick="switchPage('dashboard')">📈 仪表盘</a>
        <a onclick="switchPage('params')">⚙️ 参数配置</a>
      </div>
    </div>
  </div>
  
  <div class="container">
    <!-- 仪表盘页面 -->
    <div id="dashboard" class="page active">
      <div class="grid">
        <div class="card">
          <h2>连接状态</h2>
          <span class="status {{ 'connected' if state.connected else 'disconnected' }}">
            {{ '✓ 已连接' if state.connected else '✗ 已断开' }}
          </span>
        </div>
        <div class="card">
          <h2>运行状态</h2>
          <span class="status {{ 'running' if state.running else 'stopped' }}">
            {{ '▶ 运行中' if state.running else '⏸ 已停止' }}
          </span>
        </div>
        <div class="card">
          <h2>今日交易笔数</h2>
          <div class="value">{{ state.daily_trades }}/{{ max_trades }}</div>
        </div>
        <div class="card {{ 'positive' if state.daily_loss_rate >= 0 else 'negative' }}">
          <h2>日累计收益</h2>
          <div class="value pnl {{ 'positive' if state.daily_loss_rate >= 0 else 'negative' }}">
            {{ "%.2f%%" % (state.daily_loss_rate * 100) }}
          </div>
        </div>
        <div class="card">
          <h2>持仓状态</h2>
          {% if state.position %}
            <span class="signal {{ 'call' if state.position.direction == 'CALL' else 'put' }}">
              {{ '📈 ' + state.position.direction }}
            </span>
            <div style="margin-top: 8px; font-size: 12px; color: #666;">
              进场: ${{ "%.2f" % state.position.entry_price }}
            </div>
          {% else %}
            <span style="color: #999;">无</span>
          {% endif %}
        </div>
        <div class="card">
          <h2>最后信号</h2>
          <div style="font-size: 14px; color: #333;">
            {{ state.last_signal or '无' }}
          </div>
        </div>
      </div>

      <div class="section">
        <h3>📜 最近交易记录</h3>
        {% if records %}
          <table>
            <thead>
              <tr>
                <th>时间</th>
                <th>事件</th>
                <th>信号</th>
                <th>价格</th>
                <th>收益</th>
                <th>备注</th>
              </tr>
            </thead>
            <tbody>
              {% for record in records %}
                <tr>
                  <td><span class="time">{{ record.time }}</span></td>
                  <td>{{ record.event }}</td>
                  <td>
                    {% if record.get('signal') %}
                      <span class="signal {{ 'call' if record.signal == 'CALL' else 'put' }}">
                        {{ record.signal }}
                      </span>
                    {% elif record.get('reason') %}
                      <span style="color: #666;">{{ record.reason }}</span>
                    {% else %}
                      -
                    {% endif %}
                  </td>
                  <td>
                    {% if record.get('entry_price') %}
                      \${{ "%.2f" % record.entry_price }}
                    {% elif record.get('exit_price') %}
                      \${{ "%.2f" % record.exit_price }}
                    {% else %}
                      -
                    {% endif %}
                  </td>
                  <td>
                    {% if record.get('pnl_pct') is not none %}
                      <span class="pnl {{ 'positive' if record.pnl_pct >= 0 else 'negative' }}">
                        {{ "%.2f%%" % (record.pnl_pct * 100) }}
                      </span>
                    {% else %}
                      -
                    {% endif %}
                  </td>
                  <td>{{ record.get('quantity', '') }}</td>
                </tr>
              {% endfor %}
            </tbody>
          </table>
        {% else %}
          <p style="color: #999; text-align: center; padding: 40px;">暂无交易记录</p>
        {% endif %}
      </div>
    </div>
    
    <!-- 参数配置页面 -->
    <div id="params" class="page">
      <div style="margin-bottom: 20px;">
        <h2>策略参数配置</h2>
        <p style="color: #666; margin-top: 5px;">实时调整策略参数，保存后立即生效</p>
      </div>
      
      {% for category, params_list in categories.items() %}
        <div class="param-group">
          <h3>{{ category }}</h3>
          {% for param_key in params_list %}
            {% set meta = metadata[param_key] %}
            <div class="param-row">
              <div>
                <div class="param-label">{{ meta.description }}</div>
                {% if meta.hint %}
                  <div class="param-hint">💡 {{ meta.hint }}</div>
                {% endif %}
              </div>
              <div>
                {% if meta.type == 'string' and meta.options %}
                  <select id="param_{{ param_key }}" class="param-input" onchange="updateParam('{{ param_key }}')">
                    {% for opt in meta.options %}
                      <option value="{{ opt }}">{{ opt }}</option>
                    {% endfor %}
                  </select>
                {% else %}
                  <input 
                    type="text" 
                    id="param_{{ param_key }}" 
                    class="param-input"
                    onchange="updateParam('{{ param_key }}')"
                    placeholder="{{ meta.type }}"
                  >
                {% endif %}
              </div>
              <div class="param-value" id="value_{{ param_key }}">-</div>
            </div>
          {% endfor %}
        </div>
      {% endfor %}
      
      <div style="margin-top: 30px;">
        <button class="button primary" onclick="location.reload()">🔄 刷新页面</button>
        <button class="button secondary" onclick="resetParams()">↩️ 重置为默认值</button>
      </div>
    </div>
  </div>
  
  <footer>
    最后更新: {{ updated_at }} | 
    <a href="/">刷新</a> | 
    版本: v6.2 (参数配置版)
  </footer>
</body>
</html>
"""


def load_state() -> dict:
    ensure_paths()
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        logging.error("加载 state.json 失败: %s", e)
        return {}


def load_latest_records(limit: int = 20) -> list:
    ensure_paths()
    try:
        records = sorted(RECORDS_DIR.glob("record_*.json"), reverse=True)
        result = []
        for file in records[:limit]:
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
                result.append(data)
            except Exception as e:
                logging.error("读取记录文件失败 %s: %s", file, e)
        return result
    except Exception as e:
        logging.error("加载记录失败: %s", e)
        return []


@app.route("/")
def home() -> str:
    state = load_state()
    records = load_latest_records(20)
    
    # 获取参数和分类信息
    params = load_params()
    categories = get_param_categories()
    metadata = get_param_metadata()["metadata"]
    
    return render_template_string(
        TEMPLATE,
        state=state,
        records=records,
        categories=categories,
        metadata=metadata,
        updated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        max_trades=8,
    )


@app.route("/api/state")
def api_state():
    return jsonify(load_state())


@app.route("/api/records")
def api_records():
    return jsonify(load_latest_records(50))


@app.route("/api/params")
def api_params():
    """获取所有参数"""
    return jsonify(load_params())


@app.route("/api/update_param", methods=["POST"])
def api_update_param():
    """更新单个或多个参数"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "参数为空"})
        
        # 验证参数
        from params import validate_params, update_params
        valid, error = validate_params(data)
        if not valid:
            return jsonify({"success": False, "error": error})
        
        # 更新参数
        success, error = update_params(data)
        if success:
            logging.info("✓ 参数已更新: %s", list(data.keys()))
            return jsonify({"success": True, "updated": list(data.keys())})
        else:
            return jsonify({"success": False, "error": error or "更新失败"})
    
    except Exception as e:
        logging.error("更新参数失败: %s", e)
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/reset_params", methods=["POST"])
def api_reset_params():
    """重置所有参数为默认值"""
    try:
        from params import DEFAULT_PARAMS
        success = save_params(DEFAULT_PARAMS.copy())
        if success:
            logging.info("✓ 参数已重置为默认值")
            return jsonify({"success": True, "message": "参数已重置"})
        else:
            return jsonify({"success": False, "error": "重置失败"})
    except Exception as e:
        logging.error("重置参数失败: %s", e)
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/param_info")
def api_param_info():
    """获取参数元数据（用于前端验证和提示）"""
    metadata = get_param_metadata()
    return jsonify({
        "defaults": metadata["defaults"],
        "metadata": metadata["metadata"],
        "categories": get_param_categories(),
    })


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=False, threaded=True)
