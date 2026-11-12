import { defineStore } from 'pinia'
import { getBrand, applyBrand } from '../theme'
import { brand } from '../brand'

// 本地偏好：主题、显示过程、深度搜索、技能卡、模型、当前会话 id
// 全部持久化到 localStorage，键名与原 index.html 保持一致（wh_*）
export const useConfigStore = defineStore('config', {
  state: () => ({
    threadId: localStorage.getItem('wh_thread_id') || '',
    theme: localStorage.getItem('wh_theme') || '',
    showProc: localStorage.getItem('wh_show_process') === '1',
    deepMode: localStorage.getItem('wh_deep_mode') === '1',
    skill: localStorage.getItem('wh_db_skill') || '',
    model: localStorage.getItem('wh_model') || '',
  }),
  getters: {
    isDark: (s) => s.theme === 'dark',
  },
  actions: {
    setThreadId(id) {
      this.threadId = id || ''
      try { id ? localStorage.setItem('wh_thread_id', id) : localStorage.removeItem('wh_thread_id') } catch (_) {}
    },
    setTheme(t) {
      this.theme = t
      try { localStorage.setItem('wh_theme', t) } catch (_) {}
      document.documentElement.dataset.theme = t
      // E1：主题切换后重算品牌色阶（深色下提亮保证 AA 对比度）
      applyBrand(getBrand() || brand, t)
    },
    toggleTheme() {
      this.setTheme(this.theme === 'dark' ? 'light' : 'dark')
    },
    setShowProc(v) {
      this.showProc = v
      try { localStorage.setItem('wh_show_process', v ? '1' : '0') } catch (_) {}
    },
    setDeepMode(v) {
      this.deepMode = v
      try { localStorage.setItem('wh_deep_mode', v ? '1' : '0') } catch (_) {}
    },
    setSkill(v) {
      this.skill = v || ''
      try { localStorage.setItem('wh_db_skill', v || '') } catch (_) {}
    },
    setModel(v) {
      this.model = v || ''
      try { localStorage.setItem('wh_model', v || '') } catch (_) {}
    },
  },
})
