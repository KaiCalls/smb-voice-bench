const [reportPath,outputPath,fixturePath,playwrightModule,firefoxExecutable,chromeExecutable]=process.argv.slice(2);
if(!reportPath||!outputPath||!fixturePath)throw new Error('Usage: node browser_qa.cjs REPORT OUTPUT FIXTURES [PLAYWRIGHT_MODULE FIREFOX_EXECUTABLE CHROME_EXECUTABLE]');
const {chromium,firefox}=require(playwrightModule||'playwright');
const fs=require('fs');const path=require('path');const http=require('http');const assert=require('assert');
const root=path.resolve(reportPath);
const out=path.resolve(outputPath);
const fixtures=path.resolve(fixturePath);
const results=[];
const server=http.createServer((req,res)=>{const pathname=decodeURIComponent(new URL(req.url,'http://localhost').pathname);const file=path.join(root,pathname==='/'?'index.html':pathname);if(!file.startsWith(root+path.sep)){res.writeHead(403).end();return;}try{const data=fs.readFileSync(file);res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.json')?'application/json':'text/html');res.end(data);}catch{res.writeHead(404).end();}});
(async()=>{
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const port=server.address().port;
 for(const [name,engine] of [['chromium',chromium],['firefox',firefox]]){
  const browser=await engine.launch(name==='chromium'?{headless:true,...(chromeExecutable?{executablePath:chromeExecutable}:{})}:{headless:true,...(firefoxExecutable?{executablePath:firefoxExecutable}:{})});
  const browserVersion=browser.version();
  for(const mode of ['file','loopback'])for(const width of [375,1280]){
   const context=await browser.newContext({viewport:{width,height:900}});const page=await context.newPage();const errors=[];const external=[];
   page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().startsWith('http')&&!r.url().startsWith('http://127.0.0.1:'))external.push(r.url());});
   const url=mode==='file'?'file://'+root+'/index.html':`http://127.0.0.1:${port}/`;
   await page.goto(url);await page.getByRole('heading',{name:'Did the change complete the work?'}).waitFor();
   await page.getByRole('combobox',{name:'Filter scenario'}).selectOption('unknown-write-reconciliation');
   assert.equal(await page.locator('.comparison-card').count(),1);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'horizontal overflow');
   await page.keyboard.press('Tab');assert.equal(await page.evaluate(()=>document.activeElement.tagName!=='BODY'),true);
   if(mode==='file')await page.screenshot({path:out+`/comparison-${name}-${width}.png`,fullPage:true});
   await page.getByRole('link',{name:/reference-bad · fail/}).first().click();
   await page.getByRole('heading',{name:'The booking is complete.'}).waitFor();
   assert((await page.locator('.stat').allTextContents()).some(t=>t.includes('2Create decisions')));
   assert.equal(await page.locator('audio').count(),0);assert((await page.locator('main').textContent()).includes('Audio unavailable'));
   assert.equal(await page.locator('details[open] summary').filter({hasText:'Immutable independent attempt audit'}).count(),1);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'run horizontal overflow');
   if(mode==='file')await page.screenshot({path:out+`/evidence-${name}-${width}.png`,fullPage:true});
   const audit=page.locator('details').filter({has:page.locator('summary',{hasText:'Immutable independent attempt audit'})}).first();await audit.locator('summary').focus();await page.keyboard.press('Enter');assert.equal(await audit.getAttribute('open'),null);await page.keyboard.press('Enter');
   assert.deepEqual(errors,[]);assert.deepEqual(external,[]);results.push({browser:name,browser_version:browserVersion,mode,width,status:'pass',external_requests:0,script_errors:0});await context.close();
  }
  const context=await browser.newContext();const page=await context.newPage();
  await page.goto('file://'+fixtures+'/attack/index.html');await page.locator('.event').first().waitFor();
  assert.equal(await page.locator('.event').count(),500);assert.equal(await page.evaluate(()=>globalThis.benchXss),undefined);assert.equal(await page.locator('script').count(),2);
  await page.getByRole('button',{name:'Next →'}).focus();await page.keyboard.press('Enter');assert((await page.locator('.event').count())<500);
  await page.goto('file://'+fixtures+'/audio/index.html');await page.locator('audio').first().waitFor();assert.equal(await page.locator('audio').count(),3);
  const eventButton=page.getByRole('button',{name:'0.400s · speech.segment',exact:true});await eventButton.focus();await page.keyboard.press('Enter');
  assert(Math.abs(await page.locator('audio').first().evaluate(a=>a.currentTime)-.4)<.025);assert.equal(await page.locator('audio').first().evaluate(a=>a.paused),true);
  results.push({browser:name,browser_version:browserVersion,hostile_text:'inert',event_page_limit:500,keyboard_navigation:'pass',verified_audio_seek:'pass',autoplay:false});
  await context.close();await browser.close();
 }
 fs.writeFileSync(out+'/browser-qa.json',JSON.stringify(results,null,2));console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1;}).finally(()=>server.close());
