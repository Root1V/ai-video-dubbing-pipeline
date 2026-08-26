export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
}

export type UserRole = 'admin' | 'member'

export interface User {
  id: string
  email: string
  name: string
  role: UserRole
  is_active: boolean
  created_at: string
}
