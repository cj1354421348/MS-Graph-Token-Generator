import requests
import os
from dotenv import load_dotenv

# 加载环境配置
load_dotenv()

CLIENT_ID = os.environ.get("CLIENT_ID")
if not CLIENT_ID:
    print("❌ 错误: 未在 .env 中找到 CLIENT_ID")
    exit(1)

print("--- Microsoft Graph Refresh Token 验证工具 ---")
print(f"正在使用 Client ID: {CLIENT_ID}")
print("此工具将尝试使用 Refresh Token 获取新的 Access Token。")
print("如果成功，说明 Token 有效且适合 Public Client 模式。")
print("------------------------------------------------")

# 获取用户输入
refresh_token = input("请粘贴你的 Refresh Token (按回车确认): ").strip()

if not refresh_token:
    print("❌ 未输入 Token，程序退出。")
    exit(1)

# 构造请求
url = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
data = {
    "client_id": CLIENT_ID,
    "grant_type": "refresh_token",
    "refresh_token": refresh_token,
    # 注意：Public Client 刷新时通常不需要 scope，或者使用默认 scope
    # 但为了保险，我们可以不传，或者传原本的
}

print("\n🚀 正在向微软发送请求...")

try:
    response = requests.post(url, data=data)
    
    print(f"HTTP 状态码: {response.status_code}")
    
    if response.status_code == 200:
        json_resp = response.json()
        print("\n✅ 验证成功！Token 有效！")
        print(f"Access Token (前30字符): {json_resp.get('access_token', '')[:30]}...")
        print(f"新的 Refresh Token (前30字符): {json_resp.get('refresh_token', '')[:30]}...")
        print("\n结论: 你的 Token 没有任何问题。")
        print("如果 outlook_manager 仍然报错，请检查代码是否错误地添加了 client_secret 参数，")
        print("或者 outlook_manager 是否使用了不同的 Client ID。")
    else:
        print("\n❌ 验证失败！")
        print("微软返回的完整错误信息：")
        print(response.text)
        print("\n分析提示：")
        if "AADSTS70002" in response.text:
            print("- AADSTS70002: 只要没带 Secret 就报错？这通常意味着 Azure 里注册的还是 Web 应用，而不是 Mobile/Desktop。")
        elif "AADSTS70000" in response.text:
            print("- AADSTS70000: 请求参数错误，可能是 Token 格式不对或者已过期。")

except Exception as e:
    print(f"\n❌ 发生异常: {e}")

input("\n按回车键退出...")
