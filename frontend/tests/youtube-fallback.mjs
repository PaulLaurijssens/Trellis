// Isolated UI regression for unified search and the learning sidebar.
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.MENTOR_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.MENTOR_BROWSER_PATH?{executablePath:process.env.MENTOR_BROWSER_PATH}:{})});
try {
 const page=await browser.newPage({viewport:{width:1600,height:1050}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(12000);
 await page.addInitScript(()=>localStorage.setItem('trellis.lang','en'));
 const nodes=[{id:'v',name:'Vectors',status:'learning'},{id:'a',name:'Attention',status:'queued'},{id:'r',name:'Robotics',status:'queued'}];
 await page.route('http://localhost:8000/**',async route=>{
  const path=decodeURIComponent(new URL(route.request().url()).pathname);
  if(route.request().method()==='OPTIONS'){await route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'content-type'}});return;}
  let data;
  if(path==='/ingest/youtube'){await route.fulfill({status:503,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify({detail:'YouTube is blocking automatic transcript retrieval.'})});return;}
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
 await page.getByText('Automatic retrieval failed. If YouTube offers Show transcript, copy its text and paste it here instead.',{exact:true}).waitFor();
 assert.equal(await page.locator('#add-yt').inputValue(),url);
 await page.getByRole('button',{name:'Paste transcript instead',exact:true}).click();
 assert.equal(await page.locator('#add-url').inputValue(),url);
 assert.equal(await page.locator('#add-type').inputValue(),'youtube');
 await page.getByRole('textbox',{name:'Transcript',exact:true}).fill('0:00\nthis is a transcript');
 assert.deepEqual(errors,[]);console.log('PASS: blocked import retains URL and switches to transcript with YouTube provenance.');
}finally{await browser.close();}
