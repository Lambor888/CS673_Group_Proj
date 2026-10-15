import { AuthPage } from './features/userAuth/AuthPage'
import { HomePage} from './features/userHomePage/HomePage'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
export default function App() { 
    return (
    <BrowserRouter>
      <Routes>
        <Route path="/authpage" element={<AuthPage />} />
        <Route path="/homepage" element={<HomePage />} />
        <Route path="/" element={<Navigate to="/authpage" />} />
      </Routes>
    </BrowserRouter>
    );
}

