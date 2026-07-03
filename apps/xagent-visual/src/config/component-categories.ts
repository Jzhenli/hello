/**
 * Component category configuration
 * Uses unified componentMetaRegistry for all component data
 */

import type { ComponentTemplate } from '@/types/scada'
import { getAllTemplates } from '@/components/scada-components'

export interface CategoryConfig {
  key: string
  icon: string
  order: number
}

// Category definitions - add new categories here
export const COMPONENT_CATEGORIES: CategoryConfig[] = [
  { key: 'basic', icon: '📝', order: 1 },
  { key: 'chart', icon: '📊', order: 2 },
  { key: 'layout', icon: '📦', order: 3 },
]

// Get sorted categories
export const getSortedCategories = (): CategoryConfig[] => {
  return [...COMPONENT_CATEGORIES].sort((a, b) => a.order - b.order)
}

// Get components by category
export const getComponentsByCategory = (categoryKey: string): ComponentTemplate[] => {
  const templates = getAllTemplates()
  return templates.filter(t => t.category === `scadaComponentCategories.${categoryKey}`)
}

// Get all components grouped by category
export const getGroupedComponents = (): Record<string, ComponentTemplate[]> => {
  const grouped: Record<string, ComponentTemplate[]> = {}
  
  for (const category of getSortedCategories()) {
    const components = getComponentsByCategory(category.key)
    if (components.length > 0) {
      grouped[category.key] = components
    }
  }
  
  return grouped
}

// Get category config by key
export const getCategoryConfig = (key: string): CategoryConfig | undefined => {
  return COMPONENT_CATEGORIES.find(c => c.key === key)
}
