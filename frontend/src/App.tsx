import { useState, useEffect, useCallback } from 'react';
import { getStoredUser, checkHealthWithRetry } from './api/client';
import type { User } from './types';
import LoginPage from './components/LoginPage';
import ChatPage from './components/ChatPage';
import './styles/app.css';

export default function App() {
  const [user, setUser] = useState<User | null>(getStoredUser);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);

  const refreshHealth = useCallback(() => {
    checkHealthWithRetry().then(setApiOnline);
  }, []);

  useEffect(() => {
    refreshHealth();
    const interval = setInterval(refreshHealth, 15000);
    return () => clearInterval(interval);
  }, [refreshHealth]);

  const handleLogin = (loggedIn: User) => {
    setUser(loggedIn);
    refreshHealth();
  };

  if (!user) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return <ChatPage user={user} onLogout={() => setUser(null)} apiOnline={apiOnline} />;
}
