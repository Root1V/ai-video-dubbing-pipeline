/** Reads a theme color as its raw "H S% L%" triplet (shadcn/Tailwind CSS
 * variable convention, see index.css) so canvas/SVG drawing code matches the
 * app's palette instead of a hardcoded color that would clash if the theme
 * changes. Shared by every canvas-based visualizer (AudioWaveformPlayer,
 * LiveWaveformVisualizer) so they read the same tokens the same way. */
export function themeColor(cssVariable: string, fallback: string, alpha = 1): string {
  if (typeof window === 'undefined') return fallback
  const raw = getComputedStyle(document.documentElement).getPropertyValue(cssVariable).trim()
  if (!raw) return fallback
  return alpha < 1 ? `hsl(${raw} / ${alpha})` : `hsl(${raw})`
}
