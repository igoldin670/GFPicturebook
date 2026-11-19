import {mkdir} from 'node:fs/promises';
import {test,expect,mockAlbum} from './fixtures';

test('capture journal review screens with synthetic memories',async({page})=>{
  test.skip(!process.env.JOURNAL_SCREENSHOTS,'Set JOURNAL_SCREENSHOTS to save review artifacts.');
  const out=process.env.JOURNAL_SCREENSHOTS!;await mkdir(out,{recursive:true});await mockAlbum(page);
  for(const width of [320,390,768,1440,1920]){
    await page.setViewportSize({width,height:1000});await page.goto('/');await expect(page.locator('.photo-card').first()).toBeVisible();await page.evaluate(()=>document.fonts.ready);
    await page.screenshot({path:`${out}/memories-${width}.png`,fullPage:true});
    await page.getByRole('link',{name:'Dates',exact:true}).click();await expect(page.locator('.book-open')).toBeVisible();await page.screenshot({path:`${out}/dates-${width}.png`,fullPage:true});
    if(width===390 || width===1440){
      await page.getByRole('link',{name:/Missing dates/}).click();await expect(page.locator('.photo-card').first()).toBeVisible();await page.screenshot({path:`${out}/missing-dates-${width}.png`,fullPage:true});
      await page.locator('.photo-card').first().click();await expect(page.getByRole('dialog')).toBeVisible();await page.screenshot({path:`${out}/lightbox-${width}.png`});await page.keyboard.press('Escape');
    }
  }
  await page.getByRole('button',{name:'Sign out'}).click();
  for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:1000});await page.screenshot({path:`${out}/sign-in-${width}.png`,fullPage:true});}
});
