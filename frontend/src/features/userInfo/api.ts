import type { User } from '../userAuth/api'

export interface FriendRequest {
  id: string
  sender_id: number
  recipient_id: number
  status: 'pending' | 'accepted' | 'rejected' | 'removed'
  created_at: string
}

export class AccountError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.status = status
  }
}

async function request<T>(token: string, path: string, method = 'GET', body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/auth${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: AbortSignal.timeout(15000),
    })
  } catch {
    throw new Error('Unable to connect. Please try again.')
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new AccountError(typeof data?.detail === 'string' ? data.detail : 'Request failed. Please try again.', response.status)
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const getUser = (token: string) => request<User>(token, '/me')
export const getFriends = (token: string) => request<User[]>(token, '/friends')
export const getRequests = (token: string, direction: 'incoming' | 'outgoing') =>
  request<FriendRequest[]>(token, `/friend-requests/pending?direction=${direction}`)
export const addFriend = (token: string, recipientId: number) =>
  request<FriendRequest>(token, '/friend-requests', 'POST', { recipient_id: recipientId })
export const respondToRequest = (token: string, id: string, action: 'accept' | 'reject') =>
  request<FriendRequest>(token, `/friend-requests/${id}/${action}`, 'POST')
export const removeFriend = (token: string, id: number) => request<void>(token, `/friends/${id}`, 'DELETE')
export { logout } from '../userAuth/api'
