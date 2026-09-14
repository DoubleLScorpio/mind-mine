<script setup lang="ts">
/**
 * 一次插进来的追问。
 *
 * 这不是「另一个观点」，而是「别人站在你的观点面前，会问你的一句话」。
 * 所以它不占据视觉中心 —— 用户自己的观点仍然在上方，
 * 追问从它附近轻轻浮现，像一个插入进来的声音。
 *
 * 明确不做：两卡对撞、VS、红蓝阵营、擂台效果。
 * 这是 Reflection，不是 Debate。
 */
import type { CommunityPerspective } from '@/types'

defineProps<{
  take: string
  perspective: CommunityPerspective | null
}>()
</script>

<template>
  <div class="wrap">
    <!-- 用户的观点仍然在上面，仍然是主角 -->
    <div class="take-block">
      <p class="take-lead">你想说的是</p>
      <p class="take">{{ take }}</p>
    </div>

    <!-- 追问从观点附近浮现，缩进对齐，视觉上依附于它 -->
    <div class="voice">
      <p class="voice-lead">有人可能会追问：</p>
      <blockquote class="question">
        {{ perspective?.challenge_question }}
      </blockquote>
      <!-- 合规红线：Mock 阶段必须明确标注，不得伪装真实作者 -->
      <p v-if="perspective?.is_mock" class="note">
        {{ perspective.source_label }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.wrap {
  max-width: 620px;
  margin: 0 auto;
}

.take-block {
  transition: opacity 0.6s var(--ease);
}

.take-lead {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--text-dim);
}

.take {
  margin: 0;
  padding-left: 20px;
  border-left: 2px solid var(--insight);
  font-size: clamp(18px, 2.2vw, 21px);
  line-height: 1.72;
  font-weight: 550;
  color: var(--text);
  letter-spacing: -0.01em;
}

/* ---------- 插进来的声音 ---------- */

.voice {
  margin-top: 44px;
  margin-left: 20px;
  padding-left: 22px;
  border-left: 1px solid var(--border-strong);
  animation: voice-in 0.75s var(--ease) both;
}

.voice-lead {
  margin: 0 0 14px;
  font-size: 13.5px;
  color: var(--text-dim);
}

/* 字号刻意小于用户的观点 —— 它是来提问的，不是来压过谁的 */
.question {
  margin: 0;
  font-size: 16.5px;
  line-height: 1.85;
  color: var(--text-muted);
  white-space: pre-line;
  font-style: normal;
}

.note {
  margin: 20px 0 0;
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.8;
}

/* 轻轻浮现，像一个声音插进来。不做对撞、不做爆炸 */
@keyframes voice-in {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .voice {
    animation-duration: 0.01ms;
  }
}
</style>
