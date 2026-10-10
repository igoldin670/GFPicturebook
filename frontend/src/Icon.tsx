import type { ReactNode } from 'react';

type Name = 'album' | 'plus' | 'refresh' | 'upload' | 'close' | 'download' | 'lock';
const paths: Record<Name, ReactNode> = {
  album: <><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 3v18M11 8h6M11 12h4"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  refresh: <><path d="M20 7v5h-5M4 17v-5h5"/><path d="M6.2 6.2A8 8 0 0 1 19.7 11M4.3 13A8 8 0 0 0 17.8 17.8"/></>,
  upload: <><path d="m7 9 5-5 5 5M12 4v12M5 16v4h14v-4"/></>,
  close: <path d="m6 6 12 12M6 18 18 6"/>,
  download: <><path d="M12 4v12m-5-5 5 5 5-5M5 17v3h14v-3"/></>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></>,
};
export default function Icon({ name }: { name: Name }) {
  return <svg className="icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
