import { useEffect, useRef, useState } from 'react';
import { api, PhotoCard, type Photo } from './Gallery';

export function useSelection(scope: string, active = true) {
  const [enabled, setEnabled] = useState(false);
  const [ids, setIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState('');
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  useEffect(() => {setEnabled(false); setIds(new Set()); setEditing(false); setError('');}, [scope, active]);
  function toggle(id: string) {
    setError('');
    if (!ids.has(id) && ids.size >= 500) {setError('Select up to 500 memories at a time.'); return;}
    setIds(previous => {const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id); return next;});
  }
  function done() {setEnabled(false);setIds(new Set());setEditing(false);setError('');}
  return {enabled, setEnabled, ids, setIds, error, setError, editing, setEditing, saving, setSaving, toggle, done};
}
export type Selection = ReturnType<typeof useSelection>;

export function SelectionControls({selection: s, photos, disabled = false, csrf, saved}: {selection: Selection; photos: Photo[]; disabled?: boolean; csrf: string; saved: () => void}) {
  return <div className="selection-controls">
    {!s.enabled ? <button className="quiet select-memories" disabled={disabled || !photos.length} onClick={() => s.setEnabled(true)}>Select</button> : <div className="selection-toolbar" role="group" aria-label="Selected memories">
      <span role="status">{s.ids.size} selected</span>
      <button className="quiet" disabled={s.saving} onClick={() => {if (photos.length > 500) s.setError('Select up to 500 memories at a time.'); else {s.setIds(new Set(photos.map(p => p.id)));s.setError('');}}}>Select loaded</button>
      <button className="quiet" disabled={s.saving || !s.ids.size} onClick={() => s.setIds(new Set())}>Clear</button>
      <button className="button" disabled={disabled || s.saving || !s.ids.size} onClick={() => s.setEditing(true)}>Change date</button>
      <button className="quiet" disabled={s.saving} onClick={s.done}>Done</button>
    </div>}
    {s.error && <p className="error" role="alert">{s.error}</p>}
    {s.editing && <BulkDateDialog selection={s} csrf={csrf} saved={saved}/>}
  </div>;
}
function BulkDateDialog({selection: s, csrf, saved}: {selection: Selection; csrf: string; saved: () => void}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [date, setDate] = useState('');
  const [error, setError] = useState('');
  useEffect(() => {dialog.current?.showModal(); return () => dialog.current?.close();}, []);
  async function submit(event: React.FormEvent) {
    event.preventDefault(); if (s.saving) return;
    s.setSaving(true); setError('');
    try {
      await api('/api/photos/bulk-date/', {method:'POST', headers:{'Content-Type':'application/json', 'X-CSRFToken':csrf}, body:JSON.stringify({ids:[...s.ids],date})});
      s.done(); saved();
    } catch(e) {setError((e as Error).message);} finally {s.setSaving(false);}
  }
  return <dialog ref={dialog} className="bulk-date-dialog" aria-labelledby="bulk-heading" onCancel={event => {if (s.saving) event.preventDefault();else s.setEditing(false);}}><h2 id="bulk-heading">Give these memories a date.</h2><p>This sets the same date for {s.ids.size} {s.ids.size === 1 ? 'memory' : 'memories'}. Original files and captions stay unchanged.</p><form onSubmit={submit}><label htmlFor="bulk-date">Date taken</label><input id="bulk-date" type="date" value={date} required disabled={s.saving} onChange={e => setDate(e.target.value)}/>{error && <p className="error" role="alert">{error}</p>}<div className="bulk-actions"><button type="button" className="quiet" disabled={s.saving} onClick={() => s.setEditing(false)}>Cancel</button><button className="button" disabled={s.saving}>{s.saving ? 'Saving…' : `Apply to ${s.ids.size} ${s.ids.size === 1 ? 'memory' : 'memories'}`}</button></div></form></dialog>;
}
export function SelectableMemory({photo, selection: s, open}: {photo: Photo; selection: Selection; open: () => void}) {
  return <div className={`selectable-memory ${s.ids.has(photo.id) ? 'memory-selected' : ''}`}><PhotoCard photo={photo} open={s.enabled ? () => s.toggle(photo.id) : open} selection={s.enabled ? s.ids.has(photo.id) : undefined}/>{s.enabled && <input className="memory-checkbox" type="checkbox" checked={s.ids.has(photo.id)} disabled={s.saving} aria-label={`Select ${photo.caption || photo.filename}`} onChange={() => s.toggle(photo.id)}/>}</div>;
}
