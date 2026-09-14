# MindMine 技术设计文档

> **版本**：0.1.0-draft
> **日期**：2026-09-13
> **状态**：待确认，确认后方可进入编码

**全文标注约定**：
- 🟢 **真实 API** — 已验证的知乎 CLI 调用或确认存在的 HTTP 接口
- 🤖 **LLM** — 结构化 prompt → Pydantic 输出，不调用外部服务
- 🟡 **Mock / 兜底** — 真实服务不可用时使用的本地预置数据

---

## 1. 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        浏览器（Vue 3）                           │
│  Stage1  Stage2  Stage3  Stage4  Stage5  Stage6                 │
└───────────────────────┬─────────────────────────────────────────┘
                        │ HTTP / JSON
┌───────────────────────▼─────────────────────────────────────────┐
│                   FastAPI（单进程）                              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐    │
│  │  Session     │  │  AI 层       │  │  ZhihuService      │    │
│  │  Manager     │  │ （LLM 调用） │  │ （CLI 适配层）      │    │
│  └──────┬───────┘  └──────┬───────┘  └────────┬───────────┘    │
│         │                 │                    │                │
│  ┌──────▼─────────────────▼────────────────────▼───────────┐   │
│  │                 SQLite（sessions.db）                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
          │                           │
          ▼                           ▼
   LLM API（OpenAI 兼容）      zhihu-cli 二进制
   （env: LLM_BASE_URL）       （env: ZHIHU_CLI_PATH）
```

单进程、无消息队列、无微服务。这是 48 小时黑客松项目的正确选择。所有状态落在 SQLite，进程重启不丢会话。

---

## 2. 前端架构

**技术栈**：Vue 3 + TypeScript + Vite + Pinia + Vue Router + Tailwind CSS

```
frontend/
  src/
    main.ts
    App.vue
    router/
      index.ts               # 7 个页面的路由定义
    stores/
      session.ts             # Pinia：sessionId、stage、KnowledgeState 缓存
      profile.ts             # Pinia：UserProfile
      questions.ts           # Pinia：QuestionCard[]
    pages/
      LandingPage.vue
      OnboardOAuthPage.vue
      OnboardManualPage.vue
      QuestionsPage.vue
      InterviewPage.vue      # Stage 3 — 核心循环
      InsightPage.vue        # Stage 4 — Wow Moment 1
      ChallengePage.vue      # Stage 5
      ComposePage.vue        # Stage 6 — Wow Moment 2
    components/
      QuestionCard.vue
      ChatTurn.vue
      InsightReveal.vue      # Wow Moment 揭示动画组件
      PerspectiveCard.vue
      AnswerEditor.vue
      StateIndicator.vue     # DISCOVERY / EXPERIENCE / CONFLICT / REFLECTION / INSIGHT
    api/
      client.ts              # axios 实例，baseURL 来自 env
      session.ts             # 所有后端调用的类型化封装
    types/
      index.ts               # 与后端 Pydantic 模型对应的 TS 类型
```

**状态管理原则**：Pinia store 只存 UI 状态和 API 响应缓存。KnowledgeState 和会话数据以后端为准。刷新页面时 store 失效并重新拉取，**不持久化到 localStorage**（避免跨会话的脏状态）。

**路由表**：

```
/                           → LandingPage
/onboard/oauth              → OnboardOAuthPage
/onboard/manual             → OnboardManualPage
/questions/:sessionId       → QuestionsPage
/interview/:sessionId       → InterviewPage
/insight/:sessionId         → InsightPage
/challenge/:sessionId       → ChallengePage
/compose/:sessionId         → ComposePage
```

---

## 3. 后端架构

**技术栈**：Python 3.11+ + FastAPI + Pydantic v2 + httpx + SQLite（aiosqlite）

```
backend/
  main.py                   # FastAPI 应用、lifespan、CORS
  config.py                 # 环境变量（pydantic-settings）
  database.py               # SQLite 连接与建表
  routers/
    auth.py                 # OAuth 流程
    sessions.py             # 会话 CRUD
    profile.py              # Stage 1
    questions.py            # Stage 2
    interview.py            # Stage 3
    insight.py              # Stage 4
    challenge.py            # Stage 5
    compose.py              # Stage 6
  services/
    zhihu_service.py        # ZhihuService — 所有 CLI 调用集中于此
    llm_service.py          # LLMService — 所有 LLM 调用集中于此
    session_service.py      # 会话状态流转
  ai/
    profile_extractor.py    # 🤖 LLM 模块
    question_matcher.py     # 🤖 LLM 模块
    interview_engine.py     # 🤖 LLM 模块
    knowledge_extractor.py  # 🤖 LLM 模块
    insight_extractor.py    # 🤖 LLM 模块
    perspective_extractor.py # 🤖 LLM 模块
    challenge_selector.py   # 🤖 LLM 模块
    insight_refiner.py      # 🤖 LLM 模块
    answer_composer.py      # 🤖 LLM 模块
  models/
    session.py              # 数据模型
    profile.py
    knowledge_state.py
    perspective.py
  fixtures/
    demo_questions.json     # 🟡 Mock：5 个领域共 20 个问题
    demo_evidence.json      # 🟡 Mock：按领域组织的预置观点
    demo_session.json       # 🟡 Mock：完整的 Vicky 演示会话
```

---

## 4. 数据模型

全部使用 Pydantic v2。SQLite 以 JSON blob 存储复杂字段。

### UserProfile（用户画像）

```python
class UserProfile(BaseModel):
    session_id: str
    source: Literal["oauth", "manual"]   # 画像来源
    domains: list[str]                    # 如 ["AI", "前端"]
    experience_level: Literal["early_career", "mid_career", "senior", "curious"]
    interests: list[str]
    share_preferences: list[str]          # 如 ["踩过的坑", "对比分析"]
    raw_oauth_data: dict | None = None    # 存库但不返回给前端
```

### QuestionCard（问题卡片）

```python
class QuestionCard(BaseModel):
    question_id: str           # 从 URL 中提取
    title: str                 # 🟢 来自知乎 API
    url: str                   # 🟢 来自知乎 API
    why_fits: str              # 🤖 由 QuestionMatcher 生成
    source: Literal["api", "mock"]   # 审计追踪：区分真实与兜底
```

### KnowledgeState（知识状态）

```python
class EvidenceItem(BaseModel):
    text: str
    source: Literal["USER_QUOTE", "USER_FACT", "USER_EVENT",
                    "USER_BELIEF", "USER_CONFLICT", "USER_REFLECTION"]
    turn: int
    confirmed: bool = True     # 只有 True 的条目可进入最终回答

class KnowledgeState(BaseModel):
    session_id: str
    question_url: str
    question_title: str
    facts: list[EvidenceItem] = []
    events: list[EvidenceItem] = []
    beliefs: list[EvidenceItem] = []
    conflicts: list[EvidenceItem] = []
    reflections: list[EvidenceItem] = []
    candidate_insights: list[str] = []
    interview_stage: Literal[
        "DISCOVERY", "EXPERIENCE", "CONFLICT", "REFLECTION", "INSIGHT"
    ] = "DISCOVERY"
    turn_count: int = 0
```

### Insight（洞察）

```python
class Insight(BaseModel):
    version: Literal["V1", "V2"]
    surface_claim: str          # 一句话，「暴论」版本
    deep_insight: str           # 2-3 句
    confirmed_by_user: bool = False
    user_edited_text: str | None = None   # 用户点「我要修改」后的文本
    # 溯源：每个洞察必须引用至少一条 EvidenceItem
    evidence_keys: list[str]    # 如 ["events[0]", "conflicts[1]"]
```

### CommunityPerspective（社区观点）

```python
class CommunityPerspective(BaseModel):
    id: str                     # uuid
    claim: str                  # 🤖 PerspectiveExtractor 提取
    reason: str                 # 🤖 提取，必须被 evidence_text 支撑
    author: str                 # 🟢 来自 AuthorName 字段
    badge: str                  # 🟢 来自 AuthorBadgeText 字段
    authority_level: str        # 🟢 来自 AuthorityLevel 字段
    source_url: str             # 🟢 来自 Url 字段
    evidence_text: str          # 🟢 原始 ContentText（可能被截断）
    source: Literal["api", "mock"]
```

### Session（会话记录）

```python
class Session(BaseModel):
    id: str                     # uuid
    created_at: datetime
    updated_at: datetime
    stage: int                  # 1-6
    profile: UserProfile | None
    selected_question: QuestionCard | None
    knowledge_state: KnowledgeState | None
    insight_v1: Insight | None
    challenge_perspective: CommunityPerspective | None
    challenge_response: str | None
    insight_v2: Insight | None
    composed_answer: str | None
    oauth_token: str | None     # 加密存储，绝不写入日志
```

---

## 5. 会话状态机

```
                        ┌─────────────┐
                        │  CREATED    │  POST /sessions
                        └──────┬──────┘
                               │ 画像已保存
                        ┌──────▼──────┐
                        │  PROFILED   │  POST /sessions/{id}/profile
                        └──────┬──────┘
                               │ 问题已选择
                        ┌──────▼──────┐
                        │  QUESTION   │  POST /sessions/{id}/question
                        └──────┬──────┘
                               │ 访谈进行中
                        ┌──────▼──────┐
                        │ INTERVIEWING│  POST /sessions/{id}/turn（多次）
                        └──────┬──────┘
                               │ 洞察已确认
                        ┌──────▼──────┐
                        │  INSIGHT_V1 │  POST /sessions/{id}/insight/confirm
                        └──────┬──────┘
                               │ 挑战已回应
                        ┌──────▼──────┐
                        │ CHALLENGED  │  POST /sessions/{id}/challenge/respond
                        └──────┬──────┘
                               │ 回答已生成
                        ┌──────▼──────┐
                        │  COMPOSED   │  POST /sessions/{id}/compose
                        └─────────────┘
```

状态流转在**服务端校验**。会话还在 `PROFILED` 状态时请求 `/challenge/respond` 会返回 HTTP 409。

---

## 6. API 设计

全部挂在 `/api/v1/` 下。统一响应格式：

```json
{"ok": true, "data": {...}}
{"ok": false, "error": {"code": "...", "message": "..."}}
```

### 会话

```
POST   /api/v1/sessions                        创建会话，返回 id
GET    /api/v1/sessions/{id}                   完整会话状态
```

### Stage 1 — 画像

```
POST   /api/v1/sessions/{id}/profile/oauth     交换 OAuth code，提取画像
POST   /api/v1/sessions/{id}/profile/manual    提交手动表单
PATCH  /api/v1/sessions/{id}/profile           编辑画像（增删领域）
```

### Stage 2 — 问题

```
GET    /api/v1/sessions/{id}/questions         获取 3 个推荐问题
POST   /api/v1/sessions/{id}/question          选定问题
```

### Stage 3 — 访谈

```
POST   /api/v1/sessions/{id}/turn              提交用户消息，返回 AI 提问
GET    /api/v1/sessions/{id}/knowledge         当前 KnowledgeState
```

### Stage 4 — 洞察

```
GET    /api/v1/sessions/{id}/insight           获取当前 Insight V1
POST   /api/v1/sessions/{id}/insight/confirm   用户确认「就是这个」
POST   /api/v1/sessions/{id}/insight/refine    用户选「接近」，退回访谈
PATCH  /api/v1/sessions/{id}/insight           用户提交编辑后的洞察
```

### Stage 5 — 挑战

```
GET    /api/v1/sessions/{id}/challenge         获取挑战观点（触发抓取）
POST   /api/v1/sessions/{id}/challenge/respond 用户回应挑战
```

### Stage 6 — 成文

```
POST   /api/v1/sessions/{id}/compose           生成回答（幂等）
GET    /api/v1/sessions/{id}/compose           获取已生成回答
PATCH  /api/v1/sessions/{id}/compose           用户内联编辑回答
```

### OAuth

```
GET    /api/v1/oauth/url                       返回带 state 的知乎授权 URL
GET    /api/v1/oauth/callback                  接收 code + state，交换 token
```

---

## 7. ZhihuService — CLI 适配层

所有知乎能力调用封装于此。**其他任何模块不得执行 CLI 命令。**

```python
# backend/services/zhihu_service.py

class ZhihuServiceError(Exception):
    code: str  # 与知乎 CLI 错误码对应

class ZhihuService:
    def __init__(self, cli_path: str, timeout: int = 30):
        self.cli_path = cli_path  # 来自环境变量 ZHIHU_CLI_PATH
        self.timeout = timeout

    async def _run(self, *args) -> dict:
        """执行 CLI，解析 stdout JSON，失败时抛 ZhihuServiceError。"""
        ...

    # 🟢 真实 API — question recommend --query
    async def recommend_questions(self, query: str, count: int = 5) -> list[dict]:
        ...

    # 🟢 真实 API — search zhihu（唯一带作者信息的来源）
    async def search_answers(self, query: str, count: int = 10) -> list[dict]:
        ...

    # 🟢 真实 API — question answers
    async def get_answer_summaries(
        self, question_url: str, limit: int = 10, offset: int = 0
    ) -> dict:  # 返回 Items + Paging
        ...

    # 🟢 真实 API — me followees
    async def get_followees(self, limit: int = 20) -> list[dict]:
        ...

    # 🟢 真实 API — me favorites recent
    async def get_recent_favorites(self, limit: int = 20) -> list[dict]:
        ...

    # 🟢 真实 API — me contents
    async def get_my_contents(
        self, type: str = "all", limit: int = 20
    ) -> list[dict]:
        ...

    # 🟢 真实 API — quota
    async def get_quota(self, api_ids: list[str] | None = None) -> list[dict]:
        ...

    # HTTP 调用（非 CLI）— OAuth 用户数据
    # 🟢 真实 API — /api/v1/user/followees 带 X-OAuth-Token
    async def get_oauth_user_data(
        self, oauth_token: str
    ) -> dict:  # followees + favorites + contents
        ...
```

**本类强制执行的规则**：

1. 全部异步（subprocess + asyncio）。
2. CLI 报错（非零退出或 `"ok": false`）转换为携带原始 `code` 的 `ZhihuServiceError`。
3. 限流错误（`Code: 30001`）立即上抛，**不重试**。
4. 绝不记录 OAuth token 或 Access Secret 原值。

---

## 8. OAuth 方案

### 流程

```
前端                         后端                        知乎
  │                           │                           │
  │  GET /api/v1/oauth/url    │                           │
  │──────────────────────────►│                           │
  │  {url, state}             │ 生成随机 state            │
  │◄──────────────────────────│ 存入会话                  │
  │                           │                           │
  │  跳转到知乎───────────────┼───────────────────────────►
  │                           │                           │
  │◄──── 回调带 code + state ─────────────────────────────│
  │                           │                           │
  │  GET /oauth/callback      │                           │
  │  ?code=...&state=...      │                           │
  │──────────────────────────►│ 校验 state                │
  │                           │──── POST /access_token ──►│
  │                           │◄─── {access_token} ───────│
  │                           │                           │
  │                           │  GET /user（带 oauth token）│
  │                           │──────────────────────────►│
  │                           │◄─── 用户资料 ─────────────│
  │                           │                           │
  │  {会话已跳转}              │  通过 HTTP API 拉取        │
  │◄──────────────────────────│  关注/收藏/创作            │
```

**state 校验**：用 `secrets.token_urlsafe(32)` 生成，存入会话记录，回调时校验。不匹配、过期（5 分钟 TTL）或重复使用均返回 HTTP 400。

**Token 存储**：OAuth access token 存入 SQLite 会话记录。绝不写日志、绝不返回给前端、绝不出现在错误信息中。

**凭证配置**：

```
ZHIHU_OAUTH_APP_ID      # 公开，可入源码
ZHIHU_OAUTH_APP_KEY     # 机密，绝不入源码
ZHIHU_OAUTH_REDIRECT_URI
```

> ⚠️ **注意**：App ID 和 App Key 需在赛事页面创建项目后获取。在拿到之前，OAuth 流程使用 Mock 响应。详见第 14 节兜底方案。

---

## 9. 画像提取方案

### OAuth 路径 🟢 + 🤖

```
ZhihuService.get_oauth_user_data(token)
  → 关注列表（Fullname + Headline 字段）
  → 近期收藏（Title + Summary 字段）
  → 个人创作（Title + Summary + ContentType 字段）
  ↓
ProfileExtractor（LLM）
  输入：{followees: [...], favorites: [...], contents: [...]}
  输出：UserProfile（结构化）
```

**ProfileExtractor 契约**：

- 输入是包含上述三类数据的 JSON。
- 输出是 `UserProfile` Pydantic 对象（JSON Schema 写在 system prompt 中）。
- **LLM 不得依据常识推断领域**——只能依据数据中实际出现的内容。
- 数据为空或含糊时，返回 `domains: []`，**不要猜**。

### 手动路径 🤖

三个表单字段 → ProfileExtractor 映射到同一个 `UserProfile` schema。Prompt 更简单，输出格式一致。

---

## 10. 问题推荐方案

```python
async def get_recommended_questions(
    session_id: str, profile: UserProfile
) -> list[QuestionCard]:

    # 1. 🤖 QuestionMatcher 根据画像生成 2-4 个 query
    queries = await question_matcher.generate_queries(profile)
    # 如 ["AI 编程工具", "前端工程师职业成长", "程序员转型"]

    # 2. 🟢 真实 API：对每个 query 调用 question recommend --query
    candidates = []
    for q in queries:
        try:
            results = await zhihu_service.recommend_questions(q, count=5)
            candidates.extend(results)
        except ZhihuServiceError as e:
            if e.code == "RATE_LIMIT":
                break          # 限流：停止，不重试
            # 其他错误：继续尝试剩余 query

    # 3. 按 URL 去重
    seen = set()
    unique = [c for c in candidates if not (c["Url"] in seen or seen.add(c["Url"]))]

    # 4. 🟡 兜底：不足 3 条时用 demo_questions.json 补齐
    if len(unique) < 3:
        unique = fill_from_demo(unique, profile, target=5)

    # 5. 🤖 QuestionMatcher 重排序，返回 top 3 并生成 why_fits
    ranked = await question_matcher.rerank(unique[:10], profile)
    return ranked[:3]
```

**QuestionMatcher 重排序契约**：

- 给定 N 个问题标题和一个 UserProfile，返回排序后的 3 条，每条附 `why_fits`。
- `why_fits` 必须引用画像中的具体元素（domains、interests、share_preferences）。
- 不得生成与用户画像矛盾的 `why_fits`。

---

## 11. 社区观点管线（Community Perspective Pipeline）

该管线在 Stage 4 开始时（Insight V1 生成后）**后台执行**，这样用户走到 Stage 5 时结果已就绪。

```python
async def build_perspectives(
    question_title: str, question_url: str, insight_v1: Insight
) -> list[CommunityPerspective]:

    question_id = extract_question_id(question_url)
    # 从 "https://www.zhihu.com/question/..." 提取 "2077824745589028563"

    # --- 数据采集 ---

    # 🟢 真实 API：主数据源（含 author、badge、ContentText）
    search_results = await zhihu_service.search_answers(
        query=question_title, count=10
    )

    # 🟢 真实 API：辅助数据源（摘要覆盖面、分页）
    answer_summaries = await zhihu_service.get_answer_summaries(
        question_url=question_url, limit=10
    )

    # 按 URL 中的问题 ID 过滤，只保留目标问题的回答
    filtered_search = [
        r for r in search_results
        if question_id in r.get("Url", "")
    ]

    # 按回答 ID 合并，search 结果优先（字段更丰富）
    merged = merge_by_answer_id(filtered_search, answer_summaries["Items"])

    # 🟡 兜底：不足 3 条时从 demo_evidence.json 加载
    if len(merged) < 3:
        merged = load_demo_evidence(question_id, domain=profile.domains[0])

    # --- 作者去重 ---
    # 全集范围内，同一作者最多 2 条观点
    author_counts: dict[str, int] = {}
    deduped = []
    for item in merged:
        author = item.get("AuthorName", "unknown")
        if author_counts.get(author, 0) < 2:
            deduped.append(item)
            author_counts[author] = author_counts.get(author, 0) + 1

    # --- 观点提取 ---
    # 🤖 PerspectiveExtractor：每条一次 LLM 调用（或 3 条一批）
    # 契约：claim 和 reason 必须被 evidence_text 支撑
    # 若 ContentText 不足以支撑一个连贯主张，该条返回 None
    perspectives = []
    for item in deduped[:8]:
        p = await perspective_extractor.extract(item)
        if p is not None:
            perspectives.append(p)

    # --- 多样性过滤 ---
    # 去除近似重复的 claim（关键词重合度 > 70% 即视为重复；
    # 若有 embedding 能力则用余弦相似度 > 0.85）
    diverse = deduplicate_by_diversity(perspectives)

    return diverse
```

### 作者去重规则（在 `merge_by_answer_id` 中强制执行）

1. 候选集中每个 `AuthorName` 最多保留 2 条。
2. 某作者超过 2 条时，保留 `ContentText` 最长的 2 条。
3. 作者缺失（`AuthorName` 为空）归入独立桶——「未知作者」总共最多 2 条。

> **为什么需要这条规则**：审计实测中，6 个观点里有 4 个来自同一位作者（因为他的回答最长、论证最密）。若不去重，社区观点会退化成「单人观点集」，丧失「社区」的代表性。

### 挑战选择 🤖

```python
async def select_challenge(
    perspectives: list[CommunityPerspective],
    insight_v1: Insight
) -> CommunityPerspective | None:
    """
    ChallengeSelector 契约：
    - 给定 Insight V1 和观点列表，找出最直接挑战该洞察核心主张、
      且证据支撑清晰的那一条。
    - 若没有任何观点构成真正的挑战：
      返回视角差异最大的那条，并将 challenge_type 标为
      "alternative_view"（另一种视角）而非 "counterargument"（反论）。
    - 绝不编造挑战。列表为空时返回 None。
    """
```

**排序依据优先级**（实测 `VoteUpCount` 为空，不可用于排序）：

1. 与用户 Insight 的相关性
2. 观点差异度
3. 来源多样性
4. 作者权威信息（`AuthorityLevel` / `AuthorBadgeText`）——**仅作辅助**

---

## 12. LLM 结构化输出

每个 AI 模块遵循同一模式：

```python
# 示例：InsightExtractor
class InsightOutput(BaseModel):
    surface_claim: str
    deep_insight: str
    evidence_keys: list[str]   # 必须引用真实存在的 KnowledgeState 键
    confidence: Literal["high", "medium", "low"]

class InsightExtractor:
    async def extract(self, knowledge_state: KnowledgeState) -> InsightOutput:
        messages = [
            {"role": "system", "content": INSIGHT_SYSTEM_PROMPT},
            {"role": "user", "content": knowledge_state.model_dump_json()}
        ]
        response = await llm_service.complete(
            messages=messages,
            response_format=InsightOutput,   # 结构化输出
            temperature=0.3
        )
        return InsightOutput.model_validate(response)
```

**LLMService**：

```python
class LLMService:
    async def complete(
        self,
        messages: list[dict],
        response_format: type[BaseModel],
        temperature: float = 0.3
    ) -> dict:
        # 调用 OpenAI 兼容接口
        # 返回符合 response_format schema 的已解析 JSON
        # 失败时抛 LLMError
        ...
```

**各模块 temperature 设定**：

| 模块 | temperature | 理由 |
|---|---|---|
| ProfileExtractor | 0.1 | 分类任务，不需要创造性 |
| QuestionMatcher | 0.3 | |
| InterviewEngine | 0.7 | 对话式，需要变化 |
| InsightExtractor | 0.3 | |
| PerspectiveExtractor | 0.1 | 抽取任务，**绝不能润色发挥** |
| ChallengeSelector | 0.2 | |
| InsightRefiner | 0.4 | |
| AnswerComposer | 0.5 | |

---

## 13. 防幻觉设计

这是一等公民级别的关注点，不是事后补丁。

### PerspectiveExtractor 守卫

System prompt 包含：

```
你只能从提供的文本中抽取主张。
若文本不包含连贯、可归属的主张，返回 null。
你不得：
- 超出文本所述范围做泛化
- 推测作者「大概想说什么」
- 把不同来源的主张合并
"reason" 中的每一个字都必须能追溯到 "evidence_text" 中的某个句子。
```

### AnswerComposer 守卫

System prompt 包含：

```
你只能使用以下带标签的证据来撰写回答：
[USER_FACT: ...]、[USER_EVENT: ...]、[USER_QUOTE: ...]、
[USER_INSIGHT: ...]、[USER_RESPONSE: ...]、[COMMUNITY_EVIDENCE: ...]

规则：
1. 回答中的每一个主张都必须映射到上述某个标签。
2. 不得引入标签中不存在的事实、事件或观点。
3. 若某句话无法溯源，直接删掉，而不是换个说法保留。
4. 回答必须读起来像用户本人所写——使用第一人称。
5. 不得提及你是 AI，也不得提及这是生成的内容。
```

### 生成后校验

AnswerComposer 执行后：

```python
def validate_answer_grounding(answer: str, knowledge_state: KnowledgeState) -> bool:
    """
    启发式检查：回答中至少 N% 的句子应包含来自
    USER_QUOTE 或 USER_FACT 条目的片段。
    阈值：60%。低于阈值则标记提示用户复核（不阻塞交付）。
    """
```

---

## 14. 演示兜底系统

每个外部依赖都有兜底。兜底**按调用粒度生效**，不是全局开关——因此允许局部降级（如真实 LLM + Mock 知乎）。

```python
class FallbackConfig(BaseModel):
    use_mock_oauth: bool = False
    use_mock_questions: bool = False
    use_mock_perspectives: bool = False
    use_mock_llm: bool = False
    demo_session_id: str | None = None   # 设置后加载完整演示会话
```

### demo_questions.json

覆盖 5 个领域（AI、前端、职业、教育、金融）共 20 个问题。当 `question recommend` 失败或返回不足 3 条时使用。

### demo_evidence.json

按领域组织的预置 `CommunityPerspective` 对象。每个领域 6–8 条观点，内容真实可信（非虚构杜撰）。Vicky 演示会话使用 `programming_ai` 领域的观点。

### demo_session.json

Vicky 演示叙事的完整冻结会话（见 PRD 第 9 节）。加载该会话将绕过所有真实 API 调用。后端接口：`GET /api/v1/sessions/demo`。

### 兜底触发逻辑

```python
async def get_perspectives_with_fallback(
    question_title: str, question_url: str, insight_v1: Insight,
    config: FallbackConfig
) -> list[CommunityPerspective]:
    if config.use_mock_perspectives:
        return load_demo_evidence(domain=infer_domain(question_title))
    try:
        return await build_perspectives(question_title, question_url, insight_v1)
    except (ZhihuServiceError, asyncio.TimeoutError) as e:
        logger.warning(f"知乎 API 失败（{e}），改用预置证据")
        return load_demo_evidence(domain=infer_domain(question_title))
```

---

## 15. 错误处理

### HTTP 错误响应格式

```json
{
  "ok": false,
  "error": {
    "code": "ZHIHU_RATE_LIMIT",
    "message": "知乎 API 已达今日调用上限",
    "recoverable": true,
    "fallback_available": true
  }
}
```

### 错误码表

| Code | 含义 | 可恢复 | 有兜底 |
|---|---|---|---|
| `ZHIHU_RATE_LIMIT` | CLI 返回 `Code: 30001` | 是（次日） | 是 |
| `ZHIHU_AUTH_INVALID` | Access Secret 无效 | 否 | 否 |
| `ZHIHU_CLI_NOT_FOUND` | 二进制缺失 | 否 | 否 |
| `LLM_TIMEOUT` | LLM 无响应 | 是 | Mock |
| `LLM_INVALID_OUTPUT` | JSON 解析失败 | 是（重试） | Mock |
| `SESSION_NOT_FOUND` | 会话 ID 不存在 | 否 | 否 |
| `SESSION_INVALID_STAGE` | 非法状态流转 | 否 | 否 |
| `OAUTH_STATE_MISMATCH` | CSRF 校验失败 | 否 | 否 |

### 前端错误态

每个页面都有明确的错误态，展示：

- 什么失败了（人话，不是原始错误码）
- 用户能否重试
- 是否已启用演示数据

---

## 16. 日志

日志中不得出现敏感数据，由日志过滤器强制保证。

```python
class SanitizingFilter(logging.Filter):
    PATTERNS = [
        r'[0-9a-f]{32,}',      # Access Secret / token
        r'Bearer\s+\S+',        # OAuth token
    ]
    def filter(self, record):
        for p in self.PATTERNS:
            record.msg = re.sub(p, '[REDACTED]', str(record.msg))
        return True
```

日志级别：

- `DEBUG`：知乎 CLI 调用的完整请求/响应（仅开发环境，绝不上生产）
- `INFO`：会话状态流转、兜底触发
- `WARNING`：API 失败、兜底启用
- `ERROR`：未捕获异常、LLM 解析失败

---

## 17. 环境变量

```bash
# LLM
LLM_BASE_URL=https://...          # OpenAI 兼容接口
LLM_API_KEY=...                   # 机密
LLM_MODEL=claude-opus-5           # 或其他可用模型

# 知乎 CLI
ZHIHU_CLI_PATH=/Applications/看山工作台.app/.../zhihu-cli
# ZHIHU_ACCESS_SECRET 由系统钥匙串管理，不走环境变量
# 但在 headless/CI 环境下，CLI 支持 export ZHIHU_ACCESS_SECRET=...

# 知乎 OAuth（项目创建后从赛事页面获取）
ZHIHU_OAUTH_APP_ID=...
ZHIHU_OAUTH_APP_KEY=...           # 机密
ZHIHU_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/oauth/callback

# 应用
DATABASE_URL=sqlite+aiosqlite:///./sessions.db
CORS_ORIGINS=http://localhost:5173
SECRET_KEY=...                    # 会话签名用，32 字节随机
DEMO_MODE=false                   # 设为 true 启用 /sessions/demo

# 兜底开关（仅演示/测试用）
FALLBACK_MOCK_QUESTIONS=false
FALLBACK_MOCK_PERSPECTIVES=false
FALLBACK_MOCK_LLM=false
```

所有机密必须放在 `.env`（已加入 gitignore）。`.env.example` 提交所有键名但值为空。

---

## 18. 目录结构

```
mindmine/
  README.md
  .env.example
  .gitignore
  backend/
    main.py
    config.py
    database.py
    requirements.txt
    requirements-dev.txt
    routers/           （见第 3 节）
    services/          （见第 3 节）
    ai/                （见第 3 节）
    models/            （见第 3 节）
    fixtures/          （见第 14 节）
    tests/
      test_zhihu_service.py
      test_perspective_pipeline.py
      test_answer_grounding.py
  frontend/
    index.html
    vite.config.ts
    tsconfig.json
    package.json
    tailwind.config.ts
    src/               （见第 2 节）
    public/
  docs/
    PRD.md
    TECH_DESIGN.md
    AGENTS.md
    MINDMINE_ZHIHU_CAPABILITIES.md
```

---

## 19. 真实 / LLM / Mock 一览

这张表是本文档的索引，用于快速确认某个能力的性质。

| 能力 | 性质 | 具体来源 |
|---|---|---|
| 问题推荐 | 🟢 真实 API | `question recommend --query` |
| 回答搜索（带作者） | 🟢 真实 API | `search zhihu` |
| 回答摘要列表 | 🟢 真实 API | `question answers` |
| 用户关注 / 收藏 / 创作 | 🟢 真实 API | `me followees` / `me favorites recent` / `me contents` |
| OAuth 用户数据 | 🟢 真实 API | HTTP + `X-OAuth-Token` |
| 额度查询 | 🟢 真实 API | `quota` |
| 画像提取 | 🤖 LLM | ProfileExtractor |
| query 生成与重排序 | 🤖 LLM | QuestionMatcher |
| 访谈提问 | 🤖 LLM | InterviewEngine |
| 知识状态分类 | 🤖 LLM | KnowledgeExtractor |
| 洞察提炼 | 🤖 LLM | InsightExtractor |
| 观点抽取 | 🤖 LLM | PerspectiveExtractor |
| 挑战选择 | 🤖 LLM | ChallengeSelector |
| 洞察升级 V2 | 🤖 LLM | InsightRefiner |
| 回答成文 | 🤖 LLM | AnswerComposer |
| 问题兜底 | 🟡 Mock | `demo_questions.json` |
| 观点兜底 | 🟡 Mock | `demo_evidence.json` |
| 完整会话兜底 | 🟡 Mock | `demo_session.json` |
| OAuth 兜底 | 🟡 Mock | 手动画像路径 |
| **发布回答** | ❌ **不存在** | **无官方 API，改为打开问题 URL 人工发布** |
