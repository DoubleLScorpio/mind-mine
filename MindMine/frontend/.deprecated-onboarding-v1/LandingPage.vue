<script setup lang="ts">
/**
 * Landing —— Reader 阶段。
 *
 * 用户此刻的身份是「在知乎读过很多答案的人」。
 * 这一屏唯一要做的事：让他意识到这次可以换他来写。
 *
 * 选择必须是「挑出来的」，不是「填出来的」。
 * 所以用可点的词，不用下拉框 —— 下拉框把自我认领变成了填表。
 * 三项选完后汇聚成一句自我描述，让用户先认下「对，这大概就是我」。
 */
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useSessionStore } from '@/stores/session'
import type { CurrentStatus, SharePreference } from '@/types'

const router = useRouter()
const store = useSessionStore()

const STATUS_OPTIONS: { value: CurrentStatus; label: string; short: string }[] = [
  { value: 'student', label: '学生', short: '学生' },
  { value: 'early_career', label: '职场新人', short: '职场新人' },
  { value: 'mid_career', label: '工作 3–10 年', short: '工作 3–10 年' },
  { value: 'senior', label: '资深从业者', short: '资深从业者' },
  { value: 'freelance', label: '创业 / 自由职业', short: '创业 / 自由职业' },
]

const DOMAIN_OPTIONS = [
  '编程',
  'AI / 科技',
  '互联网',
  '职场',
  '教育',
  '金融',
  '创业',
  '生活',
]

const SHARE_OPTIONS: { value: SharePreference; label: string; short: string }[] = [
  { value: 'experience', label: '亲身经历', short: '亲身经历' },
  { value: 'opinion', label: '我的判断', short: '自己的判断' },
  { value: 'mistakes', label: '踩过的坑', short: '踩坑经历' },
  { value: 'expertise', label: '专业知识', short: '专业积累' },
]

const status = ref<CurrentStatus | null>(null)
const domain = ref<string | null>(null)
const share = ref<SharePreference | null>(null)

const ready = computed(
  () => status.value !== null && domain.value !== null && share.value !== null,
)

/** 三项选完后汇聚成的自我描述 */
const summary = computed(() => {
  if (!ready.value) return null
  const s = STATUS_OPTIONS.find((o) => o.value === status.value)!.short
  const p = SHARE_OPTIONS.find((o) => o.value === share.value)!.short
  return { status: s, domain: domain.value!, share: p }
})

function go() {
  if (!ready.value) return
  store.setProfile({
    source: 'manual',
    current_status: status.value!,
    domains: [domain.value!],
    share_preferences: [share.value!],
  })
  router.push('/questions')
}
</script>

<template>
  <div class="landing">
    <div class="inner">
      <div class="brand">
        <span class="mark">◈</span>
        <span class="name">MindMine</span>
      </div>

      <h1 class="slogan">
        你在知乎读过很多人的答案。<br />
        这次换你。
      </h1>

      <p class="prompt">先告诉我，你大概是谁。</p>

      <div class="groups">
        <section class="group">
          <div class="g-label">我现在是</div>
          <div class="chips">
            <button
              v-for="o in STATUS_OPTIONS"
              :key="o.value"
              class="chip"
              :class="{ on: status === o.value }"
              @click="status = o.value"
            >
              {{ o.label }}
            </button>
          </div>
        </section>

        <section class="group">
          <div class="g-label">我比较懂</div>
          <div class="chips">
            <button
              v-for="d in DOMAIN_OPTIONS"
              :key="d"
              class="chip"
              :class="{ on: domain === d }"
              @click="domain = d"
            >
              {{ d }}
            </button>
          </div>
        </section>

        <section class="group">
          <div class="g-label">我最想讲</div>
          <div class="chips">
            <button
              v-for="o in SHARE_OPTIONS"
              :key="o.value"
              class="chip"
              :class="{ on: share === o.value }"
              @click="share = o.value"
            >
              {{ o.label }}
            </button>
          </div>
        </section>
      </div>

      <!-- 汇聚。让用户先认下「对，这大概就是我」 -->
      <div v-if="summary" class="summary">
        <div class="s-lead">所以，你是一个</div>
        <p class="s-line">
          <span class="s-key">{{ summary.status }}</span>
          <span class="s-dot">·</span>
          <span class="s-key">懂{{ summary.domain }}</span>
          <span class="s-dot">·</span>
          <span class="s-key">愿意讲{{ summary.share }}</span>
          <span class="s-tail">的人。</span>
        </p>

        <button class="cta" @click="go">
          看看什么问题正在等你 <span class="arrow">→</span>
        </button>
      </div>
    </div>

    <footer class="foot">Phase 1 演示版本，问题与社区观点均为演示数据</footer>
  </div>
</template>

<style scoped>
.landing {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 56px 24px 28px;
}

.inner {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 680px;
  width: 100%;
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 34px;
}

.mark {
  color: var(--accent);
  font-size: 19px;
}

.name {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--text-muted);
}

.slogan {
  margin: 0 0 44px;
  font-size: clamp(27px, 4.4vw, 38px);
  line-height: 1.42;
  font-weight: 650;
  letter-spacing: -0.02em;
  animation: fade-up 0.5s var(--ease) both;
}

.prompt {
  margin: 0 0 34px;
  font-size: 15px;
  color: var(--text-dim);
  animation: fade-up 0.5s var(--ease) 0.08s both;
}

.groups {
  display: flex;
  flex-direction: column;
  gap: 28px;
  width: 100%;
  animation: fade-up 0.5s var(--ease) 0.14s both;
}

.g-label {
  font-size: 12px;
  letter-spacing: 0.14em;
  color: var(--text-dim);
  margin-bottom: 13px;
}

.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 9px;
  justify-content: center;
}

/* 未选中克制到几乎只是文字；选中必须一眼可见 */
.chip {
  padding: 9px 17px;
  border-radius: 999px;
  font-size: 15px;
  font-weight: 450;
  color: var(--text-dim);
  border: 1px solid transparent;
  background: rgba(255, 255, 255, 0.022);
  transition:
    color 0.18s var(--ease),
    background 0.18s var(--ease),
    border-color 0.18s var(--ease),
    transform 0.18s var(--ease);
}

.chip:hover {
  color: var(--text);
  background: var(--surface-raised);
  border-color: var(--border-strong);
}

.chip.on {
  color: #10131c;
  background: var(--text);
  border-color: var(--text);
  font-weight: 600;
  transform: scale(1.04);
}

.chip:active {
  transform: scale(0.97);
}

/* ---------- 汇聚 ---------- */

.summary {
  margin-top: 46px;
  padding-top: 34px;
  border-top: 1px solid var(--border);
  width: 100%;
  animation: fade-up 0.46s var(--ease) both;
}

.s-lead {
  font-size: 13px;
  color: var(--text-dim);
  margin-bottom: 14px;
}

.s-line {
  margin: 0;
  font-size: clamp(18px, 2.4vw, 23px);
  line-height: 1.65;
  font-weight: 500;
  color: var(--text-muted);
}

.s-key {
  color: var(--insight);
  font-weight: 600;
}

.s-dot {
  margin: 0 9px;
  color: var(--text-dim);
}

.s-tail {
  color: var(--text-muted);
}

.cta {
  margin-top: 36px;
  font-size: 17px;
  font-weight: 550;
  color: var(--insight);
  padding: 8px 0;
}

.arrow {
  display: inline-block;
  transition: transform 0.16s var(--ease);
}

.cta:hover .arrow {
  transform: translateX(4px);
}

.foot {
  margin-top: 40px;
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.7;
}

@media (prefers-reduced-motion: reduce) {
  .chip.on {
    transform: none;
  }
}
</style>
