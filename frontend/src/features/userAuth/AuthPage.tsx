import { useRef, useState } from 'react'
import type { FormEvent } from 'react'
import { login, register } from './api'
import type { User } from './api'
import './AuthPage.css'

export function AuthPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [session, setSession] = useState<{ user: User; token: string } | null>(null)
  const submitting = useRef(false)
  const isRegister = mode === 'register'

  function changeMode(next: 'login' | 'register') {
    setMode(next)
    setPassword('')
    setConfirmation('')
    setError('')
    setNotice('')
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (submitting.current) return
    setError('')
    setNotice('')
    if (isRegister && password !== confirmation) {
      setError('Passwords do not match.')
      return
    }
    submitting.current = true
    setPending(true)
    try {
      const credentials = { username: username.trim(), password }
      if (isRegister) {
        const user = await register(credentials)
        setUsername(user.username)
        setMode('login')
        setNotice('Registration successful. Please log in.')
      } else {
        setSession(await login(credentials))
      }
      setPassword('')
      setConfirmation('')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.')
    } finally {
      submitting.current = false
      setPending(false)
    }
  }

  return (
    <main className="auth-card" aria-labelledby="auth-title">
          {session ? <>
            <h2 id="auth-title">Welcome, {session.user.username}</h2>
            <dl className="user-details"><dt>Username</dt><dd>{session.user.username}</dd><dt>User ID</dt><dd>{session.user.id}</dd></dl>
            <button className="primary-button" onClick={() => { setSession(null); setNotice('You have been logged out.') }}>Log out</button>
          </> : <>
<h2 id="auth-title">{isRegister ? 'Sign up' : 'Log in'}</h2>
            {notice && <p className="form-notice" role="status">{notice}</p>}
            <form onSubmit={submit} aria-busy={pending}>
              <label htmlFor="username">Username</label>
              <input id="username" name="username" autoComplete="username" required minLength={isRegister ? 3 : undefined} maxLength={isRegister ? 20 : undefined} pattern={isRegister ? '[A-Za-z0-9_]+' : undefined} title={isRegister ? '3–20 letters, numbers, or underscores' : undefined} value={username} onChange={(e) => setUsername(e.target.value)} disabled={pending} placeholder="Enter your username" aria-describedby={isRegister ? 'username-help' : undefined} />
              {isRegister && <small id="username-help">3–20 letters, numbers, or underscores. Case-insensitive.</small>}
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} required minLength={isRegister ? 8 : undefined} maxLength={isRegister ? 128 : undefined} value={password} onChange={(e) => setPassword(e.target.value)} disabled={pending} placeholder={isRegister ? 'Create a password (8–128 characters)' : 'Enter your password'} />
              {isRegister && <><label htmlFor="confirmation">Confirm password</label><input id="confirmation" name="confirmation" type="password" autoComplete="new-password" required value={confirmation} onChange={(e) => setConfirmation(e.target.value)} disabled={pending} placeholder="Re-enter your password" /></>}
              {error && <p className="form-error" role="alert">{error}</p>}
              <button className="primary-button" type="submit" disabled={pending}>{pending ? 'Please wait...' : isRegister ? 'Create account' : 'Log in'}</button>
            </form>
            <p className="switch-hint">{isRegister ? 'Already have an account?' : 'Need an account?'}<button type="button" disabled={pending} onClick={() => changeMode(isRegister ? 'login' : 'register')}>{isRegister ? 'Log in' : 'Sign up'}</button></p>
          </>}
    </main>
  )
}



