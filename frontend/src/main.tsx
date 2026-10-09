import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import Gallery from './Gallery';
type User = {username: string; isAdmin: boolean};
type Session = {user: User | null; csrfToken: string};
type Counts = {photos: number; albums: number; favorites: number};
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/${path}/`, {credentials: 'same-origin', ...options});
  const body = await response.json().catch(() => ({error: 'The request could not be completed. Refresh and try again.'}));
  if (!response.ok) throw new Error(body.error || 'The request could not be completed.');
  return body;
}
function Keepsake() {
  return <div className="keepsake" aria-hidden="true"><span className="tape"/><div className="drawing"><svg viewBox="0 0 340 300"><circle cx="250" cy="67" r="30" fill="#e9b894"/><path d="M0 190 Q90 95 180 190 T340 185 V300 H0Z" fill="#b9c5b3"/><path d="M0 240 Q120 140 230 227 T340 220 V300 H0Z" fill="#859a83"/><path d="M137 300 Q220 240 182 201" stroke="#e8dec7" strokeWidth="24" fill="none"/><path d="M57 83 C40 58 12 87 57 112 C102 87 75 58 57 83Z" fill="#b97b70"/></svg></div><span>somewhere, together.</span></div>;
}
function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {request<Session>('session').then(setSession).catch(e => setError(e.message)).finally(() => setLoaded(true));}, []);
  useEffect(() => {if (session?.user) request<Counts>('summary').then(setCounts).catch(e => setError(e.message)); else setCounts(null);}, [session]);
  async function signIn(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const form = new FormData(event.currentTarget);
    try {
      const fresh = await request<Session>('session');
      const next = await request<Session>('login', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':fresh.csrfToken}, body:JSON.stringify({username:form.get('username'),password:form.get('password')})});
      setSession(next);
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  async function signOut() {
    setBusy(true); setError('');
    try {
      await request('logout', {method:'POST',headers:{'X-CSRFToken':session!.csrfToken}});
      setSession(await request<Session>('session'));
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <div className="app"><header><a className="brand" href="/" aria-label="Our little album home"><span className="brand-icon">♡</span> our little album<span className="brand-dot">.</span></a><span className="private"><span/> A place for just us</span>{session?.user && <button className="quiet" onClick={signOut} disabled={busy}>Sign out</button>}</header>
    <main>
      {!loaded ? <p role="status">Opening our little album…</p> : session?.user ? <>
        <div className="welcome"><p className="eyebrow">OUR STORY, ONE MOMENT AT A TIME</p><h1>The little things.<br/><em>The everything things.</em></h1><p className="intro">Welcome home, {session.user.username}. A quiet corner for the days<br className="desktop"/> we never want to forget.</p></div>
        <div className="stats"><div><strong>{counts?.photos ?? '—'}</strong><span>moments kept</span></div><div><strong>{counts?.albums ?? '—'}</strong><span>little chapters</span></div><div><strong>{counts?.favorites ?? '—'}</strong><span>your favorites</span></div><span className="handwritten">made for the two of us ♡</span></div>
        <Gallery csrf={session.csrfToken} changed={() => {request<Counts>('summary').then(setCounts).catch(e => setError(e.message));}}/>
        {session.user.isAdmin && <p><a className="original-link" href="/admin/">Manage our space ↗</a></p>}

      </> : <section className="login-layout"><div className="login-copy"><p className="eyebrow">OUR OWN LITTLE CORNER OF THE WORLD</p><h1>For the moments<br/><em>that become us.</em></h1><p className="intro">The big adventures. The ordinary Sundays.<br/>A little home for everything in between.</p><Keepsake/><p className="illustration-note">A place for your photographs, together.</p></div><div className="login-card"><span className="tiny-heart">♡</span><h2>Welcome home.</h2><p>Just you, me, and our memories.</p><form onSubmit={signIn}><label htmlFor="username">Username</label><input id="username" name="username" autoComplete="username" maxLength={150} required disabled={busy}/><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" maxLength={1024} required disabled={busy}/><button className="button" disabled={busy || !session}>{busy ? 'Opening the album…' : 'Step inside'}<span>→</span></button></form><p className="login-help">Invite-only, always.<br/>Accounts are created by your administrator.</p></div></section>}
      {error && <div className="error" role="alert">{error}</div>}
    </main><footer><span>Our little album</span><span>A private place. A shared story. ♡</span></footer></div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
