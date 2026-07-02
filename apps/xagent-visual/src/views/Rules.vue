<template>
  <div class="rules-page">
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          :placeholder="$t('rules.searchPlaceholder')"
          :prefix-icon="Search"
          clearable
          class="toolbar-search"
        />
        <el-select 
          v-model="typeFilter" 
          :placeholder="$t('rules.typeFilter')" 
          clearable
          class="toolbar-filter"
        >
          <el-option :label="$t('rules.allTypes')" value="" />
          <el-option :label="$t('rules.typeScene')" value="scene" />
          <el-option :label="$t('rules.typeAlert')" value="alert" />
          <el-option :label="$t('rules.typeSchedule')" value="schedule" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" :icon="Plus" @click="openEditor()" v-if="userStore.hasPermission('rules', 'create')">
          {{ $t('rules.createNew') }}
        </el-button>
        <el-button :icon="Upload" @click="handleImportRules" v-if="userStore.hasPermission('rules', 'create')">{{ $t('common.import') }}</el-button>
        <el-button :icon="Download" @click="handleExportRules">{{ $t('common.export') }}</el-button>
        <el-button :icon="Refresh" circle @click="handleRefresh" :loading="ruleStore.loading" />
      </div>
    </div>

    <div v-if="ruleStore.loading && ruleStore.rules.length === 0" class="loading-state">
      <el-icon class="is-loading" :size="24"><Loading /></el-icon>
      <span>{{ $t('rules.loadingMessage') }}</span>
    </div>

    <div v-else-if="ruleStore.error" class="error-state">
      <span>{{ ruleStore.error }}</span>
      <el-button size="small" @click="ruleStore.fetchRules()">{{ $t('common.retry') }}</el-button>
    </div>

    <div v-else-if="filteredRules.length === 0" class="empty-state">
      <span>{{ searchQuery || typeFilter ? $t('rules.noMatchingRules') : $t('rules.emptyMessage') }}</span>
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
          <code>{{ rule.expression || $t('rules.noExpression') }}</code>
        </div>
        
        <div class="rule-meta">
          <span class="meta-item">
            <span class="meta-label">{{ $t('rules.executionCount') }}:</span>
            <span class="meta-value">{{ rule.executionCount }} {{ $t('rules.times') }}</span>
          </span>
          <span class="meta-item">
            <span class="meta-label">{{ $t('rules.lastTriggered') }}:</span>
            <span class="meta-value">{{ rule.lastTriggered || $t('rules.neverTriggered') }}</span>
          </span>
        </div>
        
        <div class="rule-actions">
          <el-button type="primary" :icon="Edit" size="small" @click="openEditor(rule.id)" v-if="userStore.hasPermission('rules', 'update')">
            {{ $t('rules.edit') }}
          </el-button>
          <el-button :icon="CopyDocument" size="small" @click="handleCopyRule(rule)" v-if="userStore.hasPermission('rules', 'create')">
            {{ $t('rules.copy') }}
          </el-button>
          <el-button 
            :type="rule.enabled ? 'warning' : 'success'" 
            size="small"
            @click="handleToggleRule(rule.id)"
            v-if="userStore.hasPermission('rules', 'update')"
          >
            {{ rule.enabled ? $t('rules.disable') : $t('rules.enable') }}
          </el-button>
          <el-button type="danger" :icon="Delete" size="small" @click="handleDeleteRule(rule.id, rule.name)" v-if="userStore.hasPermission('rules', 'delete')">
            {{ $t('rules.delete') }}
          </el-button>
        </div>
      </el-card>
    </div>
    
    <el-drawer
      v-model="showEditor"
      :title="currentRuleId ? $t('rules.editRule') : $t('rules.newRule')"
      direction="rtl"
      size="80%"
      :with-header="true"
    >
      <RuleEditorCanvas :rule-id="currentRuleId" @close="showEditor = false" @saved="handleEditorSaved" />
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
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
  Delete,
  Search,
  Loading
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import RuleEditorCanvas from '@/components/RuleEditorCanvas.vue'

const { t } = useI18n()

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
    scene: t('rules.typeScene'),
    alert: t('rules.typeAlert'),
    schedule: t('rules.typeSchedule')
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
      ElMessage.success(rule.enabled ? t('rules.ruleEnabled') : t('rules.ruleDisabled'))
    }
  } catch {
    ElMessage.error(t('common.operationFailed'))
  }
}

const handleCopyRule = async (rule: RuleViewItem) => {
  try {
    await ruleStore.copyRule(rule.id)
    ElMessage.success(t('rules.ruleCopied'))
  } catch {
    ElMessage.error(t('rules.copyFailed'))
  }
}

const handleDeleteRule = (id: string, name: string) => {
  ElMessageBox.confirm(
    t('rules.deleteConfirmMessage', { name }),
    t('rules.deleteConfirmTitle'),
    {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    }
  ).then(async () => {
    try {
      await ruleStore.deleteRule(id)
      ElMessage.success(t('rules.ruleDeleted'))
    } catch {
      ElMessage.error(t('rules.deleteFailed'))
    }
  }).catch(() => {})
}

const handleRefresh = async () => {
  await ruleStore.fetchRules()
  ElMessage.success(t('rules.refreshSuccess'))
}

const handleExportRules = () => {
  const rules = ruleStore.rules
  if (rules.length === 0) {
    ElMessage.warning(t('rules.noExportableRules'))
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
  ElMessage.success(t('rules.exportSuccess', { count: rules.length }))
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
        throw new Error(t('rules.invalidFormat'))
      }

      let successCount = 0
      let failCount = 0

      for (const rule of importedRules) {
        try {
          const createData = {
            id: rule.id || `rule-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
            name: rule.name || t('rules.importedRule'),
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
        ElMessage.success(failCount > 0 ? t('rules.importPartialSuccess', { success: successCount, fail: failCount }) : t('rules.importSuccess', { count: successCount }))
      } else {
        ElMessage.error(t('rules.importFailed'))
      }
    } catch (error) {
      ElMessage.error(t('rules.importError', { message: (error as Error).message }))
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
  background: var(--settings-toolbar-bg);
  border-radius: 8px;
  box-shadow: var(--settings-toolbar-shadow);
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
  color: var(--rule-loading-color);
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
  background: var(--rule-status-inactive-bg);
  color: var(--rule-status-inactive-color);
}

.rule-status.active {
  background: var(--rule-status-active-bg);
  color: var(--rule-status-active-color);
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
  color: var(--rule-name-color);
}

.rule-expression {
  background: var(--rule-expression-bg);
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 12px;
}

.rule-expression code {
  font-family: 'Fira Code', monospace;
  font-size: 13px;
  color: var(--rule-expression-color);
}

.rule-meta {
  display: flex;
  gap: 24px;
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--rule-meta-border);
}

.meta-item {
  display: flex;
  gap: 6px;
  font-size: 13px;
}

.meta-label {
  color: var(--rule-meta-label-color);
}

.meta-value {
  color: var(--rule-meta-value-color);
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
