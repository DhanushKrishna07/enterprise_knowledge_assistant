import { useState, FormEvent } from 'react';
import { login } from '../api/client';

interface Props {
  onLogin: (user: import('../types').User) => void;
}

const DEMO_ACCOUNTS = [
  { email: 'admin@example.com', password: 'admin123', label: 'Admin' },
  { email: 'employee@example.com', password: 'employee123', label: 'Employee' },
  { email: 'hr@example.com', password: 'hr123', label: 'HR' },
];

export default function LoginPage({ onLogin }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const user = await login(email, password);
      onLogin(user);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Login failed');
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (acc: typeof DEMO_ACCOUNTS[0]) => {
    setEmail(acc.email);
    setPassword(acc.password);
  };

  return (
    <div className="login-page">
      <div className="login-bg" />
      <div className="login-card">
        <div className="login-logo">
          <div className="login-logo-icon">🧠</div>
          <div>
            <div className="login-title">Enterprise Knowledge Assistant</div>
          </div>
        </div>

        <form className="login-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              required
              autoFocus
            />
          </div>
          <div className="form-group">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>
          {error && <div className="login-error">{error}</div>}
          <button type="submit" className="btn btn-primary" disabled={loading} style={{ width: '100%' }}>
            {loading ? <span className="spinner" /> : 'Sign in'}
          </button>
        </form>

        <div className="demo-accounts">
          <p>Demo accounts — click to fill:</p>
          {DEMO_ACCOUNTS.map((acc) => (
            <span key={acc.email} className="demo-chip" onClick={() => fillDemo(acc)}>
              {acc.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
