import mqtt, { type MqttClient } from 'mqtt'
import { z } from 'zod'
import { assertNever, telemetryStages, type Telemetry } from '../domain/inspection'

const telemetryCommonSchema = z.object({
  inspection_id: z.string().min(1),
  device_id: z.string().min(1),
  progress_percent: z.number().int().min(0).max(100),
  blur_score: z.number(),
  stabilization_ms: z.number().int().nonnegative(),
  message: z.string(),
  capture_image_url: z.string().startsWith('data:image/jpeg;base64,').optional(),
})

const telemetryEnvelopeSchema = telemetryCommonSchema.extend({ stage: z.enum(telemetryStages) })
const completedTelemetrySchema = telemetryCommonSchema.extend({
  stage: z.literal('COMPLETED'),
  primary_verdict: z.enum(['PASS', 'FAIL']),
})
const repositionTelemetrySchema = telemetryCommonSchema.extend({
  stage: z.literal('REPOSITION'),
  reposition_count: z.number().int().min(1).max(3),
})

type TelemetryCommon = z.infer<typeof telemetryCommonSchema>

function mapCommonTelemetry(parsed: TelemetryCommon) {
  const common = {
    inspectionId: parsed.inspection_id,
    deviceId: parsed.device_id,
    progressPercent: parsed.progress_percent,
    blurScore: parsed.blur_score,
    stabilizationMs: parsed.stabilization_ms,
    message: parsed.message,
  }
  return parsed.capture_image_url ? { ...common, captureImageUrl: parsed.capture_image_url } : common
}

export function parseTelemetry(payload: Uint8Array): Telemetry {
  const raw: unknown = JSON.parse(new TextDecoder().decode(payload))
  const envelope = telemetryEnvelopeSchema.parse(raw)
  switch (envelope.stage) {
    case 'COMPLETED': {
      const parsed = completedTelemetrySchema.parse(raw)
      return { ...mapCommonTelemetry(parsed), stage: parsed.stage, primaryVerdict: parsed.primary_verdict }
    }
    case 'REPOSITION': {
      const parsed = repositionTelemetrySchema.parse(raw)
      return { ...mapCommonTelemetry(parsed), stage: parsed.stage, repositionCount: parsed.reposition_count }
    }
    case 'MOUNTED':
    case 'STABILIZING':
    case 'BLUR_CHECK':
    case 'OCR':
    case 'LED_CHECK':
    case 'AI_INFERENCE':
    case 'ERROR':
    case 'MANUAL_RETURN':
      return { ...mapCommonTelemetry(envelope), stage: envelope.stage }
    default:
      return assertNever(envelope.stage)
  }
}

export type TelemetryConnection = 'connecting' | 'connected' | 'disconnected' | 'error'
export type TelemetrySession = {
  readonly close: () => void
  readonly publishStart: () => Promise<boolean>
}

export function subscribeToTelemetry(brokerUrl: string, deviceId: string, onTelemetry: (telemetry: Telemetry) => void, onConnection: (state: TelemetryConnection) => void): TelemetrySession {
  const client: MqttClient = mqtt.connect(brokerUrl)
  const topic = `inspection/${deviceId}/telemetry`
  onConnection('connecting')
  client.on('connect', () => { onConnection('connected'); client.subscribe(topic, { qos: 0 }) })
  client.on('reconnect', () => onConnection('connecting'))
  client.on('offline', () => onConnection('disconnected'))
  client.on('error', () => onConnection('error'))
  client.on('message', (_topic, payload) => {
    let telemetry: Telemetry
    try { telemetry = parseTelemetry(payload) }
    catch (error: unknown) {
      if (!(error instanceof Error)) throw error
      console.warn('Ignoring invalid MQTT telemetry message', error)
      return
    }
    onTelemetry(telemetry)
  })
  return {
    close: () => client.end(true),
    publishStart: () => new Promise<boolean>(resolve => {
      if (!client.connected) { resolve(false); return }
      client.publish(`inspection/${deviceId}/command`, JSON.stringify({ action: 'START' }), { qos: 0, retain: false }, error => resolve(!error))
    }),
  }
}
