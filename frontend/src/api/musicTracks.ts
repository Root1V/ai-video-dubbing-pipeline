import { apiClient } from './client'
import type {
  CreateMusicTrackInput,
  MusicCategory,
  MusicTrack,
  MusicTrackListResponse,
} from '../types/musicTracks'

export async function fetchMusicTracks(category?: MusicCategory): Promise<MusicTrack[]> {
  const { data } = await apiClient.get<MusicTrackListResponse>('/music-tracks', {
    params: category ? { category } : undefined,
  })
  return data.items
}

export async function createMusicTrack(input: CreateMusicTrackInput): Promise<MusicTrack> {
  const formData = new FormData()
  formData.set('title', input.title)
  formData.set('category', input.category)
  formData.set('file', input.file)
  const { data } = await apiClient.post<MusicTrack>('/music-tracks', formData)
  return data
}

export async function deleteMusicTrack(id: string): Promise<void> {
  await apiClient.delete(`/music-tracks/${id}`)
}
