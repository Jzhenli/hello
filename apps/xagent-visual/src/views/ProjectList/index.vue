<template>
  <div class="project-list-container">
    <div class="header">
      <h2>{{ $t('scada.title') }}</h2>
      <div class="header-actions">
        <el-button type="success" :icon="VideoPlay" @click="showSlideshowConfig = true">
          {{ $t('scada.previewAll') }}
        </el-button>
        <el-button type="primary" :icon="Plus" @click="showCreateDialog = true">
          {{ $t('scada.newProject') }}
        </el-button>
      </div>
    </div>

    <div v-if="projects.length === 0" class="scrollable-content">
      <div class="empty-state">
        <el-empty :description="$t('scada.noProjects')">
          <el-button type="primary" @click="showCreateDialog = true">{{ $t('scada.createProject') }}</el-button>
        </el-empty>
      </div>
    </div>

    <div v-else class="scrollable-content">
      <div class="project-grid">
        <ProjectCard
          v-for="panel in projects"
          :key="panel.id"
          :panel="panel"
          :format-time="formatTime"
          @preview="handlePreview"
          @edit="handleEdit"
          @settings="openEditDialog"
          @delete="handleDelete"
        />
      </div>
    </div>

    <CreateDialog
      v-model="showCreateDialog"
      v-model:name="formName"
      v-model:type="formType"
      v-model:description="formDescription"
      @create="handleCreate"
    />

    <EditDialog
      v-model="showEditDialog"
      v-model:name="formName"
      v-model:description="formDescription"
      @save="handleSaveEdit"
    />

    <SlideshowConfig
      v-model="showSlideshowConfig"
      @start="handleStartSlideshow"
    />
  </div>
</template>

<script setup lang="ts">
import { Plus, VideoPlay } from '@element-plus/icons-vue'
import SlideshowConfig from '../vant/SlideshowConfig.vue'
import ProjectCard from './components/ProjectCard.vue'
import CreateDialog from './components/CreateDialog.vue'
import EditDialog from './components/EditDialog.vue'
import { useProjectList } from './composables/useProjectList'

const {
  showCreateDialog,
  showEditDialog,
  showSlideshowConfig,
  formName,
  formDescription,
  formType,
  projects,
  handleCreate,
  handleEdit,
  handlePreview,
  handleStartSlideshow,
  handleDelete,
  openEditDialog,
  handleSaveEdit,
  formatTime,
} = useProjectList()
</script>

<style scoped>
.project-list-container {
  height: calc(100vh - 100px - 32px);
  background-color: var(--bg-secondary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  flex-shrink: 0;
}

.header h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  gap: 8px;
}

.empty-state {
  background: var(--bg-container);
  border-radius: 8px;
  padding: 60px 20px;
}

.scrollable-content {
  flex: 1;
  overflow-y: auto;
  padding-right: 8px;
}

.project-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 20px;
}
</style>
