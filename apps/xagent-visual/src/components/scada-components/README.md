# SCADA 组件库

## 目录结构

```
scada-components/
├── types.ts              # 公共类型定义（ComponentType、StyleConfig 等）
├── registry.ts           # 组件注册表
├── index.ts              # 统一导出（自动聚合所有组件模板）
├── gauge/                # 仪表盘组件
│   ├── index.vue         # 组件实现
│   └── metadata.ts       # 组件配置（GaugeConfig 接口 + 模板定义）
├── chart/                # 图表组件
│   ├── index.vue
│   └── metadata.ts       # ChartConfig + chartLine/chartBar 两个模板
├── indicator/            # 指示灯组件
│   ├── index.vue
│   └── metadata.ts
├── switch/               # 开关组件
│   ├── index.vue
│   └── metadata.ts
├── text/                 # 文本组件
│   ├── index.vue
│   └── metadata.ts
└── button/               # 按钮组件
    ├── index.vue
    └── metadata.ts
```

## 如何添加新组件（只需在 scada-components/ 下新建文件夹）

### 1. 新建组件文件夹

例如新增 `slider` 组件：

```
scada-components/
└── slider/
    ├── index.vue         # 组件实现
    └── metadata.ts       # 组件配置
```

### 2. 编写 metadata.ts

```typescript
import type { ComponentMetadata } from '../types'

export interface SliderConfig {
  min: number
  max: number
  step: number
}

export const sliderMetadata: ComponentMetadata = {
  template: {
    type: 'slider',
    name: 'scadaComponentNames.slider',
    icon: '🎚️',
    category: 'scadaComponentCategories.control',
    defaultStyle: { width: 200, height: 40 },
    defaultConfig: {
      sliderConfig: { min: 0, max: 100, step: 1 }
    }
  }
}
```

### 3. 在 types.ts 中添加类型

```typescript
export type ComponentType =
  | 'gauge'
  | 'slider'        // ← 新增
  // ...
```

### 4. 在 registry.ts 中注册组件

```typescript
import ScadaSlider from './slider/index.vue'

export const componentRegistry: Record<string, Component> = {
  // ...
  'slider': ScadaSlider,  // ← 新增
}
```

### 5. 在 index.ts 中聚合模板和导出

```typescript
// 导出配置类型
export type { SliderConfig } from './slider/metadata'

// 聚合模板
import { sliderMetadata } from './slider/metadata'

export const COMPONENT_TEMPLATES = [
  // ... 现有模板
  sliderMetadata.template,
]

// 导出组件
export { default as ScadaSlider } from './slider/index.vue'
```

## 分类说明

组件通过 `category` 字段归类，在 `metadata.ts` 的 `template` 中指定：

| 分类 key | 说明 |
|---------|------|
| `scadaComponentCategories.basic` | 基础组件 |
| `scadaComponentCategories.gauge` | 仪表组件 |
| `scadaComponentCategories.chart` | 图表组件 |
| `scadaComponentCategories.indicator` | 指示组件 |
| `scadaComponentCategories.control` | 控制组件 |
| `scadaComponentCategories.layout` | 布局组件 |

## 文件职责

| 文件 | 职责 |
|------|------|
| `types.ts` | 公共类型（ComponentType、StyleConfig、ComponentTemplate） |
| `xxx/metadata.ts` | 组件专属配置类型 + 模板定义 |
| `xxx/index.vue` | 组件实现 |
| `registry.ts` | 组件类型 → 组件实例映射 |
| `index.ts` | 统一导出 + 聚合所有 COMPONENT_TEMPLATES |
