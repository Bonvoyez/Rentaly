import { expect, it, vi } from 'vitest'
import { subscribeToTelemetry } from './telemetry'

const broker = vi.hoisted(() => {
  const handlers = new Map<string, (...args: unknown[]) => void>()
  return {
    handlers,
    connect: vi.fn(() => ({
      on: (event: string, handler: (...args: unknown[]) => void) => { handlers.set(event, handler) },
      subscribe: vi.fn(),
      end: vi.fn(),
    })),
  }
})

vi.mock('mqtt', () => ({ default: { connect: broker.connect } }))

it('does not mark an open MQTT connection as failed for one malformed telemetry message', () => {
  const onConnection = vi.fn()
  const onTelemetry = vi.fn()
  const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  const unsubscribe = subscribeToTelemetry('wss://example.com/mqtt', 'station-01', onTelemetry, onConnection)

  broker.handlers.get('connect')?.()
  broker.handlers.get('message')?.('inspection/station-01/telemetry', new TextEncoder().encode('{bad json'))

  expect(onConnection).toHaveBeenLastCalledWith('connected')
  expect(onTelemetry).not.toHaveBeenCalled()
  unsubscribe()
  warning.mockRestore()
})
