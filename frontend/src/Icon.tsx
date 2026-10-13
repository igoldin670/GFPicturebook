import type { SVGProps } from 'react';

type Name = 'orbit' | 'spark' | 'photo' | 'book' | 'upload' | 'plus' | 'arrow' | 'external' | 'logout' | 'play' | 'film' | 'close' | 'lock';
const paths: Record<Name, React.ReactNode> = {
  orbit: <><circle cx="12" cy="12" r="6.7"/><ellipse cx="12" cy="12" rx="11" ry="3.5" transform="rotate(-40 12 12)"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="20" cy="5" r="1.7" fill="currentColor" stroke="none"/></>,
  spark: <path d="m12 3 2.8 6.2L21 12l-6.2 2.8L12 21l-2.8-6.2L3 12l6.2-2.8Z"/>,
  photo: <><rect x="3" y="3" width="18" height="18" rx="3"/><circle cx="8" cy="8" r="1.5"/><path d="m3 16 5-5 4 4 4-5 5 6"/></>,
  book: <><path d="M12 5v16M12 6C9 4 5 4 2 5v14c3-1 7-1 10 1 3-2 7-2 10-1V5c-3-1-7-1-10 1Z"/><path d="M5 9h4M15 9h4"/></>,
  upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/></>,
  plus: <path d="M12 5v14M5 12h14"/>,
  arrow: <path d="M4 12h16m-6-6 6 6-6 6"/>,
  external: <><path d="M14 4h6v6m0-6L10 14M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-4"/></>,
  logout: <><path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4m5-14 5 6-5 6M9 12h11"/></>,
  play: <path d="m9 5 11 7-11 7Z" fill="currentColor" stroke="none"/>,
  film: <><rect x="3" y="4" width="18" height="16" rx="2"/><path d="M7 4v16M17 4v16M3 9h4M3 15h4M17 9h4M17 15h4"/></>,
  close: <path d="m6 6 12 12M18 6 6 18"/>,
  lock: <><rect x="5" y="10" width="14" height="11" rx="3"/><path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3"/></>,
};
export default function Icon({name, className = '', ...props}: {name: Name} & SVGProps<SVGSVGElement>) {
  return <svg className={`icon ${className}`} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false" {...props}>{paths[name]}</svg>;
}
