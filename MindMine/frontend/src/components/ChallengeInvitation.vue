<script setup lang="ts">
/**
 * 观点压力测试的邀请。
 *
 * 用户确认观点之后不直接进入追问 —— 先让他的观点保持视觉中心，
 * 然后问他要不要看一眼别人会怎么追问。
 *
 * 两条路都必须是完整可用路径。「直接写成答案」不是退出，
 * 是一个正当选择：Challenge 是增强体验，不是必经流程。
 */
defineProps<{
  take: string
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'view'): void
  (e: 'skip'): void
}>()
</script>

<template>
  <div class="invite">
    <!-- 视觉主角始终是用户自己的观点 -->
    <div class="take-block">
      <p class="take-lead">你想说的是</p>
      <p class="take">{{ take }}</p>
    </div>

    <div class="offer">
      <p class="ready">这个观点已经可以成为答案。</p>
      <p class="ask">
        不过，在写下来之前——<br />
        要不要看看，知乎上有人会怎么追问你？
      </p>

      <div class="acts">
        <button class="btn btn-insight" :disabled="loading" @click="emit('view')">
          {{ loading ? '…' : '看看 →' }}
        </button>
        <button class="btn btn-ghost" :disabled="loading" @click="emit('skip')">
          直接写成答案
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.invite {
  max-width: 620px;
  margin: 0 auto;
  padding: 20px 0 40px;
}

.take-block {
  animation: fade-up 0.5s var(--ease) both;
}

.take-lead {
  margin: 0 0 16px;
  font-size: 13px;
  letter-spacing: 0.02em;
  color: var(--text-dim);
}

/* 用户的观点，沿用 Insight 的金竖线 —— 视觉上证明就是刚才那句 */
.take {
  margin: 0;
  padding-left: 20px;
  border-left: 2px solid var(--insight);
  font-size: clamp(19px, 2.4vw, 23px);
  line-height: 1.72;
  font-weight: 550;
  color: var(--text);
  letter-spacing: -0.01em;
}

.offer {
  margin-top: 58px;
  padding-top: 34px;
  border-top: 1px solid var(--border);
  animation: fade-up 0.5s var(--ease) 0.5s both;
}

.ready {
  margin: 0 0 18px;
  font-size: 15px;
  color: var(--text-muted);
}

.ask {
  margin: 0 0 32px;
  font-size: clamp(17px, 2.1vw, 20px);
  line-height: 1.75;
  font-weight: 550;
  color: var(--text);
}

.acts {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}
</style>
