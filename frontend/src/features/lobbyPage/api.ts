
import { request } from '../requestHandler'
import { startLobbyGame } from '../multiPlayerPage/api'

export interface PlayerOut {
    id: number
    name: string
}

export interface Lobby {
    id: string
    name: string
    player_ids: Record<number, PlayerOut>
    host_id: number
    num_players: number
    max_players: number
    flag: boolean
    code: string
}

export function leaveLobby(token: string, lobbyId: string) {
  return request<void>(`/api/lobbies/${lobbyId}/leave`, 'lobbypage', { method: 'POST' }, token)
}

export function getCurrentLobby(token: string, lobbyId: string){
    return request<Lobby>(`/api/lobbies/${lobbyId}`, 'lobbypage', {
        method:'GET'
        }, token)
}

export function openLobbySocket(token: string, lobbyId: string): WebSocket {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  return new WebSocket(
    `${protocol}://${location.host}/api/ws/${lobbyId}?token=${encodeURIComponent(token)}`
  )
}

export async function startGame(token: string, lobbyId: string){
    // Create the shared panorama before notifying everyone to open the game page.
    await startLobbyGame(token, lobbyId)
    return request<void>(`/api/lobbies/${lobbyId}/start`, 'lobbypage', { method: 'POST' }, token)
}
