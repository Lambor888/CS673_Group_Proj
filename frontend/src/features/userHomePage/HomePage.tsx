import { Navigate, useNavigate } from 'react-router-dom'
import { getToken, getUsername } from '../userAuth/api'
import './HomePage.css'

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
          <button type="button">lobby</button>
        </nav>
        <button type="button" className="home-page__player" aria-label={`Player info: ${username ?? 'Player'}`}>
          <span>Player info</span>
          <strong>{username ?? 'Player'}</strong>
        </button>
      </header>
    </main>
  )
}
