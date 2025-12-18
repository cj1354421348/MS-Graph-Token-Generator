from flask import Flask, request, redirect, url_for, session, render_template_string
import msal
import os
import uuid
import json
import datetime
from dotenv import load_dotenv

ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")

def save_to_json(email, refresh_token, client_id):
    """保存或更新账户信息到 JSON 文件"""
    print(f"DEBUG: 尝试保存到 {ACCOUNTS_FILE}...")
    print(f"DEBUG: 目标邮箱: {email}")
    
    data = {}
    if os.path.exists(ACCOUNTS_FILE):
        try:
            with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"⚠️ 读取 {ACCOUNTS_FILE} 失败: {e}")

    # 构造数据
    now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # 查找是否存在对应的 Key (忽略大小写)
    target_key = email
    for key in data.keys():
        if key.lower() == email.lower():
            target_key = key
            print(f"DEBUG: 找到现有账户: {key} (匹配 {email})")
            break
            
    if target_key not in data:
        print(f"DEBUG: 创建新账户记录: {target_key}")
        data[target_key] = {}
        # 只有新建时才初始化这些
        data[target_key]["tags"] = []
        data[target_key]["status"] = "active"

    # 更新字段
    data[target_key]["refresh_token"] = refresh_token
    data[target_key]["client_id"] = client_id
    data[target_key]["last_modified_at"] = now_str
    
    # 显式设置为 active
    data[target_key]["status"] = "active"
    if "status_reason" in data[target_key]:
        del data[target_key]["status_reason"]
    if "status_updated_at" in data[target_key]:
        del data[target_key]["status_updated_at"]
    if "token_failures" in data[target_key]:
        del data[target_key]["token_failures"]

    try:
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print("DEBUG: 写入成功！")
        return True, target_key
    except Exception as e:
        print(f"❌ 写入 {ACCOUNTS_FILE} 失败: {e}")
        return False, str(e)



# 加载 .env 文件中的环境变量
load_dotenv()


# --- 1. 配置您的应用信息 (从环境变量读取) ---
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
# Azure Public Client 通常注册 http://localhost，我们在本地运行在 5000 端口
# MSAL/Azure 允许 http://localhost 匹配 http://localhost:PORT
REDIRECT_URI = os.environ.get("REDIRECT_URI", "http://localhost:5000")
# MSAL 对 Scope 的格式要求是列表
# 注意：MSAL 会自动添加 'offline_access', 'openid', 'profile'，显式传入会报错
# 所以我们需要从配置中移除这些保留字段
RAW_SCOPES = os.environ.get("SCOPE", "offline_access Files.ReadWrite.All Sites.ReadWrite.All User.Read").split()
RESERVED_SCOPES = {'offline_access', 'openid', 'profile'}
SCOPE = [s for s in RAW_SCOPES if s.lower() not in RESERVED_SCOPES]

AUTHORITY = "https://login.microsoftonline.com/common"

# 关键配置检查
if not CLIENT_ID:
    print("❌ 错误: 未设置 CLIENT_ID 环境变量。")
    print("请参考 .env.example 配置您的环境变量。")
    exit(1)

# --- 2. 初始化 MSAL 应用 ---
# 根据是否有 CLIENT_SECRET 决定使用 Confidential 还是 Public Client
if CLIENT_SECRET:
    print("🔒 模式: Confidential Client (Web App)")
    app_msal = msal.ConfidentialClientApplication(
        CLIENT_ID, authority=AUTHORITY,
        client_credential=CLIENT_SECRET,
    )
else:
    print("📱 模式: Public Client (Desktop/Mobile - No Secret)")
    # 使用 PublicClientApplication，MSAL 会自动处理 PKCE
    app_msal = msal.PublicClientApplication(
        CLIENT_ID, authority=AUTHORITY
    )

# --- 3. 创建Flask应用 ---
app = Flask(__name__)

# --- 配置 Flask ---
app.secret_key = os.environ.get("FLASK_SECRET_KEY", os.urandom(24))
if not os.environ.get("FLASK_SECRET_KEY"):
    print("⚠️ 警告: 未设置 FLASK_SECRET_KEY，每次重启会导致用户 Session 失效。")

if os.environ.get("COOKIE_DOMAIN"):
    app.config['SESSION_COOKIE_DOMAIN'] = os.environ.get("COOKIE_DOMAIN")


# --- 4. Web 页面逻辑 ---

@app.route("/")
@app.route("/callback")
def index():
    # 如果 URL 中包含 code 参数，说明是回调
    if request.args.get('code'):
        return handle_callback()
    
    # 否则显示首页
    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Microsoft Graph 令牌生成器 (MSAL)</title>
            <style>
                body { font-family: 'Segoe UI', sans-serif; text-align: center; padding-top: 100px; background-color: #f3f2f1; }
                .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
                h1 { color: #323130; margin-bottom: 30px; }
                p { color: #605e5c; margin-bottom: 40px; }
                a.btn { text-decoration: none; padding: 15px 40px; background-color: #0078D4; color: white; border-radius: 4px; font-weight: 600; transition: background 0.2s; }
                a.btn:hover { background-color: #005a9e; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>获取 Microsoft Graph 令牌</h1>
                <p>支持 Web 与 桌面应用注册 (Public Client)</p>
                <a href="/login" class="btn">🔑 使用 Microsoft 账户登录</a>
            </div>
        </body>
        </html>
    """)


@app.route("/login")
def login():
    # 1. 启动 Auth Code Flow
    # MSAL 自动生成 state, code_verifier (PKCE) 等
    auth_flow = app_msal.initiate_auth_code_flow(
        scopes=SCOPE,
        redirect_uri=REDIRECT_URI
    )
    
    if "error" in auth_flow:
        return f"MSAL 初始化失败: {auth_flow.get('error_description')}", 500

    # 2. 将 flow 对象存入 session，回调时需要用到
    # flow 中包含了 code_verifier，这是 PKCE 的关键
    session["flow"] = auth_flow
    
    # 3. 重定向用户到微软登录页
    return redirect(auth_flow["auth_uri"])


def handle_callback():
    # 1. 从 session 取出之前存的 flow
    flow = session.get("flow")
    if not flow:
        return "❌ 错误: Session 中没有找到 Auth Flow。可能是 Session 过期或 Cookies 问题，请返回重试。", 400

    # 2. 验证 state 并处理回调参数
    try:
        # acquire_token_by_auth_code_flow 会自动处理 state 验证和 PKCE 交换
        result = app_msal.acquire_token_by_auth_code_flow(
            flow, request.args
        )
    except ValueError as e:
        return f"❌ Token 交换失败: {e}", 400

    # 3. 检查结果
    if "error" in result:
        return render_template_string("""
            <h1>🚫 认证失败</h1>
            <p><strong>错误:</strong> {{ error }}</p>
            <p><strong>描述:</strong> {{ desc }}</p>
            <a href="/">返回重试</a>
        """, error=result.get("error"), desc=result.get("error_description"))

    # 4. 成功，提取信息
    refresh_token = result.get("refresh_token")
    # access_token = result.get("access_token") # UI 不需要显示太乱
    
    # 尝试提取用户邮箱
    email = "unknown_user"
    claims = result.get("id_token_claims", {})
    if "preferred_username" in claims:
        email = claims["preferred_username"]
    elif "upn" in claims:
        email = claims["upn"]
    elif "email" in claims:
        email = claims["email"]
    
    print(f"DEBUG: 解析到的邮箱: {email}")

    # 自动保存
    save_status = False
    save_msg = ""
    if refresh_token:
        # save_to_json 返回 (success, info)
        success, info = save_to_json(email, refresh_token, CLIENT_ID)
        if success:
            save_status = True
            save_msg = f"✅ 已自动更新账户: {info}"
        else:
            save_msg = f"❌ 自动保存失败: {info}"

    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Microsoft Graph 授权成功</title>
            <style>
                body { font-family: 'Segoe UI', sans-serif; text-align: center; padding-top: 50px; background-color: #f3f2f1; }
                .container { max-width: 700px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
                h1 { color: #107c10; margin-bottom: 20px; }
                .success-msg { color: #107c10; font-weight: 600; margin-bottom: 20px; padding: 10px; background-color: #dff6dd; border-radius: 4px; display: inline-block;}
                .error-msg { color: #a80000; font-weight: 600; margin-bottom: 20px; padding: 10px; background-color: #fde7e9; border-radius: 4px; display: inline-block;}
                .token-box { background: #f8f9fa; padding: 15px; border-radius: 4px; border: 1px solid #e1dfdd; font-family: monospace; font-size: 12px; word-break: break-all; max-height: 150px; overflow-y: auto; text-align: left; margin: 20px 0; color: #333; }
                .btn { display: inline-block; padding: 10px 25px; background-color: #0078D4; color: white; text-decoration: none; border-radius: 4px; cursor: pointer; border: none; font-size: 14px; transition: background 0.2s; }
                .btn:hover { background-color: #005a9e; }
                .meta { color: #605e5c; font-size: 14px; margin-top: 5px; }
            </style>
            <script>
                function copyToken() {
                    var copyText = document.getElementById("refreshToken");
                    navigator.clipboard.writeText(copyText.innerText).then(function() {
                        alert("Refresh Token 已复制！");
                    }, function(err) {
                        alert("复制失败: " + err);
                    });
                }
            </script>
        </head>
        <body>
            <div class="container">
                <h1>🎉 授权成功</h1>
                
                {% if save_status %}
                    <div class="success-msg">{{ save_msg }}</div>
                {% else %}
                    <div class="error-msg">{{ save_msg }}</div>
                {% endif %}

                <p class="meta">Client ID: {{ client_id }}</p>
                
                <h3 style="text-align: left; margin-bottom: 5px; font-size: 16px;">Refresh Token (90天):</h3>
                <div class="token-box" id="refreshToken">{{ refresh_token }}</div>
                
                <button class="btn" onclick="copyToken()">📋 复制 Token</button>

                <div style="margin-top: 40px; border-top: 1px solid #eee; padding-top: 20px;">
                    <a href="/" style="color: #666; text-decoration: none;">返回首页生成下一个</a>
                </div>
            </div>
        </body>
        </html>
    """, refresh_token=refresh_token, client_id=CLIENT_ID, save_status=save_status, save_msg=save_msg)


# --- 5. 启动应用 ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "False").lower() == "true"
    host = os.environ.get("HOST", "0.0.0.0")
    
    print(f"🚀 启动应用: http://{host}:{port}")
    if CLIENT_SECRET:
        print(f"ℹ️  机密模式 (Confidential)")
    else:
        print(f"ℹ️  公共模式 (Public/Desktop) - PKCE Enabled")
    
    app.run(host=host, port=port, debug=debug, use_reloader=False)

