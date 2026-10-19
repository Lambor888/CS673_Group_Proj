import { useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { getToken } from '../userAuth/api'
import { GameCanvas } from './GameCanvas'
import { startRound, submitGuess } from './api'
import type { Round } from './api'
import './SinglePlayerPage.css'

export function SinglePlayerPage() {
  const token = getToken()
  const [round, setRound] = useState<Round | null>(null)
  const [guess, setGuess] = useState<google.maps.LatLngLiteral | null>(null)
  const [pending, setPending] = useState(true)
  const [error, setError] = useState('')
  const busy = useRef(false)

  useEffect(() => {
    if (!token) return
    let cancelled = false
    startRound(token).then((value) => {
      if (!cancelled) {
        setRound(value)
        setGuess(value.result?.guess ?? null)
      }
    }).catch((err: unknown) => {
      if (!cancelled) setError(err instanceof Error ? err.message : 'Unable to start a round.')
    }).finally(() => {
      if (!cancelled) setPending(false)
    })
    return () => { cancelled = true }
  }, [token])

  if (!token) return <Navigate to="/authpage" replace />

  async function handleAction() {
    if (!token || busy.current) return
    busy.current = true
    setPending(true)
    setError('')
    try {
      if (!round || round.result) {
        const value = await startRound(token, round?.round_id)
        setRound(value)
        setGuess(value.result?.guess ?? null)
      } else if (guess) {
        const result = await submitGuess(token, round.round_id, guess)
        setRound({ ...round, result })
        setGuess(result.guess)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed. Please try again.')
    } finally {
      busy.current = false
      setPending(false)
    }
  }

  return (
    <main className="single-player-page">
      <header className="single-player-page__top" />
      {round ? <GameCanvas key={round.round_id} position={round.location}
        panoId={round.location.pano_id} onGuessChange={setGuess}
        initialGuess={round.result?.guess} disabled={pending || round.result !== null} />
        : <div className="single-player-page__loading" role="status">
          {pending ? 'Finding a street-view location…' : 'No round loaded.'}
        </div>}
      <footer className="single-player-page__bottom">
        <div className="single-player-page__controls">
          <button type="button" onClick={() => void handleAction()}
            disabled={pending || (!!round && !round.result && !guess)}>
            {pending ? 'Please wait…' : !round ? 'Retry' : round.result ? 'Next round' : 'Submit guess'}
          </button>
          <label htmlFor="round-distance">Distance</label>
          <input id="round-distance" readOnly value={round?.result ? `${round.result.distance_km.toFixed(3)} km` : ''}
            placeholder="Submit a guess to see distance" />
        </div>
        {error && <p className="single-player-page__error" role="alert">{error}</p>}
      </footer>
    </main>
  )
}
