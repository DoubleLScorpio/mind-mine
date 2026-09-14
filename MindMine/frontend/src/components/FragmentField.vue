<script setup lang="ts">
/**
 * 碎片场 —— 用户思想的空间。
 *
 * 两种布局：
 *   scattered  访谈中。碎片轻微错落地漂在页面上。
 *              错落 = 尚未整理的素材；对齐 = 已归档的记录。这个差别很重要。
 *   chain      Insight 时。同一批 DOM 节点移动到中央，连成一条经历链。
 *
 * 关键实现：布局切换时不重建节点。用户能认出「这就是我刚才说的那张」，
 * 观点才像是从他的经历里长出来的。
 */
import { ref, computed, watch, nextTick, onMounted, onBeforeUnmount } from 'vue'
import ThoughtFragmentCard from './ThoughtFragment.vue'
import type { FragmentLink, ThoughtFragment } from '@/types'

const props = defineProps<{
  fragments: ThoughtFragment[]
  links: FragmentLink[]
  layout: 'scattered' | 'chain'
  /** 画连接线 */
  showLinks?: boolean
  /** 碎片退为背景证据 */
  evidence?: boolean
  /** 需要被点名的碎片 id */
  highlightIds?: string[]
}>()

const root = ref<HTMLElement | null>(null)
const lines = ref<
  { id: string; x1: number; y1: number; x2: number; y2: number }[]
>([])
const svgSize = ref({ w: 0, h: 0 })

/** 散落布局：固定的小偏移，保证每次进入位置一致，不随机跳动 */
const SCATTER_OFFSETS = [
  { x: 0, y: 0 },
  { x: 34, y: 10 },
  { x: 8, y: 6 },
  { x: 42, y: 4 },
  { x: 16, y: 12 },
]

function scatterStyle(i: number) {
  const o = SCATTER_OFFSETS[i % SCATTER_OFFSETS.length]
  return { transform: `translate(${o.x}px, ${o.y}px)` }
}

/**
 * 经历链布局。
 * 用 grid 的显式定位，把碎片排成「因 → 果」的形状，而不是列表或网格。
 * 布局本身要能读出关系：主线横向推进，代价垂在下方。
 */
const chainPos: Record<string, { col: number; row: number }> = {
  f_promise: { col: 1, row: 1 },
  f_choice: { col: 2, row: 1 },
  f_outcome: { col: 3, row: 1 },
  f_cost: { col: 2, row: 2 },
  f_reflect: { col: 2, row: 3 },
}

function chainStyle(f: ThoughtFragment, i: number) {
  const p = chainPos[f.id]
  if (p) return { gridColumn: String(p.col), gridRow: String(p.row) }
  // 未知碎片（LLM 阶段可能出现任意 id）：顺次铺开，不报错
  return { gridColumn: String((i % 3) + 1), gridRow: String(Math.floor(i / 3) + 1) }
}

const isChain = computed(() => props.layout === 'chain')

/** 测量各碎片位置，生成连接线坐标 */
async function measure() {
  await nextTick()
  const el = root.value
  if (!el || !isChain.value) {
    lines.value = []
    return
  }

  const box = el.getBoundingClientRect()
  svgSize.value = { w: box.width, h: box.height }

  const rectOf = (id: string) => {
    const node = el.querySelector<HTMLElement>(`[data-fragment-id="${id}"]`)
    if (!node) return null
    const r = node.getBoundingClientRect()
    return {
      left: r.left - box.left,
      right: r.right - box.left,
      top: r.top - box.top,
      bottom: r.bottom - box.top,
      cx: r.left - box.left + r.width / 2,
      cy: r.top - box.top + r.height / 2,
    }
  }

  const out: typeof lines.value = []
  for (const link of props.links) {
    const a = rectOf(link.from_id)
    const b = rectOf(link.to_id)
    if (!a || !b) continue

    // 同一行 → 水平连接；否则垂直连接
    const sameRow = Math.abs(a.cy - b.cy) < 24
    out.push(
      sameRow
        ? { id: `${link.from_id}-${link.to_id}`, x1: a.right + 6, y1: a.cy, x2: b.left - 6, y2: b.cy }
        : { id: `${link.from_id}-${link.to_id}`, x1: a.cx, y1: a.bottom + 6, x2: b.cx, y2: b.top - 6 },
    )
  }
  lines.value = out
}

watch(() => [props.layout, props.fragments.length, props.links.length], measure)

let ro: ResizeObserver | null = null
onMounted(() => {
  measure()
  if (typeof ResizeObserver !== 'undefined' && root.value) {
    ro = new ResizeObserver(() => measure())
    ro.observe(root.value)
  }
})
onBeforeUnmount(() => ro?.disconnect())
</script>

<template>
  <div ref="root" class="field" :class="isChain ? 'is-chain' : 'is-scattered'">
    <!-- 连接线。关系是被建立的，不是被展示的，所以逐条画出来 -->
    <svg
      v-if="showLinks && lines.length"
      class="links"
      :viewBox="`0 0 ${svgSize.w} ${svgSize.h}`"
      :width="svgSize.w"
      :height="svgSize.h"
    >
      <line
        v-for="(l, i) in lines"
        :key="l.id"
        :x1="l.x1"
        :y1="l.y1"
        :x2="l.x2"
        :y2="l.y2"
        class="link-line"
        :style="{ animationDelay: `${i * 220}ms` }"
      />
    </svg>

    <ThoughtFragmentCard
      v-for="(f, i) in fragments"
      :key="f.id"
      :fragment="f"
      :mode="evidence ? 'evidence' : isChain ? 'linked' : 'idle'"
      :highlight="highlightIds?.includes(f.id)"
      class="slot-item"
      :style="isChain ? chainStyle(f, i) : scatterStyle(i)"
    />
  </div>
</template>

<style scoped>
.field {
  position: relative;
  transition: all 0.6s var(--ease);
}

/* 访谈中：轻微错落地漂着，没有容器、没有标题、没有计数 */
.is-scattered {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 16px;
}

.is-scattered .slot-item {
  animation: frag-in 0.36s var(--ease) backwards;
}

/* Insight：排成能读出因果的形状 */
.is-chain {
  display: grid;
  grid-template-columns: repeat(3, auto);
  justify-content: center;
  align-items: center;
  justify-items: center;
  gap: 26px 44px;
}

.slot-item {
  transition:
    transform 0.72s var(--ease),
    opacity 0.5s var(--ease);
}

.links {
  position: absolute;
  inset: 0;
  pointer-events: none;
  overflow: visible;
}

.link-line {
  stroke: var(--border-strong);
  stroke-width: 1.5;
  stroke-dasharray: 200;
  stroke-dashoffset: 200;
  animation: draw 0.42s var(--ease) forwards;
}

@keyframes draw {
  to {
    stroke-dashoffset: 0;
  }
}

@keyframes frag-in {
  from {
    opacity: 0;
    transform: scale(0.94) translateY(6px);
  }
}

@media (max-width: 900px) {
  .is-chain {
    grid-template-columns: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .slot-item,
  .field {
    transition-duration: 0.01ms;
  }
  .link-line {
    animation-duration: 0.01ms;
  }
}
</style>
