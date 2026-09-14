<script setup lang="ts">
/**
 * Discovery —— Reader → Protagonist 的翻转点。
 *
 * 让用户觉得「该我回答」的唯一手段不是夸这个问题有多好，
 * 而是引用用户自己刚才填的那句自我介绍。
 *
 * 所以一屏只放一个问题。三张卡并排 = 比价心态；
 * 一张卡 = 认领心态。这个差别决定了整个产品的入口体验。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import { api, ApiError } from '@/api/client'
import type { QuestionCard } from '@/types'

const router = useRouter()
const store = useSessionStore()

const questions = ref<QuestionCard[]>([])
const index = ref(0)
const loading = ref(true)
const starting = ref(false)
const error = ref('')

const current = computed<QuestionCard | null>(
  () => questions.value[index.value] ?? null,
)

/** why_fits 第二行是回指用户自我介绍的那句，单独排版 */
const whyLines = computed(() => (current.value?.why_fits ?? '').split('\n'))

onMounted(async () => {
  if (!store.profile) {
    router.replace('/')
    return
  }
  try {
    const r = await api.listQuestions(store.profile)
    questions.value = r.items
  } catch (e) {
    error.value =
      e instanceof ApiError ? e.message : '加载问题失败，请确认后端已启动。'
  } finally {
    loading.value = false
  }
})

function next() {
  if (questions.value.length < 2) return
  index.value = (index.value + 1) % questions.value.length
}

async function claim() {
  const q = current.value
  if (!q || starting.value) return
  starting.value = true
  const s = await store.startSession(q.question_id)
  starting.value = false
  if (s) router.push(`/mine/${q.question_id}`)
}
</script>

<template>
  <div class="discovery">
    <div v-if="loading" class="state">正在找问题…</div>
    <div v-else-if="error" class="state error-banner">{{ error }}</div>

    <template v-else-if="current">
      <p class="lead">你的经历里，可能藏着这个问题的答案</p>

      <!-- 整块可点，CTA 只是它的视觉落点 -->
      <div class="q" @click="claim">
        <h1 :key="current.question_id" class="q-title">{{ current.title }}</h1>

        <div class="rule" />

        <div :key="current.question_id + '-why'" class="why">
          <p v-for="(line, i) in whyLines" :key="i" :class="{ personal: i > 0 }">
            {{ line }}
          </p>
        </div>

        <button class="cta" :disabled="starting" @click.stop="claim">
          {{ starting ? '正在开始…' : '这个，我有话说' }}
          <span class="arrow">→</span>
        </button>
      </div>

      <div class="bottom">
        <button class="swap" @click="next">换一个</button>
        <span class="count">{{ index + 1 }} / {{ questions.length }}</span>
      </div>
    </template>

    <div v-if="store.errorMessage" class="error-banner">
      {{ store.errorMessage }}
    </div>
  </div>
</template>

<style scoped>
.discovery {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px 28px;
  text-align: center;
}

.state {
  color: var(--text-dim);
  font-size: 15px;
}

.lead {
  margin: 0 0 40px;
  font-size: 14px;
  color: var(--text-dim);
  letter-spacing: 0.02em;
  animation: fade-up 0.4s var(--ease) both;
}

.q {
  max-width: 640px;
  cursor: pointer;
}

.q-title {
  margin: 0;
  font-size: clamp(27px, 4.2vw, 38px);
  line-height: 1.42;
  font-weight: 650;
  letter-spacing: -0.02em;
  animation: fade-up 0.45s var(--ease) both;
}

.rule {
  width: 46px;
  height: 1px;
  background: var(--border-strong);
  margin: 30px auto;
}

.why {
  animation: fade-up 0.45s var(--ease) 0.08s both;
}

.why p {
  margin: 0;
  font-size: 16px;
  line-height: 1.78;
  color: var(--text-muted);
}

/* 回指用户自我介绍的那句 —— 这是「为什么该你回答」的全部力量所在 */
.why p.personal {
  margin-top: 6px;
  color: var(--text);
}

.cta {
  margin-top: 44px;
  font-size: 18px;
  font-weight: 550;
  color: var(--insight);
  padding: 8px 0;
}

.arrow {
  display: inline-block;
  margin-left: 4px;
  transition: transform 0.16s var(--ease);
}

.q:hover .arrow,
.cta:hover .arrow {
  transform: translateX(4px);
}

.bottom {
  margin-top: 64px;
  display: flex;
  align-items: center;
  gap: 20px;
  font-size: 13px;
  color: var(--text-dim);
}

.swap {
  font-size: 13px;
  color: var(--text-dim);
  padding: 4px 0;
}

.swap:hover {
  color: var(--text-muted);
}

.count {
  opacity: 0.6;
}

.foot {
  position: absolute;
  bottom: 22px;
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}
</style>
