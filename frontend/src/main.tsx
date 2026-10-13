import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import Gallery from './Gallery';
import Dates from './Dates';
import Icon from './Icon';
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
  return <div className="keepsake" aria-hidden="true"><span className="tape"/><div className="drawing"><svg viewBox="0 0 340 300"><circle cx="250" cy="67" r="30" fill="#e9b894"/><path d="M0 190 Q90 95 180 190 T340 185 V300 H0Z" fill="#b9c5b3"/><path d="M0 240 Q120 140 230 227 T340 220 V300 H0Z" fill="#859a83"/><path d="M137 300 Q220 240 182 201" stroke="#e8dec7" strokeWidth="24" fill="none"/><path d="M57 59l6 17 17 6-17 6-6 17-6-17-17-6 17-6Z" fill="#b97b70"/></svg></div><span>somewhere, together.</span></div>;
}
function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [section, setSection] = useState(window.location.hash === '#dates' ? 'dates' : 'memories');
  const [revision, setRevision] = useState(0);
  const [galleryRevision, setGalleryRevision] = useState(0);
  useEffect(() => {
    const navigate = () => setSection(window.location.hash === '#dates' ? 'dates' : 'memories');
    window.addEventListener('hashchange', navigate);
    return () => window.removeEventListener('hashchange', navigate);
  }, []);
  function refreshCounts() {request<Counts>('summary').then(setCounts).catch(e => setError(e.message));}
  function navigateTo(event: React.MouseEvent<HTMLAnchorElement>, target: string) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    if (section === target) return;
    window.location.hash = target;
    setSection(target);
    window.requestAnimationFrame(() => {
      document.getElementById(target === 'dates' ? 'dates-heading' : 'memories-heading')?.focus({preventScroll: true});
      window.scrollTo({top: 0, behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth'});
    });
  }
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
  return <div className="app"><header><a className="brand" href="/" aria-label="Our little album home"><span className="brand-icon"><Icon name="orbit"/></span> our little album<span className="brand-dot">.</span></a>{session?.user && <button className="quiet" onClick={signOut} disabled={busy}><Icon name="logout"/>Sign out</button>}</header>
    <main>
      {!loaded ? <p role="status">Opening our little album…</p> : session?.user ? <div className="album-layout">
        <nav className="album-navigation" aria-label="Album sections"><div className="album-navigation-inner"><a href="#memories" aria-current={section === 'memories' ? 'page' : undefined} onClick={event => navigateTo(event, 'memories')}><Icon name="photo"/>Memories</a><a href="#dates" aria-current={section === 'dates' ? 'page' : undefined} onClick={event => navigateTo(event, 'dates')}><Icon name="book"/>Dates</a></div></nav>
        <div className="album-content">
        <div className="section-view" hidden={section !== 'memories'} inert={section !== 'memories'}>
        <div className="welcome"><h1 id="memories-heading" tabIndex={-1}>The little things.<br/><em>The everything things.</em></h1></div>
        <div className="stats"><div><strong>{counts?.photos ?? '…'}</strong><span>moments kept</span></div><div><strong>{counts?.albums ?? '…'}</strong><span>albums created</span></div><div><strong>{counts?.favorites ?? '…'}</strong><span>your favorites</span></div></div>
        <Gallery csrf={session.csrfToken} revision={galleryRevision} changed={() => {refreshCounts(); setRevision(value => value + 1);}}/>
        </div>
        {section === 'dates' && <div className="section-view"><Dates csrf={session.csrfToken} revision={revision} changed={() => {refreshCounts(); setGalleryRevision(value => value + 1);}}/></div>}
        {session.user.isAdmin && <p><a className="original-link" href="/admin/">Manage our space <Icon name="external"/></a></p>}

        </div></div> : <section className="login-layout"><div className="login-copy"><h1>For the moments<br/><em>that become us.</em></h1><p className="intro">The big adventures. The ordinary Sundays.<br/>A little home for everything in between.</p><Keepsake/></div><div className="login-card"><span className="login-emblem"><Icon name="orbit"/></span><h2>Welcome home.</h2><form onSubmit={signIn}><label htmlFor="username">Username</label><input id="username" name="username" autoComplete="username" maxLength={150} required disabled={busy}/><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" maxLength={1024} required disabled={busy}/><button className="button" disabled={busy || !session}>{busy ? 'Opening the album…' : 'Step inside'}<Icon name="arrow"/></button></form><p className="login-help">Invite-only, always.<br/>Accounts are created by your administrator.</p></div></section>}
      {error && <div className="error" role="alert">{error}</div>}
    </main><footer><span>Our little album</span></footer></div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
