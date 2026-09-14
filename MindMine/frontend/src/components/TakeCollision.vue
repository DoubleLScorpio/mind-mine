<script setup lang="ts">
/**
 * 观点对峙 —— 不是展示两条信息，而是「我的判断撞上了另一个人的判断」。
 *
 * 所以它是一个有先后的事件，不是一次性铺开的版面：
 *   own     先只有用户自己的判断，让他重新认一遍「这是我的」
 *   turn    「但知乎上，有人不会同意你。」—— 1 秒内说清接下来要发生什么
 *   clash   对方的观点从另一侧进入，两者沿中轴对峙
 *
 * 视觉上刻意不做卡片：卡片 = 信息陈列。
 * 这里只有排版和一条张力轴，两侧文字都朝轴心挤压。
 *
 * 两条红线：
 * 1. 用户的观点必须在场，且是先出现的那个（他是主场）。
 * 2. 两侧字号、行高、字重完全相同。任何一侧更大 = 系统在替用户站队。
 */
import { ref, onMounted, onBeforeUnmount } from 'vue'
import type { CommunityPerspective } from '@/types'

defineProps<{
  yourTake: string
  perspective: CommunityPerspective | null
}>()

const emit = defineEmits<{ (e: 'done'): void }>()

/** 0 只有我的判断 1 转折 2 对方进入 */
const phase = ref(0)
let timers: number[] = []

const SCHEDULE: [number, number][] = [
  [1, 1100],
  [2, 2200],
]

onMounted(() => {
  SCHEDULE.forEach(([p, d]) => {
    timers.push(window.setTimeout(() => setPhase(p), d))
  })
})

onBeforeUnmount(() => timers.forEach((t) => window.clearTimeout(t)))

function setPhase(p: number) {
  phase.value = p
  if (p >= 2) emit('done')
}

/** 点击跳过：推进到下一幕，不直接跳终态 */
function skip() {
  if (phase.value >= 2) return
  timers.forEach((t) => window.clearTimeout(t))
  timers = []
  setPhase(phase.value + 1)
}
</script>

<template>
  <div class="collision" :class="`p-${phase}`" @click="skip">
    <!-- 第一幕：只有用户自己的判断 -->
    <div class="mine">
      <div class="lead">这是你的判断。</div>
      <p class="take">{{ yourTake }}</p>
    </div>

    <!-- 张力轴。从中点向两端展开 -->
    <div v-if="phase >= 2" class="axis" />

    <!-- 第二幕：转折。1 秒内让用户知道接下来是观点挑战 -->
    <p v-if="phase >= 1" class="turn">但知乎上，有人不会同意你。</p>

    <!-- 第三幕：对方从另一侧进入 -->
    <div v-if="phase >= 2" class="theirs">
      <div class="lead theirs-lead">知乎上的另一种声音</div>
      <p class="take">「{{ perspective?.claim }}」</p>
      <p class="reason">{{ perspective?.reason }}</p>
      <!-- 合规红线：Mock 阶段必须明确标注，不得伪装真实作者或统计 -->
      <div v-if="perspective?.is_mock" class="mock-note">
        {{ perspective.source_label }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.collision {
  position: relative;
  max-width: 980px;
  margin: 0 auto;
  display: grid;
  align-items: center;
  transition: all 0.75s var(--ease);
}

/* 只有我的判断时：居中独占 */
.p-0,
.p-1 {
  grid-template-columns: 1fr;
  justify-items: center;
  text-align: center;
  min-height: 240px;
}

/* 对峙时：两侧朝轴心挤压 */
.p-2 {
  grid-template-columns: 1fr 1px 1fr;
  column-gap: 0;
  min-height: 300px;
}

.lead {
  font-size: 12px;
  letter-spacing: 0.16em;
  color: var(--text-dim);
  margin-bottom: 16px;
}

/* 两侧完全相同的排版。不给任何一方视觉优势 */
.take {
  margin: 0;
  font-size: clamp(17px, 2.1vw, 20px);
  line-height: 1.72;
  font-weight: 500;
  color: var(--text);
}

/* ---------- 我的判断 ---------- */

.mine {
  transition: all 0.75s var(--ease);
}

.p-0 .mine,
.p-1 .mine {
  max-width: 560px;
  animation: fade-up 0.5s var(--ease) both;
}

/* 进入对峙：退到左侧，文字朝轴心靠 */
.p-2 .mine {
  grid-column: 1;
  padding-right: 42px;
  text-align: right;
}

.p-2 .mine .lead {
  color: var(--insight);
}

/* ---------- 转折句 ---------- */

.turn {
  margin: 0;
  font-size: clamp(19px, 2.5vw, 24px);
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--text);
  animation: turn-in 0.5s var(--ease) both;
}

.p-1 .turn {
  margin-top: 42px;
}

/* 对峙开始后，转折句缩成轴心上的标记 */
.p-2 .turn {
  grid-column: 2;
  grid-row: 1;
  justify-self: center;
  writing-mode: vertical-rl;
  font-size: 12px;
  font-weight: 500;
  letter-spacing: 0.24em;
  color: var(--text-dim);
  background: var(--bg);
  padding: 14px 0;
  z-index: 2;
  white-space: nowrap;
}

/* ---------- 张力轴 ---------- */

.axis {
  grid-column: 2;
  grid-row: 1;
  justify-self: center;
  width: 1px;
  height: 100%;
  background: linear-gradient(
    to bottom,
    transparent,
    var(--border-strong) 18%,
    var(--border-strong) 82%,
    transparent
  );
  animation: axis-in 0.5s var(--ease) both;
}

/* ---------- 对方的判断 ---------- */

.theirs {
  grid-column: 3;
  padding-left: 42px;
  animation: from-right 0.6s var(--ease) 0.1s both;
}

.reason {
  margin: 14px 0 0;
  font-size: 14px;
  line-height: 1.65;
  color: var(--text-muted);
}

.mock-note {
  margin-top: 20px;
  font-size: 11px;
  color: var(--text-dim);
}

@keyframes turn-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
}

@keyframes axis-in {
  from {
    opacity: 0;
    transform: scaleY(0);
  }
}

@keyframes from-right {
  from {
    opacity: 0;
    transform: translateX(26px);
  }
}

@media (max-width: 820px) {
  .p-2 {
    grid-template-columns: 1fr;
    row-gap: 22px;
  }
  .p-2 .mine {
    grid-column: 1;
    padding-right: 0;
    text-align: left;
  }
  .p-2 .turn {
    grid-column: 1;
    grid-row: auto;
    writing-mode: horizontal-tb;
    padding: 0;
    justify-self: start;
  }
  .axis {
    grid-column: 1;
    grid-row: auto;
    width: 100%;
    height: 1px;
    background: var(--border-strong);
  }
  .theirs {
    grid-column: 1;
    padding-left: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .collision,
  .mine,
  .turn,
  .axis,
  .theirs {
    animation-duration: 0.01ms;
    transition-duration: 0.01ms;
  }
}
</style>
