<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useRuleStore } from '@/stores/rules'
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

const router = useRouter()
const ruleStore = useRuleStore()

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

const handleToggleRule = (id: string) => {
  ruleStore.toggleRule(id)
  const rule = ruleStore.rules.find(r => r.id === id)
  if (rule) {
    ElMessage.success(rule.enabled ? '规则已启用' : '规则已禁用')
  }
}

const handleEditRule = (id: string) => {
  router.push({ path: '/rules', query: { edit: id } })
}

const handleCopyRule = (rule: any) => {
  const newRule = {
    ...rule,
    id: `rule-${Date.now()}`,
    name: `${rule.name} (副本)`,
    executionCount: 0,
    createdAt: Date.now(),
    updatedAt: Date.now()
  }
  ruleStore.rules.push(newRule)
  ElMessage.success('规则已复制')
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
  ).then(() => {
    ruleStore.deleteRule(id)
    ElMessage.success('规则已删除')
  }).catch(() => {})
}

const handleCreateRule = () => {
  router.push({ path: '/rules', query: { new: 'true' } })
}

const showEditor = ref(false)
const currentRuleId = ref<string | null>(null)

const openEditor = (ruleId?: string) => {
  currentRuleId.value = ruleId || null
  showEditor.value = true
}
</script>

<template>
  <div class="rules-page">
    <div class="page-header">
      <h2>规则编辑</h2>
    </div>
    
    <div class="toolbar">
      <div class="toolbar-left">
        <el-input
          v-model="searchQuery"
          placeholder="搜索规则..."
          :prefix-icon="Search"
          clearable
          style="width: 250px"
        />
        <el-select 
          v-model="typeFilter" 
          placeholder="类型筛选" 
          clearable
          style="width: 140px"
        >
          <el-option label="全部类型" value="" />
          <el-option label="场景联动" value="scene" />
          <el-option label="告警规则" value="alert" />
          <el-option label="定时任务" value="schedule" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <el-button type="primary" :icon="Plus" @click="openEditor()">
          新建规则
        </el-button>
        <el-button :icon="Upload">导入</el-button>
        <el-button :icon="Download">导出</el-button>
        <el-button :icon="Refresh" circle />
      </div>
    </div>
    
    <div class="rules-list">
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
          />
        </div>
        
        <div class="rule-expression">
          <code>{{ rule.expression }}</code>
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
          <el-button type="primary" :icon="Edit" size="small" @click="openEditor(rule.id)">
            编辑
          </el-button>
          <el-button :icon="CopyDocument" size="small" @click="handleCopyRule(rule)">
            复制
          </el-button>
          <el-button 
            :type="rule.enabled ? 'warning' : 'success'" 
            size="small"
            @click="handleToggleRule(rule.id)"
          >
            {{ rule.enabled ? '禁用' : '启用' }}
          </el-button>
          <el-button type="danger" :icon="Delete" size="small" @click="handleDeleteRule(rule.id, rule.name)">
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
      <RuleEditorCanvas :rule-id="currentRuleId" @close="showEditor = false" />
    </el-drawer>
  </div>
</template>

<script lang="ts">
import { Search } from '@element-plus/icons-vue'
import RuleEditorCanvas from '@/components/RuleEditorCanvas.vue'

export default {
  components: { Search, RuleEditorCanvas }
}
</script>

<style scoped>
.rules-page {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0;
  font-size: 24px;
  color: #2c3e50;
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px;
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.toolbar-left {
  display: flex;
  gap: 12px;
}

.toolbar-right {
  display: flex;
  gap: 8px;
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
}
</style>
