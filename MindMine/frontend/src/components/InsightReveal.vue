<script setup lang="ts">
/**
 * Insight Reveal —— 观点从用户自己的经历里长出来的那一刻。
 *
 * 这不是一个新页面，也不是 Modal。调用方把它叠在访谈界面之上，
 * 访谈区不卸载，只是退到背景里。移动的是用户说过的话本身。
 *
 * 幕次由 store 的 revealPhase 驱动：
 *   settle   环境退场
 *   connect  碎片聚拢成经历链
 *   pause    静止 —— 发现之前的那口气
 *   naming   先给经历命名（只是复述用户做过什么，不加判断）
 *   insight  再长出观点
 */
import { computed, watch } from 'vue'
import FragmentField from './FragmentField.vue'
import type { FragmentLink, Insight, ThoughtFragment } from '@/types'
import type { RevealPhase } from '@/stores/session'
import { useBgmStore } from '@/stores/bgm'

const bgm = useBgmStore()

const props = defineProps<{
  phase: RevealPhase
  fragments: ThoughtFragment[]
  links: FragmentLink[]
  insight: Insight | null
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'skip'): void
  (e: 'confirm'): void
  (e: 'edit', text: string): void
}>()

const showLinks = computed(() =>
  ['connect', 'pause', 'naming', 'insight'].includes(props.phase),
)
const asEvidence = computed(() => ['naming', 'insight'].includes(props.phase))
const showWhisper = computed(() =>
  ['pause', 'naming', 'insight'].includes(props.phase),
)
const showNaming = computed(() => ['naming', 'insight'].includes(props.phase))
const showInsight = computed(() => props.phase === 'insight')

// Insight 亮相的那一刻，音乐轻微退后。
// 不换歌、不加高潮 —— 这一刻的主角是用户自己的话。
watch(showInsight, (on) => (on ? bgm.duck() : bgm.undock()))

/** 被点名的两张：代价与结果。经历链里最刺的那部分 */
const HIGHLIGHT = ['f_cost', 'f_outcome']
const highlightIds = computed(() =>
  ['pause', 'naming', 'insight'].includes(props.phase) ? HIGHLIGHT : [],
)
</script>

<template>
  <div class="reveal" @click="emit('skip')">
    <div class="stage" :class="{ 'is-evidence': asEvidence }">
      <FragmentField
        :fragments="fragments"
        :links="links"
        layout="chain"
        :show-links="showLinks"
        :evidence="asEvidence"
        :highlight-ids="highlightIds"
      />
    </div>

    <!-- 低语。不是 AI 在宣布，是用户自己心里的那句 -->
    <p v-if="showWhisper" class="whisper">等一下。这里有点东西。</p>

    <!-- 命名：只是把用户做过的事重新讲一遍，不加任何判断 -->
    <p v-if="showNaming" class="naming">{{ insight?.naming }}</p>

    <!-- 观点：从上面那件事里长出来的 -->
    <div v-if="showInsight" class="insight" @click.stop>
      <p class="insight-text">{{ insight?.deep_insight }}</p>

      <div class="actions">
        <button class="btn btn-insight" :disabled="loading" @click="emit('confirm')">
          {{ loading ? '…' : '就是这个' }}
        </button>
        <button
          class="btn btn-ghost"
          @click="emit('edit', insight?.deep_insight ?? '')"
        >
          我想改一下
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.reveal {
  position: relative;
  z-index: 3;
  min-height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 40px 24px;
}

.stage {
  transition:
    transform 0.9s var(--ease),
    opacity 0.9s var(--ease);
}

/* 观点出现后，经历链退到上方、缩小 —— 它变成观点背后的证据 */
.stage.is-evidence {
  transform: scale(0.82) translateY(-12px);
}

.whisper {
  margin: 34px 0 0;
  font-size: 15px;
  color: var(--text-muted);
  letter-spacing: 0.02em;
  animation: soft-in 0.7s var(--ease) backwards;
}

.naming {
  margin: 26px 0 0;
  max-width: 620px;
  text-align: center;
  font-size: clamp(20px, 2.6vw, 26px);
  line-height: 1.55;
  font-weight: 600;
  color: var(--insight);
  letter-spacing: -0.01em;
  animation: rise-in 0.72s var(--ease) backwards;
}

.insight {
  margin-top: 30px;
  max-width: 600px;
  animation: rise-in 0.72s var(--ease) backwards;
}

.insight-text {
  margin: 0;
  padding-left: 20px;
  border-left: 2px solid var(--insight);
  font-size: clamp(17px, 2vw, 20px);
  line-height: 1.72;
  color: var(--text);
}

.actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 34px;
  animation: soft-in 0.6s var(--ease) 0.5s backwards;
}

@keyframes soft-in {
  from {
    opacity: 0;
  }
}

@keyframes rise-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .stage,
  .whisper,
  .naming,
  .insight,
  .actions {
    animation-duration: 0.01ms;
    transition-duration: 0.01ms;
  }
}
</style>
