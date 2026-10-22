export interface GuessResult {
  distance_km: number
  score: number
  guess: google.maps.LatLngLiteral
  // The true location. The server only sends it after the guess is scored.
  answer: google.maps.LatLngLiteral
}

export interface Round {
  round_id: string
  pano_id: string
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
