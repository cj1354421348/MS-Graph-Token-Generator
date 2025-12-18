FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖 (仅当 psycopg2 需要编译时，binary版本通常不需要)
# RUN apt-get update && apt-get install -y gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# 确保安装了 postgresql 驱动
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露端口
EXPOSE 5000

# 启动默认命令 (Web UI)
# 确保绑定 0.0.0.0 以便 Docker 端口映射生效
ENV HOST=0.0.0.0
CMD ["python", "main.py"]
