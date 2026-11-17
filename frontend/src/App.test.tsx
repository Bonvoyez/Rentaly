import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import App from './App'
import { ThemeProvider } from './components/ThemeProvider'

function renderApp() {
  window.localStorage.setItem('rentaly-theme', 'light')
  return render(<ThemeProvider><App /></ThemeProvider>)
}

afterEach(() => {
  cleanup()
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
    const viewport = screen.getByRole('heading', { name: '검사 이력' }).closest('[data-admin-viewport]')
    expect(viewport).toBeInTheDocument()
    expect(viewport).toHaveClass('place-items-center', 'min-h-[100dvh]')
  })
})
