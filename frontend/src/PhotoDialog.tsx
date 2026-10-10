import { useEffect, useRef, useState } from 'react';
import { api, errorMessage } from './api';
import { readableDate } from './dates';
import Icon from './Icon';
import type { Photo } from './types';

export default function PhotoDialog({ photo, csrf, close, saved }: {
  photo: Photo; csrf: string; close: () => void; saved: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const saveRequest = useRef<AbortController | null>(null);
  const [caption, setCaption] = useState(photo.caption);
  const [date, setDate] = useState(photo.date);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const [imageAttempt, setImageAttempt] = useState(0);
  const edited = caption !== photo.caption || date !== photo.date;

  useEffect(() => {
    const node = dialog.current!;
    node.showModal();
    document.body.classList.add('dialog-open');
    return () => {
      saveRequest.current?.abort();
      node.close();
      document.body.classList.remove('dialog-open');
    };
  }, []);

  async function save(event: React.FormEvent) {
    event.preventDefault();
    const controller = new AbortController();
    saveRequest.current = controller;
    setBusy(true);
    setError('');
    try {
      await api(`/api/photos/${photo.id}/edit/`, {
        method: 'POST', signal: controller.signal,
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
        body: JSON.stringify({ caption, date }),
      });
      saved();
      close();
    } catch (error) {
      if (!controller.signal.aborted) setError(errorMessage(error));
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  return (
    <dialog ref={dialog} className="photo-dialog" aria-labelledby="photo-title"
      onCancel={event => { event.preventDefault(); close(); }}
      onClick={event => { if (event.target === event.currentTarget) close(); }}>
      <div className="dialog-layout">
        <button className="icon-button close-photo" onClick={close} aria-label="Close photo"><Icon name="close"/></button>
        <div className="photo-stage">
          {imageFailed ? <div className="image-error" role="alert">
            <p>The preview couldn’t be loaded.</p>
            <button className="secondary-button" onClick={() => { setImageFailed(false); setImageAttempt(n => n + 1); }}>Try again</button>
          </div> : <img key={imageAttempt} className="detail-image" src={photo.preview} alt={photo.caption || photo.filename} onError={() => setImageFailed(true)}/>}
        </div>
        <div className="detail-content">
          <h2 id="photo-title">{readableDate(photo.date)}</h2>
          <p className="detail-filename">{photo.filename}</p>
          <form onSubmit={save}>
            <label htmlFor="photo-caption">Caption</label>
            <textarea id="photo-caption" value={caption} maxLength={5000} onChange={event => setCaption(event.target.value)} placeholder="Add a note about this photo" disabled={busy}/>
            <label htmlFor="photo-date">Date taken</label>
            <input id="photo-date" type="date" value={date} onChange={event => setDate(event.target.value)} required disabled={busy}/>
            <p className="field-note">{photo.dateSource === 'upload' ? 'Using the upload date. You can change it here.' : photo.dateSource === 'manual' ? 'Date edited by us.' : 'From the photo’s camera metadata.'}</p>
            {error && <p className="notice error" role="alert">{error}</p>}
            <button className="button save-photo" disabled={busy || !edited}>{busy ? 'Saving…' : 'Save changes'}</button>
          </form>
          <details className="photo-information">
            <summary>Photo information</summary>
            <dl>
              <dt>Dimensions</dt><dd>{photo.width} × {photo.height}</dd>
              {photo.camera && <><dt>Camera</dt><dd>{photo.camera}</dd></>}
              {photo.latitude !== null && photo.longitude !== null && <><dt>Location</dt><dd>{photo.latitude}, {photo.longitude}</dd></>}
            </dl>
          </details>
          <a className="download-link" href={photo.original}><Icon name="download"/>Download original</a>
          <p className="field-note">Full quality, with original metadata.</p>
        </div>
      </div>
    </dialog>
  );
}
