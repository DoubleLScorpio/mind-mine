<script setup lang="ts">
/**
 * MinePage —— Protagonist → Thinker 的全过程。
 *
 * 核心视觉原则：The more you speak, the less AI you see.
 * 用户说得越多，访谈区越退后，他自己的思想碎片占据越多空间。
 * 到 Insight 时刻，屏幕上只剩他说过的话。
 *
 * 关键实现：这一页没有页面切换、没有 Modal。
 * 访谈区在 Insight 时不卸载，只是 blur 并降到极低透明度留在原位 ——
 * 这样观点才像是从他刚才那段对话里长出来的。
 */
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import FragmentField from '@/components/FragmentField.vue'
import InsightReveal from '@/components/InsightReveal.vue'
import InsightRewrite from '@/components/InsightRewrite.vue'
import ChallengeInvitation from '@/components/ChallengeInvitation.vue'
import CommunityQuestion from '@/components/CommunityQuestion.vue'
import ReflectionChoice from '@/components/ReflectionChoice.vue'
import ReflectionInput from '@/components/ReflectionInput.vue'

const router = useRouter()
const store = useSessionStore()

const draft = ref('')
const editing = ref(false)
const editDraft = ref('')
const chatBody = ref<HTMLElement | null>(null)

/** Demo 推荐输入：降低演示时的打字负担，用户仍可自由输入 */
const DEMO_INPUTS = [
  '别太相信领导画饼。',
  '之前领导跟我说年底会给我升职，所以我拒绝了另一个涨薪30%的Offer。',
  '因为领导之前对我还不错，而且说得很具体，我觉得留下来长期发展更好。',
  '年底没有升职，领导只说再等等。那个Offer也已经没了。',
  '我不是错在相信领导，而是把一个没有保证的未来机会，当成了已经确定的东西。',
]

const DEMO_CHALLENGE_REPLY =
  '值得押注的机会确实存在，但我会要求它有明确的兑现条件和时间点，而不是只有一句口头承诺。'

const suggestion = computed(() => {
  const i = store.userTurnCount
  return i < DEMO_INPUTS.length ? DEMO_INPUTS[i] : null
})

const stage = computed(() => {
  const s = store.state
  if (s === 'INSIGHT') return invited.value ? 'invite' : 'reveal'
  if (s === 'CHALLENGE') return 'reflect'
  if (s === 'REFINEMENT' || s === 'COMPOSE' || s === 'DONE') return 'refine'
  return 'interview'
})

/** AI 退场的程度。用户说得越多，访谈区越轻 */
const chatOpacity = computed(() => 1 - store.mindWeight * 0.45)
const chatScale = computed(() => 1 - store.mindWeight * 0.03)

/** 用户自己的观点。它在整段压力测试里始终是视觉主角 */
const yourTake = computed(
  () => store.insightV1?.user_edited_text || store.insightV1?.deep_insight || '',
)

/** Ownership 之后才允许成文 */
const ownDraft = ref('')
const ownEditing = ref(false)

/**
 * 观点压力测试的本地流程：
 *   invited   已认下观点，正在被问「要不要看看别人会怎么追问」
 *   adding    选择了「有一点，我想补充」，输入框才出现
 *   kept      选择了「我还是这么想」，给一句很轻的确认
 */
const invited = ref(false)
const adding = ref(false)
const kept = ref(false)

onMounted(() => {
  if (!store.sessionId) router.replace('/')
})

async function scrollToBottom() {
  await nextTick()
  const el = chatBody.value
  if (el) el.scrollTop = el.scrollHeight
}

watch(() => store.messages.length, scrollToBottom)

async function send() {
  const text = draft.value.trim()
  if (!text || store.loading) return
  draft.value = ''
  await store.sendMessage(text)
  await scrollToBottom()
}

/**
 * 用户认下这句话。先不进入追问 —— 让他的观点保持视觉中心，
 * 然后问他要不要看一眼别人会怎么追问。
 */
function confirmInsight() {
  if (editing.value) return
  invited.value = true
}

/** 「看看 →」：这时才真正拉取社区的追问 */
async function viewChallenge() {
  await store.confirmInsight()
}

/** 「直接写成答案」/「跳过」：完整可用路径，不弹二次确认 */
async function skipToAnswer() {
  const r = await store.skipChallenge()
  if (!r) return
  const c = await store.compose()
  if (c) router.push(`/result/${store.sessionId}`)
}

/**
 * 「没有，我还是这么想」：不强制生成 V2。
 *
 * 先显示确认语再改状态 —— store.keepTake() 会把 state 推到 COMPOSE，
 * 那时 reflect 段落已卸载，确认语就来不及被看到了。
 */
async function keepMyTake() {
  if (store.loading) return
  kept.value = true
  // 一句很轻的确认，让用户看见
  await new Promise((res) => setTimeout(res, 1500))
  const r = await store.keepTake()
  if (!r) {
    kept.value = false
    return
  }
  const c = await store.compose()
  if (c) router.push(`/result/${store.sessionId}`)
}

function startEdit(text: string) {
  editDraft.value = text
  editing.value = true
}

async function saveEdit() {
  const t = editDraft.value.trim()
  if (!t) return
  await store.editInsight(t)
  editing.value = false
}

async function submitChallenge(text: string) {
  const t = text.trim()
  if (!t || store.loading) return
  await store.respondChallenge(t)
  adding.value = false
}

async function claimIt() {
  await store.claimOwnership()
  const r = await store.compose()
  if (r) router.push(`/result/${store.sessionId}`)
}

function startOwnEdit() {
  ownDraft.value = store.insightV2?.deep_insight ?? ''
  ownEditing.value = true
}

async function saveOwnEdit() {
  const t = ownDraft.value.trim()
  if (!t) return
  await store.claimOwnership(t)
  ownEditing.value = false
  const r = await store.compose()
  if (r) router.push(`/result/${store.sessionId}`)
}
</script>

<template>
  <div class="mine" :class="`stage-${stage}`">
    <!-- 问题常驻。用户始终知道自己在回答什么，不需要状态机进度条 -->
    <header class="topbar">
      <span class="mark">◈</span>
      <h1 class="q">{{ store.question?.title }}</h1>
    </header>

    <div v-if="store.errorMessage" class="err">{{ store.errorMessage }}</div>

    <!-- ============ 访谈 + 碎片（同一个空间） ============ -->
    <div v-if="stage === 'interview' || stage === 'reveal'" class="space">
      <!-- Insight 时这一块不卸载，只是退到背景里 -->
      <section
        class="talk"
        :class="{ receded: stage === 'reveal' }"
        :style="
          stage === 'interview'
            ? { opacity: chatOpacity, transform: `scale(${chatScale})` }
            : undefined
        "
      >
        <div ref="chatBody" class="talk-body">
          <div v-for="(m, i) in store.messages" :key="i" class="turn" :class="m.role">
            <span v-if="m.role === 'ai'" class="ai-mark">◈</span>
            <p class="said">{{ m.content }}</p>
          </div>
          <div v-if="store.loading" class="turn ai">
            <span class="ai-mark">◈</span>
            <p class="said thinking"><span /><span /><span /></p>
          </div>
        </div>

        <div v-if="stage === 'interview'" class="composer">
          <div class="input-row">
            <textarea
              v-model="draft"
              class="input"
              rows="2"
              placeholder="说说你的真实经历…"
              :disabled="store.loading"
              @keydown.enter.exact.prevent="send"
            />
            <button
              class="send"
              :disabled="!draft.trim() || store.loading"
              @click="send"
            >
              →
            </button>
          </div>
          <button v-if="suggestion" class="hint" @click="draft = suggestion">
            试试：{{ suggestion }}
          </button>
        </div>
      </section>

      <!-- 访谈中：碎片散落在右侧留白里，没有容器、没有标题、没有计数 -->
      <aside v-if="stage === 'interview'" class="mind">
        <FragmentField
          :fragments="store.fragments"
          :links="store.fragmentLinks"
          layout="scattered"
        />
      </aside>

      <!-- Insight：同一批碎片移到中央，连成经历链 -->
      <InsightReveal
        v-if="stage === 'reveal' && !editing"
        class="overlay"
        :phase="store.revealPhase"
        :fragments="store.fragments"
        :links="store.fragmentLinks"
        :insight="store.insightV1"
        :loading="store.loading"
        @skip="store.advanceReveal()"
        @confirm="confirmInsight"
        @edit="startEdit"
      />

      <!-- 用户改写自己的观点 -->
      <div v-if="stage === 'reveal' && editing" class="overlay edit-pane">
        <p class="edit-label">用你自己的话说</p>
        <textarea v-model="editDraft" class="edit-area" rows="3" />
        <div class="edit-actions">
          <button class="btn btn-insight" @click="saveEdit">就这么说</button>
          <button class="btn btn-ghost" @click="editing = false">算了</button>
        </div>
      </div>
    </div>

    <!-- ============ 要不要看一眼别人会怎么追问 ============ -->
    <section v-else-if="stage === 'invite'" class="pressure">
      <ChallengeInvitation
        :take="yourTake"
        :loading="store.loading"
        @view="viewChallenge"
        @skip="skipToAnswer"
      />
    </section>

    <!-- ============ 一次插进来的追问 ============ -->
    <section v-else-if="stage === 'reflect'" class="pressure">
      <CommunityQuestion :take="yourTake" :perspective="store.challenge" />

      <!-- 保留原判断：一句很轻的确认，不假装用户想深了一层 -->
      <p v-if="kept" class="kept">那就保留它。</p>

      <!-- 看完追问，先问要不要改，而不是直接要输入 -->
      <ReflectionChoice
        v-else-if="!adding"
        :loading="store.loading"
        @add="adding = true"
        @keep="keepMyTake"
        @skip="skipToAnswer"
      />

      <!-- 选了「我想补充」之后才出现输入框 -->
      <ReflectionInput
        v-else
        :loading="store.loading"
        :suggestion="DEMO_CHALLENGE_REPLY"
        @submit="submitChallenge"
        @back="adding = false"
      />
    </section>

    <!-- ============ 修正 + Ownership ============ -->
    <section v-else class="refine">
      <InsightRewrite
        :v1="store.insightV1"
        :v2="store.insightV2"
        :response="store.challengeResponse"
      />

      <!-- Ownership handshake：决定「这是不是我的观点」的人只能是用户 -->
      <div v-if="!ownEditing" class="own">
        <p class="own-ask">这句话，是你的吗？</p>
        <div class="own-actions">
          <button class="btn btn-insight" :disabled="store.loading" @click="claimIt">
            {{ store.loading ? '…' : '是，这就是我想说的' }}
          </button>
          <button class="btn btn-ghost" @click="startOwnEdit">还差一点</button>
        </div>
      </div>

      <div v-else class="own edit-pane">
        <p class="edit-label">那就改成你想说的样子</p>
        <textarea v-model="ownDraft" class="edit-area" rows="3" />
        <div class="edit-actions">
          <button class="btn btn-insight" :disabled="store.loading" @click="saveOwnEdit">
            这才是我想说的
          </button>
          <button class="btn btn-ghost" @click="ownEditing = false">返回</button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.mine {
  min-height: 100vh;
  transition: background 0.8s var(--ease);
}

/* Insight 时环境压暗，让用户的话成为唯一亮着的东西 */
.stage-reveal {
  background: #040509;
}

.topbar {
  display: flex;
  align-items: center;
  gap: 10px;
  max-width: 1180px;
  margin: 0 auto;
  padding: 22px 24px 10px;
  transition: opacity 0.6s var(--ease);
}

.stage-reveal .topbar {
  opacity: 0.3;
}

.mark {
  color: var(--accent);
  font-size: 14px;
}

.q {
  margin: 0;
  font-size: 15px;
  font-weight: 550;
  color: var(--text-muted);
  letter-spacing: -0.01em;
}

.err {
  max-width: 1180px;
  margin: 0 auto;
  padding: 0 24px;
  color: #ff9d9d;
  font-size: 14px;
}

/* ---------- 访谈空间 ---------- */

.space {
  position: relative;
  max-width: 1180px;
  margin: 0 auto;
  padding: 12px 24px 32px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 300px;
  gap: 40px;
  align-items: start;
}

.talk {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 130px);
  min-height: 460px;
  transform-origin: left center;
  transition:
    opacity 0.7s var(--ease),
    transform 0.7s var(--ease),
    filter 0.7s var(--ease);
}

/* 不卸载，只退到背景里 —— Insight 发生在「我的对话」里面 */
.talk.receded {
  opacity: 0.1;
  filter: blur(3px);
  pointer-events: none;
}

.talk-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 4px 20px;
  display: flex;
  flex-direction: column;
  gap: 22px;
}

/* 去 chat 化：没有头像圆圈、没有气泡底色。更像访谈速记 */
.turn {
  display: flex;
  gap: 10px;
  max-width: 90%;
}

.turn.user {
  flex-direction: row-reverse;
  margin-left: auto;
  text-align: right;
}

.ai-mark {
  flex-shrink: 0;
  color: var(--text-dim);
  font-size: 12px;
  line-height: 2;
}

.said {
  margin: 0;
  font-size: 15.5px;
  line-height: 1.75;
}

.turn.ai .said {
  color: var(--text-muted);
}

.turn.user .said {
  color: var(--text);
  font-weight: 500;
}

.thinking {
  display: flex;
  gap: 5px;
  align-items: center;
  padding-top: 10px;
}

.thinking span {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--text-dim);
  animation: blink 1.3s infinite;
}

.thinking span:nth-child(2) {
  animation-delay: 0.2s;
}
.thinking span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%,
  60%,
  100% {
    opacity: 0.25;
  }
  30% {
    opacity: 1;
  }
}

/* ---------- 输入 ---------- */

.composer {
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.composer.center {
  max-width: 620px;
  margin: 0 auto;
  border-top: none;
  padding-top: 0;
}

.input-row {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

.input {
  flex: 1;
  resize: none;
  padding: 11px 0;
  background: none;
  border: none;
  border-bottom: 1px solid var(--border);
  color: var(--text);
  line-height: 1.6;
  transition: border-color 0.2s var(--ease);
}

.input:focus {
  outline: none;
  border-bottom-color: var(--accent);
}

.send {
  flex-shrink: 0;
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

.hint {
  margin-top: 12px;
  font-size: 12.5px;
  color: var(--text-dim);
  text-align: left;
  line-height: 1.5;
  opacity: 0.75;
}

.hint:hover {
  color: var(--accent-soft);
}

/* ---------- 碎片区 ---------- */

.mind {
  padding-top: 14px;
  min-height: 200px;
}

.overlay {
  position: absolute;
  inset: 0;
  padding: 0 24px;
}

/* ---------- 改写自己的观点 ---------- */

.edit-pane {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  z-index: 4;
}

.edit-label {
  margin: 0;
  font-size: 13px;
  letter-spacing: 0.1em;
  color: var(--text-dim);
}

.edit-area {
  width: min(560px, 100%);
  resize: none;
  padding: 16px 18px;
  border-radius: var(--radius-sm);
  background: var(--surface);
  border: 1px solid var(--border-strong);
  color: var(--text);
  font-size: 17px;
  line-height: 1.7;
}

.edit-area:focus {
  outline: none;
  border-color: var(--insight);
}

.edit-actions {
  display: flex;
  gap: 12px;
}

/* ---------- 对峙 ---------- */

.challenge {
  max-width: 1180px;
  margin: 0 auto;
  padding: 48px 24px 60px;
}

.ask {
  margin: 68px auto 34px;
  text-align: center;
  font-size: clamp(17px, 2.1vw, 20px);
  font-weight: 550;
  color: var(--text);
  animation: fade-up 0.5s var(--ease) 0.6s both;
}

/* ---------- 修正 ---------- */

.refine {
  max-width: 1180px;
  margin: 0 auto;
  padding: 60px 24px;
}

.own {
  margin-top: 56px;
  text-align: center;
  animation: fade-up 0.5s var(--ease) 3.4s both;
}

.own-ask {
  margin: 0 0 24px;
  font-size: clamp(19px, 2.3vw, 23px);
  font-weight: 600;
  color: var(--text);
}

.own-actions {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}

.own.edit-pane {
  animation: none;
}

@media (max-width: 1000px) {
  .space {
    grid-template-columns: 1fr;
    gap: 24px;
  }
  .talk {
    height: auto;
    min-height: 380px;
  }
}
</style>
