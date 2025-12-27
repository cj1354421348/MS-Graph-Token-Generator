import requests
import os
import sys
import json
import time
from datetime import datetime
import logging
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

ACCOUNTS_FILE = "accounts.json"
REPORT_FILE = os.path.join("logs", "refresh_report.json")

def ensure_logs_dir():
    if not os.path.exists("logs"):
        os.makedirs("logs")

def refresh_all_tokens():
    """
    读取 accounts.json，遍历所有账户，刷新并更新 refresh_token。
    """
    ensure_logs_dir()
    
    if not os.path.exists(ACCOUNTS_FILE):
        logger.error(f"❌ 错误: 未找到 {ACCOUNTS_FILE}")
        sys.exit(1)

    logger.info(f"📂 读取账户文件: {ACCOUNTS_FILE}...")
    
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"❌ 读取文件失败: {e}")
        # 这种严重错误不用跑了，直接写失败报告
        save_report(0, 0, [f"Fatal: {str(e)}"])
        sys.exit(1)

    has_updates = False
    total_accounts = len(data)
    success_count = 0
    failed_details = [] 
    
    logger.info(f"🔍 发现 {total_accounts} 个账户，开始轮询刷新...\n")

    for email, account in data.items():
        logger.info(f"👉 正在处理: {email}")
        
        old_refresh_token = account.get("refresh_token")
        client_id = account.get("client_id")

        if not old_refresh_token:
            logger.warning(f"   ⚠️ 跳过: 缺少 refresh_token")
            continue
        
        if not client_id:
            logger.warning(f"   ⚠️ 跳过: 缺少 client_id")
            continue

        url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
        payload = {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": old_refresh_token,
        }

        try:
            response = requests.post(url, data=payload)
            
            if response.status_code == 200:
                json_resp = response.json()
                new_refresh_token = json_resp.get("refresh_token")

                if new_refresh_token:
                    account["refresh_token"] = new_refresh_token
                    account["last_refreshed_at"] = datetime.now().isoformat()
                    has_updates = True
                    success_count += 1
                    logger.info(f"   ✅ 刷新成功！")
                else:
                    msg = "刷新成功 but no refresh_token return"
                    logger.warning(f"   ⚠️ {msg}")
                    failed_details.append({"email": email, "reason": msg})
            else:
                simple_error = f"HTTP {response.status_code}"
                error_msg = response.text
                if "AADSTS70002" in error_msg:
                    simple_error = "Client Secret Required"
                elif "AADSTS70000" in error_msg:
                    simple_error = "Token Invalid/Expired"
                
                logger.error(f"   ❌ 失败: {simple_error}")
                failed_details.append({"email": email, "reason": f"{simple_error} - {error_msg[:50]}..."})

        except Exception as e:
            logger.error(f"   ❌ 请求异常: {e}")
            failed_details.append({"email": email, "reason": str(e)})
        
        time.sleep(1)

    if has_updates:
        logger.info("\n💾 正在保存更新到 accounts.json ...")
        try:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info("To 成功！")
        except Exception as e:
            logger.error(f"❌ 保存文件失败: {e}")
            failed_details.append({"email": "SYSTEM", "reason": f"Save Error: {str(e)}"})

    # 保存执行报告供 scheduler 读取
    save_report(total_accounts, success_count, failed_details)

def save_report(total, success, failed_list):
    report = {
        "timestamp": datetime.now().isoformat(),
        "total": total,
        "success": success,
        "failed": failed_list
    }
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"📝 报告已写入: {REPORT_FILE}")
    except Exception as e:
        logger.error(f"❌ 写入报告失败: {e}")

if __name__ == "__main__":
    refresh_all_tokens()
