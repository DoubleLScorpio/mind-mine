<script setup lang="ts">
/**
 * Mind Portrait —— 「我好像看到这样一个你。」
 *
 * 这是新的第一个产品 Moment。它必须像「被理解」，
 * 而不是 AI 标签分类。所以：
 *   - 没有字段名、没有完成度、没有 Accuracy
 *   - 全部是自然语言，逐段浮现
 *   - 语气保持不确定：我好像 / 你似乎 / 可能
 *
 * 最后把解释权交还给用户：像我吗？
 * 不像的话，用自然语言告诉我 —— 不是重新出现表单。
 */
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useOnboardingStore } from '@/stores/onboarding'

const router = useRouter()
const ob = useOnboardingStore()

/** 逐段浮现的进度 */
const shown = ref(0)
const showAsk = ref(false)

const correcting = ref(false)
const draft = ref('')

const DEMO_CORRECTION =
  '我虽然最近看很多 AI，但其实只是为了转行。真正比较有经验的是前端开发，而且我对职场选择也挺有感触。'

onMounted(() => {
  if (!ob.portrait) {
    router.replace('/know-me')
    return
  }
  play()
})

/** 画像被纠正后重新浮现 */
watch(
  () => ob.portrait,
  () => {
    if (ob.portrait) play()
  },
)

async function play() {
  shown.value = 0
  showAsk.value = false
  const total = (ob.portrait?.paragraphs.length ?? 0) + 2 // + topics + core
  for (let i = 0; i < total; i++) {
    await sleep(i === 0 ? 420 : 900)
    shown.value = i + 1
  }
  await sleep(800)
  showAsk.value = true
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms))
}

/** 点击跳过：直接显示完整画像 */
function skip() {
  if (showAsk.value) return
  shown.value = (ob.portrait?.paragraphs.length ?? 0) + 2
  showAsk.value = true
}

function startCorrect() {
  correcting.value = true
  draft.value = ''
}

async function submitCorrection() {
  const text = draft.value.trim()
  if (!text || ob.loading) return
  await ob.correct(text)
  correcting.value = false
  draft.value = ''
}

async function looksLikeMe() {
  await ob.findQuestions()
  router.push('/match')
}
</script>

<template>
  <div class="portrait" @click="skip">
    <!-- ========== 自然语言纠正 ========== -->
    <div v-if="correcting" class="inner correct" @click.stop>
      <h2 class="c-title">哪里不像你？</h2>
      <p class="c-sub">直接告诉我就好。</p>

      <textarea
        v-model="draft"
        class="c-input"
        rows="4"
        placeholder="比如：我其实没那么懂 AI，我真正比较有经验的是前端……"
        :disabled="ob.loading"
      />

      <div class="c-row">
        <button class="hint" @click="draft = DEMO_CORRECTION">
          试试：{{ DEMO_CORRECTION }}
        </button>
        <div class="c-acts">
          <button class="back" @click="correcting = false">算了</button>
          <button
            class="send"
            :disabled="!draft.trim() || ob.loading"
            @click="submitCorrection"
          >
            →
          </button>
        </div>
      </div>
    </div>

    <!-- ========== 我眼中的你 ========== -->
    <div v-else class="inner">
      <!-- 纠正之后的开场：「明白了。」 -->
      <p v-if="ob.portrait?.ack" class="ack">{{ ob.portrait.ack }}</p>
      <p v-else-if="ob.portrait?.lead" class="lead">{{ ob.portrait.lead }}</p>

      <div class="paras">
        <p
          v-for="(p, i) in ob.portrait?.paragraphs ?? []"
          v-show="i < shown"
          :key="p"
          class="para"
        >
          {{ p }}
        </p>
      </div>

      <div
        v-show="shown > (ob.portrait?.paragraphs.length ?? 0)"
        class="topics-block"
      >
        <p class="t-lead">你似乎特别容易对这些事情有话说：</p>
        <div class="topics">
          <span
            v-for="(t, i) in ob.portrait?.topics ?? []"
            :key="t"
            class="topic"
            :style="{ animationDelay: `${i * 110}ms` }"
          >
            {{ t }}
          </span>
        </div>
      </div>

      <!-- 视觉权重最高的一段 -->
      <div
        v-show="shown > (ob.portrait?.paragraphs.length ?? 0) + 1"
        class="core"
      >
        <p class="core-lead">{{ ob.portrait?.core_lead }}</p>
        <p class="core-line">{{ ob.portrait?.core_line }}</p>
      </div>

      <!-- 解释权交还给用户 -->
      <div v-show="showAsk" class="ask" @click.stop>
        <p class="ask-title">
          {{ ob.profile?.correction_count ? '这次更像你吗？' : '像我吗？' }}
        </p>
        <div class="ask-acts">
          <button class="btn btn-insight" :disabled="ob.loading" @click="looksLikeMe">
            {{
              ob.loading
                ? '…'
                : ob.profile?.correction_count
                  ? '对，这更像我 →'
                  : '挺像的 →'
            }}
          </button>
          <button class="btn btn-ghost" @click="startCorrect">有一点不对</button>
        </div>
      </div>

      <div v-if="ob.errorMessage" class="error-banner">
        {{ ob.errorMessage }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.portrait {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 56px 24px 28px;
}

.inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  width: 100%;
  max-width: 600px;
}

.lead,
.ack {
  margin: 0 0 38px;
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-dim);
  animation: fade-up 0.5s var(--ease) both;
}

.ack {
  font-size: 17px;
  color: var(--text-muted);
  font-weight: 550;
}

.paras {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

/* 人物描述。字号大，因为这是「我眼中的你」，不是资料 */
.para {
  margin: 0;
  font-size: clamp(20px, 2.6vw, 25px);
  line-height: 1.68;
  font-weight: 550;
  letter-spacing: -0.015em;
  color: var(--text);
  animation: fade-up 0.65s var(--ease) both;
}

.topics-block {
  margin-top: 40px;
  animation: fade-up 0.6s var(--ease) both;
}

.t-lead {
  margin: 0 0 16px;
  font-size: 14.5px;
  color: var(--text-muted);
}

.topics {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 20px;
}

/* 不是标签墙：无边框、无底色，只是被点到的词 */
.topic {
  font-size: 17px;
  font-weight: 550;
  color: var(--accent-soft);
  animation: fade-up 0.5s var(--ease) both;
}

/* ---------- 视觉权重最高的一段 ---------- */

.core {
  margin-top: 52px;
  padding-left: 20px;
  border-left: 2px solid var(--insight);
  animation: fade-up 0.7s var(--ease) both;
}

.core-lead {
  margin: 0 0 12px;
  font-size: 15px;
  line-height: 1.75;
  color: var(--text-muted);
}

.core-line {
  margin: 0;
  font-size: clamp(20px, 2.7vw, 26px);
  line-height: 1.6;
  font-weight: 650;
  letter-spacing: -0.015em;
  color: var(--insight);
}

/* ---------- 像我吗 ---------- */

.ask {
  margin-top: 64px;
  padding-top: 34px;
  border-top: 1px solid var(--border);
  animation: fade-up 0.5s var(--ease) both;
}

.ask-title {
  margin: 0 0 22px;
  font-size: clamp(19px, 2.4vw, 23px);
  font-weight: 650;
  letter-spacing: -0.01em;
}

.ask-acts {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

/* ---------- 自然语言纠正 ---------- */

.correct {
  animation: fade-up 0.4s var(--ease) both;
}

.c-title {
  margin: 0 0 10px;
  font-size: clamp(22px, 2.8vw, 27px);
  font-weight: 650;
  letter-spacing: -0.015em;
}

.c-sub {
  margin: 0 0 32px;
  font-size: 15px;
  color: var(--text-muted);
}

.c-input {
  width: 100%;
  resize: none;
  padding: 14px 0;
  background: none;
  border: none;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  font-size: 16px;
  line-height: 1.75;
  transition: border-color 0.2s var(--ease);
}

.c-input:focus {
  outline: none;
  border-bottom-color: var(--insight);
}

.c-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 18px;
  margin-top: 16px;
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

.c-acts {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.back {
  font-size: 13px;
  color: var(--text-dim);
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

.foot {
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}

@media (prefers-reduced-motion: reduce) {
  .para,
  .topic,
  .core,
  .ask {
    animation-duration: 0.01ms;
  }
}
</style>
