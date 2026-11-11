export interface CapitalState {
  round_id: string
  number: number
  country: string
  seconds_left: number
  finished: boolean
  total_score: number
  score: number | null
  distance_km: number | null
  guess: google.maps.LatLngLiteral | null
}

export class CapitalApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.status = status }
}

async function call(token: string, method: string, path: string, body?: unknown, signal?: AbortSignal): Promise<CapitalState> {
  const response = await fetch(`/api/capfinder${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => null)
    throw new CapitalApiError(typeof error?.detail === 'string' ? error.detail : 'Unable to load capital finder.', response.status)
  }
  return response.json()
}

export const startRound = (token: string, previous?: string, signal?: AbortSignal) =>
  call(token, 'POST', '/round', { previous_round_id: previous ?? null }, signal)
export const getGame = (token: string, signal?: AbortSignal) => call(token, 'GET', '', undefined, signal)
export const submitGuess = (token: string, id: string, guess: google.maps.LatLngLiteral, signal?: AbortSignal) =>
  call(token, 'POST', `/round/${id}/guess`, guess, signal)
