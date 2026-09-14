<script setup lang="ts">
/**
 * 一张思想碎片 —— 用户说过的话，被摘出来钉在屏幕上。
 *
 * 设计约束：
 * 1. label 是开放字符串，组件不得对具体分类做任何硬编码逻辑。
 *    未来 LLM 可以生成任意标签，这里只负责渲染。
 * 2. 视觉重点永远是 text（用户原话），label 是次要的、几乎要看不见的。
 * 3. 只有两行。没有描述、没有时间戳、没有图标、没有计数。
 */
import type { ThoughtFragment } from '@/types'

defineProps<{
  fragment: ThoughtFragment
  /** idle=散落 linked=已接入经历链 evidence=退为背景证据 */
  mode?: 'idle' | 'linked' | 'evidence'
  highlight?: boolean
}>()
</script>

<template>
  <div
    class="frag"
    :class="[`mode-${mode ?? 'idle'}`, { highlight }]"
    :data-fragment-id="fragment.id"
  >
    <div v-if="fragment.label" class="frag-label">{{ fragment.label }}</div>
    <div class="frag-text">{{ fragment.text }}</div>
  </div>
</template>

<style scoped>
.frag {
  display: inline-block;
  padding: 12px 16px 13px;
  border-radius: 10px;
  background: var(--surface-raised);
  border: 1px solid var(--border-strong);
  transition:
    border-color 0.3s var(--ease),
    background 0.3s var(--ease),
    transform 0.3s var(--ease),
    opacity 0.3s var(--ease);
}

.frag-label {
  font-size: 10px;
  letter-spacing: 0.16em;
  color: var(--text-dim);
  margin-bottom: 5px;
  user-select: none;
}

.frag-text {
  font-size: 16px;
  font-weight: 550;
  color: var(--text);
  line-height: 1.35;
  white-space: nowrap;
}

/* 已接入经历链：稍微立起来 */
.mode-linked {
  border-color: var(--border-strong);
  background: var(--surface-raised);
}

/* 观点出现后，碎片退为它背后的证据 */
.mode-evidence {
  opacity: 0.55;
}

.mode-evidence .frag-text {
  font-size: 14px;
}

/* 被点名的那两张 */
.highlight {
  border-color: rgba(255, 212, 121, 0.55);
  background: rgba(255, 212, 121, 0.07);
}

.highlight .frag-text {
  color: var(--insight);
}
</style>
