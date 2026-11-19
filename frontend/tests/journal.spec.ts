import { test, expect, mockAlbum } from './fixtures';

for (const width of [320,390,768,1440,1920]) {
  test(`journal fits ${width}px and keeps full cards clickable`, async ({page,album}) => {
    await page.setViewportSize({width,height:900});await page.goto('/');
    const first=page.getByRole('button',{name:'Open photo: Sample memory 1',exact:true});await expect(first).toBeVisible();
    await page.evaluate(()=>document.fonts.ready);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    const box=(await first.boundingBox())!;
    if(width>=1440) expect(box.y+box.height).toBeLessThan(900);
    await first.click({position:{x:box.width/2,y:box.height-12}});
    await expect(page.getByRole('dialog')).toBeVisible();await expect(page.getByRole('link',{name:/Download unchanged/})).toBeVisible();
    await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0);
    await page.getByRole('link',{name:'Dates',exact:true}).click();await expect(page.locator('.book-open')).toBeVisible();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth)).toBeTruthy();
    const photo=page.locator('.book-page-right .photo-card').first();await photo.click();await expect(page.getByRole('dialog')).toBeVisible();
    await page.keyboard.press('Escape');
    const nav=await page.locator('.book-navigation').boundingBox(),book=await page.locator('.memory-book').boundingBox();
    if(width<=1100) expect(nav!.y).toBeGreaterThanOrEqual(book!.y+book!.height-5);
    expect(album.requests.length).toBeGreaterThan(0);
  });
}

test('filters follow sections and missing-date assignment updates chapters', async ({page,album})=>{
  await page.goto('/');await page.getByRole('button',{name:'Videos',exact:true}).click();
  await expect(page.locator('.photo-card')).toHaveCount(3);
  await page.getByRole('link',{name:/Missing dates/}).click();await expect(page.locator('.photo-card')).toHaveCount(1);
  await expect(page.locator('.nav-count')).toHaveText('2');await expect(page.getByText('1 need dates',{exact:true})).toBeVisible();
  await page.getByRole('button',{name:'Select',exact:true}).click();await page.getByRole('button',{name:'Select loaded'}).click();await page.getByRole('button',{name:'Change date'}).click();
  await page.getByLabel('Date taken').fill('2025-12-31');await page.getByRole('button',{name:'Apply to 1 memory'}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);await expect(page.locator('.photo-card')).toHaveCount(0);await expect(page.locator('.nav-count')).toHaveText('1');
  await page.getByRole('link',{name:'Dates',exact:true}).click();await expect(page.locator('.book-open')).toBeVisible();
  await expect(page.getByRole('button',{name:'Videos',exact:true})).toHaveAttribute('aria-pressed','true');
  await page.getByLabel('Year',{exact:true}).selectOption('2025');await expect(page.locator('.chapter-month').first()).toHaveText('December');
  expect(album.records.find(p=>p.date==='2025-12-31')?.dateSource).toBe('manual');
});

test('selection spans loaded pages and clears when leaving its scope',async({page,album})=>{
  await page.goto('/');await page.getByRole('button',{name:'Select',exact:true}).click();
  await page.getByRole('checkbox').first().check();await page.getByRole('button',{name:'More memories'}).click();
  await expect(page.locator('.photo-card')).toHaveCount(10);await expect(page.getByRole('checkbox').first()).toBeChecked();
  await page.getByRole('button',{name:'Select loaded'}).click();await expect(page.getByText('10 selected',{exact:true})).toBeVisible();
  await page.getByRole('link',{name:'Dates',exact:true}).click();await page.getByRole('link',{name:'Memories',exact:true}).click();
  await expect(page.getByRole('checkbox')).toHaveCount(0);expect(album.records.length).toBe(12);
});

test('date failures retain both selection and entered date',async({page})=>{
  await mockAlbum(page,{failBulk:true});await page.goto('/#missing-dates');
  await page.getByRole('button',{name:'Select',exact:true}).click();await page.getByRole('button',{name:'Select loaded'}).click();await page.getByRole('button',{name:'Change date'}).click();
  await page.getByLabel('Date taken').fill('2020-01-02');await page.getByRole('button',{name:'Apply to 2 memories'}).click();
  await expect(page.getByRole('alert')).toContainText('Please retry');await expect(page.getByLabel('Date taken')).toHaveValue('2020-01-02');
  await expect(page.getByText('2 selected',{exact:true})).toBeVisible();
});

test('book keyboard, focus and repeated turns keep full polaroids usable',async({page,album})=>{
  await page.goto('/#dates');await expect(page.locator('.book-open')).toBeVisible();
  const next=page.locator('.book-navigation button').last();const previous=page.locator('.book-navigation button').first();
  await expect(next).toBeDisabled();await previous.focus();await page.keyboard.press('ArrowLeft');await expect(page.locator('.chapter-month').first()).toHaveText('September');
  await expect(next).toBeFocused();
  await page.getByLabel('Year',{exact:true}).focus();await page.keyboard.press('ArrowRight');await expect(page.locator('.chapter-month').first()).toHaveText('September');
  await next.focus();await page.keyboard.press('ArrowRight');await expect(page.locator('.chapter-month').first()).toHaveText('October');
  for(let i=0;i<2;i++){await previous.click();await next.click();}
  const card=page.locator('.book-page-right .photo-card').first();const b=(await card.boundingBox())!;
  await card.click({position:{x:b.width/2,y:b.height-18}});await expect(page.getByRole('dialog')).toBeVisible();await page.keyboard.press('Escape');
  await expect(page.getByRole('heading',{name:/a page of their own/})).toBeVisible();expect(album.requests.length).toBeGreaterThan(0);
});

test('empty galleries and unauthorized member navigation expose no storage controls',async({page})=>{
  await mockAlbum(page,{empty:true});await page.goto('/');await expect(page.locator('.empty-library')).toBeVisible();
  await expect(page.getByRole('link',{name:'Manage our space'})).toHaveCount(0);
  await page.getByRole('link',{name:'Dates',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'No dated memories'})).toBeVisible();
});

test('interactive login cascade plays once and cleans up on logout',async({page})=>{
  await page.emulateMedia({reducedMotion:'no-preference'});await mockAlbum(page,{signedIn:false});await page.goto('/');
  await page.getByLabel('Username').fill('demo');await page.getByLabel('Password').fill('synthetic-only');await page.getByRole('button',{name:'Step inside'}).click();
  await expect(page.locator('.falling-memory')).toHaveCount(48);await expect(page.locator('.sign-in-flutter')).toHaveAttribute('aria-hidden','true');
  await expect(page.locator('.sign-in-flutter')).toHaveCount(0,{timeout:6000});await page.reload();await expect(page.locator('.photo-card').first()).toBeVisible();await expect(page.locator('.sign-in-flutter')).toHaveCount(0);
  await page.getByRole('button',{name:'Sign out'}).click();await expect(page.getByRole('button',{name:'Step inside'})).toBeVisible();
});

test('reduced-motion login skips cascade and exposes a settled book',async({page})=>{
  await mockAlbum(page,{signedIn:false});await page.goto('/');await page.getByLabel('Username').fill('demo');await page.getByLabel('Password').fill('synthetic-only');await page.getByRole('button',{name:'Step inside'}).click();
  await expect(page.locator('.photo-card').first()).toBeVisible();await expect(page.locator('.sign-in-flutter')).toHaveCount(0);
  await page.getByRole('link',{name:'Dates',exact:true}).click();await expect(page.locator('.book-open')).toBeVisible();
});

test('upload remains active through navigation and retry stays available',async({page,album})=>{
  let received=false;let release!:()=>void;const hold=new Promise<void>(resolve=>release=resolve);
  await page.route('**/api/photos/upload/',async route=>{received=true;await hold;await route.fulfill({status:202,json:{id:'sample-upload'}});});
  await page.goto('/');await page.getByLabel('Choose photos or videos').setInputFiles({name:'sample.jpg',mimeType:'image/jpeg',buffer:Buffer.from('synthetic-upload')});
  await expect.poll(()=>received).toBeTruthy();await page.getByRole('link',{name:'Dates',exact:true}).click();release();
  await page.getByRole('link',{name:'Memories',exact:true}).click();await expect(page.locator('.upload-progress summary')).toContainText('1 of 1 received');
  await page.route('**/api/photos/upload/',route=>route.fulfill({status:503,json:{error:'Upload test failure'}}));
  await page.getByLabel('Choose photos or videos').setInputFiles({name:'sample-retry.jpg',mimeType:'image/jpeg',buffer:Buffer.from('synthetic-upload')});
  await expect(page.getByRole('button',{name:'Retry unsuccessful uploads'})).toBeVisible();expect(album.requests.length).toBeGreaterThan(0);
});

test('animated cover and page turns remain usable under CPU throttling',async({page,album})=>{
  await page.emulateMedia({reducedMotion:'no-preference'});
  const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setCPUThrottlingRate',{rate:4});
  await page.goto('/#dates');await expect(page.locator('.book-open')).toBeVisible({timeout:10_000});
  const previous=page.locator('.book-navigation button').first(),next=page.locator('.book-navigation button').last();await expect(previous).toBeEnabled();
  await previous.click();await expect(page.locator('.turning-leaf')).toHaveAttribute('aria-hidden','true');
  await expect(page.locator('.book-spread')).toHaveAttribute('inert','');await expect(previous).toBeDisabled();await expect(next).toBeDisabled();
  await page.keyboard.press('ArrowRight');await expect(page.locator('.turning-leaf')).toHaveCount(0,{timeout:10_000});
  await expect(page.locator('.chapter-month').first()).toHaveText('September');
  await next.click();await expect(page.locator('.turning-leaf')).toHaveCount(0,{timeout:10_000});await expect(page.locator('.chapter-month').first()).toHaveText('October');
  await page.locator('.book-page-right .photo-card').first().click();await expect(page.getByRole('dialog')).toBeVisible();expect(album.requests.length).toBeGreaterThan(0);
});

test('Dates shortcuts ignore modifiers, repeats, selection mode and dialogs',async({page,album})=>{
  await page.goto('/#dates');await expect(page.locator('.book-open')).toBeVisible();
  const previous=page.locator('.book-navigation button').first();await previous.focus();
  await page.keyboard.press('Control+ArrowLeft');await expect(page.locator('.chapter-month').first()).toHaveText('October');
  await page.evaluate(()=>window.dispatchEvent(new KeyboardEvent('keydown',{key:'ArrowLeft',repeat:true,bubbles:true})));await expect(page.locator('.chapter-month').first()).toHaveText('October');
  await page.getByRole('button',{name:'Select',exact:true}).click();await page.keyboard.press('ArrowLeft');await expect(page.locator('.chapter-month').first()).toHaveText('October');
  await page.getByRole('button',{name:'Done',exact:true}).click();await page.locator('.book-page-right .photo-card').first().click();
  await page.getByLabel('A few words about this day').focus();await page.keyboard.press('ArrowLeft');await expect(page.locator('.chapter-month').first()).toHaveText('October');
  await page.keyboard.press('Escape');expect(album.requests.length).toBeGreaterThan(0);
});
