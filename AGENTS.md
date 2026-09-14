# AGENTS.md — MindMine 项目 AI 开发规范

> 本文件具有最高效力。任何 AI 编码 Agent 在写第一行代码前必须先读本文件。当本文件与某个 prompt 或框架默认行为冲突时，**以本文件为准**。

---

## 1. MindMine 是什么

MindMine 是一个**知识发现工具**。它的职责是帮用户找到并说清楚他本来就有的知识——而不是替他生成知识。

整个产品围绕一条**可测试的约束**构建：**最终回答中的每一句话，都必须能追溯到用户说过的某句话。**

这条约束不是 UI 偏好，它就是产品价值本身。违反它的代码不是「变通方案」，是**产品缺陷**。

核心链路：

```
画像 → 问题 → 访谈 → Insight V1 → 社区挑战
→ 用户回应 → Insight V2 → 成文 → 打开知乎 URL
```

**用户是作者。AI 是提问者、镜子和编辑。AI 永远不会变成作者。**

---

## 2. MindMine 不是什么

| 它不是什么 | 这对代码意味着什么 |
|---|---|
| AI 写作助手 | `AnswerComposer` 必须为每句话溯源，不能自由发挥 |
| 聊天机器人 | 访谈是状态机，不是自由对话循环 |
| 知乎自动发布器 | **没有发布 API**。「去知乎发布」= 打开一个 URL。**永远不许叫「一键发布」**。 |
| 推荐引擎 | 问题卡片只展示 3 条，不是信息流 |
| 性格测评工具 | 画像提取只能基于用户明确提供的信息或其知乎数据的直接指向 |

如果某个需求会让 MindMine 更接近上表中的任何一项，**先提出来，再决定要不要做**。

---

## 3. 技术栈

未经明确批准，不得引入本列表之外的依赖。**每一个新依赖都是演示稳定性的风险。**

### 后端

| 层 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.11+ | |
| 框架 | FastAPI | 全异步；所有模型用 Pydantic v2 |
| HTTP 客户端 | httpx | 异步；用于知乎 HTTP API |
| 数据库 | SQLite（aiosqlite） | 会话以 JSON blob 存储；MVP 不需要 ORM |
| LLM | OpenAI 兼容客户端 | base URL 来自 `LLM_BASE_URL`，模型来自 `LLM_MODEL` |
| 配置 | pydantic-settings | 统一在 `config.py`，禁止 `os.environ` 散落各处 |

### 前端

| 层 | 选型 | 说明 |
|---|---|---|
| 框架 | Vue 3 + TypeScript | 只用 Composition API |
| 构建 | Vite | |
| 状态 | Pinia | 按领域分：session、profile、questions |
| 路由 | Vue Router 4 | |
| 样式 | Tailwind CSS | 原子化优先；不用 CSS-in-JS，不用 SCSS |
| HTTP | axios | 统一在 `api/client.ts` 配置单实例 |

### 知乎集成

所有知乎能力通过已安装的 `zhihu-cli` 二进制访问，路径来自 `ZHIHU_CLI_PATH`。**不得逆向知乎内部 API。**

---

## 4. 产品原则（代码评审时强制检查）

### P1 — 所有面向用户的产出必须可溯源

`AnswerComposer` 的 system prompt 明确列出允许的来源标签：`USER_FACT`、`USER_EVENT`、`USER_QUOTE`、`USER_INSIGHT`、`USER_RESPONSE_TO_CHALLENGE`、`COMMUNITY_EVIDENCE`。任何无标签支撑的主张必须删除。回答入库前必须跑溯源校验。

### P2 — 用户确认后才能推进

Insight V1 未经用户点击三个确认按钮之一，不得进入 Stage 5。状态机在**服务端**强制执行（非法流转返回 HTTP 409）。

### P3 — 社区观点必须有原文链接

没有指向真实知乎回答 URL 的 `CommunityPerspective` **不得展示给用户**。演示预置数据的 URL 必须真实可信，**不得使用 `example.com` 或 `localhost`**。

### P4 — 「去知乎发布」只是打开 URL

该按钮打开 `https://www.zhihu.com/question/{question_id}` 新标签页。**不调用任何 API，不宣称任何内容已发布。除此之外没有第二条发布路径。**

### P5 — 不得虚构用户经历

`InterviewEngine` 可以提出假设（「听起来你可能觉得 X——是这样吗？」），但必须以**提问形式**呈现，不能作为断言。`KnowledgeState` 只存 `source` 以 `USER_` 开头的条目。AI 推断的内容可以存进 `candidate_insights`，但**不得写入 `facts` 或 `events`**。

### P6 — 一秒原则（每个核心页面强制检查）

> **每一个 MindMine 核心页面，用户必须在 1 秒内知道：
> 「现在发生了什么，以及为什么轮到我了。」**

如果某个页面必须阅读大量 UI 才能理解自己正在做什么，**继续简化**。做法是删元素，不是加说明文字——用文案解释体验，等于承认体验本身没说清楚。

各页面必须在 1 秒内传达的那句话：

| 页面 | 用户必须立刻知道 |
|---|---|
| Landing | 这是在认识我。 |
| Discovery | 这个问题可能该我回答。 |
| Mining | 我的故事正在被听见。 |
| Insight | 我的经历形成了一个观点。 |
| Challenge | 有人不同意我，现在轮到我回应。 |
| Refinement | 我的观点变得更准确了。 |
| Contribution | 现在轮到别人读我的答案。 |

评审时逐页核对。任一页无法在 1 秒内命中对应那句话，该页不算完成。

推论（可直接作为评审依据）：
- **内部状态不上屏**：`KnowledgeState` 字段名、stage 编号、状态机进度条一律不得渲染给用户。
- **AI 不是主语**：面向用户的文案不得以「我（AI）」开头，例如「我发现了一个洞察」。舞台中央永远是用户。
- **信息并列会稀释焦点**：能一次只给一个的，不要三个平铺。
- **状态变化应表现为形变，不是页面切换**：关键时刻不得用 Modal / Toast / 新 Card 替代原地转变。

### P7 — 不要让用户定义自己

> **MindMine 不要求用户定义自己。
> MindMine 尝试理解用户，然后把解释权交还给用户。**

Onboarding 禁止出现任何形式的「填写我是谁」：Dropdown、Chips、标签多选、职业阶段选择、兴趣领域选择、分享偏好选择，一律不得用于收集画像。

界面上同样禁止出现这些词：**用户画像、Profile、兴趣标签、完善资料、画像完成度、Accuracy XX%、用户属性**。MindMine 不是 LinkedIn，我们不关心把用户分类得多准确。

内部仍可使用 `ContributionProfile` 等工程术语，但它必须只通过 `MindPortrait` 的自然语言与用户见面。

纠正必须是自然语言。用户说「有一点不对」之后，不得重新出现表单或逐字段编辑，只能让他直接说哪里不像。

### P8 — Profile 的目的不是描述，而是发现

> **Profile 的目的不是描述「这个人是谁」，
> 而是发现「这个人有什么值得知乎听」。**

因此 `ContributionProfile` 中 `possible_knowledge` 与 `contribution_angles` 权重最高，它们直接决定去帮用户找什么问题。`journey` / `lived_experiences` 只是支撑它们的依据。

`ProfileExtractor` 不得做成人口统计分类器。它的任务是：**寻找用户可能拥有、但还没有写出来的知识。**

推论：
- Onboarding 的产品语言是 **Know → See → Find → Claim**，不是 Collect → Analyze → Recommend。
- 「认识用户」的过程不得表现为工程 Loading（`Analyzing...` / `Processing 4/7`），应表现为痕迹逐步浮现。
- Question 推荐理由只回答一个问题：**为什么是你？** 不得展示 Match Score、百分比、多个 Badge 或算法解释。
- 画像语气必须保持不确定：我好像看到 / 你似乎 / 可能 / 也许。这是 AI 的理解，不是事实裁决。

### P9 — AI 越聪明，表单越少

> **AI 越聪明，用户需要填写的表单应该越少。**

新增任何输入控件前先问：这件事能不能由 MindMine 自己看出来、或者用一句自然语言问出来？能，就不要加控件。

---

## 5. 禁止事项

以下是硬性红线。不要做，不要绕，不要问有没有例外。

```
❌ 直接调用知乎 API（逆向的或未公开的）
❌ 在 ZhihuService 之外的任何地方执行 CLI 命令
❌ 明文存储或记录 Access Secret、OAuth token、LLM API Key
❌ 生成没有真实 ContentText 支撑的社区观点
❌ 把发布动作标为「一键发布」或暗示已自动发帖
❌ 未经批准引入技术栈之外的库
❌ 虚构用户事实——KnowledgeState.facts 中的一切必须来自用户
❌ 对知乎限流（Code: 30001）发起重试——立即停止并走兜底
❌ 为了「先跑通」跳过会话状态机校验
❌ 未经说明就扩大任务范围
❌ 猜测某个 API 的行为——必须先用 --help 或能力清单验证
```

---

## 6. 文件结构

Agent 必须按 TECH_DESIGN.md 第 18 节定义的位置放置文件。**不要新建顶层目录。不要重组已有目录**，除非任务明确要求。

```
mindmine/
  README.md
  .env.example          ← 所有密钥键名列在此，值为空
  .gitignore            ← .env 必须在其中
  backend/
    main.py             ← 只放 FastAPI 应用、lifespan、CORS
    config.py           ← 所有环境变量在此通过 pydantic-settings 读取
    database.py         ← SQLite 初始化与建表
    routers/            ← 每个 Stage 一个文件（auth、sessions、profile、
    │                      questions、interview、insight、challenge、compose）
    services/
    │   zhihu_service.py   ← 唯一执行 CLI 命令的地方
    │   llm_service.py     ← 唯一调用 LLM 的地方
    │   session_service.py
    ai/                 ← 每个 AI 模块一个文件
    models/             ← 只放 Pydantic 模型（不含业务逻辑）
    fixtures/
        demo_questions.json
        demo_evidence.json
        demo_session.json
    tests/
  frontend/
    src/
      api/client.ts     ← 唯一的 axios 实例；所有调用在此类型化
      stores/           ← 每个领域一个文件
      pages/            ← 每个路由一个文件
      components/       ← 小而单一职责
      types/index.ts    ← 与后端 Pydantic 模型保持镜像
```

---

## 7. 编码风格

### Python

- 所有函数签名必须有类型注解。
- 跨模块边界的数据传输一律用 Pydantic v2 模型，**不用裸 dict**。
- 全程 `async`/`await`；路由处理器中不得有同步阻塞调用。
- 错误处理：捕获具体异常；不允许没有日志和重抛的 `except Exception`。
- 生产代码中不得有 `print()`——使用 `main.py` 中配置的 `logging`。
- 环境变量：只能通过 `config.py` 的 `Settings` 对象读取。**不得在路由或服务中直接调用 `os.environ.get`**。

```python
# 正确
async def get_perspectives(question_url: str) -> list[CommunityPerspective]:
    ...

# 错误
async def get_perspectives(question_url):
    ...
```

### TypeScript / Vue

- 每个组件用 `<script setup lang="ts">`，**不用 Options API**。
- Props 用 `defineProps<{...}>()` 定义类型。
- API 调用只能通过 `api/client.ts` 的类型化封装，**组件中不得内联 `axios.get`**。
- Pinia store：用 `defineStore` 的 `setup()` 写法；只暴露组件需要的部分。
- **禁止 `any`**。类型未知时用 `unknown` 并收窄。
- 组件文件名用 PascalCase，与组件名一致。

### 命名约定

| 场景 | 约定 |
|---|---|
| Python 文件 | `snake_case.py` |
| Python 类 | `PascalCase` |
| Python 函数/变量 | `snake_case` |
| Vue 组件文件 | `PascalCase.vue` |
| TypeScript 接口 | `PascalCase` |
| TypeScript 变量/函数 | `camelCase` |
| Pinia store ID | `kebab-case` |
| API 路由 | `kebab-case`（如 `/insight/confirm`） |
| 环境变量 | `SCREAMING_SNAKE_CASE` |

---

## 8. AI 模块设计原则

`backend/ai/` 下每个模块遵循同一契约：

```python
class [模块名]:
    def __init__(self, llm_service: LLMService):
        self.llm = llm_service

    async def [主方法](self, input: InputModel) -> OutputModel:
        messages = self._build_messages(input)
        raw = await self.llm.complete(
            messages=messages,
            response_format=OutputModel,
            temperature=本模块的温度常量
        )
        result = OutputModel.model_validate(raw)
        self._validate_grounding(result, input)   # 检测到幻觉则抛异常
        return result

    def _build_messages(self, input: InputModel) -> list[dict]:
        # System prompt 是模块级常量，绝不在运行时拼装
        ...

    def _validate_grounding(self, output: OutputModel, input: InputModel) -> None:
        # 各模块各自实现，见 TECH_DESIGN 第 13 节
        ...
```

规则：

- System prompt 是模块级字符串常量，**不动态拼装**。
- **绝不把用户输入的原始文本当作 system prompt** 传给 LLM。
- 每个模块声明自己的 temperature 常量，**不用全局默认值**。
- 模块返回类型化的 Pydantic 对象，**不返回裸字符串或 dict**。
- `model_validate` 失败（LLM 返回了畸形 JSON）时抛 `LLMInvalidOutputError`——路由捕获后返回 HTTP 503 并带 `fallback_available: true`。

### 各模块的允许与禁止

| 模块 | 允许生成 | 禁止生成 |
|---|---|---|
| ProfileExtractor | 来自用户数据的领域标签 | 数据中无证据的领域 |
| QuestionMatcher | query 词、基于画像的 `why_fits` | 用户没提过的领域的问题 |
| InterviewEngine | 问题、以提问形式表达的假设 | 关于用户事实的断言 |
| InsightExtractor | 基于 KnowledgeState 的洞察 | 没有 `evidence_key` 引用的主张 |
| PerspectiveExtractor | 可追溯到 `evidence_text` 的主张 | 超出文本所述的内容 |
| ChallengeSelector | 带理由的排序选择 | 输入列表之外的新观点 |
| InsightRefiner | 整合 V1 + 用户回应的 V2 | 两者都不存在的新事实 |
| AnswerComposer | 基于标签证据的行文 | 任何无来源标签的句子 |

---

## 9. API 封装原则

### ZhihuService

**`backend/services/zhihu_service.py` 之外的任何代码，不得执行 CLI 命令或调用 `subprocess`。没有例外。**

新增知乎能力时：

1. 先确认它在已验证能力清单中（见 `MINDMINE_ZHIHU_CAPABILITIES.md`）。
2. 运行 `zhihu-cli <命令> --help` 确认精确参数。
3. 在 `ZhihuService` 中添加带类型注解的方法。
4. 添加单元测试，mock subprocess 调用并验证解析逻辑。
5. 若该能力此前未验证，更新 `MINDMINE_ZHIHU_CAPABILITIES.md`。

**当某能力不在已验证清单中**：不要猜、不要包装未测试过的 CLI 命令、不要调用未公开的 HTTP 接口。在任务产出中写明「需要什么」和「实际发现了什么」，并实现兜底路径。

### HTTP API 调用（OAuth 用户数据）

直接调用知乎 HTTP API（如带 `X-OAuth-Token` 取用户数据）时，一律走 `ZhihuService.get_oauth_user_data()`。该方法负责设置正确的请求头、处理鉴权错误、并强制执行「token 不入日志」规则。

---

## 10. 密钥管理

### 以下内容绝不能出现在代码、日志或 API 响应中

- `ZHIHU_ACCESS_SECRET`（由系统钥匙串管理；仅 headless/CI 场景走环境变量）
- `ZHIHU_OAUTH_APP_KEY`
- `LLM_API_KEY`
- `SECRET_KEY`（会话签名）
- 从用户处获得的 OAuth access token

### 规则

- 密钥来自环境变量，通过 `config.py` 读取。**绝不硬编码。**
- `.env` 必须在 `.gitignore` 中。每次新建仓库都要确认这一点。
- `.env.example` 列出每个键名，值为空，并加注释说明用途。
- 日志脱敏器（`SanitizingFilter`）必须在 `main.py` 的 lifespan 中注册到 root logger。
- 数据库中的 OAuth token，时间允许时应加密存储；MVP 阶段字段存在但明文，**必须在 README 的「已知限制」中标注**。
- 需要把密钥传给知乎 CLI 时，使用 `--secret-stdin` 通过标准输入管道传入——**绝不作为命令行参数**（会进入进程列表和 shell 历史）。

---

## 11. 测试要求

### 每个 Phase 完成前必须有测试的部分

| 组件 | 测试类型 | 测什么 |
|---|---|---|
| `ZhihuService` | 单元（mock subprocess） | JSON 解析、错误码映射、限流处理 |
| 观点管线 | 单元（mock ZhihuService） | 作者去重规则、问题 ID 过滤、多样性 |
| 回答溯源 | 单元 | 溯源校验器能否抓出无来源句子 |
| 会话状态机 | 集成 | 非法流转返回 409；合法流转推进 stage |
| `/oauth/callback` | 集成 | state 不匹配返回 400；合法 state 能换 token |
| `AnswerComposer` | 单元（mock LLM） | 含无来源句子的输出应被溯源检查拦下 |

### 48h MVP 不需要测试的部分

- 视觉样式
- 前端组件渲染（黑客松阶段人工 QA 即可）
- LLM prompt 质量（人工评估）

### 测试框架

Python：`pytest` + `pytest-asyncio` + `httpx.AsyncClient`（FastAPI 集成测试）。Fixture 放 `tests/conftest.py`。

---

## 12. 任务验收标准

标记任务完成前，逐条核对：

- [ ] 代码实现了任务描述的内容，**不多也不少**
- [ ] 没有未经说明就新增依赖
- [ ] 任何可能被提交的文件中都没有密钥
- [ ] 相关单元测试通过
- [ ] 真实服务不可用时，兜底路径可用
- [ ] API 返回标准 `{"ok": true/false, "data"/"error": {...}}` 信封
- [ ] 会话状态流转在服务端有校验
- [ ] 生产代码路径中没有遗留 `console.log` 或 `print()`
- [ ] 若用到了知乎 API，它在已验证能力清单中
- [ ] 若发现了新的限制，已写入任务产出

---

## 13. 禁止自行扩大需求

若完成指定任务需要实现某个**未被指定**的东西：

1. 用桩（stub）或明确标注的 TODO 完成指定任务，把未指定部分留空。
2. 在任务产出中说明：缺了什么、用了什么桩、还需要明确什么。
3. **不要默默实现未指定的部分**——即使你觉得你知道它应该是什么样。

反面例子：

> 任务：「添加 `/questions` 接口」
> Agent 做了：添加接口 **并且** 重构了会话模型 **并且** 更新了前端 store

正面例子：

> 任务：「添加 `/questions` 接口」
> Agent 做了：添加接口，用 TODO 标记 `QuestionMatcher` 调用处，
> 并说明 `QuestionMatcher.rerank()` 需要在独立任务中实现

---

## 14. 未验证 API 政策

> **如果你不确定某个知乎能力是否存在，必须先验证再使用。**

验证步骤：

1. 查 `MINDMINE_ZHIHU_CAPABILITIES.md`——若已标注为真实且已测试，可直接用。
2. 未列出：运行 `zhihu-cli capabilities` 查看输出。
3. 仍未出现：若有具体命令猜想，运行 `zhihu-cli <命令> --help`。
4. 还是没有：**该能力不存在**。实现兜底路径，并记录这个能力缺口。

这条政策的由来——初次审计实际发现了这些「反直觉」的事实：

- `question answers` **不返回作者信息**（尽管名字听起来应该有）
- `question recommend` **未验证**支持 OAuth 用户身份切换
- `VoteUpCount` 字段存在于 schema 中，但**实测返回为空**

这类意外是常态。这条政策的作用就是防止在错误假设上构建系统。

---

## 15. 演示稳定性原则

> # **Demo stability > architecture purity.**
> **演示稳定性优先于架构纯洁性。**

这不是写烂代码的许可证，而是**做取舍时的优先级排序**。

当你必须在以下选项中二选一时：

- 更干净的抽象但要加新依赖 **vs** 稍微糙一点但不加依赖
- 更正确的异步模式但需要重构 **vs** 能跑的同步调用且今天就能上
- 完美范式化的数据模型 **vs** 48 小时内能work的 JSON blob

**选那个能让演示跑起来的。**

具体含义：

- 如果某次重构会破坏已经跑通的演示路径，**推迟重构**。
- 兜底数据（`demo_questions.json`、`demo_evidence.json`、`demo_session.json`）是**一等公民，不是测试辅助**。它们必须准确、持续维护、随时可加载。
- `GET /api/v1/sessions/demo` 必须在任何时候都能返回一个合法完整的会话。**这是演示日所有真实 API 全挂时的最后一道防线。**
- 时间压力下做取舍时，优先保证 happy path 完美，而不是让错误路径优雅。
- **已知限制可以接受，未记录的意外不可接受。** 每个已知限制都要写进任务产出和 README 的「已知限制」章节。

---

## 附录：速查

### 已验证可直接使用的知乎 CLI 命令

```bash
zhihu-cli question recommend --query "<主题>" --count <n>     # 问题发现
zhihu-cli search zhihu --query "<查询>" --count <n>            # 带作者+正文的回答
zhihu-cli question answers --question-url "<url>" --limit <n>  # 回答摘要
zhihu-cli me followees --limit <n>                             # 画像构建
zhihu-cli me favorites recent --limit <n>                      # 画像构建
zhihu-cli me contents --type all --limit <n>                   # 画像构建
zhihu-cli quota                                                # 查询剩余额度
```

### 不存在的命令

```
zhihu-cli answer create ...         # ❌ 无发布 API
zhihu-cli answer publish ...        # ❌ 无发布 API
zhihu-cli question detail ...       # ❌ 无问题详情 API
```

### 关键额度限制（2026-09-13 审计数据）

| 能力 | 每日上限 | 与谁共用 |
|---|---|---|
| `zhihu_search` | 10 | — |
| `question_answers` | 10 | — |
| `creator`（问题推荐） | 10 | me content、comments、stats |
| `user_data` | 1000 | — |
| `hot_list` | 2 | —（P2：不使用） |
| `zhida_openai` | 2 | —（P2：不使用） |
| `knowledge` | 500 | — |

**演示前必须先跑 `quota`。** 若 `creator` 接近 0，切换到 `--query` 模式并启用 Mock 问题。
