import { expect, it, vi } from 'vitest'
import { subscribeToTelemetry } from './telemetry'

const broker = vi.hoisted(() => {
  const handlers = new Map<string, (...args: unknown[]) => void>()
  return {
    handlers,
    connect: vi.fn(() => ({
      connected: true,
      on: (event: string, handler: (...args: unknown[]) => void) => { handlers.set(event, handler) },
      subscribe: vi.fn(),
      publish: vi.fn((_topic: string, _payload: string, _options: unknown, callback: (error?: Error) => void) => callback()),
      end: vi.fn(),
    })),
  }
})

vi.mock('mqtt', () => ({ default: { connect: broker.connect } }))

it('does not mark an open MQTT connection as failed for one malformed telemetry message', () => {
  const onConnection = vi.fn()
  const onTelemetry = vi.fn()
  const warning = vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  const session = subscribeToTelemetry('wss://example.com/mqtt', 'station-01', onTelemetry, onConnection)

  broker.handlers.get('connect')?.()
  broker.handlers.get('message')?.('inspection/station-01/telemetry', new TextEncoder().encode('{bad json'))

  expect(onConnection).toHaveBeenLastCalledWith('connected')
  expect(onTelemetry).not.toHaveBeenCalled()
  session.close()
  warning.mockRestore()
})

it('publishes the START command to the selected device', async () => {
  const session = subscribeToTelemetry('wss://example.com/mqtt', 'station-01', vi.fn(), vi.fn())

  expect(await session.publishStart()).toBe(true)
  const client = broker.connect.mock.results.at(-1)?.value
  expect(client?.publish).toHaveBeenCalledWith(
    'inspection/station-01/command',
    '{"action":"START"}',
    expect.objectContaining({ qos: 0, retain: false }),
    expect.any(Function),
  )
  session.close()
})
