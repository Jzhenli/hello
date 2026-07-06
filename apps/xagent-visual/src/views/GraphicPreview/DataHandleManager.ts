
import DataManager from './DataManager'

export enum PointAttrValueType {
  Analog = 'Analog',
  State = 'State',
  String = 'String',
  Binary = 'Binary'
}

export enum BasicValueTypes {
  binary = 'binary',
  state = 'state',
  analog = 'analog',
  text = 'text',
  timestamp = 'timestamp'
}

export interface PointBinding {
  cpntId: number
  bindingType: 'point'
  pointRef: string
  pointName: string
  pointType: PointAttrValueType
  valueType: BasicValueTypes
  range: Record<string, unknown>
}

type PointCallback = (value: any, type?: any, translatedText?: string) => void
type BindingPair = [PointBinding | undefined, PointCallback | undefined]

interface PointCallbackInfo {
  callback: PointCallback
  pointType: PointAttrValueType
}

export default class DataHandleManager extends DataManager {
  private intervalId: number | null = null

  async setPointBindings(bindingPairs: BindingPair[]): Promise<any[]> {
    // 清理之前的定时器
    this.clearInterval()

    // 创建点ID到回调信息的映射
    const callbackMap = new Map<string, PointCallbackInfo[]>()

    // 收集有效点ID
    const pointIds = new Set<string>()

    bindingPairs.forEach(([binding, callback]) => {
      if (!binding || !callback) return

      const parts = binding.pointRef.split(',')
      if (parts.length < 2) return

      const pointId = parts[1]
      if (!pointId) return

      // 添加到点ID集合
      pointIds.add(pointId)

      // 添加到回调映射
      if (!callbackMap.has(pointId)) {
        callbackMap.set(pointId, [])
      }

      callbackMap.get(pointId)!.push({
        callback,
        pointType: binding.pointType
      })
    })

    const uniquePointIds = Array.from(pointIds)
    if (uniquePointIds.length === 0) {
      return []
    }

    // 立即获取初始数据
    try {
      await this.fetchAndUpdatePoints(uniquePointIds, callbackMap)
    } catch (error) {
      console.error('Initial points data fetch failed', error)
    }

    // 设置定时轮询
    // this.intervalId = window.setInterval(() => {
    //   this.fetchAndUpdatePoints(uniquePointIds, callbackMap)
    // }, IntervalTimeOut())

    return []
  }

  private async fetchAndUpdatePoints(
    pointIds: string[],
    callbackMap: Map<string, PointCallbackInfo[]>
  ) {
    console.log('fetchAndUpdatePoints', pointIds, callbackMap)
    try {
    //   const res = await readPointsDataById(pointIds)
    //   if (!res.data || !Array.isArray(res.data)) {
    //     console.warn('Invalid points data response', res)
    //     return
    //   }

    //   //console.log('Fetched points data:', res.data, pointIds)
    //   res.data.forEach((item: any) => {
    //     const callbackInfos = callbackMap.get(item.metric_id)
    //     if (!callbackInfos) return

    //     callbackInfos.forEach(({ callback, pointType }) => {
    //       try {
    //         let load = cloneDeep(item.value)
    //         if (item.value === true || item.value === 'true') {
    //           load = 1
    //         } else if (item.value === false || item.value === 'false') {
    //           load = 0
    //         }
    //         //console.log(`Updating point ${item.metric_id} with value:`, load, pointType)
    //         callback(load, pointType)
    //       } catch (err) {
    //         console.error(`Error executing callback for point ${item.metric_id}`, err)
    //       }
    //     })
    //   })
    } catch (err) {
      console.error('Failed to fetch points data', err)
    }
  }

  private clearInterval() {
    if (this.intervalId !== null) {
      window.clearInterval(this.intervalId)
      this.intervalId = null
    }
  }

  dispose() {
    this.clearInterval()
  }
}
