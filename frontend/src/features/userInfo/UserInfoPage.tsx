import { useEffect, useRef, useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import type { User } from '../userAuth/api'
import { AccountError, addFriend, getFriends, getRequests, getUser, logout, removeFriend, respondToRequest } from './api'
import type { FriendRequest } from './api'
import './UserInfoPage.css'

function clearSession() {
  sessionStorage.removeItem('token')
  sessionStorage.removeItem('username')
}

export function UserInfoPage() {
  const token = sessionStorage.getItem('token')
  return token ? <AccountPage token={token} /> : <Navigate to="/authpage" replace />
}

function AccountPage({ token }: { token: string }) {
  const navigate = useNavigate()
  const [user, setUser] = useState<User | null>(null)
  const [friends, setFriends] = useState<User[]>([])
  const [incoming, setIncoming] = useState<FriendRequest[]>([])
  const [outgoing, setOutgoing] = useState<FriendRequest[]>([])
  const [recipient, setRecipient] = useState('')
  const [revision, setRevision] = useState(0)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const locked = useRef(false)
  const socket = useRef<WebSocket | null>(null)

  useEffect(() => {
    let active = true
    Promise.all([getUser(token), getFriends(token), getRequests(token, 'incoming'), getRequests(token, 'outgoing')])
      .then(([profile, list, received, sent]) => {
        if (!active) return
        setUser(profile)
        setFriends(list)
        setIncoming(received)
        setOutgoing(sent)
        setError('')
      }).catch((reason: unknown) => {
        if (!active) return
        if (reason instanceof AccountError && reason.status === 401) {
          clearSession()
          navigate('/authpage', { replace: true })
        } else {
          setError(reason instanceof Error ? reason.message : 'Unable to load account.')
        }
      }).finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [token, revision, navigate])

  useEffect(() => {
    let active = true
    let retry: ReturnType<typeof setTimeout> | undefined
    const refresh = () => setRevision(value => value + 1)
    function connect() {
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${protocol}://${location.host}/api/auth/notifications/ws?token=${encodeURIComponent(token)}`)
      socket.current = ws
      ws.onmessage = () => { if (active) refresh() }
      ws.onclose = () => {
        if (active) retry = setTimeout(connect, 5000)
      }
    }
    connect()
    // HTTP refresh also covers missed events and temporary socket failures.
    const poll = setInterval(refresh, 30000)
    window.addEventListener('focus', refresh)
    return () => {
      active = false
      clearTimeout(retry)
      clearInterval(poll)
      window.removeEventListener('focus', refresh)
      socket.current?.close()
      socket.current = null
    }
  }, [token])

  async function run(action: () => Promise<unknown>, message: string) {
    if (locked.current) return
    locked.current = true
    setBusy(true)
    setError('')
    setNotice('')
    try {
      await action()
      setNotice(message)
      setRevision(value => value + 1)
    } catch (reason) {
      if (reason instanceof AccountError && reason.status === 401) {
        clearSession()
        navigate('/authpage', { replace: true })
      } else {
        setError(reason instanceof Error ? reason.message : 'Request failed.')
      }
    } finally {
      locked.current = false
      setBusy(false)
    }
  }

  function handleLogout() {
    void run(async () => {
      await logout(token)
      socket.current?.close()
      clearSession()
      navigate('/authpage', { replace: true })
    }, '')
  }

  const recipientId = Number(recipient)
  const validRecipient = /^\d+$/.test(recipient) && Number.isSafeInteger(recipientId)
    && recipientId > 0 && recipientId !== user?.id

  return (
    <main className="user-info">
      <Link className="user-info__back" to="/homepage">← Home</Link>
      <header className="user-info__header">
        <div>
          <h1>User info</h1>
          {user ? <><p className="user-info__username">{user.username}</p><p className="user-info__muted">User ID: {user.id}</p></>
            : <p className="user-info__muted">{loading ? 'Loading account…' : 'Account unavailable'}</p>}
        </div>
        <button type="button" disabled={busy} onClick={handleLogout}>Log out</button>
      </header>
      {error && <div className="user-info__error" role="alert">{error} <button type="button" disabled={busy} onClick={() => setRevision(value => value + 1)}>Refresh</button></div>}
      {notice && <p className="user-info__notice" role="status">{notice}</p>}
      <div className="user-info__columns">
        <section className="user-info__career" aria-labelledby="career-heading">
          <h2 id="career-heading">Game career</h2>
        </section>
        <section className="user-info__friends" aria-labelledby="friends-heading" aria-busy={loading}>
          <h2 id="friends-heading">Friends</h2>
          <form onSubmit={event => {
            event.preventDefault()
            if (!validRecipient) return
            void run(async () => { await addFriend(token, recipientId); setRecipient('') }, 'Friend request sent.')
          }}>
            <label htmlFor="friend-user-id">Add friend by user ID</label>
            <div className="user-info__add">
              <input id="friend-user-id" inputMode="numeric" pattern="[0-9]+" placeholder="User ID" value={recipient}
                disabled={busy || !user} onChange={event => setRecipient(event.target.value)} required />
              <button className="user-info__primary" disabled={busy || !user || !validRecipient}>Add friend</button>
            </div>
          </form>
          <h3>Friend list <span>({friends.length})</span></h3>
          {loading ? <p className="user-info__muted">Loading…</p> : friends.length === 0 ? <p className="user-info__muted">No friends yet.</p> :
            <ul>{friends.map(friend => <li key={friend.id}>
              <div><strong>{friend.username}</strong><small>User ID: {friend.id}</small></div>
              <button type="button" disabled={busy} onClick={() => void run(() => removeFriend(token, friend.id), 'Friend removed.')}>Remove</button>
            </li>)}</ul>}
          <h3>New friend requests <span>({incoming.length})</span></h3>
          {!loading && incoming.length === 0 && <p className="user-info__muted">No pending requests.</p>}
          <ul>{incoming.map(request => <li key={request.id}>
            <div><strong>User ID: {request.sender_id}</strong><small>Pending</small></div>
            <div className="user-info__actions">
              <button type="button" className="user-info__primary" disabled={busy} onClick={() => void run(() => respondToRequest(token, request.id, 'accept'), 'Friend request accepted.')}>Accept</button>
              <button type="button" disabled={busy} onClick={() => void run(() => respondToRequest(token, request.id, 'reject'), 'Friend request declined.')}>Decline</button>
            </div>
          </li>)}</ul>
          {outgoing.length > 0 && <><h3>Sent requests</h3><ul>{outgoing.map(request => <li key={request.id}>
            <span>User ID: {request.recipient_id}</span><small>Pending</small>
          </li>)}</ul></>}
        </section>
      </div>
    </main>
  )
}
