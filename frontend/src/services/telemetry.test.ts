import { describe, expect, it } from 'vitest'
import { parseTelemetry } from './telemetry'

const baseTelemetry = {
  inspection_id: 'c9a1b8e4-7d2f-4a3e-b819-123456789abc',
  device_id: 'station-01',
  progress_percent: 100,
  blur_score: 182.4,
  stabilization_ms: 320,
  message: '검사가 완료되었습니다.',
}

function encodeTelemetry(value: Readonly<Record<string, string | number>>): Uint8Array {
  return new TextEncoder().encode(JSON.stringify(value))
}

describe('parseTelemetry', () => {
  it('parses the completed verdict from its dedicated field', () => {
    // Given
    const payload = encodeTelemetry({ ...baseTelemetry, stage: 'COMPLETED', primary_verdict: 'FAIL' })

    // When
    const telemetry = parseTelemetry(payload)

    // Then
    expect(telemetry).toMatchObject({ stage: 'COMPLETED', primaryVerdict: 'FAIL' })
  })

  it('parses the reposition attempt count', () => {
    // Given
    const payload = encodeTelemetry({ ...baseTelemetry, stage: 'REPOSITION', progress_percent: 40, reposition_count: 2 })

    // When
    const telemetry = parseTelemetry(payload)

    // Then
    expect(telemetry).toMatchObject({ stage: 'REPOSITION', repositionCount: 2 })
  })

  it('parses the captured image data URL', () => {
    // Given
    const captureImageUrl = 'data:image/jpeg;base64,ZmFrZS1jYXB0dXJl'
    const payload = encodeTelemetry({ ...baseTelemetry, stage: 'OCR', progress_percent: 30, capture_image_url: captureImageUrl })

    // When
    const telemetry = parseTelemetry(payload)

    // Then
    expect(telemetry).toMatchObject({ stage: 'OCR', captureImageUrl })
  })

  it.each(['ERROR', 'MANUAL_RETURN'] as const)('accepts the %s terminal stage', (stage) => {
    // Given
    const payload = encodeTelemetry({ ...baseTelemetry, stage })

    // When
    const telemetry = parseTelemetry(payload)

    // Then
    expect(telemetry.stage).toBe(stage)
  })
})
