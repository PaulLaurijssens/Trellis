// Phase 3 browser flow. All API requests intercepted; no real learner data written.
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.MENTOR_PLAYWRIGHT_MODULE||'playwright');
const browser=await chromium.launch({headless:true,...(process.env.MENTOR_BROWSER_PATH?{executablePath:process.env.MENTOR_BROWSER_PATH}:{})});
try {
 const page=await browser.newPage({viewport:{width:1536,height:1050}}), errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.setDefaultTimeout(12000);
 await page.addInitScript(()=>{localStorage.setItem('dendrite.lang','en');sessionStorage.setItem('dendrite.learningTrail.paul','["Robotics"]');});
 const nodes=[{id:'r',name:'Robotics',status:'queued'},{id:'v',name:'Vectors',status:'learning'},{id:'a',name:'Attention',status:'queued'}];
 const messages={Robotics:[],Vectors:[],Attention:[]};
 let saved=[],goal=null, goals=[],createFail=true,lastQuestion='',proposals=[];
 const journey=()=>({active_goal:goal,goals,recent:{concept:'Robotics',consolidated:false},review:[{concept:'Vectors',date:'2026-01-01',quote:'I can apply the dot product.'}],sources:[{id:'paper',title:'Attention paper'}]});
 await page.route('http://localhost:8000/**',async route=>{
  const req=route.request(),path=decodeURIComponent(new URL(req.url()).pathname),body=req.postData()?JSON.parse(req.postData()):{};
  if(req.method()==='OPTIONS'){await route.fulfill({status:204,headers:{'Access-Control-Allow-Origin':'*','Access-Control-Allow-Headers':'content-type','Access-Control-Allow-Methods':'GET,POST,PATCH,DELETE,OPTIONS'}});return;}
  let data={},status=200;
  if(path==='/levels')data={1:'First steps',2:'Foundations',3:'Practical',4:'Technical',5:'Advanced'};
  else if(path==='/graph')data={nodes,edges:[{source:'v',target:'a',type:'PREREQUISITE_OF'}]};
  else if(path.startsWith('/memory/'))data={ui_language:'en',ambient_motion:false,learning_profile:{},concepts:[]};
  else if(path.startsWith('/concept/'))data={...nodes.find(n=>n.name===path.slice(9)),definition:'A topic to explore.',mentions:[{source:'Attention paper',context:'A saved summary.',mentions:[{quote:'Exact source words.'}]}]};
  else if(path==='/journey/paul')data=journey();
  else if(path==='/journey/paul/goals'){
   if(createFail){createFail=false;status=503;data={detail:'Could not save this goal. Try again.'};}
   else{goal={id:'g',title:body.title,status:'active',source_title:'Attention paper',steps:[{concept_id:'v',name:'Vectors',for_concept:'Attention',reason:'A basis for attention scores.',done:false},{concept_id:'a',name:'Attention',done:false}]};goals=[goal];data=goal;}
  }else if(path==='/journey/paul/goals/g'){
   if(body.concept_id)goals[0].steps.find(s=>s.concept_id===body.concept_id).done=body.done;
   if(body.status){goals[0].status=body.status;goal=body.status==='active'?goals[0]:null;}data=goals[0];
  }else if(path==='/journey/paul/examples'){
   if(req.method()==='POST'){const text=messages[body.session_id][body.seq].content;saved=[{id:'e',session_id:body.session_id,seq:body.seq,concept:body.session_id,original:text,text,date:'2026-09-13'}];data=saved[0];}else data=saved;
  }else if(path==='/journey/paul/examples/e'){
   if(req.method()==='DELETE')saved=[];else{saved[0].text=body.text;saved[0].corrected_at='2026-09-13';}data={updated:true};
  }else if(path==='/chat'){
   lastQuestion=body.message;const m=messages[body.concept];m.push({seq:m.length,role:'user',content:body.message});m.push({seq:m.length,role:'assistant',content:'Vectors describe direction and magnitude. Think of an arrow pointing from your robot to its destination.'});
   proposals=[{id:'p',name:'Vectors',definition:'Direction and magnitude.',reason:'Useful for robot movement.',relation:'PREREQUISITE_OF',direction:'suggested_to_current',state:'pending'}];data={answer:m.at(-1).content,suggestions:proposals};
  }else if(path.startsWith('/chat/')){const name=path.slice(6);data={session_id:name,messages:messages[name],suggestions:name==='Robotics'?proposals:[],state:{covered:[]}};}
  else if(path==='/translations')data={texts:JSON.parse(req.postData()).texts};
  else throw Error('Unexpected request '+path);
  await route.fulfill({status,contentType:'application/json',headers:{'Access-Control-Allow-Origin':'*'},body:JSON.stringify(data)});
 });
 await page.goto(process.env.MENTOR_TEST_URL||'http://localhost:3000');
 await page.getByRole('button',{name:'Suggest connections',exact:true}).click();
 await page.getByText('Useful for robot movement.',{exact:true}).waitFor();
 assert.match(lastQuestion,/prerequisites and related topics/);
 await page.getByRole('button',{name:'This helped me — save',exact:true}).click();
 await page.getByRole('button',{name:'Saved as a helpful example ✓',exact:true}).waitFor();
 await page.locator('.helpful-examples > summary').click();
 await page.locator('.helpful-examples').getByRole('button',{name:'Edit',exact:true}).click();
 await page.getByLabel('Edit example',{exact:true}).fill('An arrow from robot to target.');
 await page.locator('.helpful-examples').getByRole('button',{name:'Save',exact:true}).click();
 await page.getByText('An arrow from robot to target.',{exact:true}).waitFor();
 assert.match(saved[0].original,/Think of an arrow/);
 await page.locator('.helpful-examples').getByRole('button',{name:'Remove',exact:true}).click();
 await page.getByRole('button',{name:'This helped me — save',exact:true}).waitFor();
 await page.locator('.lesson-context details').filter({has:page.locator('.sources')}).locator('summary').first().click();
 await page.getByRole('button',{name:'Discuss this source →',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.msg.user').length===2);
 assert.match(lastQuestion,/saved excerpts from “Attention paper”/);
 await page.getByRole('navigation',{name:'Workspace'}).getByRole('button',{name:'Explore',exact:true}).click();
 assert.equal(await page.locator('.atlas-scope').count(),0);
 await page.getByRole('button',{name:'New learning goal or question +',exact:true}).click();
 await page.getByLabel('What would you like to understand?',{exact:true}).fill('Understand attention in this paper');
 await page.getByLabel('Source (optional)',{exact:true}).selectOption('paper');
 await page.locator('.goal-form').getByRole('button',{name:'Save',exact:true}).click();
 await page.getByText('Could not save this goal. Try again.',{exact:true}).waitFor();
 await page.screenshot({path:'/private/tmp/phase3-goal-retry.png',fullPage:true});
 assert.equal(await page.getByLabel('What would you like to understand?',{exact:true}).inputValue(),'Understand attention in this paper');
 await page.locator('.goal-form').getByRole('button',{name:'Save',exact:true}).click();
 await page.locator('.learning-sidebar .goal-card h3').waitFor();
 assert.equal(goal.title,'Understand attention in this paper');
 await page.locator('.learning-sidebar .goal-card').getByText('View learning route · 2',{exact:true}).click();
 await page.locator('.learning-sidebar .goal-card input[type=checkbox]').first().click();
 await page.waitForFunction(()=>document.querySelector('.learning-sidebar .goal-card input[type=checkbox]')?.checked);
 assert.equal(goal.steps[0].done,true);
 await page.locator('.learning-sidebar .goal-card').getByRole('button',{name:'Pause goal',exact:true}).click();
 await page.getByText('Saved learning goals',{exact:true}).click();
 await page.locator('.saved-goal').getByRole('button',{name:'Resume',exact:true}).click();
 await page.locator('.learning-sidebar .goal-card h3').waitFor();
 await page.reload();
 await page.getByRole('navigation',{name:'Workspace'}).getByRole('button',{name:'Explore',exact:true}).click();
 await page.locator('.learning-sidebar .goal-card h3').waitFor();
 await page.getByText('Revisit something?',{exact:true}).click();
 await page.locator('.review-option').getByRole('button',{name:'Vectors →',exact:true}).click();
 await page.getByRole('button',{name:'Try a short review',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('.msg.user')?.textContent.includes('briefly revisit'));
 assert.match(lastQuestion,/briefly revisit/);
 await page.locator('.chat-log').evaluate(el=>el.scrollTop=0);
 await page.screenshot({path:'/private/tmp/phase3-mentor.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});
 await page.getByRole('navigation',{name:'Workspace'}).getByRole('button',{name:'Explore',exact:true}).click();
 await page.locator('.learning-sidebar').waitFor({state:'visible'});
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.screenshot({path:'/private/tmp/phase3-mobile.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('PASS: connection proposals, source question, helpful-example save/edit/delete, simplified browsing, goal error/retry, route completion, pause/resume, refresh persistence, optional review and mobile layout.');
}finally{await browser.close();}
