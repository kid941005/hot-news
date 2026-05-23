<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import axios from 'axios'

const API_URL = ''  // 通过代理访问

// 状态
const currentUser = ref(localStorage.getItem('username') || null)
const token = ref(localStorage.getItem('token') || null)
const news = ref([])
const newsByKeyword = ref({})  // 按关键词分组的新闻
const newsByPlatform = ref({})  // 按平台分组的新闻
const platformOptions = ref([])
const loading = ref(false)
const showLogin = ref(false)
const showAccount = ref(false)

// 刷新控制
const lastRefreshTime = ref(0)  // 上次刷新时间戳
const REFRESH_INTERVAL = 20 * 60 * 1000  // 20分钟自动刷新
const MIN_REFRESH_INTERVAL = 5 * 60 * 1000  // 5分钟最低间隔
let autoRefreshTimer = null  // 定时器

// 标签相关
const currentTag = ref(null)  // 当前选中的标签
const tags = ref(['工作', '生活', '科技'])  // 标签列表
const keywordTags = ref({})  // {tag: [keywords]}
const editingTag = ref(null)  // 当前编辑的标签
const editingKeywords = ref('')  // 编辑中的关键词（字符串格式）
const lastRefresh = ref('')  // 上次刷新时间
const renamingTag = ref(null)  // 正在重命名的标签
const tempRenameName = ref('')  // 重命名时的临时名称

// 表单
const username = ref('')
const password = ref('')

// 新标签
const newTag = ref('')

// 配置
const config = ref({
  keywords: [],
  blocked_keywords: [],
  platforms: [],
  push_enabled: false,
  push_channel: 'feishu',
  push_webhook: '',
  push_cron: '0 */4 * * *'
})

// 推送状态
const pushLoading = ref(false)
const pushMessage = ref('')
const lastPushTime = ref(null)

// cron 预设
const cronPresets = [
  { label: '每 2 小时', value: '0 */2 * * *' },
  { label: '每 4 小时', value: '0 */4 * * *' },
  { label: '每 6 小时', value: '0 */6 * * *' },
  { label: '每 8 小时', value: '0 */8 * * *' },
  { label: '每天 3 次 (8,12,18)', value: '0 8,12,18 * * *' },
  { label: '每天 2 次 (9,21)', value: '0 9,21 * * *' },
  { label: '每天 1 次 (9:00)', value: '0 9 * * *' },
]

function formatDisplayTime(item) {
  if (item.pub_time) {
    return `发布时间 ${item.pub_time}`
  }
  if (item.created_at) {
    return `获取时间 ${new Date(item.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })}`
  }
  return ''
}

function selectCronPreset(event) {
  config.value.push_cron = event.target.value
}
const newsCount = computed(() => {
  if (currentTag.value === null) {
    return Object.values(newsByPlatform.value).reduce((sum, items) => sum + items.length, 0)
  }
  return Object.values(newsByKeyword.value).reduce((sum, items) => sum + items.length, 0)
})

// 请求头
function getAuthHeader() {
  return token.value ? { headers: { Authorization: `Bearer ${token.value}` } } : {}
}

// 加载平台列表
async function loadPlatforms() {
  try {
    const res = await axios.get(`${API_URL}/api/platforms`)
    if (res.data.success) {
      platformOptions.value = res.data.platforms || []
    }
  } catch (e) {
    console.error(e)
  }
}

// 加载标签
async function loadTags() {
  try {
    const res = await axios.get(`${API_URL}/api/tags`, getAuthHeader())
    if (res.data.success) {
      tags.value = res.data.tags || ['工作', '生活', '科技']
      keywordTags.value = res.data.keyword_tags || {}
    }
  } catch (e) {
    console.error(e)
  }
}

// 加载配置
async function loadConfig() {
  try {
    const res = await axios.get(`${API_URL}/api/config`, getAuthHeader())
    if (res.data.success) {
      config.value = {
        keywords: (res.data.config.keywords || []).join(', '),
        blocked_keywords: (res.data.config.blocked_keywords || []).join(', '),
        platforms: res.data.config.platforms || [],
        keyword_tags: res.data.config.keyword_tags || {},
        push_enabled: res.data.config.push_enabled || false,
        push_channel: res.data.config.push_channel || 'feishu',
        push_webhook: res.data.config.push_webhook || '',
        push_cron: res.data.config.push_cron || '0 */4 * * *'
      }
      keywordTags.value = res.data.config.keyword_tags || {}
      lastPushTime.value = res.data.config.last_push_at || null
    }
  } catch (e) {
    console.error(e)
  }
}

// 加载新闻
async function loadNews() {
  loading.value = true
  try {
    // 当currentTag为null时，获取按平台分组的数据；否则按标签筛选
    if (currentTag.value === null) {
      // 全部标签：按平台分组（登录用户按平台筛选）
      const res = await axios.get(`${API_URL}/api/news/by_platform`, getAuthHeader())
      if (res.data.success) {
        newsByPlatform.value = res.data.platforms || {}
        newsByKeyword.value = {}
        news.value = []  // 清空普通列表
      }
    } else {
      // 其他标签：按关键词筛选（需要认证）
      newsByPlatform.value = {}  // 清空分组数据
      newsByKeyword.value = {}
      const authHeader = getAuthHeader()
      if (token.value) {
        const res = await axios.get(`${API_URL}/api/news`, { 
          ...authHeader, 
          params: { tag: currentTag.value }
        })
        if (res.data.success) {
          news.value = res.data.news || []
          newsByKeyword.value = res.data.keyword_groups || {}
        }
      } else {
        // 未登录时获取所有数据
        const res = await axios.get(`${API_URL}/api/news?all=true`)
        if (res.data.success) {
          news.value = res.data.news || []
        }
      }
    }
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

// 选择标签
async function selectTag(tag) {
  currentTag.value = tag === currentTag.value ? null : tag
  await loadNews()
}

// 拆分关键词：支持半角逗号、全角逗号、半角分号、全角分号
function splitKeywords(text) {
  return text.split(/[，,；;]/).map(s => s.trim()).filter(s => s)
}

// 编辑标签关键词
function editTagKeywords(tag) {
  editingTag.value = tag
  editingKeywords.value = (keywordTags.value[tag] || []).join(', ')
}

// 保存标签关键词
function saveTagKeywords() {
  if (editingTag.value) {
    // 把字符串转换为数组
    const keywords = splitKeywords(editingKeywords.value)
    keywordTags.value[editingTag.value] = keywords
    editingTag.value = null
  }
}

// 保存配置
async function saveConfig() {
  try {
    // 把字符串转换为数组
    const blocked = typeof config.value.blocked_keywords === 'string'
      ? splitKeywords(config.value.blocked_keywords)
      : config.value.blocked_keywords
    
    const keywords = Array.from(new Set(Object.values(keywordTags.value).flat().map(s => s.trim()).filter(s => s)))

    await axios.post(`${API_URL}/api/config`, {
      keywords: keywords,
      blocked_keywords: blocked,
      platforms: config.value.platforms,
      keyword_tags: keywordTags.value,
      push_enabled: config.value.push_enabled,
      push_channel: config.value.push_channel,
      push_webhook: config.value.push_webhook,
      push_cron: config.value.push_cron
    }, getAuthHeader())
    alert('保存成功')
    showAccount.value = false
    await loadConfig()
    await loadTags()
    await loadNews()
  } catch (e) {
    console.error(e)
    alert('保存失败')
  }
}

// 手动触发推送
async function pushNews() {
  if (!config.value.push_enabled || !config.value.push_webhook) {
    alert('请先启用推送并配置Webhook')
    return
  }
  
  pushLoading.value = true
  pushMessage.value = ''
  try {
    const res = await axios.post(`${API_URL}/api/push`, {}, getAuthHeader())
    if (res.data.success) {
      pushMessage.value = res.data.message || '推送成功'
    } else {
      pushMessage.value = res.data.error || '推送失败'
    }
  } catch (e) {
    pushMessage.value = '推送失败: ' + (e.response?.data?.detail || e.message)
  }
  pushLoading.value = false
}

// 登录
async function login() {
  if (!username.value || !password.value) {
    alert('请输入用户名和密码')
    return
  }
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
      username.value = ''
      password.value = ''
      await loadConfig()
      await loadTags()
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
  if (!username.value || !password.value) {
    alert('请输入用户名和密码')
    return
  }
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
      username.value = ''
      password.value = ''
      await loadConfig()
      await loadTags()
      await loadNews()
    } else {
      alert(res.data.error || '注册失败')
    }
  } catch (e) {
    alert('注册失败')
  }
}

// 退出登录
async function logout() {
  currentUser.value = null
  token.value = null
  currentTag.value = null
  localStorage.removeItem('username')
  localStorage.removeItem('token')
  showAccount.value = false
  showLogin.value = true
  username.value = ''
  password.value = ''
  news.value = []
}

// 切换账号
function switchAccount() {
  showAccount.value = false
  showLogin.value = true
  username.value = ''
  password.value = ''
}

// 保存配置

// 添加自定义标签
function addCustomTag() {
  if (newTag.value && !tags.value.includes(newTag.value)) {
    tags.value.push(newTag.value)
    keywordTags.value[newTag.value] = []  // 新标签初始关键词为空
    newTag.value = ''
  }
}

// 删除标签
function deleteTag(tag) {
  if (confirm(`确定删除标签"${tag}"吗？`)) {
    delete keywordTags.value[tag]
    tags.value = tags.value.filter(t => t !== tag)
    if (currentTag.value === tag) {
      currentTag.value = null
    }
    if (editingTag.value === tag) {
      editingTag.value = null
    }
  }
}

// 重命名标签
function startRenameTag(tag) {
  renamingTag.value = tag
  tempRenameName.value = tag
}

function confirmRenameTag(oldTag) {
  const newTagName = tempRenameName.value.trim()
  if (newTagName && newTagName !== oldTag) {
    // 更新 keywordTags
    const keywords = keywordTags.value[oldTag] || []
    delete keywordTags.value[oldTag]
    keywordTags.value[newTagName] = keywords
    
    // 更新 tags
    const index = tags.value.indexOf(oldTag)
    if (index !== -1) {
      tags.value[index] = newTagName
    }
    
    // 更新 currentTag
    if (currentTag.value === oldTag) {
      currentTag.value = newTagName
    }
  }
  renamingTag.value = null
  tempRenameName.value = ''
}

function cancelRenameTag() {
  renamingTag.value = null
  tempRenameName.value = ''
}

// 刷新缓存（带限流，强制刷新时忽略时间限制）
async function refresh(force = false) {
  const now = Date.now()
  const timeSinceLastRefresh = now - lastRefreshTime.value
  
  // 非强制刷新时检查时间间隔
  if (!force && lastRefreshTime.value > 0 && timeSinceLastRefresh < MIN_REFRESH_INTERVAL) {
    const remainingSeconds = Math.ceil((MIN_REFRESH_INTERVAL - timeSinceLastRefresh) / 1000)
    alert(`刷新太频繁，请等待 ${remainingSeconds} 秒后再试`)
    return
  }
  
  loading.value = true
  try {
    const res = await axios.post(`${API_URL}/api/news/refresh`, {}, getAuthHeader())
    if (res.data.last_refresh) {
      const time = new Date(res.data.last_refresh)
      lastRefresh.value = time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0')
      lastRefreshTime.value = now  // 更新刷新时间戳
      localStorage.setItem('lastRefreshTime', now.toString())
    }
    await loadNews()
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

// 加载刷新时间
async function loadRefreshTime() {
  try {
    const res = await axios.get(`${API_URL}/api/news/refresh`, getAuthHeader())
    if (res.data.last_refresh) {
      const time = new Date(res.data.last_refresh)
      lastRefresh.value = time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0')
      
      // 恢复刷新时间戳（如果本地存储的时间是今天的）
      const savedTime = localStorage.getItem('lastRefreshTime')
      if (savedTime) {
        const savedDate = new Date(parseInt(savedTime))
        const today = new Date()
        if (savedDate.toDateString() === today.toDateString()) {
          lastRefreshTime.value = parseInt(savedTime)
        } else {
          // 新的一天，重置刷新时间
          lastRefreshTime.value = 0
          localStorage.removeItem('lastRefreshTime')
        }
      }
    }
  } catch (e) {
    console.error(e)
  }
}

// 自动刷新定时器
function startAutoRefresh() {
  // 清除已有的定时器
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
  }
  // 每20分钟自动刷新
  autoRefreshTimer = setInterval(() => {
    refresh(false)  // 非强制刷新，会检查时间限制
  }, REFRESH_INTERVAL)
}

// 初始化
onMounted(async () => {
  // 页面加载时不自动刷新，只加载已有数据（刷新操作由用户手动触发或定时任务）
  await loadPlatforms()
  if (currentUser.value && token.value) {
    await loadConfig()
    await loadTags()
  }
  await loadNews()
  await loadRefreshTime()
  
  // 启动自动刷新定时器
  startAutoRefresh()
})

// 组件卸载时清除定时器
onUnmounted(() => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
  }
})
</script>

<template>
  <div class="min-h-screen bg-[linear-gradient(180deg,_#f3f7fc_0%,_#e9f0f8_44%,_#dee8f2_100%)] text-slate-700 relative overflow-hidden">
    <div class="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,_rgba(255,255,255,0.92),_transparent_18%),radial-gradient(circle_at_top_right,_rgba(186,230,253,0.5),_transparent_24%),radial-gradient(circle_at_50%_38%,_rgba(255,255,255,0.28),_transparent_28%),radial-gradient(circle_at_bottom,_rgba(203,213,225,0.62),_transparent_34%)]"></div>
    <div class="pointer-events-none absolute inset-x-0 top-0 h-64 bg-[linear-gradient(180deg,_rgba(255,255,255,0.62),_rgba(255,255,255,0))]"></div>
    <!-- 头部 -->
    <header class="sticky top-0 z-50 safe-area-top border-b border-white/55 bg-[linear-gradient(180deg,_rgba(255,255,255,0.76),_rgba(255,255,255,0.48))] px-4 py-4 text-slate-700 backdrop-blur-2xl shadow-[0_8px_18px_rgba(255,255,255,0.32),0_14px_34px_rgba(148,163,184,0.12)]">
      <div class="max-w-2xl mx-auto flex justify-between items-center">
        <h1 class="text-lg font-semibold">热点资讯</h1>
        <div class="flex gap-2">
          <button 
            v-if="currentUser" 
            @click="showAccount = true"
            class="px-3 py-1.5 rounded-full text-sm border border-white/70 bg-[linear-gradient(180deg,_rgba(255,255,255,0.95),_rgba(255,255,255,0.72))] backdrop-blur-xl shadow-[0_2px_8px_rgba(255,255,255,0.45),0_10px_24px_rgba(148,163,184,0.12)] text-slate-700"
          >
            {{ currentUser }}
          </button>
          <button 
            v-if="currentUser" 
            @click="logout"
            class="px-3 py-1.5 rounded-full text-sm border border-red-200/70 bg-[linear-gradient(180deg,_rgba(254,226,226,0.92),_rgba(252,165,165,0.55))] text-red-700 backdrop-blur-xl shadow-[0_2px_8px_rgba(255,255,255,0.35),0_10px_28px_rgba(248,113,113,0.18)]"
          >
            退出
          </button>
          <button 
            v-if="!currentUser" 
            @click="showLogin = true"
            class="px-3 py-1.5 rounded-full text-sm border border-white/70 bg-[linear-gradient(180deg,_rgba(255,255,255,0.95),_rgba(255,255,255,0.72))] backdrop-blur-xl shadow-[0_2px_8px_rgba(255,255,255,0.45),0_10px_24px_rgba(148,163,184,0.12)] text-slate-700"
          >
            登录
          </button>
        </div>
      </div>
    </header>

    <!-- 标签筛选 -->
    <div v-if="currentUser" class="sticky z-40 safe-area-top border-b border-white/30 bg-[linear-gradient(180deg,_rgba(255,255,255,0.4),_rgba(255,255,255,0.18))] backdrop-blur-2xl" style="top: max(3.5rem, env(safe-area-inset-top))">
      <div class="glass-scroll max-w-2xl mx-auto px-4 py-2 flex gap-2 overflow-x-auto">
        <button 
          @click="selectTag(null)"
            class="px-3 py-1.5 rounded-full text-sm border backdrop-blur-xl shadow-[0_2px_8px_rgba(255,255,255,0.4),0_8px_20px_rgba(148,163,184,0.10)]"
          :class="currentTag === null ? 'bg-[linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(239,246,255,0.74))] text-slate-800 border-white/85 shadow-[0_2px_10px_rgba(255,255,255,0.45),0_10px_26px_rgba(99,102,241,0.16)]' : 'bg-[linear-gradient(180deg,_rgba(255,255,255,0.62),_rgba(255,255,255,0.38))] text-slate-600 border-white/65 hover:bg-[linear-gradient(180deg,_rgba(255,255,255,0.78),_rgba(255,255,255,0.48))]'"
        >
          全部
        </button>
        <button 
          v-for="tag in tags" 
          :key="tag"
          @click="selectTag(tag)"
            class="px-3 py-1.5 rounded-full text-sm border backdrop-blur-xl shadow-[0_2px_8px_rgba(255,255,255,0.4),0_8px_20px_rgba(148,163,184,0.10)]"
          :class="currentTag === tag ? 'bg-[linear-gradient(180deg,_rgba(255,255,255,0.92),_rgba(239,246,255,0.74))] text-slate-800 border-white/85 shadow-[0_2px_10px_rgba(255,255,255,0.45),0_10px_26px_rgba(99,102,241,0.16)]' : 'bg-[linear-gradient(180deg,_rgba(255,255,255,0.62),_rgba(255,255,255,0.38))] text-slate-600 border-white/65 hover:bg-[linear-gradient(180deg,_rgba(255,255,255,0.78),_rgba(255,255,255,0.48))]'"
        >
          {{ tag }}
        </button>
      </div>
    </div>

    <!-- 内容 -->
    <main class="relative max-w-2xl mx-auto p-4">
      <!-- 操作栏 -->
      <div class="mb-5 flex items-center justify-between rounded-2xl border border-white/70 bg-[linear-gradient(180deg,_rgba(255,255,255,0.72),_rgba(255,255,255,0.42))] px-4 py-3 shadow-[0_1px_6px_rgba(255,255,255,0.28),0_16px_38px_rgba(148,163,184,0.14)] backdrop-blur-2xl">
        <div class="flex items-center gap-2">
          <span class="text-slate-700 text-sm">{{ newsCount }} 条{{ currentTag ? ` [${currentTag}]` : '' }}</span>
          <span v-if="lastRefresh" class="text-xs text-slate-500">上次刷新: {{ lastRefresh }}</span>
        </div>
        <button 
          @click="refresh(true)" 
          :disabled="loading"
            class="px-4 py-2 rounded-xl text-sm border border-white/75 bg-[linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(255,255,255,0.74))] text-slate-700 backdrop-blur-xl shadow-[0_2px_10px_rgba(255,255,255,0.4),0_12px_28px_rgba(148,163,184,0.14)] disabled:opacity-50"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <!-- 新闻列表 -->
      <!-- 按平台分组显示（全部标签） -->
      <div v-if="Object.keys(newsByPlatform).length > 0" class="space-y-4">
        <div 
          v-for="(platformNews, platform) in newsByPlatform" 
          :key="platform"
          class="overflow-hidden rounded-2xl border border-white/70 bg-[linear-gradient(180deg,_rgba(255,255,255,0.9),_rgba(244,248,252,0.78))] shadow-[0_1px_8px_rgba(255,255,255,0.26),0_16px_38px_rgba(148,163,184,0.14)] backdrop-blur-2xl"
        >
          <!-- 平台标题 -->
          <div class="px-4 py-3 bg-[linear-gradient(180deg,_rgba(255,255,255,0.62),_rgba(255,255,255,0.38))] border-b border-white/60 flex justify-between items-center">
            <span class="font-medium text-slate-800">{{ platform }}</span>
            <span class="text-xs text-slate-500">{{ platformNews.length }}条</span>
          </div>
          <!-- 平台新闻列表 -->
          <div class="divide-y divide-white/10">
            <div 
              v-for="(item, index) in platformNews" 
              :key="index"
              class="group p-4 transition-all duration-300 hover:bg-[linear-gradient(180deg,_rgba(255,255,255,0.38),_rgba(255,255,255,0.14))]"
            >
              <a 
                :href="item.url" 
                target="_blank"
                class="text-base font-medium text-slate-800 transition-colors group-hover:text-indigo-600" 
              >
                {{ item.title }}
              </a>
              <div class="flex justify-between items-center mt-2">
                <div class="flex gap-1 flex-wrap">
                  <span 
                    v-for="kw in item.matched_keywords" 
                    :key="kw"
                    class="text-xs px-2 py-0.5 rounded-full border border-fuchsia-300/30 bg-fuchsia-100/80 text-fuchsia-700"
                  >
                    {{ kw }}
                  </span>
                </div>
                <span class="text-xs text-slate-400">
                  {{ formatDisplayTime(item) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 普通列表（筛选标签） -->
      <div v-else-if="Object.keys(newsByKeyword).length > 0" class="space-y-4">
        <div 
          v-for="(keywordNews, keyword) in newsByKeyword" 
          :key="keyword"
          class="overflow-hidden rounded-2xl border border-white/70 bg-[linear-gradient(180deg,_rgba(255,255,255,0.9),_rgba(244,248,252,0.78))] shadow-[0_1px_8px_rgba(255,255,255,0.26),0_16px_38px_rgba(148,163,184,0.14)] backdrop-blur-2xl"
        >
          <div class="px-4 py-3 bg-[linear-gradient(180deg,_rgba(255,255,255,0.62),_rgba(255,255,255,0.38))] border-b border-white/60 flex justify-between items-center">
            <span class="font-medium text-slate-800">{{ keyword }}</span>
            <span class="text-xs text-slate-500">{{ keywordNews.length }}条</span>
          </div>
          <div class="divide-y divide-white/10">
            <div 
              v-for="(item, index) in keywordNews" 
              :key="index"
              class="group p-4 transition-all duration-300 hover:bg-[linear-gradient(180deg,_rgba(255,255,255,0.38),_rgba(255,255,255,0.14))]"
            >
              <div class="flex justify-between items-start">
                <a 
                  :href="item.url" 
                  target="_blank"
                  class="text-base font-medium text-slate-700 transition-colors group-hover:text-indigo-600 flex-1"
                >
                  {{ item.title }}
                </a>
                <span 
                  class="text-xs px-2 py-0.5 rounded ml-2 shrink-0"
                  :class="{
                    'bg-red-100/85 text-red-600 border border-red-200': item.platform === '微博',
                    'bg-blue-100/85 text-blue-600 border border-blue-200': item.platform === '百度',
                    'bg-pink-100/85 text-pink-600 border border-pink-200': item.platform === 'B站',
                    'bg-orange-100/85 text-orange-600 border border-orange-200': item.platform === '抖音',
                    'bg-green-100/85 text-green-600 border border-green-200': item.platform === '36kr',
                    'bg-cyan-100/85 text-cyan-600 border border-cyan-200': item.platform === 'IT之家',
                    'bg-indigo-100/85 text-indigo-600 border border-indigo-200': item.platform === '知乎',
                    'bg-yellow-100/85 text-yellow-700 border border-yellow-200': item.platform === '头条',
                    'bg-slate-100/85 text-slate-700 border border-slate-200': !['微博','百度','B站','抖音','36kr','IT之家','知乎','头条'].includes(item.platform)
                  }"
                >
                  {{ item.platform }}
                </span>
              </div>
              <div class="flex justify-between items-center mt-2">
                <div class="flex gap-1 flex-wrap">
                  <span 
                    v-for="kw in item.matched_keywords" 
                    :key="kw"
                    class="text-xs px-2 py-0.5 rounded-full border border-fuchsia-300/30 bg-fuchsia-100/80 text-fuchsia-700"
                  >
                    {{ kw }}
                  </span>
                </div>
                <span class="text-xs text-slate-400">
                  {{ formatDisplayTime(item) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="space-y-3">
        <div 
          v-for="(item, index) in news" 
          :key="index"
          class="group rounded-2xl border border-white/70 bg-[linear-gradient(180deg,_rgba(255,255,255,0.9),_rgba(244,248,252,0.78))] p-4 shadow-[0_1px_8px_rgba(255,255,255,0.26),0_16px_38px_rgba(148,163,184,0.14)] backdrop-blur-2xl transition-all duration-300 hover:-translate-y-0.5 hover:bg-[linear-gradient(180deg,_rgba(255,255,255,0.98),_rgba(238,244,249,0.86))] hover:shadow-[0_2px_10px_rgba(255,255,255,0.3),0_20px_44px_rgba(148,163,184,0.18)]"
        >
          <div class="flex justify-between items-start">
            <a 
              :href="item.url" 
              target="_blank"
              class="text-base font-medium text-slate-700 transition-colors group-hover:text-indigo-600 flex-1"
            >
              {{ item.title }}
            </a>
            <span 
              class="text-xs px-2 py-0.5 rounded ml-2 shrink-0"
              :class="{
                'bg-red-100/85 text-red-600 border border-red-200': item.platform === '微博',
                'bg-blue-100/85 text-blue-600 border border-blue-200': item.platform === '百度',
                'bg-pink-100/85 text-pink-600 border border-pink-200': item.platform === 'B站',
                'bg-orange-100/85 text-orange-600 border border-orange-200': item.platform === '抖音',
                'bg-green-100/85 text-green-600 border border-green-200': item.platform === '36kr',
                'bg-cyan-100/85 text-cyan-600 border border-cyan-200': item.platform === 'IT之家',
                'bg-indigo-100/85 text-indigo-600 border border-indigo-200': item.platform === '知乎',
                'bg-yellow-100/85 text-yellow-700 border border-yellow-200': item.platform === '头条',
                'bg-slate-100/85 text-slate-700 border border-slate-200': !['微博','百度','B站','抖音','36kr','IT之家','知乎','头条'].includes(item.platform)
              }"
            >
              {{ item.platform }}
            </span>
          </div>
          <div class="flex justify-between items-center mt-2">
            <!-- 匹配关键词标签 -->
            <div class="flex gap-1 flex-wrap">
              <span 
                v-for="kw in item.matched_keywords" 
                :key="kw"
                class="text-xs px-2 py-0.5 rounded-full border border-fuchsia-400/20 bg-fuchsia-400/12 text-fuchsia-200"
              >
                {{ kw }}
              </span>
            </div>
            <!-- 发布时间 -->
            <span class="text-xs text-slate-400">
              {{ formatDisplayTime(item) }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="currentTag !== null && Object.keys(newsByKeyword).length === 0 && !loading" class="text-center py-12 text-slate-400">
        暂无匹配的热点资讯
      </div>
      <div v-else-if="currentTag === null && news.length === 0 && Object.keys(newsByPlatform).length === 0 && !loading" class="text-center py-12 text-slate-400">
        暂无匹配的热点资讯
      </div>
    </main>

    <!-- 登录弹窗 -->
    <div v-if="showLogin" class="fixed inset-0 bg-slate-950/70 backdrop-blur-md flex items-center justify-center z-50">
      <div class="glass-scroll relative w-80 mx-4 rounded-[28px] border border-white/70 bg-white/90 p-6 text-slate-700 shadow-[0_24px_80px_rgba(148,163,184,0.16)] backdrop-blur-2xl before:pointer-events-none before:absolute before:inset-x-6 before:top-0 before:h-px before:bg-white/80">
        <h2 class="text-lg font-semibold mb-4">登录/注册</h2>
        <input 
          v-model="username" 
          placeholder="用户名" 
          class="glass-input w-full px-4 py-3 border border-white/60 bg-white/70 rounded-2xl mb-3 text-slate-800 placeholder:text-slate-400" 
        />
        <input 
          v-model="password" 
          type="password" 
          placeholder="密码" 
          class="glass-input w-full px-4 py-3 border border-white/60 bg-white/70 rounded-2xl mb-4 text-slate-800 placeholder:text-slate-400" 
          @keyup.enter="login"
        />
        <button @click="login" class="w-full py-3 rounded-2xl border border-white/70 bg-white/75 text-slate-800 backdrop-blur-xl mb-2">
          登录
        </button>
        <button @click="register" class="w-full py-3 rounded-2xl border border-white/60 bg-white/55 text-slate-700">
          注册
        </button>
        <button @click="showLogin = false" class="w-full py-2 mt-2 text-slate-400 text-sm">
          取消
        </button>
      </div>
    </div>

    <!-- 账号管理弹窗 -->
    <div v-if="showAccount" class="fixed inset-0 bg-slate-950/70 backdrop-blur-md flex items-center justify-center z-50">
      <div class="glass-scroll relative w-80 mx-4 max-h-[80vh] overflow-y-auto rounded-[28px] border border-white/70 bg-white/90 p-6 text-slate-700 shadow-[0_24px_80px_rgba(148,163,184,0.16)] backdrop-blur-2xl before:pointer-events-none before:absolute before:inset-x-6 before:top-0 before:h-px before:bg-white/80">
        <div class="mb-4">
          <div class="text-[11px] font-medium uppercase tracking-[0.18em] text-slate-400">Workspace Settings</div>
          <h2 class="mt-1 text-lg font-semibold text-slate-800">账号管理</h2>
          <div class="mt-1 text-sm text-slate-500">统一管理标签、关键词、平台监控和消息推送。</div>
        </div>
        
        <!-- 切换账号按钮 -->
        <button @click="switchAccount" class="w-full py-2 mb-4 rounded-2xl border border-white/60 bg-[linear-gradient(180deg,_rgba(255,255,255,0.82),_rgba(255,255,255,0.54))] text-slate-700 text-sm shadow-[0_8px_20px_rgba(148,163,184,0.08)]">
          切换账号
        </button>
        
        <!-- 标签关键词管理 -->
        <div class="mb-4">
          <label class="text-sm text-slate-600 block mb-2">标签关键词设置</label>
          <div class="text-xs text-slate-500 mb-2">点击标签设置其关键词</div>
          
          <!-- 标签列表 -->
          <div class="space-y-2 mb-3">
            <div 
              v-for="tag in tags" 
              :key="tag"
              class="rounded-2xl border border-white/60 bg-[linear-gradient(180deg,_rgba(255,255,255,0.78),_rgba(255,255,255,0.48))] p-3 shadow-[0_10px_24px_rgba(148,163,184,0.08)]"
            >
              <div class="flex justify-between items-center mb-1">
                <!-- 显示标签名 -->
                <span v-if="renamingTag !== tag" class="font-medium text-sm text-slate-800">{{ tag }}</span>
                <!-- 重命名输入框 -->
                <div v-else class="flex items-center gap-1">
                  <input 
                    v-model="tempRenameName"
                    @keyup.enter="confirmRenameTag(tag)"
                    class="glass-input font-medium text-sm border border-white/60 bg-white/80 rounded px-1 py-0.5 w-20 text-slate-800"
                  />
                  <button @click="confirmRenameTag(tag)" class="text-green-500">✓</button>
                  <button @click="cancelRenameTag" class="text-gray-500">✕</button>
                </div>
                <!-- 操作按钮 -->
                <div class="flex gap-1">
                  <button 
                    v-if="renamingTag !== tag"
                    @click="startRenameTag(tag)"
                    class="text-xs px-2 py-1 rounded-full border border-blue-200 bg-blue-50/80 text-blue-600"
                  >
                    重命名
                  </button>
                  <button 
                    @click="editTagKeywords(tag)"
                    class="text-xs px-2 py-1 rounded-full border border-indigo-200 bg-indigo-50/80 text-indigo-600"
                  >
                    {{ (keywordTags[tag] || []).length ? '编辑' : '设置' }}
                  </button>
                  <button 
                    v-if="!['工作', '生活', '科技'].includes(tag)"
                    @click="deleteTag(tag)"
                    class="text-xs px-2 py-1 rounded-full border border-red-200 bg-red-50/80 text-red-600"
                  >
                    删除
                  </button>
                </div>
              </div>
              <div v-if="editingTag === tag" class="mt-2">
                <textarea 
                  v-model="editingKeywords"
                  :placeholder="`${tag}标签的关键词，用逗号分隔`"
                  class="glass-input w-full px-2 py-1 border border-white/60 bg-white/80 rounded-xl text-sm text-slate-800 placeholder:text-slate-400"
                  rows="2"
                ></textarea>
                <div class="flex gap-2 mt-1">
                  <button 
                    @click="saveTagKeywords"
                    class="text-xs px-2 py-1 rounded-full border border-white/60 bg-white/80 text-slate-700"
                  >
                    保存
                  </button>
                  <button 
                    @click="editingTag = null"
                    class="text-xs px-2 py-1 rounded-full border border-white/50 bg-white/65 text-slate-500"
                  >
                    取消
                  </button>
                </div>
              </div>
              <div v-else class="text-xs text-slate-500">
                关键词: {{ (keywordTags[tag] || []).join(', ') || '未设置' }}
              </div>
            </div>
          </div>
          
          <!-- 添加新标签 -->
          <div class="flex gap-2">
            <input 
              v-model="newTag" 
              placeholder="新增标签"
              class="glass-input flex-1 px-2 py-1 border border-white/60 bg-white/80 rounded-xl text-sm text-slate-800 placeholder:text-slate-400"
              @keyup.enter="addCustomTag"
            />
            <button @click="addCustomTag" class="px-3 py-1 rounded-xl border border-white/60 bg-white/78 text-slate-700 text-sm shadow-[0_8px_20px_rgba(148,163,184,0.08)]">
              添加
            </button>
          </div>
        </div>
        
        <div class="mb-4">
          <label class="text-sm text-slate-600 block mb-1">屏蔽关键词</label>
          <textarea 
            v-model="config.blocked_keywords" 
            placeholder="不想看到的内容"
            class="glass-input w-full px-3 py-2 border border-white/60 bg-white/80 rounded-2xl text-sm text-slate-800 placeholder:text-slate-400"
            rows="2"
          ></textarea>
        </div>
        
        <div class="mb-4">
          <label class="text-sm text-slate-600 block mb-2">监控平台</label>
          <div class="flex flex-wrap gap-2">
            <label v-for="p in platformOptions" :key="p.id" class="flex items-center gap-2 border border-white/60 bg-white/70 px-3 py-1.5 rounded-full text-sm text-slate-700 shadow-[0_8px_20px_rgba(148,163,184,0.06)]">
              <input type="checkbox" :value="p.id" v-model="config.platforms" class="glass-checkbox">
              {{ p.name }}
            </label>
          </div>
        </div>
        
        <!-- 推送设置 -->
        <div class="mb-4 border-t border-white/40 pt-4">
          <label class="text-sm text-slate-600 block mb-2">📣 推送设置</label>
          
          <div class="mb-3">
            <label class="flex items-center gap-2">
              <input type="checkbox" v-model="config.push_enabled" class="glass-checkbox">
              <span class="text-sm text-slate-700">启用推送</span>
            </label>
          </div>
          
          <div v-if="config.push_enabled" class="space-y-3">
            <div>
              <label class="text-xs text-slate-500 block mb-1">推送渠道</label>
              <select v-model="config.push_channel" class="glass-select w-full px-3 py-2 border border-white/60 bg-white/80 rounded-2xl text-sm text-slate-800">
                <option value="feishu">飞书</option>
                <option value="dingtalk">钉钉</option>
                <option value="bark">Bark</option>
              </select>
            </div>
            
            <div>
              <label class="text-xs text-slate-500 block mb-1">Webhook地址</label>
              <input 
                v-model="config.push_webhook" 
                type="text" 
                placeholder="Webhook地址"
                class="glass-input w-full px-3 py-2 border border-white/60 bg-white/80 rounded-2xl text-sm text-slate-800 placeholder:text-slate-400"
              >
              <div class="text-xs text-slate-500 mt-1">
                如何获取？请查看飞书/钉钉/Bark 的 Webhook 配置文档
              </div>
            </div>

            <div>
              <label class="text-xs text-slate-500 block mb-1">推送规则</label>
              <select
                :value="cronPresets.find(p => p.value === config.push_cron)?.value || ''"
                @change="selectCronPreset"
                class="glass-select w-full px-3 py-2 border border-white/60 bg-white/80 rounded-2xl text-sm mb-2 text-slate-800"
              >
                <option value="">自定义</option>
                <option v-for="p in cronPresets" :key="p.value" :value="p.value">{{ p.label }}</option>
              </select>
              <input
                v-model="config.push_cron"
                type="text"
                placeholder="分 时 日 月 周  (如 0 */4 * * *)"
                class="glass-input w-full px-3 py-2 border border-white/60 bg-white/80 rounded-2xl text-sm font-mono text-slate-800 placeholder:text-slate-400"
              >
              <div class="text-xs text-slate-500 mt-1">cron 表达式：自动按设定规则推送</div>
            </div>

            <div v-if="lastPushTime" class="text-xs text-slate-500 text-center">
              上次推送：{{ new Date(lastPushTime).toLocaleString('zh-CN') }}
            </div>
            
            <button 
              @click="pushNews" 
              :disabled="pushLoading"
              class="w-full py-2 rounded-2xl border border-emerald-200 bg-emerald-50/85 text-emerald-700 text-sm backdrop-blur-xl shadow-[0_8px_20px_rgba(16,185,129,0.08)]"
            >
              {{ pushLoading ? '推送中...' : '📤 立即推送测试' }}
            </button>
            
            <div v-if="pushMessage" class="text-xs text-center" :class="pushMessage.includes('成功') ? 'text-green-600' : 'text-red-500'">
              {{ pushMessage }}
            </div>
          </div>
        </div>
        
        <button @click="saveConfig" class="w-full py-3 rounded-2xl border border-white/60 bg-[linear-gradient(180deg,_rgba(255,255,255,0.96),_rgba(255,255,255,0.72))] text-slate-800 mb-2 shadow-[0_10px_24px_rgba(148,163,184,0.12)]">
          保存
        </button>
        <button @click="showAccount = false" class="w-full py-2 text-slate-400 text-sm">
          取消
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
:global(body) {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background:
    radial-gradient(circle at 12% 10%, rgba(255, 255, 255, 0.95) 0%, rgba(255, 255, 255, 0.05) 30%, transparent 55%),
    radial-gradient(circle at 88% 12%, rgba(219, 234, 254, 0.92) 0%, rgba(219, 234, 254, 0.05) 24%, transparent 48%),
    linear-gradient(180deg, #f8fbff 0%, #eef4fb 100%);
  color: #0f172a;
  min-height: 100vh;
}

body::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 20% 25%, rgba(255, 255, 255, 0.55) 0, transparent 22%),
    radial-gradient(circle at 80% 28%, rgba(191, 219, 254, 0.35) 0, transparent 20%),
    radial-gradient(circle at 50% 78%, rgba(255, 255, 255, 0.4) 0, transparent 24%);
  filter: blur(14px);
  opacity: 0.9;
}

#app {
  position: relative;
  z-index: 1;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  border: 1px solid rgba(255, 255, 255, 0.75);
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.55);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  box-shadow: 0 18px 56px rgba(148, 163, 184, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.84), 0 1px 0 rgba(255, 255, 255, 0.45);
  position: relative;
}

.header::after,
.account-section::after,
.login-modal::after,
.news-item::after,
.tag-item::after,
.tag-card::after,
.config-panel::after,
.push-panel::after,
.modal-content::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: inherit;
  pointer-events: none;
  background: linear-gradient(135deg, rgba(255, 255, 255, 0.35), transparent 38%, rgba(255, 255, 255, 0.08));
}

.header h1 {
  margin: 0;
  font-size: 1.8rem;
  color: #0f172a;
  text-shadow: 0 1px 0 rgba(255, 255, 255, 0.65);
}

.user-info {
  display: flex;
  gap: 12px;
  align-items: center;
}

.user-info button,
.refresh-btn,
.logout-btn,
.login-btn,
.action-btn,
.save-btn,
.push-btn {
  border: 1px solid rgba(191, 219, 254, 0.72);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0.68));
  color: #0f172a;
  box-shadow: 0 10px 24px rgba(148, 163, 184, 0.1), inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.user-info button:hover,
.refresh-btn:hover,
.logout-btn:hover,
.login-btn:hover,
.action-btn:hover,
.save-btn:hover,
.push-btn:hover {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(255, 255, 255, 0.82));
  border-color: rgba(147, 197, 253, 0.92);
  transform: translateY(-1px);
  box-shadow: 0 14px 30px rgba(148, 163, 184, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.96);
}

.account-section,
.login-modal,
.news-item,
.empty-state,
.tag-item,
.tag-card,
.config-panel,
.push-panel,
.modal-content {
  border: 1px solid rgba(255, 255, 255, 0.84);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.62));
  backdrop-filter: blur(26px) saturate(185%);
  -webkit-backdrop-filter: blur(26px) saturate(185%);
  box-shadow: 0 20px 52px rgba(148, 163, 184, 0.14), inset 0 1px 0 rgba(255, 255, 255, 0.9), inset 0 -1px 0 rgba(255, 255, 255, 0.32);
}

.news-item:hover,
.tag-item:hover,
.tag-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 24px 56px rgba(148, 163, 184, 0.18), inset 0 1px 0 rgba(255, 255, 255, 0.94), inset 0 -1px 0 rgba(255, 255, 255, 0.34);
}

.news-meta,
.news-source,
.news-time,
.last-refresh,
.login-info,
.tag-meta,
.empty-state {
  color: #475569;
}

.tag,
.platform-tag,
.keyword-badge {
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.88), rgba(255, 255, 255, 0.7));
  color: #334155;
  border: 1px solid rgba(191, 219, 254, 0.78);
  box-shadow: 0 8px 20px rgba(148, 163, 184, 0.08), inset 0 1px 0 rgba(255, 255, 255, 0.9);
}

.tag.active {
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.98), rgba(224, 242, 254, 0.98));
  color: #1d4ed8;
  border-color: rgba(96, 165, 250, 0.92);
  box-shadow: 0 10px 24px rgba(96, 165, 250, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.modal-content input,
.modal-content textarea,
.modal-content select,
.config-panel input,
.config-panel textarea,
.config-panel select {
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(191, 219, 254, 0.78);
  color: #0f172a;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.92);
}

.modal-content input:focus,
.modal-content textarea:focus,
.modal-content select:focus,
.config-panel input:focus,
.config-panel textarea:focus,
.config-panel select:focus {
  border-color: rgba(96, 165, 250, 0.98);
  box-shadow: 0 0 0 3px rgba(191, 219, 254, 0.36), inset 0 1px 0 rgba(255, 255, 255, 0.94);
}
</style>
