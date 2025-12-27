import json
import os
import psycopg2
import sys
import logging
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Configuration
ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")
REPORT_FILE = os.path.join("logs", "sync_report.json")
DB_URL = os.environ.get("DB_URL")

if not DB_URL:
    logger.error("❌ Error: DB_URL not found in environment variables.")
    # 我们不直接退出了，而是生成一个错误报告，让 scheduler 知道
    # sys.exit(1) 

def ensure_logs_dir():
    if not os.path.exists("logs"):
        os.makedirs("logs")

def load_local_accounts():
    """读取本地 accounts.json"""
    if not os.path.exists(ACCOUNTS_FILE):
        logger.error(f"❌ 本地文件不存在: {ACCOUNTS_FILE}")
        return {}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ 读取本地文件失败: {e}")
        return {}

def save_report(stats, error=None):
    report = {
        "timestamp": datetime.now().isoformat(),
        "stats": stats,
        "error": str(error) if error else None
    }
    try:
        with open(REPORT_FILE, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"📝 同步报告已写入: {REPORT_FILE}")
    except Exception as e:
        logger.error(f"❌ 写入报告失败: {e}")

def sync_to_db():
    ensure_logs_dir()
    
    stats = {
        "inserted": 0,
        "updated": 0,
        "skipped": 0
    }

    if not DB_URL:
        save_report(stats, "DB_URL not configured")
        return

    local_data = load_local_accounts()
    if not local_data:
        logger.warning("⚠ 没有本地数据，结束同步。")
        save_report(stats, "No local data found")
        return

    logger.info(f"🔄 开始同步 {len(local_data)} 个本地账户到数据库...")

    conn = None
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        for email, info in local_data.items():
            local_refresh_token = info.get("refresh_token")
            local_client_id = info.get("client_id")
            
            if not local_refresh_token or not local_client_id:
                logger.warning(f"⚠️ 跳过不完整数据: {email}")
                continue

            # 1. 查询数据库是否存在 (忽略大小写)
            cur.execute("SELECT data, email FROM account_backups WHERE LOWER(email) = LOWER(%s)", (email,))
            row = cur.fetchone()

            if row:
                # --- 情况 B: 数据库已存在 (增量融合) ---
                db_data_str = row[0]
                db_actual_email = row[1]

                try:
                    db_json = json.loads(db_data_str)
                except:
                    db_json = {} 

                # 检查是否需要更新
                needs_update = False
                
                if db_json.get("refresh_token") != local_refresh_token:
                    db_json["refresh_token"] = local_refresh_token
                    needs_update = True
                
                if db_json.get("client_id") != local_client_id:
                    db_json["client_id"] = local_client_id
                    needs_update = True
                
                if needs_update:
                    new_data_str = json.dumps(db_json, ensure_ascii=False)
                    cur.execute("""
                        UPDATE account_backups 
                        SET data = %s, last_modified_at = NOW() 
                        WHERE email = %s
                    """, (new_data_str, db_actual_email))
                    logger.info(f"✅ [更新] {db_actual_email}")
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1

            else:
                # --- 情况 A: 数据库不存在 (新增) ---
                new_json = {
                    "refresh_token": local_refresh_token,
                    "client_id": local_client_id
                }
                new_data_str = json.dumps(new_json, ensure_ascii=False)
                
                cur.execute("""
                    INSERT INTO account_backups (email, data, last_modified_at)
                    VALUES (%s, %s, NOW())
                """, (email, new_data_str))
                logger.info(f"🆕 [新增] {email}")
                stats["inserted"] += 1

        conn.commit()
        cur.close()
        
        logger.info("-" * 50)
        logger.info(f"🎉 同步完成! 新增: {stats['inserted']}, 更新: {stats['updated']}, 跳过: {stats['skipped']}")
        logger.info("-" * 50)
        
        save_report(stats)

    except Exception as e:
        logger.error(f"❌ 数据库操作失败: {e}")
        save_report(stats, str(e))
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    sync_to_db()
