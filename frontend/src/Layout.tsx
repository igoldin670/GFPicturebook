import type { MouseEvent, ReactNode } from 'react';
import Icon from './Icon';

export function Brand() {
  return <a className="brand" href="/" aria-label="Our little album home"><Icon name="orbit"/><span>our little album<span className="brand-dot">.</span></span></a>;
}

export function AlbumNavigation({section, undatedCount, navigate}: {
  section: string; undatedCount: number;
  navigate: (event: MouseEvent<HTMLAnchorElement>, target: string) => void;
}) {
  return <nav className="album-navigation" aria-label="Album sections"><div className="album-navigation-inner">
    <div className="rail-inscription" aria-hidden="true"><Icon name="orbit"/><span>Our days,<br/><em>together.</em></span></div>
    <a href="#memories" aria-current={section === 'memories' ? 'page' : undefined} onClick={event => navigate(event, 'memories')}><Icon name="photo"/>Memories</a>
    <a className="missing-dates-link" href="#missing-dates" aria-current={section === 'missing-dates' ? 'page' : undefined} onClick={event => navigate(event, 'missing-dates')}><span>Missing dates</span><span className="nav-count">{undatedCount}</span></a>
    <a href="#dates" aria-current={section === 'dates' ? 'page' : undefined} onClick={event => navigate(event, 'dates')}><Icon name="book"/>Dates</a>
    <div id="dates-sidebar" className="dates-sidebar-host"/>
    <span className="rail-binding" aria-hidden="true"/>
  </div></nav>;
}

export function PageTitle({id, children}: {id: string; children: ReactNode}) {
  return <h1 id={id} tabIndex={-1} className="page-title">{children}</h1>;
}

export function JournalCover() {
  return <div className="journal-cover"><Icon name="orbit"/><h1>For the moments<br/><em>that become us.</em></h1><p>Our little album</p><span className="journal-stitch" aria-hidden="true"/></div>;
}
