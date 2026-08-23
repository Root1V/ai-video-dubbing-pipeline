import { createContext } from 'react'
import type { User } from '../types/auth'

export interface AuthContextValue {
  user: User | undefined
  isLoadingUser: boolean
  isAuthenticated: boolean
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)
