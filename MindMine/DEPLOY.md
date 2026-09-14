# MindMine 部署手册

目标：前端 Vercel + 后端 Railway，LLM 走真实 DeepSeek。

---

## 第一步：建 GitHub 仓库

1. 打开 https://github.com/new，建一个**私有**仓库，名字随意（例如 `mindmine`）
2. 不要勾选 Initialize with README

---

## 第二步：把代码推上去

在终端（本项目根目录）执行：

```bash
git remote add origin https://github.com/<你的用户名>/<仓库名>.git
git push -u origin main
```

---

## 第三步：部署后端（Railway）

### 3.1 创建 Service

1. 打开 https://railway.com，用 GitHub 账号登录
2. **New Project** → **Deploy from GitHub repo** → 选刚才的仓库
3. 首次会要求授权 Railway 访问 GitHub，按提示允许

Railway 会先把整个仓库当成一个服务。因为后端在子目录里，要手动指定根目录：

进入这个 service → **Settings** 标签页：

| 区块 | 字段 | 值 |
|------|------|-----|
| Source | Root Directory | `MindMine/backend` |
| Build | Builder | Dockerfile（识别到 Dockerfile 后自动选中） |
| Deploy | Custom Start Command | **留空** |
| Networking | Public Networking | 点 **Generate Domain** |

> **Root Directory 是最容易漏的一项**。不填的话 Railway 在仓库根目录找不到
> `Dockerfile` 和 `requirements.txt`，构建直接失败。
>
> **Start Command 留空**：`Dockerfile` 最后一行的
> `CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]` 会生效。
> Railway 在运行时注入 `PORT`，所以这里绝不能写死端口，
> 否则平台路由不到你的进程，部署会一直显示失败。
>
> 仓库里的 `MindMine/backend/railway.json` 已经配好了 healthcheck，
> Railway 会自动读取，不需要在界面上再填一遍。

### 3.2 配置环境变量（Variables）

进入 service → **Variables** 标签页 → **New Variable** 逐条添加
（也可以点 **Raw Editor** 一次性粘贴）：

| Key | Value | 说明 |
|-----|-------|------|
| `LLM_PROVIDER` | `auto` | |
| `LLM_API_KEY` | `<你的 DeepSeek Key>` | |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | |
| `LLM_MODEL` | `deepseek-chat` | |
| `LLM_TIMEOUT_SECONDS` | `30` | 线上网络比本地慢，稍微放长 |
| `LLM_MAX_RETRIES` | `1` | |
| `ZHIHU_PROVIDER` | `auto` | |
| `ZHIHU_ACCESS_SECRET` | `<你的知乎 Access Secret>` | zhihu-cli 优先读此变量，不依赖钥匙串 |
| `ZHIHU_CLI_PATH` | 留空 | Docker 镜像内没有 zhihu-cli，留空即走 mock |
| `ZHIHU_TIMEOUT_SECONDS` | `20` | |
| `PROFILE_PROVIDER` | `auto` | |
| `CORS_ORIGINS` | 部署前端后回填，例如 `https://mindmine-xxx.vercel.app` | |
| `LOG_LEVEL` | `INFO` | |
| `VERBOSE_PROVIDER_LOG` | `true` | |

Raw Editor 粘贴版本（`LLM_API_KEY` 和 `ZHIHU_ACCESS_SECRET` 自己填）：

```
LLM_PROVIDER=auto
LLM_API_KEY=
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=1
ZHIHU_PROVIDER=auto
ZHIHU_ACCESS_SECRET=
ZHIHU_CLI_PATH=
ZHIHU_TIMEOUT_SECONDS=20
PROFILE_PROVIDER=auto
LOG_LEVEL=INFO
VERBOSE_PROVIDER_LOG=true
```

> **不要手动添加 `PORT`**。Railway 自己注入，手写会和平台路由冲突。

> **关于计费**：Railway 新账号有一次性 $5 试用额度（约 30 天）。
> 这个后端是 512MB 级别的小服务，Hackathon 期间用不完。
> 试用额度耗尽后服务会停止，需要绑卡才能继续 —— 演示前确认一下额度还在。

> **关于知乎**：Docker 镜像里没有 zhihu-cli 二进制（它是看山工作台随附的 macOS 程序），
> `ZHIHU_CLI_PATH` 留空时 `resolved_zhihu_cli_path()` 返回的默认路径在容器内不存在，
> `zhihu.available` 为 False，自动 fallback 到 Mock 问题和 Mock 观点。
> LLM 功能（Mining / Insight / Compose）不受影响。
> 即便如此也建议照填 `ZHIHU_ACCESS_SECRET`，后续补上 Linux 版 CLI 即可直接生效。
> 如果需要线上跑真实知乎：见下方「进阶：线上知乎」。

### 3.3 记录 Backend URL

在 **Settings → Networking → Public Networking** 点 **Generate Domain** 后，
Railway 会分配一个地址，形如：
`https://mindmine-backend-production-xxxx.up.railway.app`

打开 `<这个地址>/api/v1/health` 验证，应该返回：

```json
{
  "ok": true,
  "data": {
    "status": "healthy",
    "providers": {
      "llm": { "configured": true, "mode": "real", "model": "deepseek-chat" },
      "zhihu": { "mode": "real", "cli_available": false }
    }
  }
}
```

重点看 `llm.mode` 是不是 `real`、`configured` 是不是 `true`。
如果是 `mock`，说明 `LLM_API_KEY` 没填或填错了。
`zhihu.cli_available` 为 `false` 属于预期。

记下这个地址，第四步要用。

---

## 第四步：部署前端（Vercel）

### 4.1 创建 Project

1. 打开 https://vercel.com，注册或登录
2. New Project → Import Git Repository → 选同一个仓库
3. 配置如下：

| 字段 | 值 |
|------|-----|
| Root Directory | `MindMine/frontend` |
| Framework Preset | Vite |
| Build Command | `npm run build` |
| Output Directory | `dist` |

### 4.2 配置环境变量

在 Vercel → Settings → Environment Variables 添加：

| Key | Value |
|-----|-------|
| `VITE_API_BASE_URL` | `https://mindmine-backend-production-xxxx.up.railway.app`（第三步的 URL）|

> 结尾**不要带斜杠**。前端会拼成 `${VITE_API_BASE_URL}/api/v1`，
> 多一个斜杠会变成 `//api/v1`。

### 4.3 部署完成后

Vercel 会分配一个 URL，形如：`https://mindmine-xxx.vercel.app`

**回到 Railway** → Variables → 把 `CORS_ORIGINS` 设为这个 URL：
`https://mindmine-xxx.vercel.app`

同样**不要带结尾斜杠** —— 后端按字符串精确匹配 origin，
多一个斜杠会匹配不上，浏览器直接报跨域。

改完 Railway 会自动重新部署，等状态变回 Active 即可。

---

## 第五步：验收

按顺序测试：

1. 打开 `https://mindmine-xxx.vercel.app` → 首页加载正常
2. 访问 `https://mindmine-backend-production-xxxx.up.railway.app/api/v1/health` → 返回 `{"ok": true, "data": {...}}`
3. 刷新 `/portrait`、`/mine/xxx`、`/result/xxx` → 不 404（Vercel 自动处理 SPA fallback）
4. 走完 Opening → Chat → Portrait → Match → Mining → Insight → Compose 全流程
5. 打开 DevTools Network → 确认没有请求打到 localhost → 确认没有 API Key 出现在响应里

---

## 进阶：线上知乎（可选，部署后补做）

Railway 容器里没有看山工作台，但知乎 CLI 是独立二进制，可以在构建时下载。
需要：
1. 从看山工作台的更新包里提取 `zhihu-cli` Linux 版本（目前只有 macOS 版，需要官方提供 Linux 构建）
2. 或者把知乎功能改成 HTTP API 模式（不依赖本地 CLI）

拿到 Linux 版二进制后，在 `Dockerfile` 里 `COPY` 进镜像，
并把 `ZHIHU_CLI_PATH` 指向容器内路径即可，后端代码不用改。

这两个方案都需要官方支持或较大代码改动，Hackathon 阶段不建议花时间在这里。
**线上 Mining → Insight → Compose 走真实 LLM，已经足够展示核心能力。**

---

## 本地开发继续用

本地什么都不需要改，照常用：

```bash
# 后端
cd MindMine/backend && ./.venv/bin/uvicorn main:app --reload --port 8078

# 前端
cd MindMine/frontend && npm run dev
```

前端 `vite.config.ts` 的 proxy 配置不受影响（`VITE_API_BASE_URL` 为空时走 proxy）。
