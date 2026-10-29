import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { openLobbySocket } from './api'
import { getToken } from '../userAuth/api'

// Close codes sent by the backend (backend/app/modules/connections/router.py and lobby/service.py).
export const CLOSE_NOT_A_MEMBER = 4401 // bad token, unknown lobby, or no longer in it
export const CLOSE_REPLACED = 4409 // the same player opened this lobby in another tab

export type LobbySocketStatus = 'connecting' | 'open' | 'reconnecting' | 'replaced' | 'closed'

export interface LobbySocketMessage {
    type: string
    [key: string]: unknown
}

const RETRY_BASE_MS = 500
const RETRY_MAX_MS = 5000

/**
 * One websocket to /ws/:lobbyId that survives drops.
 *
 * The server keeps a player's seat for a grace period after their socket closes, so a refresh,
 * moving from the lobby page to the game page, or a network blip doesn't kick them out. This hook
 * holds up the other end: it reconnects with backoff after an unexpected drop, and only gives up
 * when the server closes on purpose (left the lobby, lobby closed, not a member any more), in
 * which case it sends the player home with a note saying why.
 */
export function useLobbySocket(
    lobbyId: string | undefined,
    onMessage: (msg: LobbySocketMessage) => void,
) {
    const navigate = useNavigate()
    const [status, setStatus] = useState<LobbySocketStatus>('connecting')
    const wsRef = useRef<WebSocket | null>(null)
    // Set by stop(): we're leaving on purpose, so don't reconnect or react to the close.
    const stoppedRef = useRef(false)
    // Keep the latest handler without reconnecting every render.
    const onMessageRef = useRef(onMessage)
    useEffect(() => {
        onMessageRef.current = onMessage
    })

    useEffect(() => {
        if (!lobbyId) return
        let stopped = false
        let attempt = 0
        let retryTimer: ReturnType<typeof setTimeout> | undefined
        let current: WebSocket | null = null
        stoppedRef.current = false

        function goHome(notice: string) {
            stopped = true
            navigate('/HomePage', { replace: true, state: { notice } })
        }

        function connect() {
            if (stopped || stoppedRef.current) return
            const ws = openLobbySocket(getToken(), lobbyId!)
            current = ws
            wsRef.current = ws

            ws.onopen = () => {
                attempt = 0
                setStatus('open')
            }

            ws.onmessage = (event) => {
                const msg = JSON.parse(event.data) as LobbySocketMessage
                if (msg.type === 'lobby_closed') {
                    goHome('The host closed the lobby.')
                    return
                }
                onMessageRef.current(msg)
            }

            ws.onclose = (event) => {
                if (wsRef.current === ws) wsRef.current = null
                if (stopped || stoppedRef.current) return
                if (event.code === CLOSE_REPLACED) {
                    setStatus('replaced')
                } else if (event.code === CLOSE_NOT_A_MEMBER) {
                    setStatus('closed')
                    goHome("You're no longer in that lobby.")
                } else if (event.code === 1000) {
                    // The server ended it on purpose (you left, e.g. from another tab).
                    setStatus('closed')
                    goHome('You left the lobby.')
                } else {
                    // Network drop, server restart, laptop sleep... try again; our seat is held for a while.
                    setStatus('reconnecting')
                    const delay = Math.min(RETRY_BASE_MS * 2 ** attempt, RETRY_MAX_MS)
                    attempt += 1
                    retryTimer = setTimeout(connect, delay)
                }
            }
        }

        connect()
        return () => {
            stopped = true
            clearTimeout(retryTimer)
            current?.close()
            wsRef.current = null
        }
    }, [lobbyId, navigate])

    const send = useCallback((msg: LobbySocketMessage) => {
        const ws = wsRef.current
        if (!ws || ws.readyState !== WebSocket.OPEN) return false
        ws.send(JSON.stringify(msg))
        return true
    }, [])

    // Call before leaving on purpose (Leave button) so the close that follows isn't treated as a drop.
    const stop = useCallback(() => {
        stoppedRef.current = true
        wsRef.current?.close()
        wsRef.current = null
    }, [])

    return { status, send, stop }
}
