import { useCallback, useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { Countdown } from '../../common/countdown/Countdown'
import type { CountdownHandle } from '../../common/countdown/Countdown'
import { GuessMap } from '../../common/googleMapUtil/GuessMap'
import { CapitalApiError, getGame, startRound, submitGuess } from './api'
import type { CapitalState } from './api'
import '../singlePlayer/SinglePlayerPage.css'
import '../../common/gameLayout.css'
import './CapitalFinderPage.css'

export function CapitalFinderPage() {
  const token = sessionStorage.getItem('token')
  return token ? <CapitalGame token={token} /> : <Navigate to="/authpage" replace />
}

function CapitalGame({ token }: { token: string }) {
  const navigate = useNavigate()
  const [game, setGame] = useState<CapitalState | null>(null)
  const [guess, setGuess] = useState<google.maps.LatLngLiteral | null>(null)
  const [pending, setPending] = useState(true)
  const [error, setError] = useState('')
  const timer = useRef<CountdownHandle>(null)
  const roundId = useRef('')
  const busy = useRef(false)
  const version = useRef(0)
  const lifetime = useRef<AbortController | null>(null)

  const apply = useCallback((value: CapitalState) => {
    if (roundId.current !== value.round_id) setGuess(value.guess)
    roundId.current = value.round_id
    setGame(value)
    setError('')
    timer.current?.settimer(value.finished ? 0 : value.seconds_left)
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    lifetime.current = controller
    startRound(token, undefined, controller.signal).then(value => {
      if (!controller.signal.aborted) apply(value)
    }).catch(err => {
      if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to start game.')
    }).finally(() => {
      if (!controller.signal.aborted) setPending(false)
    })
    return () => controller.abort()
  }, [token, apply])

  const running = !!game && !game.finished
  useEffect(() => {
    if (!running) return
    const controller = new AbortController()
    let refresh: ReturnType<typeof setTimeout>
    async function poll() {
      const requestedVersion = version.current
      try {
        if (busy.current) return
        const value = await getGame(token, controller.signal)
        if (!controller.signal.aborted && !busy.current && requestedVersion === version.current) apply(value)
      } catch (err) {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : 'Unable to refresh game.')
      } finally {
        if (!controller.signal.aborted) refresh = setTimeout(() => void poll(), 1000)
      }
    }
    refresh = setTimeout(() => void poll(), 1000)
    return () => { controller.abort(); clearTimeout(refresh) }
  }, [running, token, apply])

  async function handleAction() {
    if (busy.current || pending || (game && !game.finished && !guess)) return
    const signal = lifetime.current?.signal
    busy.current = true
    version.current += 1
    setPending(true)
    setError('')
    try {
      const value = !game ? await startRound(token, undefined, signal)
        : game.finished ? await startRound(token, game.round_id, signal)
        : await submitGuess(token, game.round_id, guess!, signal)
      if (!signal?.aborted) apply(value)
    } catch (err) {
      if (signal?.aborted) return
      if (err instanceof CapitalApiError && err.status === 409) {
        try { const value = await getGame(token, signal); if (!signal?.aborted) apply(value) }
        catch { if (!signal?.aborted) setError('Unable to refresh the round. Please try again.') }
      } else setError(err instanceof Error ? err.message : 'Request failed. Please try again.')
    } finally {
      busy.current = false
      if (!signal?.aborted) setPending(false)
    }
  }

  const result = !game?.finished ? '' : game.distance_km === null ? "Time's up · 0 pts"
    : `${game.score?.toLocaleString()} pts · ${game.distance_km.toFixed(3)} km`

  return <main className="single-player-page capital-finder-page">
    <header className="game-hud capital-finder-page__header">
      <span className="game-hud__round">{game ? `Round ${game.number}` : 'Round —'}</span>
      <div className="capital-finder-page__prompt">
        <span>Find the capital of</span>
        <strong>{game?.country ?? 'Loading…'}</strong>
        <Countdown ref={timer} />
      </div>
      <span className="game-hud__score">Score: {(game?.total_score ?? 0).toLocaleString()} pts</span>
    </header>
    <div className="capital-finder-page__map">
      {game && <GuessMap key={game.round_id} blank fill initialGuess={game.guess}
        onGuessChange={setGuess} disabled={pending || game.finished} />}
    </div>
    <footer className="single-player-page__bottom game-footer">
      <div className="single-player-page__controls game-controls">
        <button type="button" onClick={() => void handleAction()}
          disabled={pending || (!!game && !game.finished && !guess)}>
          {pending ? 'Please wait…' : !game ? 'Retry' : game.finished ? 'Next round' : 'Submit guess'}
        </button>
        <label htmlFor="capital-result">Result</label>
        <input id="capital-result" readOnly value={result} placeholder="Submit a guess to see your score" />
        <button className="game-exit" type="button" onClick={() => navigate('/homepage', { replace: true })}>Exit game</button>
      </div>
      {error && <p className="single-player-page__error" role="alert">{error}</p>}
    </footer>
  </main>
}
