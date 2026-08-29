import type { Theme } from '../context/theme-context'

export const THEME_STORAGE_KEY = 'prosodia-theme'

/** Sin preferencia explícita guardada, el tema se elige por la hora del
 * sistema del usuario (no por `prefers-color-scheme`, que refleja el tema
 * del SO/navegador, no la hora): de día (6:00 a 17:59) modo claro, de noche
 * modo oscuro. */
export function getSystemHourTheme(): Theme {
  const hour = new Date().getHours()
  return hour >= 6 && hour < 18 ? 'light' : 'dark'
}

export function getStoredTheme(): Theme | null {
  const stored = localStorage.getItem(THEME_STORAGE_KEY)
  return stored === 'light' || stored === 'dark' ? stored : null
}

export function getInitialTheme(): Theme {
  return getStoredTheme() ?? getSystemHourTheme()
}

export function applyTheme(theme: Theme): void {
  document.documentElement.classList.toggle('dark', theme === 'dark')
}
