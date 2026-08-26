import type { User } from './auth'

export interface UserListResponse {
  items: User[]
  total: number
  page: number
  page_size: number
}

export interface UpdateUserInput {
  role?: User['role']
  is_active?: boolean
}
