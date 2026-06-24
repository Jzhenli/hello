<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useScadaStore } from '@/stores/scada'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Setting } from '@element-plus/icons-vue'

const router = useRouter()
const scadaStore = useScadaStore()

const showCreateDialog = ref(false)
const showEditDialog = ref(false)
const formName = ref('')
const formDescription = ref('')
const formWidth = ref(1200)
const formHeight = ref(800)
const editingPanelId = ref<string | null>(null)

const projects = computed(() => scadaStore.panels)

const handleCreate = async () => {
  if (!formName.value.trim()) {
    ElMessage.warning('请输入项目名称')
    return
  }
  
  scadaStore.createPanel(
    formName.value,
    formDescription.value,
    formWidth.value,
    formHeight.value
  )
  
  ElMessage.success('创建成功')
  showCreateDialog.value = false
  resetForm()
}

const handleEdit = (id: string) => {
  router.push({ name: 'ScadaEdit', params: { id } })
}

const handleDelete = async (id: string) => {
  try {
    await ElMessageBox.confirm('确定要删除这个项目吗？此操作不可恢复。', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    scadaStore.deletePanel(id)
    ElMessage.success('删除成功')
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
    ElMessage.warning('请输入项目名称')
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
  
  ElMessage.success('保存成功')
  showEditDialog.value = false
  resetForm()
}

const resetForm = () => {
  formName.value = ''
  formDescription.value = ''
  formWidth.value = 1200
  formHeight.value = 800
  editingPanelId.value = null
}

const formatTime = (timestamp: number) => {
  return new Date(timestamp).toLocaleString('zh-CN')
}
</script>

<template>
  <div class="project-list-container">
    <div class="header">
      <h2>项目管理</h2>
      <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">
        新建项目
      </el-button>
    </div>

    <div v-if="projects.length === 0" class="empty-state">
      <el-empty description="暂无项目，请点击右上角创建新项目">
        <el-button type="primary" @click="showCreateDialog = true">创建项目</el-button>
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
          <h3 class="project-name">{{ panel.name }}</h3>
          <p class="project-desc">{{ panel.description || '暂无描述' }}</p>
          <div class="project-meta">
            <span>组件数: {{ panel.components?.length || 0 }}</span>
            <span>创建时间: {{ formatTime(panel.createdAt) }}</span>
          </div>
        </div>
        <div class="project-actions">
          <el-button 
            type="primary" 
            :icon="Edit"
            size="small"
            @click="handleEdit(panel.id)"
          >
            编辑
          </el-button>
          <el-button 
            type="warning" 
            :icon="Setting"
            size="small"
            @click="openEditDialog(panel)"
          >
            设置
          </el-button>
          <el-button 
            type="danger" 
            :icon="Delete"
            size="small"
            @click="handleDelete(panel.id)"
          >
            删除
          </el-button>
        </div>
      </el-card>
    </div>

    <!-- 创建项目对话框 -->
    <el-dialog
      v-model="showCreateDialog"
      title="新建项目"
      width="500px"
    >
      <el-form label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="formName" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="formDescription"
            type="textarea"
            placeholder="请输入项目描述"
            :rows="3"
          />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="画布宽度">
              <el-input-number v-model="formWidth" :min="400" :max="4000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="画布高度">
              <el-input-number v-model="formHeight" :min="300" :max="3000" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showCreateDialog = false">取消</el-button>
        <el-button type="primary" @click="handleCreate">确定</el-button>
      </template>
    </el-dialog>

    <!-- 编辑项目对话框 -->
    <el-dialog
      v-model="showEditDialog"
      title="编辑项目"
      width="500px"
    >
      <el-form label-width="80px">
        <el-form-item label="项目名称" required>
          <el-input v-model="formName" placeholder="请输入项目名称" />
        </el-form-item>
        <el-form-item label="项目描述">
          <el-input
            v-model="formDescription"
            type="textarea"
            placeholder="请输入项目描述"
            :rows="3"
          />
        </el-form-item>
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="画布宽度">
              <el-input-number v-model="formWidth" :min="400" :max="4000" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="画布高度">
              <el-input-number v-model="formHeight" :min="300" :max="3000" />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="showEditDialog = false">取消</el-button>
        <el-button type="primary" @click="handleSaveEdit">确定</el-button>
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
  margin: 0 0 8px 0;
  font-size: 18px;
  font-weight: 600;
  color: #303133;
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
