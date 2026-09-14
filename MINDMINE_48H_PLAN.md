# MindMine 48 小时实施计划

> **起点**：Day 1，09:00
> **目标**：可演示的完整链路 + 真实知乎 API 接入 + 全套兜底系统可用
> **开发顺序**：Mock 完整旅程 → 接真实 LLM → 接真实知乎 API → 接 OAuth → 视觉与演示打磨

---

## 指导约束

1. **每个 Phase 结束时，演示都必须能端到端跑通。** 破坏演示的 Phase 不算完成。
2. 兜底数据（`demo_questions.json`、`demo_evidence.json`、`demo_session.json`）在 Phase 0 写好，全程维护，**绝不删除或清空**。
3. 真实服务**增量接入**。每个 Phase 只接一个真实服务，其余全部保持兜底状态。
4. 从 Phase 1 起，`GET /api/v1/sessions/demo` 必须随时能返回完整的 Vicky 会话。

---

## Phase 0 — 地基 + 完整 Mock 旅程

**时长**：约 6 小时
**目标**：后端和前端都能跑起来，每个阶段返回 Mock 数据。不调用真实 LLM 和知乎 API。**完整 6 阶段用户旅程可以点通。**

### 要建什么

**后端**：

- `mindmine/backend/` 脚手架：`main.py`、`config.py`、`database.py`
- SQLite 表结构：`sessions` 表，所有会话字段用 JSON blob 列
- 会话状态机（所有流转都校验）
- 8 个 router，处理器返回硬编码 Mock 响应
- `fixtures/demo_questions.json` — 5 个领域共 20 个问题
- `fixtures/demo_evidence.json` — 每领域 6–8 条观点，`CommunityPerspective` 字段完整
- `fixtures/demo_session.json` — 完整 Vicky 会话（6 个阶段全部预填）
- `GET /api/v1/sessions/demo` — 加载并返回演示会话
- `config.py` 中的 `FallbackConfig`，所有兜底默认为 `true`

**前端**：

- `mindmine/frontend/` 脚手架：Vite + Vue 3 + TypeScript + Tailwind
- Vue Router 定义全部 7 个路由
- 7 个页面骨架（标题 + 主内容区，暂不做样式打磨）
- Pinia store：`session`、`profile`、`questions`
- `api/client.ts` 的 axios 实例 + 所有接口的类型化封装
- 逐阶段导航完整可用：6 个阶段能点着走完

**新建文件**：

```
mindmine/
  .env.example
  .gitignore
  README.md
  backend/
    main.py
    config.py
    database.py
    requirements.txt
    routers/auth.py sessions.py profile.py questions.py
             interview.py insight.py challenge.py compose.py
    services/session_service.py
    models/session.py profile.py knowledge_state.py perspective.py
    fixtures/demo_questions.json demo_evidence.json demo_session.json
  frontend/
    package.json vite.config.ts tsconfig.json tailwind.config.ts
    src/main.ts App.vue router/index.ts
    src/stores/session.ts profile.ts questions.ts
    src/api/client.ts session.ts
    src/types/index.ts
    src/pages/（全部 7 个）
    src/components/（桩）
```

### 完成标准

- [ ] `cd backend && uvicorn main:app --reload` 无错启动
- [ ] `cd frontend && npm run dev` 无错启动
- [ ] `POST /api/v1/sessions` 返回会话 ID
- [ ] 浏览器中完整旅程可走通：落地页 → 手动画像 → 问题 → 访谈（3 轮）→ 洞察 → 挑战 → 成文
- [ ] 每个页面都能渲染内容（不是白屏或 500）
- [ ] `GET /api/v1/sessions/demo` 返回 6 个字段全部填充的合法会话
- [ ] 每次流转后 `GET /api/v1/sessions/{id}` 能返回当前状态

### 怎么测

```bash
# 后端冒烟测试
curl -s -X POST localhost:8000/api/v1/sessions | python3 -m json.tool
curl -s localhost:8000/api/v1/sessions/demo | python3 -m json.tool

# 人工：打开 http://localhost:5173，点完 6 个阶段
```

### 风险

- SQLite 异步初始化偶尔有坑；若 SQLAlchemy async 增加复杂度，直接用 `aiosqlite`。
- Vue Router history 模式需要开发服务器代理后端请求，在 `vite.config.ts` 配置 `proxy: {'/api': 'http://localhost:8000'}`。

---

## Phase 1 — 接入真实 LLM

**时长**：约 5 小时
**目标**：所有 Mock 的 AI 响应替换为真实 LLM 调用。知乎 API 仍为 Mock。演示会话兜底保持可用。

### 要建什么

**后端 `ai/` 模块**（全部 9 个，按优先级顺序接入）：

1. `interview_engine.py` — 用户感知最强，先接
2. `insight_extractor.py` — Stage 4，第一个 Wow Moment
3. `answer_composer.py` — Stage 6 产出，含防幻觉守卫
4. `profile_extractor.py` — Stage 1 手动路径
5. `question_matcher.py` — Stage 2 query 生成 + 重排序
6. `perspective_extractor.py` — Stage 5（知乎仍 Mock）
7. `challenge_selector.py` — Stage 5 选择逻辑
8. `insight_refiner.py` — Stage 6 的 V2
9. `knowledge_extractor.py` — 访谈过程中更新 KnowledgeState

**`backend/services/llm_service.py`**：

- OpenAI 兼容客户端，使用 `config.py` 中的 `LLM_BASE_URL` + `LLM_API_KEY`
- `complete(messages, response_format, temperature)`，遇 `LLMInvalidOutputError` 重试（最多 2 次）
- 超时：30 秒
- 兜底：LLM 不可用时抛 `LLMError`，router 返回演示数据中的 Mock 响应

**System Prompt** — 每模块一个常量，需实际验证效果：

- `INTERVIEW_SYSTEM_PROMPT` — 感知当前 `interview_stage`，禁止对用户做断言
- `INSIGHT_SYSTEM_PROMPT` — 要求 `evidence_keys` 引用真实 KnowledgeState 条目
- `COMPOSER_SYSTEM_PROMPT` — 强制来源标签、第一人称、不得暴露 AI 身份
- （其余见 TECH_DESIGN 第 12 节）

**KnowledgeState 更新器**：每轮访谈后，`knowledge_extractor` 对用户消息分类并追加到对应的 KnowledgeState 桶。阶段推进逻辑检查是否满足最小条目要求。

**`SanitizingFilter`** 注册到 root logger。

### 完成标准

- [ ] Stage 3 访谈返回真实 LLM 生成的问题（不是硬编码字符串）
- [ ] KnowledgeState 随轮次累积（通过 `GET /knowledge` 检查）
- [ ] Stage 4 洞察揭示展示基于 KnowledgeState 的真实洞察
- [ ] Stage 6 成文回答中至少包含一处可追溯到用户原话的片段
- [ ] 溯源校验器运行；无来源句子被标记（记日志，不阻塞）
- [ ] `LLM_BASE_URL` 未配置或不可达时，透明返回演示数据
- [ ] 任何日志行中都没有 LLM API Key

### 怎么测

```bash
# 配置真实 LLM
export LLM_BASE_URL=https://... LLM_API_KEY=... LLM_MODEL=claude-opus-5

# 人工走完访谈；4 轮后检查知识状态
curl -s localhost:8000/api/v1/sessions/{id}/knowledge | python3 -m json.tool

# 验证兜底：取消 LLM_BASE_URL 再跑一次，应返回演示内容
```

### 风险

- LLM 的结构化输出（JSON mode）在复杂 Pydantic schema 上可能失败；**尽早测试 `InsightOutput` 和 `AnswerOutput` 这两个 schema**。
- 访谈阶段推进依赖 KnowledgeState 达到最小条目数；若 LLM 抽取效果差，阶段可能卡住。**加一个 `force_advance` 开关供演示时使用。**

---

## Phase 2 — 接入真实知乎 API

**时长**：约 4 小时
**目标**：Mock 的知乎响应替换为真实 CLI 调用。OAuth 仍为 Mock（只走手动画像）。每个调用都有已测试的兜底。

### 要建什么

**`backend/services/zhihu_service.py`** — 完整实现：

- `_run()` 异步 subprocess 封装：解析 stdout JSON，非零退出或 `"ok": false` 时抛 `ZhihuServiceError`
- 全部 7 个方法（见 TECH_DESIGN 第 7 节）
- 限流处理：捕获 `Code: 30001`，立即抛 `ZhihuRateLimitError`（**不重试**）
- 每次 CLI 调用超时 30 秒

**社区观点管线** — 完整实现：

- `services/session_service.py` 中的 `build_perspectives()`
- 作者去重规则（每作者最多 2 条，未知作者独立桶）
- 从 URL 提取问题 ID 并过滤
- 合并 `search_answers` + `get_answer_summaries` 结果
- 逐条调用 `perspective_extractor`
- 多样性去重（关键词重合度启发式，MVP 不需要 embedding）
- 对最终列表调用 `challenge_selector`

**问题推荐管线** — 完整实现：

- `get_recommended_questions()`：`QuestionMatcher` 生成 2–4 个 query
- 真实结果不足 3 条时回落到 `demo_questions.json`

**后台预取**：Stage 4 确认 Insight V1 时，用异步后台任务触发 `build_perspectives()`，这样用户走到 Stage 5 时结果已就绪。

**`quota` 预检**：新增 `GET /api/v1/quota` 接口调用 `zhihu_service.get_quota()`。前端在应用加载时调用，若有 P0 能力额度为 0 则显示提示条。

### 完成标准

- [ ] `GET /api/v1/sessions/{id}/questions` 返回 3 个真实知乎问题（核对标题是否为真实内容）
- [ ] `GET /api/v1/sessions/{id}/challenge` 返回的观点带有指向真实知乎回答的 `source_url`
- [ ] 作者去重验证：用一个已知有多条同作者回答的问题测试，确认该作者最多 2 条
- [ ] 限流测试：Mock CLI 返回 `Code: 30001`，验证返回 `ZHIHU_RATE_LIMIT` 且兜底启用
- [ ] 兜底验证：设 `FALLBACK_MOCK_PERSPECTIVES=true`，确认返回演示证据
- [ ] `GET /api/v1/quota` 返回当前额度（真实调用，INFO 级别记录）

### 怎么测

```bash
# 验证真实问题推荐
curl -s localhost:8000/api/v1/sessions/{id}/questions | python3 -m json.tool
# → Items[0].source 应为 "api"，不是 "mock"

# 验证观点来源 URL 真实
curl -s localhost:8000/api/v1/sessions/{id}/challenge | python3 -m json.tool
# → data.source_url 应包含 "zhihu.com/question/.../answer/..."

# 跑单元测试
cd backend && pytest tests/test_zhihu_service.py tests/test_perspective_pipeline.py -v
```

### 风险

- 同一问题的 `search zhihu` 和 `question answers` 结果可能重叠；**在进入下一阶段前先测通合并去重逻辑**。
- 后台观点预取不得阻塞 Stage 4 响应。用 `asyncio.create_task()`，**不要 `await`**。
- 若演示机器未配置 Access Secret，所有知乎调用都会失败。**本阶段开始前先跑 `zhihu-cli auth status --verify` 确认。**

---

## Phase 3 — 接入 OAuth

**时长**：约 3 小时
**目标**：知乎 OAuth 登录可用，从真实关注/收藏/创作提取用户画像。手动画像兜底保持可用。

### 要建什么

**`routers/auth.py`** — 完整实现：

- `GET /api/v1/oauth/url` — 生成 state、存入会话、返回授权 URL
- `GET /api/v1/oauth/callback` — 校验 state（5 分钟 TTL、单次有效）、用 code 换 token、拉取 `/user` 资料
- state 与 `oauth_state_created_at` 时间戳一起存入会话记录

**`ZhihuService.get_oauth_user_data()`** — HTTP 调用（非 CLI）：

- `GET https://developer.zhihu.com/api/v1/user/followees`（带 `X-OAuth-Token`）
- `GET https://developer.zhihu.com/api/v1/user/contents`（带 `X-OAuth-Token`）
- 近期收藏
- 返回 `{profile, followees, favorites, contents}`

**`ProfileExtractor`** — OAuth 路径：输入合并后的 OAuth 数据，输出 `UserProfile`（与手动路径同 schema）。

**前端 OAuth 流程**：

- `OnboardOAuthPage.vue` — 「用知乎登录」按钮，触发 `GET /oauth/url` 后跳转
- 回调由 `OnboardOAuthPage.vue` 处理（读取 `?code=&state=` 参数）
- 后端拉取和提取期间显示加载态
- 提取完成后展示可编辑的领域卡片

**兜底**：`ZHIHU_OAUTH_APP_ID` 或 `ZHIHU_OAUTH_APP_KEY` 未配置时，OAuth 按钮替换为「暂不登录，手动填写」，直接进入手动路径。

### 完成标准

- [ ] OAuth 全流程走通：授权 → 回调 → 画像提取 → 可编辑领域卡片
- [ ] state 不匹配返回 HTTP 400（手动改 `state` 参数测试）
- [ ] state 过期（> 5 分钟）返回 HTTP 400
- [ ] 提取出的画像领域与测试账号实际关注/收藏相符
- [ ] `raw_oauth_data` 存入会话但**绝不出现在任何 API 响应中**
- [ ] OAuth token 不出现在任何日志行
- [ ] `ZHIHU_OAUTH_APP_KEY` 未配置时，OAuth 按钮优雅降级到手动路径

### 怎么测

```bash
# 配置好真实 OAuth 凭证后：
# 1. 打开 http://localhost:5173
# 2. 点「用知乎登录」
# 3. 在浏览器完成知乎授权
# 4. 确认返回后出现领域卡片

# state 校验测试：
curl "localhost:8000/api/v1/oauth/callback?code=test&state=WRONG"
# → HTTP 400，OAUTH_STATE_MISMATCH

# 无 OAuth 凭证时：
# unset ZHIHU_OAUTH_APP_ID
# → 落地页只显示「手动填写」按钮
```

### 风险

- OAuth 的 `redirect_uri` 必须与赛事页面登记值**完全一致**。在拿到 App ID / Key 之前，本阶段使用 Mock OAuth 流程（后端生成假 token 并跳过交换步骤）。**这是演示日最可能部分 Mock 的阶段，这是可接受的。**
- `httpx` 异步调用知乎 HTTP API 的超时处理可能与 subprocess CLI 调用不同。

---

## Phase 4 — 界面打磨 + Wow Moment

**时长**：约 4 小时
**目标**：两个 Wow Moment 动画落地，视觉足够自信地演示，所有页面处理好加载/错误/空状态。

### 要建什么

**设计 Token**（`tailwind.config.ts`）：

- 中性色阶：从接近白 `oklch(97% 0.005 250)` 到接近黑 `oklch(14% 0.010 250)`，10 级
- 强调色：单一克制的颜色（建议 `oklch(58% 0.18 250)` — 深靛蓝，自信但不咄咄逼人）
- Token 命名：`surface`、`surface-raised`、`border`、`muted`、`body`、`accent`、`accent-hover`
- 深色模式 Token 组（强调色降低 chroma、提高 lightness）
- WCAG AA 验证：正文文字与背景对比度 ≥ 4.5:1

**`InsightReveal.vue`** — Wow Moment 动画组件：

- 父组件挂载后延迟 200ms 淡入
- Surface Claim 先出现（大字号、居中、短暂停顿）
- Deep Insight 随后在下方淡入（150ms 过渡，opacity + translateY）
- **不用流式打字光标** — 全文一次性出现
- `prefers-reduced-motion`：跳过动画，直接显示

**Stage 4 页面**（`InsightPage.vue`）：

- 全幅布局，界面元素极简
- 三个按钮有清晰视觉层级：「就是这个」（强调色，主按钮）、「接近，但还不对」（次级）、「我要修改」（幽灵按钮）
- 「我要修改」进入内联编辑：textarea 替换 deep insight 文本，附确认按钮

**Stage 6 页面**（`ComposePage.vue`）：

- V1 → 挑战 → 回应 → V2 演进：以 4 步时间线呈现
- V2 揭示使用 `InsightReveal.vue`，标题为「这才是你真正想说的。」
- 成文回答放在可编辑 `textarea` 中，带字数统计
- 三个按钮：[编辑回答] [复制回答] [去知乎发布]
- 「去知乎发布」执行 `window.open(questionUrl, '_blank')`，提示语：「我们会帮你打开知乎页面，你来发布。」

**所有页面**：

- 加载骨架屏与最终布局一致（**不用转圈 spinner**）
- 错误态：人话提示 + 重试按钮（或「使用演示数据」，若兜底可用）
- 空状态：仅问题卡片需要（返回不足 3 条时）

**`InterviewPage.vue` 中的状态指示器**：

- `StateIndicator.vue`：横向面包屑展示 DISCOVERY / EXPERIENCE / CONFLICT / REFLECTION / INSIGHT，高亮当前状态
- 更新时**不得导致布局跳动**

**`QuestionCard.vue`**：

- 标题、「为什么适合你」一行、「我有话说」按钮
- Hover 态：轻微 `surface-raised` 背景 + 边框色变化
- 按钮点击区域 44px

### 完成标准

- [ ] 两个 Wow Moment 页面的观感与访谈流程明显不同
- [ ] 洞察揭示动画播放正确；`prefers-reduced-motion` 下跳过动画
- [ ] Stage 6 中 V1 与 V2 视觉上可区分
- [ ] 「去知乎发布」打开正确的问题 URL（新标签页）
- [ ] 复制按钮使用 `navigator.clipboard.writeText()`，显示「已复制」确认 2 秒
- [ ] 所有交互元素在浅色和深色模式下都有可见的焦点环
- [ ] 每个页面都有非空白的错误态
- [ ] 正文文字对比度通过 WCAG AA（在 DevTools 无障碍面板验证）

### 怎么测

- 人工视觉 QA：7 个页面 × 浅色/深色两种模式
- 键盘导航：Tab 遍历所有交互元素，确认焦点顺序合理
- 模拟错误态：临时让后端返回 500，确认错误界面正常
- 移动端视口测试（375px）：确认布局重排、按钮可点

### 风险

- 动画节奏第一版往往感觉不对；**为 Wow Moment 1 的时序调优单独预留 30 分钟**。
- Clipboard API 需要 HTTPS 或 localhost；开发环境没问题，部署演示需要 HTTPS。
- 深色模式：若时间紧张，**宁可只交付一套完整的浅色主题**，也不要赶一个粗糙的深色模式。

---

## Phase 5 — 演示加固 + 最终集成

**时长**：约 4 小时（演示前最后几小时）
**目标**：演示日零意外。所有失败模式都已演练过。Vicky 演示能从 `demo_session.json` 完美跑通。额度已核实。

### 要建什么

**`GET /api/v1/sessions/demo`** — 最终校验：

- 返回 6 个阶段全部填充的完整 Vicky 会话
- 所有观点的 `source_url` 指向演示所用的真实问题 URL
- 所有 `USER_QUOTE` 条目包含 Vicky 的真实演示原话
- `composed_answer` 是打磨过的 Vicky 回答，已人工审阅质量

**前端额度预检**：

- 应用加载时调用 `GET /api/v1/quota`
- 若 `creator` 剩余 < 3 或 `zhihu_search` 剩余 < 3，显示可关闭的提示条：「知乎 API 今日额度偏低，将使用演示数据备份」
- 这是无声的体验设计，**不是阻塞性错误**

**兜底验证** — 逐个关闭真实服务跑完整链路：

- `FALLBACK_MOCK_QUESTIONS=true` — 确认演示问题出现，标签一致
- `FALLBACK_MOCK_PERSPECTIVES=true` — 确认演示观点出现，source URL 真实可信
- `FALLBACK_MOCK_LLM=true` — 确认演示会话内容加载，访谈返回演示响应
- **三个同时开启** — 确认完整演示能跑完

**前端加载演示会话**：

- 落地页支持 `?demo=1` URL 参数
- 检测到该参数时，自动从 `GET /api/v1/sessions/demo` 创建会话并跳转到 Stage 6
- 这是给评委的「直接看结果」快捷入口

**README.md**（最终版）：

- 安装说明（3 条命令跑起来）
- 所需环境变量及获取途径
- 演示运行方式（`?demo=1`）
- 已知限制（OAuth 待 App ID、Skill 命名冲突、代码签名说明）

**最终单元测试**：

- `pytest tests/ -v` 必须 0 失败
- 演示前修完所有不稳定的测试

### 完成标准

- [ ] `?demo=1` 快捷入口加载 Vicky 会话并落到 Stage 6 成文页
- [ ] 完整人工演示（不走快捷方式）4 分钟内跑完
- [ ] 全兜底状态下的完整演示表现一致
- [ ] 额度检查显示当前状态；额度低时提示条出现
- [ ] `pytest tests/ -v` 0 失败
- [ ] `README.md` 的安装说明在全新 clone 下可用
- [ ] 演示过程中浏览器控制台无报错
- [ ] 「去知乎发布」打开正确的问题 URL（用演示问题实测）

### 怎么测

```bash
# 完整演示彩排
open "http://localhost:5173?demo=1"
# → 应落到成文页，Vicky 回答已预填

# 兜底彩排
FALLBACK_MOCK_QUESTIONS=true FALLBACK_MOCK_PERSPECTIVES=true \
  FALLBACK_MOCK_LLM=true uvicorn main:app --reload &
# 走完整旅程 — 必须无可见差异地跑完

# 单元测试
cd backend && pytest tests/ -v --tb=short

# 额度检查
curl localhost:8000/api/v1/quota | python3 -m json.tool
```

### 风险

- 演示机器网络问题：确保 `demo_session.json` 和所有兜底数据**完整到足以离线跑完整个 Vicky 叙事**。
- Vite 生产构建与开发服务器行为可能不同：**演示日前至少完整测试一次 `npm run build && npm run preview`**。
- 浏览器弹窗拦截可能拦下「去知乎发布」的 `window.open()`。**用 `<a target="_blank">` 替代 JS `window.open()` 可规避。**

---

## 时间线汇总

```
Day 1
  09:00 – 15:00  Phase 0  地基 + Mock 旅程          （6h）
  15:00 – 20:00  Phase 1  接真实 LLM                （5h）

Day 2
  09:00 – 13:00  Phase 2  接真实知乎 API            （4h）
  13:00 – 16:00  Phase 3  接 OAuth                  （3h）
  16:00 – 20:00  Phase 4  界面打磨 + Wow Moment     （4h）
  20:00 – 00:00  Phase 5  演示加固                  （4h）
```

总计约 26 小时有效开发，两天内留出约 22 小时缓冲，用于迭代、调试和处理意外阻塞。

---

## 多人协作时的依赖顺序

Phase 0 之后，若有两人并行：

| A 同学 | B 同学 |
|---|---|
| Phase 1：`interview_engine` + `insight_extractor` + `answer_composer` | Phase 1：`profile_extractor` + `question_matcher` + `perspective_extractor` |
| Phase 2：`zhihu_service` + 问题管线 | Phase 2：观点管线 + 挑战选择 |
| Phase 3：OAuth 后端 | Phase 4：界面打磨启动（设计 Token + 页面骨架） |
| Phase 3：OAuth 前端 | Phase 4：Wow Moment 动画 |
| Phase 5：演示加固（共同） | Phase 5：README + 测试 |

**依赖边界是 `ZhihuService` 接口**：只要在 Phase 2 开始时把 `zhihu_service.py` 的方法签名约定并冻结，A 可以先 mock 它，B 同时实现它。

---

## 时间不够时砍什么

按「最后才砍 → 最先砍」排序：

1. **永远保留**：Mock 完整旅程（Phase 0）、Wow Moment 动画（Phase 4 部分）、演示兜底系统（Phase 5）
2. **最先砍**：OAuth（Phase 3）— 手动画像是完整可用的替代方案
3. **其次砍**：深色模式 — 只交付一套完整的浅色主题
4. **再次砍**：知识库上传（`knowledge upload`）— 它本来就是 P2
5. **接着砍**：额度提示条 — 额度查询接口保留，提示条只是锦上添花
6. **最后才动核心**：多 query 问题推荐 — 退回单 query

**无论如何都不能砍的**：演示会话接口、观点的原文链接、溯源校验器、「去知乎发布」的 URL 打开功能。
