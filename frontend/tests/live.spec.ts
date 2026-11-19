import {test,expect} from '@playwright/test';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {join} from 'node:path';

test('built app: real uploads, metadata, video seeking, downloads and admin authorization',async({page,request})=>{
  test.skip(!process.env.ALBUM_LIVE_FIXTURES,'Requires an isolated backend, worker and synthetic upload fixtures; see docs/version-1.2.md.');
  test.setTimeout(90_000);
  const member=process.env.ALBUM_LIVE_MEMBER!,admin=process.env.ALBUM_LIVE_ADMIN!,password=process.env.ALBUM_LIVE_PASSWORD!;
  expect((await request.get('/api/admin/storage/')).status()).toBe(401);
  await page.goto('/');await page.getByLabel('Username').fill(member);await page.getByLabel('Password').fill(password);await page.getByRole('button',{name:'Step inside'}).click();
  await expect(page.getByRole('heading',{name:/The little things/})).toBeVisible();
  const names=['camera-original.jpg','undated.png','camera-video.mp4'];
  await page.getByLabel('Choose photos or videos').setInputFiles(names.map(name=>join(process.env.ALBUM_LIVE_FIXTURES!,name)));
  await expect(page.locator('.upload-progress summary')).toContainText('3 of 3 received');
  await expect.poll(async()=>page.evaluate(async()=>{const r=await fetch('/api/summary/');return (await r.json()).photos;}),{timeout:45_000}).toBe(3);
  const dated=await page.evaluate(async()=>{const r=await fetch('/api/photos/');return (await r.json()).photos;});
  expect(dated).toHaveLength(2);
  for(const media of dated){
    const original=await page.request.get(media.original);expect(original.ok()).toBeTruthy();
    const bytes=await readFile(join(process.env.ALBUM_LIVE_FIXTURES!,media.filename));
    expect(createHash('sha256').update(await original.body()).digest('hex')).toBe(createHash('sha256').update(bytes).digest('hex'));
  }
  expect((await page.request.get('/api/admin/storage/')).status()).toBe(403);
  await page.getByRole('button',{name:'Play video: camera-video.mp4'}).click();
  const video=page.locator('video');await expect(video).toBeVisible();
  await expect.poll(()=>video.evaluate((v:HTMLVideoElement)=>v.readyState)).toBeGreaterThanOrEqual(2);
  await video.evaluate(async(v:HTMLVideoElement)=>{await v.play();v.currentTime=1;});
  await expect.poll(()=>video.evaluate((v:HTMLVideoElement)=>v.currentTime)).toBeGreaterThanOrEqual(.9);
  const stream=await page.request.get(dated.find((p:{kind:string})=>p.kind==='video').playback,{headers:{Range:'bytes=0-31'}});expect(stream.status()).toBe(206);expect((await stream.body()).length).toBe(32);
  await page.keyboard.press('Escape');await page.getByRole('link',{name:/Missing dates/}).click();await expect(page.locator('.photo-card')).toHaveCount(1);
  await page.getByRole('button',{name:'Select',exact:true}).click();await page.getByRole('button',{name:'Select loaded'}).click();await page.getByRole('button',{name:'Change date'}).click();await page.getByLabel('Date taken').fill('2022-05-06');await page.getByRole('button',{name:'Apply to 1 memory'}).click();await expect(page.locator('.nav-count')).toHaveText('0');
  await page.getByRole('link',{name:'Dates',exact:true}).click();await expect(page.locator('.book-open')).toBeVisible();await expect(page.locator('.chapter-month').first()).toHaveText('May');
  await page.getByRole('button',{name:'Sign out'}).click();await page.getByLabel('Username').fill(admin);await page.getByLabel('Password').fill(password);await page.getByRole('button',{name:'Step inside'}).click();
  await page.getByRole('link',{name:'Manage our space'}).click();await expect(page.getByText('Site administration',{exact:true})).toBeVisible();
  await page.goto('/admin/storage/');await expect(page.getByRole('heading',{name:'Media archive storage',exact:true})).toBeVisible();
  if(process.env.JOURNAL_SCREENSHOTS){
    await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:join(process.env.JOURNAL_SCREENSHOTS,'admin-storage.png'),fullPage:true});
    await page.evaluate(()=>{document.documentElement.dataset.theme='dark';});await page.screenshot({path:join(process.env.JOURNAL_SCREENSHOTS,'admin-storage-dark.png'),fullPage:true});
  }
});
