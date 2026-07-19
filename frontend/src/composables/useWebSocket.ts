import { ref, onMounted, onUnmounted } from 'vue'

export function useWebSocket() {
  const messages = ref<any[]>([])
  const connected = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null

  function wsUrl(): string {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('access_token') || ''
    const orgId = localStorage.getItem('active_org_id')
    let url = `${proto}//${location.host}/ws?token=${encodeURIComponent(token)}`
    if (orgId) url += `&org_id=${encodeURIComponent(orgId)}`
    return url
  }

  function connect() {
    ws = new WebSocket(wsUrl())

    ws.onopen = () => { connected.value = true }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        messages.value.unshift(data)
        if (messages.value.length > 100) messages.value.pop()
      } catch {}
    }

    ws.onclose = () => {
      connected.value = false
      reconnectTimer = setTimeout(connect, 3000)
    }
  }

  onMounted(connect)

  onUnmounted(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  })

  return { messages, connected }
}
