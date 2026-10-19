export interface GuessResult {
  distance_km: number
  guess: google.maps.LatLngLiteral
}

export interface Round {
  round_id: string
  location: { pano_id: string; lat: number; lng: number }
  result: GuessResult | null
}

async function request<T>(token: string, path: string, body: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/singleplayer/${path}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal: AbortSignal.timeout(60000),
    })
  } catch {
    throw new Error('Unable to reach the server. Please try again.')
  }
  if (!response.ok) {
    if (response.status === 401) throw new Error('Your session has expired. Please log in again.')
    const error = await response.json().catch(() => null)
    throw new Error(typeof error?.detail === 'string' ? error.detail : 'Request failed. Please try again.')
  }
  return response.json() as Promise<T>
}

export function startRound(token: string, previousRoundId?: string) {
  return request<Round>(token, 'round', previousRoundId ? { previous_round_id: previousRoundId } : {})
}

export function submitGuess(token: string, roundId: string, guess: google.maps.LatLngLiteral) {
  return request<GuessResult>(token, `round/${roundId}/guess`, guess)
}
