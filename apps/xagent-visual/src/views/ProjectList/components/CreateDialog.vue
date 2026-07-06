<template>
  <el-dialog
    v-model="visible"
    :title="$t('scada.newProject')"
    width="500px"
  >
    <el-form label-width="80px">
      <el-form-item :label="$t('scada.projectName')" required>
        <el-input v-model="name" :placeholder="$t('scada.enterProjectName')" />
      </el-form-item>
      <el-form-item :label="$t('scada.projectType')" required>
        <el-select v-model="type" :placeholder="$t('scada.selectProjectType')">
          <el-option :label="$t('scada.dashboardType')" value="Dashboard" />
          <el-option :label="$t('scada.graphicType')" value="Graphic" />
        </el-select>
      </el-form-item>
      <el-form-item :label="$t('scada.projectDesc')">
        <el-input
          v-model="description"
          type="textarea"
          :placeholder="$t('scada.enterProjectDesc')"
          :rows="3"
        />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="visible = false">{{ $t('common.cancel') }}</el-button>
      <el-button type="primary" @click="$emit('create')">{{ $t('common.confirm') }}</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
const visible = defineModel<boolean>({ required: true })
const name = defineModel<string>('name', { required: true })
const type = defineModel<'Dashboard' | 'Graphic'>('type', { required: true })
const description = defineModel<string>('description', { required: true })

defineEmits<{
  (e: 'create'): void
}>()
</script>
