<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import api, { getErrorMessage } from './api'
import { useToast } from './composables/useToast'
import packageInfo from '../package.json'

const { toasts, showToast, removeToast } = useToast()
const appVersion = packageInfo.version

function readJsonStorage(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || JSON.stringify(fallback))
  } catch (e) {
    localStorage.removeItem(key)
    return fallback
  }
}

function clearLoginState() {
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

function handleRequestError(e) {
  // 403/404/500 已由 api 拦截器统一提示，这里避免重复 toast
  if (![403, 404, 500].includes(e?.response?.status)) {
    showToast(getErrorMessage(e), 'error')
  }
  console.error(e)
}

// 状态
const currentUser = ref(localStorage.getItem('username') || null)
const token = ref(localStorage.getItem('token') || null)
const news = ref([])
const newsByKeyword = ref({})  // 按关键词分组的新闻
const newsByPlatform = ref({})  // 按平台分组的新闻
const platformOptions = ref([])
const platformOrder = ref(readJsonStorage('platformOrder', []))
const draggingPlatform = ref(null)
const allViewMode = ref('hot')
const loading = ref(false)
const refreshingPlatform = ref(null)
const refreshState = ref({ last_refresh: null, refreshing: false, stale: false })
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
const draggingTag = ref(null)

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

const defaultPlatformClass = 'liquid-badge text-primary'
const platformMeta = {
  '微博热搜': { logo: '微', icon: 'https://www.google.com/s2/favicons?sz=64&domain=weibo.com', class: 'bg-red-100/85 text-red-600 border border-red-200' },
  '微博': { logo: '微', icon: 'https://www.google.com/s2/favicons?sz=64&domain=weibo.com', class: 'bg-red-100/85 text-red-600 border border-red-200' },
  '百度': { logo: '百', icon: 'https://www.google.com/s2/favicons?sz=64&domain=baidu.com', class: 'bg-blue-100/85 text-blue-600 border border-blue-200' },
  'B站': { logo: 'B', icon: 'https://www.google.com/s2/favicons?sz=64&domain=bilibili.com', class: 'bg-pink-100/85 text-pink-600 border border-pink-200' },
  'B站热门视频': { logo: 'B', icon: 'https://www.google.com/s2/favicons?sz=64&domain=bilibili.com', class: 'bg-pink-100/85 text-pink-600 border border-pink-200' },
  'B站排行榜': { logo: 'B', icon: 'https://www.google.com/s2/favicons?sz=64&domain=bilibili.com', class: 'bg-pink-100/85 text-pink-600 border border-pink-200' },
  '抖音': { logo: '抖', icon: 'https://www.google.com/s2/favicons?sz=64&domain=douyin.com', class: 'bg-orange-100/85 text-orange-600 border border-orange-200' },
  '知乎': { logo: '知', icon: 'https://www.google.com/s2/favicons?sz=64&domain=zhihu.com', class: 'bg-indigo-100/85 text-indigo-600 border border-indigo-200' },
  '头条': { logo: '头', icon: 'https://www.google.com/s2/favicons?sz=64&domain=toutiao.com', class: 'bg-yellow-100/85 text-yellow-700 border border-yellow-200' },
  'IT之家': { logo: 'IT', icon: 'https://www.google.com/s2/favicons?sz=64&domain=ithome.com', class: 'bg-cyan-100/85 text-cyan-600 border border-cyan-200' },
  '36Kr快讯': { logo: '快', icon: 'https://www.google.com/s2/favicons?sz=64&domain=36kr.com' },
  '36Kr热榜': { logo: '36', icon: 'https://www.google.com/s2/favicons?sz=64&domain=36kr.com', class: 'bg-green-100/85 text-green-600 border border-green-200' },
  '雪球热门股票': { logo: '雪', icon: 'https://www.google.com/s2/favicons?sz=64&domain=xueqiu.com', class: 'bg-sky-100/85 text-sky-600 border border-sky-200' },
  '快手': { logo: '快', icon: 'https://www.google.com/s2/favicons?sz=64&domain=kuaishou.com', class: 'bg-orange-100/85 text-orange-600 border border-orange-200' },
  '36kr': { logo: '36', icon: 'https://www.google.com/s2/favicons?sz=64&domain=36kr.com', class: 'bg-green-100/85 text-green-600 border border-green-200' },
  'GitHub': { logo: 'GH', icon: 'https://www.google.com/s2/favicons?sz=64&domain=github.com' },
  '财联社': { logo: '财', icon: 'https://www.google.com/s2/favicons?sz=64&domain=cls.cn' },
  '金十数据': { logo: '金', icon: 'https://www.google.com/s2/favicons?sz=64&domain=jin10.com' },
  '联合早报': { logo: '早', icon: 'https://www.google.com/s2/favicons?sz=64&domain=zaobao.com' },
  '格隆汇': { logo: '格', icon: 'https://www.google.com/s2/favicons?sz=64&domain=gelonghui.com' },
  '法布财经': { logo: '法', icon: 'https://www.google.com/s2/favicons?sz=64&domain=fastbull.com' },
  '远景论坛': { logo: '远', icon: 'https://www.google.com/s2/favicons?sz=64&domain=pcbeta.com' },
  'Solidot': { logo: 'So', icon: 'https://www.google.com/s2/favicons?sz=64&domain=solidot.org' },
  'AIHOT': { logo: 'AI', icon: 'https://www.google.com/s2/favicons?sz=64&domain=aihot.virxact.com' },
  'Product Hunt': { logo: 'PH', icon: 'https://www.google.com/s2/favicons?sz=64&domain=producthunt.com' },
  '虫部落': { logo: '虫', icon: 'https://www.google.com/s2/favicons?sz=64&domain=chongbuluo.com' },
  '华尔街见闻': { logo: '华', icon: 'https://www.google.com/s2/favicons?sz=64&domain=wallstreetcn.com' },
  '澎湃': { logo: '澎', icon: 'https://www.google.com/s2/favicons?sz=64&domain=thepaper.cn' },
  '凤凰': { logo: '凤', icon: 'https://www.google.com/s2/favicons?sz=64&domain=ifeng.com' },
  '少数派': { logo: '少', icon: 'https://www.google.com/s2/favicons?sz=64&domain=sspai.com' },
  '腾讯新闻': { logo: '腾', icon: '/icons/tencent.png' },
  '靠谱新闻': { logo: '靠', icon: '/icons/kaopu.png' },
  '参考消息': { logo: '参', icon: '/icons/cankaoxiaoxi.png' },
  '虎扑': { logo: '虎', icon: '/icons/hupu.png' },
  '百度贴吧': { logo: '吧', icon: '/icons/tieba.png' }
}

function getPlatformClass(platform) {
  return platformMeta[platform]?.class || defaultPlatformClass
}

function getPlatformLogo(platform) {
  return platformMeta[platform]?.logo || platform?.slice(0, 2) || '站'
}

function getPlatformLogoUrl(platform) {
  return platformMeta[platform]?.icon || ''
}

function getPlatformId(platform) {
  return platformOptions.value.find(item => item.name === platform)?.id || platform
}

function formatHotDisplayTime(item, platformNews = []) {
  if (platformNews.some(news => news.pub_time)) {
    return item.pub_time ? `发布时间 ${item.pub_time}` : ''
  }
  if (item.created_at) {
    return `抓取时间 ${new Date(item.created_at).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', hour12: false })}`
  }
  return ''
}

function getRelativeTimeText(date) {
  const diff = Date.now() - date.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)
  if (seconds < 60) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function getRealtimeDate(item) {
  const pubTime = (item.pub_time || '').trim()
  if (pubTime) {
    if (pubTime === '刚刚') return new Date()
    const relative = pubTime.match(/^(\d+)\s*(秒|分钟|小时|天)前$/)
    if (relative) {
      const value = Number(relative[1])
      const unit = relative[2]
      const ms = unit === '秒' ? value * 1000 : unit === '分钟' ? value * 60 * 1000 : unit === '小时' ? value * 60 * 60 * 1000 : value * 24 * 60 * 60 * 1000
      return new Date(Date.now() - ms)
    }
    const timeOnly = pubTime.match(/^(\d{1,2}):(\d{2})$/)
    if (timeOnly) {
      const date = new Date()
      date.setHours(Number(timeOnly[1]), Number(timeOnly[2]), 0, 0)
      if (date.getTime() - Date.now() > 60 * 1000) date.setDate(date.getDate() - 1)
      return date
    }
    const parsed = new Date(pubTime.replace(/-/g, '/'))
    if (!Number.isNaN(parsed.getTime())) return parsed
  }
  const fallback = item.updated_at || item.created_at
  if (!fallback) return null
  const date = new Date(fallback)
  return Number.isNaN(date.getTime()) ? null : date
}

function formatRelativeTime(item) {
  const date = getRealtimeDate(item)
  return date ? getRelativeTimeText(date) : ''
}

function formatDisplayTime(item) {
  return formatRelativeTime(item)
}

function selectCronPreset(event) {
  config.value.push_cron = event.target.value
}
const newsCount = computed(() => {
  if (currentTag.value === null) {
    return currentPlatformNews.value.reduce((sum, [, items]) => sum + items.length, 0)
  }
  return Object.values(newsByKeyword.value).reduce((sum, items) => sum + items.length, 0)
})

function isRealtimePlatform(platform) {
  return realtimePlatformSet.value.has(platform)
}

const realtimePlatformSet = computed(
  () => new Set(platformOptions.value.filter(p => p.realtime).map(p => p.name))
)

function getItemTimestamp(item) {
  const date = getRealtimeDate(item)
  return date ? date.getTime() : 0
}

const currentPlatformNews = computed(() => {
  const entries = Object.entries(newsByPlatform.value).filter(([platform]) => allViewMode.value === 'realtime' ? isRealtimePlatform(platform) : !isRealtimePlatform(platform))
  const order = platformOrder.value
  return entries
    .map(([platform, items]) => {
      const sortedItems = allViewMode.value === 'realtime'
        ? [...items].sort((a, b) => getItemTimestamp(b) - getItemTimestamp(a))
        : items
      return [platform, sortedItems]
    })
    .sort(([a], [b]) => {
      const ai = order.indexOf(a)
      const bi = order.indexOf(b)
      if (ai === -1 && bi === -1) return 0
      if (ai === -1) return 1
      if (bi === -1) return -1
      return ai - bi
    })
})

const orderedPlatformEntries = computed(() => currentPlatformNews.value)
const keywordGroupEntries = computed(() => Object.entries(newsByKeyword.value))
const hasKeywordGroups = computed(() => keywordGroupEntries.value.length > 0)

function ensurePlatformOrder() {
  const all = Object.keys(newsByPlatform.value)
  const merged = [
    ...platformOrder.value.filter(p => all.includes(p)),
    ...all.filter(p => !platformOrder.value.includes(p)),
  ]
  platformOrder.value = merged
  localStorage.setItem('platformOrder', JSON.stringify(merged))
}

function movePlatform(targetPlatform) {
  if (!draggingPlatform.value || draggingPlatform.value === targetPlatform) return
  const current = [...platformOrder.value]
  const from = current.indexOf(draggingPlatform.value)
  const to = current.indexOf(targetPlatform)
  if (from === -1 || to === -1) return
  current.splice(to, 0, current.splice(from, 1)[0])
  platformOrder.value = current
  localStorage.setItem('platformOrder', JSON.stringify(current))
}

function moveTag(targetTag) {
  if (!draggingTag.value || draggingTag.value === targetTag) return
  const current = [...tags.value]
  const from = current.indexOf(draggingTag.value)
  const to = current.indexOf(targetTag)
  if (from === -1 || to === -1) return
  current.splice(to, 0, current.splice(from, 1)[0])
  tags.value = current
  keywordTags.value = Object.fromEntries(current.map(tag => [tag, keywordTags.value[tag] || []]))
}

// 加载平台列表
async function loadPlatforms() {
  try {
    const res = await api.get('/api/platforms')
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
    const res = await api.get('/api/tags')
    if (res.data.success) {
      tags.value = res.data.tags || ['工作', '生活', '科技']
      keywordTags.value = res.data.keyword_tags || {}
    }
  } catch (e) {
    handleRequestError(e)
  }
}

// 加载配置
async function loadConfig() {
  try {
    const res = await api.get('/api/config')
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
    handleRequestError(e)
  }
}

// 加载新闻
function applyRefreshState(state) {
  if (!state) return
  refreshState.value = {
    last_refresh: state.last_refresh || null,
    refreshing: !!state.refreshing,
    stale: !!state.stale,
    stale_platforms: state.stale_platforms || [],
    sources: state.sources || {},
  }
  if (state.last_refresh) {
    const time = new Date(state.last_refresh)
    if (!Number.isNaN(time.getTime())) {
      lastRefresh.value = time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0')
    }
  }
}

function formatClockText(value) {
  if (!value) return ''
  const time = new Date(value)
  if (Number.isNaN(time.getTime())) return ''
  return time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0')
}

function platformSource(platform) {
  const id = getPlatformId(platform)
  return (refreshState.value.sources || {})[id] || null
}

// 每个平台卡片显示该平台真实的最近更新时间/失败状态，替代全局时间
function platformStatusText(platform) {
  const src = platformSource(platform)
  if (!src) return lastRefresh.value ? `更新于 ${lastRefresh.value}` : ''
  const fetchTime = formatClockText(src.last_fetch)
  const successTime = formatClockText(src.last_success_at || src.last_fetch)
  // 本次失败/空结果但库中仍有旧数据：继续展示旧数据，并明确标注“可能滞后”
  if (src.status === 'error') {
    if (src.has_cache) return successTime ? `更新失败 · 数据可能滞后（${successTime} 更新）` : '更新失败 · 展示旧数据'
    return fetchTime ? `更新失败 ${fetchTime}` : '更新失败'
  }
  if (src.status === 'empty') {
    if (src.has_cache) return successTime ? `数据可能滞后 · 更新于 ${successTime}` : '数据可能滞后'
    return fetchTime ? `暂无数据 ${fetchTime}` : '暂无数据'
  }
  if (src.status === 'missing') return '暂无数据'
  return successTime ? `更新于 ${successTime}` : ''
}

async function loadNews(silent = false) {
  if (!silent) loading.value = true
  try {
    // 当currentTag为null时，获取按平台分组的数据；否则按标签筛选
    if (currentTag.value === null) {
      // 全部标签：按平台分组（登录用户按平台筛选）
      const res = await api.get('/api/news/by_platform', {
        params: allViewMode.value === 'realtime' ? { sort: 'timeline' } : {}
      })
      if (res.data.success) {
        newsByPlatform.value = res.data.platforms || {}
        ensurePlatformOrder()
        newsByKeyword.value = {}
        news.value = []  // 清空普通列表
        applyRefreshState(res.data)
      }
    } else {
      // 其他标签：按关键词筛选（需要认证）
      newsByPlatform.value = {}  // 清空分组数据
      newsByKeyword.value = {}
      if (token.value) {
        const res = await api.get('/api/news', {
          params: { tag: currentTag.value }
        })
        if (res.data.success) {
          news.value = res.data.news || []
          newsByKeyword.value = res.data.keyword_groups || {}
          applyRefreshState(res.data)
        }
      } else {
        // 未登录时回到公开的按平台数据
        currentTag.value = null
        const res = await api.get('/api/news/by_platform')
        if (res.data.success) {
          newsByPlatform.value = res.data.platforms || {}
          ensurePlatformOrder()
          news.value = []
          applyRefreshState(res.data)
        }
      }
    }
  } catch (e) {
    if (silent) {
      console.error(e)
    } else {
      handleRequestError(e)
    }
  } finally {
    if (!silent) loading.value = false
  }
}

// 选择标签
async function selectTag(tag) {
  currentTag.value = tag === currentTag.value ? null : tag
  await loadNews()
}

async function selectAllView(mode) {
  currentTag.value = null
  allViewMode.value = mode
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

    await api.post('/api/config', {
      keywords: keywords,
      blocked_keywords: blocked,
      platforms: config.value.platforms,
      keyword_tags: keywordTags.value,
      push_enabled: config.value.push_enabled,
      push_channel: config.value.push_channel,
      push_webhook: config.value.push_webhook,
      push_cron: config.value.push_cron
    })
    showToast('保存成功', 'success')
    showAccount.value = false
    await loadConfig()
    await loadTags()
    await loadNews()
  } catch (e) {
    console.error(e)
    showToast(getErrorMessage(e, '保存失败'), 'error')
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
    const res = await api.post('/api/push', {})
    if (res.data.success) {
      pushMessage.value = res.data.message || '推送成功'
    } else {
      pushMessage.value = res.data.error || '推送失败'
    }
  } catch (e) {
    pushMessage.value = '推送失败: ' + getErrorMessage(e, '推送失败')
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
    const res = await api.post('/api/login', {
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
    alert(getErrorMessage(e, '登录失败'))
  }
}

// 注册
async function register() {
  if (!username.value || !password.value) {
    alert('请输入用户名和密码')
    return
  }
  try {
    const res = await api.post('/api/register', {
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
    alert(getErrorMessage(e, '注册失败'))
  }
}

// 退出登录
async function logout() {
  try {
    await api.post('/api/logout', {})
  } catch (e) {
    console.error(e)
  }
  clearLoginState()
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
  const tag = newTag.value.trim()
  if (tag && !tags.value.includes(tag)) {
    tags.value.push(tag)
    keywordTags.value[tag] = []  // 新标签初始关键词为空
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
    keywordTags.value = Object.fromEntries(tags.value.map(tag => [tag, keywordTags.value[tag] || []]))
    
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
    showToast(`刷新太频繁，请等待 ${remainingSeconds} 秒后再试`, 'info')
    return
  }
  
  loading.value = true
  try {
    const res = await api.post('/api/news/refresh', {})
    if (!res.data.success) {
      showToast(res.data.error || '刷新失败', 'error')
      return
    }
    if (res.data.last_refresh) {
      const time = new Date(res.data.last_refresh)
      lastRefresh.value = time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0')
      lastRefreshTime.value = now  // 更新刷新时间戳
      localStorage.setItem('lastRefreshTime', now.toString())
    }
    await loadNews()
  } catch (e) {
    console.error(e)
    showToast(getErrorMessage(e, '刷新失败'), 'error')
  } finally {
    loading.value = false
  }
}

async function refreshPlatform(platform) {
  if (refreshingPlatform.value) return
  const now = Date.now()
  refreshingPlatform.value = platform
  try {
    const res = await api.post('/api/news/refresh', {}, {
      params: { platform: getPlatformId(platform) }
    })
    if (!res.data.success) {
      showToast(res.data.error || '刷新失败', 'error')
      return
    }
    if (res.data.last_refresh) {
      const time = new Date(res.data.last_refresh)
      lastRefresh.value = time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0')
      lastRefreshTime.value = now
      localStorage.setItem('lastRefreshTime', now.toString())
    }
    await loadNews()
  } catch (e) {
    handleRequestError(e)
  } finally {
    refreshingPlatform.value = null
  }
}

// 加载刷新时间
async function loadRefreshTime() {
  try {
    const res = await api.get('/api/news/refresh')
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

// 静默轮询：后台刷新中 5s 一次，空闲 60s 一次，不打断用户操作
let pollTimer = null

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

function startPolling() {
  stopPolling()
  const interval = refreshState.value.refreshing ? 5000 : 60000
  pollTimer = setInterval(() => {
    silentReload()
  }, interval)
}

async function silentReload() {
  if (loading.value || refreshingPlatform.value) return
  await loadNews(true)
}

// 后台刷新完成后自动切换回低频轮询
watch(() => refreshState.value.refreshing, () => startPolling())

// 初始化
function onAuthExpired() {
  clearLoginState()
  showToast('登录已过期，请重新登录', 'error')
}

function onApiError(e) {
  const message = e?.detail?.message
  if (message) {
    showToast(message, 'error')
  }
}

onMounted(async () => {
  window.addEventListener('auth:expired', onAuthExpired)
  window.addEventListener('api:error', onApiError)
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
  startPolling()
})

// 组件卸载时清除定时器
onUnmounted(() => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer)
  }
  stopPolling()
  window.removeEventListener('auth:expired', onAuthExpired)
  window.removeEventListener('api:error', onApiError)
})
</script>

<template>
  <div class="liquid-app min-h-screen relative overflow-hidden pb-[max(1rem,env(safe-area-inset-bottom))]">
    <div class="liquid-aurora pointer-events-none absolute inset-0"></div>
    <div class="liquid-top-sheen pointer-events-none absolute inset-x-0 top-0 h-64"></div>
    <!-- 头部 -->
    <header class="liquid-header sticky top-0 z-50 safe-area-top px-5 py-3 sm:px-4 sm:py-4">
      <div class="max-w-6xl mx-auto flex items-center justify-between gap-3 sm:gap-4">
        <div class="min-w-0 flex-1">
          <h1 class="text-primary-strong text-base font-semibold tracking-tight sm:text-lg">热点资讯</h1>
          <p class="text-secondary mt-1 text-xs sm:text-sm">
            <span v-if="loading">正在刷新中</span>
            <span v-else-if="refreshState.refreshing">正在后台刷新</span>
            <span v-else-if="refreshState.last_refresh">最后刷新：{{ lastRefresh }}</span>
            <span v-else>暂无刷新记录</span>
            <span v-if="refreshState.stale" class="liquid-chip-accent ml-2 rounded-full px-2 py-0.5 text-[11px]" :title="'过期平台数：' + (refreshState.stale_platforms || []).length">部分数据已过期</span>
          </p>
        </div>
        <div class="flex shrink-0 flex-wrap justify-end gap-2">
          <button
            v-if="currentUser" 
            @click="showAccount = true"
            class="liquid-chip px-3 py-1.5 rounded-full text-sm text-primary"
          >
            {{ currentUser }}
          </button>
          <button
            v-if="currentUser" 
            @click="logout"
            class="liquid-chip-danger px-3 py-1.5 rounded-full text-sm"
          >
            退出
          </button>
          <button
            v-if="!currentUser" 
            @click="showLogin = true"
            class="liquid-chip px-3 py-1.5 rounded-full text-sm text-primary"
          >
            登录
          </button>
        </div>
      </div>
    </header>

    <!-- 标签筛选 -->
    <div v-if="currentUser" class="liquid-subheader sticky z-40 safe-area-top" style="top: max(3rem, env(safe-area-inset-top))">
      <div class="glass-scroll max-w-6xl mx-auto px-5 py-1.5 flex gap-2 overflow-x-auto whitespace-nowrap sm:px-4 sm:py-2">
        <button
          @click="selectAllView('hot')"
            class="px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-200"
          :class="currentTag === null && allViewMode === 'hot' ? 'liquid-chip-active' : 'liquid-chip-inactive'"
        >
          热榜
        </button>
        <button
          @click="selectAllView('realtime')"
            class="px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-200"
          :class="currentTag === null && allViewMode === 'realtime' ? 'liquid-chip-active' : 'liquid-chip-inactive'"
        >
          实时
        </button>
        <button
          v-for="tag in tags" 
          :key="tag"
          @click="selectTag(tag)"
            class="px-3.5 py-1.5 rounded-full text-sm font-medium transition-all duration-200"
          :class="currentTag === tag ? 'liquid-chip-active' : 'liquid-chip-inactive'"
        >
          {{ tag }}
        </button>
      </div>
    </div>

    <!-- 内容 -->
    <main class="relative max-w-6xl mx-auto px-5 py-5 sm:px-4 sm:py-6">
      <!-- 操作栏 -->
      <div class="liquid-panel mb-5 flex flex-col gap-3 rounded-[1.35rem] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div class="flex flex-wrap items-center gap-2">
          <span class="text-primary text-sm">{{ newsCount }} 条{{ currentTag ? ` [${currentTag}]` : '' }}</span>
          <span v-if="lastRefresh" class="text-secondary text-xs">上次刷新: {{ lastRefresh }}</span>
        </div>
        <button
          @click="refresh(true)" 
          :disabled="loading"
            class="liquid-chip-active px-4 py-2 rounded-xl text-sm font-medium transition-all duration-200 hover:-translate-y-0.5 disabled:opacity-50"
        >
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>

      <!-- 新闻列表 -->
      <!-- 按平台分组显示（全部标签） -->
      <div v-if="currentTag === null && orderedPlatformEntries.length > 0" class="grid grid-cols-1 gap-4 lg:grid-cols-2 xl:grid-cols-3">
        <div
          v-for="[platform, platformNews] in orderedPlatformEntries"
          :key="platform"
          draggable="true"
          @dragstart="draggingPlatform = platform"
          @dragover.prevent
          @dragenter.prevent="movePlatform(platform)"
          @drop.prevent="movePlatform(platform); draggingPlatform = null"
          @dragend="draggingPlatform = null"
          class="liquid-surface glass-edge-lines flex h-full flex-col overflow-hidden rounded-[1.4rem] lg:min-h-[34rem]"
          :class="draggingPlatform === platform ? 'opacity-60' : ''"
        >
          <!-- 平台标题 -->
          <div class="liquid-card-header px-4 py-3 flex justify-between items-center">
            <div class="flex items-center gap-2.5 min-w-0">
              <span class="liquid-avatar inline-flex h-10 min-w-[2.5rem] items-center justify-center overflow-hidden rounded-2xl px-2.5 text-sm font-bold">
                <img v-if="getPlatformLogoUrl(platform)" :src="getPlatformLogoUrl(platform)" :alt="platform" class="h-5 w-5 object-contain" referrerpolicy="no-referrer" />
                <span v-else>{{ getPlatformLogo(platform) }}</span>
              </span>
              <div class="min-w-0">
                <div class="text-primary-strong text-lg font-bold tracking-tight truncate">{{ platform }}</div>
                <div v-if="platformStatusText(platform)" class="text-[11px] text-tertiary">{{ platformStatusText(platform) }}</div>
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-2">
              <span class="liquid-badge rounded-full px-2.5 py-1 text-xs font-medium">{{ allViewMode === 'realtime' ? '实时源' : '拖拽排序' }} · {{ platformNews.length }}条</span>
              <button
                type="button"
                @click.stop="refreshPlatform(platform)"
                :disabled="refreshingPlatform === platform"
                class="liquid-chip-accent rounded-full px-2.5 py-1 text-xs font-medium transition disabled:opacity-55"
              >
                {{ refreshingPlatform === platform ? '刷新中' : '刷新' }}
              </button>
            </div>
          </div>
          <!-- 平台新闻列表 -->
          <div class="glass-scroll flex-1 lg:max-h-[28rem] lg:overflow-y-auto">
            <!-- 实时模式：时间线风格 -->
            <div v-if="allViewMode === 'realtime'" class="border-s border-divider flex flex-col ml-3 py-2 gap-1">
              <div v-for="item in platformNews" :key="item.id || item.url" class="flex flex-col">
                <span class="flex items-center gap-1 text-tertiary ml-[-1px]">
                  <span class="text-tertiary">-</span>
                  <span class="text-xs text-tertiary">{{ formatRelativeTime(item) }}</span>
                </span>
                <a
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="ml-3 px-1 py-0.5 text-base text-primary hover-bg-subtle rounded transition-all visited:text-tertiary"
                >
                  {{ item.title }}
                </a>
              </div>
            </div>
            <!-- 热榜模式：序号排名风格 -->
            <div v-else class="divide-y divide-divider">
              <div
                v-for="(item, index) in platformNews"
                :key="item.id || item.url"
                class="group p-4 transition-all duration-300 hover-glass"
              >
              <div class="flex items-start gap-3">
                <span
                  class="mt-0.5 inline-flex h-7 min-w-[1.75rem] shrink-0 items-center justify-center rounded-lg text-xs font-semibold shadow-[0_2px_8px_rgba(148,163,184,0.12)]"
                  :class="index === 0
                    ? 'bg-[linear-gradient(180deg,_rgba(254,240,138,0.95),_rgba(250,204,21,0.82))] text-amber-900 border border-amber-200/80'
                    : index === 1
                      ? 'bg-[linear-gradient(180deg,_rgba(226,232,240,0.98),_rgba(203,213,225,0.85))] text-primary border border-slate-200/80'
                      : index === 2
                        ? 'bg-[linear-gradient(180deg,_rgba(253,230,138,0.9),_rgba(251,191,36,0.72))] text-orange-900 border border-orange-200/80'
                        : 'bg-slate-100/70 text-secondary border border-white/65'"
                >
                  {{ index + 1 }}
                </span>
                <div class="min-w-0 flex-1">
                  <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                    <a
                      :href="item.url"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="min-w-0 flex-1 text-base font-medium text-primary-strong transition-colors group-hover-accent"
                    >
                      {{ item.title }}
                    </a>
                  </div>
                  <div class="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div class="flex flex-wrap gap-1">
                      <span
                        v-for="kw in (item.matched_keywords || [])"
                        :key="kw"
                        class="text-sm px-2.5 py-0.5 rounded-full border border-fuchsia-300/30 bg-fuchsia-100/80 text-fuchsia-700"
                      >
                        {{ kw }}
                      </span>
                    </div>
                    <span class="liquid-badge w-fit rounded-full px-2.5 py-1 text-[11px] font-medium text-secondary sm:ml-2">
                      {{ formatHotDisplayTime(item, platformNews) }}
                    </span>
                  </div>
                </div>
              </div>
            </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 普通列表（筛选标签） -->
      <div v-else-if="hasKeywordGroups" class="space-y-4">
        <div 
          v-for="[keyword, keywordNews] in keywordGroupEntries"
          :key="keyword"
          class="liquid-surface glass-edge-lines overflow-hidden rounded-[1.4rem]"
        >
          <div class="liquid-card-header px-4 py-3 flex justify-between items-center">
            <span class="font-medium text-primary-strong">{{ keyword }}</span>
            <span class="text-secondary text-xs">{{ keywordNews.length }}条</span>
          </div>
          <div class="divide-y divide-white/10">
            <div
              v-for="item in keywordNews"
              :key="item.id || item.url"
              class="group p-4 transition-all duration-300 hover-glass"
            >
              <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <a
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="min-w-0 flex-1 text-base font-medium text-primary transition-colors group-hover-accent"
                >
                  {{ item.title }}
                </a>
                <span
                  class="inline-flex w-fit shrink-0 items-center gap-1.5 text-xs px-2 py-1 rounded-full sm:ml-2"
                  :class="getPlatformClass(item.platform)"
                >
                  <span class="inline-flex h-5 min-w-[1.25rem] items-center justify-center overflow-hidden rounded-full bg-slate-50/65 px-1 text-[10px] font-semibold leading-none">
                    <img v-if="getPlatformLogoUrl(item.platform)" :src="getPlatformLogoUrl(item.platform)" :alt="item.platform" class="h-3.5 w-3.5 object-contain" referrerpolicy="no-referrer" />
                    <span v-else>{{ getPlatformLogo(item.platform) }}</span>
                  </span>
                  <span>{{ item.platform }}</span>
                </span>
              </div>
              <div class="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="kw in (item.matched_keywords || [])"
                    :key="kw"
                    class="text-sm px-2.5 py-0.5 rounded-full border border-fuchsia-300/30 bg-fuchsia-100/80 text-fuchsia-700"
                  >
                    {{ kw }}
                  </span>
                </div>
                <span class="liquid-badge w-fit rounded-full px-2.5 py-1 text-[11px] font-medium text-secondary sm:ml-2">
                  {{ formatDisplayTime(item) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="space-y-3">
        <div
          v-for="item in news"
          :key="item.id || item.url"
          class="liquid-surface glass-edge-lines group rounded-[1.4rem] p-4 transition-all duration-300 hover:-translate-y-0.5 hover-glass"
        >
          <div class="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
            <a
              :href="item.url"
              target="_blank"
              rel="noopener noreferrer"
              class="min-w-0 flex-1 text-base font-medium text-primary transition-colors group-hover-accent"
            >
              {{ item.title }}
            </a>
            <span
              class="inline-flex w-fit shrink-0 items-center gap-1.5 text-xs px-2 py-1 rounded-full sm:ml-2"
              :class="getPlatformClass(item.platform)"
            >
              <span class="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-slate-50/65 px-1 text-[10px] font-semibold leading-none">{{ getPlatformLogo(item.platform) }}</span>
              <span>{{ item.platform }}</span>
            </span>
          </div>
          <div class="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <!-- 匹配关键词标签 -->
            <div class="flex flex-wrap gap-1">
              <span
                v-for="kw in (item.matched_keywords || [])"
                :key="kw"
                class="text-sm px-2.5 py-0.5 rounded-full border border-fuchsia-300/30 bg-fuchsia-100/80 text-fuchsia-700"
              >
                {{ kw }}
              </span>
            </div>
            <!-- 发布时间 -->
            <span class="liquid-badge w-fit rounded-full px-2.5 py-1 text-[11px] font-medium text-secondary sm:ml-2">
              {{ formatDisplayTime(item) }}
            </span>
          </div>
        </div>
      </div>

      <div v-if="currentTag !== null && !hasKeywordGroups && news.length === 0 && !loading" class="text-center py-12 text-tertiary">
        暂无匹配的热点资讯
      </div>
      <div v-else-if="currentTag === null && news.length === 0 && Object.keys(newsByPlatform).length === 0 && !loading" class="text-center py-12 text-tertiary">
        暂无匹配的热点资讯
      </div>
    </main>

    <footer class="relative max-w-6xl mx-auto px-4 pb-6 text-center text-secondary text-xs">
      v{{ appVersion }}
    </footer>

    <!-- 登录弹窗 -->
      <div v-if="showLogin" class="liquid-overlay fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="liquid-modal glass-edge-lines glass-scroll relative max-h-[calc(100vh-max(2rem,env(safe-area-inset-top)+env(safe-area-inset-bottom)))] w-full max-w-sm overflow-y-auto rounded-[28px] p-5 text-primary sm:p-6">
        <h2 class="text-lg font-semibold mb-4">登录/注册</h2>
        <input 
          v-model="username" 
          placeholder="用户名" 
          class="liquid-input w-full px-4 py-3 rounded-2xl mb-3 text-primary-strong placeholder:text-tertiary"
        />
        <input 
          v-model="password" 
          type="password" 
          placeholder="密码" 
          class="liquid-input w-full px-4 py-3 rounded-2xl mb-4 text-primary-strong placeholder:text-tertiary"
          @keyup.enter="login"
        />
        <button @click="login" class="liquid-chip-active w-full py-3 rounded-2xl mb-2">
          登录
        </button>
        <button @click="register" class="liquid-chip w-full py-3 rounded-2xl text-primary">
          注册
        </button>
        <button @click="showLogin = false" class="w-full py-2 mt-2 text-tertiary text-sm">
          取消
        </button>
      </div>
    </div>

    <!-- 账号管理弹窗 -->
    <div v-if="showAccount" class="liquid-overlay fixed inset-0 z-50 flex items-center justify-center p-4">
      <div class="liquid-modal glass-edge-lines relative w-full max-w-sm rounded-[30px] text-primary">
        <div class="glass-scroll max-h-[calc(100vh-max(2rem,env(safe-area-inset-top)+env(safe-area-inset-bottom)))] overflow-y-auto px-5 py-5 pr-4 sm:px-6 sm:py-6 sm:pr-5">
        <div class="mb-4">
          <div class="text-[11px] font-medium uppercase tracking-[0.18em] text-tertiary">Workspace Settings</div>
          <h2 class="mt-1 text-lg font-semibold text-primary-strong">账号管理</h2>
          <div class="mt-1 text-sm text-secondary">统一管理标签、关键词、平台监控和消息推送。</div>
        </div>
        
        <!-- 切换账号按钮 -->
        <button @click="switchAccount" class="liquid-chip w-full py-2 mb-4 rounded-2xl text-primary text-sm">
          切换账号
        </button>
        
        <!-- 标签关键词管理 -->
        <div class="liquid-panel mb-4 rounded-2xl p-3">
          <label class="text-sm font-medium text-primary block mb-2">标签关键词设置</label>
          <div class="text-secondary text-xs mb-2">点击标签设置其关键词</div>
          
          <!-- 标签列表 -->
          <div class="space-y-2 mb-3">
            <div 
              v-for="tag in tags" 
              :key="tag"
              draggable="true"
              @dragstart="draggingTag = tag"
              @dragover.prevent
              @dragenter.prevent="moveTag(tag)"
              @drop.prevent="moveTag(tag); draggingTag = null"
              @dragend="draggingTag = null"
              class="liquid-surface rounded-2xl p-3"
              :class="draggingTag === tag ? 'opacity-60' : ''"
            >
              <div class="flex justify-between items-center mb-1">
                <!-- 显示标签名 -->
                <span v-if="renamingTag !== tag" class="font-medium text-sm text-primary-strong">{{ tag }}</span>
                <!-- 重命名输入框 -->
                <div v-else class="flex items-center gap-1">
                  <input 
                    v-model="tempRenameName"
                    @keyup.enter="confirmRenameTag(tag)"
                    class="liquid-input font-medium text-sm rounded px-1 py-0.5 w-20 text-primary-strong"
                  />
                  <button @click="confirmRenameTag(tag)" class="text-green-500">✓</button>
                  <button @click="cancelRenameTag()" class="text-gray-500">✕</button>
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
                  class="liquid-input w-full px-2 py-1 rounded-xl text-sm text-primary-strong placeholder:text-tertiary"
                  rows="2"
                ></textarea>
                <div class="flex gap-2 mt-1">
                  <button
                    @click="saveTagKeywords"
                    class="text-xs px-2 py-1 rounded-full text-primary"
                  >
                    保存
                  </button>
                  <button
                    @click="editingTag = null"
                    class="text-xs px-2 py-1 rounded-full text-secondary"
                  >
                    取消
                  </button>
                </div>
              </div>
              <div v-else class="text-secondary text-xs">
                关键词: {{ (keywordTags[tag] || []).join(', ') || '未设置' }}
              </div>
            </div>
          </div>
          
          <!-- 添加新标签 -->
          <div class="flex gap-2">
            <input 
              v-model="newTag" 
              placeholder="新增标签"
              class="liquid-input flex-1 px-2 py-1 rounded-xl text-sm text-primary-strong placeholder:text-tertiary"
              @keyup.enter="addCustomTag"
            />
            <button @click="addCustomTag" class="px-3 py-1 rounded-xl text-primary text-sm shadow-[0_8px_20px_rgba(148,163,184,0.08)]">
              添加
            </button>
          </div>
        </div>
        
        <div class="liquid-panel mb-4 rounded-2xl p-3">
          <label class="text-sm font-medium text-primary block mb-1">屏蔽关键词</label>
          <textarea 
            v-model="config.blocked_keywords" 
            placeholder="不想看到的内容"
            class="liquid-input w-full px-3 py-2 rounded-2xl text-sm text-primary-strong placeholder:text-tertiary"
            rows="2"
          ></textarea>
        </div>
        
        <div class="liquid-panel mb-4 rounded-2xl p-3">
          <label class="text-sm font-medium text-primary block mb-2">监控平台</label>
          <div class="flex flex-wrap gap-2">
            <label v-for="p in platformOptions" :key="p.id" class="liquid-chip flex items-center gap-2 px-3 py-1.5 rounded-full text-sm text-primary">
              <input type="checkbox" :value="p.id" v-model="config.platforms" class="liquid-checkbox">
              {{ p.name }}
            </label>
          </div>
        </div>
        
        <!-- 推送设置 -->
        <div class="liquid-panel mb-4 rounded-2xl p-3">
          <label class="text-sm font-medium text-primary block mb-2">📣 推送设置</label>
          
          <div class="mb-3">
            <label class="flex items-center gap-2">
              <input type="checkbox" v-model="config.push_enabled" class="liquid-checkbox">
              <span class="text-sm text-primary">启用推送</span>
            </label>
          </div>
          
          <div v-if="config.push_enabled" class="space-y-3">
            <div>
              <label class="text-secondary text-xs block mb-1">推送渠道</label>
              <select v-model="config.push_channel" class="liquid-select w-full px-3 py-2 rounded-2xl text-sm text-primary-strong">
                <option value="feishu">飞书</option>
                <option value="dingtalk">钉钉</option>
                <option value="bark">Bark</option>
              </select>
            </div>
            
            <div>
              <label class="text-secondary text-xs block mb-1">Webhook地址</label>
              <input 
                v-model="config.push_webhook" 
                type="text" 
                placeholder="Webhook地址"
                class="liquid-input w-full px-3 py-2 rounded-2xl text-sm text-primary-strong placeholder:text-tertiary"
              >
              <div class="text-secondary text-xs mt-1">
                如何获取？请查看飞书/钉钉/Bark 的 Webhook 配置文档
              </div>
            </div>

            <div>
              <label class="text-secondary text-xs block mb-1">推送规则</label>
              <select
                :value="cronPresets.find(p => p.value === config.push_cron)?.value || ''"
                @change="selectCronPreset"
                class="liquid-select w-full px-3 py-2 rounded-2xl text-sm mb-2 text-primary-strong"
              >
                <option value="">自定义</option>
                <option v-for="p in cronPresets" :key="p.value" :value="p.value">{{ p.label }}</option>
              </select>
              <input
                v-model="config.push_cron"
                type="text"
                placeholder="分 时 日 月 周  (如 0 */4 * * *)"
                class="liquid-input w-full px-3 py-2 rounded-2xl text-sm font-mono text-primary-strong placeholder:text-tertiary"
              >
              <div class="text-secondary text-xs mt-1">cron 表达式：自动按设定规则推送</div>
            </div>

            <div v-if="lastPushTime" class="text-secondary text-xs text-center">
              上次推送：{{ new Date(lastPushTime).toLocaleString('zh-CN') }}
            </div>
            
            <button
              @click="pushNews" 
              :disabled="pushLoading"
              class="liquid-success w-full py-2 rounded-2xl text-sm"
            >
              {{ pushLoading ? '推送中...' : '📤 立即推送测试' }}
            </button>
            
            <div v-if="pushMessage" class="text-xs text-center" :class="pushMessage.includes('成功') ? 'text-green-600' : 'text-red-500'">
              {{ pushMessage }}
            </div>
          </div>
        </div>
        
        <button @click="saveConfig" class="liquid-chip-active w-full py-3 rounded-2xl mb-2 font-medium">
          保存
        </button>
        <button @click="showAccount = false" class="w-full py-2 text-tertiary text-sm">
          取消
        </button>
        </div>
      </div>
    </div>

    <!-- 全局 Toast -->
    <div class="fixed inset-x-0 top-4 z-[100] flex flex-col items-center gap-2 px-4 pointer-events-none">
      <TransitionGroup name="toast">
        <div
          v-for="toast in toasts"
          :key="toast.id"
          class="liquid-surface pointer-events-auto max-w-sm rounded-2xl px-4 py-2.5 text-sm"
          :class="toast.type === 'success' ? 'liquid-success' : toast.type === 'error' ? 'liquid-error' : 'liquid-badge text-primary'"
          @click="removeToast(toast.id)"
        >
          {{ toast.message }}
        </div>
      </TransitionGroup>
    </div>
  </div>
</template>
