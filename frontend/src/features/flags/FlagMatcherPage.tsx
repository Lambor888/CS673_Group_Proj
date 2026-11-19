import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { request } from '../requestHandler'
import { getToken, isLoggedIn } from '../userAuth/api'
import '../singlePlayer/SinglePlayerPage.css'
import '../../common/gameLayout.css'
import './FlagMatcherPage.css'

type Question = { id: string; number: number; score: number; flag_url: string; options: string[] }
type Result = { correct: boolean; country: string; score: number; done: boolean }

const post = <T,>(path: string, body?: unknown) =>
  request<T>(`/api/flags${path}`, 'account', { method: 'POST', body: JSON.stringify(body ?? {}) }, getToken())

export function FlagMatcherPage() {
  if (!isLoggedIn()) return <Navigate to="/authpage" replace />
  return <FlagMatcher />
}

function FlagMatcher() {
  const navigate = useNavigate()
  const [question, setQuestion] = useState<Question | null>(null)
  const [result, setResult] = useState<Result | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    post<Question>('/question')
      .then(setQuestion)
      .catch((err: unknown) => setError(err instanceof Error ? err.message : 'Something went wrong.'))
  }, [])

  async function run<T>(call: () => Promise<T>, then: (value: T) => void) {
    setError('')
    try { then(await call()) } catch (err) { setError(err instanceof Error ? err.message : 'Something went wrong.') }
  }
  const next = () => run(() => post<Question>('/question'), (q) => { setQuestion(q); setResult(null) })
  const pick = (country: string) => {
    if (question) run(() => post<Result>('/answer', { id: question.id, country }), setResult)
  }
  const resultText = result ? result.correct ? 'Correct!' : `Wrong, it was ${result.country}.` : ''

  return (
    <main className="single-player-page flag-matcher-page" aria-label="Flag matcher">
      <header className="game-hud flag-matcher-page__header">
        <span className="game-hud__round">{question ? `Round ${question.number} / 10` : 'Round —'}</span>
        <span className="game-hud__score">Score: {result?.score ?? question?.score ?? 0} pts</span>
      </header>
      <div className="flag-matcher-page__flag">
        {question ? <img src={question.flag_url} alt="Flag to match" />
          : <p role="status">{error ? 'No flag loaded.' : 'Loading a flag…'}</p>}
      </div>
      <footer className="single-player-page__bottom game-footer flag-matcher-page__footer">
        {question && (
          <div className="single-player-page__controls game-controls flag-matcher-page__options" role="group" aria-label="Choose the country">
            {question.options.map((country) => (
              <button key={country} type="button" disabled={!!result} onClick={() => pick(country)}>{country}</button>
            ))}
          </div>
        )}
        <div className="single-player-page__controls game-controls">
          {(result || (!question && error)) && (
            <button type="button" onClick={next}>
              {!question ? 'Retry' : result?.done ? 'Play again' : 'Next round'}
            </button>
          )}
          <label htmlFor="flag-result">Result</label>
          <input id="flag-result" readOnly value={resultText} placeholder="Choose a country to see your result" />
          <button className="game-exit" type="button" onClick={() => navigate('/homepage')}>Exit game</button>
        </div>
        {result?.done && <p className="flag-matcher-page__summary" role="status">Game over · {result.score} / 10 pts</p>}
        {error && <p className="single-player-page__error" role="alert">{error}</p>}
      </footer>
    </main>
  )
}
