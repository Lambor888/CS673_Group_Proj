import { AuthPage } from './features/userAuth/AuthPage'
import { HomePage} from './features/userHomePage/HomePage'
import { LobbyPage} from './features/lobbyPage/LobbyPage'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
export default function App() { 
    return (
    <BrowserRouter>
      <Routes>
        <Route path="/authpage" element={<AuthPage />} />
        <Route path="/homepage" element={<HomePage />} />
        <Route path="/lobby/:id" element={<LobbyPage />} />
        <Route path="/" element={<Navigate to="/authpage" />} />
      </Routes>
    </BrowserRouter>
    );
}

