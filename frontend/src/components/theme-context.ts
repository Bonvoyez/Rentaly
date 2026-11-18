import { createContext, useContext } from 'react'

export type Theme = 'light' | 'dark'
export type ThemeContextValue = { readonly theme: Theme; readonly toggleTheme: () => void }

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext)
  if (value === null) throw new TypeError('useTheme must be used inside ThemeProvider')
  return value
}
