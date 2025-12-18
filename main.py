from flask import Flask, request, redirect, url_for, session, render_template_string
import msal
import os
import uuid
from dotenv import load_dotenv

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
    # MSAL 返回的 result 包含 access_token, id_token, refresh_token 等
    refresh_token = result.get("refresh_token")
    
    if not refresh_token:
        # 有时候如果没有 offline_access scope，可能不会返回 refresh_token
        return "⚠️ 获取成功，但未返回 Refresh Token。请检查 Scope 中是否包含 offline_access。", 200

    return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>成功获取令牌</title>
            <style>
                body { font-family: 'Segoe UI', sans-serif; padding: 40px; background-color: #f3f2f1; }
                .container { max-width: 800px; margin: 0 auto; background: white; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
                .token-box { word-wrap: break-word; background-color: #f8f9fa; padding: 20px; border: 1px solid #e1dfdd; border-radius: 4px; font-family: 'Consolas', monospace; margin: 20px 0; max-height: 300px; overflow-y: auto; color: #a4262c; }
                h1 { color: #107c10; display: flex; align-items: center; gap: 10px; }
                p { color: #605e5c; }
                button { cursor: pointer; padding: 10px 20px; background-color: #0078D4; color: white; border: none; border-radius: 4px; font-size: 14px; }
                button:hover { background-color: #005a9e; }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>🎉 认证成功</h1>
                <p>以下是您的 Refresh Token，请妥善保管：</p>
                <div class="token-box">
                    <code id="token-code">{{ token }}</code>
                </div>
                <button onclick="copyToken()">📋 一键复制令牌</button>
                <p style="margin-top: 30px; font-size: 0.9em; color: #888;">注意: 此 Token 直接与您的 Client ID 绑定。</p>
            </div>

            <script>
                function copyToken() {
                    var tokenText = document.getElementById("token-code").innerText;
                    navigator.clipboard.writeText(tokenText).then(function() {
                        alert("✅ 令牌已复制到剪贴板！");
                    }, function(err) {
                        alert("❌ 复制失败: " + err);
                    });
                }
            </script>
        </body>
        </html>
    """, token=refresh_token)


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
