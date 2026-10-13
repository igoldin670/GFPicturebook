import { useEffect, useRef, useState } from 'react';
import { api, PhotoCard, PhotoDetail, type Page, type Photo } from './Gallery';
import './Dates.css';

type Chapter = {month: string; count: number};
type Spread = Page & {chapter: Chapter; number: number};
type Turn = {from: Spread; to: Spread; direction: 'next' | 'previous'};
const monthDate = (month: string) => {const date = new Date(0); const [year, number] = month.split('-').map(Number); date.setFullYear(year, number - 1, 1); date.setHours(12, 0, 0, 0); return date;};
const monthName = (month: string) => monthDate(month).toLocaleDateString(undefined, {month: 'long'});
const monthLabel = (month: string) => `${monthName(month)} ${month.split('-')[0]}`;
const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function Flourish() {
  return <svg className="book-flourish" viewBox="0 0 100 52" fill="none" aria-hidden="true"><path d="M50 44V14M50 33C30 35 20 25 20 16C37 15 48 22 50 33ZM50 25C65 27 77 19 78 9C62 8 52 15 50 25ZM50 17C42 11 43 5 50 2C57 5 58 11 50 17Z" stroke="currentColor" strokeWidth="1.1"/><path d="M10 45Q50 39 90 45" stroke="currentColor" strokeWidth=".7"/></svg>;
}
function ChapterPage({spread}: {spread: Spread | null}) {
  return <div className="chapter-page"><span className="chapter-kicker">{spread ? `CHAPTER ${String(spread.number).padStart(2, '0')}` : 'THE STORY BEGINS'}</span><Flourish/><h2 className="chapter-month">{spread ? monthName(spread.chapter.month) : 'Someday'}</h2><p className="chapter-year">{spread ? spread.chapter.month.split('-')[0] : 'starts here'}</p><span className="chapter-rule"/><p className="chapter-note">{spread ? 'A little piece of our story.' : 'No memories from this month yet.'}</p><p className="chapter-count">{spread ? `${spread.chapter.count} ${spread.chapter.count === 1 ? 'memory' : 'memories'} tucked between these pages` : 'Add a memory to write the first chapter.'}</p></div>;
}
function KeepsakePage({spread, open}: {spread: Spread | null; open: (photo: Photo) => void}) {
  return <div className="keepsake-page"><span className="page-handwriting">the days we’ll keep ♡</span><div className="book-keepsakes">{spread?.photos.slice(0, 2).map(photo => <div className="book-keepsake" key={photo.id}><span className="book-photo-tape" aria-hidden="true"/><PhotoCard photo={photo} open={() => open(photo)}/></div>)}{!spread?.photos.length && <div className="unwritten-memory"><span>♡</span><p>Room for all the<br/>days to come.</p></div>}</div><span className="page-number">{spread ? String(spread.number * 2).padStart(2, '0') : '01'}</span></div>;
}

export default function Dates({csrf, revision, changed}: {csrf: string; revision: number; changed: () => void}) {
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [spread, setSpread] = useState<Spread | null>(null);
  const [phase, setPhase] = useState<'closed' | 'opening' | 'open'>('closed');
  const [turn, setTurn] = useState<Turn | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState<Photo | null>(null);
  const [reload, setReload] = useState(0);
  const current = useRef<Spread | null>(null);
  const request = useRef<AbortController | null>(null);
  const timers = useRef<number[]>([]);
  const locked = useRef(false);
  const navigation = useRef<HTMLElement>(null);
  current.current = spread;
  const schedule = (fn: () => void, delay: number) => {timers.current.push(window.setTimeout(fn, delay));};
  useEffect(() => {
    if (reducedMotion()) setPhase('open');
    else {schedule(() => setPhase('opening'), 420); schedule(() => setPhase('open'), 2180);}
    return () => {timers.current.forEach(window.clearTimeout); request.current?.abort();};
  }, []);
  useEffect(() => {
    const controller = new AbortController();
    let refreshTimer: number | undefined;
    // Finish an in-flight page turn before refreshing metadata from background uploads.
    async function refresh() {
      if (locked.current) {refreshTimer = window.setTimeout(() => void refresh(), 1200); return;}
      request.current?.abort(); request.current = controller;
      setLoading(true);
      try {
        const result = await api<{months: Chapter[]}>('/api/photos/months/', {signal: controller.signal});
        const index = Math.max(0, result.months.findIndex(chapter => chapter.month === current.current?.chapter.month));
        const chapter = current.current && result.months.some(chapter => chapter.month === current.current?.chapter.month) ? result.months[index] : result.months.at(-1);
        const page = chapter ? await api<Page>(`/api/photos/?month=${chapter.month}`, {signal: controller.signal}) : null;
        if (controller.signal.aborted) return;
        setChapters(result.months);
        setSpread(chapter && page ? {...page, chapter, number: result.months.indexOf(chapter) + 1} : null);
        setError('');
      } catch(e) {if (!controller.signal.aborted) setError((e as Error).message);}
      finally {if (!controller.signal.aborted) setLoading(false);}
    }
    void refresh();
    return () => {controller.abort(); window.clearTimeout(refreshTimer);};
  }, [revision, reload]);

  async function travel(index: number) {
    if (locked.current || phase !== 'open' || loading || !spread || index < 0 || index >= chapters.length || chapters[index].month === spread.chapter.month) return;
    locked.current = true; setBusy(true); setError('');
    const focused = document.activeElement;
    const restoreFocus = () => window.requestAnimationFrame(() => {
      if (focused instanceof HTMLElement && focused.isConnected && !focused.matches(':disabled')) focused.focus({preventScroll: true});
      else navigation.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus({preventScroll: true});
    });
    const controller = new AbortController(); request.current?.abort(); request.current = controller;
    try {
      const page = await api<Page>(`/api/photos/?month=${chapters[index].month}`, {signal: controller.signal});
      if (controller.signal.aborted) return;
      const target = {...page, chapter: chapters[index], number: index + 1};
      if (reducedMotion()) {setSpread(target); locked.current = false; setBusy(false); restoreFocus();}
      else {
        setTurn({from: spread, to: target, direction: index > spread.number - 1 ? 'next' : 'previous'});
        schedule(() => setSpread(target), 530);
        schedule(() => {setTurn(null); locked.current = false; setBusy(false); restoreFocus();}, 1100);
      }
    } catch(e) {
      if (!controller.signal.aborted) {setError((e as Error).message); locked.current = false; setBusy(false); restoreFocus();}
    }
  }
  async function more() {
    if (!spread?.next || locked.current) return;
    locked.current = true; setBusy(true); setError('');
    const controller = new AbortController(); request.current?.abort(); request.current = controller;
    try {
      const page = await api<Page>(`/api/photos/?month=${spread.chapter.month}&cursor=${encodeURIComponent(spread.next)}`, {signal: controller.signal});
      if (!controller.signal.aborted) setSpread({...spread, next: page.next, photos: [...spread.photos, ...page.photos.filter(photo => !spread.photos.some(old => old.id === photo.id))]});
    } catch(e) {if (!controller.signal.aborted) setError((e as Error).message);}
    finally {if (!controller.signal.aborted) {locked.current = false; setBusy(false);}}
  }
  const index = spread ? spread.number - 1 : -1;
  const previous = chapters[index - 1]; const next = chapters[index + 1];
  const unavailable = busy || loading || phase !== 'open';
  return <section className="dates-section" aria-labelledby="dates-heading">
    <div className="dates-heading"><p className="eyebrow">OUR STORY, CHAPTER BY CHAPTER</p><h1 id="dates-heading" tabIndex={-1}>Some days deserve<br/><em>a page of their own.</em></h1><p className="intro">Open a chapter. Stay a little while.</p></div>
    <div className={`book-scene book-${phase} ${turn ? 'book-turning' : ''}`} aria-busy={busy || loading}>
      <div className="book-ground-shadow" aria-hidden="true"/>
      <div className="memory-book">
        <div className="book-back-cover" aria-hidden="true"/>
        <div className="book-page-stack book-stack-left" aria-hidden="true"/>
        <div className="book-page-stack book-stack-right" aria-hidden="true"/>
        <div className="book-spread" inert={phase !== 'open' || Boolean(turn)}>
          <div className="book-page book-page-left"><ChapterPage spread={spread}/></div>
          <div className="book-page book-page-right"><KeepsakePage spread={spread} open={setSelected}/></div>
          <div className="book-binding" aria-hidden="true"><span/><span/><span/></div>
          <nav ref={navigation} className="book-navigation" aria-label="Memory chapters">
            <button disabled={unavailable || !previous} onClick={() => void travel(index - 1)} aria-label={previous ? `Previous chapter: ${monthLabel(previous.month)}` : 'No earlier chapter'}><span aria-hidden="true">‹</span><span>{previous ? monthName(previous.month) : 'First chapter'}<small>{previous?.month.split('-')[0] ?? 'The beginning'}</small></span></button>
            <span className="book-pagination" aria-hidden="true">{spread ? `${spread.number} / ${chapters.length}` : '♡'}</span>
            <button disabled={unavailable || !next} onClick={() => void travel(index + 1)} aria-label={next ? `Next chapter: ${monthLabel(next.month)}` : 'No later chapter'}><span>{next ? monthName(next.month) : 'Latest chapter'}<small>{next?.month.split('-')[0] ?? 'To be continued'}</small></span><span aria-hidden="true">›</span></button>
          </nav>
        </div>
        {turn && <div className={`turning-leaf turn-${turn.direction}`} aria-hidden="true" inert><div className="leaf-face leaf-front">{turn.direction === 'next' ? <KeepsakePage spread={turn.from} open={() => {}}/> : <ChapterPage spread={turn.from}/>}</div><div className="leaf-face leaf-back">{turn.direction === 'next' ? <ChapterPage spread={turn.to}/> : <KeepsakePage spread={turn.to} open={() => {}}/>}</div></div>}
        <div className="book-front-cover" aria-hidden="true"><div className="cover-face cover-outside"><span className="cover-edition">OUR LITTLE ALBUM</span><div className="cover-title"><Flourish/><p>Our days,<br/><em>together.</em></p><span>A COLLECTION OF LITTLE MOMENTS</span></div><span className="cover-heart">♡</span><span className="cover-spine"/></div><div className="cover-face cover-inside"><span className="inside-inscription">Every day, a little more us.</span></div></div>
        <span className="book-ribbon" aria-hidden="true"/>
      </div>
    </div>
    <p className="book-status" role="status" aria-live="polite">{loading ? 'Finding our chapters…' : busy ? 'Turning to another little piece of our story…' : phase !== 'open' ? 'Opening the memory book…' : spread ? `${monthLabel(spread.chapter.month)} · ${spread.chapter.count} ${spread.chapter.count === 1 ? 'memory' : 'memories'}` : 'Your first chapter is waiting to be written.'}</p>
    {error && <p className="error" role="alert">{error} <button className="quiet" onClick={() => setReload(value => value + 1)}>Try again</button></p>}
    {spread && <div className={`chapter-collection ${turn ? 'collection-turning' : ''} ${phase !== 'open' ? 'collection-waiting' : ''}`} inert={phase !== 'open' || Boolean(turn)} aria-hidden={phase !== 'open' || undefined}><div className="chapter-collection-heading"><div><p className="eyebrow">BETWEEN THESE PAGES</p><h2>{monthLabel(spread.chapter.month)}</h2></div><label className="chapter-picker">Find a chapter<select value={spread.chapter.month} disabled={unavailable} onChange={event => void travel(chapters.findIndex(chapter => chapter.month === event.target.value))}>{chapters.map(chapter => <option key={chapter.month} value={chapter.month}>{monthLabel(chapter.month)} · {chapter.count}</option>)}</select></label></div><div className="photo-grid" key={spread.chapter.month}>{spread.photos.map(photo => <PhotoCard key={photo.id} photo={photo} open={() => setSelected(photo)}/>)}</div>{spread.photos.length === 0 && <p className="empty-library">No memories from this month yet.</p>}{spread.next && <button className="button load-more" disabled={unavailable} onClick={() => void more()}>More from this chapter ↓</button>}</div>}
    {selected && <PhotoDetail key={selected.id} photo={selected} csrf={csrf} close={() => setSelected(null)} saved={() => {setReload(value => value + 1); changed();}}/>}
  </section>;
}
