import type { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

interface ProtectedRouteProps {
  children: ReactNode
  /** Ademas de requerir sesion, exige que el usuario tenga role "admin" --
   * redirige a "/" en vez de "/login" ya que si llega aca ya esta
   * autenticado, solo le falta el permiso. */
  adminOnly?: boolean
}

export function ProtectedRoute({ children, adminOnly }: ProtectedRouteProps) {
  const { isAuthenticated, isLoadingUser, user } = useAuth()

  if (isLoadingUser) {
    return (
      <div className="flex h-screen w-full items-center justify-center text-muted-foreground">
        Cargando…
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />
  }

  if (adminOnly && user?.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}
