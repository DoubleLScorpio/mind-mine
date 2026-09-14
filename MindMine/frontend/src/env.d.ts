/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<{}, {}, any>
  export default component
}

/**
 * 前端只允许读取公开配置。
 * 任何 Secret（LLM_API_KEY / 知乎 Access Secret）都不得出现在这里。
 */
interface ImportMetaEnv {
  /** 后端 API 根地址。留空则走本地 vite 代理 */
  readonly VITE_API_BASE_URL?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
