<script setup lang="ts">
import { useRoute, useRouter } from "vue-router";
import { useI18n } from "vue-i18n";
import { ArrowLeft } from "@element-plus/icons-vue";
import { GraphicEditor } from "@x-plateform/graphic-editor";
import { onMounted, ref } from "vue";

const route = useRoute();
const router = useRouter();
const { t } = useI18n();

const graphicData = ref<any | null>(null);

onMounted(() => {
  graphicData.value = JSON.parse("{}");
});

const onExit = () => {
  router.push({ name: "ScadaList" });
};

const onSave = (data: any, callback?: (success: boolean) => void) => {};

const showPreview = () => {};
</script>

<template>
  <div class="graphic-editor-container">
    <GraphicEditor
      class="graphic-editor"
      v-if="graphicData !== null"
      :graphicData="graphicData"
      @onExit="onExit()"
      @onSave="onSave"
      @showPreview="showPreview"
    ></GraphicEditor>
  </div>
</template>

<style scoped>
.graphic-editor-container {
  height: calc(100vh - 100px - 32px);
  display: flex;
  flex-direction: column;
  background-color: #f5f7fa;
}
</style>
