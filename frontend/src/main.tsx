import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import Gallery from './Gallery';
import Dates from './Dates';
import Icon from './Icon';
import { AlbumNavigation, Brand, JournalCover, PageTitle } from './Layout';
import {type MediaKind} from './MediaFilter';
type User = {username: string; isAdmin: boolean};
type Session = {user: User | null; csrfToken: string};
type Counts = {undatedCount: number; photos: number; albums: number; favorites: number};
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/${path}/`, {credentials: 'same-origin', ...options});
  const body = await response.json().catch(() => ({error: 'The request could not be completed. Refresh and try again.'}));
  if (!response.ok) throw new Error(body.error || 'The request could not be completed.');
  return body;
}
function SignInCascade() {
  const [items] = useState(() => {const count = window.matchMedia('(max-width: 800px)').matches ? 28 : 48;return Array.from({length: count}, (_, i) => {
    const variation = (seed: number) => ((i * seed + 17) % 97) / 97;
    return {id: i, sheet: i % 4 === 0, style: {
      left: `${variation(37) * 96}%`, '--size': `${38 + variation(19) * 44}px`,
      '--delay': `${Math.floor(i / Math.ceil(count / 3)) * .48 + variation(41) * .35}s`,
      '--fall': `${2.1 + variation(29) * .5}s`, '--tilt': `${-35 + variation(23) * 70}deg`,
      '--drift': `${-90 + variation(53) * 180}px`, '--spin': `${-65 + variation(31) * 130}deg`,
      '--flutter': `${.5 + variation(13) * .65}s`,
    } as React.CSSProperties};
  });});
  return <div className="sign-in-flutter" aria-hidden="true">{items.map(item => <span key={item.id} className="falling-memory" style={item.style}><span className={`cascade-paper ${item.sheet ? 'scrapbook-sheet' : ''}`}><i/></span></span>)}</div>;
}
const initialSection = () => ['#dates', '#missing-dates'].includes(window.location.hash) ? window.location.hash.slice(1) : 'memories';
function App() {
  const [flutter, setFlutter] = useState(false);
  useEffect(() => {if (!flutter) return;const timeout = window.setTimeout(() => setFlutter(false), 4000);return () => window.clearTimeout(timeout);}, [flutter]);
  const [session, setSession] = useState<Session | null>(null);
  const [counts, setCounts] = useState<Counts | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [section, setSection] = useState(initialSection);
  const [kind, setKind] = useState<MediaKind>('');
  const [revision, setRevision] = useState(0);
  const [galleryRevision, setGalleryRevision] = useState(0);
  useEffect(() => {
    const navigate = () => setSection(initialSection());
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
      document.getElementById(target === 'dates' ? 'dates-heading' : target === 'missing-dates' ? 'missing-heading' : 'memories-heading')?.focus({preventScroll: true});
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
      setKind('');
      setSession(next);
      if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) setFlutter(true);
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  async function signOut() {
    setBusy(true); setError('');
    try {
      await request('logout', {method:'POST',headers:{'X-CSRFToken':session!.csrfToken}});
      setFlutter(false);
      setSession(await request<Session>('session'));
    } catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <div className="app">{flutter && <SignInCascade/>}<a className="skip-link" href="#main-content">Skip to memories</a><header><Brand/>{session?.user && <button className="quiet" onClick={signOut} disabled={busy}><Icon name="logout"/>Sign out</button>}</header>
    <main id="main-content" tabIndex={-1}>
      {!loaded ? <p role="status">Opening our little album…</p> : session?.user ? <div className="album-layout">
        <AlbumNavigation section={section} undatedCount={counts?.undatedCount ?? 0} navigate={navigateTo}/>
        <div className="album-content">
        <div className="section-view" hidden={section === 'dates'} inert={section === 'dates'}>
        <div className="welcome" hidden={section === 'missing-dates'}><PageTitle id="memories-heading">The little things.<br/><em>The everything things.</em></PageTitle></div>
        <Gallery kind={kind} setKind={setKind} undated={section === 'missing-dates'} active={section !== 'dates'} csrf={session.csrfToken} revision={galleryRevision} changed={() => {refreshCounts(); setRevision(value => value + 1);}}/>
        </div>
        {section === 'dates' && <div className="section-view"><Dates kind={kind} setKind={setKind} csrf={session.csrfToken} revision={revision} changed={() => {refreshCounts(); setGalleryRevision(value => value + 1);}}/></div>}
        {session.user.isAdmin && <p><a className="original-link" href="/admin/">Manage our space <Icon name="external"/></a></p>}

        </div></div> : <section className="login-layout"><JournalCover/><div className="login-card"><h2>Welcome home.</h2>{error && <p className="error" role="alert">{error}</p>}<form onSubmit={signIn}><label htmlFor="username">Username</label><input id="username" name="username" autoComplete="username" maxLength={150} required disabled={busy}/><label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" maxLength={1024} required disabled={busy}/><button className="button" disabled={busy || !session}>{busy ? 'Opening the album…' : 'Step inside'}<Icon name="arrow"/></button></form><p className="login-help">A private place for our digital world.</p></div></section>}
      {error && session?.user && <div className="error" role="alert">{error}</div>}
    </main><footer><span>Our little album</span><span>Made for the memories.</span></footer></div>;
}
createRoot(document.getElementById('root')!).render(<React.StrictMode><App/></React.StrictMode>);
