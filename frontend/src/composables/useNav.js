// 全局视图切换（无路由，轻量导航状态）
// view: 'workbench' 工作台 | 'users' 用户管理 | 'changes' 变更历史
// approvalCenterOpen: 审批中心抽屉开关；settingsOpen: 设置抽屉开关（N3）
// searchPulse / clearSearchSignal: 供全局快捷键（Ctrl+K / Esc）驱动侧栏搜索框（N4/N5）
import { reactive, readonly } from 'vue'

const state = reactive({
  view: 'workbench',
  approvalCenterOpen: false,
  approvalPending: 0,   // 待审批数（管理员徽标，审批中心加载后回写）
  settingsOpen: false,
  auditOpen: false,     // E2 审计日志占位弹窗
  searchPulse: 0,       // Ctrl+K：递增后侧栏聚焦搜索框
  clearSearchSignal: 0, // Esc：递增后侧栏清空搜索词
})

export function useNav() {
  return {
    state: readonly(state),
    setView(v) { state.view = v },
    openApprovalCenter() { state.approvalCenterOpen = true },
    closeApprovalCenter() { state.approvalCenterOpen = false },
    setApprovalPending(n) { state.approvalPending = Number(n) || 0 },
    openSettings() { state.settingsOpen = true },
    closeSettings() { state.settingsOpen = false },
    openAudit() { state.auditOpen = true },
    closeAudit() { state.auditOpen = false },
    requestSearchFocus() { state.searchPulse += 1 },
    requestClearSearch() { state.clearSearchSignal += 1 },
  }
}
