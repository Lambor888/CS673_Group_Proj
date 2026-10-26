import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { createLobby, joinLobby } from './api'
import {getToken, getUsername} from '../userAuth/api'
import './HomePage.css'

function Header(){
    return (
        <header><h1>Create a Lobby</h1></header>
    )
}

function LobbyCreation(){
    const navigate = useNavigate()
    const [creating, setCreating] = useState(false)
    const [lobbyError, setLobbyError] = useState<string | null>(null)
    const token: string = getToken()
    console.log(`token: ${token}`)
    const username = getUsername()

    async function handleCreateLobby() {
        setLobbyError(null)
        setCreating(true)
        try {
            const lobby = await createLobby(token, `${username}'s lobby`)
            for (const [key, value] of Object.entries(lobby)){
                console.log(`${key}: ${value}`)
            }
            
            navigate(`/lobby/${lobby.id}`)
        } catch (e) {
            setLobbyError(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
            setCreating(false)
        }
    }
    return (
        <>
            <button className="create-button" onClick={handleCreateLobby} disabled={creating}>
                {creating ? 'Creating…' : 'Create lobby'}
            </button>
            {lobbyError && <p className="create-error" role="alert">{lobbyError}</p>}
                
        </>
    )
}


function JoinLobby(){
    const navigate = useNavigate()
    const [code, setCode] = useState('')
    const [error, setError] = useState<string | null>(null)
    const [joining, setJoining] = useState(false)
    const token: string = getToken()
    if (!token) { 
        navigate('/login'); 
        return 
    }

    //since it is a form submission, need to prevent page reloading
    async function handleJoinLobby(event: React.SubmitEvent<HTMLFormElement>) {
        event.preventDefault()
        setError(null)
        setJoining(true)
        try {
            console.log(code)
            const lobby = await joinLobby(token, code.trim().toUpperCase())
            navigate(`/lobby/${lobby.id}`)
        
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
            setJoining(false)
        }
    }
    return (
        <form onSubmit={handleJoinLobby} className="join-form">
        <input
            type="text"
            value={code}
            onChange={e => setCode(e.target.value.toUpperCase())}
            placeholder="Enter lobby code"
            maxLength={6}
            autoComplete="off"
        />
        <button type="submit" disabled={code.length !== 6 || joining}>
            {joining ? 'Joining...' : 'Join'}
        </button>
        {error && <p className="error">{error}</p>}
        </form>
  )
}

export function HomePage() {
  const navigate = useNavigate()
  const token = getToken()
  const username = getUsername()
  if (!token) return <Navigate to="/authpage" replace />

  return (
    <main className="home-page">
      <header className="home-page__header">
        <nav className="home-page__menu" aria-label="Game modes">
          <button type="button" onClick={() => navigate('/singleplayer')}>singleplayer</button>          
        </nav>
        <button type="button" className="home-page__player" aria-label={`Player info: ${username ?? 'Player'}`}>
          <span>Player info</span>
          <strong>{username ?? 'Player'}</strong>
        </button>
      </header>
      
      <LobbyCreation />
      <JoinLobby />
    </main>
  )
}
