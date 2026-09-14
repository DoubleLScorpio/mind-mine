<script setup lang="ts">
/**
 * Opening —— 第一屏只承担一个任务：
 * 让用户从 Reader 心态进入「这次轮到我」的心态。
 *
 * 所以这里没有画像、没有选择框、没有功能列表、没有 AI 技术介绍。
 * 只有一句话，和一个决定。
 */
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<template>
  <div class="opening">
    <div class="inner">
      <div class="brand">
        <span class="mark">◈</span>
        <span class="name">MindMine</span>
      </div>

      <h1 class="hook">
        你在知乎读过很多人的答案。<br />
        这次，换你来。
      </h1>

      <p class="slogan">You know more than you think.</p>

      <button class="cta" @click="router.push('/know-me')">
        轮到我了 <span class="arrow">→</span>
      </button>
    </div>

    <footer class="foot">Phase 1 演示版本</footer>
  </div>
</template>

<style scoped>
.opening {
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
  max-width: 600px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 9px;
  margin-bottom: 72px;
  animation: fade-up 0.5s var(--ease) both;
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

.hook {
  margin: 0;
  font-size: clamp(30px, 5vw, 44px);
  line-height: 1.45;
  font-weight: 650;
  letter-spacing: -0.025em;
  animation: fade-up 0.6s var(--ease) 0.15s both;
}

.slogan {
  margin: 40px 0 0;
  font-size: 14px;
  letter-spacing: 0.04em;
  color: var(--text-dim);
  animation: fade-up 0.6s var(--ease) 0.5s both;
}

.cta {
  margin-top: 76px;
  font-size: 18px;
  font-weight: 550;
  color: var(--insight);
  padding: 8px 0;
  animation: fade-up 0.6s var(--ease) 0.9s both;
}

.arrow {
  display: inline-block;
  transition: transform 0.16s var(--ease);
}

.cta:hover .arrow {
  transform: translateX(4px);
}

.foot {
  font-size: 11px;
  color: var(--text-dim);
  opacity: 0.6;
}
</style>
