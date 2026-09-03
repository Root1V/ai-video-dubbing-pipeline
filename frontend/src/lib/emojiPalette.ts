/** Set curado de emojis disponibles para RM-32 -- los `id` DEBEN coincidir
 * exactamente con los nombres de archivo bundleados en
 * `src/video_translator/assets/emojis/{id}.png` (backend). `label` es el
 * glyph Unicode real, usado solo como texto del botón en el picker -- el
 * navegador SÍ puede mostrar emoji normalmente, el problema es específico
 * del pipeline ffmpeg/libass del backend (ver docs/roadmap.md RM-32). */
export interface EmojiPaletteItem {
  id: string
  label: string
}

export const EMOJI_PALETTE: EmojiPaletteItem[] = [
  { id: 'fuego', label: '🔥' },
  { id: 'risa', label: '😂' },
  { id: 'corazon', label: '❤️' },
  { id: 'ojos_corazon', label: '😍' },
  { id: 'pulgar_arriba', label: '👍' },
  { id: 'fiesta', label: '🎉' },
  { id: 'destellos', label: '✨' },
  { id: 'cien', label: '💯' },
  { id: 'susto', label: '😱' },
  { id: 'manos_arriba', label: '🙌' },
  { id: 'ojos', label: '👀' },
  { id: 'calavera', label: '💀' },
  { id: 'carita_corazones', label: '🥰' },
  { id: 'llanto', label: '😭' },
  { id: 'pensando', label: '🤔' },
  { id: 'aplausos', label: '👏' },
  { id: 'estrella', label: '⭐' },
  { id: 'cool', label: '😎' },
  { id: 'triste', label: '😢' },
  { id: 'sonrisa', label: '😊' },
]
