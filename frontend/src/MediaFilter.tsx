export type MediaKind = '' | 'photo' | 'video';
export type FilterProps = {kind: MediaKind; setKind: (kind: MediaKind) => void};
export default function MediaFilter({kind, setKind, disabled = false}: FilterProps & {disabled?: boolean}) {
  return <div className="media-filter" role="group" aria-label="Media type">{([['', 'All'], ['photo', 'Photos'], ['video', 'Videos']] as const).map(([value,label]) => <button key={value} type="button" aria-pressed={kind === value} disabled={disabled} onClick={() => setKind(value)}>{label}</button>)}</div>;
}
