FROM python:3.12-slim

WORKDIR /app

# ------------------------------------------------------------------
# 知乎 CLI（Linux amd64）
#
# zhihu-cli 是知乎开放平台的官方命令行客户端。
# Railway / Render 容器是 linux/amd64，本地开发是 macOS arm64，
# 所以必须在构建时下载 Linux 版，不能直接复制本地二进制。
#
# 版本与 sha256 来自官方 manifest：
# https://developer-cdn.zhihu.com/zhihu-cli/releases/beta/manifest.json
#
# 凭据通过 Railway 环境变量 ZHIHU_ACCESS_SECRET 注入，
# zhihu-cli 会优先读取该环境变量，不依赖系统钥匙串。
# ------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && ZHIHU_CLI_VERSION="0.6.0-beta.20260908125143" \
    && ZHIHU_CLI_SHA256="d21691ac3bebeac4fb29f6982da6b4e4dddf659b731cd8f65dea1c0242a7d0ba" \
    && curl -fsSL \
       "https://developer-cdn.zhihu.com/zhihu-cli/releases/beta/cli/${ZHIHU_CLI_VERSION}/zhihu-cli-${ZHIHU_CLI_VERSION}-linux-amd64.tar.gz" \
       -o /tmp/zhihu-cli.tar.gz \
    && echo "${ZHIHU_CLI_SHA256}  /tmp/zhihu-cli.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/zhihu-cli.tar.gz -C /usr/local/bin/ \
    && chmod +x /usr/local/bin/zhihu-cli \
    && rm /tmp/zhihu-cli.tar.gz \
    && apt-get remove -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖，利用 Docker 层缓存：源码变动时不必重装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源码。.dockerignore 已排除 .env / .venv，
# 密钥一律通过平台环境变量注入，绝不打进镜像。
COPY . .

# 告知 config.py 去哪里找 zhihu-cli。
# Railway 运行时会再注入 ZHIHU_ACCESS_SECRET，CLI 自动读取，不依赖钥匙串。
ENV ZHIHU_CLI_PATH=/usr/local/bin/zhihu-cli
# Railway / Render 等平台会在运行时注入 PORT 覆盖这个默认值。
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
