import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api, errorMessage } from './api';
import Gallery from './Gallery';
import Icon from './Icon';
import type { Session } from './types';
import './style.css';

function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const controller = new AbortController();
    api<Session>('/api/session/', { signal: controller.signal })
      .then(setSession)
      .catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)); })
      .finally(() => { if (!controller.signal.aborted) setLoading(false); });
    const expired = () => {
      setSession(null);
      setError('Your session has ended. Sign in again.');
    };
    window.addEventListener('session-expired', expired);
    return () => {
      controller.abort();
      window.removeEventListener('session-expired', expired);
    };
  }, []);

  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    const form = new FormData(event.currentTarget);
    try {
      const fresh = await api<Session>('/api/session/');
      const next = await api<Session>('/api/login/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': fresh.csrfToken },
        body: JSON.stringify({ username: form.get('username'), password: form.get('password') }),
      });
      setSession(next);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError('');
    try {
      await api('/api/logout/', { method: 'POST', headers: { 'X-CSRFToken': session!.csrfToken } });
      // Remove private UI immediately, even if the next network request fails.
      setSession(null);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="app">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="site-header">
        <a className="brand" href="/" aria-label="Our album home"><Icon name="album"/>Our album</a>
        <nav className="header-actions" aria-label="Account">
          {session?.user ? <>
            <span className="username">{session.user.username}</span>
            {session.user.isAdmin && <a className="text-button" href="/admin/">Settings</a>}
            <button className="text-button" onClick={signOut} disabled={busy}>Sign out</button>
          </> : <span className="private-label"><Icon name="lock"/>Just us</span>}
        </nav>
      </header>
      <main id="main">
        {loading ? <p className="page-status" role="status">Loading…</p> : session?.user ? <>
          {error && <p className="notice error" role="alert">{error}</p>}
          <Gallery csrf={session.csrfToken}/>
        </> : <section className="login-page">
          <div className="login-card">
            <span className="login-mark"><Icon name="album"/></span>
            <h1>Our album</h1>
            <p className="login-intro">A place for our photos.</p>
            <form onSubmit={signIn}>
              <label htmlFor="username">Username</label>
              <input id="username" name="username" autoComplete="username" autoCapitalize="none" spellCheck={false} maxLength={150} required disabled={busy}/>
              <label htmlFor="password">Password</label>
              <input id="password" name="password" type="password" autoComplete="current-password" maxLength={1024} required disabled={busy}/>
              {error && <p className="notice error" role="alert">{error}</p>}
              <button className="button login-submit" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
            </form>
            <p className="login-note"><Icon name="lock"/>Private, and shared by us.</p>
          </div>
        </section>}
      </main>
      <footer className="site-footer"><span>Our album</span><span>For the two of us <span className="footer-heart" aria-hidden="true">♡</span></span></footer>
    </div>
  );
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
