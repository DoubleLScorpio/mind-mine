<script setup lang="ts">
/**
 * 背景音乐开关。
 *
 * 低存在感原则：不写「背景音乐：开启」，不占一个 Card，
 * 只有一个 ♪ / ♫ 符号待在右上角。
 * 用户不该注意到它，直到他想安静下来的那一刻。
 */
import { computed } from 'vue'
import { useBgmStore } from '@/stores/bgm'

const bgm = useBgmStore()

const label = computed(() =>
  bgm.enabled ? '关闭背景音乐' : '打开背景音乐',
)
</script>

<template>
  <!-- 音频不可用时整个按钮消失，不向用户暴露技术故障 -->
  <button
    v-if="!bgm.unavailable"
    class="bgm-toggle"
    :class="{ 'is-on': bgm.enabled }"
    type="button"
    :title="label"
    :aria-label="label"
    :aria-pressed="bgm.enabled"
    @click="bgm.toggle()"
  >
    <span aria-hidden="true">{{ bgm.enabled ? '♫' : '♪' }}</span>
  </button>
</template>

<style scoped>
.bgm-toggle {
  position: fixed;
  top: 18px;
  right: 20px;
  z-index: 50;

  /* 移动端可点区域足够（44×44 是触摸最小推荐值） */
  width: 44px;
  height: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  border-radius: 999px;
  border: 1px solid transparent;
  background: transparent;

  font-size: 17px;
  line-height: 1;
  color: var(--text-dim);

  transition:
    color 0.2s var(--ease),
    background 0.2s var(--ease),
    border-color 0.2s var(--ease);
}

.bgm-toggle:hover {
  color: var(--text-muted);
  background: rgba(255, 255, 255, 0.04);
  border-color: var(--border);
}

/* 开启时只是「稍微亮一点」，不做呼吸灯、不做旋转动画 */
.bgm-toggle.is-on {
  color: var(--accent-soft);
  border-color: rgba(110, 139, 255, 0.24);
  background: var(--accent-dim);
}

@media (max-width: 640px) {
  .bgm-toggle {
    top: 12px;
    right: 12px;
  }
}
</style>
