/**
 * Onboarding Store。
 *
 * 产品原则：不要让用户填写「我是谁」。
 * 所以这里没有任何「画像字段编辑」状态，只有：
 *   认识我 → 我眼中的你 → 哪里不像 → 该你答的问题
 *
 * 前端不关心画像来自 Mock / OAuth / LLM。
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api, ApiError } from '@/api/client'
import type {
  ContributionProfile,
  MatchedQuestion,
  MindPortrait,
  ProfileEvidence,
} from '@/types/profile'

/** Onboarding 的情绪线：Know → See → Find → Claim */
export type OnboardingStage =
  | 'opening'
  | 'knowme'
  | 'tracing'
  | 'chatting'
  | 'portrait'
  | 'correcting'
  | 'handoff'
  | 'match'

export const useOnboardingStore = defineStore('onboarding', () => {
  const stage = ref<OnboardingStage>('opening')

  const onboardingId = ref<string | null>(null)
  const profile = ref<ContributionProfile | null>(null)
  const portrait = ref<MindPortrait | null>(null)
  const questions = ref<MatchedQuestion[]>([])

  /** 逐步浮现的痕迹 */
  const traces = ref<ProfileEvidence[]>([])
  const revealedTraces = ref(0)

  /** 先聊两句 */
  const chatStep = ref(0)
  const chatQuestion = ref<string | null>(null)
  const chatHistory = ref<string[]>([])

  const loading = ref(false)
  const errorMessage = ref('')

  const ready = computed(() => onboardingId.value !== null && portrait.value !== null)

  function reset() {
    stage.value = 'opening'
    onboardingId.value = null
    profile.value = null
    portrait.value = null
    questions.value = []
    traces.value = []
    revealedTraces.value = 0
    chatStep.value = 0
    chatQuestion.value = null
    chatHistory.value = []
    errorMessage.value = ''
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

  function adopt(s: {
    onboarding_id: string
    profile: ContributionProfile
    portrait: MindPortrait
  }) {
    onboardingId.value = s.onboarding_id
    profile.value = s.profile
    portrait.value = s.portrait
  }

  // ---- 路径 A：用知乎认识我 ----

  /**
   * 痕迹逐条浮现。不是 Loading，是「正在从散落的痕迹里认出一个人」。
   * 所以每条之间有停顿，并且控制在几秒内。
   */
  async function traceMe() {
    stage.value = 'tracing'
    revealedTraces.value = 0

    const r = await withGuard(async () => {
      const t = await api.traces()
      traces.value = t.items
      return t
    })
    if (!r) return null

    for (let i = 0; i < traces.value.length; i++) {
      await sleep(i === 0 ? 500 : 1250)
      revealedTraces.value = i + 1
    }
    await sleep(1100)

    return withGuard(async () => {
      const s = await api.fromZhihu()
      adopt(s)
      stage.value = 'portrait'
      return s
    })
  }

  // ---- 路径 B：先聊两句 ----

  async function startChat() {
    stage.value = 'chatting'
    chatStep.value = 0
    chatHistory.value = []
    return withGuard(async () => {
      const r = await api.chatQuestion(0)
      chatQuestion.value = r.question
      return r
    })
  }

  /** 回答一轮。问够了就直接生成画像 */
  async function answerChat(content: string) {
    return withGuard(async () => {
      const next = await api.chatQuestion(chatStep.value + 1)

      if (next.done) {
        const s = await api.fromChat(
          chatStep.value,
          content,
          chatHistory.value,
        )
        chatHistory.value.push(content)
        adopt(s)
        stage.value = 'portrait'
        return s
      }

      chatHistory.value.push(content)
      chatStep.value += 1
      chatQuestion.value = next.question
      return next
    })
  }

  /** 用户觉得问够了，提前结束 */
  async function finishChatEarly(content: string) {
    return withGuard(async () => {
      const s = await api.fromChat(chatStep.value, content, chatHistory.value)
      chatHistory.value.push(content)
      adopt(s)
      stage.value = 'portrait'
      return s
    })
  }

  // ---- 自然语言纠正 ----

  async function correct(content: string) {
    if (!onboardingId.value) return null
    return withGuard(async () => {
      const s = await api.correctPortrait(onboardingId.value!, content)
      adopt(s)
      stage.value = 'portrait'
      return s
    })
  }

  // ---- 从画像出发找问题 ----

  async function findQuestions() {
    if (!onboardingId.value) return null
    // 「好。我大概知道该去哪里找了。」—— 一个很短的过渡
    stage.value = 'handoff'
    await sleep(1800)

    return withGuard(async () => {
      const r = await api.matchedQuestions(onboardingId.value!)
      questions.value = r.items
      stage.value = 'match'
      return r
    })
  }

  function sleep(ms: number) {
    return new Promise((r) => setTimeout(r, ms))
  }

  return {
    stage,
    onboardingId,
    profile,
    portrait,
    questions,
    traces,
    revealedTraces,
    chatStep,
    chatQuestion,
    chatHistory,
    loading,
    errorMessage,
    ready,
    reset,
    traceMe,
    startChat,
    answerChat,
    finishChatEarly,
    correct,
    findQuestions,
  }
})
