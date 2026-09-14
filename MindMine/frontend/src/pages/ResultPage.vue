<script setup lang="ts">
/**
 * Result —— Thinker → Contributor，也是整段旅程的首尾闭合。
 *
 * 开场说「你在知乎读过很多人的答案」，这里说「现在，加上你的」。
 * 身份翻转在这一屏完成。
 *
 * 合规红线：Phase 1 不得编造任何真实知乎统计（回答数、排名、阅读量），
 * 也不伪造发布能力。
 */
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'

const router = useRouter()
const store = useSessionStore()

const editing = ref(false)
const draft = ref('')
const copied = ref(false)
const publishNotice = ref(false)

onMounted(async () => {
  if (!store.sessionId) {
    router.replace('/')
    return
  }
  if (!store.composedAnswer) await store.compose()
  draft.value = store.composedAnswer
})

/** 把 Mock Composer 的极简 Markdown 渲染成段落 / 小标题 */
const blocks = computed(() => {
  const text = editing.value ? draft.value : store.composedAnswer
  return text
    .split('\n')
    .filter((l) => l.trim() !== '')
    .map((line) => {
      const bold = /^\*\*(.+)\*\*$/.exec(line.trim())
      return bold
        ? { type: 'heading' as const, text: bold[1] }
        : { type: 'para' as const, text: line }
    })
})

const charCount = computed(
  () => (editing.value ? draft.value : store.composedAnswer).length,
)

/**
 * 成文采用的那句话。
 *
 * 没有 V2 不等于用户没想清楚 —— 跳过追问、或看完追问仍然保留原判断，
 * 都是正当路径。所以这里回退到 V1，不能假设 V2 一定存在。
 */
const finalInsight = computed(() => {
  const ins = store.insightV2 ?? store.insightV1
  return ins?.user_edited_text || ins?.deep_insight || ''
})

function startEdit() {
  draft.value = store.composedAnswer
  editing.value = true
}

function saveEdit() {
  store.composedAnswer = draft.value
  editing.value = false
}

async function copyAnswer() {
  const text = editing.value ? draft.value : store.composedAnswer
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
  }
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

function publish() {
  // Phase 1：不伪造发布能力
  publishNotice.value = true
  setTimeout(() => (publishNotice.value = false), 5000)
}

function restart() {
  store.reset()
  router.push('/')
}
</script>

<template>
  <div class="result">
    <!-- 用户的观点在最上面，沿用 Insight 时的金竖线 —— 视觉上证明就是刚才那句 -->
    <section class="take">
      <p class="take-text">{{ finalInsight }}</p>
      <p class="origin">从「{{ store.insightV1?.surface_claim }}」开始</p>
    </section>

    <div class="rule" />

    <!-- 身份翻转的那一句 -->
    <section class="turn">
      <p class="turn-lead">这个问题，已经有很多人的答案。</p>
      <p class="turn-main">现在，加上你的。</p>
    </section>

    <article class="answer">
      <header class="answer-head">
        <span class="q">{{ store.question?.title }}</span>
        <span class="count">{{ charCount }} 字</span>
      </header>

      <div v-if="!editing" class="body">
        <template v-for="(b, i) in blocks" :key="i">
          <h3 v-if="b.type === 'heading'" class="h">{{ b.text }}</h3>
          <p v-else class="p">{{ b.text }}</p>
        </template>
      </div>

      <textarea v-else v-model="draft" class="editor" rows="20" />
    </article>

    <div class="actions">
      <template v-if="!editing">
        <button class="btn btn-secondary" @click="copyAnswer">
          {{ copied ? '已复制' : '复制回答' }}
        </button>
        <button class="btn btn-ghost" @click="startEdit">编辑</button>
        <button class="btn btn-primary" @click="publish">去知乎发布</button>
      </template>
      <template v-else>
        <button class="btn btn-primary" @click="saveEdit">保存</button>
        <button class="btn btn-ghost" @click="editing = false">取消</button>
      </template>
    </div>

    <p v-if="publishNotice" class="notice">
      真实知乎问题链接将在 Zhihu API 接入阶段启用。
    </p>

    <!-- 很轻的一句收尾。不解释、不总结、不夸奖 -->
    <p class="ending">
      曾经，你在这里读别人的答案。<br />
      现在，也会有人读到你的。
    </p>

    <button class="restart" @click="restart">再挖一个问题</button>

    <footer class="foot">演示数据 · 未接入真实知乎 API</footer>
  </div>
</template>

<style scoped>
.result {
  max-width: 720px;
  margin: 0 auto;
  padding: 72px 24px 80px;
}

.take {
  animation: fade-up 0.5s var(--ease) both;
}

.take-text {
  margin: 0;
  padding-left: 20px;
  border-left: 2px solid var(--insight);
  font-size: clamp(18px, 2.2vw, 21px);
  line-height: 1.75;
  font-weight: 500;
  color: var(--text);
}

.origin {
  margin: 16px 0 0 22px;
  font-size: 13px;
  color: var(--text-dim);
}

.rule {
  height: 1px;
  background: var(--border);
  margin: 46px 0;
}

.turn {
  text-align: center;
  margin-bottom: 44px;
  animation: fade-up 0.5s var(--ease) 0.1s both;
}

.turn-lead {
  margin: 0 0 8px;
  font-size: 15px;
  color: var(--text-dim);
}

.turn-main {
  margin: 0;
  font-size: clamp(21px, 2.6vw, 26px);
  font-weight: 650;
  letter-spacing: -0.01em;
  color: var(--text);
}

.answer {
  animation: fade-up 0.5s var(--ease) 0.16s both;
}

.answer-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 16px;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 28px;
}

.q {
  font-size: 14px;
  color: var(--text-muted);
  font-weight: 550;
}

.count {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-dim);
}

.h {
  margin: 32px 0 12px;
  font-size: 16px;
  font-weight: 650;
  color: var(--text);
}

.p {
  margin: 0 0 16px;
  font-size: 15.5px;
  line-height: 1.85;
  color: var(--text-muted);
}

.editor {
  width: 100%;
  resize: vertical;
  padding: 18px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border-strong);
  color: var(--text);
  font-size: 15px;
  line-height: 1.8;
}

.editor:focus {
  outline: none;
  border-color: var(--accent);
}

.actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 40px;
  padding-top: 28px;
  border-top: 1px solid var(--border);
}

.notice {
  margin: 16px 0 0;
  font-size: 13px;
  color: #ffb05c;
}

.ending {
  margin: 64px 0 0;
  text-align: center;
  font-size: 14px;
  line-height: 2;
  color: var(--text-dim);
}

.restart {
  display: block;
  margin: 40px auto 0;
  font-size: 13px;
  color: var(--text-dim);
}

.restart:hover {
  color: var(--text-muted);
}

.foot {
  margin-top: 48px;
  text-align: center;
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}
</style>
