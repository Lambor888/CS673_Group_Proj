import { useEffect, useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { isLoggedIn } from '../userAuth/api'
import { getLeaderboard } from '../profilePage/api'
import type { LeaderboardEntry, LeaderboardScope } from '../profilePage/api'

type Result = { scope: LeaderboardScope; rows?: LeaderboardEntry[]; error?: string }

export function LeaderboardPage() {
  if (!isLoggedIn()) return <Navigate to="/authpage" replace />
  return <Leaderboard />
}

function Leaderboard() {
  const navigate = useNavigate()
  const [scope, setScope] = useState<LeaderboardScope>('global')
  const [result, setResult] = useState<Result | null>(null)

  useEffect(() => {
    let live = true
    getLeaderboard(scope)
      .then((rows) => { if (live) setResult({ scope, rows }) })
      .catch((err) => { if (live) setResult({ scope, error: err instanceof Error ? err.message : 'Unable to load the leaderboard.' }) })
    return () => { live = false }
  }, [scope])

  const current = result?.scope === scope ? result : null
  return (
    <main>
      <button type="button" onClick={() => navigate('/homepage')}>Back</button>
      <h1>Leaderboard: single player</h1>
      <div role="group" aria-label="Leaderboard scope">
        <button type="button" disabled={scope === 'global'} onClick={() => setScope('global')}>Global</button>
        <button type="button" disabled={scope === 'friends'} onClick={() => setScope('friends')}>Friends</button>
      </div>
      {!current && <p>Loading…</p>}
      {current?.error && <p role="alert">{current.error}</p>}
      {current?.rows?.length === 0 && <p>No finished games yet.</p>}
      {!!current?.rows?.length && (
        <table>
          <thead><tr><th>#</th><th>Player</th><th>Best score</th><th>Games</th></tr></thead>
          <tbody>
            {current.rows.map((row) => (
              <tr key={row.username}><td>{row.rank}</td><td>{row.username}</td><td>{row.best_score}</td><td>{row.games}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </main>
  )
}
