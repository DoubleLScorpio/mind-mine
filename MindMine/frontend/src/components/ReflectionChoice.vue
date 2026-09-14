<script setup lang="ts">
/**
 * 看完追问之后的三个选择。
 *
 * 关键：不立刻要求输入。先问「这让你想改刚才那句话吗？」
 * 三条路都必须真实可用，且都不制造负罪感 ——
 * 跳过不是放弃深度思考，保留不是没想清楚。
 */
defineProps<{
  loading?: boolean
}>()

const emit = defineEmits<{
  (e: 'add'): void
  (e: 'keep'): void
  (e: 'skip'): void
}>()
</script>

<template>
  <div class="choice">
    <p class="ask">这让你想改刚才那句话吗？</p>

    <div class="opts">
      <button class="opt primary" :disabled="loading" @click="emit('add')">
        有一点，我想补充
      </button>
      <button class="opt" :disabled="loading" @click="emit('keep')">
        没有，我还是这么想
      </button>
      <button class="opt quiet" :disabled="loading" @click="emit('skip')">
        跳过，直接写答案
      </button>
    </div>
  </div>
</template>

<style scoped>
.choice {
  max-width: 620px;
  margin: 0 auto;
  padding-top: 46px;
  animation: fade-up 0.5s var(--ease) 0.85s both;
}

.ask {
  margin: 0 0 26px;
  font-size: clamp(18px, 2.2vw, 21px);
  font-weight: 600;
  letter-spacing: -0.01em;
  color: var(--text);
}

/* 竖排，不是并列按钮组 —— 三个是并列的可能，不是主次动作 */
.opts {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.opt {
  padding: 11px 0;
  font-size: 16px;
  font-weight: 450;
  color: var(--text-muted);
  text-align: left;
  transition: color 0.16s var(--ease), transform 0.16s var(--ease);
}

.opt:hover:not(:disabled) {
  color: var(--text);
  transform: translateX(3px);
}

.opt.primary {
  color: var(--insight);
  font-weight: 550;
}

.opt.primary:hover:not(:disabled) {
  color: var(--insight);
}

/* 跳过不弱化到像被劝阻，只是安静一点 */
.opt.quiet {
  font-size: 14.5px;
  color: var(--text-dim);
}

@media (prefers-reduced-motion: reduce) {
  .opt:hover:not(:disabled) {
    transform: none;
  }
}
</style>
