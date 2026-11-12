// 全局视图切换（无路由，轻量导航状态）
// view: 'workbench' 工作台 | 'users' 用户管理
// approvalCenterOpen: 审批中心抽屉开关
import { reactive, readonly } from 'vue'

const state = reactive({
  view: 'workbench',
  approvalCenterOpen: false,
  approvalPending: 0,   // 待审批数（管理员徽标，审批中心加载后回写）
})

export function useNav() {
  return {
    state: readonly(state),
    setView(v) { state.view = v },
    openApprovalCenter() { state.approvalCenterOpen = true },
    closeApprovalCenter() { state.approvalCenterOpen = false },
    setApprovalPending(n) { state.approvalPending = Number(n) || 0 },
  }
}
