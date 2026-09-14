/**
 * 唯一的 API 客户端。
 * AGENTS.md 约束：组件中不得内联 fetch/axios 调用，全部走此处的类型化封装。
 */

import type {
  ApiEnvelope,
  ChallengeRespondResponse,
  ComposeResponse,
  ConfirmInsightResponse,
  Insight,
  OwnershipResponse,
  PostMessageResponse,
  Session,
  UserProfile,
} from '@/types'
import type {
  MatchedQuestion,
  OnboardingState,
  ProfileEvidence,
} from '@/types/profile'

/**
 * API 根地址。
 *
 * 本地开发：留空，走 vite.config.ts 的 /api 代理到 127.0.0.1:8078。
 * 线上部署：设 VITE_API_BASE_URL=https://<backend-host>，指向独立部署的后端。
 *
 * 只允许放公开配置。任何 Secret（LLM_API_KEY / 知乎 Access Secret）
 * 都不得出现在前端，只能配置在后端部署平台的环境变量里。
 */
const API_ORIGIN = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '')
const BASE = `${API_ORIGIN}/api/v1`

export class ApiError extends Error {
  code: string
  constructor(code: string, message: string) {
    super(message)
    this.code = code
    this.name = 'ApiError'
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  let res: Response
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    })
  } catch {
    throw new ApiError('NETWORK_ERROR', '无法连接到后端服务，请确认后端已启动。')
  }

  let body: ApiEnvelope<T> | { detail?: ApiEnvelope<T> }
  try {
    body = await res.json()
  } catch {
    throw new ApiError('INVALID_RESPONSE', '服务端返回了无法解析的内容。')
  }

  // FastAPI 的 HTTPException 会把信封包在 detail 中
  const envelope = (
    'detail' in body && body.detail ? body.detail : body
  ) as ApiEnvelope<T>

  if (!res.ok || !envelope.ok) {
    throw new ApiError(
      envelope.error?.code ?? 'UNKNOWN',
      envelope.error?.message ?? `请求失败（HTTP ${res.status}）`,
    )
  }

  return envelope.data as T
}

export const api = {
  health: () =>
    request<{ status: string; phase: string; demo_mode: boolean }>('/health'),

  // ---- Onboarding：不要让用户填写「我是谁」 ----

  /** 逐步浮现的痕迹。Phase 1 全部是演示数据 */
  traces: () =>
    request<{ items: ProfileEvidence[] }>('/onboarding/traces'),

  /** 用知乎认识我。Phase 1 不接 OAuth */
  fromZhihu: () =>
    request<OnboardingState>('/onboarding/from-zhihu', { method: 'POST' }),

  /** 先聊两句：取第 step 个问题 */
  chatQuestion: (step: number) =>
    request<{ question: string | null; done: boolean }>(
      `/onboarding/chat/${step}`,
    ),

  fromChat: (step: number, content: string, history: string[]) =>
    request<OnboardingState>('/onboarding/from-chat', {
      method: 'POST',
      body: JSON.stringify({ step, content, history }),
    }),

  /** 自然语言纠正。不是字段编辑 */
  correctPortrait: (onboardingId: string, content: string) =>
    request<OnboardingState>('/onboarding/correct', {
      method: 'POST',
      body: JSON.stringify({ onboarding_id: onboardingId, content }),
    }),

  /** 从画像出发找问题 */
  matchedQuestions: (onboardingId: string) =>
    request<{ items: MatchedQuestion[] }>(
      `/onboarding/${onboardingId}/questions`,
    ),

  createSession: (
    profile: UserProfile,
    questionId: string,
    title = '',
    url = '',
  ) =>
    request<Session>('/sessions', {
      method: 'POST',
      body: JSON.stringify({
        profile,
        question_id: questionId,
        title,
        url,
      }),
    }),

  getSession: (sessionId: string) =>
    request<Session>(`/sessions/${sessionId}`),

  postMessage: (sessionId: string, content: string) =>
    request<PostMessageResponse>(`/sessions/${sessionId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    }),

  confirmInsight: (sessionId: string) =>
    request<ConfirmInsightResponse>(`/sessions/${sessionId}/insight/confirm`, {
      method: 'POST',
    }),

  editInsight: (sessionId: string, content: string) =>
    request<{ insight_v1: Insight }>(`/sessions/${sessionId}/insight`, {
      method: 'PATCH',
      body: JSON.stringify({ content }),
    }),

  respondChallenge: (sessionId: string, content: string) =>
    request<ChallengeRespondResponse>(
      `/sessions/${sessionId}/challenge/respond`,
      {
        method: 'POST',
        body: JSON.stringify({ content }),
      },
    ),

  /** 不看追问，或看完直接去写答案。不弹二次确认 */
  skipChallenge: (sessionId: string) =>
    request<{
      state: import('@/types').SessionState
      insight_v1: Insight
      challenge_skipped: boolean
    }>(`/sessions/${sessionId}/challenge/skip`, { method: 'POST' }),

  /** 看了追问，仍然这么想。不强制生成 V2 */
  keepTake: (sessionId: string) =>
    request<{
      state: import('@/types').SessionState
      insight_v1: Insight
      take_kept: boolean
    }>(`/sessions/${sessionId}/challenge/keep`, { method: 'POST' }),

  /**
   * Ownership handshake。
   * 后端强制约束：未经用户认领，compose 会返回 409。
   */
  setOwnership: (sessionId: string, owned: boolean, editedText?: string) =>
    request<OwnershipResponse>(`/sessions/${sessionId}/insight/ownership`, {
      method: 'POST',
      body: JSON.stringify({ owned, edited_text: editedText ?? null }),
    }),

  compose: (sessionId: string) =>
    request<ComposeResponse>(`/sessions/${sessionId}/compose`, {
      method: 'POST',
    }),
}
