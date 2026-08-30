/**
 * Reproductor singleton para previews cortos (voces/musica): al iniciar uno
 * nuevo, para cualquier otro que estuviera sonando -- sin esto, hacer clic
 * en varios botones de preview rapido los superpondria a todos sonando a
 * la vez.
 */
let currentAudio: HTMLAudioElement | null = null
let currentKey: string | null = null

export function playPreview(key: string, url: string, onEnded: () => void): void {
  currentAudio?.pause()
  const audio = new Audio(url)
  audio.addEventListener('ended', onEnded)
  currentAudio = audio
  currentKey = key
  void audio.play()
}

export function stopPreview(): void {
  currentAudio?.pause()
  currentAudio = null
  currentKey = null
}

export function isPreviewKeyPlaying(key: string): boolean {
  return currentKey === key && currentAudio !== null && !currentAudio.paused
}
