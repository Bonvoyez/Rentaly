import mqtt, { type MqttClient } from 'mqtt'
import { z } from 'zod'
import { telemetryStages, type Telemetry } from '../domain/inspection'

const telemetrySchema = z.object({
  inspection_id: z.string().min(1),
  device_id: z.string().min(1),
  stage: z.enum(telemetryStages),
  progress_percent: z.number().int().min(0).max(100),
  blur_score: z.number(),
  stabilization_ms: z.number().int().nonnegative(),
  message: z.string(),
})

export function parseTelemetry(payload: Uint8Array): Telemetry {
  const raw: unknown = JSON.parse(new TextDecoder().decode(payload))
  const parsed = telemetrySchema.parse(raw)
  return {
    inspectionId: parsed.inspection_id,
    deviceId: parsed.device_id,
    stage: parsed.stage,
    progressPercent: parsed.progress_percent,
    blurScore: parsed.blur_score,
    stabilizationMs: parsed.stabilization_ms,
    message: parsed.message,
  }
}

export type TelemetryConnection = 'connecting' | 'connected' | 'disconnected' | 'error'

export function subscribeToTelemetry(brokerUrl: string, deviceId: string, onTelemetry: (telemetry: Telemetry) => void, onConnection: (state: TelemetryConnection) => void): () => void {
  const client: MqttClient = mqtt.connect(brokerUrl)
  const topic = `inspection/${deviceId}/telemetry`
  onConnection('connecting')
  client.on('connect', () => { onConnection('connected'); client.subscribe(topic) })
  client.on('reconnect', () => onConnection('connecting'))
  client.on('offline', () => onConnection('disconnected'))
  client.on('error', () => onConnection('error'))
  client.on('message', (_topic, payload) => {
    try { onTelemetry(parseTelemetry(payload)) } catch (error: unknown) { if (error instanceof Error) onConnection('error'); else throw error }
  })
  return () => client.end(true)
}
