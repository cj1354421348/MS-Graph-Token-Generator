import json
import os
import psycopg2
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")
DB_URL = os.environ.get("DB_URL")

if not DB_URL:
    print("❌ Error: DB_URL not found in environment variables.")
    sys.exit(1)

def load_local_accounts():
    """读取本地 accounts.json"""
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"❌ 本地文件不存在: {ACCOUNTS_FILE}")
        return {}
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ 读取本地文件失败: {e}")
        return {}

def sync_to_db():
    local_data = load_local_accounts()
    if not local_data:
        print("⚠ 没有本地数据，结束同步。")
        return

    print(f"🔄 开始同步 {len(local_data)} 个本地账户到数据库...")

    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        
        updated_count = 0
        inserted_count = 0
        skipped_count = 0

        for email, info in local_data.items():
            local_refresh_token = info.get("refresh_token")
            local_client_id = info.get("client_id")
            
            if not local_refresh_token or not local_client_id:
                print(f"⚠️ 跳过不完整数据: {email}")
                continue

            # 1. 查询数据库是否存在 (忽略大小写)
            # 我们同时取回 email 字段，以便后续 UPDATE 时使用数据库里实际存储的大小写格式
            cur.execute("SELECT data, email FROM account_backups WHERE LOWER(email) = LOWER(%s)", (email,))
            row = cur.fetchone()

            if row:
                # --- 情况 B: 数据库已存在 (增量融合) ---
                db_data_str = row[0]
                db_actual_email = row[1] # 数据库里存储的真实邮箱 (可能与 email 大小写不同)

                try:
                    db_json = json.loads(db_data_str)
                except:
                    db_json = {} #如果数据库里原来的不是json，就初始化为空

                # 检查是否需要更新
                needs_update = False
                
                if db_json.get("refresh_token") != local_refresh_token:
                    db_json["refresh_token"] = local_refresh_token
                    needs_update = True
                
                if db_json.get("client_id") != local_client_id:
                    db_json["client_id"] = local_client_id
                    needs_update = True
                
                if needs_update:
                    # 执行更新 (注意 WHERE 使用 db_actual_email)
                    new_data_str = json.dumps(db_json, ensure_ascii=False)
                    cur.execute("""
                        UPDATE account_backups 
                        SET data = %s, last_modified_at = NOW() 
                        WHERE email = %s
                    """, (new_data_str, db_actual_email))
                    print(f"✅ [更新] {db_actual_email} (匹配本地 {email})")
                    updated_count += 1
                else:
                    # 数据一致，跳过
                    # print(f"zz [跳过] {db_actual_email} (数据一致)") 
                    skipped_count += 1

            else:
                # --- 情况 A: 数据库不存在 (新增) ---
                # 构造初始 Json (只包含我们知道的信息)
                new_json = {
                    "refresh_token": local_refresh_token,
                    "client_id": local_client_id
                }
                new_data_str = json.dumps(new_json, ensure_ascii=False)
                
                cur.execute("""
                    INSERT INTO account_backups (email, data, last_modified_at)
                    VALUES (%s, %s, NOW())
                """, (email, new_data_str))
                print(f"🆕 [新增] {email}")
                inserted_count += 1

        conn.commit()
        cur.close()
        conn.close()
        
        print("-" * 50)
        print(f"🎉 同步完成!")
        print(f"🆕 新增: {inserted_count}")
        print(f"✅ 更新: {updated_count}")
        print(f"⏭️ 跳过: {skipped_count} (无变化)")
        print("-" * 50)

    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")

if __name__ == "__main__":
    sync_to_db()
