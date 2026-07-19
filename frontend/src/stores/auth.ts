import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import api from '../api/client'

export interface AuthOrganization {
  id: number
  name: string
  slug: string
}

export interface AuthUser {
  id: number
  username: string
  email: string
  role: string
  is_active: boolean
  is_super_admin?: boolean
  organization?: AuthOrganization | null
  org_role?: string | null
  member_id?: number | null
  permissions?: string[]
}

export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  const accessToken = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))
  const activeOrgId = ref<number | null>(
    localStorage.getItem('active_org_id') ? Number(localStorage.getItem('active_org_id')) : null
  )

  const isAuthenticated = computed(() => !!accessToken.value)
  const permissions = computed(() => user.value?.permissions || [])
  const organizationName = computed(() => user.value?.organization?.name || '')
  const isSuperAdmin = computed(() => user.value?.is_super_admin === true || user.value?.role === 'admin')

  function hasPermission(perm: string): boolean {
    return permissions.value.includes(perm)
  }

  function setActiveOrganizationId(id: number | null) {
    activeOrgId.value = id
    if (id) {
      api.defaults.headers.common['X-Organization-Id'] = String(id)
      localStorage.setItem('active_org_id', String(id))
    } else {
      delete api.defaults.headers.common['X-Organization-Id']
      localStorage.removeItem('active_org_id')
    }
  }

  function setTokens(access: string, refresh: string) {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem('access_token', access)
    localStorage.setItem('refresh_token', refresh)
    api.defaults.headers.common['Authorization'] = `Bearer ${access}`
  }

  function clearAuth() {
    user.value = null
    accessToken.value = null
    refreshToken.value = null
    setActiveOrganizationId(null)
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    delete api.defaults.headers.common['Authorization']
  }

  async function login(username: string, password: string) {
    const { data } = await api.post('/auth/login', { username, password })
    setTokens(data.access_token, data.refresh_token)
    await fetchUser()
  }

  async function fetchUser() {
    try {
      const { data } = await api.get<AuthUser>('/auth/me')
      user.value = data
      if (data.is_super_admin && activeOrgId.value) {
        api.defaults.headers.common['X-Organization-Id'] = String(activeOrgId.value)
      }
    } catch {
      clearAuth()
    }
  }

  async function refresh() {
    if (!refreshToken.value) throw new Error('No refresh token')
    const { data } = await api.post('/auth/refresh', { refresh_token: refreshToken.value })
    setTokens(data.access_token, data.refresh_token)
  }

  function logout() {
    clearAuth()
  }

  function init() {
    if (accessToken.value) {
      api.defaults.headers.common['Authorization'] = `Bearer ${accessToken.value}`
      if (activeOrgId.value) {
        api.defaults.headers.common['X-Organization-Id'] = String(activeOrgId.value)
      }
      fetchUser()
    }
  }

  return {
    user, accessToken, refreshToken, activeOrgId,
    isAuthenticated, permissions, organizationName, isSuperAdmin,
    hasPermission, setActiveOrganizationId,
    login, logout, fetchUser, refresh, init, setTokens, clearAuth,
  }
})
