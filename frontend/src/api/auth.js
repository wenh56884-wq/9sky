// 认证接口封装（契约见 OPTIMIZATION_TASKS.md §4.1）
// /api/auth/login 公开；其余需鉴权（请求层自动带 Bearer 令牌，401 自动清登录）
import { request } from './index'

export const authApi = {
  // 登录：body {username, password} → {token, user:{id,username,role}}
  async login(username, password) {
    return request('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ username, password }),
    })
  },

  // 登出：销毁当前会话令牌
  async logout() {
    return request('/api/auth/logout', { method: 'POST', body: JSON.stringify({}) })
  },

  // 当前用户：{user:{id,username,role}}
  async me() {
    return request('/api/auth/me')
  },

  // 改密：body {old_password, new_password}
  async changePassword(oldPassword, newPassword) {
    return request('/api/auth/change-password', {
      method: 'POST',
      body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
    })
  },

  // ---- 用户管理（超管，role ≥ 3）----
  // 用户列表
  async listUsers() {
    return request('/api/auth/users')
  },

  // 创建用户：body {username, password, role}
  async createUser({ username, password, role }) {
    return request('/api/auth/users', {
      method: 'POST',
      body: JSON.stringify({ username, password, role }),
    })
  },

  // 改角色 / 重置密码：body {role?, password?}
  async updateUser(id, patch) {
    return request('/api/auth/users/' + encodeURIComponent(id), {
      method: 'PATCH',
      body: JSON.stringify(patch),
    })
  },

  // 删除用户（后端限制：不可删自己 / 最后一个超管）
  async deleteUser(id) {
    return request('/api/auth/users/' + encodeURIComponent(id), { method: 'DELETE' })
  },
}
