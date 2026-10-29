import { request } from '../requestHandler'

export interface User { id: number; username: string }

// Your own account, from /auth/me.
export interface Account {
  id: number
  username: string
  email: string | null
  has_password: boolean // false for accounts that only sign in with Google
  google_connected: boolean
  created_at: string
}

interface Registration { username: string; email: string; password: string }
// `username` may also be the account's email.
interface Credentials { username: string; password: string }

export function register(registration: Registration) {
  return request<Account>('/api/auth/register', 'authpage', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(registration),
  })
}

// Stores the session for the rest of the app (getToken / getUsername).
async function startSession(accessToken: string) {
  const user = await getMe(accessToken)
  sessionStorage.setItem('username', user.username)
  sessionStorage.setItem('token', accessToken)
  return user
}

export async function login(credentials: Credentials) {
  const token = await request<{ access_token: string }>('/api/auth/login', 'authpage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ ...credentials }),
  })
  const user = await startSession(token.access_token)
  return { user, token: token.access_token }
}

// `credential` is the ID token the "Sign in with Google" button gives us.
export async function loginWithGoogle(credential: string) {
  const token = await request<{ access_token: string; new_account: boolean }>('/api/auth/google', 'google', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ credential }),
  })
  const user = await startSession(token.access_token)
  return { user, newAccount: token.new_account }
}

export async function logout(token: string | null = sessionStorage.getItem('token')) {
  if (token) {
    const response = await fetch('/api/auth/logout', {
      method: 'POST', headers: { Authorization: `Bearer ${token}` },
      signal: AbortSignal.timeout(15000),
    })
    // An expired or previously revoked session can also be cleared locally.
    if (!response.ok && response.status !== 401) {
      throw new Error('Unable to log out. Please try again.')
    }
  }
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('username')
}

export function getMe(token: string = getToken()) {
  return request<Account>('/api/auth/me', 'account', { method: 'GET' }, token)
}

export async function changeUsername(username: string) {
  const account = await request<Account>('/api/auth/me', 'account', {
    method: 'PATCH', body: JSON.stringify({ username }),
  }, getToken())
  sessionStorage.setItem('username', account.username)
  return account
}

// Leave currentPassword out when setting a first password on a Google-only account.
export function changePassword(newPassword: string, currentPassword?: string) {
  return request<void>('/api/auth/password', 'account', {
    method: 'POST',
    body: JSON.stringify({ new_password: newPassword, current_password: currentPassword ?? null }),
  }, getToken())
}

export function connectGoogle(credential: string) {
  return request<Account>('/api/auth/google/link', 'account', {
    method: 'POST', body: JSON.stringify({ credential }),
  }, getToken())
}

export function isLoggedIn(): boolean {
  return sessionStorage.getItem('token') !== null
}

export function getToken(): string{
  const token = sessionStorage.getItem('token')
  if (token == null){
    throw new Error("No auth token")
  }
  return token
}
export function getUsername(){
  return sessionStorage.getItem('username')
}
