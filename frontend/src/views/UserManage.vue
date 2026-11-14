<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore, ROLE_LABELS } from '../stores/auth'
import { useNav } from '../composables/useNav'
import { confirm as askConfirm } from '../composables/useConfirm'

const auth = useAuthStore()
const nav = useNav()

const users = ref([])
const loading = ref(false)
const error = ref('')

// 新建用户
const form = ref({ username: '', password: '', role: 1 })
const formError = ref('')
const creating = ref(false)

// 重置密码弹层
const resetFor = ref(null)
const resetPwd = ref('')
const resetConfirm = ref('')
const resetError = ref('')
const resetting = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    users.value = await auth.listUsers()
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function create() {
  formError.value = ''
  if (!form.value.username.trim()) { formError.value = '请填写用户名。'; return }
  if (!form.value.password) { formError.value = '请填写密码。'; return }
  if (form.value.password.length < 6) { formError.value = '密码至少 6 位。'; return }
  creating.value = true
  try {
    const user = await auth.createUser({
      username: form.value.username.trim(),
      password: form.value.password,
      role: Number(form.value.role) || 0,
    })
    users.value = [...users.value, user]
    form.value = { username: '', password: '', role: 1 }
  } catch (e) {
    formError.value = e.message
  } finally {
    creating.value = false
  }
}

async function changeRole(u, role) {
  const next = Number(role)
  if (u.role === next) return
  try {
    const updated = await auth.updateUser(u.id, { role: next })
    const idx = users.value.findIndex((x) => x.id === u.id)
    if (idx >= 0 && updated) users.value[idx] = { ...users.value[idx], ...updated }
  } catch (e) {
    error.value = '改角色失败：' + e.message
    load()   // 失败时以后端状态为准，避免下拉框显示与实际角色不一致
  }
}

// 超管禅让：唯一超管把身份移交他人；旧超管立即降为管理员并强制下线
async function transferSuper(u) {
  const ok = await askConfirm({
    title: '移交超级管理员',
    text: '确定把超级管理员身份移交给「' + u.username + '」？移交后你将降为管理员，并需要重新登录。',
    okText: '确认移交',
    danger: true,
  })
  if (!ok) return
  try {
    await auth.transferSuper(u.id)
  } catch (e) {
    error.value = '移交失败：' + e.message
  }
}

function openReset(u) {
  resetFor.value = u
  resetPwd.value = ''
  resetConfirm.value = ''
  resetError.value = ''
}

async function submitReset() {
  resetError.value = ''
  if (!resetFor.value) return
  if (!resetPwd.value) { resetError.value = '请填写新密码。'; return }
  if (resetPwd.value.length < 6) { resetError.value = '密码至少 6 位。'; return }
  if (resetPwd.value !== resetConfirm.value) { resetError.value = '两次输入的新密码不一致。'; return }
  resetting.value = true
  try {
    const updated = await auth.updateUser(resetFor.value.id, { password: resetPwd.value })
    const idx = users.value.findIndex((x) => x.id === resetFor.value.id)
    if (idx >= 0 && updated) users.value[idx] = { ...users.value[idx], ...updated }
    resetFor.value = null
  } catch (e) {
    resetError.value = e.message
  } finally {
    resetting.value = false
  }
}

async function remove(u) {
  const ok = await askConfirm({
    title: '删除用户',
    text: '确定删除用户「' + u.username + '」？该用户将无法再登录。',
    okText: '删除',
    danger: true,
  })
  if (!ok) return
  try {
    await auth.deleteUser(u.id)
    users.value = users.value.filter((x) => x.id !== u.id)
  } catch (e) {
    error.value = '删除失败：' + e.message
  }
}

function fmtTime(v) {
  if (!v) return '—'
  return String(v).replace('T', ' ').slice(0, 19)
}
</script>

<template>
  <div class="um-page">
    <header class="um-head">
      <div class="um-head-title">
        <b>用户管理</b>
        <small>增删用户 · 改角色 · 重置密码（仅超级管理员）</small>
      </div>
      <button type="button" class="head-btn" @click="nav.setView('workbench')">返回工作台</button>
    </header>

    <div v-if="error" class="um-error">{{ error }}</div>

    <div class="um-body">
      <!-- 新建用户 -->
      <section class="um-create">
        <b>新建用户</b>
        <div class="um-create-grid">
          <label class="um-field">
            <span>用户名</span>
            <input v-model="form.username" type="text" placeholder="登录用户名">
          </label>
          <label class="um-field">
            <span>密码</span>
            <input v-model="form.password" type="password" placeholder="至少 6 位">
          </label>
          <label class="um-field">
            <span>角色</span>
            <!-- 超级管理员唯一：创建入口只开放访客/普通用户/管理员 -->
            <select v-model.number="form.role">
              <template v-for="(label, r) in ROLE_LABELS" :key="r">
                <option v-if="Number(r) < 3" :value="Number(r)">{{ label }}</option>
              </template>
            </select>
          </label>
          <button type="button" class="um-create-btn" :disabled="creating" @click="create">
            {{ creating ? '创建中…' : '创建用户' }}
          </button>
        </div>
        <div v-if="formError" class="um-error">{{ formError }}</div>
      </section>

      <!-- 用户列表 -->
      <section class="um-list">
        <div class="um-list-head">
          <b>用户列表</b>
          <span class="um-count">{{ users.length }} 个用户</span>
        </div>
        <div v-if="loading" class="um-empty">加载中…</div>
        <div v-else-if="!users.length" class="um-empty">还没有用户。</div>
        <table v-else class="um-table">
          <thead>
            <tr>
              <th>用户名</th>
              <th>角色</th>
              <th>创建时间</th>
              <th>最后登录</th>
              <th class="um-ops">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="u in users" :key="u.id" :class="{ 'is-self': auth.user && u.id === auth.user.id }">
              <td class="um-name">
                {{ u.username }}
                <span v-if="auth.user && u.id === auth.user.id" class="um-self">（当前登录）</span>
              </td>
              <td>
                <select
                  class="um-role-select"
                  :value="Number(u.role)"
                  :disabled="(auth.user && u.id === auth.user.id) || Number(u.role) === 3"
                  :title="Number(u.role) === 3 ? '唯一超管不可直接改角色；交接请用「移交超管」' : ''"
                  @change="changeRole(u, $event.target.value)"
                >
                  <template v-for="(label, r) in ROLE_LABELS" :key="r">
                    <option v-if="Number(r) < 3 || Number(u.role) === 3" :value="Number(r)">{{ label }}</option>
                  </template>
                </select>
              </td>
              <td class="um-time">{{ fmtTime(u.created_at) }}</td>
              <td class="um-time">{{ fmtTime(u.last_login) }}</td>
              <td class="um-ops">
                <button type="button" class="um-op" @click="openReset(u)">重置密码</button>
                <button
                  v-if="auth.isSuper && auth.user && u.id !== auth.user.id && Number(u.role) < 3"
                  type="button"
                  class="um-op"
                  title="把唯一超级管理员身份移交给该用户（你将降为管理员并重新登录）"
                  @click="transferSuper(u)"
                >移交超管</button>
                <button
                  type="button"
                  class="um-op danger"
                  :disabled="auth.user && u.id === auth.user.id"
                  :title="auth.user && u.id === auth.user.id ? '不可删除当前登录账号' : '删除用户'"
                  @click="remove(u)"
                >删除</button>
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <!-- 重置密码弹层 -->
    <div v-if="resetFor" class="up-mask show" @click.self="resetFor = null">
      <div class="um-modal">
        <b>重置密码 · {{ resetFor.username }}</b>
        <label class="um-field">
          <span>新密码</span>
          <input v-model="resetPwd" type="password" placeholder="至少 6 位">
        </label>
        <label class="um-field">
          <span>确认新密码</span>
          <input v-model="resetConfirm" type="password" placeholder="再次输入新密码">
        </label>
        <div v-if="resetError" class="um-error">{{ resetError }}</div>
        <div class="um-modal-actions">
          <button type="button" class="um-create-btn" :disabled="resetting" @click="submitReset">
            {{ resetting ? '提交中…' : '确认重置' }}
          </button>
          <button type="button" class="login-cancel" @click="resetFor = null">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>
