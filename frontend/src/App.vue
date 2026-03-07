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

// 标签相关
const currentTag = ref(null)  // 当前选中的标签
const tags = ref(['工作', '生活', '科技'])  // 标签列表
const keywordTags = ref({})  // {tag: [keywords]}
const editingTag = ref(null)  // 当前编辑的标签
const editingKeywords = ref('')  // 编辑中的关键词（字符串格式）
const lastRefresh = ref('')  // 上次刷新时间
const editingTagName = ref('')  // 正在重命名的标签名

// 表单
const username = ref('')
const password = ref('')

// 新标签
const newTag = ref('')

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
        keyword_tags: res.data.config.keyword_tags || {}
      }
      keywordTags.value = res.data.config.keyword_tags || {}
    }
  } catch (e) {
    console.error(e)
  }
}

// 加载新闻
async function loadNews() {
  loading.value = true
  try {
    const params = currentTag.value ? { tag: currentTag.value } : {}
    const res = await axios.get(`${API_URL}/api/news`, { 
      ...getAuthHeader(), 
      params 
    })
    if (res.data.success) {
      news.value = res.data.news
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

// 编辑标签关键词
function editTagKeywords(tag) {
  editingTag.value = tag
  // 把数组转换为逗号分隔的字符串
  editingKeywords.value = (keywordTags.value[tag] || []).join(', ')
}

// 保存标签关键词
function saveTagKeywords() {
  if (editingTag.value) {
    // 把字符串转换为数组
    const keywords = editingKeywords.value.split(',').map(s => s.trim()).filter(s => s)
    keywordTags.value[editingTag.value] = keywords
  }
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
async function saveConfig() {
  try {
    // 把字符串转换为数组
    const blocked = typeof config.value.blocked_keywords === 'string'
      ? config.value.blocked_keywords.split(',').map(s => s.trim()).filter(s => s)
      : config.value.blocked_keywords
    
    await axios.post(`${API_URL}/api/config`, {
      blocked_keywords: blocked,
      platforms: config.value.platforms,
      keyword_tags: keywordTags.value
    }, getAuthHeader())
    alert('保存成功')
    showAccount.value = false
    editingTag.value = null
    await loadConfig()
    await loadTags()
    await loadNews()
  } catch (e) {
    console.error(e)
    alert('保存失败')
  }
}

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
  editingTagName.value = tag
}

function confirmRenameTag(oldTag) {
  const newTag = editingTagName.value.trim()
  if (newTag && newTag !== oldTag) {
    // 更新 keywordTags
    const keywords = keywordTags.value[oldTag] || []
    delete keywordTags.value[oldTag]
    keywordTags.value[newTag] = keywords
    
    // 更新 tags
    const index = tags.value.indexOf(oldTag)
    if (index !== -1) {
      tags.value[index] = newTag
    }
    
    // 更新 currentTag
    if (currentTag.value === oldTag) {
      currentTag.value = newTag
    }
  }
  editingTagName.value = ''
}

function cancelRenameTag() {
  editingTagName.value = ''
}

// 刷新缓存
async function refresh() {
  loading.value = true
  try {
    const res = await axios.post(`${API_URL}/api/news/refresh`, {}, getAuthHeader())
    if (res.data.last_refresh) {
      const time = new Date(res.data.last_refresh)
      lastRefresh.value = time.getHours().toString().padStart(2, '0') + ':' + time.getMinutes().toString().padStart(2, '0')
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
    }
  } catch (e) {
    console.error(e)
  }
}

// 初始化
onMounted(async () => {
  if (currentUser.value && token.value) {
    await loadConfig()
    await loadTags()
  }
  await loadNews()
  await loadRefreshTime()
})
</script>

<template>
  <div class="min-h-screen bg-gray-100">
    <!-- 头部 -->
    <header class="bg-gradient-to-r from-indigo-500 to-purple-600 text-white px-4 py-4 sticky top-0 z-50">
      <div class="max-w-2xl mx-auto flex justify-between items-center">
        <h1 class="text-lg font-semibold">热点资讯</h1>
        <div class="flex gap-2">
          <button 
            v-if="currentUser" 
            @click="showAccount = true"
            class="px-3 py-1.5 bg-white/20 rounded-full text-sm"
          >
            {{ currentUser }}
          </button>
          <button 
            v-if="currentUser" 
            @click="logout"
            class="px-3 py-1.5 bg-red-500/50 rounded-full text-sm"
          >
            退出
          </button>
          <button 
            v-if="!currentUser" 
            @click="showLogin = true"
            class="px-3 py-1.5 bg-white/20 rounded-full text-sm"
          >
            登录
          </button>
        </div>
      </div>
    </header>

    <!-- 标签筛选 -->
    <div v-if="currentUser" class="bg-white border-b sticky top-14 z-40">
      <div class="max-w-2xl mx-auto px-4 py-2 flex gap-2 overflow-x-auto">
        <button 
          @click="selectTag(null)"
          class="px-3 py-1 rounded-full text-sm whitespace-nowrap transition-colors"
          :class="currentTag === null ? 'bg-indigo-500 text-white' : 'bg-gray-100 text-gray-600'"
        >
          全部
        </button>
        <button 
          v-for="tag in tags" 
          :key="tag"
          @click="selectTag(tag)"
          class="px-3 py-1 rounded-full text-sm whitespace-nowrap transition-colors"
          :class="currentTag === tag ? 'bg-indigo-500 text-white' : 'bg-gray-100 text-gray-600'"
        >
          {{ tag }}
        </button>
      </div>
    </div>

    <!-- 内容 -->
    <main class="max-w-2xl mx-auto p-4">
      <!-- 操作栏 -->
      <div class="flex justify-between items-center mb-4">
        <div class="flex items-center gap-2">
          <span class="text-gray-500 text-sm">{{ news.length }} 条{{ currentTag ? ` [${currentTag}]` : '' }}</span>
          <span v-if="lastRefresh" class="text-xs text-gray-400">上次刷新: {{ lastRefresh }}</span>
        </div>
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
              class="text-xs px-2 py-0.5 rounded ml-2 shrink-0"
              :class="{
                'bg-red-100 text-red-600': item.platform === '微博',
                'bg-blue-100 text-blue-600': item.platform === '百度',
                'bg-pink-100 text-pink-600': item.platform === 'B站',
                'bg-orange-100 text-orange-600': item.platform === '抖音',
                'bg-green-100 text-green-600': item.platform === '36Kr',
                'bg-cyan-100 text-cyan-600': item.platform === 'IT之家',
                'bg-indigo-100 text-indigo-600': item.platform === '知乎',
                'bg-yellow-100 text-yellow-600': item.platform === '头条',
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
                class="text-xs px-2 py-0.5 bg-purple-100 text-purple-600 rounded"
              >
                {{ kw }}
              </span>
            </div>
            <!-- 发布时间 -->
            <span class="text-xs text-gray-400">
              {{ item.pub_time || item.created_at?.slice(11,16) || '' }}
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
          @keyup.enter="login"
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
        
        <!-- 切换账号按钮 -->
        <button @click="switchAccount" class="w-full py-2 mb-4 bg-gray-100 rounded-xl text-gray-600 text-sm">
          切换账号
        </button>
        
        <!-- 标签关键词管理 -->
        <div class="mb-4">
          <label class="text-sm text-gray-500 block mb-2">标签关键词设置</label>
          <div class="text-xs text-gray-400 mb-2">点击标签设置其关键词</div>
          
          <!-- 标签列表 -->
          <div class="space-y-2 mb-3">
            <div 
              v-for="tag in tags" 
              :key="tag"
              class="border rounded-lg p-2"
            >
              <div class="flex justify-between items-center mb-1">
                <span v-if="editingTagName !== tag" class="font-medium text-sm">{{ tag }}</span>
                <input 
                  v-else
                  v-model="editingTagName"
                  @keyup.enter="confirmRenameTag(tag)"
                  @blur="confirmRenameTag(tag)"
                  class="font-medium text-sm border rounded px-1 py-0.5 w-24"
                />
                <div class="flex gap-1">
                  <button 
                    v-if="editingTagName !== tag"
                    @click="startRenameTag(tag)"
                    class="text-xs px-2 py-1 bg-blue-100 text-blue-600 rounded"
                  >
                    重命名
                  </button>
                  <button 
                    @click="editTagKeywords(tag)"
                    class="text-xs px-2 py-1 bg-indigo-100 text-indigo-600 rounded"
                  >
                    {{ (keywordTags[tag] || []).length ? '编辑' : '设置' }}
                  </button>
                  <button 
                    v-if="!['工作', '生活', '科技'].includes(tag)"
                    @click="deleteTag(tag)"
                    class="text-xs px-2 py-1 bg-red-100 text-red-600 rounded"
                  >
                    删除
                  </button>
                </div>
              </div>
              <div v-if="editingTag === tag" class="mt-2">
                <textarea 
                  v-model="editingKeywords"
                  :placeholder="`${tag}标签的关键词，用逗号分隔`"
                  class="w-full px-2 py-1 border rounded text-sm"
                  rows="2"
                ></textarea>
                <div class="flex gap-2 mt-1">
                  <button 
                    @click="saveTagKeywords"
                    class="text-xs px-2 py-1 bg-indigo-500 text-white rounded"
                  >
                    保存
                  </button>
                  <button 
                    @click="editingTag = null"
                    class="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded"
                  >
                    取消
                  </button>
                </div>
              </div>
              <div v-else class="text-xs text-gray-400">
                关键词: {{ (keywordTags[tag] || []).join(', ') || '未设置' }}
              </div>
            </div>
          </div>
          
          <!-- 添加新标签 -->
          <div class="flex gap-2">
            <input 
              v-model="newTag" 
              placeholder="新增标签"
              class="flex-1 px-2 py-1 border rounded text-sm"
              @keyup.enter="addCustomTag"
            />
            <button @click="addCustomTag" class="px-3 py-1 bg-indigo-500 text-white rounded text-sm">
              添加
            </button>
          </div>
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
            <label v-for="p in [
              {id: 'weibo', name: '微博'},
              {id: 'baidu', name: '百度'},
              {id: 'douyin', name: '抖音'},
              {id: 'bilibili', name: 'B站'},
              {id: 'zhihu', name: '知乎'},
              {id: 'toutiao', name: '头条'},
              {id: 'wallstreetcn', name: '华尔街见闻'},
              {id: 'thepaper', name: '澎湃'},
              {id: 'ifeng', name: '凤凰'},
              {id: 'sspai', name: '少数派'},
              {id: 'v2ex', name: 'V2EX'},
              {id: 'jin10', name: '金十数据'},
              {id: 'ithome', name: 'IT之家'},
              {id: '36kr', name: '36Kr'}
            ]" :key="p.id" class="flex items-center gap-1 bg-gray-100 px-3 py-1 rounded-full text-sm">
              <input type="checkbox" :value="p.id" v-model="config.platforms">
              {{ p.name }}
            </label>
          </div>
        </div>
        
        <button @click="saveConfig" class="w-full py-3 bg-indigo-500 text-white rounded-xl mb-2">
          保存
        </button>
        <button @click="showAccount = false" class="w-full py-2 text-gray-400 text-sm">
          取消
        </button>
      </div>
    </div>
  </div>
</template>
