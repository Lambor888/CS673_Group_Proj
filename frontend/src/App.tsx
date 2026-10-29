import { AuthPage } from './features/userAuth/AuthPage'
import { HomePage} from './features/userHomePage/HomePage'
import { LobbyPage} from './features/lobbyPage/LobbyPage'
import {GamePage } from './features/multiPlayerPage/GamePage'
import { SinglePlayerPage } from './features/singlePlayer/SinglePlayerPage'
import { ProfilePage } from './features/profilePage/ProfilePage'
import { UserInfoPage } from './features/userInfo/UserInfoPage'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
export default function App() { 
    return (
    <BrowserRouter>
      <Routes>
        <Route path="/authpage" element={<AuthPage />} />
        <Route path="/homepage" element={<HomePage />} />
        <Route path="/userinfo" element={<UserInfoPage />} />
        <Route path="/lobby/:id" element={<LobbyPage />} />
        <Route path="/game/:id" element={<GamePage />} />
        <Route path="/singleplayer" element={<SinglePlayerPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/" element={<Navigate to="/authpage" />} />
      </Routes>
    </BrowserRouter>
    );
}

