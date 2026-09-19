// Isolated UI regression for unified search and the learning sidebar.
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.MENTOR_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.MENTOR_BROWSER_PATH?{executablePath:process.env.MENTOR_BROWSER_PATH}:{})});
try {
 const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(12000);
 await page.addInitScript(()=>localStorage.setItem('dendrite.lang','en'));
 const nodes=[{id:'v',name:'Vectors',status:'learning'},{id:'a',name:'Attention',status:'queued'},{id:'r',name:'Robotics',status:'queued'}];
 await page.route('http://localhost:8000/**',async route=>{
  const path=decodeURIComponent(new URL(route.request().url()).pathname);
  if(route.request().method()==='OPTIONS'){await route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'content-type'}});return;}
  let data;
  if(path==='/ingest/youtube'){await new Promise(resolve=>setTimeout(resolve,2200));await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify({source_id:'fixture',title:'Video analysis fixture',candidates:[{name:'AI safety',definition:'Understanding risks',context:'[AI video analysis — paraphrase, not a verified quotation] Discusses risk',importance:3,aliases:[],mentions:[{start_sec:12,quote:'',provenance:'ai_video_analysis'}]}],candidate_relations:[],meta:{analysis_method:'ai_video_analysis',chunks:1}})});return;}
  else if(path.startsWith('/ingest/status/'))data={phase:'video',done:0,total:0};
  else if(path==='/graph')data={nodes,edges:[{source:'v',target:'a',type:'PREREQUISITE_OF'}]};
  else if(path==='/levels')data={1:'First steps',2:'Foundations',3:'Practical',4:'Technical',5:'Advanced'};
  else if(path.startsWith('/memory/'))data={ui_language:'en',ambient_motion:false,learning_profile:{},concepts:[]};
  else if(path==='/journey/paul')data={active_goal:null,goals:[],recent:{concept:'Vectors',consolidated:false},review:[],sources:[]};
  else if(path==='/journey/paul/examples')data=[];
  else if(path.startsWith('/concept/'))data={...nodes.find(n=>n.name===path.slice(9)),definition:'A useful topic with connections.',mentions:[{source:'Fixture source',context:'Stored source context'}]};
  else if(path.startsWith('/chat/'))data={session_id:null,messages:[],state:{},suggestions:[]};
  else if(path==='/translations')data={texts:JSON.parse(route.request().postData()).texts};
  else throw Error('Unexpected request '+path);
  await route.fulfill({status:200,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(data)});
 });
 await page.goto('http://localhost:3000');
 await page.getByRole('button',{name:/^Add/}).click();
 await page.getByRole('tab',{name:'YouTube',exact:true}).click();
 const url='https://www.youtube.com/watch?v=AxzcWOxzkiw';
 await page.locator('#add-yt').fill(url);
 await page.locator('.cmd-actions .btn').click();
 await page.locator('.import-progress').waitFor();
 assert.match(await page.locator('.import-progress').innerText(),/Analysis is running/);
 const card=await page.locator('.cmd-card').boundingBox(), box=await page.locator('.cmd.open').boundingBox();
 assert.ok(Math.abs(card.width-box.width)<4,'form must fill its container');
 await page.screenshot({path:'/private/tmp/import-processing-desktop.png',fullPage:true});
 await page.getByText('AI video analysis · paraphrases, not verified captions. Timestamps are approximate.',{exact:true}).waitFor();
 await page.getByRole('heading',{name:'Video analysis fixture',exact:true}).waitFor();
 await page.screenshot({path:'/private/tmp/review-spaced-desktop.png',fullPage:true});
 assert.equal(await page.locator('.review-commit').isDisabled(),true);
 await page.getByRole('button',{name:'Select all',exact:true}).click();
 assert.equal(await page.locator('.review-commit').isEnabled(),true);
 await page.setViewportSize({width:390,height:844});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.screenshot({path:'/private/tmp/review-spaced-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);console.log('PASS: direct-video result opens existing review with provenance label.');
}finally{await browser.close();}
