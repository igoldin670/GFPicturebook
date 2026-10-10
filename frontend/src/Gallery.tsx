import { useCallback, useEffect, useRef, useState } from 'react';
import { api, errorMessage } from './api';
import { readableDate } from './dates';
import Icon from './Icon';
import PhotoDialog from './PhotoDialog';
import type { Job, Page, Photo, Transfer } from './types';

function uploadFile(item: Transfer, csrf: string, signal: AbortSignal, progress: (percent: number) => void) {
  return new Promise<void>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/photos/upload/');
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('X-CSRFToken', csrf);
    xhr.setRequestHeader('Idempotency-Key', item.id);
    xhr.setRequestHeader('X-Filename', encodeURIComponent(item.file.name));
    xhr.timeout = 120000;
    xhr.upload.onprogress = event => {
      if (event.lengthComputable) progress(Math.round(event.loaded / event.total * 100));
    };
    const abort = () => xhr.abort();
    signal.addEventListener('abort', abort, { once: true });
    xhr.onloadend = () => signal.removeEventListener('abort', abort);
    xhr.onload = () => {
      if (signal.aborted) return reject(new Error('Upload stopped.'));
      if (xhr.status === 202) return resolve();
      if (xhr.status === 401) window.dispatchEvent(new Event('session-expired'));
      let message = xhr.status === 413 ? 'Maximum photo size is 50 MiB.' : 'Upload failed. Please try again.';
      try { message = JSON.parse(xhr.responseText).error || message; } catch { /* Proxy errors may be plain text. */ }
      reject(new Error(message));
    };
    xhr.onerror = () => reject(new Error('Connection lost. You can safely retry.'));
    xhr.ontimeout = () => reject(new Error('Upload timed out. You can safely retry.'));
    xhr.onabort = () => reject(new Error('Upload stopped.'));
    if (signal.aborted) reject(new Error('Upload stopped.'));
    else xhr.send(item.file);
  });
}

function PhotoCard({ photo, open }: { photo: Photo; open: () => void }) {
  const [failed, setFailed] = useState(false);
  return <button className="photo-card" onClick={open} aria-label={`Open ${photo.caption || photo.filename}`}>
    {failed ? <span className="thumbnail-error">Preview unavailable</span> : <img
      src={photo.thumbnail} loading="lazy" decoding="async" alt={photo.caption || photo.filename}
      onError={() => setFailed(true)}/>}
    {photo.caption && <span className="photo-caption">{photo.caption}</span>}
  </button>;
}

export default function Gallery({ csrf }: { csrf: string }) {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [count, setCount] = useState<number | null>(null);
  const [next, setNext] = useState<string | null>(null);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [selected, setSelected] = useState<Photo | null>(null);
  const picker = useRef<HTMLInputElement>(null);
  const uploadController = useRef<AbortController | null>(null);
  const pageController = useRef<AbortController | null>(null);
  const statusController = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const busy = useRef(false);
  const refreshPending = useRef(false);
  const pendingSignature = useRef('');
  const dragDepth = useRef(0);

  const load = useCallback(async (cursor?: string) => {
    // A replaced request cannot overwrite a newer page or a metadata correction.
    pageController.current?.abort();
    const controller = new AbortController();
    pageController.current = controller;
    setLoading(true);
    try {
      const [page, summary] = await Promise.all([
        api<Page>(`/api/photos/${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ''}`, { signal: controller.signal }),
        api<{ photos: number }>('/api/summary/', { signal: controller.signal }),
      ]);
      if (controller.signal.aborted || !mounted.current) return;
      setPhotos(previous => cursor
        ? [...previous, ...page.photos.filter(photo => !previous.some(old => old.id === photo.id))]
        : page.photos);
      setCount(summary.photos);
      setNext(page.next);
      setError('');
    } catch (error) {
      if (!controller.signal.aborted && mounted.current) setError(errorMessage(error));
    } finally {
      if (pageController.current === controller && mounted.current) setLoading(false);
    }
  }, []);

  const poll = useCallback(async () => {
    if (statusController.current) return;
    const controller = new AbortController();
    statusController.current = controller;
    try {
      const result = await api<{ uploads: Job[] }>('/api/photos/uploads/', { signal: controller.signal });
      if (controller.signal.aborted || !mounted.current) return;
      const signature = result.uploads.filter(job => job.status === 'pending' || job.status === 'processing')
        .map(job => job.id).sort().join(',');
      if (refreshPending.current || pendingSignature.current !== signature) void load();
      refreshPending.current = false;
      pendingSignature.current = signature;
      setJobs(result.uploads);
    } catch (error) {
      if (!controller.signal.aborted && mounted.current) setError(errorMessage(error));
    } finally {
      if (statusController.current === controller) statusController.current = null;
    }
  }, [load]);

  useEffect(() => {
    mounted.current = true;
    void load();
    void poll();
    const timer = window.setInterval(() => { if (!document.hidden) void poll(); }, 4000);
    return () => {
      mounted.current = false;
      window.clearInterval(timer);
      pageController.current?.abort();
      statusController.current?.abort();
      statusController.current = null;
      uploadController.current?.abort();
    };
  }, [load, poll]);

  function update(id: string, patch: Partial<Transfer>) {
    if (mounted.current) setTransfers(items => items.map(item => item.id === id ? { ...item, ...patch } : item));
  }

  async function send(items: Transfer[]) {
    if (busy.current) return;
    busy.current = true;
    setUploading(true);
    const controller = new AbortController();
    uploadController.current = controller;
    // Send one file at a time. Retrying reuses its identity and cannot duplicate receipt.
    for (const item of items) {
      if (controller.signal.aborted) break;
      update(item.id, { state: 'sending', error: undefined });
      try {
        if (item.file.size > 50 * 1024 * 1024) throw new Error('Maximum photo size is 50 MiB.');
        await uploadFile(item, csrf, controller.signal, percent => update(item.id, { progress: percent }));
        update(item.id, { state: 'accepted', progress: 100 });
        refreshPending.current = true;
        void poll();
      } catch (error) {
        update(item.id, { state: 'error', error: errorMessage(error) });
      }
    }
    busy.current = false;
    if (mounted.current) {
      setUploading(false);
      void poll();
      void load();
    }
  }

  function choose(files: FileList | null) {
    if (!files?.length || busy.current) return;
    if (files.length > 100) {
      setError('Choose up to 100 photos at a time.');
      return;
    }
    const items: Transfer[] = Array.from(files).map(file => ({
      id: crypto.randomUUID(), file, progress: 0, state: 'queued',
    }));
    setTransfers(items);
    setError('');
    void send(items);
  }

  const groups: { date: string; photos: Photo[] }[] = [];
  for (const photo of photos) {
    const last = groups[groups.length - 1];
    if (last?.date === photo.date) last.photos.push(photo);
    else groups.push({ date: photo.date, photos: [photo] });
  }
  const pending = jobs.filter(job => job.status !== 'failed').length;
  const failed = jobs.filter(job => job.status === 'failed').length;
  const received = transfers.filter(item => item.state === 'accepted').length;
  const extraJobs = jobs.filter(job => !transfers.some(item => item.id === job.id));
  const activity = uploading ? `Uploading ${received + 1} of ${transfers.length}`
    : pending ? `Processing ${pending} ${pending === 1 ? 'photo' : 'photos'}`
    : failed ? `${failed} ${failed === 1 ? 'photo needs' : 'photos need'} attention` : 'Upload complete';

  return (
    <section className={`library${dragging ? ' is-dragging' : ''}`}
      onDragEnter={event => {
        if (event.dataTransfer.types.includes('Files')) { event.preventDefault(); dragDepth.current++; setDragging(true); }
      }}
      onDragOver={event => { if (event.dataTransfer.types.includes('Files')) event.preventDefault(); }}
      onDragLeave={() => { if (--dragDepth.current <= 0) { dragDepth.current = 0; setDragging(false); } }}
      onDrop={event => { event.preventDefault(); dragDepth.current = 0; setDragging(false); choose(event.dataTransfer.files); }}>
      <div className="library-heading">
        <div><h1>Our photos</h1><p className="collection-count">{count === null ? 'Our shared collection' : `${count.toLocaleString()} ${count === 1 ? 'photo' : 'photos'}`}<span className="sort-label">Latest first</span></p></div>
        <div className="library-actions">
          <button className="icon-button" title="Refresh photos" aria-label="Refresh photos" disabled={loading} onClick={() => { void load(); void poll(); }}><Icon name="refresh"/></button>
          <button className="button" disabled={uploading} onClick={() => picker.current?.click()}><Icon name="plus"/>Add photos</button>
        </div>
      </div>
      <input className="file-picker" ref={picker} type="file" accept="image/jpeg,image/mpo,image/png,image/webp,image/heic,image/heif,.mpo,.heic,.heif" multiple
        onChange={event => { choose(event.target.files); event.target.value = ''; }} aria-label="Choose photos"/>
      <div className={`upload-area${photos.length === 0 && !loading ? ' empty-upload' : ''}`}>
        <Icon name="upload"/>
        <div><p>{dragging ? 'Drop photos to upload' : photos.length === 0 && !loading ? 'Add your first photos' : 'Drop photos here, or choose from your library.'}</p><span>JPEG, PNG, WebP & HEIC · up to 50 MiB each</span></div>
        <button className="text-button" disabled={uploading} onClick={() => picker.current?.click()}>Choose photos</button>
      </div>
      {(transfers.length > 0 || jobs.length > 0) && <details className="upload-activity" open={uploading || pending > 0 || transfers.some(item => item.state === 'error')}>
        <summary><span>{activity}</span>{failed > 0 && pending > 0 && <span className="activity-failures">{failed} failed</span>}</summary>
        <ul>{transfers.map(item => {
          const job = jobs.find(job => job.id === item.id);
          const label = item.state === 'sending' ? `${item.progress}%` : item.state === 'error' ? item.error
            : item.state === 'queued' ? 'Waiting to upload' : job?.message || 'Uploaded';
          return <li key={item.id}><div className="activity-row"><span>{item.file.name}</span><span className={item.state === 'error' || job?.status === 'failed' ? 'activity-error' : 'activity-state'}>{label}</span></div>
            {item.state === 'sending' && <progress max={100} value={item.progress} aria-label={`Uploading ${item.file.name}`}/>}</li>;
        })}{extraJobs.map(job => <li key={job.id}><div className="activity-row"><span>{job.filename}</span><span className={job.status === 'failed' ? 'activity-error' : 'activity-state'}>{job.message}</span></div></li>)}</ul>
        <div className="activity-actions">
          {transfers.some(item => item.state === 'error') && <button className="text-button" disabled={uploading} onClick={() => void send(transfers.filter(item => item.state === 'error'))}>Retry failed uploads</button>}
          {transfers.length > 0 && !uploading && <button className="text-button" onClick={() => setTransfers([])}>Clear upload list</button>}
        </div>
      </details>}
      {error && <p className="notice error" role="alert">{error}</p>}
      <div className="photo-collection">{groups.map(group => <section className="day-group" key={group.date} aria-label={readableDate(group.date)}>
        <div className="day-heading"><h2><time dateTime={group.date}>{readableDate(group.date)}</time></h2><span>{group.photos.length} {group.photos.length === 1 ? 'photo' : 'photos'}</span></div>
        <div className="photo-grid">{group.photos.map(photo => <PhotoCard key={photo.id} photo={photo} open={() => setSelected(photo)}/>)}</div>
      </section>)}</div>
      {loading && <p className="page-status" role="status">Loading photos…</p>}
      {next && <button className="secondary-button load-more" disabled={loading} onClick={() => void load(next)}>{loading ? 'Loading…' : 'Load more photos'}</button>}
      <p className="backup-note">Keep a separate copy of your photos. Automatic backups aren’t set up yet.</p>
      {selected && <PhotoDialog key={selected.id} photo={selected} csrf={csrf} close={() => setSelected(null)} saved={() => void load()}/>}
    </section>
  );
}
