<script setup lang="ts">
/**
 * OAuth 返回页 —— 知乎授权完成后的落地页。
 *
 * 后端 callback 完成后 302 到这里，携带本次会话的 onboarding_id：
 *   /oauth/return?ob=<onboarding_id>
 * 或携带错误：
 *   /oauth/return?error=<declined|token_failed|...>
 *
 * 这里只负责「恢复画像」或「引导去先聊两句」，
 * 不展示任何 OAuth 技术细节。
 */
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useOnboardingStore } from '@/stores/onboarding'

const route = useRoute()
const router = useRouter()
const ob = useOnboardingStore()

const status = ref<'loading' | 'done' | 'error'>('loading')
const errorMessage = ref('')

onMounted(async () => {
  const obId = String(route.query.ob ?? '')
  const err = String(route.query.error ?? '')

  if (obId) {
    const s = await ob.completeOAuth(obId)
    if (s) {
      status.value = 'done'
      router.replace('/portrait')
      return
    }
  }

  // 未拿到画像：回到 Know Me，引导「先聊两句」
  status.value = 'error'
  errorMessage.value =
    err === 'declined' || err === 'not_configured'
      ? '没关系，不授权也可以先聊两句。'
      : '这次没能从知乎认出来，先聊两句也一样。'
})

function goKnowMe() {
  ob.reset()
  router.replace('/know-me')
}

function goChat() {
  router.replace('/know-me')
  // 交给 KnowMe 的入口，避免这里重复 startChat
}
</script>

<template>
  <div class="oauth-return">
    <div class="inner">
      <template v-if="status === 'loading'">
        <p class="line">正在把你留下的痕迹，慢慢拼起来……</p>
      </template>

      <template v-else-if="status === 'error'">
        <h1 class="title">没关系。</h1>
        <p class="sub">{{ errorMessage }}</p>
        <button class="cta" @click="goKnowMe">先聊两句 →</button>
        <button class="alt" @click="goChat">回到「认识我」</button>
      </template>
    </div>
  </div>
</template>

<style scoped>
.oauth-return {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}

.inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  max-width: 520px;
}

.title {
  margin: 0 0 20px;
  font-size: clamp(26px, 4vw, 34px);
  font-weight: 650;
  letter-spacing: -0.02em;
}

.sub {
  margin: 0 0 40px;
  font-size: 15.5px;
  line-height: 1.85;
  color: var(--text-muted);
}

.line {
  margin: 0;
  font-size: 15px;
  color: var(--text-dim);
}

.cta {
  font-size: 19px;
  font-weight: 600;
  color: var(--insight);
  padding: 8px 0;
}

.alt {
  margin-top: 18px;
  font-size: 14px;
  color: var(--text-dim);
  padding: 6px 0;
}
</style>
