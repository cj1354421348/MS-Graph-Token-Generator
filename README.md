# MS Graph Token Manager (Microsoft Graph 令牌管理器)

这是一个用于生成、验证和自动续期 Microsoft Graph Refresh Token 的工具套件。
特别适用于需要长期运行的脚本或后台服务 (如 Outlook 邮件管理)，支持 **Public Client (桌面/无密码)** 模式，解决 90 天有效期问题。

## 🚀 快速开始

### 1. 环境准备
确保已安装 Python，然后安装依赖：
```bash
pip install -r requirements.txt
```

### 2. 核心配置 (`.env`)
复制 `.env.example` 为 `.env`，并修改以下关键项：

```properties
# 你的 Azure 应用 ID
CLIENT_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# 【关键】桌面/脚本应用必须留空或删除 Client Secret！
# CLIENT_SECRET=

# 回调地址 (必须与 Azure 门户一致)
# Azure 门户 -> 身份验证 -> 移动和桌面应用程序 -> 添加 URI: http://localhost
REDIRECT_URI=http://localhost:5000

# 权限范围 (收发邮件推荐配置)
SCOPE=offline_access https://outlook.office.com/IMAP.AccessAsUser.All https://outlook.office.com/SMTP.Send
```

---

## 🛠️ 工具使用指南

### 1. 获取新 Token (初次或失效时)
当你要添加新账号，或者某个账号 Token 失效时使用。

运行：
```bash
python main.py
```
1. 浏览器打开 `http://localhost:5000`。
2. 点击登录，授权微软账号。
3. 成功后，页面会显示 **Client ID** 和 **Refresh Token**。
4. 将这些信息填入你的 `accounts.json` 文件中。

---

### 2. 自动续期/保活 (核心功能)
微软 Token 有效期为 90 天。为了避免过期，请**定期运行**此工具。

运行：
```bash
python token_refresher.py
```
**功能：**
- 自动读取 `accounts.json` 中的所有账户。
- 逐个尝试用旧 Token 换取新 Token。
- **成功**：自动更新 json 文件里的 `refresh_token`，实现“无限续杯”。
- **失败**：提示错误 (通常意味着需要用步骤 1 重新人工登录)。

**建议**：加入系统计划任务 (Windows Task Scheduler)，每周运行一次。

---

### 3. Token 诊断
如果你不确定某个 Token 是否还能用：

运行：
```bash
python verify_token.py
```
粘贴你的 Token，它会告诉你是否存活，或者具体的死亡原因。

---

### 4. 账户文件示例 (accounts.json)
`token_refresher.py` 依赖此文件来存储和更新 Token。
格式如下（Json 字典，Key 是邮箱，Value 是详细信息）：

```json
{
  "example@outlook.com": {
    "refresh_token": "M.C542_SN1.0.U.-Ckx...",
    "client_id": "你的_CLIENT_ID"
  },
  "another_user@outlook.com": {
    "refresh_token": "M.C538_BAY.0.U.-Ci1...",
    "client_id": "另一个_CLIENT_ID"
  }
}
```
**注意：** `refresh_token` 和 `client_id` 是必须的字段。

---

## 📂 文件说明
- `accounts.json`: 你的账户数据库 (存储 Token 的地方)。
- `main.py`: 网页版生成器 (人工操作)。
- `token_refresher.py`: 批量自动续期脚本 (机器操作)。
- `verify_token.py`: 单个 Token 测试工具。
