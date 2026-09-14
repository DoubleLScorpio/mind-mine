<script setup lang="ts">
/**
 * Know Me —— 两个入口，最终汇聚到同一个 Mind Portrait。
 *
 *   知乎足迹  ↘
 *              Mind Portrait
 *   聊两句    ↗
 *
 * 这一屏不让用户选择任何标签。用户唯一要做的决定是：
 * 你希望我怎么认识你。
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useOnboardingStore } from '@/stores/onboarding'

const router = useRouter()
const ob = useOnboardingStore()

onMounted(() => {
  // 重新进入时回到干净状态
  if (ob.stage !== 'knowme') ob.reset()
  ob.stage = 'knowme'
})

async function byZhihu() {
  router.push('/tracing')
}

async function byChat() {
  await ob.startChat()
  router.push('/chat')
}
</script>

<template>
  <div class="knowme">
    <div class="inner">
      <h1 class="title">
        在找属于你的问题之前，<br />
        先让我认识你。
      </h1>

      <p class="sub">
        不是认识你的简历。<br />
        是看看，你可能有哪些值得讲出来的东西。
      </p>

      <button class="cta" @click="byZhihu">
        用知乎认识我 <span class="arrow">→</span>
      </button>

      <button class="alt" @click="byChat">先聊两句也可以</button>

      <!-- 用户必须知道：MindMine 在认识我，但最终「我是谁」由我确认 -->
      <p class="privacy">
        只用来寻找你可能值得回答的问题。<br />
        你可以随时修改 MindMine 对你的理解。
      </p>
    </div>
  </div>
</template>

<style scoped>
.knowme {
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
  align-items: center;
  justify-content: center;
  text-align: center;
  max-width: 560px;
}

.title {
  margin: 0;
  font-size: clamp(26px, 4.2vw, 36px);
  line-height: 1.48;
  font-weight: 650;
  letter-spacing: -0.02em;
  animation: fade-up 0.5s var(--ease) both;
}

.sub {
  margin: 28px 0 0;
  font-size: 15.5px;
  line-height: 1.85;
  color: var(--text-muted);
  animation: fade-up 0.5s var(--ease) 0.14s both;
}

.cta {
  margin-top: 64px;
  font-size: clamp(19px, 2.4vw, 23px);
  font-weight: 600;
  color: var(--insight);
  padding: 10px 0;
  letter-spacing: -0.01em;
  animation: fade-up 0.5s var(--ease) 0.28s both;
}

.arrow {
  display: inline-block;
  transition: transform 0.16s var(--ease);
}

.cta:hover .arrow {
  transform: translateX(4px);
}

.alt {
  margin-top: 22px;
  font-size: 14px;
  color: var(--text-dim);
  padding: 6px 0;
  animation: fade-up 0.5s var(--ease) 0.36s both;
}

.alt:hover {
  color: var(--text-muted);
}

.privacy {
  margin: 70px 0 0;
  font-size: 12px;
  line-height: 1.9;
  color: var(--text-dim);
  opacity: 0.72;
  animation: fade-up 0.5s var(--ease) 0.5s both;
}

.foot {
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}
</style>
