import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AccountError, getRequests } from './api'

/** The badge represents unresolved incoming requests, not merely unseen messages. */
export function usePendingFriendRequests(token: string | null) {
  const navigate = useNavigate()
  const [snapshot, setSnapshot] = useState({ token: '', count: 0 })

  useEffect(() => {
    if (!token) return
    let active = true
    let sequence = 0
    let socket: WebSocket | undefined
    let retry: ReturnType<typeof setTimeout> | undefined

    async function refresh() {
      const requestSequence = ++sequence
      try {
        const requests = await getRequests(token!, 'incoming')
        if (active && requestSequence === sequence) {
          setSnapshot({ token: token!, count: requests.length })
        }
      } catch (error) {
        if (active && error instanceof AccountError && error.status === 401) {
          sessionStorage.removeItem('token')
          sessionStorage.removeItem('username')
          navigate('/authpage', { replace: true })
        }
        // Keep the last known count on network failure; subsequent refreshes retry.
      }
    }

    function connect() {
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
      socket = new WebSocket(`${protocol}://${location.host}/api/auth/notifications/ws?token=${encodeURIComponent(token!)}`)
      socket.onmessage = () => { if (active) void refresh() }
      socket.onclose = () => {
        if (active) retry = setTimeout(connect, 5000)
      }
    }

    void refresh()
    connect()
    const poll = setInterval(refresh, 30000)
    window.addEventListener('focus', refresh)
    return () => {
      active = false
      clearTimeout(retry)
      clearInterval(poll)
      window.removeEventListener('focus', refresh)
      socket?.close()
    }
  }, [token, navigate])

  return snapshot.token === token ? snapshot.count : 0
}
