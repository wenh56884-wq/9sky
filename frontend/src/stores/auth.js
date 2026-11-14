// 认证状态：token / 当前用户 / 角色权限
// 令牌持久化到 localStorage（wh_token），刷新后由 /api/auth/me 校验
import { defineStore } from 'pinia'
import { setToken, onUnauthorized } from '../api'
import { authApi } from '../api/auth'

const TOKEN_KEY = 'wh_token'
const USER_KEY = 'wh_user'
const SUPER_PWD_KEY = 'wh_super_pwd_changed'

function loadToken() {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch (_) { return '' }
}

function saveToken(t) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY) } catch (_) {}
}

function loadUser() {
  try {
    const raw = localStorage.getItem(USER_KEY)
    return raw ? JSON.parse(raw) : null
  } catch (_) { return null }
}

function saveUser(u) {
  try { u ? localStorage.setItem(USER_KEY, JSON.stringify(u)) : localStorage.removeItem(USER_KEY) } catch (_) {}
}

// 角色等级：0 访客 / 1 普通用户 / 2 管理员 / 3 超级管理员（见任务文档 §二）
export const ROLE_LABELS = {
  0: '访客',
  1: '普通用户',
  2: '管理员',
  3: '超级管理员',
}

// ---- 时序修复：store 模块加载时就把本地令牌注入请求层 ----
// 为什么必须在模块级做：刷新页面后各组件 onMounted 会立刻发请求（如 Composer 拉
// /api/models、/api/skills），若等到 App.vue 的 onMounted 才 setToken，这些先发的
// 请求会 401，触发 handleUnauthorized 清空登录态 —— 表现为「刷新一下就要重新登录」。
// 这里在模块加载期（早于任何组件挂载）注入 token，保证首个请求就带 Authorization。
const _initialToken = loadToken()
if (_initialToken) setToken(_initialToken)

export const useAuthStore = defineStore('auth', {
  state: () => ({
    token: _initialToken,
    user: loadUser(),
    expiredNotice: '',   // 401 失效时给登录页的提示文案
  }),
  getters: {
    loggedIn: (s) => !!s.token && !!s.user,
    role: (s) => (s.user ? Number(s.user.role) : 0),
    isAdmin: (s) => (s.user ? Number(s.user.role) >= 2 : false),
    isSuper: (s) => (s.user ? Number(s.user.role) === 3 : false),
  },
  actions: {
    // 角色能力辅助（≥ 指定等级）
    can(minRole) {
      return this.role >= minRole
    },
    hasRole(minRole) {
      return this.role >= minRole
    },

    // 把令牌注入请求层，并注册 401 回调：失效时清登录、跳登录页
    init() {
      setToken(this.token)
      onUnauthorized(() => {
        this.token = ''
        this.user = null
        this.expiredNotice = '登录状态已失效，请重新登录。'
        saveToken('')
        saveUser(null)
      })
    },

    async login(username, password) {
      const data = await authApi.login(username, password)
      this.token = data.token || ''
      this.user = data.user || null
      this.expiredNotice = ''
      setToken(this.token)
      saveToken(this.token)
      saveUser(this.user)
      return this.user
    },

    // 开放注册（固定 role=1）：注册成功后自动登录，进入工作台
    async register(username, password, confirm) {
      await authApi.register(username, password, confirm)
      return this.login(username, password)
    },

    // 注册入口是否开放（后端 REG_ENABLED 控制）
    async registerOpen() {
      try {
        const data = await authApi.registerStatus()
        return data.open !== false
      } catch (_) {
        return true
      }
    },

    // 刷新页面后校验本地令牌是否仍有效
    async refreshMe() {
      const data = await authApi.me()
      if (data.user) {
        this.user = data.user
        saveUser(this.user)
      }
      return this.user
    },

    async logout() {
      try {
        await authApi.logout()
      } catch (_) {
        // 服务端会话可能已失效：本地照常清理
      }
      this.clear()
    },

    clear() {
      this.token = ''
      this.user = null
      this.expiredNotice = ''
      setToken('')
      saveToken('')
      saveUser(null)
    },

    async changePassword(oldPassword, newPassword) {
      return authApi.changePassword(oldPassword, newPassword)
    },

    // 首次登录超管默认密码提示改密：本地标记，改密成功后清除
    needsPasswordChange() {
      return this.isSuper && localStorage.getItem(SUPER_PWD_KEY) !== '1'
    },
    async markPasswordChanged() {
      try { localStorage.setItem(SUPER_PWD_KEY, '1') } catch (_) {}
    },

    // ---- 用户管理（超管）----
    async listUsers() {
      const data = await authApi.listUsers()
      return data.users || []
    },
    async createUser(payload) {
      const data = await authApi.createUser(payload)
      return data.user
    },
    async updateUser(id, patch) {
      const data = await authApi.updateUser(id, patch)
      return data.user
    },
    async deleteUser(id) {
      return authApi.deleteUser(id)
    },

    // 超管禅让：成功后本会话随即失效（后端删了旧超管全部会话）→ 清理本地并回登录页
    async transferSuper(successorId) {
      await authApi.transferSuper(successorId)
      this.clear()
    },
  },
})
