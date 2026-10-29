import { useCallback } from 'react'
import { useParams } from 'react-router-dom'
import { useLobbySocket } from '../lobbyPage/useLobbySocket'
import { ConnectionBanner } from '../lobbyPage/ConnectionBanner'

export function GamePage(){
    const { id } = useParams<{id: string}>()
    // Stay connected to the lobby while playing: the server keeps your seat only while you're
    // connected (or briefly after a drop), and this is where lobby_closed / removal reach you.
    const handleMessage = useCallback(() => {
        // Game messages will be handled here once multiplayer rounds land.
    }, [])
    const { status } = useLobbySocket(id, handleMessage)

    return (
        <>
        <header><h1> Game Page</h1></header>
        <ConnectionBanner status={status} />
        </>
    )
}
