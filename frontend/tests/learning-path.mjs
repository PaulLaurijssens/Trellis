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
  if(path==='/curriculum')data={coverage:3,conflicts:[],groups:[{title:'Shared foundations',stage:0,ids:['v'],reason:'Background for the rest'},{title:'AI mechanisms',stage:1,ids:['a'],reason:'Build on foundations'},{title:'Robotics branch',stage:3,ids:['r'],reason:'Specialized application'}]};
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
 await page.getByRole('button',{name:'Learning path',exact:true}).click();
 await page.getByRole('heading',{name:'From foundations to new frontiers',exact:true}).waitFor();
 assert.equal(await page.locator('.map-group').count(),3);
 await page.getByRole('button',{name:'Start with: Vectors →',exact:true}).waitFor();
 const toggle=await page.locator('.explore-view-switch').boundingBox(), search=await page.locator('.cmd-wrap').boundingBox();
 assert.ok(Math.abs(toggle.y-search.y)<5,'toggle aligned with search');
 const vp=page.locator('.map-viewport');
 assert.ok(await vp.evaluate(el=>el.scrollWidth>el.clientWidth+500),'canvas must extend horizontally');
 const box=await vp.boundingBox();
 await page.mouse.move(box.x+box.width-60,box.y+box.height-40);
 await page.mouse.down();await page.mouse.move(box.x+box.width-300,box.y+box.height-40,{steps:5});await page.mouse.up();
 assert.ok(await vp.evaluate(el=>el.scrollLeft)>100,'empty-space dragging pans right');
 await page.getByRole('button',{name:'My next step',exact:true}).click();
 assert.equal(await page.locator('.map-topic-list').count(),1);
 await page.getByRole('button',{name:'Zoom in',exact:true}).click();
 await page.getByRole('button',{name:'Overview',exact:true}).click();
 assert.equal(await page.locator('.map-topic-list').count(),0);
 await page.getByRole('button',{name:'My next step',exact:true}).click();
 await page.getByRole('button',{name:'Close group',exact:true}).click();
 await page.screenshot({path:'/private/tmp/whole-roadmap.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.waitForTimeout(300);
 assert.ok(await page.locator('.map-mobile-stage').count()>0);
 const dims=await page.locator('.map-viewport').evaluate(el=>({w:el.clientWidth,h:el.clientHeight,sw:el.scrollWidth}));
 await page.screenshot({path:'/private/tmp/roadmap-mobile.png'});
 assert.ok(dims.h>100,'mobile map has usable height');
 assert.ok(dims.sw<=dims.w+2,'mobile map fits width');
 await page.setViewportSize({width:1600,height:1050});
 await page.getByRole('button',{name:'Start with: Vectors →',exact:true}).click();
 await page.locator('.lesson-main').waitFor();
 assert.deepEqual(errors,[]);console.log('PASS: graph/path switch, prerequisite recommendation and mentor entry.');
}finally{await browser.close();}
