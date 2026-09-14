<script setup lang="ts">
/**
 * App Root。
 *
 * BackgroundMusic 必须挂在这一层（而不是任何 Page 组件）：
 * RouterView 切换时本组件不卸载，所以 Audio 实例不会被重建，
 * 音乐跨路由连续播放，不会从头开始。
 */
import { onMounted } from 'vue'
import { RouterView } from 'vue-router'
import MusicToggle from '@/components/MusicToggle.vue'
import { useBgmStore } from '@/stores/bgm'

const bgm = useBgmStore()

onMounted(() => {
  // 恢复用户上次的选择。被 autoplay policy 拦截时静默保持 OFF。
  void bgm.init()
})
</script>

<template>
  <MusicToggle />

  <RouterView v-slot="{ Component }">
    <component :is="Component" />
  </RouterView>
</template>
