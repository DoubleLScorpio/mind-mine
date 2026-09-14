"""Onboarding 的 Mock 服务。

这一层的唯一任务：在不接 OAuth / LLM 的情况下，
让用户感觉「这个产品正在试着理解我」，而不是「我正在完善 Profile」。

接入真实能力时的替换路径：
    MockProfileService
      ↓  知乎 OAuth（followees / favorites / creations）
      ↓  ProfileExtractor（LLM）
    ContributionProfile

路由与前端契约保持不变。
"""

from __future__ import annotations

import uuid

from models.profile import (
    ChatAnswerRequest,
    ContributionProfile,
    MatchedQuestion,
    MindPortrait,
    OnboardingState,
    ProfileEvidence,
    QuestionMatchReason,
)

# --------------------------------------------------------------------------
# 「用知乎认识我」——逐步浮现的痕迹
#
# 不是扫描仪，是从散落的痕迹里慢慢认出一个人。
# 所以是三组「看到了什么」，不是 Processing 4/7。
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
#
# 不问「你的职业是什么」。只问能发现「值得贡献的经验」的问题。
# --------------------------------------------------------------------------

CHAT_QUESTIONS: list[str] = [
    "最近几年，你把最多时间花在什么事情上？",
    "这里面有没有什么，是你踩过坑以后才真正懂的？",
    "有没有哪件事，现在的你会很想提醒当时的自己？",
]


class MockProfileService:
    """进程内 Onboarding 存储 + Mock 画像生成。"""

    def __init__(self) -> None:
        self._states: dict[str, OnboardingState] = {}

    # ------------------------------------------------------------------
    # 读取
    # ------------------------------------------------------------------

    def get(self, onboarding_id: str) -> OnboardingState | None:
        return self._states.get(onboarding_id)

    def _save(self, state: OnboardingState) -> OnboardingState:
        self._states[state.onboarding_id] = state
        return state

    @staticmethod
    def _new_id() -> str:
        return f"ob_{uuid.uuid4().hex[:12]}"

    # ------------------------------------------------------------------
    # 路径 A —— 用知乎认识我
    # ------------------------------------------------------------------

    def traces(self) -> list[ProfileEvidence]:
        """返回逐步浮现的痕迹。全部是演示数据。"""
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
        """第 step 个问题（从 0 开始）。返回 None 表示可以生成画像了。"""
        if step < 0 or step >= len(CHAT_QUESTIONS):
            return None
        return CHAT_QUESTIONS[step]

    def from_chat(self, req: ChatAnswerRequest) -> OnboardingState:
        """根据用户自己说的话生成画像。

        Phase 1 不做真正的语义理解，但必须保证：
        画像里出现的是用户实际说过的内容，不是凭空虚构的经历。
        """
        said = [s for s in [*req.history, req.content] if s.strip()]

        profile = ContributionProfile(
            source="mock_chat",
            journey="正在经历一段自己还在消化的变化",
            lived_experiences=said[:4],
            recurring_interests=["自己正在做的事", "踩过的坑"],
            possible_knowledge=[
                "亲身做过之后才知道的判断",
                "当时想不明白、后来才想明白的事",
            ],
            contribution_angles=[
                "踩过的坑",
                "真实的取舍",
                "经验与教训",
            ],
            evidence=[
                ProfileEvidence(
                    kind="said",
                    label="你刚才说……",
                    items=said,
                )
            ],
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

        return self._save(
            OnboardingState(
                onboarding_id=self._new_id(),
                profile=profile,
                portrait=portrait,
            )
        )

    # ------------------------------------------------------------------
    # 自然语言纠正
    #
    # 不是字段编辑。用户直接说哪里不像，我们重新理解。
    # ------------------------------------------------------------------

    def correct(self, onboarding_id: str, content: str) -> OnboardingState | None:
        state = self.get(onboarding_id)
        if state is None:
            return None

        text = content.strip()
        profile = state.profile

        # Phase 1 用关键词命中做一次「重新理解」。
        # 命中与否都必须给出合理回应，绝不能让用户觉得白说了。
        lowered = text.lower()
        hit_frontend = any(k in text for k in ["前端", "网页", "页面", "UI"])
        hit_not_ai = any(
            k in text for k in ["没那么懂 AI", "不是 AI", "没那么懂AI", "只是为了转行", "转行"]
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
                "比起让我找 AI 专业知识，我更应该去找："
                "技术转型、前端实践、职业选择、学习踩坑这些问题。",
            ]
        elif hit_backend:
            profile.journey = "更偏工程和系统实现的开发者"
            profile.possible_knowledge = ["系统实现中的权衡", "线上问题里学到的东西"]
            profile.contribution_angles = ["工程实践", "系统设计", "线上踩坑", "职业选择"]
            ack = "明白了。"
            paragraphs = [
                "你更靠近工程和系统那一侧。",
                "那我应该去找的，是工程实践、系统设计、线上踩坑这类问题，"
                "而不是泛泛的技术讨论。",
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
            # 没命中关键词也必须认真回应用户说的话
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

        return self._save(state)

    # ------------------------------------------------------------------
    # 从画像出发找问题
    #
    # 「为什么是你？」必须引用画像里真实存在的信息。
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
                    from_you=f"这题需要的是具体的那一刻，而不是道理。",
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
