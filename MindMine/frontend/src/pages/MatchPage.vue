<script setup lang="ts">
/**
 * Question Match —— 「也许，这题该你来答。」
 *
 * 这一屏要建立的是因果关系，不是推荐：
 *   不是「AI 推荐了一个热门问题」
 *   而是「这个问题，是因为我是谁、我经历过什么而找到我的」
 *
 * 所以「为什么是你？」必须引用 Mind Portrait 里真实存在的信息，
 * 而不是硬编码在这个组件里。
 *
 * 明确不展示：Match Score / 92% suitable / 多个 Badge / 推荐算法解释。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useOnboardingStore } from '@/stores/onboarding'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const ob = useOnboardingStore()
const store = useSessionStore()

const index = ref(0)
const starting = ref(false)

const current = computed(() => ob.questions[index.value] ?? null)

onMounted(() => {
  if (!ob.questions.length) router.replace('/know-me')
})

function next() {
  if (ob.questions.length < 2) return
  index.value = (index.value + 1) % ob.questions.length
}

async function claim() {
  const q = current.value
  if (!q || starting.value) return
  starting.value = true

  // Mining 之后的流程不变，这里把贡献画像转成会话所需的输入
  store.setProfile({
    source: 'manual',
    current_status: 'mid_career',
    domains: ob.profile?.recurring_interests.slice(0, 2) ?? [],
    share_preferences: ['experience'],
  })

  const s = await store.startSession(q.question_id)
  starting.value = false
  if (s) router.push(`/mine/${q.question_id}`)
}
</script>

<template>
  <div class="match">
    <!-- 很短的过渡：好。我大概知道该去哪里找了。 -->
    <div v-if="ob.stage === 'handoff'" class="handoff">
      <p class="h-line">好。</p>
      <p class="h-line delay">我大概知道该去哪里找了。</p>
      <p class="h-sub">去知乎里找几个，可能真的该你回答的问题。</p>
    </div>

    <template v-else-if="current">
      <div class="inner">
        <p class="lead">也许，这题该你来答。</p>

        <h1 :key="current.question_id" class="title" @click="claim">
          {{ current.title }}
        </h1>

        <div :key="current.question_id + '-why'" class="why">
          <p class="why-label">为什么是你？</p>
          <p class="why-text">{{ current.reason.from_you }}</p>
          <p class="why-text">{{ current.reason.therefore }}</p>
        </div>

        <button class="cta" :disabled="starting" @click="claim">
          {{ starting ? '正在开始…' : '这题，我来答' }}
          <span class="arrow">→</span>
        </button>

        <div class="bottom">
          <button class="swap" @click="next">换一个</button>
          <span class="count">{{ index + 1 }} / {{ ob.questions.length }}</span>
        </div>
      </div>

      <div v-if="store.errorMessage" class="error-banner">
        {{ store.errorMessage }}
      </div>
    </template>

    <footer class="foot">演示数据</footer>
  </div>
</template>

<style scoped>
.match {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px 28px;
}

/* ---------- 过渡 ---------- */

.handoff {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
}

.h-line {
  margin: 0 0 10px;
  font-size: clamp(22px, 2.9vw, 28px);
  font-weight: 600;
  letter-spacing: -0.015em;
  animation: fade-up 0.5s var(--ease) both;
}

.h-line.delay {
  animation-delay: 0.45s;
}

.h-sub {
  margin: 30px 0 0;
  font-size: 15px;
  color: var(--text-muted);
  animation: fade-up 0.5s var(--ease) 1.1s both;
}

/* ---------- 问题 ---------- */

.inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  width: 100%;
  max-width: 600px;
}

.lead {
  margin: 0 0 34px;
  font-size: 14px;
  color: var(--text-dim);
  animation: fade-up 0.45s var(--ease) both;
}

.title {
  margin: 0;
  font-size: clamp(27px, 4.2vw, 37px);
  line-height: 1.44;
  font-weight: 650;
  letter-spacing: -0.022em;
  cursor: pointer;
  animation: fade-up 0.5s var(--ease) 0.06s both;
}

.why {
  margin-top: 44px;
  padding-left: 18px;
  border-left: 1px solid var(--border-strong);
  animation: fade-up 0.5s var(--ease) 0.16s both;
}

.why-label {
  margin: 0 0 14px;
  font-size: 13px;
  font-weight: 600;
  color: var(--insight);
  letter-spacing: 0.02em;
}

.why-text {
  margin: 0 0 6px;
  font-size: 15.5px;
  line-height: 1.82;
  color: var(--text-muted);
}

.why-text:last-child {
  margin-bottom: 0;
  color: var(--text);
}

.cta {
  align-self: flex-start;
  margin-top: 46px;
  font-size: 18px;
  font-weight: 550;
  color: var(--insight);
  padding: 8px 0;
  animation: fade-up 0.45s var(--ease) 0.26s both;
}

.arrow {
  display: inline-block;
  margin-left: 4px;
  transition: transform 0.16s var(--ease);
}

.cta:hover .arrow {
  transform: translateX(4px);
}

.bottom {
  display: flex;
  align-items: center;
  gap: 20px;
  margin-top: 58px;
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
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}
</style>
