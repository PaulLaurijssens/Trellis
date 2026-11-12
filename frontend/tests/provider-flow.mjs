// Setup with a live key test, provider errors in the UI language, and the AI provider card in Settings.
// Run against `next start` on :3000 with the API mocked: node tests/provider-flow.mjs
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.MENTOR_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,executablePath:process.env.MENTOR_BROWSER_PATH});
const PROVIDERS={gemini:{label:'Google Gemini',key_env:'GEMINI_API_KEY',key_hint:'Create a key.',mentor:'gemini/pro',extract:'gemini/flash',embed:'gemini/emb',embed_dim:3072},
 openai:{label:'OpenAI',key_env:'OPENAI_API_KEY',key_hint:'Create a key.',mentor:'openai/gpt',extract:'openai/mini',embed:'openai/emb',embed_dim:3072},
 anthropic:{label:'Anthropic Claude',key_env:'ANTHROPIC_API_KEY',key_hint:'Create a key.',mentor:'anthropic/s',extract:'anthropic/h',embed:null,embed_dim:null}};
const check=(name,ok,code)=>({name,model:'gemini/'+name,ok,code:ok?null:code,params:{retry_after:null},message:'English fallback'});
try{
 var page=await browser.newPage({viewport:{width:1300,height:1000}}),errors=[],calls=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&!m.text().startsWith('Failed to load resource'))errors.push(m.text());});
 let authed=false,settings={provider:'gemini',embed_provider:'gemini',mentor_key_set:true,mentor_key_tail:'wxyz',embed_key_set:false,embed_key_tail:'',models:{mentor:'gemini/pro',extract:'gemini/flash',embed:'gemini/emb',embed_dim:3072}};
 await page.route('http://localhost:8000/**',async route=>{
  const req=route.request(),path=new URL(req.url()).pathname,body=req.postData()?JSON.parse(req.postData()):{};
  if(req.method()==='OPTIONS'){await route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'http://localhost:3000','Access-Control-Allow-Credentials':'true','Access-Control-Allow-Headers':'content-type','Access-Control-Allow-Methods':'GET,PATCH,POST,PUT'}});return;}
  calls.push({path,body});
  let data={},status=200;
  if(path==='/auth/status')data={setup_needed:!authed,authenticated:authed,person:authed?{id:'paul',name:'Paul',language:'en',is_admin:true}:null,profiles:[],providers:PROVIDERS,embedding_providers:['gemini','openai'],configured:false};
  else if(path==='/auth/check-provider'){
   if(body.mentor_key==='bad')data={ok:false,checks:[check('extract',false,'provider.auth'),check('mentor',false,'provider.auth'),check('embed',false,'provider.auth')],key_hint:{code:'key.looksAzure',params:{}},suggest:null};
   else if(body.mentor_key==='busy')data={ok:false,checks:[check('extract',true),check('mentor',false,'provider.busy'),check('embed',true)],key_hint:null,suggest:null};
   else if(body.mentor_key==='free'&&!body.mentor_model)data={ok:false,checks:[check('extract',true),check('mentor',false,'provider.quotaZero'),check('embed',true)],key_hint:null,suggest:{mentor_model:'gemini/flash',reason:'provider.quotaZero'}};
   else data={ok:true,checks:[check('extract',true),check('mentor',true),check('embed',true)],key_hint:null,suggest:null};
  }
  else if(path==='/auth/setup'){authed=true;data={person:{id:'paul',name:'Paul',language:'en',is_admin:true}};}
  else if(path==='/auth/settings'&&req.method()==='PUT'){status=409;data={detail:'Vector index has 3072 dimensions'};}
  else if(path==='/auth/settings')data=settings;
  else if(path==='/auth/me')data={person:{id:'paul',name:'Paul',language:'en',is_admin:true},settings};
  else if(path==='/admin/backups')data={available:false,backups:[]};
  else if(path==='/health')data={ok:true,version:'0.4.0',commit:'abcdef123'};
  else if(path==='/graph')data={nodes:[],edges:[]};
  else if(path==='/levels')data={};
  else if(path==='/journey/paul')data={goals:[],review:[],sources:[]};
  else if(path==='/journey/paul/examples')data=[];
  else if(path==='/memory/paul')data={learning_profile:{},ui_language:'en',ambient_motion:true,concepts:[]};
  else if(path.startsWith('/teach/'))data={enabled:false,lessons:0,estimated_usd:0,total:0,cached:0,model:'x',price_per_mtok:{input:0,output:0}};
  else if(path==='/curriculum')data={groups:[]};
  else if(path==='/ingest/raw'){status=502;data={detail:{code:'provider.auth',params:{provider:'openai',model:'openai/mini',retry_after:null,stage:'extract'},message:'English'}};}
  else data={};
  await route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'http://localhost:3000','Access-Control-Allow-Credentials':'true'},body:JSON.stringify(data)});
 });
 await page.goto('http://localhost:3000');
 await page.getByLabel('Your name').fill('Paul');
 await page.getByRole('button',{name:'Next'}).click();
 // The Claude note is visible before picking it.
 assert.ok(await page.locator('option',{hasText:'Anthropic Claude (needs a second key)'}).count());
 const next=page.getByRole('button',{name:/^(Next|Continue anyway)$/});
 assert.equal(await next.isDisabled(),true);
 await page.getByLabel(/^API key/).fill('bad');
 await page.getByRole('button',{name:'Test connection'}).click();
 await page.getByText('This key looks like an Azure').waitFor();
 assert.equal(await page.locator('.provider-checks li.fail').count(),3);
 if(process.env.SHOTS)await page.screenshot({path:process.env.SHOTS+'/setup-failed.png',fullPage:true});
 assert.equal(await next.isDisabled(),true);
 // Editing resets the result.
 await page.getByLabel(/^API key/).fill('busy');
 assert.equal(await page.locator('.provider-checks').count(),0);
 await page.getByRole('button',{name:'Test connection'}).click();
 await page.getByRole('button',{name:'Continue anyway'}).waitFor();
 // Free tier: offer the extract model as mentor, which re-tests.
 await page.getByLabel(/^API key/).fill('free');
 await page.getByRole('button',{name:'Test connection'}).click();
 await page.getByRole('button',{name:/Use gemini\/flash as the mentor/}).click();
 await page.getByText('All three models answered').waitFor();
 assert.equal(calls.filter(c=>c.path==='/auth/check-provider').at(-1).body.mentor_model,'gemini/flash');
 await page.getByRole('button',{name:'Next'}).click();
 await page.getByLabel(/^Password/).fill('long-password');
 await page.getByLabel('Repeat the password').fill('long-password');
 await page.getByRole('button',{name:'Finish setup'}).click();
 await page.getByRole('button',{name:'My profile',exact:true}).waitFor();
 const setup=calls.find(c=>c.path==='/auth/setup').body;
 assert.equal(setup.mentor_model,'gemini/flash'); assert.equal(setup.mentor_key,'free');
 // Learn is off with an empty map, and says why.
 await page.waitForFunction(()=>document.querySelector('.workspace-header nav button[aria-describedby]')?.title==='Add a source first: Learn needs at least one concept on the map');
 assert.equal(await page.locator('#learn-hint').textContent(),'Add a source first: Learn needs at least one concept on the map');
 // Settings: provider card, test again, change, 409 in plain words, version and report link.
 await page.getByRole('button',{name:'My profile',exact:true}).click();
 const card=page.locator('.provider-card');
 await card.getByText('•••• wxyz').waitFor();
 await card.getByRole('button',{name:'Test again'}).click();
 await card.getByText('All three models answered').waitFor();
 assert.equal(calls.filter(c=>c.path==='/auth/check-provider').at(-1).body.use_stored_keys,true);
 await card.getByRole('button',{name:'Change'}).click();
 await card.getByLabel(/^Provider/).selectOption('openai');
 assert.equal(await card.getByRole('button',{name:'Test connection'}).isDisabled(),true);
 await card.getByLabel(/^API key/).fill('good');
 await card.getByRole('button',{name:'Test connection'}).click();
 await card.getByRole('button',{name:'Save'}).click();
 await card.getByText('You cannot switch to a provider with a different embedding size').waitFor();
 await page.getByText('Trellis 0.4.0').waitFor();
 if(process.env.SHOTS)await card.screenshot({path:process.env.SHOTS+'/settings-card.png'});
 const href=await page.getByRole('link',{name:/Report a problem/}).getAttribute('href');
 assert.match(href,/template=bug_report\.yml&version=0\.4\.0%20\(abcdef1\)&environment=Browser%3A/);
 assert.ok(!href.includes('good')&&!href.includes('wxyz'));
 assert.deepEqual(errors,[]);
 console.log('provider flow ok');
}catch(e){console.log("page errors:",errors);if(process.env.SHOT)await browser.contexts()[0]?.pages()[0]?.screenshot({path:process.env.SHOT,fullPage:true});throw e;}finally{await browser.close();}
