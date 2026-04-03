export function getApiBase() {
  const envBase = (import.meta.env.VITE_API_BASE || '').trim()
  if (envBase) {
    return envBase
  }

  if (typeof window !== 'undefined' && window.location?.origin) {
    const { port, origin } = window.location
    if (port && port !== '3000') {
      return origin
    }
  }

  return 'http://localhost:8001'
}

export function getWsBase() {
  return getApiBase().replace(/^http/, 'ws')
}
