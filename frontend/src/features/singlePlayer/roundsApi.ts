// Client for the round-based endpoints in backend/app/modules/rounds (served at /games/...).
// The server owns the clock: every response says how many seconds are left in the round.

export type LatLng = google.maps.LatLngLiteral

export interface PlayerResult {
  guessed: boolean // false when the timer ran out before this player guessed
  lat: number | null
  lng: number | null
  distance_km: number | null
  score: number | null // single player: points earned this round
  penalty: number | null // lobby: points lost this round
}

export interface RoundState {
  number: number
  total_rounds: number | null
  multiplier: number
  seconds_left: number
  finished: boolean
  pano_id: string
  submitted: number[]
  answer: LatLng | null // the server only sends the true location once the round is over
  results: Record<string, PlayerResult> | null
}

export interface GameState {
  mode: 'single' | 'lobby'
  over: boolean
  winner: number | null
  active_players: number[]
  eliminated_players: number[]
  total_score: number | null
  round_scores: number[] | null
  points: Record<string, number> | null
  current_round: RoundState
}

export class ApiError extends Error {
  status: number

  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function call<T>(token: string, method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let response: Response
  try {
    response = await fetch(`/api/games/${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(60000),
    })
  } catch {
    throw new ApiError('Unable to reach the server. Please try again.', 0)
  }
  if (!response.ok) {
    if (response.status === 401) throw new ApiError('Your session has expired. Please log in again.', 401)
    const error = await response.json().catch(() => null)
    const detail = typeof error?.detail === 'string' ? error.detail : 'Request failed. Please try again.'
    throw new ApiError(detail, response.status)
  }
  return response.json() as Promise<T>
}

// Returns the game in progress, or starts a new 5-round game if there is none (or the last one is over).
export function startGame(token: string) {
  return call<GameState>(token, 'POST', 'single')
}

// Reading the state also lets the server close the round if its timer has run out.
export function getGame(token: string) {
  return call<GameState>(token, 'GET', 'single')
}

export function submitGuess(token: string, guess: LatLng) {
  return call<GameState>(token, 'POST', 'single/guess', guess)
}

export function nextRound(token: string, previousRound: number) {
  return call<GameState>(token, 'POST', 'single/next', { previous_round: previousRound })
}
