import logging
import subprocess
import sys
import time
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [watchdog] %(levelname)s %(message)s",
)

SCRIPT_DIR = Path(__file__).resolve().parent
TRADE_SCRIPT = SCRIPT_DIR / "live_trader.py"
WEB_SCRIPT = SCRIPT_DIR / "trader_web.py"
RESTART_DELAY = 5


def start_process(script_path):
    """启动子进程"""
    try:
        return subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        logging.error("启动进程失败 %s: %s", script_path, e)
        return None


def monitor_processes(processes):
    """监控进程，自动重启已退出的进程"""
    for name, proc in list(processes.items()):
        if proc is None:
            logging.warning("%s 进程无效，尝试重启...", name)
            script = TRADE_SCRIPT if name == "trade" else WEB_SCRIPT
            processes[name] = start_process(script)
        elif proc.poll() is not None:
            exit_code = proc.returncode
            logging.warning("%s 进程已退出 (code: %d)，准备重启...", name, exit_code)
            script = TRADE_SCRIPT if name == "trade" else WEB_SCRIPT
            processes[name] = start_process(script)


def main():
    logging.info("===== QQQ 交易守护进程启动 =====")
    processes = {
        "trade": start_process(TRADE_SCRIPT),
        "web": start_process(WEB_SCRIPT),
    }

    if not all(processes.values()):
        logging.error("无法启动所有进程，退出。")
        sys.exit(1)

    logging.info("✓ 交易引擎已启动 (PID: %d)", processes["trade"].pid)
    logging.info("✓ Web 仪表盘已启动 (PID: %d)", processes["web"].pid)

    try:
        while True:
            monitor_processes(processes)
            time.sleep(RESTART_DELAY)
    except KeyboardInterrupt:
        logging.info("守护进程收到停止信号，正在关闭子进程...")
        for name, proc in processes.items():
            if proc and proc.poll() is None:
                logging.info("正在关闭 %s...", name)
                proc.terminate()
        
        # 等待进程退出
        for name, proc in processes.items():
            if proc:
                try:
                    proc.wait(timeout=10)
                    logging.info("✓ %s 已关闭", name)
                except subprocess.TimeoutExpired:
                    logging.warning("%s 未在时限内关闭，强制杀死。", name)
                    proc.kill()
        
        logging.info("===== 守护进程已停止 =====")


if __name__ == "__main__":
    main()

