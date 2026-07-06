<template>
  <GraphicRender
    ref="graphicRenderItem"
    v-if="graphicData != null"
    :manager="dataHandleManager"
    :graphicData="parsedGraphics"
    @graphicLoaded="graphicLoaded"
    @itemClick="itemclick"
  ></GraphicRender>
</template>

<script setup lang="ts">
import { GraphicRender } from "@x-plateform/graphic-editor";
import { ref, computed, onMounted } from "vue";
import DataHandleManager from "./DataHandleManager";

const graphicData = ref<any | null>(null);
const graphicRenderItem = ref<InstanceType<typeof GraphicRender> | null>(null);

const isShowModal = ref(false);
const clickParam = ref({});

const dataHandleManager = new DataHandleManager();

onMounted(() => {
  console.log("onMounted", graphicRenderItem);

  graphicData.value = {
    data: '{"meta":{"width":1920,"height":1080,"backgroundColor":"white","enableAutoAlign":true,"sensitivity":25,"deviceInitRate":0.1,"renderAlign":{"alignX":"left","alignY":"top"},"lightEffect":{"enabled":false,"darken":0.5,"compositeType":"multiply"}},"customImageCache":[],"layers":[{"name":"背景图层","uqId":3,"items":[{"className":"LargePlateHeatExchanger","viewPosIdx":0,"center":{"x":1399.3926247288503,"y":335.4013015184382},"rotation":0,"width":143.3,"height":152.3,"keepAspectRatio":true,"rate":0.1,"bindingNavigation":null,"bindingMultiplePopup":{"type":"dashboard","dashboardAttr":{"position":"left"},"pointsAttr":{"width":200,"height":100},"chartAttr":{"width":200,"height":200}},"colorShader":"#fff","backgroundColor":"#ccc","enableAnimationConfig":true,"multiFrameAnimationConfig":[{"series":[],"type":"loop","focus":false},{"series":[{"duration":1.8,"offsetPosition":{"x":0,"y":0},"offsetRotation":0,"opacity":0.6,"focus":false,"backgroundColor":"#fff"},{"duration":1.8,"offsetPosition":{"x":0,"y":0},"offsetRotation":0,"opacity":0,"focus":false,"backgroundColor":"#fff"}],"type":"loop","focus":false}],"inputPrimaryValue":{"bindingList":[{"cpntId":1783066168696520,"bindingType":"point","pointRef":"001,point_3,,","pointName":"","pointType":"Analog","valueType":"analog","range":{}}],"animationConfig":{"continous":["0","1"],"discrete":["0","1"]}},"outputPrimaryValue":{"animationConfig":{"continous":["0","1"],"discrete":["0","1"]}},"uqId":1,"id":1,"childrenUqIds":[{"uqId":2,"index":0}]},{"uqId":2,"className":"BasicShapeBindingValue","center":{"x":1327.7426247288502,"y":223.25130151843814},"width":71.99989318847656,"height":24,"rotation":0,"borderRadius":0,"enableBackground":false,"backgroundColor":"#ccc","showBorder":false,"borderColor":"#aaa","borderWidth":0,"enableShadow":false,"shadowColor":"#000","enableBorderShadow":false,"borderShadowColor":"#000","shadowBlur":0,"shadowOffset":{"x":0,"y":0},"enableInnerShadow":false,"innerShadowColor":"#000","innerShadowBlur":0,"text":"---- ----","fontFamily":"思源黑体","fontSize":24,"color":"#666","fontWeight":"normal","fontStyle":"normal","textDecoration":"none","textAlign":"left","paddingTop":0,"paddingRight":0,"paddingBottom":0,"paddingLeft":0,"enableTextShadow":false,"textShadowOffset":{"x":0,"y":0},"textShadowBlur":10,"parentUqId":1,"propName":"inputPrimaryValue","propLabel":"主输入","displayOrder":0,"showPropLabel":true,"showValue":true,"showUnit":true,"showState":false,"precision":2,"bindingValue":{"bindingList":[{"cpntId":1783066168696520,"bindingType":"point","pointRef":"001,point_3,,","pointName":"","pointType":"Analog","valueType":"analog","range":{}}],"animationConfig":{"continous":["0","1"],"discrete":["0","1"]}},"bindingNavigation":null,"bindingPopup":null,"bindingMultiplePopup":{"type":"dashboard","dashboardAttr":{"position":"left"},"pointsAttr":{"width":200,"height":100},"chartAttr":{"width":200,"height":200}},"lastTextWidth":71.99989318847656,"id":2}]}],"equipList":[]}',
    previewImage:
      "data:image/png;base64,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",
    lastUpdateTime: "2026/7/3 16:09:39",
  };
});

const parsedGraphics = computed(() => {
  let ret = {};
  try {
    if (graphicData.value) {
      ret = JSON.parse(graphicData.value.data || "{}");
    }
  } catch (e) {
    console.error(e);
  }
  return ret;
});

const graphicLoaded = () => {
  //graphicRenderItem.value?.zoomFit()
};

const itemclick = (params: any) => {
  if (params.action === "setValue") {
    console.log("itemclick", params);
    clickParam.value = params;
    isShowModal.value = true;
  }
};
</script>

<style lang="scss" scoped></style>
