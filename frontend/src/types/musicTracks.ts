export type MusicCategory =
  | 'calm_meditation'
  | 'commercials_professional'
  | 'energy_pop'
  | 'happy_romantic'
  | 'social_network'

export interface MusicTrack {
  id: string
  title: string
  category: MusicCategory
  created_at: string
}

export interface MusicTrackListResponse {
  items: MusicTrack[]
}

export interface CreateMusicTrackInput {
  title: string
  category: MusicCategory
  file: File
}
