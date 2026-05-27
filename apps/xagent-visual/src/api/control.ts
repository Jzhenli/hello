import api from './index'

export interface ControlCommandRequest {
  target_service: string
  target_asset: string
  operation: string
  parameters: Record<string, unknown>
  expiry?: number
}

export interface ControlCommandResponse {
  command_id: string
  status: string
  message: string
}

export interface ControlCommandStatus {
  command_id: string
  status: 'PENDING' | 'ACCEPTED' | 'EXECUTING' | 'COMPLETED' | 'FAILED' | 'EXPIRED'
  result: unknown
  error: string | null
  created_at: number
  updated_at: number
}

export const controlApi = {
  async submitCommand(request: ControlCommandRequest): Promise<ControlCommandResponse> {
    const res = await api.post('/api/control', request)
    return res.data
  },

  async getCommandStatus(commandId: string): Promise<ControlCommandStatus> {
    const res = await api.get(`/api/control/${commandId}`)
    return res.data
  },

  async writeSetpoint(
    targetService: string,
    targetAsset: string,
    point: string,
    value: number | boolean | string,
    expiry = 30
  ): Promise<ControlCommandResponse> {
    return this.submitCommand({
      target_service: targetService,
      target_asset: targetAsset,
      operation: 'write_setpoint',
      parameters: { point, value },
      expiry
    })
  }
}
