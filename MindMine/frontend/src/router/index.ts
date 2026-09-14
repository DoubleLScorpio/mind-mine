import { createRouter, createWebHistory } from 'vue-router'

/**
 * Onboarding 的情绪线：Know → See → Find → Claim
 *
 *   /            Opening      这次，换你。
 *   /know-me     Know Me      先让我认识你。
 *   /tracing     Trace        正在从散落的痕迹里认出一个人
 *   /chat        Chat         先聊两句（无知乎登录的 fallback）
 *   /portrait    Portrait     我好像看到这样一个你。
 *   /match       Match        也许，这题该你来答。
 *
 * 之后的 Mining / Insight / Challenge / Refinement / Contribution 不变。
 */
const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'opening',
      component: () => import('@/pages/OpeningPage.vue'),
    },
    {
      path: '/know-me',
      name: 'know-me',
      component: () => import('@/pages/KnowMePage.vue'),
    },
    {
      path: '/tracing',
      name: 'tracing',
      component: () => import('@/pages/TracingPage.vue'),
    },
    {
      path: '/chat',
      name: 'chat',
      component: () => import('@/pages/ChatIntroPage.vue'),
    },
    {
      path: '/portrait',
      name: 'portrait',
      component: () => import('@/pages/PortraitPage.vue'),
    },
    {
      path: '/match',
      name: 'match',
      component: () => import('@/pages/MatchPage.vue'),
    },
    {
      path: '/mine/:questionId',
      name: 'mine',
      component: () => import('@/pages/MinePage.vue'),
    },
    {
      path: '/result/:sessionId',
      name: 'result',
      component: () => import('@/pages/ResultPage.vue'),
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
