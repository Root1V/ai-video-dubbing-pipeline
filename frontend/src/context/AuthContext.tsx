import { useCallback, useState } from 'react'
import type { ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCurrentUser, login as loginRequest } from '../api/auth'
import { clearToken, getToken, setToken } from '../api/client'
import { AuthContext } from './auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [hasToken, setHasToken] = useState(() => Boolean(getToken()))

  const {
    data: user,
    isLoading: isLoadingUser,
    isError,
  } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: fetchCurrentUser,
    enabled: hasToken,
    retry: false,
  })

  const login = useCallback(
    async (email: string, password: string) => {
      const { access_token } = await loginRequest(email, password)
      setToken(access_token)
      setHasToken(true)
      await queryClient.invalidateQueries({ queryKey: ['auth', 'me'] })
    },
    [queryClient],
  )

  const logout = useCallback(() => {
    clearToken()
    setHasToken(false)
    queryClient.setQueryData(['auth', 'me'], undefined)
    queryClient.clear()
  }, [queryClient])

  const isAuthenticated = hasToken && !isError

  return (
    <AuthContext.Provider
      value={{ user, isLoadingUser, isAuthenticated, login, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}
