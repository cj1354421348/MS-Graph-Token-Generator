import os
import requests
import logging
from dotenv import load_dotenv

# 加载环境变量 (确保本地测试也能读取到 .env)
load_dotenv()

# 配置日志
logger = logging.getLogger(__name__)

def send(title, content, level="info"):
    """
    发送通知到 Notify Hub。
    
    Args:
        title (str): 消息标题
        content (str): 消息正文
        level (str): 消息级别 ('info', 'success', 'warning', 'error')
    """
    api_url = os.environ.get("NOTIFY_API_URL")
    api_key = os.environ.get("NOTIFY_KEY")
    
    # 如果未配置，则静默跳过 (仅已配置时才发送)
    if not api_url or not api_key:
        logger.warning(f"🔕 通知服务未配置，跳过发送! (当前环境: NOTIFY_API_URL={api_url}, NOTIFY_KEY={'***' if api_key else 'None'})")
        return

    payload = {
        "project_name": "MS-Graph-Refresher",
        "title": title,
        "content": content,
        "level": level
    }
    
    headers = {
        "X-Project-Key": api_key,
        "Content-Type": "application/json"
    }
    
    try:
        if not api_url.startswith("http"):
            logger.warning(f"⚠️ 通知 API URL 格式似乎不正确: {api_url}")

        response = requests.post(api_url, json=payload, headers=headers, timeout=10)
        
        if response.status_code == 200:
            logger.info("📢 通知已发送")
        elif response.status_code == 403:
            logger.error("❌ 通知发送失败: 鉴权被拒绝 (请检查 NOTIFY_KEY)")
        else:
            logger.error(f"❌ 通知发送失败 (HTTP {response.status_code}): {response.text}")
            
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ 通知网络请求异常: {e}")
    except Exception as e:
        logger.error(f"❌ 通知发送未知错误: {e}")

if __name__ == "__main__":
    # 简单的本地测试逻辑
    logging.basicConfig(level=logging.INFO)
    print("Running notify.py self-test...")
    if os.environ.get("NOTIFY_API_URL"):
        send("Notification Test", "This is a test from notify.py", "info")
    else:
        print("Skipping test: Environment variables not set.")
