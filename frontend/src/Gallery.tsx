import { useCallback, useEffect, useRef, useState } from 'react';

type Photo = {id: string; filename: string; date: string; dateSource: string; caption: string; width: number; height: number; camera: string; latitude: string | null; longitude: string | null; thumbnail: string; preview: string; original: string};
type Page = {photos: Photo[]; next: string | null};
type Job = {id: string; filename: string; status: string; message: string};
type Transfer = {id: string; file: File; progress: number; state: 'queued' | 'sending' | 'accepted' | 'error'; error?: string};
async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, {credentials: 'same-origin', ...options});
  const data = await response.json().catch(() => ({error: 'Request failed. Check your connection and try again.'}));
  if (!response.ok) throw new Error(data.error || 'Request failed. Please refresh and try again.');
  return data;
}
function uploadFile(item: Transfer, csrf: string, signal: AbortSignal, progress: (percent: number) => void) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/photos/upload/');
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('X-CSRFToken', csrf);
    xhr.setRequestHeader('Idempotency-Key', item.id);
    xhr.setRequestHeader('X-Filename', encodeURIComponent(item.file.name));
    xhr.timeout = 120000;
    xhr.upload.onprogress = event => {if (event.lengthComputable) progress(Math.round(event.loaded / event.total * 100));};
    const abort = () => xhr.abort();
    signal.addEventListener('abort', abort, {once:true});
    xhr.onloadend = () => signal.removeEventListener('abort', abort);
    xhr.onload = () => {
      if (xhr.status === 202) resolve();
      else {
        let message = xhr.status === 413 ? 'This photo is too large (maximum 50 MiB).' : 'Upload failed. Refresh your session and retry.';
        try {message = JSON.parse(xhr.responseText).error || message;} catch { /* Proxy errors may not be JSON. */ }
        reject(new Error(message));
      }
    };
    xhr.onerror = () => reject(new Error('Connection lost. Retry uses the same upload identifier.'));
    xhr.ontimeout = () => reject(new Error('Upload timed out. You can retry safely.'));
    xhr.onabort = () => reject(new Error('Upload stopped.'));
    if (signal.aborted) reject(new Error('Upload stopped.'));
    else xhr.send(item.file);
  });
}
const readableDate = (value: string) => new Date(`${value}T12:00:00`).toLocaleDateString(undefined, {year:'numeric', month:'long', day:'numeric'});

function PhotoDetail({photo, csrf, close, saved}: {photo: Photo; csrf: string; close: () => void; saved: () => void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [caption, setCaption] = useState(photo.caption);
  const [date, setDate] = useState(photo.date);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  useEffect(() => {dialog.current?.showModal();}, []);
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true); setError('');
    try {await api(`/api/photos/${photo.id}/edit/`, {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({caption,date})}); saved(); close();}
    catch(e) {setError((e as Error).message);} finally {setBusy(false);}
  }
  return <dialog ref={dialog} className="photo-dialog" onCancel={close} aria-labelledby="detail-heading"><button className="close-photo" onClick={close} aria-label="Close photo">×</button><img className="detail-image" src={photo.preview} alt={photo.caption || photo.filename}/><div className="detail-content"><p className="eyebrow">A MOMENT TO KEEP</p><h2 id="detail-heading">{readableDate(photo.date)}</h2><form onSubmit={save}><label htmlFor="photo-date">Date taken</label><input id="photo-date" type="date" value={date} onChange={event => setDate(event.target.value)} required/><p className="field-note">Date source: {photo.dateSource === 'upload' ? 'Upload date — no usable capture date found' : photo.dateSource === 'manual' ? 'Manually edited' : 'Camera metadata'}</p><label htmlFor="photo-caption">A few words about this day</label><textarea id="photo-caption" value={caption} maxLength={5000} onChange={event => setCaption(event.target.value)} placeholder="What do you want to remember?"/><button className="button" disabled={busy}>{busy ? 'Saving…' : 'Save this memory'}</button></form>{error && <p role="alert" className="error">{error}</p>}<dl className="photo-facts"><dt>Original size</dt><dd>{photo.width} × {photo.height}</dd>{photo.camera && <><dt>Camera</dt><dd>{photo.camera}</dd></>}{photo.latitude !== null && photo.longitude !== null && <><dt>GPS coordinates</dt><dd>{photo.latitude}, {photo.longitude}</dd></>}</dl><a className="original-link" href={photo.original}>Download unchanged original ↗</a><p className="field-note">Originals may include location metadata.</p></div></dialog>;
}

export default function Gallery({csrf, changed}: {csrf: string; changed: () => void}) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [next, setNext] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<Photo | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const loadingRef = useRef(false);
  const busyRef = useRef(false);
  const pendingRef = useRef(false);
  const pendingSignature = useRef('');
  const changedRef = useRef(changed);
  changedRef.current = changed;
  useEffect(() => {mounted.current = true; return () => {mounted.current = false; controller.current?.abort();};}, []);
  const load = useCallback(async (cursor?: string) => {
    if (loadingRef.current) return;
    loadingRef.current = true; setLoading(true);
    try {
      const page = await api<Page>(`/api/photos/${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`);
      if (!mounted.current) return;
      setPhotos(previous => cursor ? [...previous, ...page.photos.filter(p => !previous.some(old => old.id === p.id))] : page.photos);
      setNext(page.next); setError('');
    } catch(e) {if (mounted.current) setError((e as Error).message);}
    finally {loadingRef.current = false; if (mounted.current) setLoading(false);}
  }, []);
  const poll = useCallback(async () => {
    try {
      const result = await api<{uploads: Job[]}>('/api/photos/uploads/');
      if (!mounted.current) return;
      const signature = result.uploads.filter(j => j.status === 'pending' || j.status === 'processing').map(j => j.id).sort().join(',');
      if (pendingRef.current || pendingSignature.current !== signature) {void load(); changedRef.current();}
      pendingRef.current = false;
      pendingSignature.current = signature;
      setJobs(result.uploads);
    } catch(e) {if (mounted.current) setError((e as Error).message);}
  }, [load]);
  useEffect(() => {void load(); void poll(); const timer = window.setInterval(() => {if (!document.hidden) void poll();}, 4000); return () => window.clearInterval(timer);}, [load,poll]);
  function update(id: string, patch: Partial<Transfer>) {if (mounted.current) setTransfers(items => items.map(item => item.id === id ? {...item,...patch} : item));}
  async function send(items: Transfer[]) {
    if (busyRef.current) return;
    busyRef.current = true; setUploading(true); const abort = new AbortController(); controller.current = abort;
    // Sequential uploads bound memory, request pressure, and phone bandwidth.
    for (const item of items) {
      if (abort.signal.aborted) break;
      update(item.id, {state:'sending',error:undefined});
      try {
        if (item.file.size > 50*1024*1024) throw new Error('Photo exceeds the 50 MiB limit.');
        await uploadFile(item, csrf, abort.signal, percent => update(item.id,{progress:percent}));
        update(item.id,{state:'accepted',progress:100}); pendingRef.current = true;
        void poll();
      } catch(e) {update(item.id,{state:'error',error:(e as Error).message});}
    }
    busyRef.current = false;
    if (mounted.current) {setUploading(false); void load(); changedRef.current();}
  }
  function choose(files: FileList | null) {
    if (!files || busyRef.current) return;
    if (files.length > 100) {setError('Choose up to 100 photos per batch.'); return;}
    const items: Transfer[] = Array.from(files).map(file => ({id:crypto.randomUUID(),file,progress:0,state:'queued'}));
    setTransfers(items); void send(items);
  }
  return <section className="library"><div className="library-heading"><div><p className="eyebrow">OUR GROWING COLLECTION</p><h2>Little moments, kept.</h2></div><button className="button" disabled={uploading} onClick={() => picker.current?.click()}>＋ Add photos</button></div><input className="file-picker" ref={picker} type="file" accept="image/jpeg,image/png,image/webp,image/heic,image/heif,.heic,.heif" multiple onChange={event => {choose(event.target.files); event.target.value='';}} aria-label="Choose photos"/>
    <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={event => {event.preventDefault();setDragging(true);}} onDragLeave={() => setDragging(false)} onDrop={event => {event.preventDefault();setDragging(false);choose(event.dataTransfer.files);}}><span>♡</span><p>Bring a little of your world here.</p><button className="quiet" disabled={uploading} onClick={() => picker.current?.click()}>Choose photos <span className="desktop">or drag them here</span></button><small>JPEG, PNG, WebP & HEIC · up to 50 MiB each · originals kept unchanged</small></div>
    <p className="backup-note">Backups are not automatic yet. Please keep another copy of every photo you upload.</p>
    {transfers.length > 0 && <details className="upload-progress" open><summary>Uploads · {transfers.filter(t => t.state === 'accepted').length} of {transfers.length} received</summary><ul>{transfers.map(item => <li key={item.id}><span>{item.file.name}</span><span>{item.state === 'sending' ? `${item.progress}%` : item.state === 'accepted' ? 'Received — processing separately' : item.state === 'error' ? item.error : 'Queued'}</span>{item.state === 'sending' && <progress max={100} value={item.progress} aria-label={`Uploading ${item.file.name}`}/>}</li>)}</ul>{transfers.some(item => item.state === 'error') && <button className="quiet" disabled={uploading} onClick={() => void send(transfers.filter(t => t.state === 'error'))}>Retry unsuccessful uploads</button>}{!uploading && <button className="quiet" onClick={() => setTransfers([])}>Dismiss upload progress</button>}</details>}
    {jobs.length > 0 && <details className="processing-status" open={jobs.some(j => j.status !== 'failed')}><summary>{jobs.filter(j => j.status !== 'failed').length} processing · {jobs.filter(j => j.status === 'failed').length} unable to process</summary><ul>{jobs.map(job => <li key={job.id}><strong>{job.filename}</strong><span>{job.message}</span></li>)}</ul></details>}
    {error && <p className="error" role="alert">{error} <button className="quiet" onClick={() => void load()}>Refresh</button></p>}
    <div className="photo-grid">{photos.map((photo,index) => <div className="memory-cell" key={photo.id}>{(index === 0 || photo.date !== photos[index-1].date) && <p className="date-divider">{readableDate(photo.date)}</p>}<button className="photo-card" onClick={() => setSelected(photo)}><img loading="lazy" decoding="async" src={photo.thumbnail} alt={photo.caption || photo.filename}/><span>{photo.caption || readableDate(photo.date)}</span></button></div>)}</div>
    {loading && <p role="status">Gathering our moments…</p>}{!loading && photos.length === 0 && <p className="empty-library">The first page is waiting for you. Add a photo to begin.</p>}{next && <button className="button load-more" disabled={loading} onClick={() => void load(next)}>More memories ↓</button>}
    {selected && <PhotoDetail key={selected.id} photo={selected} csrf={csrf} close={() => setSelected(null)} saved={() => {void load();changedRef.current();}}/>}
  </section>;
}
