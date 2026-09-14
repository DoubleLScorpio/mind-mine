<script setup lang="ts">
/**
 * 已废弃页面：旧「知乎痕迹逐条浮现」路径已改为真实 OAuth 整页跳转。
 * 若有人直接访问 /tracing，这里兜底跳回 Know Me，避免残留死链接。
 */
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()

onMounted(() => {
  router.replace('/know-me')
})
</script>

<template>
  <div class="tracing">
    <p class="line">正在跳转……</p>
  </div>
</template>

<style scoped>
.tracing {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
}
.line {
  font-size: 15px;
  color: var(--text-dim);
}
</style>
