import { apiClient } from './client'
import type { MediaPreview, MediaSearchResponse } from '../types/media'

export async function fetchMediaPreview(url: string): Promise<MediaPreview> {
  const { data } = await apiClient.get<MediaPreview>('/media/preview', {
    params: { url },
  })
  return data
}

export async function searchYoutubeVideos(
  query: string,
  limit = 12,
): Promise<MediaPreview[]> {
  const { data } = await apiClient.get<MediaSearchResponse>('/media/search', {
    params: { q: query, limit },
  })
  return data.items
}
