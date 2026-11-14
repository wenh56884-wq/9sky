<script setup>
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '../stores/auth'
import { brand } from '../brand'

const auth = useAuthStore()

const username = ref('')
const password = ref('')
const busy = ref(false)
const error = ref('')

// 注册模式：与后端 auth_store.validate_username / validate_password 同规则的客户端预校验
// （真正的边界以后端为准；这里只做即时提示，避免用户白提交）
const mode = ref('login')
const registerOpen = ref(true)
const regUsername = ref('')
const regPassword = ref('')
const regConfirm = ref('')
const regBusy = ref(false)
const regError = ref('')

const USERNAME_RE = /^(?=.*[\w一-龥])[\w\-一-龥]{3,32}$/

function utf8Bytes(text) {
  try { return new TextEncoder().encode(text).length } catch (_) { return text.length * 3 }
}

function validateRegister() {
  const name = regUsername.value.trim()
  if (!name) return '请填写用户名。'
  if (name.length < 3) return '用户名至少 3 个字符。'
  if (name.length > 32) return '用户名最多 32 个字符。'
  if (!USERNAME_RE.test(name)) return '用户名只能包含中文、字母、数字、下划线或连字符。'
  if (!regPassword.value || regPassword.value.trim().length < 6) return '密码至少 6 位。'
  if (utf8Bytes(regPassword.value) > 72) return '密码过长（UTF-8 编码后不能超过 72 字节）。'
  if (regPassword.value !== regConfirm.value) return '两次输入的密码不一致。'
  return ''
}

async function submitRegister() {
  regError.value = ''
  const bad = validateRegister()
  if (bad) { regError.value = bad; return }
  regBusy.value = true
  try {
    await auth.register(regUsername.value.trim(), regPassword.value, regConfirm.value)
    // 注册成功即自动登录；App.vue 监听 loggedIn 进入工作台
  } catch (e) {
    regError.value = e.message
  } finally {
    regBusy.value = false
  }
}

function switchMode(next) {
  mode.value = next
  error.value = ''
  regError.value = ''
}

onMounted(async () => {
  registerOpen.value = await auth.registerOpen()
})

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
    <!-- 左侧品牌展示区：桌面端呈现产品定位与能力，窄屏自动隐藏 -->
    <aside class="login-aside" aria-hidden="true">
      <div class="la-top">
        <div class="la-logo">梧</div>
        <div class="la-name">{{ brand.name }}<span>AI 工作台</span></div>
      </div>

      <div class="la-hero">
        <h1>用一句话，<br>问清你的业务数据</h1>
        <p>自然语言直连业务库，只读查询、知识库检索、趋势预测，全程可追溯；涉及写入的操作先进入审批，由人确认后执行。</p>
      </div>

      <ul class="la-feats">
        <li>
          <span class="la-ico"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.7 3.6 3 8 3s8-1.3 8-3V5"/><path d="M4 11v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/></svg></span>
          <div><b>业务数据</b><small>打通业务库，只读 SQL 由系统校验后执行</small></div>
        </li>
        <li>
          <span class="la-ico"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H20v15H6.5A2.5 2.5 0 0 0 4 20.5z"/><path d="M8 7h8M8 11h6"/></svg></span>
          <div><b>知识库检索</b><small>文档切片与向量召回，回答带原文出处</small></div>
        </li>
        <li>
          <span class="la-ico"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 17l5-6 4 3 5-7 4 4"/><path d="M3 21h18"/></svg></span>
          <div><b>趋势预测</b><small>基于历史数据建模，输出可解释的预测区间</small></div>
        </li>
        <li>
          <span class="la-ico"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 11l3 3 8-8"/><path d="M20 12v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h9"/></svg></span>
          <div><b>人机协同</b><small>写操作按风险分级审批，全程留痕可回滚</small></div>
        </li>
      </ul>

      <div class="la-foot">本地部署 · 数据不出内网</div>
    </aside>

    <div class="login-main">
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

      <!-- 注册表单（普通用户自助注册，注册成功自动登录；角色固定为普通用户） -->
      <form v-else-if="mode === 'register'" class="login-form" @submit.prevent="submitRegister">
        <div class="login-change-title">
          <b>注册新账号</b>
          <small>注册后为普通用户，可使用查询与分析功能；更高角色由超级管理员分配</small>
        </div>
        <label class="login-field">
          <span>用户名</span>
          <input v-model="regUsername" type="text" autocomplete="username" placeholder="3–32 个字符，支持中文">
        </label>
        <label class="login-field">
          <span>密码</span>
          <input v-model="regPassword" type="password" autocomplete="new-password" placeholder="至少 6 位">
        </label>
        <label class="login-field">
          <span>确认密码</span>
          <input v-model="regConfirm" type="password" autocomplete="new-password" placeholder="再次输入密码">
        </label>
        <div v-if="regError" class="login-error">{{ regError }}</div>
        <div class="login-actions">
          <button type="submit" class="login-submit" :disabled="regBusy">
            {{ regBusy ? '注册中…' : '注册并登录' }}
          </button>
          <button type="button" class="login-cancel" @click="switchMode('login')">返回登录</button>
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
        <p v-if="registerOpen" class="login-tip">
          还没有账号？<button type="button" class="login-link" @click="switchMode('register')">注册一个</button>
        </p>
        <p class="login-tip">首次启动默认超管账号见服务端配置（默认 admin / admin123），登录后请及时改密。</p>
      </form>
    </div>
    <p class="login-foot">九天梧桐 AI 工作台 · 登录后按角色进入工作台</p>
    </div>
  </div>
</template>
