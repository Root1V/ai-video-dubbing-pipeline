import { apiClient } from './client'
import type { User } from '../types/auth'
import type { UpdateUserInput, UserListResponse } from '../types/users'

export async function fetchUsers(page: number, pageSize: number): Promise<UserListResponse> {
  const { data } = await apiClient.get<UserListResponse>('/users', {
    params: { page, page_size: pageSize },
  })
  return data
}

export async function updateUser(id: string, input: UpdateUserInput): Promise<User> {
  const { data } = await apiClient.patch<User>(`/users/${id}`, input)
  return data
}
