import { apiClient } from './client'

/**
 * Trae una muestra de audio empaquetada con la app (voz publica o pista de
 * musica) como blob autenticado y devuelve una object URL reproducible --
 * un <audio src="/api/..."> plano no puede llevar el Bearer token, mismo
 * motivo que useProjectArtifactUrl.ts para los artefactos de un proyecto.
 */
export async function fetchVoiceSampleUrl(voiceId: string): Promise<string> {
  const { data } = await apiClient.get(`/samples/voices/${voiceId}`, { responseType: 'blob' })
  return URL.createObjectURL(data as Blob)
}

export async function fetchMusicSampleUrl(trackId: string): Promise<string> {
  const { data } = await apiClient.get(`/samples/music/${trackId}`, { responseType: 'blob' })
  return URL.createObjectURL(data as Blob)
}

export async function fetchEmojiSampleUrl(emojiId: string): Promise<string> {
  const { data } = await apiClient.get(`/samples/emoji/${emojiId}`, { responseType: 'blob' })
  return URL.createObjectURL(data as Blob)
}
