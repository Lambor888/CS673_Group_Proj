export interface User { id: number; username: string }
interface Credentials { username: string; password: string }

// Temporary adapter for existing FastAPI endpoints; replace with the generated
// OpenAPI client when the shared client-generation workflow is introduced.
async function request<T>(path: string, options: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/auth/${path}`, {
      ...options, signal: AbortSignal.timeout(15000),
    })
  } catch {
    throw new Error('Unable to connect to the server. Check that the backend is running and try again.')
  }
  if (!response.ok) {
    if (response.status === 409) throw new Error('This username is already taken. Please choose another.')
    if (response.status === 401) throw new Error('Invalid username or password. Please try again.')
    if (response.status === 422) throw new Error('Invalid input. Please check your username and password.')
    throw new Error('Request failed. Check that the backend is running and try again.')
  }
  try { return await response.json() as T }
  catch { throw new Error('The server returned an invalid response. Please try again.') }
}
export function register(credentials: Credentials) {
  return request<User>('register', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(credentials),
  })
}
export async function login(credentials: Credentials) {
  const token = await request<{ access_token: string }>('login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ ...credentials }),
  })
  const user = await request<User>('me', {
    headers: { Authorization: `Bearer ${token.access_token}` },
  })
  return { user, token: token.access_token }
}


