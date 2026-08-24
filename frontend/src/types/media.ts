export interface MediaPreview {
  title: string
  thumbnail_url: string | null
  duration_seconds: number | null
  source_url: string
  is_youtube: boolean
  youtube_video_id: string | null
}

export interface MediaSearchResponse {
  items: MediaPreview[]
}
