export interface User { id: number; username: string }
interface Credentials { username: string; password: string }
import { request } from '../requestHandler'


export function register(credentials: Credentials) {
  return request<User>('/api/auth/register', 'authpage', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
}
export async function login(credentials: Credentials) {
  const token = await request<{ access_token: string }>('/api/auth/login', 'authpage', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ ...credentials }),
  })
  const user = await request<User>('/api/auth/me', 'authpage', {
    headers: { Authorization: `Bearer ${token.access_token}` },
  })
  localStorage.setItem('username', user.username)
  localStorage.setItem('token', token.access_token)

  return { user, token: token.access_token }
}

export function getToken(): string{
  const token = localStorage.getItem('token')
  if (token == null){
    throw new Error("No auth token")
  }
  return token
}
export function getUsername(){
  return localStorage.getItem('username')
}

