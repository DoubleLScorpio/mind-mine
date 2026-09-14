"""Phase 1 演示数据与 Mock 推进逻辑。

设计要点：
1. 所有 Mock 内容集中于此，业务层不散落硬编码，
   后续接入 LLM 时只需替换 MockInterviewEngine 的实现。
2. 社区观点必须标记 is_mock=True，前端显式标注「演示数据」。
3. 成文回答只能使用 Demo 故事中用户实际说过的内容，
   不得额外虚构用户经历（AGENTS.md P5 / P1）。
"""

from __future__ import annotations

from models.session import (
    ChatMessage,
    CommunityPerspective,
    FragmentLink,
    Insight,
    KnowledgeEvent,
    KnowledgeState,
    QuestionCard,
    Session,
    SessionState,
    ThoughtFragment,
    UserProfile,
)

# --------------------------------------------------------------------------
# Stage 2 — Mock 问题列表
# --------------------------------------------------------------------------

DEMO_QUESTIONS: list[QuestionCard] = [
    QuestionCard(
        question_id="q_career_lessons",
        title="工作两三年后，你悟出了哪些职场道理？",
        why_fits="这个问题最好的答案，往往来自真实的代价。",
        tag="职场 / 成长",
        source="mock",
    ),
    QuestionCard(
        question_id="q_ai_jobs",
        title="AI 会让程序员失业吗？",
        why_fits="这个问题缺的不是预测，而是一线实践者的判断。",
        tag="AI / 职业",
        source="mock",
    ),
    QuestionCard(
        question_id="q_job_switch",
        title="程序员在哪个瞬间意识到自己应该跳槽？",
        why_fits="这个问题只有具体的场景才答得好，泛泛而谈没有说服力。",
        tag="职场 / 决策",
        source="mock",
    ),
]

# 主 Demo 故事绑定的问题
DEMO_QUESTION_ID = "q_career_lessons"


# --------------------------------------------------------------------------
# Why you? —— 认领理由
#
# 让用户觉得「该我回答」的唯一手段不是夸问题，而是引用用户自己。
# 所以这里必须回指用户刚才填的自我介绍，而不是描述问题有多好。
# --------------------------------------------------------------------------

_SHARE_PHRASE: dict[str, str] = {
    "experience": "你说过你更愿意讲亲身经历 —— 那种答案，很少。",
    "opinion": "你说过你更愿意讲自己的判断 —— 那种答案，很少。",
    "expertise": "你说过你更愿意讲专业上的门道 —— 那种答案，很少。",
    "mistakes": "你说过你更愿意讲踩过的坑 —— 那种答案，很少。",
}

_STATUS_PHRASE: dict[str, str] = {
    "student": "你还在学校，但旁观者视角本身就稀缺。",
    "early_career": "你正在经历它，而不是回忆它。",
    "mid_career": "你已经走过这一段，知道代价长什么样。",
    "senior": "你见过足够多的样本，能分辨什么是特例。",
    "freelance": "你自己承担后果，判断会更诚实。",
}


def render_why_fits(question: QuestionCard, profile: UserProfile | None) -> str:
    """把问题的固定理由 + 用户自我介绍拼成一句「该你回答」的话。

    Phase 1 用模板实现，不需要 LLM。接入 LLM 后替换本函数即可。
    """
    base = question.why_fits
    if profile is None:
        return base

    tail = ""
    for pref in profile.share_preferences:
        if pref in _SHARE_PHRASE:
            tail = _SHARE_PHRASE[pref]
            break
    if not tail:
        tail = _STATUS_PHRASE.get(profile.current_status, "")

    return f"{base}\n{tail}" if tail else base


# --------------------------------------------------------------------------
# Stage 3 — 固定四轮访谈脚本
# --------------------------------------------------------------------------

OPENING_QUESTION = "关于这个问题，你现在最想说的一句话是什么？"

# 每轮：AI 的下一个提问 + 本轮从用户发言中提取的知识增量
#
# fragments 是本轮新增的展示碎片。约束：
# 1. text 必须是用户原话的压缩，不超过 10 字，不得是 AI 的重新表述。
# 2. label 是开放字符串，前端不得据此做分类逻辑。
# 3. 第 1 轮故意不产出碎片 —— 第一句是态度不是素材，
#    让空白留在那里，用户后面才会感到「是我讲出来之后才有的」。
INTERVIEW_SCRIPT: list[dict] = [
    {
        # 用户发言 1（Demo 推荐：别太相信领导画饼。）
        "next_question": "发生过什么事，让你开始有这种感觉？",
        "state": SessionState.EXPERIENCE,
        "beliefs": ["不应该轻易相信领导的口头承诺"],
        "fragments": [],
    },
    {
        # 用户发言 2（Demo 推荐：领导承诺年底升职，因此拒绝了涨薪 30% 的 Offer）
        "next_question": "当时你为什么愿意相信这个承诺？",
        "state": SessionState.EXPERIENCE,
        "facts": [
            "用户曾获得一个涨薪30%的Offer",
            "用户因为内部晋升承诺拒绝了Offer",
        ],
        "events": [
            KnowledgeEvent(event="领导承诺年底晋升", result="用户据此拒绝了外部 Offer"),
        ],
        "fragments": [
            {"id": "f_promise", "label": "期待", "text": "年底晋升"},
            {"id": "f_choice", "label": "选择", "text": "拒绝 +30% Offer"},
        ],
    },
    {
        # 用户发言 3（Demo 推荐：领导之前不错、说得具体，觉得长期发展更好）
        "next_question": "后来发生了什么？",
        "state": SessionState.REFLECTION,
        "beliefs": ["当时认为留下长期发展收益更高"],
        "conflicts": ["外部确定Offer vs 内部不确定晋升承诺"],
        "fragments": [
            {"id": "f_cost", "label": "代价", "text": "错过确定机会"},
        ],
    },
    {
        # 用户发言 4（Demo 推荐：年底没升职，Offer 也没了）
        "next_question": "现在回头看，你觉得自己真正判断错的是什么？",
        "state": SessionState.REFLECTION,
        "events": [
            KnowledgeEvent(event="领导承诺年底晋升", result="年底未兑现"),
        ],
        "facts": ["那个外部 Offer 已经失效"],
        "fragments": [
            {"id": "f_outcome", "label": "结果", "text": "承诺没有兑现"},
        ],
    },
    {
        # 用户发言 5（Demo 推荐：错在把没保证的未来当成确定的东西）
        # 第 5 次发言后触发 Insight Moment
        "next_question": None,
        "state": SessionState.INSIGHT,
        "reflections": ["把未经确认的未来机会当成确定收益"],
        "candidate_insights": ["未来承诺应该按照不确定性进行风险定价"],
        "fragments": [
            {"id": "f_reflect", "label": "回头看", "text": "把可能当成了确定"},
        ],
    },
]

# 触发 Insight Moment 所需的用户发言轮次
INSIGHT_TRIGGER_TURN = len(INTERVIEW_SCRIPT)


# --------------------------------------------------------------------------
# 碎片之间的因果关系
#
# Insight Reveal 时据此把散落的碎片连成一条经历链。
# 关系本身也来自用户讲述的顺序，不是 AI 额外推断出来的东西。
# --------------------------------------------------------------------------

DEMO_FRAGMENT_LINKS: list[FragmentLink] = [
    FragmentLink(from_id="f_promise", to_id="f_choice"),
    FragmentLink(from_id="f_choice", to_id="f_outcome"),
    FragmentLink(from_id="f_choice", to_id="f_cost"),
]


# --------------------------------------------------------------------------
# Stage 4 — Insight V1
# --------------------------------------------------------------------------

DEMO_INSIGHT_V1 = Insight(
    version="V1",
    surface_claim="别太相信领导画饼。",
    # naming 先出现：它只是把用户的经历重新讲了一遍，没有加任何判断。
    # 用户先认下这句「我确实这么干了」，后面的观点才站得住。
    naming="你用一次确定的机会，换了一个还没发生的承诺。",
    deep_insight=(
        "不要让未经验证的未来承诺，"
        "拥有和当前确定机会相同的决策权重。"
    ),
)


# --------------------------------------------------------------------------
# Stage 5 — 社区挑战（Mock）
# --------------------------------------------------------------------------

DEMO_CHALLENGE = CommunityPerspective(
    id="mock_perspective_001",
    claim=(
        "职业早期最重要的并不是短期薪资，"
        "而是成长空间、关键项目和好的管理者。"
    ),
    reason="有些值得押注的机会，本身就不可能完全确定。",
    author="Mock Author",
    badge="演示数据",
    source_label="来自知乎社区的一种观点 · 演示数据",
    source_url=None,
    # 这不是「另一个观点」，而是「别人站在你的观点面前，会问你的一句话」。
    # 用户要立刻明白：这和我刚才形成的观点有关。
    challenge_question=(
        "可是，真正值得押注的长期机会，本来就很少是完全确定的。\n"
        "如果什么都等确定了再选择，会不会也错过成长？"
    ),
    is_mock=True,
)


# --------------------------------------------------------------------------
# Stage 6 — Insight V2
# --------------------------------------------------------------------------

DEMO_INSIGHT_V2 = Insight(
    version="V2",
    surface_claim="别太相信领导画饼。",
    naming="你用一次确定的机会，换了一个还没发生的承诺。",
    deep_insight=(
        "长期机会可以值得冒险，"
        "但应该根据兑现条件、概率和机会成本，"
        "对未来承诺进行风险定价。"
    ),
    # 界面上要演示「同一个观点被修正」，而不是替换成新版本：
    # softened_span 是 V1 里被弱化掉的绝对化表达，
    # added_qualifiers 是用户经过 Challenge 之后自己加上的限定条件。
    softened_span="不要让",
    added_qualifiers=["兑现条件", "概率", "机会成本"],
)

CHALLENGE_SUMMARY = "长期收益本身就存在不确定性。"
# TODO: optional LLM-generated summary; not required for hackathon core flow
# 当前为固定文本，不代表真实知乎原文，仅用于界面展示


def compose_answer(session: Session) -> str:
    """基于 Demo 故事生成知乎回答。

    约束（AGENTS.md P1 / P5）：只能使用用户在本次会话中实际说过的内容、
    已确认的 Insight，以及被标记为演示数据的社区观点。
    不得虚构任何额外的用户经历。
    """
    user_messages = [m.content for m in session.messages if m.role == "user"]

    # 用户原话（若用户偏离了 Demo 推荐输入，这里仍取其真实发言）
    quote_first = user_messages[0] if user_messages else ""
    response = session.challenge_response or ""

    insight_v2 = session.insight_v2.deep_insight if session.insight_v2 else ""

    parts: list[str] = []

    parts.append("工作两三年，我用一次真实的代价换来了一个判断。")
    parts.append("")

    if quote_first:
        parts.append(f"最开始我会说：「{quote_first}」")
        parts.append("")

    parts.append("**先说发生了什么**")
    parts.append("")
    parts.append(
        "那年我手上有一个外部 Offer，涨薪 30%。同时我的领导告诉我，"
        "年底会给我升职。他之前对我一直不错，话也说得很具体，"
        "我判断留下来长期发展更划算，于是拒绝了那个 Offer。"
    )
    parts.append("")
    parts.append("结果是：年底没有升职，领导只说再等等。而那个 Offer 早就没了。")
    parts.append("")

    parts.append("**我一开始归因错了**")
    parts.append("")
    parts.append(
        "很长一段时间里，我把这件事总结成「别太相信领导画饼」。"
        "但这个结论其实没什么用——它只是情绪，不是方法。"
    )
    parts.append("")
    parts.append(
        "后来我想清楚了：我不是错在相信领导，"
        "而是把一个没有保证的未来机会，当成了已经确定的东西。"
        "一个确定的 30% 涨薪，和一个没有书面条件、没有时间表的晋升口头承诺，"
        "在我当时的决策里被赋予了同样的权重。这才是真正的错误。"
    )
    parts.append("")

    parts.append("**有人提出了不同看法**")
    parts.append("")
    parts.append(
        f"也有观点认为：{DEMO_CHALLENGE.claim}"
        f"{DEMO_CHALLENGE.reason}"
    )
    parts.append("")

    if response:
        parts.append(f"我的回应是：{response}")
        parts.append("")

    parts.append("**所以我现在的判断是**")
    parts.append("")
    parts.append(insight_v2)
    parts.append("")
    parts.append(
        "具体到做法上：当有人给你一个未来的承诺时，"
        "问三件事——什么时间兑现、兑现的条件是什么、如果没兑现会怎样。"
        "三个问题都答不上来的承诺，不该参与你的重大决策。"
    )

    return "\n".join(parts)


# --------------------------------------------------------------------------
# Mock 访谈引擎
# --------------------------------------------------------------------------


class MockInterviewEngine:
    """固定脚本驱动的访谈引擎。

    Phase 1 按用户发言次数推进，不使用 LLM 判断状态。
    接入真实 LLM 时，替换本类即可，路由与数据契约保持不变。
    """

    @staticmethod
    def opening_question() -> str:
        return OPENING_QUESTION

    @staticmethod
    def advance(session: Session, user_content: str) -> tuple[str | None, bool]:
        """处理一次用户发言。

        返回 (ai_reply, insight_ready)。
        insight_ready 为 True 时，前端切换到 Insight Card。
        """
        session.user_turn_count += 1
        turn_index = session.user_turn_count - 1

        if turn_index >= len(INTERVIEW_SCRIPT):
            # 已走完脚本，保持在 INSIGHT 状态
            return None, True

        step = INTERVIEW_SCRIPT[turn_index]
        ks: KnowledgeState = session.knowledge_state

        # 本轮用户发言的 message id，供碎片溯源「这是我说的哪一句」
        source_message_id = f"m_{session.user_turn_count}"

        # 累积展示碎片（用户唯一看得见的那一层）
        for spec in step.get("fragments", []):
            session.fragments.append(
                ThoughtFragment(
                    id=spec["id"],
                    label=spec.get("label"),
                    text=spec["text"],
                    source_message_id=source_message_id,
                )
            )

        # 只保留两端都已出现的连接，避免指向尚未产生的碎片
        present = {f.id for f in session.fragments}
        session.fragment_links = [
            link
            for link in DEMO_FRAGMENT_LINKS
            if link.from_id in present and link.to_id in present
        ]

        # 累积知识状态（只追加脚本中定义的、来自用户发言的内容）
        ks.facts.extend(step.get("facts", []))
        ks.events.extend(step.get("events", []))
        ks.beliefs.extend(step.get("beliefs", []))
        ks.conflicts.extend(step.get("conflicts", []))
        ks.reflections.extend(step.get("reflections", []))
        ks.candidate_insights.extend(step.get("candidate_insights", []))

        session.state = step["state"]

        next_question = step.get("next_question")
        if next_question is None:
            # 触发 Insight Moment
            session.insight_v1 = DEMO_INSIGHT_V1.model_copy(deep=True)
            return None, True

        session.messages.append(
            ChatMessage(
                role="ai",
                content=next_question,
                turn=session.user_turn_count,
            )
        )
        return next_question, False
