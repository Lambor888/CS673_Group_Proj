import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useLobbySocket } from '../lobbyPage/useLobbySocket'
import { ConnectionBanner } from '../lobbyPage/ConnectionBanner'
import { GameCanvas } from './GameCanvas'
import { Countdown } from '../../common/countdown/Countdown'
import type { CountdownHandle } from '../../common/countdown/Countdown'
import { getMe, getToken } from '../userAuth/api'
import { getLobbyGame, submitLobbyGuess } from './api'
import type { LobbyGame } from './api'
import { leaveLobby } from '../lobbyPage/api'
import './GamePage.css'

function hasEnded(game: LobbyGame) {
    return game.over
}

export function GamePage(){
    const { id } = useParams<{id: string}>()
    return id ? <LobbyGamePage key={id} id={id} /> : <p role="alert">Missing lobby ID.</p>
}

function LobbyGamePage({ id }: { id: string }) {
    const navigate = useNavigate()
    const [guess, setGuess] = useState<google.maps.LatLngLiteral | null>(null)
    const [game, setGame] = useState<LobbyGame | null>(null)
    const [error, setError] = useState('')
    const [submitError, setSubmitError] = useState('')
    const [userId, setUserId] = useState<number | null>(null)
    const [pending, setPending] = useState(false)
    const [leaving, setLeaving] = useState(false)
    const [leaveError, setLeaveError] = useState('')
    const ended = useRef(false)
    const leavingRef = useRef(false)
    const busy = useRef(false)
    const version = useRef(0)
    const timer = useRef<CountdownHandle>(null)
    useEffect(() => {
        timer.current?.settimer(180)
    }, [id])
    useEffect(() => {
        const controller = new AbortController()
        let refresh: ReturnType<typeof setTimeout> | undefined
        let previousRound = ''
        let playerId: number | null = null
        async function load() {
            if (ended.current) return
            const requestVersion = version.current
            try {
                if (playerId === null) {
                    const user = await getMe(getToken())
                    if (controller.signal.aborted) return
                    playerId = user.id
                    setUserId(user.id)
                }
                const value = await getLobbyGame(getToken(), id, controller.signal)
                if (controller.signal.aborted) return
                if (busy.current || ended.current || leavingRef.current || requestVersion !== version.current) return
                const roundKey = `${value.current_round.number}:${value.current_round.pano_id}`
                if (roundKey !== previousRound) setGuess(null)
                previousRound = roundKey
                setGame(value)
                ended.current = hasEnded(value)
                setError('')
            } catch (err) {
                if (controller.signal.aborted) return
                setError(err instanceof Error ? err.message : 'Unable to load street view.')
            } finally {
                // Always resume polling, including when a stale response is ignored.
                if (!controller.signal.aborted && !ended.current) refresh = setTimeout(() => void load(), 3000)
            }
        }
        void load()
        return () => {
            controller.abort()
            clearTimeout(refresh)
        }
    }, [id])
    // Stay connected to the lobby while playing: the server keeps your seat only while you're
    // connected (or briefly after a drop), and this is where lobby_closed / removal reach you.
    const handleMessage = useCallback(() => {
        // Game messages will be handled here once multiplayer rounds land.
    }, [])
    const { status, stop } = useLobbySocket(id, handleMessage)

    const gameEnded = game !== null && hasEnded(game)
    const submitted = userId !== null && !!game?.current_round.submitted.includes(userId)
    const disabled = pending || leaving || gameEnded || !game || userId === null || submitted || game.current_round.finished
        || game.over || !game.active_players.includes(userId)
    const result = userId === null ? null : game?.current_round.results?.[userId]
    const resultText = result
        ? `${result.guessed ? `${result.distance_km?.toFixed(3)} km` : 'No guess'} · -${result.penalty ?? 0} HP · ${game?.points[userId!] ?? 0} HP left`
        : submitted ? 'Submitted. Waiting for other players…' : ''

    async function handleSubmit() {
        if (busy.current || disabled || !guess) return
        busy.current = true
        version.current += 1
        setPending(true)
        setSubmitError('')
        try {
            const value = await submitLobbyGuess(getToken(), id, guess)
            ended.current = hasEnded(value)
            setGame(value)
        } catch (err) {
            setSubmitError(err instanceof Error ? err.message : 'Unable to submit guess.')
        } finally {
            busy.current = false
            setPending(false)
        }
    }

    async function handleLeave() {
        if (leavingRef.current || busy.current) return
        leavingRef.current = true
        setLeaving(true)
        setLeaveError('')
        try {
            await leaveLobby(getToken(), id)
            stop()
            navigate('/homepage', { replace: true })
        } catch (err) {
            setLeaveError(err instanceof Error ? err.message : 'Unable to leave the game.')
            leavingRef.current = false
            setLeaving(false)
        }
    }

    return (
        <main className="multiplayer-page">
          <header className="multiplayer-page__top">
            <input className="multiplayer-page__round" aria-label="Round" readOnly
              value={game ? `Round ${game.current_round.number}` : 'Round —'} />
            {gameEnded ? <span role="status">Game over</span> : <Countdown ref={timer} />}
            <button className="multiplayer-page__exit" type="button" disabled={leaving || pending}
              onClick={() => void handleLeave()}>{leaving ? 'Leaving…' : 'Exit game'}</button>
            <ConnectionBanner status={status} />
          </header>
          {gameEnded ? <section className="multiplayer-page__loading" aria-label="Game results">
              <div><h2>Game over</h2>
                <p>The game has ended.</p>
                {userId !== null && <p>Remaining HP: {game.points[userId] ?? 0}</p>}
              </div>
            </section> : game ? <GameCanvas
            key={`${game.current_round.number}:${game.current_round.pano_id}`}
            panoId={game.current_round.pano_id} onGuessChange={setGuess} disabled={disabled} />
            : <div className="multiplayer-page__loading" role="status">
                {error ? 'Waiting for the lobby street view. Retrying…' : 'Loading lobby street view…'}
              </div>}
          <footer className="multiplayer-page__bottom">
            <div className="multiplayer-page__controls">
              <button type="button" disabled={disabled || !guess} onClick={() => void handleSubmit()}>
                {gameEnded ? 'Game over' : pending ? 'Submitting…' : submitted ? 'Submitted' : 'Submit guess'}
              </button>
              <label htmlFor="multiplayer-result">Result</label>
              <input id="multiplayer-result" readOnly value={resultText}
                placeholder="Submit a guess to see your result" />
            </div>
            {submitError && <p className="multiplayer-page__error" role="alert">{submitError}</p>}
            {error && <p className="multiplayer-page__error" role="alert">{error}</p>}
            {leaveError && <p className="multiplayer-page__error" role="alert">{leaveError}</p>}
          </footer>
        </main>
    )
}
