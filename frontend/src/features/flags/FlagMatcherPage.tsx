import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { request } from '../requestHandler'
import { getToken, isLoggedIn } from '../userAuth/api'

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

  async function run<T>(call: () => Promise<T>, then: (value: T) => void) {
    setError('')
    try { then(await call()) } catch (err) { setError(err instanceof Error ? err.message : 'Something went wrong.') }
  }
  const next = () => run(() => post<Question>('/question'), (q) => { setQuestion(q); setResult(null) })
  const pick = (country: string) => {
    if (question) run(() => post<Result>('/answer', { id: question.id, country }), setResult)
  }

  return (
    <main>
      <button type="button" onClick={() => navigate('/homepage')}>Back</button>
      <h1>Flag matcher</h1>
      {error && <p role="alert">{error}</p>}
      {!question && <button type="button" onClick={next}>Start</button>}
      {question && (
        <>
          <p>Flag {question.number} of 10 · Score {result?.score ?? question.score}</p>
          <img src={question.flag_url} alt="Flag to match" width={320} />
          <div>
            {question.options.map((country) => (
              <button key={country} type="button" disabled={!!result} onClick={() => pick(country)}>{country}</button>
            ))}
          </div>
          {result && <p>{result.correct ? 'Correct!' : `Wrong, it was ${result.country}.`}</p>}
          {result && <button type="button" onClick={next}>{result.done ? `Done: ${result.score}/10. Play again` : 'Next flag'}</button>}
        </>
      )}
    </main>
  )
}
