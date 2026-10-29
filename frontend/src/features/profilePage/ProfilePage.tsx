import { useEffect, useState } from 'react'
import type { SubmitEvent } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import type { Account } from '../userAuth/api'
import { changePassword, changeUsername, connectGoogle, getMe, isLoggedIn, logout } from '../userAuth/api'
import { GoogleSignInButton } from '../userAuth/GoogleSignInButton'
import { googleSignInEnabled } from '../userAuth/google'
import { getStats } from './api'
import type { Stats } from './api'
import './ProfilePage.css'

const errorText = (err: unknown, fallback: string) => (err instanceof Error ? err.message : fallback)

export function ProfilePage() {
  if (!isLoggedIn()) return <Navigate to="/authpage" replace />
  return <Profile />
}

function Profile() {
  const navigate = useNavigate()
  const [account, setAccount] = useState<Account | null>(null)
  const [stats, setStats] = useState<Stats | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    Promise.all([getMe(), getStats()])
      .then(([me, myStats]) => {
        if (cancelled) return
        setAccount(me)
        setStats(myStats)
      })
      .catch((err) => {
        if (!cancelled) setLoadError(errorText(err, 'Unable to load your profile.'))
      })
    return () => {
      cancelled = true
    }
  }, [])

  function handleLogout() {
    logout()
    navigate('/authpage', { replace: true })
  }

  return (
    <main className="profile-page">
      <header className="profile-page__header">
        <button type="button" onClick={() => navigate('/homepage')}>← Home</button>
        <h1>Profile</h1>
        <button type="button" onClick={handleLogout}>Log out</button>
      </header>

      {loadError && (
        <section className="profile-card">
          <p className="form-error" role="alert">{loadError}</p>
          <button type="button" onClick={handleLogout}>Log in again</button>
        </section>
      )}
      {!account && !loadError && <p>Loading…</p>}
      {account && (
        <>
          <AccountDetails account={account} onChange={setAccount} />
          {stats && <StatsPanel stats={stats} onPlay={() => navigate('/singleplayer')} />}
          <PasswordForm account={account} onChange={setAccount} />
          <GoogleConnection account={account} onChange={setAccount} />
        </>
      )}
    </main>
  )
}

function AccountDetails({ account, onChange }: { account: Account; onChange: (a: Account) => void }) {
  const [editing, setEditing] = useState(false)
  const [username, setUsername] = useState(account.username)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)
    try {
      onChange(await changeUsername(username.trim()))
      setEditing(false)
    } catch (err) {
      setError(errorText(err, 'Unable to change your username.'))
    } finally {
      setPending(false)
    }
  }

  const methods = [account.has_password && 'Password', account.google_connected && 'Google'].filter(Boolean)
  return (
    <section className="profile-card" aria-labelledby="account-title">
      <h2 id="account-title">Account</h2>
      <dl className="profile-details">
        <dt>Username</dt>
        <dd>
          {editing ? (
            <form className="inline-form" onSubmit={save}>
              <input aria-label="New username" value={username} onChange={(e) => setUsername(e.target.value)}
                required minLength={3} maxLength={20} pattern="[A-Za-z0-9_]+"
                title="3–20 letters, numbers, or underscores" disabled={pending} autoFocus />
              <button type="submit" disabled={pending}>Save</button>
              <button type="button" disabled={pending}
                onClick={() => { setEditing(false); setUsername(account.username); setError(null) }}>Cancel</button>
            </form>
          ) : (
            <>
              <strong>{account.username}</strong>{' '}
              <button type="button" className="link-button" onClick={() => setEditing(true)}>Change</button>
            </>
          )}
          {error && <p className="form-error" role="alert">{error}</p>}
        </dd>
        <dt>Email</dt>
        <dd>{account.email ?? <span className="muted">Not set</span>}</dd>
        <dt>Signs in with</dt>
        <dd>{methods.join(' and ')}</dd>
        <dt>Member since</dt>
        <dd>{new Date(account.created_at).toLocaleDateString()}</dd>
      </dl>
    </section>
  )
}

function StatsPanel({ stats, onPlay }: { stats: Stats; onPlay: () => void }) {
  const km = (value: number | null) => (value === null ? '—' : `${value.toLocaleString(undefined, { maximumFractionDigits: 1 })} km`)
  const points = (value: number | null) => (value === null ? '—' : Math.round(value).toLocaleString())
  return (
    <section className="profile-card" aria-labelledby="stats-title">
      <h2 id="stats-title">Single player stats</h2>
      {stats.rounds_played === 0 ? (
        <p className="muted">
          No rounds played yet.{' '}
          <button type="button" className="link-button" onClick={onPlay}>Play single player</button>{' '}
          to start building your stats.
        </p>
      ) : (
        <dl className="stats-grid">
          <div><dt>Rounds played</dt><dd>{stats.rounds_played.toLocaleString()}</dd></div>
          <div><dt>Total score</dt><dd>{points(stats.total_score)}</dd></div>
          <div><dt>Best round</dt><dd>{points(stats.best_score)}</dd></div>
          <div><dt>Average round</dt><dd>{points(stats.average_score)}</dd></div>
          <div><dt>Closest guess</dt><dd>{km(stats.best_distance_km)}</dd></div>
          <div><dt>Average distance</dt><dd>{km(stats.average_distance_km)}</dd></div>
        </dl>
      )}
    </section>
  )
}

function PasswordForm({ account, onChange }: { account: Account; onChange: (a: Account) => void }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)
  const hasPassword = account.has_password

  async function submit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setNotice(null)
    if (next !== confirmation) {
      setError('New passwords do not match.')
      return
    }
    setPending(true)
    try {
      await changePassword(next, hasPassword ? current : undefined)
      setCurrent('')
      setNext('')
      setConfirmation('')
      setNotice(hasPassword ? 'Password changed.' : 'Password set. You can now also log in with your username or email.')
      if (!hasPassword) onChange({ ...account, has_password: true })
    } catch (err) {
      setError(errorText(err, 'Unable to change your password.'))
    } finally {
      setPending(false)
    }
  }

  return (
    <section className="profile-card" aria-labelledby="password-title">
      <h2 id="password-title">{hasPassword ? 'Change password' : 'Set a password'}</h2>
      {!hasPassword && <p className="muted">You sign in with Google. Add a password to also log in with your username or email.</p>}
      <form className="stacked-form" onSubmit={submit}>
        {hasPassword && <>
          <label htmlFor="current-password">Current password</label>
          <input id="current-password" type="password" autoComplete="current-password" required
            value={current} onChange={(e) => setCurrent(e.target.value)} disabled={pending} />
        </>}
        <label htmlFor="new-password">New password</label>
        <input id="new-password" type="password" autoComplete="new-password" required minLength={8} maxLength={128}
          value={next} onChange={(e) => setNext(e.target.value)} disabled={pending} placeholder="8–128 characters" />
        <label htmlFor="confirm-password">Confirm new password</label>
        <input id="confirm-password" type="password" autoComplete="new-password" required
          value={confirmation} onChange={(e) => setConfirmation(e.target.value)} disabled={pending} />
        {error && <p className="form-error" role="alert">{error}</p>}
        {notice && <p className="form-notice" role="status">{notice}</p>}
        <button type="submit" disabled={pending}>{pending ? 'Saving…' : hasPassword ? 'Change password' : 'Set password'}</button>
      </form>
    </section>
  )
}

function GoogleConnection({ account, onChange }: { account: Account; onChange: (a: Account) => void }) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [notice, setNotice] = useState<string | null>(null)

  async function connect(credential: string) {
    setPending(true)
    setError(null)
    try {
      onChange(await connectGoogle(credential))
      setNotice('Google connected. You can now sign in with Google too.')
    } catch (err) {
      setError(errorText(err, 'Unable to connect Google.'))
    } finally {
      setPending(false)
    }
  }

  if (!account.google_connected && !googleSignInEnabled) return null
  return (
    <section className="profile-card" aria-labelledby="google-title">
      <h2 id="google-title">Google</h2>
      {account.google_connected ? (
        <p>{notice ?? 'Your Google account is connected. You can sign in with Google.'}</p>
      ) : (
        <>
          <p className="muted">Connect your Google account to sign in with Google.</p>
          <GoogleSignInButton onCredential={connect} text="continue_with" disabled={pending} />
        </>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  )
}
