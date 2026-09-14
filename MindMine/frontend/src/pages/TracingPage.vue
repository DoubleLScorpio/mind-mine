<script setup lang="ts">
/**
 * Mock Zhihu Trace —— 「正在从散落的痕迹里认出一个人」。
 *
 * 明确不要做的事：
 *   Loading... / Analyzing user profile... / Processing 4/7
 * 那是系统扫描仪的语言。
 *
 * 这里是逐条浮现 MindMine「看到了什么」，每条之间有停顿。
 * 全部是演示数据，必须明确标注，不得伪装成真实知乎账户数据。
 */
import { onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useOnboardingStore } from '@/stores/onboarding'

const router = useRouter()
const ob = useOnboardingStore()

onMounted(() => {
  if (!ob.traces.length) ob.traceMe()
})

// 画像生成完成后进入 Mind Portrait
watch(
  () => ob.stage,
  (s) => {
    if (s === 'portrait') router.push('/portrait')
  },
)
</script>

<template>
  <div class="tracing">
    <div class="inner">
      <div
        v-for="(t, i) in ob.traces"
        v-show="i < ob.revealedTraces"
        :key="t.kind"
        class="trace"
      >
        <p class="label">{{ t.label }}</p>
        <div class="items">
          <span
            v-for="(item, j) in t.items"
            :key="item"
            class="item"
            :style="{ animationDelay: `${j * 130}ms` }"
          >
            {{ item }}
          </span>
        </div>
      </div>

      <div v-if="ob.errorMessage" class="error-banner">
        {{ ob.errorMessage }}
      </div>
    </div>
  </div>
</template>

<style scoped>
.tracing {
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
  gap: 46px;
  width: 100%;
  max-width: 520px;
}

.trace {
  animation: fade-up 0.6s var(--ease) both;
}

.label {
  margin: 0 0 16px;
  font-size: 15px;
  color: var(--text-dim);
}

.items {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 18px;
}

/* 痕迹是「看到的东西」，不是标签。所以没有边框、没有底色 */
.item {
  font-size: clamp(18px, 2.3vw, 22px);
  font-weight: 550;
  color: var(--text);
  letter-spacing: -0.01em;
  animation: trace-in 0.55s var(--ease) both;
}

@keyframes trace-in {
  from {
    opacity: 0;
    transform: translateY(7px);
  }
}

.foot {
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}

@media (prefers-reduced-motion: reduce) {
  .item,
  .trace {
    animation-duration: 0.01ms;
  }
}
</style>
