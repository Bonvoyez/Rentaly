export const telemetryStages = [
  'MOUNTED', 'STABILIZING', 'BLUR_CHECK', 'OCR',
  'LED_CHECK', 'AI_INFERENCE', 'COMPLETED', 'REPOSITION',
  'ERROR', 'MANUAL_RETURN',
] as const

export type TelemetryStage = (typeof telemetryStages)[number]
export type PrimaryVerdict = 'PASS' | 'FAIL'
export type FinalStatus = 'PASS' | 'FAIL' | 'ERROR' | 'PENDING_REVIEW' | 'CONFIRMED_PASS' | 'CONFIRMED_REJECT' | 'UNKNOWN'
export type KioskView = 'ready' | 'ocr' | 'led' | 'ai' | 'pass' | 'complete' | 'reposition' | 'fail' | 'manual' | 'error'
export type InspectionDetailKind = 'pending' | 'pass' | 'error'

type TelemetryCommon = {
  readonly inspectionId: string
  readonly deviceId: string
  readonly progressPercent: number
  readonly blurScore: number
  readonly stabilizationMs: number
  readonly message: string
  readonly captureImageUrl?: string
}

export type Telemetry = TelemetryCommon & (
  | { readonly stage: Exclude<TelemetryStage, 'COMPLETED' | 'REPOSITION'> }
  | { readonly stage: 'COMPLETED'; readonly primaryVerdict: PrimaryVerdict }
  | { readonly stage: 'REPOSITION'; readonly repositionCount: number }
)

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
