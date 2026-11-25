import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ThemeProvider } from './components/ThemeProvider'
import type { Telemetry } from './domain/inspection'

let emitTelemetry: ((telemetry: Telemetry) => void) | undefined

vi.mock('./services/telemetry', () => ({
  subscribeToTelemetry: (_brokerUrl: string, _deviceId: string, onTelemetry: (telemetry: Telemetry) => void) => {
    emitTelemetry = onTelemetry
    return () => undefined
  },
}))

function renderApp() {
  window.localStorage.setItem('rentaly-theme', 'light')
  return render(<ThemeProvider><App /></ThemeProvider>)
}

afterEach(() => {
  cleanup()
  emitTelemetry = undefined
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

  it('shows the captured inspection image received through telemetry', () => {
    // Given
    const captureImageUrl = 'data:image/jpeg;base64,ZmFrZS1jYXB0dXJl'
    vi.stubEnv('VITE_APP_MODE', 'kiosk')
    vi.stubEnv('VITE_MQTT_BROKER_URL', 'ws://localhost:9001')
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
    expect(screen.getByRole('img', { name: '검사대에서 촬영한 Raspberry Pi 보드' })).toHaveAttribute('src', captureImageUrl)
  })
})
