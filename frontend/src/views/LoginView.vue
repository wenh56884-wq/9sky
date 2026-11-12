<script setup>
import { ref, computed } from 'vue'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()

const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

// 首次登录超管默认密码：提示改密
const showChange = ref(false)
const oldPwd = ref('')
const newPwd = ref('')
const confirmPwd = ref('')
const changeError = ref('')
const changeBusy = ref(false)

const canSubmit = computed(() => !!username.value.trim() && !!password.value && !busy.value)

async function submit() {
  error.value = ''
  if (!username.value.trim() || !password.value) return
  busy.value = true
  try {
    await auth.login(username.value.trim(), password.value)
    // 首次登录的超管（默认密码）提示改密
    if (auth.needsPasswordChange()) {
      showChange.value = true
    }
  } catch (e) {
    error.value = e.message
  } finally {
    busy.value = false
  }
}

async function submitChange() {
  changeError.value = ''
  if (!oldPwd.value || !newPwd.value) {
    changeError.value = '请填写原密码与新密码。'
    return
  }
  if (newPwd.value !== confirmPwd.value) {
    changeError.value = '两次输入的新密码不一致。'
    return
  }
  if (newPwd.value.length < 6) {
    changeError.value = '新密码至少 6 位。'
    return
  }
  changeBusy.value = true
  try {
    await auth.changePassword(oldPwd.value, newPwd.value)
    await auth.markPasswordChanged()
    showChange.value = false
    username.value = ''
    password.value = ''
  } catch (e) {
    changeError.value = e.message
  } finally {
    changeBusy.value = false
  }
}

function cancelChange() {
  showChange.value = false
  changeError.value = ''
  oldPwd.value = ''
  newPwd.value = ''
  confirmPwd.value = ''
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <div class="logo">梧</div>
        <div>
          <b>九天梧桐 AI 工作台</b>
          <small>业务数据 · 知识库 · 预测 · 人机协同</small>
        </div>
      </div>

      <!-- 登录失效提示 -->
      <div v-if="auth.expiredNotice" class="login-notice">{{ auth.expiredNotice }}</div>

      <!-- 首次登录改密 -->
      <form v-if="showChange" class="login-form" @submit.prevent="submitChange">
        <div class="login-change-title">
          <b>首次登录，建议立即修改密码</b>
          <small>当前为超级管理员默认密码，请设置新密码后继续使用</small>
        </div>
        <label class="login-field">
          <span>原密码</span>
          <input v-model="oldPwd" type="password" autocomplete="current-password" placeholder="请输入当前密码">
        </label>
        <label class="login-field">
          <span>新密码</span>
          <input v-model="newPwd" type="password" autocomplete="new-password" placeholder="至少 6 位">
        </label>
        <label class="login-field">
          <span>确认新密码</span>
          <input v-model="confirmPwd" type="password" autocomplete="new-password" placeholder="再次输入新密码">
        </label>
        <div v-if="changeError" class="login-error">{{ changeError }}</div>
        <div class="login-actions">
          <button type="submit" class="login-submit" :disabled="changeBusy">
            {{ changeBusy ? '提交中…' : '确认修改并继续' }}
          </button>
          <button type="button" class="login-cancel" @click="cancelChange">稍后再说</button>
        </div>
      </form>

      <!-- 登录表单 -->
      <form v-else class="login-form" @submit.prevent="submit">
        <label class="login-field">
          <span>用户名</span>
          <input v-model="username" type="text" autocomplete="username" placeholder="请输入用户名">
        </label>
        <label class="login-field">
          <span>密码</span>
          <input v-model="password" type="password" autocomplete="current-password" placeholder="请输入密码">
        </label>
        <div v-if="error" class="login-error">{{ error }}</div>
        <div class="login-actions">
          <button type="submit" class="login-submit" :disabled="!canSubmit">
            {{ busy ? '登录中…' : '登录' }}
          </button>
        </div>
        <p class="login-tip">首次启动默认超管账号见服务端配置（默认 admin / admin123），登录后请及时改密。</p>
      </form>
    </div>
    <p class="login-foot">九天梧桐 AI 工作台 · 登录后按角色进入工作台</p>
  </div>
</template>
