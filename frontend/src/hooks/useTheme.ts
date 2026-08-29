import { useContext } from 'react'
import { ThemeContext } from '../context/theme-context'
import type { ThemeContextValue } from '../context/theme-context'

export function useTheme(): ThemeContextValue {
  const ctx = useContext(ThemeContext)
  if (!ctx) {
    throw new Error('useTheme must be used within a ThemeProvider')
  }
  return ctx
}
