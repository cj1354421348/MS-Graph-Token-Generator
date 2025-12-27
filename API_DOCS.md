# Notify Hub API 文档

本文档详细说明了 Notify Hub 的后端接口，主要包括**消息推送**（发送通知）和**消息查询**两部分。

---

## 🚀 1. 消息推送接口 (Send Notification)

这是最核心的接口，用于从您的业务系统（Python脚本, 后端服务, CI/CD等）发送通知到 Notify Hub。

### 基本信息
- **URL**: `POST /api/notify`
- **鉴权方式**: Header `X-Project-Key`
    - 该 Key 必须与后端 `.env` 文件中的 `NOTIFY_KEY` 一致。
    - **注意**：这不是具体项目的 Key，而是全局推送密钥。
- **自动创建项目**: 如果请求体中的 `project_name` 对应的项目不存在，系统会**自动创建**该项目。

### 请求参数 (JSON Body)
| 字段 | 类型 | 必填 | 说明 | 默认值 |
| :--- | :--- | :--- | :--- | :--- |
| `project_name` | string | **是** | 项目名称 (作为归类的唯一标识) | - |
| `content` | string | **是** | 消息正文 | - |
| `title` | string | 否 | 消息标题 | null |
| `level` | string | 否 | 消息级别 (`info`, `success`, `warning`, `error`) | `info` |

### 请求示例

#### ✅ Python (Requests)
```python
import requests

url = "http://localhost:8000/api/notify"
headers = {
    "X-Project-Key": "my-fixed-secret-key-123",  # 对应后端 .env 的 NOTIFY_KEY
    "Content-Type": "application/json"
}
data = {
    "project_name": "支付系统",
    "title": "支付失败告警",
    "content": "订单 #9982 由用户 UserA 支付失败，原因：余额不足。",
    "level": "error"
}

try:
    resp = requests.post(url, json=data, headers=headers)
    print(resp.json())
except Exception as e:
    print("发送失败:", e)
```

#### ✅ Curl
```bash
curl -X POST "http://localhost:8000/api/notify" \
     -H "Content-Type: application/json" \
     -H "X-Project-Key: my-fixed-secret-key-123" \
     -d '{
           "project_name": "每日备份",
           "title": "备份完成",
           "content": "数据库备份已上传至 S3，大小 500MB。",
           "level": "success"
         }'
```

### 响应示例
**成功 (200 OK)**:
```json
{
  "status": "success",
  "message_id": 42,
  "project": "支付系统"
}
```

**失败 (403 Forbidden)**: `X-Project-Key` 错误。
**失败 (422 Validation Error)**: 缺少必填字段。

---

## 🔍 2. 消息列表接口 (Query Messages)

Dashboard 前端主要使用此接口查询数据。支持多种筛选方式。

### 基本信息
- **URL**: `GET /api/messages`
- **鉴权方式**: Bearer Token (JWT, 用于前端登录用户)

### 查询参数 (Query Parameters)
| 参数 | 类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `limit` | int | 返回数量限制 (默认 50) | `500` |
| `start_date` | string (ISO) | 起始时间 | `2024-01-01T00:00:00Z` |
| `end_date` | string (ISO) | 结束时间 | `2024-01-31T23:59:59Z` |
| `level` | string | 筛选级别 | `error` |
| `project_id` | int | 筛选项目ID | `1` |
| `search` | string | 搜索标题或内容关键字 | `超时` |

---

## 🗑️ 3. 删除/清理接口

1.  **软删除单条消息**: `DELETE /api/messages/{id}`
2.  **清空回收站 (物理删除)**: `DELETE /api/system/purge`
    *   删除所有 `is_deleted=True` 的消息。
3.  **删除项目**: `DELETE /api/projects/{id}`

---

## 🔑 4. 后端环境配置 (.env)

确保 `backend/.env` 包含以下配置：

```ini
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/dbname
WEB_USERNAME=admin            # 前端登录用户名
WEB_PASSWORD=password123      # 前端登录密码
SECRET_KEY=your-jwt-secret    # JWT 签名密钥
NOTIFY_KEY=my-fixed-secret-key-123  # 全局推送鉴权 Key (最重要)
```
