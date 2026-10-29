import { useParams } from 'react-router-dom'
import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import type {Lobby} from './api'
import { leaveLobby, getCurrentLobby, openLobbySocket, startGame } from './api'
import {getToken} from '../userAuth/api'
import './LobbyPage.css'

function Header(){
    return (
        <header><h1> Current Lobby</h1></header>
    )
}

function LeaveLobbyButton(){
    const navigator = useNavigate()
    const { id } = useParams<{id: string}>()
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!id){
            return
        }
    }, [id])
    function handleLeaving(){
        if (!id) return
        try {
            leaveLobby(getToken(), id)
        
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Something went wrong. Please try again.')
        }
        navigator(`/HomePage`)
        
    }

    return (
        <>
            <button className="create-leave-button" onClick={handleLeaving}> Leave Lobby </button>
            {error && <p className="error" role="alert">{error}</p>}
        </>
    )
}

function StartGameButton({ lobby }: { lobby: Lobby }) {
    const [error, setError] = useState<string | null>(null)
    const [starting, setStarting] = useState(false)

    async function handleStart() {
        setError(null)
        if (lobby.num_players <= 1) {
            setError('You need at least 2 players to start the game.')
            return
        }
        setStarting(true)
        try {
            await startGame(getToken(), lobby.id)
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to start the game.')
            setStarting(false)
        }
    }

    return (
        <>
            <button
                className="create-leave-button"
                onClick={handleStart}
                disabled={starting || lobby.num_players <= 1}
            >
                {starting ? 'Starting...' : 'Start Game'}
            </button>
            {error && <p className="error">{error}</p>}
        </>
    )
}

function PlayerList({ lobby}: { lobby: Lobby }){
    let curr_players = Object.entries(lobby.player_ids) 

    return (
        <ul className="player-list">
            {curr_players.map(([key, value]) => (
                <li key={key} className="player-card">
                    {value.name}
                </li>
            ))}
        </ul>
    )
}

interface ChatMessage {
    user: string
    text: string
}

function MessageBox({ messages, wsRef }: {
    messages: ChatMessage[]
    wsRef: React.RefObject<WebSocket | null>
}) {
    const [text, setText] = useState('')
    const bottomRef = useRef<HTMLDivElement>(null)

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }, [messages])

    function handleSubmit(e: React.SubmitEvent<HTMLFormElement>) {
        e.preventDefault()
        const trimmed = text.trim()
        const ws = wsRef.current
        if (!trimmed || !ws || ws.readyState !== WebSocket.OPEN) return
        ws.send(JSON.stringify({ type: 'chat', text: trimmed }))
        setText('')
    }

    return (
        <div className="chat-box">
            <div className="chat-messages">
                {messages.map((m, i) => (
                    <p key={i}>{m.user}: {m.text}</p>
                ))}
                <div ref={bottomRef} />
            </div>
            <form onSubmit={handleSubmit} className="chat-form">
                <input
                    value={text}
                    onChange={e => setText(e.target.value)}
                    placeholder="Type a message"
                    maxLength={200}
                    autoComplete="off"
                />
                <button type="submit" disabled={!text.trim()}>Send</button>
            </form>
        </div>
    )
}


export function LobbyPage(){
    const navigator = useNavigate()
    // useParams uses the URL in order to find the exact lobby's id
    const { id } = useParams<{id: string}>()
    const [lobby, setLobby] = useState<Lobby | null>(null)
    const [error, setError] = useState<string | null>(null)
    const [messages, setMessages] = useState<ChatMessage[]>([])
    const wsRef = useRef<WebSocket | null>(null)

    useEffect(() => {
        if (!id){
            return
        }
        getCurrentLobby(getToken(), id).then(setLobby).catch(e => setError(e))
    }, [id])

    useEffect(() => {
        if (!id) return
        const ws = openLobbySocket(getToken(), id)
        wsRef.current = ws

        ws.onmessage = (event) => {
            const msg = JSON.parse(event.data)
            if (msg.type === 'lobby_update') {
                setLobby(msg.data)
            } else if (msg.type === 'lobby_closed') {
                navigator('/HomePage', { replace: true })
            } else if (msg.type === 'game_started') {
                navigator(`/game/${id}`)
            } else if (msg.type === 'chat'){
                setMessages(prevMessages => [...prevMessages, {user: msg.user, text: msg.text}].slice(-200))
            }
        }

        return () => {
            ws.close()
            wsRef.current = null
        }
    }, [id, navigator])

    if (error) return <p>{error}</p>
    if (!lobby) return <p>Loading...</p>
    console.log(lobby.num_players)
    console.log(`lobby: ${lobby.name}`)
    console.log(`lobby code: ${lobby.code}`)
    return(
        <>
            <Header />
            <div className="lobby-page">
                <h1>{lobby.name}</h1>
                <p>{lobby.num_players} / {lobby.max_players} players</p>
                <PlayerList lobby={lobby} />
                <LeaveLobbyButton />
                <StartGameButton lobby={lobby}/ >
                <p>Lobby Code: {lobby.code}</p>
                <MessageBox messages={messages} wsRef={wsRef}/>
            </div>
    
        
        </>
    )

}
