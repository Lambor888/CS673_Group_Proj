import { AuthPage } from './features/userAuth/AuthPage'
import { HomePage} from './features/userHomePage/HomePage'
import { SinglePlayerPage } from './features/singlePlayer/SinglePlayerPage'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
export default function App() { 
    return (
    <BrowserRouter>
      <Routes>
        <Route path="/authpage" element={<AuthPage />} />
        <Route path="/homepage" element={<HomePage />} />
        <Route path="/singleplayer" element={<SinglePlayerPage />} />
        <Route path="/" element={<Navigate to="/authpage" />} />
      </Routes>
    </BrowserRouter>
    );
}

