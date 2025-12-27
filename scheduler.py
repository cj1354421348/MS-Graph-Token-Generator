import time
import signal
import sys
import logging
import subprocess
import threading
import os
import json
from datetime import datetime # 添加 datetime
from dotenv import load_dotenv
import notify

# 加载环境变量
load_dotenv()

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 优雅退出的标志位
shutdown_event = threading.Event()

REFRESH_REPORT = os.path.join("logs", "refresh_report.json")
SYNC_REPORT = os.path.join("logs", "sync_report.json")

def signal_handler(signum, frame):
    """
    捕获 SIGINT (Ctrl+C) 和 SIGTERM (Docker stop) 信号
    """
    signame = signal.Signals(signum).name
    logging.info(f"🛑 接收到信号 {signame} ({signum})，正在准备停止...")
    shutdown_event.set()

def run_script(script_name):
    """
    每次调用子进程运行脚本，确保环境隔离，避免 sys.exit() 影响主进程
    """
    if shutdown_event.is_set():
        return False

    script_path = os.path.join(os.path.dirname(__file__), script_name)
    
    if not os.path.exists(script_path):
        logging.error(f"❌ 找不到文件: {script_name}")
        return False

    try:
        logging.info(f"🚀 启动任务: {script_name}")
        # flush=True 确保日志没被缓冲
        start_time = time.time()
        
        # 使用当前 python 解释器调用子脚本
        result = subprocess.run(
            [sys.executable, "-u", script_path], 
            check=False
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            logging.info(f"✅ 任务成功: {script_name} (耗时 {duration:.2f}s)")
            return True
        else:
            logging.error(f"❌ 任务失败: {script_name} (退出码 {result.returncode}, 耗时 {duration:.2f}s)")
            return False
            
    except Exception as e:
        logging.error(f"❌ 无法执行 {script_name}: {e}")
        return False

def collect_and_notify():
    """
    读取 token_refresher 和 sync_db 的运行报告，发送汇总通知
    """
    refresh_data = {}
    sync_data = {}
    
    # 1. 读取 Refresh 报告
    if os.path.exists(REFRESH_REPORT):
        try:
            with open(REFRESH_REPORT, "r", encoding="utf-8") as f:
                refresh_data = json.load(f)
        except Exception as e:
            logging.error(f"读取 Refresh 报告失败: {e}")
            refresh_data = {"error": str(e)}
    else:
        refresh_data = {"error": "Report file not found"}

    # 2. 读取 Sync 报告
    if os.path.exists(SYNC_REPORT):
        try:
            with open(SYNC_REPORT, "r", encoding="utf-8") as f:
                sync_data = json.load(f)
        except Exception as e:
            logging.error(f"读取 Sync 报告失败: {e}")
            sync_data = {"error": str(e)}
    else:
        sync_data = {"error": "Report file not found"}

    # 3. 综合判断状态
    level = "info"
    title_suffix = ""
    
    r_failed_list = refresh_data.get("failed", [])
    r_total = refresh_data.get("total", 0)
    r_success = refresh_data.get("success", 0)
    
    s_stats = sync_data.get("stats", {})
    s_error = sync_data.get("error")

    # 逻辑: 
    # - 任何脚本执行层面的 error (如报告丢失, sync_db 挂了) -> Error
    # - Refresh 有失败 -> Error (重要业务)
    # - Sync 正常但有跳过不算错 -> Success
    
    if refresh_data.get("error") or s_error:
        level = "error"
        title_suffix = "执行异常"
    elif r_failed_list:
        if r_success == 0 and r_total > 0:
            level = "error"
            title_suffix = "全部刷新失败"
        else:
            level = "warning"
            title_suffix = "部分刷新失败"
    else:
        level = "success"
        title_suffix = "执行成功"

    if level == "success":
        title = f"✅ MS Graph 任务完成"
        content = (
            f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"------------------\n"
            f"🔄 Token刷新: {r_success}/{r_total} 成功\n"
            f"💾 DB同步: 新增 {s_stats.get('inserted',0)}, 更新 {s_stats.get('updated',0)}\n"
            f"状态: 所有服务运行正常。"
        )
    else:
        title = f"⚠️ MS Graph 任务: {title_suffix}"
        content = f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        
        # 刷新部分详情
        content += f"------------------\n[Token 刷新]\n"
        if refresh_data.get("error"):
             content += f"异常: {refresh_data.get('error')}\n"
        else:
             content += f"成功: {r_success}/{r_total}\n"
             if r_failed_list:
                 content += f"失败详情 ({len(r_failed_list)}):\n"
                 for item in r_failed_list[:5]: # 最多显示5条
                     content += f"- {item.get('email')}: {item.get('reason')}\n"

        # 同步部分详情
        content += f"------------------\n[DB 同步]\n"
        if s_error:
            content += f"异常: {s_error}\n"
        elif sync_data.get("error"): # 兼容旧逻辑
             content += f"异常: {sync_data.get('error')}\n"
        else:
            content += f"新增: {s_stats.get('inserted',0)}, 更新: {s_stats.get('updated',0)}, 跳过: {s_stats.get('skipped',0)}\n"

    logging.info(f"📡 发送综合通知 ({level})...")
    notify.send(title, content, level)


def main():
    # 注册信号处理
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logging.info("🤖 自动刷新调度器已启动 (PID: {})".format(os.getpid()))

    while not shutdown_event.is_set():
        logging.info("⏰ 开始执行本轮任务...")
        
        # 1. 刷新 Token
        run_script("token_refresher.py")
        
        # 2. 同步数据库
        run_script("sync_db.py")
        
        # 3. 收集报告并发送汇总通知
        if not shutdown_event.is_set():
            collect_and_notify()
        
        if shutdown_event.is_set():
            break

        # 休眠 7 天 (604800 秒)
        SLEEP_SECONDS = 604800
        logging.info(f"😴 本轮任务结束，进入休眠 {SLEEP_SECONDS} 秒 (7天)...")
        
        # 使用 wait 进行休眠，支持信号唤醒退出
        is_stopped = shutdown_event.wait(timeout=SLEEP_SECONDS)
        
        if is_stopped:
            logging.info("⚡ 休眠被中断，准备退出。")
            break

    logging.info("👋 调度器已安全退出。Bye!")

if __name__ == "__main__":
    main()
