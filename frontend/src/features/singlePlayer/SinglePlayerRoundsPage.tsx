import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { getToken } from '../userAuth/api'
import { CountdownTimer } from './CountdownTimer'
import { GameCanvas } from './GameCanvas'
import { ApiError, getGame, nextRound, startGame, submitGuess } from './roundsApi'
import type { GameState, LatLng } from './roundsApi'
import './SinglePlayerPage.css'
import './SinglePlayerRoundsPage.css'

// If the player has a pin down when time is nearly up, send it just before the server's deadline
// (a guess sent after the deadline is refused). Then ask the server for the final state.
const AUTO_SUBMIT_LEAD_MS = 400
const SYNC_GRACE_MS = 150

function messageOf(err: unknown) {
  return err instanceof Error ? err.message : 'Request failed. Please try again.'
}

export function SinglePlayerRoundsPage() {
  const token = getToken()
  const [game, setGame] = useState<GameState | null>(null)
  const [deadline, setDeadline] = useState<number | null>(null)
  const [guess, setGuess] = useState<LatLng | null>(null)
  const [pending, setPending] = useState(true)
  const [error, setError] = useState('')
  const busy = useRef(false)
  const guessRef = useRef<LatLng | null>(null)

  useEffect(() => { guessRef.current = guess }, [guess])

  // Take whatever the server says: store it and restart the countdown from its seconds_left.
  const apply = useCallback((next: GameState) => {
    const round = next.current_round
    setGame(next)
    setDeadline(round.finished ? null : Date.now() + round.seconds_left * 1000)
    if (round.finished) {
      const mine = round.results ? Object.values(round.results)[0] : undefined
      setGuess(mine?.guessed && mine.lat !== null && mine.lng !== null ? { lat: mine.lat, lng: mine.lng } : null)
    }
  }, [])

  const sync = useCallback(async () => {
    if (!token) return
    try {
      apply(await getGame(token))
    } catch (err) {
      setError(messageOf(err))
    }
  }, [token, apply])

  const submit = useCallback(async (pin: LatLng) => {
    if (!token || busy.current) return
    busy.current = true
    setPending(true)
    setError('')
    try {
      apply(await submitGuess(token, pin))
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) await sync() // too late: the round just ended
      else setError(messageOf(err))
    } finally {
      busy.current = false
      setPending(false)
    }
  }, [token, apply, sync])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    startGame(token).then((value) => {
      if (!cancelled) apply(value)
    }).catch((err: unknown) => {
      if (!cancelled) setError(messageOf(err))
    }).finally(() => {
      if (!cancelled) setPending(false)
    })
    return () => { cancelled = true }
  }, [token, apply])

  // The round ends when the timer does: send any pin the player has placed, then fetch the result.
  useEffect(() => {
    if (!token || deadline === null) return
    const submitTimer = window.setTimeout(() => {
      const pin = guessRef.current
      if (pin) void submit(pin)
    }, Math.max(0, deadline - Date.now() - AUTO_SUBMIT_LEAD_MS))
    const syncTimer = window.setTimeout(() => {
      void sync()
    }, Math.max(0, deadline - Date.now() + SYNC_GRACE_MS))
    return () => {
      window.clearTimeout(submitTimer)
      window.clearTimeout(syncTimer)
    }
  }, [token, deadline, submit, sync])

  if (!token) return <Navigate to="/authpage" replace />

  async function handleAction() {
    if (!token || busy.current) return
    if (game && !game.current_round.finished) {
      if (guess) await submit(guess)
      return
    }
    busy.current = true
    setPending(true)
    setError('')
    try {
      setGuess(null)
      if (!game || game.over) apply(await startGame(token)) // first load failed, or "Play again"
      else apply(await nextRound(token, game.current_round.number))
    } catch (err) {
      setError(messageOf(err))
    } finally {
      busy.current = false
      setPending(false)
    }
  }

  const round = game?.current_round ?? null
  const mine = round?.results ? Object.values(round.results)[0] ?? null : null
  const buttonLabel = pending ? 'Please wait…'
    : !game ? 'Retry'
    : game.over ? 'Play again'
    : round?.finished ? 'Next round'
    : 'Submit guess'
  const resultText = !round?.finished ? ''
    : mine?.guessed ? `${(mine.score ?? 0).toLocaleString()} pts · ${(mine.distance_km ?? 0).toFixed(3)} km`
    : "Time's up · no guess · 0 pts"

  return (
    <main className="single-player-page">
      <header className="single-player-page__top rounds-hud">
        {game && round && <>
          <span className="rounds-hud__round">
            Round {round.number}{round.total_rounds ? ` of ${round.total_rounds}` : ''}
          </span>
          <CountdownTimer key={deadline ?? 'stopped'} deadline={deadline} />
          <span className="rounds-hud__score">{(game.total_score ?? 0).toLocaleString()} pts</span>
        </>}
      </header>
      {round ? <GameCanvas key={`${round.number}:${round.pano_id}`}
        panoId={round.pano_id} onGuessChange={setGuess}
        initialGuess={round.finished ? guess : null} disabled={pending || round.finished} />
        : <div className="single-player-page__loading" role="status">
          {pending ? 'Finding a street-view location…' : 'No round loaded.'}
        </div>}
      <footer className="single-player-page__bottom">
        <div className="single-player-page__controls">
          <button type="button" onClick={() => void handleAction()}
            disabled={pending || (!!round && !round.finished && !guess)}>
            {buttonLabel}
          </button>
          <label htmlFor="round-result">Result</label>
          <input id="round-result" readOnly value={resultText} placeholder="Submit a guess to see your score" />
        </div>
        {game?.over && <p className="rounds-summary" role="status">
          Game over · {(game.total_score ?? 0).toLocaleString()} pts
          {game.round_scores ? ` (${game.round_scores.map((s) => s.toLocaleString()).join(' + ')})` : ''}
        </p>}
        {error && <p className="single-player-page__error" role="alert">{error}</p>}
      </footer>
    </main>
  )
}
