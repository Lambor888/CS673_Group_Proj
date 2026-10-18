
import { request } from '../requestHandler'

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