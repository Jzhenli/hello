<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Setting } from '@element-plus/icons-vue'

const { t } = useI18n()
const router = useRouter()
const scadaStore = useScadaStore()

const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const formName = ref('')
const formDescription = ref('')
const formWidth = ref(1920)
const formHeight = ref(1080)
const editingPanelId = ref<string | null>(null)
const formType = ref<'Dashboard' | 'Graphic'>('Dashboard')

const projects = computed(() => scadaStore.panels)

const handleCreate = async () => {
  if (!formName.value.trim()) {
    ElMessage.warning(t('scada.enterProjectName'))
    return
  }
  
  scadaStore.createPanel(
    formName.value,
    formType.value,
    formDescription.value,
    formWidth.value,
    formHeight.value
  )
  
  ElMessage.success(t('scada.createSuccess'))
  showCreateDialog.value = false
  resetForm()
}

const handleEdit = (panel: any) => {
  if (panel.type === 'Graphic') {
    router.push({ name: 'GraphicEdit', params: { id: panel.id } })
  } else {
    router.push({ name: 'ScadaEdit', params: { id: panel.id } })
  }
}

const handleDelete = async (id: string) => {
  try {
    await ElMessageBox.confirm(t('scada.deleteConfirm'), t('scada.deleteConfirmTitle'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning'
    })
    
    scadaStore.deletePanel(id)
    ElMessage.success(t('scada.deleteSuccess'))
  } catch {
    // User cancelled
  }
}

const openEditDialog = (panel: any) => {
  editingPanelId.value = panel.id
  formName.value = panel.name
  formDescription.value = panel.description || ''
  formWidth.value = panel.width
  formHeight.value = panel.height
  showEditDialog.value = true
}

const handleSaveEdit = async () => {
  if (!formName.value.trim()) {
    ElMessage.warning(t('scada.enterProjectName'))
    return
  }
  
  if (!editingPanelId.value) return
  
  const currentPanelId = scadaStore.currentPanelId
  if (currentPanelId !== editingPanelId.value) {
    scadaStore.selectPanel(editingPanelId.value)
  }
  
  scadaStore.updatePanel({
    name: formName.value,
    description: formDescription.value,
    width: formWidth.value,
    height: formHeight.value
  })
  
  ElMessage.success(t('scada.saveSuccess'))
  showEditDialog.value = false
  resetForm()
}

const resetForm = () => {
  formName.value = ''
  formDescription.value = ''
  formWidth.value = 1920
  formHeight.value = 1080
  editingPanelId.value = null
  formType.value = 'Dashboard'
}

const formatTime = (timestamp: number) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="project-list-container">
    <div class="header">
      <h2>{{ $t('scada.title') }}</h2>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">
        {{ $t('scada.newProject') }}
      </el-button>
    </div>

    <div v-if="projects.length === 0" class="empty-state">
      <el-empty :description="$t('scada.noProjects')">
        <el-button type="primary" @click="showCreateDialog = true">{{ $t('scada.createProject') }}</el-button>
      </el-empty>
    </div>

    <div v-else class="project-grid">
      <el-card 
        v-for="panel in projects" 
        :key="panel.id" 
        class="project-card"
        shadow="hover"
      >
        <div class="project-info">
          <div class="project-title-row">
            <h3 class="project-name">{{ panel.name }}</h3>
            <el-tag :type="panel.type === 'Dashboard' ? '' : 'warning'" size="small" class="type-tag">
              {{ panel.type === 'Dashboard' ? $t('scada.dashboardType') : $t('scada.graphicType') }}
            </el-tag>
          </div>
          <p class="project-desc">{{ panel.description || $t('scada.noDescription') }}</p>
          <div class="project-meta">
            <span>{{ $t('scada.componentCount') }}: {{ panel.components?.length || 0 }}</span>
            <span>{{ $t('scada.createTime') }}: {{ formatTime(panel.createdAt) }}</span>
          </div>
        </div>
        <div class="project-actions">
          <el-button 
            type="primary" 
            :icon="Edit"
            size="small"
            @click="handleEdit(panel)"
          >
            {{ $t('scada.edit') }}
          </el-button>
          <el-button 
            type="warning" 
            :icon="Setting"
            size="small"
            @click="openEditDialog(panel)"
          >
            {{ $t('scada.settings') }}
          </el-button>
          <el-button 
            type="danger" 
            :icon="Delete"
            size="small"
            @click="handleDelete(panel.id)"
          >
            {{ $t('scada.delete') }}
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 创建项目对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      :title="$t('scada.newProject')"
      width="500px"
    >
      <el-form label-width="80px">
        <el-form-item :label="$t('scada.projectName')" required>
          <el-input v-model="formName" :placeholder="$t('scada.enterProjectName')" />
        </el-form-item>
        <el-form-item :label="$t('scada.projectType')" required>
          <el-select v-model="formType" :placeholder="$t('scada.selectProjectType')">
            <el-option :label="$t('scada.dashboardType')" value="Dashboard" />
            <el-option :label="$t('scada.graphicType')" value="Graphic" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('scada.projectDesc')">
          <el-input
            v-model="formDescription"
            type="textarea"
            :placeholder="$t('scada.enterProjectDesc')"
            :rows="3"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleCreate">{{ $t('common.confirm') }}</el-button>
      </template>
    </el-dialog>

    <!-- 编辑项目对话框 -->
    <el-dialog
      v-model="showEditDialog"
      :title="$t('scada.editProject')"
      width="500px"
    >
      <el-form label-width="80px">
        <el-form-item :label="$t('scada.projectName')" required>
          <el-input v-model="formName" :placeholder="$t('scada.enterProjectName')" />
        </el-form-item>
        <el-form-item :label="$t('scada.projectDesc')">
          <el-input
            v-model="formDescription"
            type="textarea"
            :placeholder="$t('scada.enterProjectDesc')"
            :rows="3"
          />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item :label="$t('scada.canvasWidth')">
              <el-input-number v-model="formWidth" :min="400" :max="4000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item :label="$t('scada.canvasHeight')">
              <el-input-number v-model="formHeight" :min="300" :max="3000" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="handleSaveEdit">{{ $t('common.confirm') }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.project-list-container {
  padding: 20px;
  min-height: calc(100vh - 60px);
  background-color: #f5f7fa;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}

.empty-state {
  background: white;
  border-radius: 8px;
  padding: 60px 20px;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}

.project-card {
  transition: all 0.3s;
}

.project-card:hover {
  transform: translateY(-4px);
}

.project-info {
  margin-bottom: 16px;
}

.project-name {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.project-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.type-tag {
  flex-shrink: 0;
}

.project-desc {
  margin: 0 0 12px 0;
  font-size: 14px;
  color: #909399;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
}

.project-meta {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 12px;
  color: #a8abb2;
}

.project-actions {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}
</style>
