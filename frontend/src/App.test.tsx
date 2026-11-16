import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import App from './App'

afterEach(() => {
  cleanup()
})

describe('Rentaly routes', () => {
  it('shows the kiosk ready state when opening the kiosk route', () => {
    // Given
    window.history.replaceState({}, '', '/kiosk')

    // When
    render(<App />)

    // Then
    expect(screen.getByRole('heading', { name: '반납을 시작할까요?' })).toBeVisible()
  })

  it('labels the admin authentication flow as mock-backed', () => {
    // Given
    window.history.replaceState({}, '', '/admin/login')

    // When
    render(<App />)

    // Then
    expect(screen.getByText('Mock 인증')).toBeVisible()
  })
})
