# SCADA 组件库

## 目录结构

```
scada-components/
├── types.ts              # 公共类型定义（StyleConfig、ScadaComponentMeta）
├── registry.ts           # 组件注册表 + 查询/注册 API
├── index.ts              # 统一导出（类型 + 注册表 API）
├── gauge/                # 仪表盘组件
│   ├── index.vue
│   ├── metadata.ts       # 组件元数据（视图 + 配置面板 + 模板）
│   └── ConfigPanel.vue   # 专属配置面板
├── chart/                # 图表组件（折线图 + 柱状图）
│   ├── index.vue
│   ├── metadata.ts       # chartLineMeta + chartBarMeta 两个元数据
│   └── ConfigPanel.vue
├── indicator/            # 指示灯组件
│   ├── index.vue
│   ├── metadata.ts
│   └── ConfigPanel.vue
├── switch/               # 开关组件
│   ├── index.vue
│   └── metadata.ts
├── slider/               # 滑块组件
│   ├── index.vue
│   └── metadata.ts
├── text/                 # 文本组件
│   ├── index.vue
│   └── metadata.ts
├── image/                # 图片组件
│   ├── index.vue
│   ├── metadata.ts
│   └── ConfigPanel.vue
├── button/               # 按钮组件
│   ├── index.vue
│   └── metadata.ts
└── container/            # 容器组件
    ├── index.vue
    └── metadata.ts
```

## 核心设计

- **统一注册表** `componentMetaRegistry`：`type → ScadaComponentMeta` 映射，整合组件视图、配置面板、模板信息
- **自动类型推导**：`ComponentType` 由注册表键名自动推导，无需手动维护联合类型
- **查询 API**：`getComponent` / `getConfigPanel` / `getComponentTemplate` / `getAllTemplates` 等
- **动态注册**：`registerComponent(meta)` 支持运行时注册新组件

## 如何添加新组件（两步）

### 1. 新建组件文件夹

在 `scada-components/` 下新建文件夹，包含 `index.vue` 和 `metadata.ts`（可选 `ConfigPanel.vue`）：

```
scada-components/
└── my-component/
    ├── index.vue         # 组件实现
    ├── metadata.ts       # 组件元数据
    └── ConfigPanel.vue   # 专属配置面板（可选）
```

### 2. 在 registry.ts 中注册

**registry.ts** — 添加配置接口、导入元数据、注册映射：

```typescript
// 1. 添加配置接口
export interface MyComponentConfig {
  // 组件配置字段...
}

// 2. 导入元数据
import { myComponentMeta } from './my-component/metadata'

// 3. 添加到注册表
export const componentMetaRegistry = {
  // ... 已有组件
  'my-component': myComponentMeta,  // ← 新增
}
```

**metadata.ts** — 从 registry 导入配置类型：

```typescript
import type { ScadaComponentMeta } from '../types'
import type { MyComponentConfig } from '../registry'
import MyComponent from './index.vue'

export const myComponentMeta: ScadaComponentMeta = {
  type: 'my-component',
  component: MyComponent,
  configPanel: null, // 或导入 ConfigPanel 组件
  template: {
    name: 'scadaComponentNames.myComponent',
    icon: '🔧',
    category: 'scadaComponentCategories.control',
    defaultStyle: { width: 200, height: 100 },
    defaultConfig: {
      myComponentConfig: { /* 默认配置 */ }
    }
  }
}
```

> **注意**：`ComponentType` 由注册表自动推导，无需修改 `types.ts`。配置接口统一在 `registry.ts` 中定义，无需修改 `index.ts`。

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
| `types.ts` | 公共类型（StyleConfig、ScadaComponentMeta） |
| `xxx/metadata.ts` | 组件元数据（视图 + 配置面板 + 模板，统一为 ScadaComponentMeta） |
| `xxx/index.vue` | 组件视图实现 |
| `xxx/ConfigPanel.vue` | 组件专属配置面板（可选，无则使用通用配置） |
| `registry.ts` | 统一注册表 + 查询/注册 API |
| `index.ts` | 统一导出（类型 + 注册表 API） |
