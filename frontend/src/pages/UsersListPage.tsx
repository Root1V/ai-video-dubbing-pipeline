import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import axios from 'axios'
import { ChevronLeft, ChevronRight } from 'lucide-react'
import { fetchUsers, updateUser } from '../api/users'
import { useAuth } from '../hooks/useAuth'
import type { User, UserRole } from '../types/auth'
import { Card, CardContent } from '../components/ui/Card'
import { Badge } from '../components/ui/Badge'
import { Select } from '../components/ui/Select'
import { Switch } from '../components/ui/Switch'
import { Button } from '../components/ui/Button'
import { Alert } from '../components/ui/Alert'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui/Table'
import { formatDateTime } from '../lib/format'

const PAGE_SIZE = 20

const ROLE_LABELS: Record<UserRole, string> = {
  admin: 'Admin',
  member: 'Miembro',
}

export function UsersListPage() {
  const { user: currentUser } = useAuth()
  const queryClient = useQueryClient()
  const [page, setPage] = useState(1)
  const [error, setError] = useState<string | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['users', page],
    queryFn: () => fetchUsers(page, PAGE_SIZE),
  })

  const mutation = useMutation({
    mutationFn: ({ id, input }: { id: string; input: { role?: UserRole; is_active?: boolean } }) =>
      updateUser(id, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err) => {
      setError(
        axios.isAxiosError(err)
          ? ((err.response?.data as { detail?: string } | undefined)?.detail ??
              'No se pudo actualizar el usuario.')
          : 'No se pudo actualizar el usuario.',
      )
    },
  })

  const users = data?.items ?? []
  const total = data?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function isSelf(user: User): boolean {
    return user.id === currentUser?.id
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Usuarios</h1>
        <p className="text-sm text-muted-foreground">
          Administra quién tiene acceso al dashboard y con qué rol.
        </p>
      </div>

      {error && <Alert variant="error" onDismiss={() => setError(null)}>{error}</Alert>}

      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <p className="p-6 text-sm text-muted-foreground">Cargando…</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Rol</TableHead>
                  <TableHead>Activo</TableHead>
                  <TableHead>Creado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((user) => (
                  <TableRow key={user.id}>
                    <TableCell className="font-medium">
                      {user.name}
                      {isSelf(user) && (
                        <span className="ml-1.5 text-xs text-muted-foreground">(tú)</span>
                      )}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{user.email}</TableCell>
                    <TableCell>
                      {isSelf(user) ? (
                        <Badge variant="secondary">{ROLE_LABELS[user.role]}</Badge>
                      ) : (
                        <div className="w-32">
                          <Select
                            value={user.role}
                            onChange={(e) =>
                              mutation.mutate({
                                id: user.id,
                                input: { role: e.target.value as UserRole },
                              })
                            }
                          >
                            {(Object.keys(ROLE_LABELS) as UserRole[]).map((role) => (
                              <option key={role} value={role}>
                                {ROLE_LABELS[role]}
                              </option>
                            ))}
                          </Select>
                        </div>
                      )}
                    </TableCell>
                    <TableCell>
                      <Switch
                        checked={user.is_active}
                        disabled={isSelf(user)}
                        onCheckedChange={(checked) =>
                          mutation.mutate({ id: user.id, input: { is_active: checked } })
                        }
                      />
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(user.created_at)}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {total > 0 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Página {page} de {totalPages} · {total} usuario{total === 1 ? '' : 's'}
          </span>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
            >
              <ChevronLeft className="h-4 w-4" />
              Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            >
              Siguiente
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
