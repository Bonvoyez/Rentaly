export const telemetryStages = [
  'MOUNTED', 'STABILIZING', 'BLUR_CHECK', 'OCR',
  'LED_CHECK', 'AI_INFERENCE', 'COMPLETED', 'REPOSITION',
] as const

export type TelemetryStage = (typeof telemetryStages)[number]
export type FinalStatus = 'PASS' | 'FAIL' | 'ERROR' | 'PENDING_REVIEW'
export type KioskView = 'ready' | 'ocr' | 'led' | 'ai' | 'pass' | 'complete' | 'reposition' | 'fail' | 'manual' | 'error'
export type InspectionDetailKind = 'pending' | 'pass' | 'error'

export type Telemetry = {
  readonly inspectionId: string
  readonly deviceId: string
  readonly stage: TelemetryStage
  readonly progressPercent: number
  readonly blurScore: number
  readonly stabilizationMs: number
  readonly message: string
}

export type InspectionRecord = {
  readonly id: string
  readonly device: string
  readonly inspectedAt: string
  readonly serial: string
  readonly aiResult: string
  readonly status: FinalStatus
}

export type DeviceStatus = 'ONLINE' | 'INSPECTING' | 'OFFLINE' | 'MAINTENANCE'
export type DeviceRecord = {
  readonly id: string
  readonly location: string
  readonly status: DeviceStatus
  readonly lastSeen: string
  readonly inspectionsToday: number
  readonly firmware: string
}

export function assertNever(value: never): never {
  throw new TypeError(`Unhandled variant: ${String(value)}`)
}
