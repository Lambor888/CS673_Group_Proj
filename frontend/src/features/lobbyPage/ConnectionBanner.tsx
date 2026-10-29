import type { LobbySocketStatus } from './useLobbySocket'
import './ConnectionBanner.css'

// Tells the player when their lobby connection is down; renders nothing while it's fine.
export function ConnectionBanner({ status }: { status: LobbySocketStatus }) {
    if (status === 'reconnecting') {
        return (
            <p className="connection-banner" role="status">
                Connection lost. Reconnecting…
            </p>
        )
    }
    if (status === 'replaced') {
        return (
            <p className="connection-banner" role="status">
                This lobby is open in another tab. Close this one or refresh to use it here.
            </p>
        )
    }
    return null
}
