/**
 * 会话 Store。
 * 后端是会话状态的唯一真相来源，这里只做 UI 状态与响应缓存。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, ApiError } from '@/api/client'
import {
  emptyKnowledgeState,
  type CommunityPerspective,
  type FragmentLink,
  type Insight,
  type KnowledgeState,
  type ChatMessage,
  type QuestionCard,
  type SessionState,
  type ThoughtFragment,
  type UserProfile,
} from '@/types'

/**
 * Insight Reveal 的幕次。
 *
 * 这不是页面切换，而是同一个空间内的形变：
 *   idle      访谈进行中
 *   settle    环境退场，只剩用户说过的话
 *   connect   碎片聚拢成经历链
 *   pause     静止。发现之前的那口气
 *   naming    先给经历命名
 *   insight   再长出观点
 */
export type RevealPhase =
  | 'idle'
  | 'settle'
  | 'connect'
  | 'pause'
  | 'naming'
  | 'insight'

export const useSessionStore = defineStore('session', () => {
  // ---- 画像（Stage 1，进入会话前保存在前端） ----
  const profile = ref<UserProfile | null>(null)

  // ---- 会话核心状态 ----
  const sessionId = ref<string | null>(null)
  const state = ref<SessionState>('PROFILE')
  const question = ref<QuestionCard | null>(null)
  const messages = ref<ChatMessage[]>([])
  /** 系统内部结构，仅用于调试与后续 LLM 接入，不渲染到界面 */
  const knowledgeState = ref<KnowledgeState>(emptyKnowledgeState())
  /** 用户唯一看得见的那一层 */
  const fragments = ref<ThoughtFragment[]>([])
  const fragmentLinks = ref<FragmentLink[]>([])
  const userTurnCount = ref(0)

  const insightV1 = ref<Insight | null>(null)
  const challenge = ref<CommunityPerspective | null>(null)
  const challengeSummary = ref('')
  const challengeResponse = ref('')
  const insightV2 = ref<Insight | null>(null)
  const insightV2Owned = ref(false)
  /** 看了追问但决定保留原判断 —— 不生成 V2，也不算没想清楚 */
  const takeKept = ref(false)
  const composedAnswer = ref('')

  // ---- UI 状态 ----
  const loading = ref(false)
  const errorMessage = ref('')
  const revealPhase = ref<RevealPhase>('idle')

  const insightReady = computed(
    () => state.value === 'INSIGHT' && insightV1.value !== null,
  )

  /**
   * The more you speak, the less AI you see.
   * 用户说得越多，AI 在视觉上退得越靠后。
   * 返回 0~1，0 = 访谈刚开始，1 = 用户的思想完全占据画面。
   */
  const mindWeight = computed(() => {
    if (revealPhase.value !== 'idle') return 1
    const n = fragments.value.length
    return Math.min(n / 5, 1)
  })

  function reset() {
    sessionId.value = null
    state.value = 'PROFILE'
    question.value = null
    messages.value = []
    knowledgeState.value = emptyKnowledgeState()
    fragments.value = []
    fragmentLinks.value = []
    userTurnCount.value = 0
    insightV1.value = null
    challenge.value = null
    challengeSummary.value = ''
    challengeResponse.value = ''
    insightV2.value = null
    insightV2Owned.value = false
    composedAnswer.value = ''
    errorMessage.value = ''
    revealPhase.value = 'idle'
    clearRevealTimers()
  }

  // ---- Insight Reveal 时序编排 ----
  //
  // 关键：这不是页面切换。聊天区不卸载，只是退到背景里。
  // 移动的是用户自己说过的话，所以观点看起来是从他的经历里长出来的。

  let revealTimers: number[] = []

  function clearRevealTimers() {
    revealTimers.forEach((t) => window.clearTimeout(t))
    revealTimers = []
  }

  /** 幕次时间表（毫秒）。pause 那一段的静止是刻意的，不要压缩。 */
  const REVEAL_SCHEDULE: [RevealPhase, number][] = [
    ['settle', 80],
    ['connect', 620],
    ['pause', 1900],
    ['naming', 2600],
    ['insight', 4000],
  ]

  function startReveal() {
    clearRevealTimers()
    REVEAL_SCHEDULE.forEach(([phase, delay]) => {
      revealTimers.push(
        window.setTimeout(() => {
          revealPhase.value = phase
        }, delay),
      )
    })
  }

  /** 点击跳过：推进到下一幕，而不是直接跳到终态 */
  function advanceReveal() {
    const order: RevealPhase[] = [
      'idle',
      'settle',
      'connect',
      'pause',
      'naming',
      'insight',
    ]
    const i = order.indexOf(revealPhase.value)
    if (i < 0 || i >= order.length - 1) return
    clearRevealTimers()
    revealPhase.value = order[i + 1]
  }

  function setProfile(p: UserProfile) {
    profile.value = p
  }

  async function withGuard<T>(fn: () => Promise<T>): Promise<T | null> {
    loading.value = true
    errorMessage.value = ''
    try {
      return await fn()
    } catch (e) {
      errorMessage.value =
        e instanceof ApiError ? e.message : '发生了未知错误，请重试。'
      return null
    } finally {
      loading.value = false
    }
  }

  async function startSession(questionId: string) {
    if (!profile.value) {
      errorMessage.value = '请先完成轻画像。'
      return null
    }
    return withGuard(async () => {
      reset()
      const s = await api.createSession(profile.value!, questionId)
      sessionId.value = s.id
      state.value = s.state
      question.value = s.question
      messages.value = s.messages
      knowledgeState.value = s.knowledge_state
      fragments.value = s.fragments ?? []
      fragmentLinks.value = s.fragment_links ?? []
      userTurnCount.value = s.user_turn_count
      return s
    })
  }

  async function loadSession(id: string) {
    return withGuard(async () => {
      const s = await api.getSession(id)
      sessionId.value = s.id
      state.value = s.state
      question.value = s.question
      messages.value = s.messages
      knowledgeState.value = s.knowledge_state
      fragments.value = s.fragments ?? []
      fragmentLinks.value = s.fragment_links ?? []
      userTurnCount.value = s.user_turn_count
      insightV1.value = s.insight_v1
      challenge.value = s.challenge
      challengeResponse.value = s.challenge_response ?? ''
      insightV2.value = s.insight_v2
      insightV2Owned.value = s.insight_v2_owned ?? false
      composedAnswer.value = s.composed_answer ?? ''
      if (s.profile) profile.value = s.profile
      return s
    })
  }

  async function sendMessage(content: string) {
    if (!sessionId.value) return null
    // 乐观追加用户消息，让对话区立即有反馈
    messages.value.push({
      role: 'user',
      content,
      turn: userTurnCount.value + 1,
    })
    return withGuard(async () => {
      const r = await api.postMessage(sessionId.value!, content)
      state.value = r.state
      knowledgeState.value = r.knowledge_state
      fragments.value = r.fragments ?? []
      fragmentLinks.value = r.fragment_links ?? []
      userTurnCount.value = r.user_turn_count
      if (r.ai_reply) {
        messages.value.push({
          role: 'ai',
          content: r.ai_reply,
          turn: r.user_turn_count,
        })
      }
      if (r.insight_ready && r.insight) {
        insightV1.value = r.insight
        // 不切页面、不弹窗：在当前空间里启动三幕形变
        startReveal()
      }
      return r
    })
  }

  async function confirmInsight() {
    if (!sessionId.value) return null
    return withGuard(async () => {
      const r = await api.confirmInsight(sessionId.value!)
      state.value = r.state
      insightV1.value = r.insight_v1
      challenge.value = r.challenge
      return r
    })
  }

  async function editInsight(text: string) {
    if (!sessionId.value) return null
    return withGuard(async () => {
      const r = await api.editInsight(sessionId.value!, text)
      insightV1.value = r.insight_v1
      return r
    })
  }

  async function respondChallenge(content: string) {
    if (!sessionId.value) return null
    challengeResponse.value = content
    return withGuard(async () => {
      const r = await api.respondChallenge(sessionId.value!, content)
      state.value = r.state
      insightV2.value = r.insight_v2
      insightV2Owned.value = false
      challengeSummary.value = r.challenge_summary
      return r
    })
  }

  /**
   * 不看追问，或看完直接去写答案。
   * Challenge 是增强体验，不是必经流程 —— 所以这是一条完整可用路径。
   */
  async function skipChallenge() {
    if (!sessionId.value) return null
    return withGuard(async () => {
      const r = await api.skipChallenge(sessionId.value!)
      state.value = r.state
      insightV1.value = r.insight_v1
      insightV2.value = null
      insightV2Owned.value = true
      return r
    })
  }

  /**
   * 看了追问，仍然这么想。
   * 不强制生成 V2 —— 观点经过追问后仍然成立，本身也是一次更坚定的确认。
   */
  async function keepTake() {
    if (!sessionId.value) return null
    return withGuard(async () => {
      const r = await api.keepTake(sessionId.value!)
      state.value = r.state
      insightV1.value = r.insight_v1
      insightV2.value = null
      insightV2Owned.value = true
      takeKept.value = true
      return r
    })
  }

  /**
   * Ownership handshake。
   * AI 可以帮助发现和整理，但「这是不是我的观点」只能由用户决定。
   */
  async function claimOwnership(editedText?: string) {
    if (!sessionId.value) return null
    return withGuard(async () => {
      const r = await api.setOwnership(sessionId.value!, true, editedText)
      insightV2.value = r.insight_v2
      insightV2Owned.value = r.owned
      return r
    })
  }

  async function compose() {
    if (!sessionId.value) return null
    return withGuard(async () => {
      const r = await api.compose(sessionId.value!)
      state.value = r.state
      insightV1.value = r.insight_v1
      challenge.value = r.challenge
      challengeResponse.value = r.challenge_response
      insightV2.value = r.insight_v2
      composedAnswer.value = r.composed_answer
      challengeSummary.value = r.challenge_summary
      return r
    })
  }

  return {
    profile,
    sessionId,
    state,
    question,
    messages,
    knowledgeState,
    fragments,
    fragmentLinks,
    userTurnCount,
    insightV1,
    challenge,
    challengeSummary,
    challengeResponse,
    insightV2,
    insightV2Owned,
    takeKept,
    composedAnswer,
    loading,
    errorMessage,
    insightReady,
    revealPhase,
    mindWeight,
    reset,
    setProfile,
    startSession,
    loadSession,
    sendMessage,
    confirmInsight,
    editInsight,
    respondChallenge,
    skipChallenge,
    keepTake,
    claimOwnership,
    compose,
    startReveal,
    advanceReveal,
  }
})
