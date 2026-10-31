import { useEffect, useRef, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { getToken } from '../userAuth/api'
import { GameCanvas } from './GameCanvas'
import { startRound, submitGuess } from './api'
import type { Round } from './api'
import { Countdown } from '../../common/countdown/Countdown'
import type { CountdownHandle } from '../../common/countdown/Countdown'
import './SinglePlayerPage.css'

const MAX_ROUNDS = 5

export function SinglePlayerPage() {
  const navigate = useNavigate()
  const token = getToken()
  const [round, setRound] = useState<Round | null>(null)
  // Temporary display count until the single-player round API exposes a number.
  const [roundNumber, setRoundNumber] = useState(1)
  const [guess, setGuess] = useState<google.maps.LatLngLiteral | null>(null)
  const [pending, setPending] = useState(true)
  const [error, setError] = useState('')
  const busy = useRef(false)
  const timer = useRef<CountdownHandle>(null)
  const gameEnded = roundNumber >= MAX_ROUNDS && round?.result != null
  const roundId = round?.round_id

  useEffect(() => {
    if (roundId) timer.current?.settimer(180)
  }, [roundId])

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
    if (!token || busy.current || gameEnded) return
    busy.current = true
    setPending(true)
    setError('')
    try {
      if (!round || round.result) {
        const value = await startRound(token, round?.round_id)
        if (round && value.round_id !== round.round_id) setRoundNumber(number => number + 1)
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
      <header className="single-player-page__top">
        <input className="single-player-page__round" aria-label="Round" readOnly
          value={round ? `Round ${roundNumber} / ${MAX_ROUNDS}` : 'Round —'} />
        {!gameEnded && <Countdown ref={timer} />}
      </header>
      {round ? <GameCanvas key={round.round_id}
        panoId={round.pano_id} onGuessChange={setGuess}
        initialGuess={round.result?.guess} disabled={pending || round.result !== null} />
        : <div className="single-player-page__loading" role="status">
          {pending ? 'Finding a street-view location…' : 'No round loaded.'}
        </div>}
      <footer className="single-player-page__bottom">
        <div className="single-player-page__controls">
          <button type="button" onClick={() => void handleAction()}
            disabled={gameEnded || pending || (!!round && !round.result && !guess)}>
            {gameEnded ? 'Game over' : pending ? 'Please wait…' : !round ? 'Retry' : round.result ? 'Next round' : 'Submit guess'}
          </button>
          {gameEnded && <button type="button" onClick={() => navigate('/homepage', { replace: true })}>
            Exit game
          </button>}
          <label htmlFor="round-result">Result</label>
          <input id="round-result" readOnly value={round?.result
            ? `${round.result.score.toLocaleString()} pts · ${round.result.distance_km.toFixed(3)} km`
            : ''}
            placeholder="Submit a guess to see your score" />
        </div>
        {error && <p className="single-player-page__error" role="alert">{error}</p>}
      </footer>
    </main>
  )
}
