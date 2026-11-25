import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ThemeProvider } from './components/ThemeProvider'
import type { Telemetry } from './domain/inspection'
import type { TelemetryConnection } from './services/telemetry'

let emitTelemetry: ((telemetry: Telemetry) => void) | undefined
let emitConnection: ((connection: TelemetryConnection) => void) | undefined
const publishStart = vi.hoisted(() => vi.fn(async () => true))

vi.mock('./services/telemetry', () => ({
  subscribeToTelemetry: (_brokerUrl: string, _deviceId: string, onTelemetry: (telemetry: Telemetry) => void, onConnection: (connection: TelemetryConnection) => void) => {
    emitTelemetry = onTelemetry
    emitConnection = onConnection
    return { close: () => undefined, publishStart }
  },
}))

function renderApp() {
  window.localStorage.setItem('rentaly-theme', 'light')
  return render(<ThemeProvider><App /></ThemeProvider>)
}

afterEach(() => {
  cleanup()
  emitTelemetry = undefined
  emitConnection = undefined
  publishStart.mockClear()
  vi.unstubAllEnvs()
})

describe('Rentaly routes', () => {
  it('shows the kiosk ready state when opening the kiosk route', () => {
    // Given
    window.history.replaceState({}, '', '/kiosk')

    // When
    renderApp()

    // Then
    expect(screen.getByRole('heading', { name: '반납을 시작할까요?' })).toBeVisible()
  })

  it('shows the camera feed behind the placement guide and falls back when it fails', () => {
    vi.stubEnv('VITE_CAMERA_FEED_URL', 'https://camera.example.com/video_feed')
    window.history.replaceState({}, '', '/kiosk')
    renderApp()

    const preview = screen.getByRole('img', { name: '실시간 카메라 프리뷰' })
    expect(preview).toHaveAttribute('src', 'https://camera.example.com/video_feed')
    expect(preview.parentElement).toHaveClass('h-[200px]', 'w-[282px]')
    expect(preview).toHaveClass('object-cover')
    expect(screen.getByLabelText('보드 배치 가이드')).toHaveClass('inset-7')

    fireEvent.error(preview)
    expect(screen.getByRole('img', { name: '검사대 중앙에 놓인 Raspberry Pi 보드' })).toBeVisible()
    expect(screen.getByLabelText('보드 배치 가이드')).toBeVisible()
  })

  it('publishes START and keeps the camera stream visible during inspection', async () => {
    vi.stubEnv('VITE_APP_MODE', 'kiosk')
    vi.stubEnv('VITE_MQTT_BROKER_URL', 'wss://example.com/mqtt')
    vi.stubEnv('VITE_CAMERA_FEED_URL', 'https://camera.example.com/video_feed')
    window.history.replaceState({}, '', '/kiosk')
    renderApp()

    act(() => emitConnection?.('connected'))
    fireEvent.click(screen.getByRole('button', { name: '검사 시작' }))

    await waitFor(() => expect(publishStart).toHaveBeenCalledOnce())
    expect(await screen.findByRole('img', { name: '실시간 카메라 프리뷰' })).toHaveAttribute('src', 'https://camera.example.com/video_feed')
    expect(screen.getByText('고유번호 확인')).toBeVisible()
  })

  it('labels the admin authentication flow as mock-backed', () => {
    // Given
    window.history.replaceState({}, '', '/admin/login')

    // When
    renderApp()

    // Then
    expect(screen.getByText('Mock 인증')).toBeVisible()
  })

  it('centers the admin frame inside the viewport', () => {
    // Given
    window.history.replaceState({}, '', '/admin/inspections')

    // When
    renderApp()

    // Then
    const shell = screen.getByRole('heading', { name: '검사 이력' }).closest('main')?.parentElement
    expect(shell).toBeInTheDocument()
    expect(shell).toHaveClass('max-w-[1440px]', 'w-full')
  })

  it('keeps unknown admin routes inside the admin flow', () => {
    // Given
    window.history.replaceState({}, '', '/admin/not-a-page')

    // When
    renderApp()

    // Then
    expect(screen.getByText('Mock 인증')).toBeVisible()
    expect(screen.queryByRole('heading', { name: '반납을 시작할까요?' })).not.toBeInTheDocument()
  })

  it('blocks admin routes in a kiosk deployment', () => {
    // Given
    vi.stubEnv('VITE_APP_MODE', 'kiosk')
    window.history.replaceState({}, '', '/admin/login')

    // When
    renderApp()

    // Then
    expect(screen.getByRole('heading', { name: '반납을 시작할까요?' })).toBeVisible()
    expect(screen.queryByText('Mock 인증')).not.toBeInTheDocument()
  })

  it('blocks kiosk routes in an admin deployment', () => {
    // Given
    vi.stubEnv('VITE_APP_MODE', 'admin')
    window.history.replaceState({}, '', '/kiosk')

    // When
    renderApp()

    // Then
    expect(screen.getByRole('heading', { name: '관리자 로그인' })).toBeVisible()
    expect(screen.queryByText('Mock 인증')).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '반납을 시작할까요?' })).not.toBeInTheDocument()
  })

  it('keeps the camera live and uses the captured image only if the stream fails', () => {
    // Given
    const captureImageUrl = 'data:image/jpeg;base64,ZmFrZS1jYXB0dXJl'
    vi.stubEnv('VITE_APP_MODE', 'kiosk')
    vi.stubEnv('VITE_MQTT_BROKER_URL', 'ws://localhost:9001')
    vi.stubEnv('VITE_CAMERA_FEED_URL', 'https://camera.example.com/video_feed')
    window.history.replaceState({}, '', '/kiosk')
    renderApp()

    // When
    act(() => emitTelemetry?.({
      inspectionId: 'c9a1b8e4-7d2f-4a3e-b819-123456789abc',
      deviceId: 'station-01',
      stage: 'OCR',
      progressPercent: 30,
      blurScore: 182.4,
      stabilizationMs: 320,
      message: 'OCR',
      captureImageUrl,
    }))

    // Then
    const preview = screen.getByRole('img', { name: '실시간 카메라 프리뷰' })
    expect(preview).toHaveAttribute('src', 'https://camera.example.com/video_feed')
    fireEvent.error(preview)
    expect(screen.getByRole('img', { name: '검사대에서 촬영한 Raspberry Pi 보드' })).toHaveAttribute('src', captureImageUrl)
  })

  it('keeps a received inspection visible without calling a dropped MQTT connection demo mode', () => {
    vi.stubEnv('VITE_APP_MODE', 'kiosk')
    vi.stubEnv('VITE_MQTT_BROKER_URL', 'wss://rentaly.duckdns.org/mqtt')
    window.history.replaceState({}, '', '/kiosk')
    renderApp()

    act(() => emitConnection?.('connected'))
    act(() => emitTelemetry?.({
      inspectionId: 'inspection-1', deviceId: 'station-01', stage: 'AI_INFERENCE',
      progressPercent: 86, blurScore: 180, stabilizationMs: 300, message: '외관 검사 중',
    }))
    act(() => emitConnection?.('disconnected'))

    expect(screen.getByText('연결 끊김')).toBeVisible()
    expect(screen.queryByText('데모 모드')).not.toBeInTheDocument()
    expect(screen.getByText('86%')).toBeVisible()
  })
})
