import assert from 'node:assert/strict';
const {chromium}=await import(process.env.MENTOR_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,executablePath:process.env.MENTOR_BROWSER_PATH});
try{
 const page=await browser.newPage({viewport:{width:1450,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>localStorage.setItem('trellis.lang','nl'));
 let language='en',motion=true,failOnce=true;
 const profile={works_well:['Code examples with a very long observation that should wrap within the panel rather than overlapping neighboring content.'],works_poorly:['Abstract analogies'],preferences:['Concise explanations'],teaching_preferences:[],notes:''};
 await page.route('http://localhost:8000/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname,body=req.postData()?JSON.parse(req.postData()):{};
  if(req.method()==='OPTIONS'){await route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'content-type','Access-Control-Allow-Methods':'GET,PATCH,POST'}});return;}
  let data={},status=200;
  if(path==='/graph')data={nodes:[],edges:[]};
  else if(path==='/levels')data={};
  else if(path==='/journey/paul')data={goals:[],review:[],sources:[]};
  else if(path==='/journey/paul/examples')data=[];
  else if(path==='/memory/paul/profile'){
   if(body.teaching_preferences && failOnce){failOnce=false;status=503;data={detail:'Please retry saving your preference.'};}
   else{if(body.ui_language)language=body.ui_language;if(typeof body.ambient_motion==='boolean')motion=body.ambient_motion;for(const k of Object.keys(profile))if(k in body)profile[k]=body[k];data={...profile,ui_language:language,ambient_motion:motion};}
  }else if(path==='/memory/paul')data={learning_profile:profile,ui_language:language,ambient_motion:motion,concepts:[{concept:'Vectors',summary:'Een eerdere Nederlandse samenvatting.',concept_status:'learning',covered:[],struggles:[],misconceptions:[],quiz_correct:0,quiz_wrong:0}]};
  else if(path==='/translations')data={texts:body.texts};
  else throw Error(path);
  await route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(data)});
 });
 await page.goto('http://localhost:3000');
 await page.getByRole('button',{name:'My profile',exact:true}).click();
 const dialog=page.getByRole('dialog',{name:'My profile'});
 await dialog.getByRole('tab',{name:'Settings',exact:true}).waitFor();
 assert.equal(await dialog.locator('.mentor-preferences').count(),0);
 await dialog.getByRole('checkbox',{name:'Ambient motion',exact:true}).uncheck();
 await page.waitForFunction(()=>!document.querySelector('.motion-setting input').checked);
 await dialog.getByRole('tab',{name:'Teaching preferences',exact:true}).click();
 const code=dialog.getByRole('button',{name:'Code examples',exact:true});
 await code.click();await dialog.getByText('Please retry saving your preference.',{exact:true}).waitFor();
 assert.equal(await code.getAttribute('aria-pressed'),'false');
 await code.click();await page.waitForFunction(()=>document.querySelector('.preference-pill.selected')?.textContent==='Code examples');
 assert.deepEqual(profile.teaching_preferences,['Code examples']);
 await dialog.getByPlaceholder('Add your own preference').fill('Use short Python exercises');
 await dialog.getByRole('button',{name:'Add',exact:true}).click();
 await dialog.getByRole('button',{name:'Use short Python exercises',exact:true}).waitFor();
 assert.equal(await dialog.locator('.observed').count(),3);
 await dialog.getByRole('tab',{name:'Memory',exact:true}).click();
 await dialog.getByText('Een eerdere Nederlandse samenvatting.',{exact:true}).waitFor();
 await dialog.getByRole('button',{name:'Rebuild memory',exact:true}).waitFor();
 await dialog.getByRole('tab',{name:'Teaching preferences',exact:true}).click();
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 assert.equal(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth),true);
 await page.screenshot({path:'/private/tmp/profile-teaching-mobile.png',fullPage:true,animations:'disabled'});
 await dialog.getByRole('tab',{name:'Settings',exact:true}).click();
 await page.setViewportSize({width:1450,height:1000});
 await page.screenshot({path:'/private/tmp/profile-settings.png',fullPage:true,animations:'disabled'});
 assert.equal(await page.evaluate(()=>localStorage.getItem('trellis.lang')),'en');
 assert.deepEqual(errors,[]);
 console.log('PASS: focused settings, tabs, preference error/retry, custom pills, distinct observations, preserved Dutch memory, server language over stale local cache, and mobile containment.');
}finally{await browser.close();}
