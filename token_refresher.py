import requests
import os
import sys
import json
import time

ACCOUNTS_FILE = "accounts.json"

def refresh_all_tokens():
    """
    读取 accounts.json，遍历所有账户，刷新并更新 refresh_token。
    """
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"❌ 错误: 未找到 {ACCOUNTS_FILE}")
        sys.exit(1)

    print(f"📂 读取账户文件: {ACCOUNTS_FILE}...")
    
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 解析失败: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ 读取文件失败: {e}")
        sys.exit(1)

    has_updates = False
    
    print(f"🔍 发现 {len(data)} 个账户，开始轮询刷新...\n")

    for email, account in data.items():
        print(f"👉 正在处理: {email}")
        
        # 提取关键信息
        old_refresh_token = account.get("refresh_token")
        client_id = account.get("client_id")

        if not old_refresh_token:
            print(f"   ⚠️ 跳过: 缺少 refresh_token")
            continue
        
        if not client_id:
            print(f"   ⚠️ 跳过: 缺少 client_id")
            continue

        # 尝试刷新
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
                # access_token = json_resp.get("access_token") # 我们这里主要目的是保活，access_token 可按需使用

                if new_refresh_token:
                    # 仅更新 refresh_token，不修改其他字段
                    account["refresh_token"] = new_refresh_token
                    # 可选：更新一个 last_refreshed 时间戳，方便追踪
                    # account["last_refreshed_at"] = ... 
                    
                    has_updates = True
                    print(f"   ✅ 刷新成功！Token 已更新。")
                else:
                    print(f"   ⚠️ 刷新成功但未返回新 Refresh Token。")
            
            else:
                # 失败处理
                error_msg = response.text
                if "AADSTS70002" in error_msg:
                     print(f"   ❌ 失败: Azure 认为该应用是 Web App (需要 Client Secret)，但我们作为 Public Client 发起请求。请检查 Azure 注册类型。")
                elif "AADSTS70000" in error_msg:
                     print(f"   ❌ 失败: Token 可能已失效或过期。")
                else:
                     print(f"   ❌ 失败 (HTTP {response.status_code}): {error_msg}")

        except Exception as e:
            print(f"   ❌ 请求异常: {e}")
        
        # 礼貌性延时，避免被风控
        time.sleep(1)
        print("-" * 40)

    # 如果有任何更新，保存回文件
    if has_updates:
        print("\n💾 正在保存更新到 accounts.json ...")
        try:
            with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print("To 成功！所有有效的 Token 都已续期。")
        except Exception as e:
            print(f"❌ 保存文件失败: {e}")
    else:
        print("\nℹ️ 没有检测到任何 Token 更新 (可能全部失败或无需更新)。")

if __name__ == "__main__":
    refresh_all_tokens()
