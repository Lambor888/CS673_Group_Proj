import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Countdown } from '../../common/countdown/Countdown'
import type { CountdownHandle } from '../../common/countdown/Countdown'
import { GameCanvas } from './GameCanvas'
import { ApiError, getGame, nextRound, startGame, submitGuess } from './roundsApi'
import type { GameState, LatLng } from './roundsApi'
import './SinglePlayerPage.css'
import './SinglePlayerRoundsPage.css'
import '../../common/gameLayout.css'

// If the player has a pin down when time is nearly up, send it just before the server's deadline
// (a guess sent after the deadline is refused). Then ask the server for the final state.
const AUTO_SUBMIT_LEAD_MS = 400
const SYNC_GRACE_MS = 150

function messageOf(err: unknown) {
  return err instanceof Error ? err.message : 'Request failed. Please try again.'
}

export function SinglePlayerRoundsPage() {
  const navigate = useNavigate()
  const timer = useRef<CountdownHandle>(null)
  const token = sessionStorage.getItem('token')
  const [game, setGame] = useState<GameState | null>(null)
  const [deadline, setDeadline] = useState<number | null>(null)
  const [guess, setGuess] = useState<LatLng | null>(null)
  const [pending, setPending] = useState(true)
  const [error, setError] = useState('')
  const busy = useRef(false)
  const guessRef = useRef<LatLng | null>(null)
  const currentRound = useRef('')
  const version = useRef(0)

  useEffect(() => { guessRef.current = guess }, [guess])
  useEffect(() => {
    timer.current?.settimer(deadline === null ? 0 : Math.max(0, (deadline - Date.now()) / 1000))
  }, [deadline])

  // Take whatever the server says: store it and restart the countdown from its seconds_left.
  const apply = useCallback((next: GameState) => {
    const round = next.current_round
    if (currentRound.current !== round.round_id) setGuess(null)
    currentRound.current = round.round_id
    setGame(next)
    setDeadline(round.finished ? null : Date.now() + round.seconds_left * 1000)
    if (round.finished) {
      const mine = round.results ? Object.values(round.results)[0] : undefined
      setGuess(mine?.guessed && mine.lat !== null && mine.lng !== null ? { lat: mine.lat, lng: mine.lng } : null)
    }
  }, [])

  const sync = useCallback(async () => {
    if (!token || busy.current) return
    const requestedVersion = version.current
    try {
      const value = await getGame(token)
      if (!busy.current && version.current === requestedVersion) apply(value)
    } catch (err) {
      setError(messageOf(err))
    }
  }, [token, apply])

  const submit = useCallback(async (pin: LatLng) => {
    if (!token || busy.current) return
    busy.current = true
    version.current += 1
    setPending(true)
    setError('')
    try {
      apply(await submitGuess(token, pin, currentRound.current))
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        try { apply(await getGame(token)) }
        catch (refreshError) { setError(messageOf(refreshError)) }
      } else setError(messageOf(err))
    } finally {
      busy.current = false
      setPending(false)
    }
  }, [token, apply])

  useEffect(() => {
    if (!token) return
    let cancelled = false
    getGame(token).catch((err: unknown) => {
      if (err instanceof ApiError && err.status === 404) return startGame(token)
      throw err
    }).then((value) => {
      if (!cancelled) apply(value)
    }).catch((err: unknown) => {
      if (!cancelled) setError(messageOf(err))
    }).finally(() => {
      if (!cancelled) setPending(false)
    })
    return () => { cancelled = true }
  }, [token, apply])

  const running = !!game && !game.over
  useEffect(() => {
    if (!running) return
    const retry = window.setInterval(() => { if (!busy.current) void sync() }, 3000)
    return () => window.clearInterval(retry)
  }, [running, sync])

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
    version.current += 1
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
      <header className="single-player-page__top game-hud">
          <span className="game-hud__round">
            {round ? `Round ${round.number}${round.total_rounds ? ` / ${round.total_rounds}` : ''}` : 'Round —'}
          </span>
          <Countdown ref={timer} />
          <span className="game-hud__score">Score: {(game?.total_score ?? 0).toLocaleString()} pts</span>
      </header>
      {round ? <GameCanvas key={`${round.number}:${round.pano_id}`}
        panoId={round.pano_id} onGuessChange={setGuess}
        initialGuess={round.finished ? guess : null} disabled={pending || round.finished} />
        : <div className="single-player-page__loading" role="status">
          {pending ? 'Finding a street-view location…' : 'No round loaded.'}
        </div>}
      <footer className="single-player-page__bottom game-footer">
        <div className="single-player-page__controls game-controls">
          <button type="button" onClick={() => void handleAction()}
            disabled={pending || (!!round && !round.finished && !guess)}>
            {buttonLabel}
          </button>
          <label htmlFor="round-result">Result</label>
          <input id="round-result" readOnly value={resultText} placeholder="Submit a guess to see your score" />
          <button className="game-exit" type="button" disabled={pending}
            onClick={() => navigate('/homepage', { replace: true })}>Exit game</button>
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
