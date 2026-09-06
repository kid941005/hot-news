/**
 * 全局 Toast 提示（组合式函数）
 * - 模块级响应式状态，任何组件都可调用 useToast() 获取同一份提示队列
 * - 自动 3.5 秒后消失；支持 info / success / error 三种类型
 */
import { ref } from 'vue'

const toasts = ref([])
let nextId = 1
const TOAST_DURATION = 3500

function removeToast(id) {
  const index = toasts.value.findIndex((item) => item.id === id)
  if (index !== -1) {
    toasts.value.splice(index, 1)
  }
}

function showToast(message, type = 'info') {
  if (!message) return
  const id = nextId++
  toasts.value.push({ id, message, type })
  setTimeout(() => removeToast(id), TOAST_DURATION)
}

export function useToast() {
  return { toasts, showToast, removeToast }
}
