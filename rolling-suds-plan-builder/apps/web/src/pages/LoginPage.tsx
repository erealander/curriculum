import { useState } from 'react';
import { api, setToken } from '../lib/api';

export function LoginPage({ onDone }: { onDone: (user: { id: string; name: string }) => void }) {
  const [email, setEmail] = useState('estimator@rollingsuds.com');
  const [password, setPassword] = useState('rolling123!');
  const [error, setError] = useState('');

  return (
    <main style={{ maxWidth: 420, margin: '64px auto' }}>
      <h1>Rolling Suds Login</h1>
      <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="email" />
      <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="password" />
      <button onClick={async () => {
        try {
          const result = await api.login(email, password);
          setToken(result.token);
          onDone(result.user);
        } catch {
          setError('Login failed');
        }
      }}>Sign in</button>
      {error && <p>{error}</p>}
    </main>
  );
}
