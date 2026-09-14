"""Onboarding 服务。

Phase 1 使用 MockProfileService 作为进程内存储。

真实 LLM 路径：
    from_chat()  → ChatPortraitExtractor（LLM）→ 失败退回关键词拼接
    correct()    → CorrectionExtractor（LLM）→ 失败退回关键词匹配

路由与前端契约保持不变。
"""

from __future__ import annotations

import logging
import uuid

from pydantic import BaseModel, Field

from ai import prompts
from models.profile import (
    ChatAnswerRequest,
    ContributionProfile,
    MatchedQuestion,
    MindPortrait,
    OnboardingState,
    ProfileEvidence,
    QuestionMatchReason,
)
from services.llm_service import LLMUnavailable, llm

logger = logging.getLogger("mindmine.profile_svc")


# --------------------------------------------------------------------------
# 「用知乎认识我」——逐步浮现的痕迹（Mock，路径 A 的演示数据）
# --------------------------------------------------------------------------

MOCK_TRACES: list[ProfileEvidence] = [
    ProfileEvidence(
        kind="follow",
        label="你经常停留在……",
        items=["AI", "前端开发", "职业成长"],
    ),
    ProfileEvidence(
        kind="favorite",
        label="你收藏过不少关于……",
        items=["技术转型", "学习方法", "工作选择"],
    ),
    ProfileEvidence(
        kind="creation",
        label="还有一些内容似乎反复出现……",
        items=["「怎么学」", "「要不要转」", "「真正做过以后才知道什么」"],
    ),
]


# --------------------------------------------------------------------------
# 「先聊两句」——最多三问
# --------------------------------------------------------------------------

CHAT_QUESTIONS: list[str] = [
    "最近几年，你把最多时间花在什么事情上？",
    "这里面有没有什么，是你踩过坑以后才真正懂的？",
    "有没有哪件事，现在的你会很想提醒当时的自己？",
]


# --------------------------------------------------------------------------
# LLM Schema：from_chat 的结构化输出
# --------------------------------------------------------------------------

class ChatPortraitOut(BaseModel):
    journey: str
    lived_experiences: list[str] = Field(default_factory=list)
    recurring_interests: list[str] = Field(default_factory=list)
    possible_knowledge: list[str] = Field(default_factory=list)
    contribution_angles: list[str] = Field(default_factory=list)
    paragraphs: list[str] = Field(default_factory=list)


_CHAT_PORTRAIT_SYSTEM = f"""{prompts.PHILOSOPHY}

你现在的角色：从一个人自己说的话里，看出他可能有什么值得知乎听的东西。

重要：你的任务不是给他贴标签，而是回答一个问题——
这个人经历过什么，别人替代不了？

硬性约束：
- 只能基于用户说过的话推断，不虚构职业、年限、身份、工作单位。
- 看不出来的字段留空列表，不要编造。

输出字段（权重从低到高）：
- journey：他正在走的路。一句话，第三人称描述，不超过 25 字。
- lived_experiences：他真正待过的领域，3-5 个短词。
- recurring_interests：反复出现的关注，3-5 个短词。
- possible_knowledge：**最重要**。他可能有、但还没写出来的知识。
  必须是「只有经历过才知道」那一类。2-4 条。
- contribution_angles：**最重要**。他可以从哪些角度贡献。3-4 个短词。
- paragraphs：面向他本人的自然语言描述，恰好 2 段。
  第二人称「你」。语气必须不确定：好像 / 似乎 / 可能。
  不要下定义、不要评价、不要表扬。每段不超过 50 字。"""


# --------------------------------------------------------------------------
# LLM Schema：correct 的结构化输出
# --------------------------------------------------------------------------

class CorrectionOut(BaseModel):
    journey: str
    possible_knowledge: list[str] = Field(default_factory=list)
    contribution_angles: list[str] = Field(default_factory=list)
    ack: str
    paragraphs: list[str] = Field(default_factory=list)


_CORRECTION_SYSTEM = f"""{prompts.PHILOSOPHY}

你现在的角色：用户说「我刚才的描述有一点不对」，
你要理解他的意思，更新对他的认识。

硬性约束：
- 只能基于用户说过的话（原始对话 + 本次纠正）重新推断，不虚构。
- ack 必须先认可用户的纠正，一句话，不超过 15 字。
- paragraphs：重新描述他，恰好 2 段，第二人称「你」，不确定语气。每段不超过 50 字。
- possible_knowledge 和 contribution_angles 比之前的描述更准确。"""


# --------------------------------------------------------------------------
# MockProfileService
# --------------------------------------------------------------------------

class MockProfileService:
    """进程内 Onboarding 存储。

    LLM 可用时 from_chat / correct 走真实路径；
    失败则退回 Phase 1 的关键词拼接，保证 Demo 不卡死。
    """

    def __init__(self) -> None:
        self._states: dict[str, OnboardingState] = {}

    # ------------------------------------------------------------------
    # 存储基础
    # ------------------------------------------------------------------

    def get(self, onboarding_id: str) -> OnboardingState | None:
        return self._states.get(onboarding_id)

    def _save(self, state: OnboardingState) -> OnboardingState:
        self._states[state.onboarding_id] = state
        return state

    def adopt(
        self, profile: ContributionProfile, portrait: MindPortrait
    ) -> OnboardingState:
        """接纳外部（真实 OAuth + LLM）生成的画像。"""
        return self._save(
            OnboardingState(
                onboarding_id=self._new_id(),
                profile=profile,
                portrait=portrait,
            )
        )

    @staticmethod
    def _new_id() -> str:
        return f"ob_{uuid.uuid4().hex[:12]}"

    # ------------------------------------------------------------------
    # 路径 A —— 用知乎认识我（Mock traces，由 profile_extractor 升级为真实）
    # ------------------------------------------------------------------

    def traces(self) -> list[ProfileEvidence]:
        return [t.model_copy(deep=True) for t in MOCK_TRACES]

    def from_zhihu(self) -> OnboardingState:
        profile = ContributionProfile(
            source="mock_zhihu",
            journey="正在从传统开发向 AI 能力扩展",
            lived_experiences=["前端开发", "项目实践", "技术学习", "职业选择"],
            recurring_interests=["AI", "前端开发", "职业成长", "学习方法"],
            possible_knowledge=[
                "技术转型踩过的坑",
                "工程实践中的判断",
                "职业选择中的取舍",
            ],
            contribution_angles=[
                "技术转型",
                "程序员成长",
                "AI 与职业",
                "学习新技术踩过的坑",
            ],
            evidence=self.traces(),
        )

        portrait = MindPortrait(
            lead="从你留下的这些痕迹里，我好像看到这样一个你。",
            paragraphs=[
                "你是一个正在从「写代码」走向「理解 AI」的人。",
                "你关注的不只是怎么把东西做出来，"
                "也很在意技术变化会把自己的职业带到哪里。",
            ],
            topics=profile.contribution_angles,
            core_lead="而你真正值得写下来的，可能不是某个知识点。",
            core_line="是那些——「做过之后才知道」的东西。",
        )

        return self._save(
            OnboardingState(
                onboarding_id=self._new_id(),
                profile=profile,
                portrait=portrait,
            )
        )

    # ------------------------------------------------------------------
    # 路径 B —— 先聊两句
    # ------------------------------------------------------------------

    def chat_question(self, step: int) -> str | None:
        if step < 0 or step >= len(CHAT_QUESTIONS):
            return None
        return CHAT_QUESTIONS[step]

    async def from_chat(self, req: ChatAnswerRequest) -> OnboardingState:
        """根据用户说过的话生成画像。

        Real 路径：LLM 语义理解 → ChatPortraitOut。
        Fallback：画像里出现的是用户实际说过的内容，不虚构经历。
        """
        said = [s for s in [*req.history, req.content] if s.strip()]

        if llm.available and said:
            try:
                out: ChatPortraitOut = await llm.generate_structured(
                    system=_CHAT_PORTRAIT_SYSTEM,
                    user=(
                        "这个人在回答「先聊两句」问题时说了这些：\n\n"
                        + "\n".join(f"- {s}" for s in said)
                    ),
                    schema=ChatPortraitOut,
                    temperature=0.5,
                    max_tokens=900,
                    stage="chat_portrait",
                )
                angles = [a.strip() for a in out.contribution_angles if a.strip()][:4]
                paragraphs = [p.strip() for p in out.paragraphs if p.strip()][:2]

                if angles and paragraphs:
                    profile = ContributionProfile(
                        source="chat_llm",
                        journey=out.journey.strip() or "正在经历一段自己还在消化的变化",
                        lived_experiences=[x.strip() for x in out.lived_experiences if x.strip()][:5],
                        recurring_interests=[x.strip() for x in out.recurring_interests if x.strip()][:5],
                        possible_knowledge=[x.strip() for x in out.possible_knowledge if x.strip()][:4],
                        contribution_angles=angles,
                        evidence=[ProfileEvidence(kind="said", label="你刚才说……", items=said)],
                    )
                    portrait = MindPortrait(
                        lead="从你刚才说的这些，我好像看到这样一个你。",
                        paragraphs=paragraphs,
                        topics=angles,
                        core_lead="而你真正值得写下来的，可能不是某个道理。",
                        core_line="是那些——「做过之后才知道」的东西。",
                    )
                    logger.info(
                        "profile stage=chat_portrait provider=real fallback=False"
                    )
                    return self._save(
                        OnboardingState(
                            onboarding_id=self._new_id(),
                            profile=profile,
                            portrait=portrait,
                        )
                    )
            except LLMUnavailable as exc:
                logger.warning(
                    "profile stage=chat_portrait provider=real fallback=True reason=%s",
                    exc,
                )

        # --- Fallback：保留用户原话，不虚构 ---
        logger.info("profile stage=chat_portrait provider=mock fallback=True")
        return self._save(self._mock_from_chat(said))

    def _mock_from_chat(self, said: list[str]) -> OnboardingState:
        profile = ContributionProfile(
            source="mock_chat",
            journey="正在经历一段自己还在消化的变化",
            lived_experiences=said[:4],
            recurring_interests=["自己正在做的事", "踩过的坑"],
            possible_knowledge=[
                "亲身做过之后才知道的判断",
                "当时想不明白、后来才想明白的事",
            ],
            contribution_angles=["踩过的坑", "真实的取舍", "经验与教训"],
            evidence=[ProfileEvidence(kind="said", label="你刚才说……", items=said)],
        )
        portrait = MindPortrait(
            lead="从你刚才说的这些，我好像看到这样一个你。",
            paragraphs=[
                "你不是在旁观，你是真的在里面待过。",
                "比起结论，你更清楚事情发生时具体是什么样子——"
                "那种东西，没做过的人写不出来。",
            ],
            topics=profile.contribution_angles,
            core_lead="而你真正值得写下来的，可能不是某个道理。",
            core_line="是那些——「做过之后才知道」的东西。",
        )
        return OnboardingState(
            onboarding_id=self._new_id(),
            profile=profile,
            portrait=portrait,
        )

    # ------------------------------------------------------------------
    # 自然语言纠正
    # ------------------------------------------------------------------

    async def correct(
        self, onboarding_id: str, content: str
    ) -> tuple[OnboardingState | None, bool]:
        """自然语言纠正。返回 (state, used_real)。"""
        state = self.get(onboarding_id)
        if state is None:
            return None, False

        text = content.strip()
        if not text:
            return state, False

        if llm.available:
            try:
                profile = state.profile
                said_so_far = [e.items for e in profile.evidence if e.kind == "said"]
                said_flat = [s for sublist in said_so_far for s in sublist]

                out: CorrectionOut = await llm.generate_structured(
                    system=_CORRECTION_SYSTEM,
                    user=(
                        f"用户之前说过：\n{chr(10).join(f'- {s}' for s in said_flat) if said_flat else '（没有历史记录）'}\n\n"
                        f"我对他的原始描述：\n"
                        f"- 正在走的路：{profile.journey}\n"
                        f"- 可能的知识：{'、'.join(profile.possible_knowledge)}\n"
                        f"- 贡献角度：{'、'.join(profile.contribution_angles)}\n\n"
                        f"他现在说：「{text}」\n\n"
                        "请更新对他的认识。"
                    ),
                    schema=CorrectionOut,
                    temperature=0.5,
                    max_tokens=700,
                    stage="correction",
                )

                angles = [a.strip() for a in out.contribution_angles if a.strip()][:4]
                paragraphs = [p.strip() for p in out.paragraphs if p.strip()][:2]

                if angles and paragraphs and out.ack:
                    profile.journey = out.journey.strip() or profile.journey
                    profile.possible_knowledge = [
                        x.strip() for x in out.possible_knowledge if x.strip()
                    ][:4] or profile.possible_knowledge
                    profile.contribution_angles = angles
                    profile.correction_count += 1

                    state.portrait = MindPortrait(
                        lead="",
                        ack=out.ack.strip(),
                        paragraphs=paragraphs,
                        topics=angles,
                        core_lead="我要找的，仍然是那些别人替代不了的部分。",
                        core_line="也就是——「做过之后才知道」的东西。",
                    )
                    logger.info(
                        "profile stage=correction provider=real fallback=False"
                    )
                    return self._save(state), True
            except LLMUnavailable as exc:
                logger.warning(
                    "profile stage=correction provider=real fallback=True reason=%s",
                    exc,
                )

        # --- Fallback：关键词规则 ---
        logger.info("profile stage=correction provider=mock fallback=True")
        return self._save(self._keyword_correct(state, text)), False

    def _keyword_correct(
        self, state: OnboardingState, text: str
    ) -> OnboardingState:
        """关键词命中的规则纠正。原 correct() 逻辑，作为 LLM 的 fallback。"""
        profile = state.profile
        hit_frontend = any(k in text for k in ["前端", "网页", "页面", "UI"])
        hit_not_ai = any(
            k in text
            for k in ["没那么懂 AI", "不是 AI", "没那么懂AI", "只是为了转行", "转行"]
        )
        hit_career = any(k in text for k in ["职场", "职业", "选择", "跳槽"])
        hit_backend = any(k in text for k in ["后端", "服务端", "架构"])

        if hit_frontend or hit_not_ai:
            profile.journey = "正在经历一次技术转型的前端开发者"
            profile.possible_knowledge = [
                "技术转型时真实的犹豫和取舍",
                "前端工程实践中的判断",
            ]
            profile.contribution_angles = ["技术转型", "前端实践", "职业选择", "学习踩坑"]
            ack = "明白了。"
            paragraphs = [
                "你不是一个「长期 AI 从业者」。",
                "更像是：一个正在经历技术转型的前端开发者。",
            ]
        elif hit_backend:
            profile.journey = "更偏工程和系统实现的开发者"
            profile.possible_knowledge = ["系统实现中的权衡", "线上问题里学到的东西"]
            profile.contribution_angles = ["工程实践", "系统设计", "线上踩坑", "职业选择"]
            ack = "明白了。"
            paragraphs = [
                "你更靠近工程和系统那一侧。",
                "那我应该去找的，是工程实践、系统设计、线上踩坑这类问题。",
            ]
        elif hit_career:
            profile.journey = "对职业路径本身有真实感触的人"
            profile.possible_knowledge = ["职业选择中的取舍", "做过决定之后才明白的事"]
            profile.contribution_angles = ["职业选择", "职场判断", "成长路径", "踩过的坑"]
            ack = "明白了。"
            paragraphs = [
                "比起技术本身，你更有话说的是职业路径这件事。",
                "那我应该去找的，是职业选择、职场判断、成长取舍这类问题。",
            ]
        else:
            profile.journey = "还在自己定义方向的人"
            profile.lived_experiences = [text[:40]] + profile.lived_experiences[:2]
            profile.possible_knowledge = ["自己真实经历过、别人替代不了的部分"]
            profile.contribution_angles = ["亲身经历", "真实取舍", "踩过的坑"]
            ack = "明白了。"
            paragraphs = [
                "那我刚才理解得太窄了。",
                f"按你说的，真正该被找出来的，是「{text[:28]}」这一类你亲身经历过的东西。",
            ]

        profile.correction_count += 1

        state.portrait = MindPortrait(
            lead="",
            ack=ack,
            paragraphs=paragraphs,
            topics=profile.contribution_angles,
            core_lead="我要找的，仍然是那些别人替代不了的部分。",
            core_line="也就是——「做过之后才知道」的东西。",
        )
        return state

    # ------------------------------------------------------------------
    # 从画像出发找问题（Mock fallback，真实链路走 question_matcher）
    # ------------------------------------------------------------------

    def match_questions(self, onboarding_id: str) -> list[MatchedQuestion]:
        state = self.get(onboarding_id)
        profile = state.profile if state else ContributionProfile()

        journey = profile.journey or "正在经历一些变化"
        knowledge = (
            profile.possible_knowledge[0]
            if profile.possible_knowledge
            else "做过之后才知道的东西"
        )
        angles = profile.contribution_angles or ["踩过的坑"]

        return [
            MatchedQuestion(
                question_id="q_career_lessons",
                title="工作两三年后，你悟出了哪些职场道理？",
                reason=QuestionMatchReason(
                    from_you=f"你刚才告诉我，你{journey}，",
                    therefore=f"而且真正让你有话说的，往往是那些「{knowledge}」。",
                ),
            ),
            MatchedQuestion(
                question_id="q_job_switch",
                title="程序员在哪个瞬间意识到自己应该跳槽？",
                reason=QuestionMatchReason(
                    from_you="这题需要的是具体的那一刻，而不是道理。",
                    therefore=f"你经历过{angles[0]}，这种瞬间你大概率真的有一个。",
                ),
            ),
            MatchedQuestion(
                question_id="q_ai_jobs",
                title="AI 会让程序员失业吗？",
                reason=QuestionMatchReason(
                    from_you="这题被太多没写过代码的人回答过了。",
                    therefore=f"而你是在里面的人——{journey}，你的判断和旁观者不一样。",
                ),
            ),
        ]


profile_service = MockProfileService()
