<script setup lang="ts">
/**
 * 观点修正 —— 同一个观点正在被改写，不是换成一个新版本。
 *
 * 用户必须看见自己那句话发生了什么：
 *   1. 绝对化的表达被划掉、淡出
 *   2. 新的限定条件逐个升起、落位
 *
 * 目标不是「AI 给了我一个更高级的版本」，
 * 而是「我刚才确实把自己的观点想得更准确了」。
 * 所以限定词是逐个出现的 —— 用户能数出自己多想到了几件事。
 */
import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import type { Insight } from '@/types'

const props = defineProps<{
  v1: Insight | null
  v2: Insight | null
  /** 用户回应挑战时说的话 */
  response: string
}>()

/** 0 原句 1 松动 2 落入限定 3 定名 */
const step = ref(0)
let timers: number[] = []

const qualifiers = computed(() => props.v2?.added_qualifiers ?? [])
const softened = computed(() => props.v2?.softened_span ?? '')

/** 把 V1 拆成「被弱化的部分 + 其余」，好单独给前者加删除线 */
const v1Parts = computed(() => {
  const text = props.v1?.deep_insight ?? ''
  const span = softened.value
  if (span && text.startsWith(span)) {
    return { head: span, rest: text.slice(span.length) }
  }
  return { head: '', rest: text }
})

/** 把 V2 按限定词切开，好让它们逐个落位 */
const v2Parts = computed(() => {
  const text = props.v2?.deep_insight ?? ''
  const qs = qualifiers.value
  if (!qs.length) return [{ text, qualifier: false }]

  const pattern = new RegExp(`(${qs.map(escapeRe).join('|')})`, 'g')
  return text
    .split(pattern)
    .filter((s) => s !== '')
    .map((s) => ({ text: s, qualifier: qs.includes(s) }))
})

function escapeRe(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

onMounted(() => {
  const schedule: [number, number][] = [
    [1, 500],
    [2, 1500],
    [3, 3000],
  ]
  schedule.forEach(([s, d]) => {
    timers.push(window.setTimeout(() => (step.value = s), d))
  })
})

onBeforeUnmount(() => timers.forEach((t) => window.clearTimeout(t)))

function skip() {
  timers.forEach((t) => window.clearTimeout(t))
  timers = []
  if (step.value < 3) step.value += 1
}
</script>

<template>
  <div class="rewrite" @click="skip">
    <!-- 原句。先让用户认出「这是我刚才那句」 -->
    <div v-if="step < 2" class="line original" :class="{ loosening: step >= 1 }">
      <span v-if="v1Parts.head" class="softened">{{ v1Parts.head }}</span
      ><span>{{ v1Parts.rest }}</span>
    </div>

    <!-- 用户自己回应里的那半句，是修正的来源 -->
    <p v-if="step >= 1 && step < 3" class="from-you">你说：{{ response }}</p>

    <!-- 改写后的句子。限定词逐个落位 -->
    <div v-if="step >= 2" class="line refined">
      <template v-for="(p, i) in v2Parts" :key="i">
        <span
          v-if="p.qualifier"
          class="qualifier"
          :style="{ animationDelay: `${i * 120}ms` }"
          >{{ p.text }}</span
        >
        <span v-else>{{ p.text }}</span>
      </template>
    </div>

    <div v-if="step >= 3" class="label">YOUR TAKE, REFINED.</div>
  </div>
</template>

<style scoped>
.rewrite {
  max-width: 620px;
  margin: 0 auto;
  min-height: 260px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.line {
  font-size: clamp(19px, 2.3vw, 23px);
  line-height: 1.72;
  font-weight: 500;
  color: var(--text);
}

.original {
  transition: opacity 0.5s var(--ease);
}

/* 绝对化的表达被划掉、褪色，原地留下空缺 */
.softened {
  transition:
    opacity 0.7s var(--ease),
    color 0.7s var(--ease);
}

.loosening .softened {
  text-decoration: line-through;
  opacity: 0.28;
}

.from-you {
  margin: 26px 0 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-dim);
  max-width: 340px;
  animation: soft-in 0.5s var(--ease) backwards;
}

.refined {
  animation: soft-in 0.6s var(--ease) backwards;
}

/* 新加的限定条件：升起、落位，短暂闪一下金色 */
.qualifier {
  display: inline-block;
  color: var(--insight);
  font-weight: 600;
  animation: land 0.52s var(--ease) backwards;
}

.label {
  margin-top: 32px;
  font-size: 13px;
  letter-spacing: 0.16em;
  color: var(--insight);
  animation: soft-in 0.6s var(--ease) backwards;
}

@keyframes land {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
}

@keyframes soft-in {
  from {
    opacity: 0;
    transform: translateY(6px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .qualifier,
  .refined,
  .from-you,
  .label {
    animation-duration: 0.01ms;
  }
}
</style>
