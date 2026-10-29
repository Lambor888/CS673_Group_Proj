import { request } from '../requestHandler'
export interface Player { id: number; username: string }

export interface PlayerOut {
    id: number
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

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

export function createLobby(token: string, name: string) {
  return request<Lobby>(`/api/lobbies/createLobby`, 'homepage',{
    method: 'POST',
    body: JSON.stringify({name}),
  },
  token)
}

export function getLobby(token: string, lobbyId: string) {
  return request<Lobby>(`/api/lobbies/${lobbyId}`, 'homepage', {}, token)
}

export function joinLobby(token: string, lobbyCode: string) {
  return request<Lobby>(`/api/lobbies/${lobbyCode}/join`, 'homepage', { method: 'POST' }, token)
}
