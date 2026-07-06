import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { useScadaStore } from '@/stores/scada'
import { ElMessage, ElMessageBox } from 'element-plus'
import type { SlideshowConfig as SlideshowConfigType } from '../../vant/SlideshowConfig.vue'

export function useProjectList() {
  const { t } = useI18n()
  const router = useRouter()
  const scadaStore = useScadaStore()

  const showCreateDialog = ref(false)
  const showEditDialog = ref(false)
  const showSlideshowConfig = ref(false)
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

  const handlePreview = (panel: any) => {
    scadaStore.isFullscreenPreview = true
    if (panel.type === 'Graphic') {
      router.push({ name: 'GraphicPreview', params: { id: panel.id } })
    } else {
      router.push({ name: 'ScadaPreview', params: { id: panel.id } })
    }
  }

  const handleStartSlideshow = (config: SlideshowConfigType) => {
    router.push({
      name: 'SlideshowPreview',
      query: {
        interval: String(config.interval),
        loop: config.loop ? 'true' : 'false',
        autoPlay: config.autoPlay ? 'true' : 'false',
        transition: config.transition,
        scope: config.scope,
      },
    })
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

  return {
    t,
    showCreateDialog,
    showEditDialog,
    showSlideshowConfig,
    formName,
    formDescription,
    formType,
    editingPanelId,
    projects,
    handleCreate,
    handleEdit,
    handlePreview,
    handleStartSlideshow,
    handleDelete,
    openEditDialog,
    handleSaveEdit,
    formatTime,
  }
}
