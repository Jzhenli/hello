<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRuleStore, type RuleViewItem } from '@/stores/rules'
import { useUserStore } from '@/stores/users'
import { 
  Plus, 
  Upload, 
  Download, 
  Refresh,
  CircleCheck,
  CircleClose,
  Edit,
  CopyDocument,
  Delete
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const ruleStore = useRuleStore()
const userStore = useUserStore()

const searchQuery = ref('')
const typeFilter = ref('')

const filteredRules = computed(() => {
  let rules = [...ruleStore.rules]
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    rules = rules.filter(r => 
      r.name.toLowerCase().includes(query) || 
      r.description?.toLowerCase().includes(query)
    )
  }
  
  if (typeFilter.value) {
    rules = rules.filter(r => r.type === typeFilter.value)
  }
  
  return rules
})

const getTypeLabel = (type: string) => {
  const labels: Record<string, string> = {
    scene: '场景联动',
    alert: '告警规则',
    schedule: '定时任务'
  }
  return labels[type] || type
}

const getTypeTag = (type: string) => {
  const tags: Record<string, string> = {
    scene: 'primary',
    alert: 'danger',
    schedule: 'warning'
  }
  return tags[type] || 'info'
}

const handleToggleRule = async (id: string) => {
  try {
    await ruleStore.toggleRule(id)
    const rule = ruleStore.rules.find(r => r.id === id)
    if (rule) {
      ElMessage.success(rule.enabled ? '规则已启用' : '规则已禁用')
    }
  } catch {
    ElMessage.error('操作失败')
  }
}

const handleCopyRule = async (rule: RuleViewItem) => {
  try {
    await ruleStore.copyRule(rule.id)
    ElMessage.success('规则已复制')
  } catch {
    ElMessage.error('复制规则失败')
  }
}

const handleDeleteRule = (id: string, name: string) => {
  ElMessageBox.confirm(
    `确定要删除规则 "${name}" 吗？`,
    '删除确认',
    {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    }
  ).then(async () => {
    try {
      await ruleStore.deleteRule(id)
      ElMessage.success('规则已删除')
    } catch {
      ElMessage.error('删除规则失败')
    }
  }).catch(() => {})
}

const handleRefresh = async () => {
  await ruleStore.fetchRules()
  ElMessage.success('规则列表已刷新')
}

const handleExportRules = () => {
  const rules = ruleStore.rules
  if (rules.length === 0) {
    ElMessage.warning('没有可导出的规则')
    return
  }

  const json = JSON.stringify(rules, null, 2)
  const blob = new Blob([json], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `rules-export-${new Date().toISOString().slice(0, 10)}.json`
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(`已导出 ${rules.length} 条规则`)
}

const handleImportRules = () => {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'

  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      const importedRules = JSON.parse(text)

      if (!Array.isArray(importedRules)) {
        throw new Error('无效的规则文件格式')
      }

      let successCount = 0
      let failCount = 0

      for (const rule of importedRules) {
        try {
          const createData = {
            id: rule.id || `rule-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            name: rule.name || '导入的规则',
            description: rule.description,
            enabled: rule.enabled ?? false,
            plugin: rule.plugin || { name: 'threshold_rule', config: {} },
            data_subscriptions: rule.data_subscriptions,
            notification: rule.notification,
            pipeline_id: rule.pipeline_id,
            channel_ids: rule.channel_ids,
          }
          await ruleStore.createRule(createData)
          successCount++
        } catch {
          failCount++
        }
      }

      if (successCount > 0) {
        ElMessage.success(`成功导入 ${successCount} 条规则${failCount > 0 ? `，${failCount} 条失败` : ''}`)
      } else {
        ElMessage.error('导入失败')
      }
    } catch (error) {
      ElMessage.error('导入失败：' + (error as Error).message)
    }
  }

  input.click()
}

const showEditor = ref(false)
const currentRuleId = ref<string | null>(null)

const openEditor = (ruleId?: string) => {
  currentRuleId.value = ruleId || null
  showEditor.value = true
}

const handleEditorSaved = () => {
  ruleStore.fetchRules()
}

onMounted(() => {
  ruleStore.fetchRules()
})
</script>

<template>
  <div class="rules-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          placeholder="搜索规则..."
          :prefix-icon="Search"
          clearable
          class="toolbar-search"
        />
        <el-select 
          v-model="typeFilter" 
          placeholder="类型筛选" 
          clearable
          class="toolbar-filter"
        >
          <el-option label="全部类型" value="" />
          <el-option label="场景联动" value="scene" />
          <el-option label="告警规则" value="alert" />
          <el-option label="定时任务" value="schedule" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" :icon="Plus" @click="openEditor()" v-if="userStore.hasPermission('rules', 'create')">
          新建规则
        </el-button>
        <el-button :icon="Upload" @click="handleImportRules" v-if="userStore.hasPermission('rules', 'create')">导入</el-button>
        <el-button :icon="Download" @click="handleExportRules">导出</el-button>
        <el-button :icon="Refresh" circle @click="handleRefresh" :loading="ruleStore.loading" />
      </div>
    </div>

    <div v-if="ruleStore.loading && ruleStore.rules.length === 0" class="loading-state">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>加载规则列表中...</span>
    </div>

    <div v-else-if="ruleStore.error" class="error-state">
      <span>{{ ruleStore.error }}</span>
      <el-button size="small" @click="ruleStore.fetchRules()">重试</el-button>
    </div>

    <div v-else-if="filteredRules.length === 0" class="empty-state">
      <span>{{ searchQuery || typeFilter ? '没有匹配的规则' : '暂无规则，点击"新建规则"开始创建' }}</span>
    </div>
    
    <div v-else class="rules-list">
      <el-card 
        v-for="rule in filteredRules" 
        :key="rule.id" 
        class="rule-card"
        shadow="hover"
        :class="{ disabled: !rule.enabled }"
      >
        <div class="rule-header">
          <div class="rule-status" :class="{ active: rule.enabled }">
            <el-icon v-if="rule.enabled"><CircleCheck /></el-icon>
            <el-icon v-else><CircleClose /></el-icon>
          </div>
          <div class="rule-title">
            <span class="rule-name">{{ rule.name }}</span>
            <el-tag :type="getTypeTag(rule.type)" size="small">
              {{ getTypeLabel(rule.type) }}
            </el-tag>
          </div>
          <el-switch 
            v-model="rule.enabled"
            size="small"
            @change="handleToggleRule(rule.id)"
            v-if="userStore.hasPermission('rules', 'update')"
          />
        </div>
        
        <div class="rule-expression">
          <code>{{ rule.expression || '无表达式' }}</code>
        </div>
        
        <div class="rule-meta">
          <span class="meta-item">
            <span class="meta-label">执行次数:</span>
            <span class="meta-value">{{ rule.executionCount }} 次</span>
          </span>
          <span class="meta-item">
            <span class="meta-label">最后触发:</span>
            <span class="meta-value">{{ rule.lastTriggered || '从未触发' }}</span>
          </span>
        </div>
        
        <div class="rule-actions">
          <el-button type="primary" :icon="Edit" size="small" @click="openEditor(rule.id)" v-if="userStore.hasPermission('rules', 'update')">
            编辑
          </el-button>
          <el-button :icon="CopyDocument" size="small" @click="handleCopyRule(rule)" v-if="userStore.hasPermission('rules', 'create')">
            复制
          </el-button>
          <el-button 
            :type="rule.enabled ? 'warning' : 'success'" 
            size="small"
            @click="handleToggleRule(rule.id)"
            v-if="userStore.hasPermission('rules', 'update')"
          >
            {{ rule.enabled ? '禁用' : '启用' }}
          </el-button>
          <el-button type="danger" :icon="Delete" size="small" @click="handleDeleteRule(rule.id, rule.name)" v-if="userStore.hasPermission('rules', 'delete')">
            删除
          </el-button>
        </div>
      </el-card>
    </div>
    
    <el-drawer
      v-model="showEditor"
      :title="currentRuleId ? '编辑规则' : '新建规则'"
      direction="rtl"
      size="80%"
      :with-header="true"
    >
      <RuleEditorCanvas :rule-id="currentRuleId" @close="showEditor = false" @saved="handleEditorSaved" />
    </el-drawer>
  </div>
</template>

<script lang="ts">
import { Search, Loading } from '@element-plus/icons-vue'
import RuleEditorCanvas from '@/components/RuleEditorCanvas.vue'

export default {
  components: { Search, Loading, RuleEditorCanvas }
}
</script>

<style scoped>
.rules-page {
  padding: 0;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 20px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.toolbar-left {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.toolbar-search {
  width: 250px;
}

.toolbar-filter {
  width: 140px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.loading-state,
.error-state,
.empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 48px;
  color: #7f8c8d;
  font-size: 14px;
}

.rules-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rule-card {
  transition: all 0.3s ease;
}

.rule-card:hover {
  transform: translateX(4px);
}

.rule-card.disabled {
  opacity: 0.6;
}

.rule-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.rule-status {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #ffebee;
  color: #e74c3c;
}

.rule-status.active {
  background: #e8f5e9;
  color: #27ae60;
}

.rule-title {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 10px;
}

.rule-name {
  font-size: 16px;
  font-weight: 600;
  color: #2c3e50;
}

.rule-expression {
  background: #f8f9fa;
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 12px;
}

.rule-expression code {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: #3498db;
}

.rule-meta {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid #eee;
}

.meta-item {
  display: flex;
  gap: 6px;
  font-size: 13px;
}

.meta-label {
  color: #7f8c8d;
}

.meta-value {
  color: #2c3e50;
  font-weight: 500;
}

.rule-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

@media (max-width: 1024px) {
  .toolbar-search {
    width: 200px;
  }

  .toolbar-filter {
    width: 120px;
  }
}

@media (max-width: 768px) {
  .toolbar {
    padding: 12px;
  }

  .toolbar-search {
    width: 100%;
  }

  .toolbar-filter {
    width: 100%;
  }

  .rule-meta {
    flex-direction: column;
    gap: 8px;
  }
}
</style>