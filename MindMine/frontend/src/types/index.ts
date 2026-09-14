/**
 * MindMine 前端类型定义。
 * 与后端 backend/models/session.py 的 Pydantic 模型保持镜像。
 * 修改时必须两端同步。
 */

export type SessionState =
  | 'PROFILE'
  | 'DISCOVERY'
  | 'EXPERIENCE'
  | 'REFLECTION'
  | 'INSIGHT'
  | 'CHALLENGE'
  | 'REFINEMENT'
  | 'COMPOSE'
  | 'DONE'

export type CurrentStatus =
  | 'student'
  | 'early_career'
  | 'mid_career'
  | 'senior'
  | 'freelance'

export type SharePreference =
  | 'experience'
  | 'opinion'
  | 'expertise'
  | 'mistakes'

export interface UserProfile {
  source: 'manual' | 'oauth'
  current_status: CurrentStatus
  domains: string[]
  share_preferences: SharePreference[]
}

export interface QuestionCard {
  question_id: string
  title: string
  why_fits: string
  tag: string
  url: string | null
  /** mock = 演示数据；api = 真实知乎数据 */
  source: 'mock' | 'api'
}

export interface KnowledgeEvent {
  event: string
  result: string
}

/**
 * KnowledgeState 是系统内部结构，永远不直接渲染到界面上。
 * 用户看得见的只有 ThoughtFragment。
 */
export interface KnowledgeState {
  facts: string[]
  events: KnowledgeEvent[]
  beliefs: string[]
  conflicts: string[]
  reflections: string[]
  candidate_insights: string[]
}

/**
 * 面向用户展示的思想碎片。
 *
 * label 是开放字符串，不是枚举 —— 组件不得对具体分类做硬编码逻辑，
 * 接入 LLM 后可以生成任意标签。视觉重点始终是 text（用户原话），
 * 而不是分类标签。
 */
export interface ThoughtFragment {
  id: string
  label?: string | null
  text: string
  source_message_id: string
}

/** 碎片之间的因果关系，Insight Reveal 时据此绘制连接线 */
export interface FragmentLink {
  from_id: string
  to_id: string
  relation?: string | null
}

export interface ChatMessage {
  role: 'user' | 'ai'
  content: string
  turn: number
}

export interface Insight {
  version: 'V1' | 'V2'
  surface_claim: string
  deep_insight: string
  /**
   * 对经历的命名，先于 deep_insight 出现。
   * 顺序很重要：先「你做了什么」，再「所以什么成立」。
   */
  naming?: string | null
  confirmed_by_user: boolean
  user_edited_text: string | null
  /** V2：被弱化掉的绝对化表达，如「不要让」 */
  softened_span?: string | null
  /** V2：经过 Challenge 后用户自己加上的限定条件 */
  added_qualifiers?: string[]
}

export interface CommunityPerspective {
  id: string
  claim: string
  reason: string
  author: string
  badge: string
  source_label: string
  source_url: string | null
  challenge_question: string
  /** Phase 1 恒为 true，UI 必须显式标注演示数据 */
  is_mock: boolean
}

export interface Session {
  id: string
  created_at: string
  updated_at: string
  state: SessionState
  profile: UserProfile | null
  question: QuestionCard | null
  messages: ChatMessage[]
  knowledge_state: KnowledgeState
  fragments: ThoughtFragment[]
  fragment_links: FragmentLink[]
  user_turn_count: number
  insight_v1: Insight | null
  challenge: CommunityPerspective | null
  challenge_response: string | null
  insight_v2: Insight | null
  insight_v2_owned: boolean
  composed_answer: string | null
}

export interface PostMessageResponse {
  state: SessionState
  ai_reply: string | null
  knowledge_state: KnowledgeState
  fragments: ThoughtFragment[]
  fragment_links: FragmentLink[]
  user_turn_count: number
  insight_ready: boolean
  insight: Insight | null
}

export interface OwnershipResponse {
  state: SessionState
  insight_v2: Insight
  owned: boolean
}

export interface ConfirmInsightResponse {
  state: SessionState
  insight_v1: Insight
  challenge: CommunityPerspective
}

export interface ChallengeRespondResponse {
  state: SessionState
  insight_v2: Insight
  challenge_summary: string
}

export interface ComposeResponse {
  state: SessionState
  insight_v1: Insight
  challenge: CommunityPerspective
  challenge_response: string
  insight_v2: Insight
  composed_answer: string
  challenge_summary: string
}

/** 统一响应信封 */
export interface ApiEnvelope<T> {
  ok: boolean
  data?: T
  error?: {
    code: string
    message: string
  }
}

export function emptyKnowledgeState(): KnowledgeState {
  return {
    facts: [],
    events: [],
    beliefs: [],
    conflicts: [],
    reflections: [],
    candidate_insights: [],
  }
}
