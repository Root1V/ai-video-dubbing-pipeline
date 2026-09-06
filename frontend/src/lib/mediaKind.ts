const VIDEO_EXTENSION_RE = /\.(mp4|mov|webm|mkv|avi)$/i

/** Un item del micro-video es un clip de video o una imagen (ver RM-36) --
 * `File.type` puede venir vacío para contenedores menos comunes (p.ej.
 * .mkv en algunos navegadores/SO), así que se combina con la extensión del
 * nombre de archivo, mismo criterio de tolerancia que el backend (que
 * deriva el tipo de la extensión real del path). */
export function isVideoFile(file: File): boolean {
  return file.type.startsWith('video/') || VIDEO_EXTENSION_RE.test(file.name)
}
