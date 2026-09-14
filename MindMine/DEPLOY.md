# MindMine 部署手册

目标：前端 Vercel + 后端 Render，知乎和 LLM 全部走真实路径。

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

## 第三步：部署后端（Render）

### 3.1 创建 Web Service

1. 打开 https://render.com，注册或登录
2. New → Web Service → Connect a repository → 选刚才的 GitHub 仓库
3. 配置如下：

| 字段 | 值 |
|------|-----|
| Name | mindmine-backend |
| Root Directory | `MindMine/backend` |
| Runtime | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Instance Type | Free（Hackathon 够用） |

### 3.2 配置环境变量（Environment）

在 Render Dashboard → Environment 页面，添加以下变量：

| Key | Value | 说明 |
|-----|-------|------|
| `LLM_PROVIDER` | `auto` | |
| `LLM_API_KEY` | `<你的 DeepSeek Key>` | 用 Secret 类型 |
| `LLM_BASE_URL` | `https://api.deepseek.com/v1` | |
| `LLM_MODEL` | `deepseek-chat` | |
| `LLM_TIMEOUT_SECONDS` | `30` | 线上网络比本地慢，稍微放长 |
| `LLM_MAX_RETRIES` | `1` | |
| `ZHIHU_PROVIDER` | `auto` | |
| `ZHIHU_ACCESS_SECRET` | `<你的知乎 Access Secret>` | 用 Secret 类型；CLI 会自动读取 |
| `ZHIHU_CLI_PATH` | 留空 | Render 容器没有看山工作台，这里留空会让知乎走 mock |
| `ZHIHU_TIMEOUT_SECONDS` | `20` | |
| `PROFILE_PROVIDER` | `auto` | |
| `CORS_ORIGINS` | 部署前端后填入，例如 `https://mindmine-xxx.vercel.app` | |
| `LOG_LEVEL` | `INFO` | |
| `VERBOSE_PROVIDER_LOG` | `true` | |

> **注意**：Render 的 Free 实例在 15 分钟无请求后会休眠，第一次唤醒需要约 30-60 秒。
> Hackathon Demo 前，先用浏览器访问一次 `/health` 接口唤醒它。

> **关于知乎**：Render 容器没有看山工作台内置的 zhihu-cli，`ZHIHU_CLI_PATH` 留空时
> `resolved_zhihu_cli_path()` 会返回一个不存在的路径，`zhihu.available` 为 False，
> 自动 fallback 到 Mock 问题和 Mock 观点。LLM 功能（Mining / Insight / Compose）不受影响。
> 如果需要线上跑真实知乎：见下方「进阶：线上知乎」。

### 3.3 记录 Backend URL

部署完成后，Render 会分配一个 URL，形如：
`https://mindmine-backend-xxxx.onrender.com`

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
| `VITE_API_BASE_URL` | `https://mindmine-backend-xxxx.onrender.com`（第三步的 URL）|

### 4.3 部署完成后

Vercel 会分配一个 URL，形如：`https://mindmine-xxx.vercel.app`

**回到 Render**，把 `CORS_ORIGINS` 更新为这个 URL：
`https://mindmine-xxx.vercel.app`

然后在 Render Dashboard 手动触发一次 Redeploy（让 CORS 配置生效）。

---

## 第五步：验收

按顺序测试：

1. 打开 `https://mindmine-xxx.vercel.app` → 首页加载正常
2. 访问 `https://mindmine-backend-xxxx.onrender.com/api/v1/health` → 返回 `{"ok": true, "data": {...}}`
3. 刷新 `/portrait`、`/mine/xxx`、`/result/xxx` → 不 404（Vercel 自动处理 SPA fallback）
4. 走完 Opening → Chat → Portrait → Match → Mining → Insight → Compose 全流程
5. 打开 DevTools Network → 确认没有请求打到 localhost → 确认没有 API Key 出现在响应里

---

## 进阶：线上知乎（可选，部署后补做）

Render 容器里没有看山工作台，但知乎 CLI 是独立二进制，可以在构建时下载。
需要：
1. 从看山工作台的更新包里提取 `zhihu-cli` Linux 版本（目前只有 macOS 版，需要官方提供 Linux 构建）
2. 或者把知乎功能改成 HTTP API 模式（不依赖本地 CLI）

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
