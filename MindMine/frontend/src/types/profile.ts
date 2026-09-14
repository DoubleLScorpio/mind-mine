/**
 * Onboarding 类型定义。
 * 与后端 backend/models/profile.py 的 Pydantic 模型保持镜像。
 * 修改时必须两端同步。
 *
 * 注意：这些字段名永远不会出现在界面上。
 * 用户只看到 MindPortrait 的自然语言。
 */

/** MindMine 认识这个人所依据的痕迹。Phase 1 全部是演示数据 */
export interface ProfileEvidence {
  kind: 'follow' | 'favorite' | 'creation' | 'said'
  label: string
  items: string[]
  is_mock: boolean
}

/**
 * 不是「这个人是谁」，而是「这个人有什么值得写下来」。
 * possible_knowledge 与 contribution_angles 权重最高。
 */
export interface ContributionProfile {
  source:
    | 'mock_zhihu'
    | 'mock_chat'
    | 'oauth'
    | 'chat_llm'
    | 'chat_mock'
  journey: string
  lived_experiences: string[]
  recurring_interests: string[]
  possible_knowledge: string[]
  contribution_angles: string[]
  evidence: ProfileEvidence[]
  correction_count: number
}

/**
 * 「我好像看到这样一个你。」
 * 语气必须保持不确定 —— 这是 AI 的理解，不是事实裁决。
 */
export interface MindPortrait {
  lead: string
  paragraphs: string[]
  topics: string[]
  core_lead: string
  core_line: string
  /** 纠正之后的开场白（「明白了。」） */
  ack?: string | null
}

export interface OnboardingState {
  onboarding_id: string
  profile: ContributionProfile
  portrait: MindPortrait
}

/** 「为什么是你？」必须引用画像里真实存在的信息 */
export interface QuestionMatchReason {
  from_you: string
  therefore: string
}

export interface MatchedQuestion {
  question_id: string
  title: string
  reason: QuestionMatchReason
  url: string | null
  source: 'mock' | 'api'
}
