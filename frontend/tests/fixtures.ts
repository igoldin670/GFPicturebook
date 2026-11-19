import { test as base, expect, type Page } from '@playwright/test';

export const sampleArt = (index = 0) => `<svg xmlns="http://www.w3.org/2000/svg" width="600" height="600"><rect width="600" height="600" fill="${['#a7bbc1','#d5b99c','#a9b3a2','#c6b3b0'][index % 4]}"/><circle cx="440" cy="130" r="55" fill="#f4e6c9"/><path d="M0 390 170 190 350 360 470 260 600 390V600H0" fill="${['#6d8b97','#a1836f','#6f8b79','#8e7e83'][index % 4]}"/><path d="M0 480Q180 340 360 470T600 440V600H0" fill="${['#3d6375','#716452','#415e50','#625462'][index % 4]}"/></svg>`;
export const memories = Array.from({length: 12}, (_, i) => ({
  id: `00000000-0000-4000-8000-${String(i + 1).padStart(12,'0')}`, filename: `sample-${i}.jpg`,
  date: i < 8 ? `2026-10-${String(i + 10).padStart(2,'0')}` : i < 10 ? '2026-09-12' : null,
  dateSource: i < 10 ? 'manual' : 'missing', caption: `Sample memory ${i + 1}`,
  width: 600, height: 600, camera: '', latitude: null, longitude: null,
  thumbnail: `/test-media/${i}.svg`, preview: `/test-media/${i}.svg`, original: `/test-media/${i}.svg`,
  kind: i % 3 === 1 ? 'video' : 'photo', duration: i % 3 === 1 ? 24 : null,
  byteSize: 1024000, playback: i % 3 === 1 ? '/test-media/sample.mp4' : null,
}));
export type DemoOptions = { signedIn?: boolean; admin?: boolean; empty?: boolean; failBulk?: boolean };
export async function mockAlbum(page: Page, options: DemoOptions = {}) {
  let signedIn = options.signedIn !== false;
  const records = structuredClone(options.empty ? [] : memories);
  const requests: string[] = [];
  await page.route('**/test-media/**', route => route.fulfill({contentType:'image/svg+xml',body:sampleArt(Number(route.request().url().match(/(\d+)\.svg/)?.[1] || 0))}));
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url()); const path = url.pathname; requests.push(path + url.search);
    const body = route.request().method() === 'POST' ? route.request().postDataJSON() : null;
    let data: unknown = {};
    if (path === '/api/login/') signedIn = true;
    if (path === '/api/logout/') signedIn = false;
    if (path === '/api/session/' || path === '/api/login/') data = {user: signedIn ? {username:'demo',isAdmin:options.admin || false} : null,csrfToken:'synthetic-test-token'};
    else if (path === '/api/summary/') data = {photos:records.length,albums:0,favorites:0,undatedCount:records.filter(p=>p.date === null).length};
    else if (path === '/api/photos/limits/') data = {photoMaxBytes:null,videoMaxBytes:107374182400,requestMaxBytes:107374182400,batchMaxFiles:100};
    else if (path === '/api/photos/uploads/') data = {uploads:[]};
    else if (path === '/api/photos/bulk-date/') {
      if(options.failBulk) return route.fulfill({status:503,json:{error:'Please retry this date change.'}});
      records.forEach(p => {if(body.ids.includes(p.id)){p.date=body.date;p.dateSource='manual';}}); data={updated:body.ids.length,date:body.date};
    } else if (path.endsWith('/edit/')) { const p=records.find(p=>path.includes(p.id)); if(p) Object.assign(p,body); data={}; }
    else if (path === '/api/photos/months/') {
      const counts = new Map<string,number>();
      records.filter(p=>p.date && (!url.searchParams.get('kind') || p.kind===url.searchParams.get('kind'))).forEach(p=>{const m=p.date!.slice(0,7);counts.set(m,(counts.get(m)||0)+1);});
      data={months:[...counts].sort().map(([month,count])=>({month,count}))};
    } else if (path === '/api/photos/') {
      const matching=records.filter(p=>(url.searchParams.has('undated') ? p.date===null : p.date!==null) && (!url.searchParams.get('kind') || p.kind===url.searchParams.get('kind')) && (!url.searchParams.get('month') || p.date?.startsWith(url.searchParams.get('month')!)));
      const offset=url.searchParams.has('cursor')?6:0;
      data={photos:matching.slice(offset,offset+6),count:matching.length,next:matching.length>offset+6?'synthetic-next':null};
    }
    await route.fulfill({json:data});
  });
  return {records,requests};
}
export const test = base.extend<{album: Awaited<ReturnType<typeof mockAlbum>>}>({
  album: async ({page}, use) => { await use(await mockAlbum(page)); },
});
export { expect };
