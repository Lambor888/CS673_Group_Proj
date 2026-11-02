export interface LobbyGame {
  final_results: { player_id: number; username: string; rank: number; final_score: number }[] | null
  over: boolean
  active_players: number[]
  points: Record<string, number>
  current_round: {
    round_id: string
    number: number
    pano_id: string
    finished: boolean
    seconds_left: number
    submitted: number[]
    results: Record<string, { guessed: boolean; distance_km: number | null; penalty: number | null }> | null
  }
}

async function gameRequest(token: string, lobbyId: string, action: '' | '/start' | '/guess' | '/next', signal?: AbortSignal, body?: (google.maps.LatLngLiteral & { round_id: string }) | { previous_round: number }): Promise<LobbyGame> {
  const response = await fetch(`/api/games/lobby/${encodeURIComponent(lobbyId)}${action}`, {
    method: action ? 'POST' : 'GET',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60000)]) : AbortSignal.timeout(60000),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new Error(typeof error?.detail === 'string' ? error.detail : 'Unable to load the lobby game.')
  }
  return response.json() as Promise<LobbyGame>
}

export const startLobbyGame = (token: string, lobbyId: string) => gameRequest(token, lobbyId, '/start')
export const getLobbyGame = (token: string, lobbyId: string, signal?: AbortSignal) => gameRequest(token, lobbyId, '', signal)
export const submitLobbyGuess = (token: string, lobbyId: string, guess: google.maps.LatLngLiteral, roundId: string) => gameRequest(token, lobbyId, '/guess', undefined, { ...guess, round_id: roundId })
export const nextLobbyRound = (token: string, lobbyId: string, previousRound: number) => gameRequest(token, lobbyId, '/next', undefined, { previous_round: previousRound })
