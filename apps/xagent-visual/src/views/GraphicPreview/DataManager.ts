export default class DataManager {
  currentSpaceRef: string = ''

  dataModels: any[] = []

  modelBindings: any[] = []

  interval: number | null = null

  setDataModels(list: any[]) {
    console.log('setDataModels', list)
  }

  spaceEquipmentsPromise: Promise<any[]> = Promise.resolve([])

  async setPointBindings(
    list: [
      any | undefined,
      ((value: any, type?: any, translatedText?: string) => void) | undefined
    ][]
  ): Promise<any[]> {
    console.log('setPointBindings', list)
    return []
  }

  setCurrentSpace(spaceRef?: string) {
    console.log('setCurrentSpace', spaceRef)
  }

  async getCurrentSpaceEquipmentByName(name: string, templateRef: string) {
    console.log('getCurrentSpaceEquipmentByName', name, templateRef)
    return undefined
  }

  setModelBindings(list: any[]) {
    console.log('setModelBindings', list)
  }

  pointTrendCache: Map<string, Promise<string>> = new Map()

  async getTrendRefByPointRef(pointRef: string) {
    console.log('getTrendRefByPointRef', pointRef)
    return ''
  }

  async getTrendRef(list: (any | undefined)[]) {
    console.log('getTrendRef', list)
    return []
  }

  async getTrendResult(
    list: (any | undefined)[],
    chartCondition: { jMode: number; dMode: number; startDate: Date; endDate: Date }
  ) {
    console.log('getTrendResult', list, chartCondition)
    return []
  }

  subscribedPointMap: Map<string, ((value: any, type?: any, translatedText?: string) => void)[]> =
    new Map()

  async getEquipmentByDataModelBinding(binding: any) {
    console.log('getEquipmentByDataModelBinding', binding)
    return undefined
  }

  pointValidateCache = new Map<string, Promise<boolean>>()
  modelValidateCache = new Map<string, Promise<any | undefined>>()

  async validateBinding(
    binding?: any | { cpntId: number; innerName?: string; bindingType?: undefined }
  ): Promise<
    | undefined
    | 'networkPointLost'
    | 'equipmentReferenceLost'
    | 'equipmentPointUnbind'
    | 'equipmentPointBindingLost'
  > {
    console.log('validateBinding', binding)
    return undefined
  }

  async validatePoint(pointRef: string) {
    console.log('validatePoint', pointRef)
    return true
  }

  async getEquipmentByRef(modelRef: string): Promise<any | undefined> {
    console.log('getEquipmentByRef', modelRef)
    return undefined
  }

  _eventCallback = new Map<String, any[]>()

  on(eventName: string, callback: any) {
    console.log('on', eventName, callback)
    return () => {}
  }
  off(eventName: string, callback?: any) {
    console.log('off', eventName, callback)
  }

  dispatch(eventName: string, event?: any, ...args: any[]) {
    console.log('dispatch', eventName, event, ...args)
  }

  dispose() {}
}
