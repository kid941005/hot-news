/**
 * 统一 API 请求封装（对标 DailyHot request.js）
 * - 请求拦截：自动注入登录 token
 * - 响应拦截：401 统一清理登录态；403/404/500 统一抛错误事件供 UI 提示
 * - 错误归一化：getErrorMessage 提取后端 error/detail 文案
 */
import axios from 'axios'

export const TOKEN_KEY = 'token'
export const USERNAME_KEY = 'username'

const http = axios.create({
  baseURL: '',
  timeout: 30000,
})

// 请求拦截：统一注入 token，调用方无需再手动拼 Authorization 头
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

export function getErrorMessage(e, fallback = '请求失败') {
  const data = e?.response?.data
  if (data?.error) return data.error
  if (data?.detail) {
    if (typeof data.detail === 'string') return data.detail
    if (Array.isArray(data.detail)) {
      const messages = data.detail.map((item) => item?.msg || '').filter(Boolean)
      if (messages.length) return messages.join('；')
    }
  }
  if (e?.message) return e.message
  return fallback
}

// 全局错误/认证过期事件：供 UI（toast）监听
export function emitApiError(message) {
  window.dispatchEvent(new CustomEvent('api:error', { detail: { message } }))
}

export function emitAuthExpired() {
  window.dispatchEvent(new CustomEvent('auth:expired'))
}

// 响应拦截：401 清理登录态；403/404/500 提示错误
http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    if (status === 401) {
      const url = error?.config?.url || ''
      const isAuthAttempt = url.includes('/api/login') || url.includes('/api/register')
      if (!isAuthAttempt) {
        localStorage.removeItem(TOKEN_KEY)
        localStorage.removeItem(USERNAME_KEY)
        emitAuthExpired()
      }
    } else if (status === 403 || status === 404 || status === 500) {
      const fallback = status === 404 ? '接口不存在' : status === 403 ? '没有权限' : '服务器错误'
      emitApiError(getErrorMessage(error, fallback))
    }
    error.message = getErrorMessage(error)
    return Promise.reject(error)
  }
)

export function get(url, config = {}) {
  return http.get(url, config)
}

export function post(url, data, config = {}) {
  return http.post(url, data, config)
}

export default http
