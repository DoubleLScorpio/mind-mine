<script setup lang="ts">
/**
 * 先聊两句 —— 无知乎登录的 fallback。
 *
 * 不是表单，是一段很短的对话（最多 3 问）。
 * 问题必须帮助发现「用户有什么值得贡献的经验」，
 * 所以不问「你的职业是什么」，只问经历和教训。
 *
 * 2～3 轮后同样汇聚到 Mind Portrait。
 */
import { ref, watch, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { useOnboardingStore } from '@/stores/onboarding'

const router = useRouter()
const ob = useOnboardingStore()

const draft = ref('')
const inputEl = ref<HTMLTextAreaElement | null>(null)

/** Demo 推荐输入，降低演示时的打字负担 */
const DEMO_ANSWERS = [
  '大部分时间都在做前端，最近一年在自己学 AI 相关的东西。',
  '学新东西的时候总想一次学完，后来才知道不动手做项目根本记不住。',
  '会告诉当时的自己：别急着换方向，先把手上的事做出一个能拿得出手的结果。',
]

async function submit() {
  const text = draft.value.trim()
  if (!text || ob.loading) return
  draft.value = ''
  await ob.answerChat(text)
  await nextTick()
  inputEl.value?.focus()
}

async function finishNow() {
  const text = draft.value.trim()
  if (!text || ob.loading) return
  draft.value = ''
  await ob.finishChatEarly(text)
}

watch(
  () => ob.stage,
  (s) => {
    if (s === 'portrait') router.push('/portrait')
  },
)
</script>

<template>
  <div class="chat">
    <div class="inner">
      <!-- 已回答过的，留在上面作为痕迹 -->
      <div v-if="ob.chatHistory.length" class="said-list">
        <p v-for="(h, i) in ob.chatHistory" :key="i" class="said">{{ h }}</p>
      </div>

      <p :key="ob.chatStep" class="question">{{ ob.chatQuestion }}</p>

      <div class="composer">
        <textarea
          ref="inputEl"
          v-model="draft"
          class="input"
          rows="3"
          placeholder="随便说说就好…"
          :disabled="ob.loading"
          @keydown.enter.exact.prevent="submit"
        />
        <div class="row">
          <button
            class="hint"
            @click="draft = DEMO_ANSWERS[Math.min(ob.chatStep, DEMO_ANSWERS.length - 1)]"
          >
            试试：{{ DEMO_ANSWERS[Math.min(ob.chatStep, DEMO_ANSWERS.length - 1)] }}
          </button>
          <div class="acts">
            <button
              v-if="ob.chatStep >= 1"
              class="skip"
              :disabled="!draft.trim() || ob.loading"
              @click="finishNow"
            >
              就说到这
            </button>
            <button
              class="send"
              :disabled="!draft.trim() || ob.loading"
              @click="submit"
            >
              →
            </button>
          </div>
        </div>
      </div>

      <div v-if="ob.errorMessage" class="error-banner">
        {{ ob.errorMessage }}
      </div>
    </div>

    <footer class="foot">{{ ob.chatStep + 1 }} / 3</footer>
  </div>
</template>

<style scoped>
.chat {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px 24px 28px;
}

.inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  width: 100%;
  max-width: 560px;
}

.said-list {
  margin-bottom: 40px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 用户说过的话留在上面，淡一点 —— 它们是痕迹，不是聊天记录 */
.said {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-dim);
  padding-left: 14px;
  border-left: 1px solid var(--border);
}

.question {
  margin: 0 0 34px;
  font-size: clamp(21px, 2.8vw, 26px);
  line-height: 1.6;
  font-weight: 600;
  letter-spacing: -0.015em;
  animation: fade-up 0.5s var(--ease) both;
}

.composer {
  animation: fade-up 0.5s var(--ease) 0.12s both;
}

.input {
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

.input:focus {
  outline: none;
  border-bottom-color: var(--accent);
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

.skip {
  font-size: 13px;
  color: var(--text-dim);
}

.skip:hover:not(:disabled) {
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
  border-color: var(--accent);
  color: var(--accent);
}

.foot {
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}
</style>
