import { useCallback, useState } from 'react'
import type { ReactNode } from 'react'
import { applyTheme, getInitialTheme, THEME_STORAGE_KEY } from '../lib/theme'
import { ThemeContext } from './theme-context'

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setTheme] = useState(() => {
    const initial = getInitialTheme()
    applyTheme(initial)
    return initial
  })

  const toggleTheme = useCallback(() => {
    setTheme((current) => {
      const next = current === 'dark' ? 'light' : 'dark'
      localStorage.setItem(THEME_STORAGE_KEY, next)
      applyTheme(next)
      return next
    })
  }, [])

  return <ThemeContext.Provider value={{ theme, toggleTheme }}>{children}</ThemeContext.Provider>
}
