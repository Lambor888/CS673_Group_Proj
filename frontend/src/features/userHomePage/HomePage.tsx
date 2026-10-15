import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { createLobby } from './api'
import {getToken, getUsername} from '../userAuth/api'
import './HomePage.css'


export function HomePage(){

    const navigate = useNavigate()
    const [creating, setCreating] = useState(false)
    const [lobbyError, setLobbyError] = useState<string | null>(null)
    const token: string | null = getToken()
    const username = getUsername()
    if (!token) { 
        navigate('/login'); 
        return 
    }

    async function handleCreateLobby() {
    setLobbyError(null)
    setCreating(true)
    try {
        const lobby = await createLobby(token, `${username}'s lobby`)
        navigate(`/lobby/${lobby.id}`)
    } catch (e) {
        setLobbyError(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
        setCreating(false)
    }
    }

    return (
        <main>
        <button className="create-lobby-button" onClick={handleCreateLobby} disabled={creating}>
            {creating ? 'Creating…' : 'Create lobby'}
        </button>
        {lobbyError && <p className="create-lobby-error" role="alert">{lobbyError}</p>}
        </main>
    )


}