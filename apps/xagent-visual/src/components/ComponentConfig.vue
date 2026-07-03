<template>
  <div class="config-panel">
    <div class="panel-header">
      <h3>
        ⚙️
        {{
          component
            ? t("componentConfig.componentConfig")
            : t("componentConfig.panelConfig")
        }}
      </h3>
    </div>

    <div v-if="component" class="panel-body">
      <!-- 基本信息 -->
      <div class="config-section">
        <div class="section-title">{{ t("componentConfig.basicInfo") }}</div>
        <div class="form-group">
          <label>{{ t("componentConfig.name") }}</label>
          <input
            type="text"
            :value="displayName"
            @input="
              scadaStore.updateComponent(component.id, {
                name: ($event.target as HTMLInputElement).value,
              })
            "
          />
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>X</label>
            <input
              type="number"
              :value="component.x"
              @input="
                scadaStore.moveComponent(
                  component.id,
                  +($event.target as HTMLInputElement).value,
                  component.y,
                )
              "
            />
          </div>
          <div class="form-group">
            <label>Y</label>
            <input
              type="number"
              :value="component.y"
              @input="
                scadaStore.moveComponent(
                  component.id,
                  component.x,
                  +($event.target as HTMLInputElement).value,
                )
              "
            />
          </div>
        </div>
        <div class="form-row">
          <div class="form-group">
            <label>{{ t("componentConfig.width") }}</label>
            <input
              type="number"
              :value="component.style.width"
              @input="
                updateStyle('width', +($event.target as HTMLInputElement).value)
              "
            />
          </div>
          <div class="form-group">
            <label>{{ t("componentConfig.height") }}</label>
            <input
              type="number"
              :value="component.style.height"
              @input="
                updateStyle(
                  'height',
                  +($event.target as HTMLInputElement).value,
                )
              "
            />
          </div>
        </div>
      </div>

      <!-- 点位绑定 -->
      <div class="config-section">
        <div class="section-title">{{ t("componentConfig.pointBinding") }}</div>
        <div class="form-group">
          <label>{{ t("componentConfig.device") }}</label>
          <el-select
            v-model="selectedDevice"
            @change="handleDeviceChange"
            clearable
            :placeholder="t('componentConfig.selectDevice')"
            style="width: 100%"
          >
            <el-option
              v-for="device in pointStore.devices"
              :key="device.asset"
              :value="device.asset"
              :label="device.name"
            />
          </el-select>
        </div>
        <div class="form-group">
          <label>{{ t("componentConfig.point") }}</label>
          <el-select
            v-model="selectedPoint"
            @change="handlePointChange"
            clearable
            :placeholder="t('componentConfig.selectPoint')"
            style="width: 100%"
            :disabled="!selectedDevice"
          >
            <el-option
              v-for="point in availablePoints"
              :key="point.name"
              :value="point.name"
              :label="
                point.name +
                (point.description ? ' (' + point.description + ')' : '')
              "
            />
          </el-select>
        </div>
      </div>

      <!-- 动态渲染组件专属配置面板 -->
      <component
        v-if="componentConfigPanel && component"
        :is="componentConfigPanel"
        :component="component"
      />
    </div>

    <!-- 面板设置（未选中组件时显示） -->
    <div v-else-if="currentPanel" class="panel-body">
      <div class="config-section">
        <div class="section-title">{{ t("componentConfig.canvasSize") }}</div>
        <div class="form-row">
          <div class="form-group">
            <label>{{ t("componentConfig.width") }}</label>
            <input
              type="number"
              v-model.number="panelWidth"
              min="400"
              max="4096"
              @change="updatePanelSize"
            />
          </div>
          <div class="form-group">
            <label>{{ t("componentConfig.height") }}</label>
            <input
              type="number"
              v-model.number="panelHeight"
              min="300"
              max="4096"
              @change="updatePanelSize"
            />
          </div>
        </div>
        <div class="preset-buttons">
          <el-button
            v-for="preset in presetSizes"
            :key="preset.key"
            size="small"
            @click="applyPreset(preset)"
          >
            {{ t("componentConfig." + preset.key) }}
          </el-button>
        </div>
      </div>

      <div class="config-section">
        <div class="section-title">{{ t("componentConfig.canvasStyle") }}</div>
        <div class="form-group">
          <label>{{ t("componentConfig.bgType") }}</label>
          <el-radio-group v-model="panelBgType" @change="onBgTypeChange">
            <el-radio value="color">{{
              t("componentConfig.bgColor")
            }}</el-radio>
            <el-radio value="image">{{
              t("componentConfig.bgImage")
            }}</el-radio>
          </el-radio-group>
        </div>
        <div v-if="panelBgType === 'color'" class="form-group">
          <label>{{ t("componentConfig.backgroundColor") }}</label>
          <div class="color-input">
            <input
              type="color"
              v-model="panelBgColor"
              @change="updatePanelSize"
            />
            <input
              type="text"
              v-model="panelBgColor"
              @change="updatePanelSize"
              placeholder="#f0f2f5"
            />
          </div>
        </div>
        <div v-else class="form-group">
          <label>{{ t("componentConfig.backgroundImage") }}</label>
          <div v-if="panelBgImage" class="bg-image-card">
            <div class="bg-image-preview">
              <img :src="panelBgImage" alt="bg" />
            </div>
            <div class="bg-image-actions">
              <el-button size="small" @click="triggerBgImageUpload">{{
                t("componentConfig.changeBgImage")
              }}</el-button>
              <el-button size="small" type="danger" @click="removeBgImage">{{
                t("componentConfig.removeBgImage")
              }}</el-button>
            </div>
          </div>
          <div v-else class="bg-upload-area" @click="triggerBgImageUpload">
            <span class="upload-icon">+</span>
            <span class="upload-text">{{
              t("componentConfig.uploadBgImage")
            }}</span>
          </div>
          <input
            ref="bgImageInput"
            type="file"
            accept="image/*"
            class="hidden-file-input"
            @change="handleBgImageUpload"
          />
        </div>
        <div class="form-group">
          <label>{{ t("componentConfig.gridSize") }}</label>
          <input
            type="number"
            v-model.number="panelGrid"
            min="10"
            max="50"
            step="5"
            @change="updatePanelSize"
          />
        </div>
      </div>

      <div class="config-section">
        <div class="section-title">{{ t("componentConfig.panelInfo") }}</div>
        <div class="info-item">
          <span class="info-label">{{ t("componentConfig.panelName") }}</span>
          <span class="info-value">{{ currentPanel.name }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{
            t("componentConfig.componentCount")
          }}</span>
          <span class="info-value">{{ currentPanel.components.length }}</span>
        </div>
        <div class="info-item">
          <span class="info-label">{{
            t("componentConfig.canvasDimensions")
          }}</span>
          <span class="info-value"
            >{{ currentPanel.width }} × {{ currentPanel.height }}</span
          >
        </div>
      </div>
    </div>

    <div v-else class="empty-state">
      <span class="empty-icon">📦</span>
      <p>{{ t("componentConfig.selectComponentHint") }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, markRaw } from "vue";
import { useI18n } from "vue-i18n";
import { useScadaStore } from "@/stores/scada";
import { usePointStore } from "@/stores/points";
import type { PointBinding } from "@/types/scada";
import { getConfigPanel } from "@/components/scada-components";

const { t } = useI18n();
const scadaStore = useScadaStore();
const pointStore = usePointStore();

const selectedDevice = ref<string>("");
const selectedPoint = ref<string>("");

const component = computed(() => scadaStore.selectedComponent);
const currentPanel = computed(() => scadaStore.currentPanel);

const currentBinding = computed(() => component.value?.binding);

// 获取当前组件类型的配置面板
const componentConfigPanel = computed(() => {
  if (!component.value) return null;
  const panel = getConfigPanel(component.value.type);
  return panel ? markRaw(panel) : null;
});

// Display name: translate if it's a template key, otherwise show custom name
const displayName = computed(() => {
  if (!component.value) return "";
  if (component.value.name?.startsWith("scadaComponentNames.")) {
    return t(component.value.name);
  }
  return component.value.name || component.value.type;
});

const panelWidth = ref(1200);
const panelHeight = ref(800);
const panelBgColor = ref("#f0f2f5");
const panelGrid = ref(20);
const panelBgImage = ref<string | undefined>(undefined);
const panelBgType = ref<"color" | "image">("color");
const bgImageInput = ref<HTMLInputElement | null>(null);

watch(
  currentPanel,
  (panel) => {
    if (panel) {
      panelWidth.value = panel.width;
      panelHeight.value = panel.height;
      panelBgColor.value = panel.backgroundColor;
      panelGrid.value = panel.grid;
      panelBgImage.value = panel.backgroundImage;
      panelBgType.value = panel.backgroundImage ? "image" : "color";
    }
  },
  { immediate: true },
);

watch(
  currentBinding,
  (binding) => {
    if (binding) {
      selectedDevice.value = binding.deviceId;
      selectedPoint.value = binding.pointName;
    } else {
      selectedDevice.value = "";
      selectedPoint.value = "";
    }
  },
  { immediate: true },
);

const availablePoints = computed(() => {
  if (!selectedDevice.value) return [];
  const device = pointStore.devices.find(
    (d) => d.asset === selectedDevice.value || d.name === selectedDevice.value,
  );
  return device?.points || [];
});

const handleDeviceChange = () => {
  selectedPoint.value = "";
  if (!component.value) return;
  if (!selectedDevice.value) {
    scadaStore.bindPoint(component.value.id, null);
  }
};

const handlePointChange = () => {
  if (!component.value) return;

  if (!selectedDevice.value || !selectedPoint.value) {
    scadaStore.bindPoint(component.value.id, null);
    return;
  }

  const point = availablePoints.value.find(
    (p) => p.name === selectedPoint.value,
  );
  if (!point) return;

  const binding: PointBinding = {
    deviceId: selectedDevice.value,
    pointName: selectedPoint.value,
    pointDescription: point.description,
    unit: point.unit,
  };

  scadaStore.bindPoint(component.value.id, binding);
};

const updateStyle = (key: string, value: any) => {
  if (!component.value) return;
  scadaStore.updateComponent(component.value.id, {
    style: { ...component.value.style, [key]: value },
  });
};

const updatePanelSize = () => {
  if (!currentPanel.value) return;
  scadaStore.updatePanel({
    width: panelWidth.value,
    height: panelHeight.value,
    backgroundColor: panelBgColor.value,
    grid: panelGrid.value,
    backgroundImage:
      panelBgType.value === "image" ? panelBgImage.value : undefined,
  });
};

const onBgTypeChange = (type: "color" | "image") => {
  if (type === "color") {
    // Clear image when switching to color mode
    panelBgImage.value = undefined;
  }
  updatePanelSize();
};

const handleBgImageUpload = (e: Event) => {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;

  const reader = new FileReader();
  reader.onload = (event) => {
    const result = event.target?.result as string;
    if (result) {
      panelBgImage.value = result;
      panelBgType.value = "image";
      updatePanelSize();
    }
  };
  reader.readAsDataURL(file);

  // Reset input
  input.value = "";
};

const removeBgImage = () => {
  panelBgImage.value = undefined;
  panelBgType.value = "color";
  updatePanelSize();
};

const triggerBgImageUpload = () => {
  bgImageInput.value?.click();
};

const presetSizes = [
  { key: "small", name: "componentConfig.small", width: 800, height: 600 },
  { key: "medium", name: "componentConfig.medium", width: 1200, height: 800 },
  { key: "large", name: "componentConfig.large", width: 1920, height: 1080 },
  {
    key: "extraWide",
    name: "componentConfig.extraWide",
    width: 2560,
    height: 1080,
  },
];

const applyPreset = (preset: (typeof presetSizes)[0]) => {
  panelWidth.value = preset.width;
  panelHeight.value = preset.height;
  updatePanelSize();
};
</script>

<style scoped>
.config-panel {
  width: 280px;
  background: var(--bg-container);
  border-left: 1px solid var(--border-base);
  display: flex;
  flex-direction: column;
}

.panel-header {
  height: 44px;
  padding: 0 12px;
  border-bottom: 1px solid var(--border-base);
  background: var(--bg-hover);
  display: flex;
  align-items: center;
}

.panel-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.panel-body {
  flex: 1;
  padding: 12px;
  overflow-y: auto;
}

.config-section {
  margin-bottom: 16px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-light);
}

.config-section:last-child {
  border-bottom: none;
}

.section-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  margin-bottom: 10px;
}

.form-group {
  margin-bottom: 10px;
}

.form-group label {
  display: block;
  font-size: 12px;
  color: var(--text-primary);
  margin-bottom: 4px;
}

.hidden-file-input {
  display: none;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 6px 8px;
  border: 1px solid var(--border-base);
  border-radius: 4px;
  font-size: 13px;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: var(--color-primary);
}

.form-row {
  display: flex;
  gap: 8px;
}

.form-row .form-group {
  flex: 1;
}

.color-input {
  display: flex;
  gap: 8px;
}

.color-input input[type="color"] {
  width: 40px;
  padding: 2px;
  cursor: pointer;
}

.color-input input[type="text"] {
  flex: 1;
}

.preset-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}

.bg-image-control {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.bg-image-control .el-button {
  align-self: flex-start;
}

.bg-image-card {
  border: 1px solid var(--border-base);
  border-radius: 6px;
  overflow: hidden;
}

.bg-image-preview {
  width: 100%;
  height: 100px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.bg-image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.bg-image-actions {
  display: flex;
  gap: 8px;
  padding: 8px;
  background: var(--bg-container);
}

.bg-image-actions .el-button {
  flex: 1;
}

.bg-upload-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100px;
  border: 2px dashed var(--border-base);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.bg-upload-area:hover {
  border-color: var(--color-primary);
  background: rgba(64, 158, 255, 0.05);
}

.upload-icon {
  font-size: 32px;
  color: var(--text-secondary);
  line-height: 1;
  margin-bottom: 8px;
}

.upload-text {
  font-size: 12px;
  color: var(--text-secondary);
}

.preset-buttons .el-button {
  flex: 1;
  min-width: calc(50% - 3px);
  font-size: 11px;
}

.info-item {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-light);
}

.info-item:last-child {
  border-bottom: none;
}

.info-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.info-value {
  font-size: 12px;
  color: var(--text-primary);
  font-weight: 500;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 8px;
}

.empty-state p {
  margin: 0;
  font-size: 13px;
}
</style>
