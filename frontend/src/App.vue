<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API_URL = ''  // 通过代理访问

// 状态
const currentUser = ref(localStorage.getItem('username') || null)
const token = ref(localStorage.getItem('token') || null)
const news = ref([])
const loading = ref(false)
const showLogin = ref(false)
const showAccount = ref(false)

// 表单
const username = ref('')
const password = ref('')

// 配置
const config = ref({
  keywords: [],
  blocked_keywords: [],
  platforms: []
})

// 请求头
function getAuthHeader() {
  return token.value ? { headers: { Authorization: `Bearer ${token.value}` } } : {}
}

// 加载配置
async function loadConfig() {
  try {
    const res = await axios.get(`${API_URL}/api/config`, getAuthHeader())
    if (res.data.success) {
      // 数组转字符串（给textarea用）
      config.value = {
        keywords: (res.data.config.keywords || []).join(', '),
        blocked_keywords: (res.data.config.blocked_keywords || []).join(', '),
        platforms: res.data.config.platforms || []
      }
    }
  } catch (e) {
    console.error(e)
  }
}

// 加载新闻
async function loadNews() {
  loading.value = true
  try {
    const res = await axios.get(`${API_URL}/api/news`, getAuthHeader())
    if (res.data.success) {
      news.value = res.data.news
    }
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

// 登录
async function login() {
  try {
    const res = await axios.post(`${API_URL}/api/login`, {
      username: username.value,
      password: password.value
    })
    if (res.data.success) {
      currentUser.value = res.data.username
      token.value = res.data.token
      localStorage.setItem('username', res.data.username)
      localStorage.setItem('token', res.data.token)
      showLogin.value = false
      await loadConfig()
      await loadNews()
    } else {
      alert(res.data.error || '登录失败')
    }
  } catch (e) {
    alert('登录失败')
  }
}

// 注册
async function register() {
  try {
    const res = await axios.post(`${API_URL}/api/register`, {
      username: username.value,
      password: password.value
    })
    if (res.data.success) {
      currentUser.value = res.data.username
      token.value = res.data.token
      localStorage.setItem('username', res.data.username)
      localStorage.setItem('token', res.data.token)
      showLogin.value = false
      await loadConfig()
      await loadNews()
    } else {
      alert(res.data.error || '注册失败')
    }
  } catch (e) {
    alert('注册失败')
  }
}

// 保存配置
async function saveConfig() {
  try {
    // 把字符串转换为数组
    const keywords = typeof config.value.keywords === 'string' 
      ? config.value.keywords.split(',').map(s => s.trim()).filter(s => s)
      : config.value.keywords
    const blocked = typeof config.value.blocked_keywords === 'string'
      ? config.value.blocked_keywords.split(',').map(s => s.trim()).filter(s => s)
      : config.value.blocked_keywords
    
    await axios.post(`${API_URL}/api/config`, {
      keywords: keywords,
      blocked_keywords: blocked,
      platforms: config.value.platforms
    }, getAuthHeader())
    alert('保存成功')
    showAccount.value = false
    await loadNews()
  } catch (e) {
    console.error(e)
    alert('保存失败')
  }
}

// 刷新缓存
async function refresh() {
  loading.value = true
  try {
    await axios.post(`${API_URL}/api/news/refresh`, {}, getAuthHeader())
    await loadNews()
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

// 退出登录
async function logout() {
  currentUser.value = null
  token.value = null
  localStorage.removeItem('username')
  localStorage.removeItem('token')
  showAccount.value = false
  await loadNews()
}

// 初始化
onMounted(async () => {
  await loadConfig()
  await loadNews()
})
</script>

<template>
  <div class="min-h-screen bg-gray-100">
    <!-- 头部 -->
    <header class="bg-gradient-to-r from-indigo-500 to-purple-600 text-white px-4 py-4 sticky top-0 z-50">
      <div class="max-w-2xl mx-auto flex justify-between items-center">
        <h1 class="text-lg font-semibold">热点资讯</h1>
        <button 
          v-if="currentUser" 
          @click="showAccount = true"
          class="px-3 py-1.5 bg-white/20 rounded-full text-sm"
        >
          {{ currentUser }}
        </button>
        <button 
          v-else 
          @click="showLogin = true"
          class="px-3 py-1.5 bg-white/20 rounded-full text-sm"
        >
          登录
        </button>
      </div>
    </header>

    <!-- 内容 -->
    <main class="max-w-2xl mx-auto p-4">
      <!-- 操作栏 -->
      <div class="flex justify-between items-center mb-4">
        <span class="text-gray-500 text-sm">{{ news.length }} 条匹配</span>
        <button 
          @click="refresh" 
          :disabled="loading"
          class="px-4 py-2 bg-indigo-500 text-white rounded-lg text-sm"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <!-- 新闻列表 -->
      <div class="space-y-3">
        <div 
          v-for="(item, index) in news" 
          :key="index"
          class="bg-white p-4 rounded-xl shadow-sm"
        >
          <div class="flex justify-between items-start">
            <a 
              :href="item.url" 
              target="_blank"
              class="text-base font-medium text-gray-800 hover:text-indigo-600 flex-1"
            >
              {{ item.title }}
            </a>
            <span 
              class="text-xs px-2 py-0.5 rounded ml-2"
              :class="{
                'bg-red-100 text-red-600': item.platform === '微博',
                'bg-blue-100 text-blue-600': item.platform === '百度',
                'bg-pink-100 text-pink-600': item.platform === 'B站',
                'bg-orange-100 text-orange-600': item.platform === '抖音',
              }"
            >
              {{ item.platform }}
            </span>
          </div>
        </div>
        
        <div v-if="news.length === 0 && !loading" class="text-center py-12 text-gray-400">
          暂无匹配的热点资讯
        </div>
      </div>
    </main>

    <!-- 登录弹窗 -->
    <div v-if="showLogin" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-2xl p-6 w-80 mx-4">
        <h2 class="text-lg font-semibold mb-4">登录/注册</h2>
        <input 
          v-model="username" 
          placeholder="用户名" 
          class="w-full px-4 py-3 border rounded-xl mb-3"
        />
        <input 
          v-model="password" 
          type="password" 
          placeholder="密码" 
          class="w-full px-4 py-3 border rounded-xl mb-4"
        />
        <button @click="login" class="w-full py-3 bg-indigo-500 text-white rounded-xl mb-2">
          登录
        </button>
        <button @click="register" class="w-full py-3 bg-gray-100 rounded-xl text-gray-600">
          注册
        </button>
        <button @click="showLogin = false" class="w-full py-2 mt-2 text-gray-400 text-sm">
          取消
        </button>
      </div>
    </div>

    <!-- 账号管理弹窗 -->
    <div v-if="showAccount" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-2xl p-6 w-80 mx-4 max-h-[80vh] overflow-y-auto">
        <h2 class="text-lg font-semibold mb-4">账号管理</h2>
        
        <div class="mb-4">
          <label class="text-sm text-gray-500 block mb-1">关注关键词</label>
          <textarea 
            v-model="config.keywords" 
            placeholder="用逗号分隔，如: AI,科技,基金"
            class="w-full px-3 py-2 border rounded-lg text-sm"
            rows="3"
          ></textarea>
        </div>
        
        <div class="mb-4">
          <label class="text-sm text-gray-500 block mb-1">屏蔽关键词</label>
          <textarea 
            v-model="config.blocked_keywords" 
            placeholder="不想看到的内容"
            class="w-full px-3 py-2 border rounded-lg text-sm"
            rows="2"
          ></textarea>
        </div>
        
        <div class="mb-4">
          <label class="text-sm text-gray-500 block mb-2">监控平台</label>
          <div class="flex flex-wrap gap-2">
            <label v-for="p in ['weibo', 'baidu', 'douyin', 'bilibili']" :key="p" class="flex items-center gap-1 bg-gray-100 px-3 py-1 rounded-full text-sm">
              <input type="checkbox" :value="p" v-model="config.platforms">
              {{ p }}
            </label>
          </div>
        </div>
        
        <button @click="saveConfig" class="w-full py-3 bg-indigo-500 text-white rounded-xl mb-2">
          保存
        </button>
        <button @click="showAccount = false" class="w-full py-2 text-gray-400 text-sm">
          关闭
        </button>
      </div>
    </div>
  </div>
</template>
