<script setup lang="ts">
import { computed } from 'vue'
import type { KnowledgeState } from '@/types'

const props = defineProps<{
  knowledge: KnowledgeState
}>()

const groups = computed(() => [
  {
    key: 'facts',
    label: '已发现经历',
    icon: '◆',
    items: props.knowledge.facts,
  },
  {
    key: 'events',
    label: '关键事件',
    icon: '◇',
    items: props.knowledge.events.map((e) => `${e.event} → ${e.result}`),
  },
  {
    key: 'beliefs',
    label: '当时的信念',
    icon: '○',
    items: props.knowledge.beliefs,
  },
  {
    key: 'conflicts',
    label: '冲突',
    icon: '✕',
    items: props.knowledge.conflicts,
  },
  {
    key: 'reflections',
    label: '反思',
    icon: '◐',
    items: props.knowledge.reflections,
  },
  {
    key: 'candidate_insights',
    label: '潜在 Insight',
    icon: '✦',
    items: props.knowledge.candidate_insights,
  },
])

const total = computed(() =>
  groups.value.reduce((sum, g) => sum + g.items.length, 0),
)
</script>

<template>
  <aside class="panel">
    <div class="panel-head">
      <div class="section-label">MINDMINE</div>
      <h3 class="panel-title">
        Knowledge Panel
        <span class="count">{{ total }}</span>
      </h3>
      <p class="panel-hint">
        对话中被识别出的内容会实时出现在这里。<br />
        这些全部来自<strong>你说过的话</strong>。
      </p>
    </div>

    <div v-if="total === 0" class="empty">
      <div class="empty-mark">◈</div>
      <p>还没有内容。<br />开始回答左侧的问题吧。</p>
    </div>

    <div v-else class="groups">
      <section
        v-for="g in groups"
        v-show="g.items.length > 0"
        :key="g.key"
        class="group"
        :class="{ 'is-insight': g.key === 'candidate_insights' }"
      >
        <div class="group-head">
          <span class="group-icon">{{ g.icon }}</span>
          <span class="group-label">{{ g.label }}</span>
          <span class="group-count">{{ g.items.length }}</span>
        </div>
        <ul class="items">
          <li v-for="(item, i) in g.items" :key="i" class="item fade-up">
            {{ item }}
          </li>
        </ul>
      </section>
    </div>
  </aside>
</template>

<style scoped>
.panel {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 22px;
  position: sticky;
  top: 24px;
  max-height: calc(100vh - 48px);
  overflow-y: auto;
}

.panel-head {
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 18px;
}

.panel-title {
  margin: 8px 0 10px;
  font-size: 18px;
  font-weight: 650;
  display: flex;
  align-items: center;
  gap: 10px;
}

.count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 24px;
  height: 24px;
  padding: 0 7px;
  border-radius: 999px;
  background: var(--accent-dim);
  border: 1px solid rgba(110, 139, 255, 0.28);
  color: var(--accent-soft);
  font-size: 12px;
  font-weight: 700;
}

.panel-hint {
  margin: 0;
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-dim);
}

.panel-hint strong {
  color: var(--text-muted);
  font-weight: 600;
}

.empty {
  padding: 48px 12px;
  text-align: center;
  color: var(--text-dim);
  font-size: 13.5px;
  line-height: 1.7;
}

.empty-mark {
  font-size: 30px;
  opacity: 0.28;
  margin-bottom: 14px;
}

.groups {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.group-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.group-icon {
  color: var(--accent);
  font-size: 12px;
}

.group-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--text-muted);
  text-transform: uppercase;
}

.group-count {
  font-size: 11px;
  color: var(--text-dim);
}

.items {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.item {
  padding: 11px 13px;
  border-radius: var(--radius-sm);
  background: var(--bg-soft);
  border: 1px solid var(--border);
  border-left: 2px solid var(--border-strong);
  font-size: 13.5px;
  line-height: 1.55;
  color: var(--text-muted);
}

.is-insight .group-icon {
  color: var(--insight);
}

.is-insight .item {
  background: var(--insight-dim);
  border-color: rgba(255, 212, 121, 0.2);
  border-left-color: var(--insight);
  color: #ffe4ae;
}
</style>
