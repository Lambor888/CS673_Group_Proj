import { useParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import type {Lobby} from './api'
import { leaveLobby, getCurrentLobby } from './api'
import {getToken, getUsername} from '../userAuth/api'
import './LobbyPage.css'

function Header(){
    return (
        <header><h1> Current Lobby</h1></header>
    )
}

function LeaveLobbyButton(){

    function handleLeaving(){
        return
    }

    return (
        <>
            <button className="create-leave-button" onClick={handleLeaving}>
            </button>
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


export function LobbyPage(){
    const navigator = useNavigate()
    // useParams uses the URL in order to find the exact lobby's id
    const { id } = useParams<{id: string}>()
    const [lobby, setLobby] = useState<Lobby | null>(null)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        if (!id){
            return
        }
        getCurrentLobby(getToken(), id).then(setLobby).catch(e => setError(e))
    }, [id])
    if (error) return <p>{error}</p>
    if (!lobby) return <p>Loading...</p>
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
                <p>Lobby Code: {lobby.code}</p>
            </div>
    
        
        </>
    )

}