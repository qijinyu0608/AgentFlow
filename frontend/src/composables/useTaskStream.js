import { ref } from 'vue'
import { getWsBase } from './useApiBase'

export function useTaskStream() {
  const ws = ref(null)
  const wsStatus = ref('disconnected') // disconnected | connecting | connected

  const connectProcessSocket = () => {
    if (ws.value && (ws.value.readyState === WebSocket.OPEN || ws.value.readyState === WebSocket.CONNECTING)) {
      return ws.value
    }
    wsStatus.value = 'connecting'
    const url = `${getWsBase()}/api/v1/task/process`
    ws.value = new WebSocket(url)
    ws.value.onopen = () => (wsStatus.value = 'connected')
    ws.value.onclose = () => (wsStatus.value = 'disconnected')
    ws.value.onerror = () => (wsStatus.value = 'disconnected')
    return ws.value
  }

  const connectTaskStreamSocket = (taskId, onMessage) => {
    wsStatus.value = 'connecting'
    const url = `${getWsBase()}/api/v1/tasks/${encodeURIComponent(taskId)}/stream`
    const w = new WebSocket(url)
    w.onopen = () => (wsStatus.value = 'connected')
    w.onclose = () => (wsStatus.value = 'disconnected')
    w.onerror = () => (wsStatus.value = 'disconnected')
    w.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data)
        onMessage?.(msg)
      } catch {
        // ignore
      }
    }
    return w
  }

  const close = () => {
    try {
      ws.value?.close()
    } catch {
      // ignore
    }
    ws.value = null
    wsStatus.value = 'disconnected'
  }

  return { ws, wsStatus, connectProcessSocket, connectTaskStreamSocket, close }
}

