FROM python:3.12-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码（不含 .env，密钥通过平台环境变量注入）
COPY . .

# Render / 其他平台会通过 PORT 环境变量注入端口
ENV PORT=8000

# 使用 exec 形式，让进程能接收 SIGTERM 正常退出
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
