import { useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import { login, loginWithGoogle, register } from './api'
import { useNavigate } from 'react-router-dom';
import { GoogleSignInButton } from './GoogleSignInButton'
import { googleSignInEnabled } from './google'
import './AuthPage.css'

export function AuthPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const submitting = useRef(false)
  const isRegister = mode === 'register'
  const navigate = useNavigate()

  function changeMode(next: 'login' | 'register') {
    setMode(next)
    setPassword('')
    setConfirmation('')
    setError('')
    setNotice('')
  }

  async function submit(event: SubmitEvent<HTMLFormElement>) {
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
        const user = await register({ ...credentials, email: email.trim() })
        setUsername(user.username)
        setMode('login')
        setNotice('Registration successful. Please log in.')
      } else {
        await login(credentials)
        navigate('/homepage', { replace: true })
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

  async function signInWithGoogle(credential: string) {
    if (submitting.current) return
    submitting.current = true
    setPending(true)
    setError('')
    setNotice('')
    try {
      const { user, newAccount } = await loginWithGoogle(credential)
      const welcome = newAccount
        ? `Welcome! You're signed in as ${user.username}. You can change your username on your profile.`
        : undefined
      navigate('/homepage', { replace: true, state: welcome ? { notice: welcome } : undefined })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Google sign-in failed. Please try again.')
    } finally {
      submitting.current = false
      setPending(false)
    }
  }

  return (
    <main className="auth-card" aria-labelledby="auth-title">
<h2 id="auth-title">{isRegister ? 'Sign up' : 'Log in'}</h2>
            {notice && <p className="form-notice" role="status">{notice}</p>}
            <form onSubmit={submit} aria-busy={pending}>
              <label htmlFor="username">{isRegister ? 'Username' : 'Username or email'}</label>
              <input id="username" name="username" autoComplete="username" required minLength={isRegister ? 3 : undefined} maxLength={isRegister ? 20 : undefined} pattern={isRegister ? '[A-Za-z0-9_]+' : undefined} title={isRegister ? '3–20 letters, numbers, or underscores' : undefined} value={username} onChange={(e) => setUsername(e.target.value)} disabled={pending} placeholder={isRegister ? 'Choose a username' : 'Enter your username or email'} aria-describedby={isRegister ? 'username-help' : undefined} />
              {isRegister && <small id="username-help">3–20 letters, numbers, or underscores. Case-insensitive.</small>}
              {isRegister && <><label htmlFor="email">Email</label><input id="email" name="email" type="email" autoComplete="email" required maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} disabled={pending} placeholder="you@example.com" /></>}
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete={isRegister ? 'new-password' : 'current-password'} required minLength={isRegister ? 8 : undefined} maxLength={isRegister ? 128 : undefined} value={password} onChange={(e) => setPassword(e.target.value)} disabled={pending} placeholder={isRegister ? 'Create a password (8–128 characters)' : 'Enter your password'} />
              {isRegister && <><label htmlFor="confirmation">Confirm password</label><input id="confirmation" name="confirmation" type="password" autoComplete="new-password" required value={confirmation} onChange={(e) => setConfirmation(e.target.value)} disabled={pending} placeholder="Re-enter your password" /></>}
              {error && <p className="form-error" role="alert">{error}</p>}
              <button className="primary-button" type="submit" disabled={pending}>{pending ? 'Please wait...' : isRegister ? 'Create account' : 'Log in'}</button>
            </form>
            {googleSignInEnabled && <>
              <p className="auth-divider"><span>or</span></p>
              <GoogleSignInButton onCredential={signInWithGoogle} text={isRegister ? 'signup_with' : 'signin_with'} disabled={pending} />
            </>}
            <p className="switch-hint">{isRegister ? 'Already have an account?' : 'Need an account?'}<button type="button" disabled={pending} onClick={() => changeMode(isRegister ? 'login' : 'register')}>{isRegister ? 'Log in' : 'Sign up'}</button></p>
    </main>
  )
}



