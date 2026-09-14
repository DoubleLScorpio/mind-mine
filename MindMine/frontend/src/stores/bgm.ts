/**
 * 背景音乐：全局单例。
 *
 * 产品定位：不是播放器，是「一个人晚上开始回忆时房间里的一层空气」。
 * 所以这里只有 on / off 两个状态，没有进度、没有列表、没有可视化。
 *
 * 三条硬约束：
 * 1. 默认 OFF，绝不自动播放（尊重浏览器 autoplay policy 与用户注意力）。
 * 2. 任何音频失败都必须 silent failure —— BGM 不能影响 MindMine 主流程。
 * 3. Audio 实例全局唯一，挂在 App Root，路由切换不重建、不重播。
 */

import { defineStore } from 'pinia'
import { ref } from 'vue'

const SRC = '/audio/mindmine-ambient.mp3'

const KEY_ENABLED = 'mindmine_bgm_enabled'
const KEY_VOLUME = 'mindmine_bgm_volume'

/** 阅读态基准音量。必须明显低于用户注意力与现场讲解声。 */
export const DEFAULT_VOLUME = 0.18
/** Insight / 成文阅读阶段的减弱音量，让位给用户自己的话。 */
export const DIMMED_VOLUME = 0.11

function readStoredVolume(): number {
  try {
    const raw = localStorage.getItem(KEY_VOLUME)
    if (raw === null) return DEFAULT_VOLUME
    const v = Number.parseFloat(raw)
    // 上限 0.4：BGM 不该有变响的可能
    if (!Number.isFinite(v) || v < 0 || v > 0.4) return DEFAULT_VOLUME
    return v
  } catch {
    return DEFAULT_VOLUME
  }
}

function readStoredEnabled(): boolean {
  try {
    return localStorage.getItem(KEY_ENABLED) === 'true'
  } catch {
    return false
  }
}

function persist(key: string, value: string): void {
  try {
    localStorage.setItem(key, value)
  } catch {
    // 隐私模式下 localStorage 可能抛错，静默忽略
  }
}

export const useBgmStore = defineStore('bgm', () => {
  /** 用户是否希望播放。这是意图，不等于真的在响 */
  const enabled = ref(false)
  const volume = ref(DEFAULT_VOLUME)
  /** 音频不可用（404 / decode / 不支持）。为 true 时隐藏按钮，不打扰用户 */
  const unavailable = ref(false)

  let audio: HTMLAudioElement | null = null
  let fadeTimer: number | null = null

  function ensureAudio(): HTMLAudioElement | null {
    if (unavailable.value) return null
    if (audio) return audio

    try {
      const el = new Audio(SRC)
      el.loop = true
      el.preload = 'none' // 默认 OFF，不为未开启的功能耗流量
      el.volume = volume.value

      el.addEventListener('error', () => {
        // 404 / 解码失败 / 格式不支持：静默降级
        console.warn('[bgm] audio unavailable, disabling silently')
        unavailable.value = true
        enabled.value = false
      })

      audio = el
      return el
    } catch (err) {
      console.warn('[bgm] failed to create audio element', err)
      unavailable.value = true
      return null
    }
  }

  /** 从 localStorage 恢复偏好。被浏览器拦截时静默保持 OFF */
  async function init(): Promise<void> {
    volume.value = readStoredVolume()

    if (!readStoredEnabled()) return

    const el = ensureAudio()
    if (!el) return

    el.volume = volume.value
    try {
      await el.play()
      enabled.value = true
    } catch {
      // autoplay policy：没有用户手势就播不了。
      // 这是预期行为，不是错误 —— 保持 OFF，等用户自己点。
      enabled.value = false
    }
  }

  async function toggle(): Promise<void> {
    const el = ensureAudio()
    if (!el) return

    if (enabled.value) {
      el.pause()
      enabled.value = false
      persist(KEY_ENABLED, 'false')
      return
    }

    el.volume = volume.value
    try {
      await el.play()
      enabled.value = true
      persist(KEY_ENABLED, 'true')
    } catch (err) {
      // 用户手势后仍失败：静默放弃，不弹任何错误 UI
      console.warn('[bgm] play rejected', err)
      enabled.value = false
    }
  }

  /**
   * 平滑过渡到目标音量。
   * 用于 Insight Reveal / 成文阅读时轻微让位，不换歌、不制造高潮。
   */
  function fadeTo(target: number, ms = 600): void {
    const el = audio
    if (!el || !enabled.value) return

    if (fadeTimer !== null) {
      clearInterval(fadeTimer)
      fadeTimer = null
    }

    const from = el.volume
    const steps = Math.max(1, Math.round(ms / 40))
    let i = 0

    fadeTimer = window.setInterval(() => {
      i += 1
      const t = i / steps
      const next = from + (target - from) * t
      el.volume = Math.min(0.4, Math.max(0, next))
      if (i >= steps && fadeTimer !== null) {
        clearInterval(fadeTimer)
        fadeTimer = null
      }
    }, 40)
  }

  /** 让位给用户自己的话 */
  function duck(): void {
    fadeTo(DIMMED_VOLUME)
  }

  /** 恢复常规音量 */
  function undock(): void {
    fadeTo(volume.value)
  }

  return {
    enabled,
    volume,
    unavailable,
    init,
    toggle,
    duck,
    undock,
  }
})
