<script setup lang="ts">
/**
 * 用户选择「有一点，我想补充」之后才出现的输入框。
 *
 * 语义不是「回应挑战」，而是「你想给自己的观点补上什么」。
 * 所以文案明确降低门槛：不用写完整，想到什么说什么。
 */
import { ref, onMounted } from 'vue'

const props = defineProps<{
  loading?: boolean
  suggestion?: string
}>()

const emit = defineEmits<{
  (e: 'submit', text: string): void
  (e: 'back'): void
}>()

const draft = ref('')
const el = ref<HTMLTextAreaElement | null>(null)

onMounted(() => el.value?.focus())

function submit() {
  const t = draft.value.trim()
  if (!t || props.loading) return
  emit('submit', t)
}
</script>

<template>
  <div class="input-pane">
    <p class="title">你想补上什么？</p>
    <p class="sub">不用写完整。<br />想到什么，说什么。</p>

    <textarea
      ref="el"
      v-model="draft"
      class="area"
      rows="3"
      placeholder="随便说说就好…"
      :disabled="loading"
      @keydown.enter.exact.prevent="submit"
    />

    <div class="row">
      <button v-if="suggestion" class="hint" @click="draft = suggestion">
        试试：{{ suggestion }}
      </button>
      <span v-else />
      <div class="acts">
        <button class="back" :disabled="loading" @click="emit('back')">
          返回
        </button>
        <button
          class="send"
          :disabled="!draft.trim() || loading"
          @click="submit"
        >
          →
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.input-pane {
  max-width: 620px;
  margin: 0 auto;
  padding-top: 44px;
  animation: fade-up 0.42s var(--ease) both;
}

.title {
  margin: 0 0 10px;
  font-size: clamp(18px, 2.2vw, 21px);
  font-weight: 600;
  letter-spacing: -0.01em;
}

.sub {
  margin: 0 0 26px;
  font-size: 14px;
  line-height: 1.75;
  color: var(--text-dim);
}

.area {
  width: 100%;
  resize: none;
  padding: 12px 0;
  background: none;
  border: none;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  font-size: 16px;
  line-height: 1.7;
  transition: border-color 0.2s var(--ease);
}

.area:focus {
  outline: none;
  border-bottom-color: var(--insight);
}

.row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-top: 14px;
}

.hint {
  flex: 1;
  text-align: left;
  font-size: 12.5px;
  line-height: 1.55;
  color: var(--text-dim);
  opacity: 0.75;
}

.hint:hover {
  color: var(--accent-soft);
}

.acts {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.back {
  font-size: 13px;
  color: var(--text-dim);
}

.back:hover:not(:disabled) {
  color: var(--text-muted);
}

.send {
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: var(--surface-raised);
  border: 1px solid var(--border-strong);
  color: var(--text-muted);
  font-size: 16px;
  transition: all 0.16s var(--ease);
}

.send:not(:disabled):hover {
  border-color: var(--insight);
  color: var(--insight);
}
</style>
