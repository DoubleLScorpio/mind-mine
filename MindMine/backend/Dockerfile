FROM python:3.12-slim

WORKDIR /app

# 先装依赖，利用 Docker 层缓存：源码变动时不必重装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码。.dockerignore 已排除 .env / .venv，
# 密钥一律通过平台环境变量注入，绝不打进镜像。
COPY . .

# Railway / Render 等平台会在运行时注入 PORT 覆盖这个默认值。
# 本地 docker run 时没有注入，就用 8000。
ENV PORT=8000
EXPOSE 8000

# 必须用 sh -c，否则 ${PORT} 不会被展开，会被当成字面量传给 uvicorn。
# 必须监听 0.0.0.0，绑 127.0.0.1 在容器外无法访问，平台健康检查会失败。
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
