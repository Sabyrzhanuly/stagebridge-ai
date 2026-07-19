import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '../api/client'
import type { Server } from '../api/types'

export const useServersStore = defineStore('servers', () => {
  const servers = ref<Server[]>([])
  const loading = ref(false)

  async function fetchServers() {
    loading.value = true
    try {
      const { data } = await api.get<Server[]>('/servers')
      servers.value = data
    } finally {
      loading.value = false
    }
  }

  async function createServer(payload: {
    name: string; host: string; port: number; admin_user: string; admin_password: string
    ssh_user?: string; environment?: string
  }) {
    const { data } = await api.post<Server>('/servers', payload)
    servers.value.push(data)
    return data
  }

  async function updateServer(id: number, payload: Record<string, unknown>) {
    const { data } = await api.patch<Server>(`/servers/${id}`, payload)
    const idx = servers.value.findIndex(s => s.id === id)
    if (idx !== -1) servers.value[idx] = data
    return data
  }

  async function assignOrganization(id: number, organizationId: number) {
    const { data } = await api.put<Server>(`/servers/${id}/organization`, {
      organization_id: organizationId,
    })
    const idx = servers.value.findIndex(s => s.id === id)
    if (idx !== -1) servers.value[idx] = data
    return data
  }

  async function deleteServer(id: number) {
    await api.delete(`/servers/${id}`)
    servers.value = servers.value.filter(s => s.id !== id)
  }

  async function testServer(id: number) {
    const { data } = await api.post<{
      success: boolean
      version?: string | null
      error?: string | null
      error_code?: string | null
      error_title?: string | null
      error_hint?: string | null
    }>(`/servers/${id}/test`)
    const { data: updated } = await api.get<Server>(`/servers/${id}`)
    const idx = servers.value.findIndex(s => s.id === id)
    if (idx !== -1) servers.value[idx] = updated
    return data
  }

  return { servers, loading, fetchServers, createServer, updateServer, assignOrganization, deleteServer, testServer }
})
