import api from './index'

export interface ConfigBackup {
  filename: string
  size_mb: number
  created_at: string
}

export interface ConfigListResponse {
  configs: ConfigBackup[]
  total: number
}

export interface ExportConfigResponse {
  success: boolean
  file: string
  path: string
  size_mb: number
  tables: string[]
  records: number
  created_at: string
  error?: string
}

export interface ImportConfigResponse {
  success: boolean
  tables: string[]
  records: number
  auto_reload: boolean
  reload_result?: {
    success: boolean
    details: {
      config: boolean
      devices: boolean
    }
  }
  stop_result?: {
    success: boolean
    stopped_count: number
    stopped_plugins: string[]
  }
  message: string
  error?: string
}

export const configApi = {
  /**
   * 导出配置（创建备份）
   */
  async exportConfig(): Promise<ExportConfigResponse> {
    const res = await api.post('/api/config/export')
    return res.data
  },

  /**
   * 列出所有备份配置
   */
  async listConfigs(): Promise<ConfigListResponse> {
    const res = await api.get('/api/config/list')
    return res.data
  },

  /**
   * 获取API Token
   * 优先级：localStorage > 环境变量 > 默认token
   */
  getToken(): string {
    return localStorage.getItem('xagent_api_token')
      || import.meta.env.VITE_API_TOKEN
      || 'xagent_47808'
  },

  /**
   * 下载备份配置文件
   */
  getDownloadUrl(filename: string): string {
    // 获取API基础URL
    const baseURL = api.defaults.baseURL || ''
    // 获取token
    const token = this.getToken()
    // 返回带token的下载URL
    return `${baseURL}/api/config/export/download/${filename}?token=${token}`
  },

  /**
   * 导入配置
   */
  async importConfig(file: File, autoReload: boolean = true): Promise<ImportConfigResponse> {
    const formData = new FormData()
    formData.append('file', file)
    
    const res = await api.post('/api/config/import', formData, {
      params: { auto_reload: autoReload },
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
    return res.data
  },

  /**
   * 删除备份配置
   */
  async deleteConfig(filename: string): Promise<{ success: boolean; message: string }> {
    const res = await api.delete(`/api/config/export/${filename}`)
    return res.data
  }
}
