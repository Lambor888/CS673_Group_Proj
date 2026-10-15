export interface Player { id: number; username: string }
export interface Lobby {
  id: string
  name: string
  host_id: number
  max_players: number
  players: Player[]
}

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(token: string, path: string, options: RequestInit = {}): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/lobbies${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      signal: AbortSignal.timeout(15000),
    })
  } catch {
    throw new ApiError('Unable to connect to the server. Check that the backend is running and try again.', 0)
  }
  if (!response.ok) {
    if (response.status === 404) throw new ApiError('This lobby no longer exists.', 404)
    if (response.status === 409) throw new ApiError('This lobby is full.', 409)
    throw new ApiError('Request failed. Please try again.', response.status)
  }
  if (response.status === 204) return undefined as T
  try {
    return (await response.json()) as T
  } catch {
    throw new ApiError('The server returned an invalid response. Please try again.', response.status)
  }
}

export function createLobby(token: string | null, name: string) {
  if (token == null){
    throw new Error("token is null")
  }
  return request<Lobby>(token, '/createLobby', {
    method: 'POST',
    body: JSON.stringify({name}),
  })
}

export function getLobby(token: string, lobbyId: string) {
  return request<Lobby>(token, `/${lobbyId}`)
}

export function joinLobby(token: string, lobbyId: string) {
  return request<Lobby>(token, `/${lobbyId}/join`, { method: 'POST' })
}

export function leaveLobby(token: string, lobbyId: string) {
  return request<void>(token, `/${lobbyId}/leave`, { method: 'POST' })
}